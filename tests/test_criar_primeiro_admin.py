"""scripts/criar_primeiro_admin.py — primeiro super_admin de um ambiente reconstruído vazio
(Produção, decisão de Marcelo 2026-08-28). Roda o script de verdade (subprocess, contra o banco
de teste isolado do `app_db`) e confirma pelo caminho de autenticação REAL do app
(`auth.fazer_login`) — não só que a linha em `usuarios` existe. Depois confirma que rodar de
novo é recusado (script de primeiro acesso, não de criação de usuário) e não duplica nada.
"""
import os
import subprocess
import sys

import auth.auth as auth_mod

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rodar_script(db_url, login, senha, nome="Marcelo"):
    env = {**os.environ, "DATABASE_URL": db_url,
           "ORIZON_ADMIN_LOGIN": login, "ORIZON_ADMIN_SENHA": senha,
           "ORIZON_ADMIN_NOME": nome}
    return subprocess.run([sys.executable, "scripts/criar_primeiro_admin.py"],
                          cwd=REPO_ROOT, env=env, capture_output=True, text=True)


def test_cria_admin_e_login_funciona_pelo_caminho_real_depois_recusa_repeticao(app_db):
    db_url = app_db.ENGINE.url.render_as_string(hide_password=False)
    db = app_db.get_session()
    assert db.query(app_db.Usuario).count() == 0, "pre-condicao: base de teste devia nascer vazia"
    db.close()

    login, senha = "mbn1972@gmail.com", "teste123"
    proc = _rodar_script(db_url, login, senha)
    assert proc.returncode == 0, f"script falhou:\n{proc.stdout}\n{proc.stderr}"
    assert senha not in proc.stdout and senha not in proc.stderr, \
        "a senha nao pode aparecer na saida do script"

    # autenticacao pelo caminho REAL do app, nao so' a linha existir no banco
    resultado = auth_mod.fazer_login(login, senha)
    assert resultado["ok"] is True, resultado
    assert resultado["precisa_trocar_senha"] is True
    assert resultado["usuario"]["nivel"] == "super_admin"

    db = app_db.get_session()
    assert db.query(app_db.Usuario).count() == 1
    db.close()

    # rodar de novo e' RECUSADO (base ja nao esta vazia) -- nao duplica, nao troca senha
    proc2 = _rodar_script(db_url, "outro@exemplo.com", "outrasenha123", nome="Outro")
    assert proc2.returncode != 0
    assert "RECUSADO" in (proc2.stdout + proc2.stderr)

    db = app_db.get_session()
    assert db.query(app_db.Usuario).count() == 1, "rodar de novo nao pode criar um 2o usuario"
    db.close()

    # o login original continua sendo o unico caminho valido
    resultado2 = auth_mod.fazer_login("outro@exemplo.com", "outrasenha123")
    assert resultado2["ok"] is False
