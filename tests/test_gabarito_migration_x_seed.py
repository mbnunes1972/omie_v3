"""docs/db/TAREFA_CENTRO_CUSTO_2.md, item 4 — "o gabarito em dois lugares".

`PLANO_PADRAO`/`CENTRO_CUSTO_PADRAO`/`CLASSIFICACAO_GRUPO5_V1` (mod_contabil.py, o que o
seed-on-first-access grava numa loja nova) e a cadeia de migrations (o que `alembic upgrade
head` grava num ambiente reconstruido) descrevem o MESMO gabarito por dois caminhos
independentes. Se divergirem, uma loja criada pela tela nasce com um plano de contas
diferente do de um ambiente reconstruido — e a diferença só aparece meses depois, num
relatório que não fecha.

Constrói `orizon_baseline_teste` do zero só com `alembic upgrade head` (mesmo utilitário do
B2 — nunca escreve id de revisão à mão) e compara, por owner_tipo, contra o que o código
produziria hoje para um owner novo:
- centro_custo: mesmos códigos, mesmos nomes, mesmo pai (por código).
- conta: mesmos códigos, nomes, grupo, tipo, natureza contábil e pai.
- classificação do grupo 5: mesmo centro de custo e natureza de custo por código.

Isto vale mais que corrigir os defeitos individuais (item 1: nome de 1.1.09/2.1.09) — fecha a
CLASSE: qualquer novo código futuro acrescentado só de um lado dos dois vira falha aqui, no
mesmo dia, em vez de divergência silenciosa entre "loja reconstruída" e "loja nova".
"""

import pytest
from sqlalchemy import create_engine, text

from _schema_util import baseline_urls, construir_schema_do_zero
import mod_contabil as mc


def _pai_codigo(codigo):
    return mc._pai_codigo(codigo)


def _gabarito_centro_custo_esperado():
    return {codigo: (nome, _pai_codigo(codigo)) for codigo, nome in mc.CENTRO_CUSTO_PADRAO}


def _gabarito_conta_esperado():
    codigos = {c for c, _ in mc.PLANO_PADRAO}
    esperado = {}
    for codigo, nome in mc.PLANO_PADRAO:
        grupo = int(codigo.split(".")[0])
        tipo = "sintetica" if any(o.startswith(codigo + ".") for o in codigos) else "analitica"
        cc_codigo, nat_custo = mc.CLASSIFICACAO_GRUPO5_V1.get(codigo, (None, None))
        esperado[codigo] = (nome, grupo, tipo, mc._natureza(grupo), _pai_codigo(codigo),
                             cc_codigo, nat_custo)
    return esperado


def _snapshot_construido(psycopg_url):
    """{(owner_tipo, owner_id): ({codigo: (nome, pai_codigo)}, {codigo: (nome, grupo, tipo,
    natureza, pai_codigo, cc_codigo, natureza_custo)})} do banco construido so' por migrations."""
    eng = create_engine(psycopg_url)
    with eng.connect() as conn:
        cc_rows = conn.execute(text(
            "SELECT id, owner_tipo, owner_id, codigo, nome, pai_id FROM centro_custo"
        )).mappings().all()
        cc_by_id = {r["id"]: r for r in cc_rows}

        conta_rows = conn.execute(text("""
            SELECT c.id, c.owner_tipo, c.owner_id, c.codigo, c.nome, c.grupo, c.tipo,
                   c.natureza, c.pai_id, cc.codigo AS cc_codigo, c.natureza_custo
            FROM conta c LEFT JOIN centro_custo cc ON cc.id = c.centro_custo_id
        """)).mappings().all()
        conta_by_id = {r["id"]: r for r in conta_rows}
    eng.dispose()

    owners = {(r["owner_tipo"], r["owner_id"]) for r in cc_rows} | \
             {(r["owner_tipo"], r["owner_id"]) for r in conta_rows}

    out = {}
    for owner_tipo, owner_id in owners:
        cc_map = {
            r["codigo"]: (r["nome"], cc_by_id[r["pai_id"]]["codigo"] if r["pai_id"] else None)
            for r in cc_rows if (r["owner_tipo"], r["owner_id"]) == (owner_tipo, owner_id)
        }
        conta_map = {
            r["codigo"]: (r["nome"], r["grupo"], r["tipo"], r["natureza"],
                          conta_by_id[r["pai_id"]]["codigo"] if r["pai_id"] else None,
                          r["cc_codigo"], r["natureza_custo"])
            for r in conta_rows if (r["owner_tipo"], r["owner_id"]) == (owner_tipo, owner_id)
        }
        out[(owner_tipo, owner_id)] = (cc_map, conta_map)
    return out


def test_gabarito_da_migration_bate_com_plano_padrao_e_centro_custo_padrao():
    try:
        alembic_url, psycopg_url = baseline_urls()
    except RuntimeError as e:
        pytest.skip(str(e))

    construir_schema_do_zero(alembic_url, psycopg_url)
    construido = _snapshot_construido(psycopg_url)

    assert construido, (
        "Banco construido so' por `alembic upgrade head` nao tem NENHUM owner com "
        "centro_custo/conta — a migration de dado nao rodou ou nao semeou nada."
    )

    cc_esperado = _gabarito_centro_custo_esperado()
    conta_esperado = _gabarito_conta_esperado()

    divergencias = []
    for (owner_tipo, owner_id), (cc_real, conta_real) in sorted(construido.items()):
        owner = f"{owner_tipo},{owner_id}"

        for codigo in set(cc_esperado) | set(cc_real):
            if cc_esperado.get(codigo) != cc_real.get(codigo):
                divergencias.append(
                    f"centro_custo[{owner}][{codigo}]: PLANO_PADRAO(codigo)="
                    f"{cc_esperado.get(codigo)!r} vs construido={cc_real.get(codigo)!r}"
                )

        for codigo in set(conta_esperado) | set(conta_real):
            if conta_esperado.get(codigo) != conta_real.get(codigo):
                divergencias.append(
                    f"conta[{owner}][{codigo}]: PLANO_PADRAO/CLASSIFICACAO_GRUPO5_V1="
                    f"{conta_esperado.get(codigo)!r} vs construido={conta_real.get(codigo)!r}"
                )

    assert not divergencias, (
        f"Gabarito da migration diverge do gabarito de mod_contabil.py "
        f"({len(divergencias)} diferenca(s)) — uma loja nova (seed-on-first-access) e uma "
        "loja reconstruida (migrations) nasceriam com planos diferentes:\n"
        + "\n".join(sorted(divergencias))
    )
