"""seed.py — super_admin de bootstrap lê ORIZON_ADMIN_LOGIN/ORIZON_ADMIN_SENHA do ambiente,
sem valor default (achado de 28/08/2026: o login/senha hardcoded que viviam em
`database._SEED_SA_LOGIN`/`_SEED_SA_SENHA` acabaram como super_admin de verdade na Integração e
na Homologação, com `senha_provisoria=0` — chegaram pelo dump de `usuarios`, não por alguém
rodando `seed.py` nos servidores; ver docstring da constante removida em database.py).

Os dois lados: sem as variáveis, `seed()` se recusa a criar o super_admin (mas continua
seedando o resto — loja/usuários de teste/funções, que não têm o mesmo problema); com elas,
cria com `senha_provisoria=1` (mesma regra de `scripts/criar_primeiro_admin.py`) e o login
funciona pelo caminho de autenticação real do app.
"""
import auth.auth as auth_mod


def test_sem_variaveis_de_ambiente_recusa_criar_super_admin(app_db, monkeypatch):
    monkeypatch.delenv("ORIZON_ADMIN_LOGIN", raising=False)
    monkeypatch.delenv("ORIZON_ADMIN_SENHA", raising=False)

    import seed
    seed.seed()

    db = app_db.get_session()
    assert db.query(app_db.Usuario).filter_by(nivel="super_admin").first() is None
    db.close()


def test_com_variaveis_de_ambiente_cria_com_senha_provisoria_e_login_funciona(app_db, monkeypatch):
    monkeypatch.setenv("ORIZON_ADMIN_LOGIN", "mbn1972@gmail.com")
    monkeypatch.setenv("ORIZON_ADMIN_SENHA", "teste123")

    import seed
    seed.seed()

    db = app_db.get_session()
    sa = db.query(app_db.Usuario).filter_by(nivel="super_admin").first()
    assert sa is not None
    assert sa.login == "mbn1972@gmail.com"
    assert sa.senha_provisoria == 1
    db.close()

    resultado = auth_mod.fazer_login("mbn1972@gmail.com", "teste123")
    assert resultado["ok"] is True, resultado
    assert resultado["precisa_trocar_senha"] is True
    assert resultado["usuario"]["nivel"] == "super_admin"
