# -*- coding: utf-8 -*-
"""Bootstrap de banco para o E2E de navegador (tests/test_e2e_browser_conciliacao_final.py).

Roda como SUBPROCESSO isolado (nunca importado direto pelo processo principal do pytest) —
assim o rebind de `database.ENGINE/Session` daqui nunca vaza pro resto da suíte. Reusa o mesmo
`orizon_test` da suíte normal (o `orizon` local não tem CREATEDB — sem privilégio pra um banco
`orizon_e2e` dedicado, ver docs/db/IMPLANTAR.md) — schema derrubado e recriado a cada run, igual
ao `_reset_schema_pg` de conftest.py. **Nunca rode ao mesmo tempo que `pytest -q` da suíte
inteira** — os dois disputam o mesmo schema."""
import glob
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main(db_url):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import database

    engine = create_engine(db_url, echo=False)
    with engine.begin() as conn:
        conn.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid() "
            "AND usename = current_user"))
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    database.ENGINE = engine
    database.Session = sessionmaker(bind=engine)
    database.init_db()

    # Higiene: cada rodada do E2E cria um diretório de projeto novo em PROJETOS_DIR (a
    # numeração `_N` de _criar_projeto olha o disco, não só o banco — sem isto, cada rerun
    # deixa lixo permanente e o sufixo só cresce).
    from storage import PROJETOS_DIR
    for caminho in glob.glob(os.path.join(PROJETOS_DIR, "E2E_Cozinha_Playwright*")):
        shutil.rmtree(caminho, ignore_errors=True)

    db = database.get_session()
    try:
        loja = db.query(database.Loja).order_by(database.Loja.id).first()
        u = database.Usuario(nome="E2E Master", login="e2e_master", nivel="master",
                             loja_id=loja.id, ativo=1)
        u.set_senha("senha123")
        db.add(u)
        cli = database.Cliente(nome="Cliente E2E", cpf="111.444.777-35", loja_id=loja.id,
                               email="cliente-e2e@exemplo.com", telefone="(11) 99999-0000",
                               cep="01310-100", logradouro="Av. Paulista", numero="1000",
                               bairro="Bela Vista", cidade="São Paulo", estado="SP",
                               inst_mesmo_residencial=1)
        db.add(cli)
        db.commit()
        print("LOJA_ID=%d" % loja.id)
        print("CLIENTE_ID=%d" % cli.id)
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1])
