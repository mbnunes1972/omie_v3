# -*- coding: utf-8 -*-
"""Bootstrap de banco para o E2E de navegador (tests/test_e2e_browser_conciliacao_final.py).

Roda como SUBPROCESSO isolado (nunca importado direto pelo processo principal do pytest) —
assim o rebind de `database.ENGINE/Session` daqui nunca vaza pro resto da suíte. Banco PRÓPRIO
(`orizon_e2e`, docs/db/ESTEIRA.md — "teste fora da rodada padrão apodrece": o problema era
isolamento, não custo, e isolamento se resolve com banco próprio, não tirando o teste da
suíte) — nunca `orizon_test` (esse é do resto da suíte; os dois disputariam o mesmo schema se
rodassem juntos).

GUARDA (ESTEIRA.md — "todo teste que abre banco afirma o nome do banco antes de qualquer
coisa"): confere `current_database()` antes do DROP SCHEMA e recusa se não for `orizon_e2e` —
mesma disciplina do ACHADO-18 (ler o estado, não confiar em quem chamou passar o valor certo).
Em 31/08 um `DATABASE_URL` esquecido na sessão do shell fez este bootstrap escrever no banco de
dev — a causa (usar `database.get_session()` sem bind próprio) já foi corrigida no teste; esta
é a guarda que falta contra a PRÓXIMA forma de o mesmo acidente acontecer (ex.: alguém passar a
URL errada como argumento)."""
import glob
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

NOME_BANCO_ESPERADO = "orizon_e2e"


def main(db_url):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import database

    engine = create_engine(db_url, echo=False)
    with engine.begin() as conn:
        atual = conn.execute(text("SELECT current_database()")).scalar()
    if atual != NOME_BANCO_ESPERADO:
        raise RuntimeError(
            "Recusado: este bootstrap só roda contra %r — conectou em %r. DROP SCHEMA CASCADE "
            "num banco errado destruiria dado de verdade; corrija a URL antes de tentar de novo."
            % (NOME_BANCO_ESPERADO, atual))

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
