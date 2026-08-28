"""docs/db/TAREFA_CENTRO_CUSTO_2.md, item 5 — a migration de gabarito NAO pode enumerar owners.

`c1ab3f8007c4` conhece 3 owners fixos (rede,1 / loja,1 / loja,3— os do localhost). Medido nos
servidores em 28/08/2026: a Integração tem só `loja,1`; a Homologação tem 10 owners com ids que
não batem com nenhum dos 3 fixos. Owner é polimórfico (sem FK) — a migration fixa gravaria dado
para owners inexistentes num ambiente e deixaria de fora os owners reais de outro, em silêncio.

`46a93cfd591b` corrige isso: deriva os owners do próprio banco (`SELECT id FROM redes`/`lojas`)
e chama `mod_contabil.aplicar_gabarito_completo` para cada um — a MESMA função que a criação de
loja usa (item 2). Este teste prova exatamente o cenário que uma lista fixa erraria: constrói o
banco até UMA REVISÃO ANTES desta (resolvida pelo ScriptDirectory, nunca por id de revisão
escrito à mão — regra R12/CLAUDE.md), insere uma rede e duas lojas com ids que NÃO existem no
localhost, sobe até `head` e afirma que os owners novos nascem com o gabarito completo — não só
os 3 fixos que `c1ab3f8007c4` já conhecia.
"""
import pytest
from sqlalchemy import create_engine, text

from _schema_util import baseline_urls, _reset_schema, _alembic, _head_e_pai
import mod_contabil as mc


# ids deliberadamente fora do que qualquer migration fixa conhece (localhost = rede,1/loja,1/loja,3)
REDE_NOVA = 501
LOJA_NOVA_1 = 502
LOJA_NOVA_2 = 503


def _gabarito_completo(conn, owner_tipo, owner_id):
    n_cc = conn.execute(text(
        "SELECT count(*) FROM centro_custo WHERE owner_tipo = :ot AND owner_id = :oid"
    ), {"ot": owner_tipo, "oid": owner_id}).scalar_one()
    n_conta = conn.execute(text(
        "SELECT count(*) FROM conta WHERE owner_tipo = :ot AND owner_id = :oid"
    ), {"ot": owner_tipo, "oid": owner_id}).scalar_one()
    n_sem_classificacao = conn.execute(text(
        "SELECT count(*) FROM conta WHERE owner_tipo = :ot AND owner_id = :oid "
        "AND grupo = 5 AND tipo = 'analitica' AND codigo = ANY(:codigos) "
        "AND (centro_custo_id IS NULL OR natureza_custo IS NULL)"
    ), {"ot": owner_tipo, "oid": owner_id,
        "codigos": list(mc.CLASSIFICACAO_GRUPO5_V1)}).scalar_one()
    return {
        "centro_custo": n_cc, "conta": n_conta, "sem_classificacao": n_sem_classificacao,
    }


def test_migration_deriva_owners_do_banco_nao_de_lista_fixa():
    try:
        alembic_url, psycopg_url = baseline_urls()
    except RuntimeError as e:
        pytest.skip(str(e))

    _reset_schema(psycopg_url)

    head, pai_do_head = _head_e_pai()
    if pai_do_head is None:
        pytest.skip("head sem down_revision — nao ha revisao anterior pra parar antes do gabarito "
                    "dinamico (a cadeia mudou; ajuste este teste pra achar a revisao certa).")

    # sobe ate UMA REVISAO ANTES do gabarito dinamico -- ainda so' os 3 owners fixos existem
    proc = _alembic(["upgrade", pai_do_head], alembic_url)
    assert proc.returncode == 0, f"upgrade ate {pai_do_head} falhou:\n{proc.stdout}\n{proc.stderr}"

    # owners que NAO existem no localhost, inseridos direto nas tabelas de instancia
    eng = create_engine(psycopg_url)
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO redes (id, nome, ativo) VALUES (:id, 'Rede Nova (teste item 5)', 1)"
        ), {"id": REDE_NOVA})
        conn.execute(text(
            "INSERT INTO lojas (id, rede_id, nome, codigo) VALUES (:id, :rede_id, :nome, :codigo)"
        ), {"id": LOJA_NOVA_1, "rede_id": REDE_NOVA, "nome": "Loja Nova 1 (teste item 5)", "codigo": "TA1"})
        conn.execute(text(
            "INSERT INTO lojas (id, rede_id, nome, codigo) VALUES (:id, :rede_id, :nome, :codigo)"
        ), {"id": LOJA_NOVA_2, "rede_id": REDE_NOVA, "nome": "Loja Nova 2 (teste item 5)", "codigo": "TA2"})

    proc = _alembic(["upgrade", "head"], alembic_url)
    assert proc.returncode == 0, f"upgrade ate head falhou:\n{proc.stdout}\n{proc.stderr}"

    with eng.connect() as conn:
        owners_novos = [("rede", REDE_NOVA), ("loja", LOJA_NOVA_1), ("loja", LOJA_NOVA_2)]
        owners_fixos = [("rede", 1), ("loja", 1), ("loja", 3)]

        for owner_tipo, owner_id in owners_novos + owners_fixos:
            g = _gabarito_completo(conn, owner_tipo, owner_id)
            assert g["centro_custo"] == len(mc.CENTRO_CUSTO_PADRAO), (
                f"{owner_tipo},{owner_id}: {g['centro_custo']} nos de centro_custo, "
                f"esperava {len(mc.CENTRO_CUSTO_PADRAO)}"
            )
            assert g["conta"] == len(mc.PLANO_PADRAO), (
                f"{owner_tipo},{owner_id}: {g['conta']} contas, esperava {len(mc.PLANO_PADRAO)}"
            )
            assert g["sem_classificacao"] == 0, (
                f"{owner_tipo},{owner_id}: {g['sem_classificacao']} conta(s) do grupo 5 sem "
                "centro_custo_id/natureza_custo"
            )
    eng.dispose()
