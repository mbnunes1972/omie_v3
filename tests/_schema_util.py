"""Utilitario de schema compartilhado pelos testes de baseline Alembic.

Nenhum id de revisao e' escrito a mao aqui, nem em quem usa isto — toda
resolucao de "qual e' o head" e "qual e' o pai dele" passa por
ScriptDirectory.from_config(). Regra registrada em CLAUDE.md: id de revisao
hardcoded em teste ou script e' estado duplicado com um humano encarregado de
manter sincronizado — a mesma doenca por tras dos achados desta etapa
(fk_convmsg_documento_ref, ix_ciclo_etapas_responsavel_terceiro, e a constante
_STAMP_PONTE_PRE_B3 que este arquivo substitui).
"""

import os
import re
import subprocess

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text as sa_text

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

_MINIMO_TABELAS_SCHEMA_COMPLETO = 50


def _script_directory():
    cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    return ScriptDirectory.from_config(cfg)


def _head_e_pai():
    """(head, down_revision do head), lidos do grafo real de migrations/versions/."""
    script = _script_directory()
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(
            f"Esperava exatamente 1 head no Alembic, achei {len(heads)}: {heads}. "
            "Resolva o branch antes de rodar este teste."
        )
    head_rev = script.get_revision(heads[0])
    return heads[0], head_rev.down_revision


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


def _contar_tabelas(psycopg_url):
    eng = create_engine(psycopg_url)
    n = len(inspect(eng).get_table_names())
    eng.dispose()
    return n


def _alembic(comando, alembic_url):
    return subprocess.run(
        ["alembic"] + comando,
        cwd=REPO_ROOT,
        env={**os.environ, "DATABASE_URL": alembic_url},
        capture_output=True, text=True,
    )


def construir_schema_do_zero(alembic_url, psycopg_url):
    """Zera o schema e constroi via Alembic, cobrindo os dois estados possiveis da
    cadeia de migrations sem nenhum id de revisao escrito a mao:

    - Mundo pos-B3: a baseline e' a unica base — `alembic upgrade head` direto
      constroi tudo a partir de um banco vazio.
    - Mundo intermediario (hoje): 0001 e' uma baseline vazia de stamp e quem cria
      as tabelas de verdade e' o candidato no fim da fila — `upgrade head` direto
      falha ou nao cria nada, porque as revisoes do meio pressupoem tabelas ja
      existentes. Resolve head e o down_revision dele pelo ScriptDirectory, stampa
      ate' o down_revision, e so' entao roda upgrade head — isolando o passo que
      faz o CREATE completo.

    Levanta RuntimeError, com o head pelo nome, se nenhum dos dois caminhos
    produzir um schema completo — nunca passa em falso.
    """
    _reset_schema(psycopg_url)
    proc = _alembic(["upgrade", "head"], alembic_url)
    if proc.returncode == 0 and _contar_tabelas(psycopg_url) > _MINIMO_TABELAS_SCHEMA_COMPLETO:
        return

    head, pai = _head_e_pai()
    if pai is None:
        raise RuntimeError(
            f"`alembic upgrade head` nao construiu um schema completo (mundo pos-B3 "
            f"esperado) e o head atual ({head}) nao tem down_revision pra tentar o "
            "caminho do mundo intermediario. O head nao e' uma baseline capaz de "
            f"construir do zero.\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
        )

    _reset_schema(psycopg_url)
    proc_stamp = _alembic(["stamp", pai], alembic_url)
    if proc_stamp.returncode != 0:
        raise RuntimeError(
            f"`alembic stamp {pai}` falhou:\n{proc_stamp.stdout}\n{proc_stamp.stderr}"
        )
    proc = _alembic(["upgrade", "head"], alembic_url)
    if proc.returncode != 0:
        raise RuntimeError(
            f"`alembic upgrade head` falhou mesmo apos stamp {pai} (down_revision "
            f"do head {head}):\n{proc.stdout}\n{proc.stderr}"
        )
    n = _contar_tabelas(psycopg_url)
    if n <= _MINIMO_TABELAS_SCHEMA_COMPLETO:
        raise RuntimeError(
            f"Head {head} (stampando ate' o pai {pai}) nao e' uma baseline capaz de "
            f"construir do zero — resultou em {n} tabelas (esperava mais de "
            f"{_MINIMO_TABELAS_SCHEMA_COMPLETO}). Alguem acrescentou uma revisao real "
            "sem regerar o candidato a baseline no fim da fila?"
        )


def baseline_urls():
    """(url_alembic, url_psycopg2) de orizon_baseline_teste — nunca outro banco.
    Deriva do DATABASE_URL do .env trocando so' o nome do banco."""
    env_path = os.path.join(REPO_ROOT, ".env")
    if not os.path.exists(env_path):
        raise RuntimeError("Sem .env — nao da pra derivar orizon_baseline_teste.")
    with open(env_path, encoding="utf-8") as f:
        m = re.search(r"DATABASE_URL\s*=\s*['\"]?(postgresql[^'\"\s]+)", f.read())
    if not m:
        raise RuntimeError("Sem DATABASE_URL no .env — nao da pra derivar orizon_baseline_teste.")
    alembic_url = m.group(1).rsplit("/", 1)[0] + "/orizon_baseline_teste"
    return alembic_url, alembic_url.replace("+psycopg2", "")
