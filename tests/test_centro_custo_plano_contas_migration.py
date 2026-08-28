"""Critério de aceite de docs/db/TAREFA_CENTRO_CUSTO.md, virado teste — mesmo método do B2
(tests/test_schema_boot_estavel.py), agora aplicado a DADO em vez de schema: constrói
`orizon_baseline_teste` do zero só com `alembic upgrade head` e compara `conta`/`centro_custo`
contra o localhost (banco do `DATABASE_URL` do `.env`) por CHAVE NATURAL — nunca por id, que
diverge entre ambientes por construção. Existe pra não depender de alguém lembrar de rodar a
comparação a mão antes de promover a migration de dado pra Integração/Homologação.

Chave natural (mesma da migration `c1ab3f8007c4`, mesma do critério de aceite):
- centro_custo: owner_tipo, owner_id, nome do nó + nome do pai.
- conta: owner_tipo, owner_id, codigo, nome, natureza, tipo, natureza_custo + caminho de centro
  de custo (nome do nó + nome do pai) — não o id de nenhum dos dois.

A comparação é restrita aos OWNERS que o banco construído produz (docs/db/TAREFA_CENTRO_CUSTO_2.md
item 5): `46a93cfd591b` deriva owners de `redes`/`lojas` do próprio ambiente, e o build daqui não
tem dado de instância (redes/lojas nascem vazias, fora do escopo de migration — regra R6). O
localhost real tem MAIS owners do que os 3 originais (qualquer loja real de verdade ganha
gabarito agora) — isso é o item 5 funcionando, não uma divergência a cobrar aqui. A garantia de
"owner dinâmico recebe gabarito completo" tem teste próprio, com owners sintéticos que não
existem no localhost: tests/test_gabarito_migration_por_owner_dinamico.py.

Roda inteiramente contra `orizon_baseline_teste` (nunca o banco principal nem o `orizon_test` do
resto da suíte) — mesma cautela de test_schema_boot_estavel.py.
"""

import os
import re

import pytest
from sqlalchemy import create_engine, text

from _schema_util import baseline_urls, construir_schema_do_zero, REPO_ROOT


def _database_url_local():
    """URL do banco principal (localhost) — o `DATABASE_URL` do `.env`, sem trocar o database
    (ao contrário de `baseline_urls()`, que deriva o `orizon_baseline_teste`)."""
    env_path = os.path.join(REPO_ROOT, ".env")
    if not os.path.exists(env_path):
        raise RuntimeError("Sem .env — nao da pra achar o banco local pra comparar.")
    with open(env_path, encoding="utf-8") as f:
        m = re.search(r"DATABASE_URL\s*=\s*['\"]?(postgresql[^'\"\s]+)", f.read())
    if not m:
        raise RuntimeError("Sem DATABASE_URL no .env.")
    return m.group(1).replace("+psycopg2", "")


def _snapshot(psycopg_url):
    """(centro_custo_por_chave_natural, conta_por_chave_natural) — ver docstring do módulo."""
    eng = create_engine(psycopg_url)
    with eng.connect() as conn:
        cc_rows = conn.execute(text(
            "SELECT id, owner_tipo, owner_id, nome, pai_id FROM centro_custo"
        )).mappings().all()
        cc_by_id = {r["id"]: r for r in cc_rows}
        centro_custo = {}
        for r in cc_rows:
            pai_nome = cc_by_id[r["pai_id"]]["nome"] if r["pai_id"] else None
            centro_custo[(r["owner_tipo"], r["owner_id"], r["nome"])] = pai_nome

        conta_rows = conn.execute(text("""
            SELECT c.owner_tipo, c.owner_id, c.codigo, c.nome, c.natureza, c.tipo,
                   c.natureza_custo, cc.nome AS cc_nome, cc_pai.nome AS cc_pai_nome
            FROM conta c
            LEFT JOIN centro_custo cc ON cc.id = c.centro_custo_id
            LEFT JOIN centro_custo cc_pai ON cc_pai.id = cc.pai_id
        """)).mappings().all()
        conta = {
            (r["owner_tipo"], r["owner_id"], r["codigo"]): (
                r["nome"], r["natureza"], r["tipo"], r["natureza_custo"],
                r["cc_nome"], r["cc_pai_nome"],
            )
            for r in conta_rows
        }
    eng.dispose()
    return centro_custo, conta


def test_migration_de_dado_reproduz_centro_custo_e_conta_do_localhost():
    try:
        alembic_url, psycopg_url = baseline_urls()
        url_local = _database_url_local()
    except RuntimeError as e:
        pytest.skip(str(e))

    construir_schema_do_zero(alembic_url, psycopg_url)

    cc_local, conta_local = _snapshot(url_local)
    cc_teste, conta_teste = _snapshot(psycopg_url)

    if not conta_local:
        pytest.skip(
            "Localhost sem plano de contas — nada de real pra comparar (este teste valida a "
            "migration contra o dado de referência do ambiente de desenvolvimento)."
        )

    # so' os owners que o proprio banco construido produz (ver docstring do modulo) — localhost
    # pode ter MAIS owners (lojas reais de verdade), isso e' esperado e nao e' o que se testa aqui.
    owners_construido = {(ot, oid) for (ot, oid, _cod) in conta_teste} | \
                        {(ot, oid) for (ot, oid, _nome) in cc_teste}
    assert owners_construido, (
        "Banco construido nao produziu NENHUM owner com centro_custo/conta — "
        "a cadeia de migrations de dado nao rodou ou nao semeou nada."
    )

    divergencias = []
    for chave in set(cc_local) | set(cc_teste):
        if chave[:2] not in owners_construido:
            continue
        if cc_local.get(chave) != cc_teste.get(chave):
            divergencias.append(f"centro_custo{chave}: local={cc_local.get(chave)!r} "
                                 f"vs construido={cc_teste.get(chave)!r}")
    for chave in set(conta_local) | set(conta_teste):
        if chave[:2] not in owners_construido:
            continue
        if conta_local.get(chave) != conta_teste.get(chave):
            divergencias.append(f"conta{chave}: local={conta_local.get(chave)!r} "
                                 f"vs construido={conta_teste.get(chave)!r}")

    assert not divergencias, (
        f"Migration nao reproduz o localhost, para os owners que ela produz "
        f"({len(divergencias)} diferenca(s) por chave natural):\n" + "\n".join(sorted(divergencias))
    )
