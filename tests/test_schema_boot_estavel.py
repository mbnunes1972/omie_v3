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
"""

import os
import re
import subprocess

import pytest
from sqlalchemy import create_engine, inspect, text as sa_text

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

# PONTE TEMPORARIA, ate' a B3 substituir 0001-000N pela baseline real: hoje 0001 e' uma
# baseline VAZIA (pass/pass) e 0002+ sao ALTERs que pressupoem tabelas ja existentes —
# `alembic upgrade head` a partir de um banco vazio FALHA na 0002 ("relation does not
# exist"), confirmado empiricamente ao escrever este teste. Isso e' esperado: e' o
# problema original que motivou a B1/B2/B3 inteira, nao um bug deste teste. Ate' a B3
# rodar, este teste stampa ate' a ultima revisao real (a mais recente que NAO e' o
# candidato a baseline) e so' entao roda upgrade head — isolando so' o passo do
# candidato (que faz o CREATE completo do zero), equivalente a rodar `alembic upgrade
# head` puro depois que a B3 substituir 0001-000N. Atualizar este valor toda vez que uma
# migration real nova entrar ANTES da B3 acontecer (ficou desatualizado uma vez, na
# 0008->0009 — o candidato tinha que ser regerado sobre a 0009). REMOVER o stamp assim
# que a B3 acontecer (upgrade head direto passa a funcionar sozinho).
_STAMP_PONTE_PRE_B3 = "0009"


def _baseline_urls():
    """(url_alembic, url_psycopg2) de orizon_baseline_teste — nunca outro banco.
    Deriva do DATABASE_URL do .env trocando so' o nome do banco, igual ao
    _test_database_url() do conftest.py, mas apontando pro rascunho dedicado."""
    env_path = os.path.join(_REPO_ROOT, ".env")
    if not os.path.exists(env_path):
        pytest.skip("Sem .env — nao da pra derivar orizon_baseline_teste.")
    with open(env_path, encoding="utf-8") as f:
        m = re.search(r"DATABASE_URL\s*=\s*['\"]?(postgresql[^'\"\s]+)", f.read())
    if not m:
        pytest.skip("Sem DATABASE_URL no .env — nao da pra derivar orizon_baseline_teste.")
    alembic_url = m.group(1).rsplit("/", 1)[0] + "/orizon_baseline_teste"
    return alembic_url, alembic_url.replace("+psycopg2", "")


def _reset_schema(psycopg_url):
    eng = create_engine(psycopg_url)
    with eng.begin() as conn:
        conn.execute(sa_text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid() "
            "AND usename = current_user"))
    with eng.begin() as conn:
        conn.execute(sa_text("DROP SCHEMA public CASCADE"))
        conn.execute(sa_text("CREATE SCHEMA public"))
    eng.dispose()


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
    alembic_url, psycopg_url = _baseline_urls()

    # --- lado A: `alembic upgrade head`, do zero
    _reset_schema(psycopg_url)
    proc = subprocess.run(
        ["alembic", "stamp", _STAMP_PONTE_PRE_B3],
        cwd=_REPO_ROOT,
        env={**os.environ, "DATABASE_URL": alembic_url},
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"alembic stamp {_STAMP_PONTE_PRE_B3} falhou em orizon_baseline_teste:\n{proc.stdout}\n{proc.stderr}"
    )
    proc = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=_REPO_ROOT,
        env={**os.environ, "DATABASE_URL": alembic_url},
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"alembic upgrade head falhou em orizon_baseline_teste:\n{proc.stdout}\n{proc.stderr}"
    )
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
        "Tabelas divergem entre `alembic upgrade head` e `init_db()`:\n"
        f"so' no alembic: {sorted(set(retrato_alembic['tabelas']) - set(retrato_initdb['tabelas']))}\n"
        f"so' no init_db: {sorted(set(retrato_initdb['tabelas']) - set(retrato_alembic['tabelas']))}"
    )

    divergencias = []
    for dim in ("colunas", "fks", "unicos", "checks", "pks", "indices"):
        for t in retrato_alembic["tabelas"]:
            a, b = retrato_alembic[dim][t], retrato_initdb[dim][t]
            if a != b:
                divergencias.append(
                    f"{dim}['{t}']:\n  alembic upgrade head: {a}\n  init_db():            {b}"
                )

    assert not divergencias, (
        "Schema de `alembic upgrade head` diverge de `init_db()` "
        "(algo fora das migrations mexeu no schema):\n\n" + "\n\n".join(divergencias)
    )
