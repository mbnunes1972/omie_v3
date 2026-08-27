"""Fecha a classe inteira "algo fora das migrations mexe no schema", nao um caso isolado.

Hoje dois caminhos de bootstrap coexistem: `alembic upgrade head` (a baseline) e
`database.init_db()` (create_all + `_migrar_colunas_pg` + seeds, usado por conftest.py
em app_db/db_pg_limpo). Precisam produzir o MESMO schema. Enquanto `_migrar_colunas_pg`
nao for removido (ver "divida de Onda 2" em CLAUDE.md), este teste e' a contencao: um
bloco novo la' que mexa em coluna/constraint/indice sem uma migration Alembic
equivalente quebra AQUI, no CI, nao em producao meses depois.

Roda inteiramente contra `orizon_baseline_teste` (banco de RASCUNHO dedicado, derivado
do DATABASE_URL do .env) — NUNCA o banco principal (`orizon`) nem o `orizon_test` usado
pelo resto da suite (evita concorrencia com os outros testes, que podem rodar em
paralelo e dependem do orizon_test ficar disponivel o tempo todo).

A construcao do schema via Alembic (reset + upgrade, cobrindo tanto o mundo pos-B3
quanto o intermediario de hoje) vive em tests/_schema_util.py — sem nenhum id de
revisao escrito a mao aqui nem la'. Ver a regra em CLAUDE.md.
"""

import pytest
from sqlalchemy import create_engine, inspect

from _schema_util import baseline_urls, construir_schema_do_zero, _reset_schema


def _snapshot(psycopg_url):
    """Retrato do schema nas 4 dimensoes do B2: colunas (tipo/nullable/default), FKs,
    PK/unique/check, indices. Comparado por conteudo — ordem fisica de coluna e nome
    de constraint sem name explicito nao entram (mesmo criterio ja usado na comparacao
    manual do B2: divergem por convencao, nao por bug de schema)."""
    eng = create_engine(psycopg_url)
    insp = inspect(eng)
    tabelas = sorted(
        t for t in insp.get_table_names()
        if not t.startswith("alembic") and not t.startswith("pg_stat")
    )

    retrato = {"tabelas": tabelas, "colunas": {}, "fks": {}, "unicos": {},
               "checks": {}, "pks": {}, "indices": {}}
    for t in tabelas:
        retrato["colunas"][t] = sorted(
            (c["name"], str(c["type"]), c["nullable"], str(c.get("default")))
            for c in insp.get_columns(t)
        )
        retrato["fks"][t] = sorted(
            (tuple(sorted(fk["constrained_columns"])), fk["referred_table"],
             tuple(sorted(fk["referred_columns"])))
            for fk in insp.get_foreign_keys(t)
        )
        unicos = [tuple(sorted(uc["column_names"])) for uc in insp.get_unique_constraints(t)]
        unicos += [tuple(sorted(idx["column_names"])) for idx in insp.get_indexes(t) if idx.get("unique")]
        retrato["unicos"][t] = sorted(unicos)
        retrato["checks"][t] = sorted(ck.get("sqltext", "") for ck in insp.get_check_constraints(t))
        pk = insp.get_pk_constraint(t)
        retrato["pks"][t] = tuple(sorted(pk.get("constrained_columns") or []))
        retrato["indices"][t] = sorted(
            (tuple(idx["column_names"]), bool(idx["unique"])) for idx in insp.get_indexes(t)
        )

    eng.dispose()
    return retrato


def test_init_db_produz_schema_identico_a_alembic_upgrade_head():
    try:
        alembic_url, psycopg_url = baseline_urls()
    except RuntimeError as e:
        pytest.skip(str(e))

    # --- lado A: Alembic, do zero
    construir_schema_do_zero(alembic_url, psycopg_url)
    retrato_alembic = _snapshot(psycopg_url)

    # --- lado B: `database.init_db()`, do zero, no MESMO banco
    _reset_schema(psycopg_url)
    import database
    from sqlalchemy.orm import sessionmaker

    orig = (database.ENGINE, database.Session)
    database.ENGINE = create_engine(psycopg_url)
    database.Session = sessionmaker(bind=database.ENGINE)
    try:
        database.init_db()
        retrato_initdb = _snapshot(psycopg_url)
    finally:
        database.ENGINE.dispose()
        database.ENGINE, database.Session = orig

    assert retrato_alembic["tabelas"] == retrato_initdb["tabelas"], (
        "Tabelas divergem entre Alembic e `init_db()`:\n"
        f"so' no alembic: {sorted(set(retrato_alembic['tabelas']) - set(retrato_initdb['tabelas']))}\n"
        f"so' no init_db: {sorted(set(retrato_initdb['tabelas']) - set(retrato_alembic['tabelas']))}"
    )

    divergencias = []
    for dim in ("colunas", "fks", "unicos", "checks", "pks", "indices"):
        for t in retrato_alembic["tabelas"]:
            a, b = retrato_alembic[dim][t], retrato_initdb[dim][t]
            if a != b:
                divergencias.append(
                    f"{dim}['{t}']:\n  alembic:  {a}\n  init_db(): {b}"
                )

    assert not divergencias, (
        "Schema do Alembic diverge de `init_db()` "
        "(algo fora das migrations mexeu no schema):\n\n" + "\n\n".join(divergencias)
    )
