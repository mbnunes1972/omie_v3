"""Bug real de Produção (28/08/2026): `scripts/aplicar_gabarito.py` tinha um `return` cedo
quando `redes`/`lojas` vinham vazias ("nada a fazer") — e pulava a varredura de órfãos junto.
É exatamente o caso em que ela mais importa: um banco construído só pelas migrations, sem
NENHUMA configuração restaurada, tem o gabarito incondicional da `c1ab3f8007c4` (480 `conta`,
48 `centro_custo` — os 3 owners fixos) inteiro órfão, e ficava lá pra sempre.

Semear e varrer são duas etapas independentes agora — este teste é o cenário que nenhum outro
cobria (todos partiam de um banco com pelo menos 1 owner real em `redes`/`lojas`): roda o
script contra um banco recém-migrado, SEM restaurar configuração nenhuma, e afirma que
`conta`/`centro_custo` terminam em ZERO.
"""
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text

from _schema_util import baseline_urls, construir_schema_do_zero

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_banco_sem_nenhum_owner_termina_com_conta_e_centro_custo_zerados():
    try:
        alembic_url, psycopg_url = baseline_urls()
    except RuntimeError as e:
        pytest.skip(str(e))

    construir_schema_do_zero(alembic_url, psycopg_url)

    eng = create_engine(psycopg_url)
    with eng.connect() as conn:
        n_redes = conn.execute(text("SELECT count(*) FROM redes")).scalar_one()
        n_lojas = conn.execute(text("SELECT count(*) FROM lojas")).scalar_one()
        n_conta_antes = conn.execute(text("SELECT count(*) FROM conta")).scalar_one()
        n_cc_antes = conn.execute(text("SELECT count(*) FROM centro_custo")).scalar_one()
    assert (n_redes, n_lojas) == (0, 0), "pre-condicao: banco recem-migrado nao pode ter owner"
    assert n_conta_antes > 0 and n_cc_antes > 0, (
        "pre-condicao: a migration de gabarito devia ter semeado os 3 owners fixos mesmo sem "
        "redes/lojas (e' exatamente o gabarito que fica orfao neste cenario)"
    )

    proc = subprocess.run([sys.executable, "scripts/aplicar_gabarito.py"],
                          cwd=REPO_ROOT, env={**os.environ, "DATABASE_URL": alembic_url},
                          capture_output=True, text=True)
    assert proc.returncode == 0, f"script falhou:\n{proc.stdout}\n{proc.stderr}"

    with eng.connect() as conn:
        n_conta_depois = conn.execute(text("SELECT count(*) FROM conta")).scalar_one()
        n_cc_depois = conn.execute(text("SELECT count(*) FROM centro_custo")).scalar_one()
    eng.dispose()

    assert n_conta_depois == 0, f"conta deveria zerar (tudo orfao), ficou com {n_conta_depois}"
    assert n_cc_depois == 0, f"centro_custo deveria zerar (tudo orfao), ficou com {n_cc_depois}"
