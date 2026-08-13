"""Achado de auditoria 2026-08-13: fazer_login não tinha nenhum contador de tentativas/lockout —
força bruta *online* sem barreira nenhuma. Rate limit em memória, thread-safe, chaveado pelo ID
do usuário RESOLVIDO (login e e-mail da mesma conta caem no mesmo balde). `auth._LOGIN_TENTATIVAS`
é estado de PROCESSO compartilhado entre testes — cada teste limpa o próprio balde antes de usar,
pra não depender de ordem de execução nem vazar contagem de outros arquivos de teste."""
from auth import auth as _auth


def _reset(app_db, login):
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login=login).first()
    db.close()
    if u:
        _auth._login_limpar_falhas("u:%d" % u.id)


def test_bloqueia_apos_N_tentativas_erradas(http_client_factory, seed, app_db):
    _reset(app_db, "cons_l1")
    c = http_client_factory()
    for _ in range(_auth._LOGIN_MAX_TENTATIVAS):
        st, d = c.post("/api/auth/login", {"login": "cons_l1", "senha": "senha_errada"})
        assert st == 401 and d["ok"] is False

    # a Nª+1 tentativa é bloqueada MESMO COM A SENHA CERTA — a conta está sob lockout
    st2, d2 = c.post("/api/auth/login", {"login": "cons_l1", "senha": "senha123"})
    assert st2 == 401 and d2["ok"] is False
    assert "tentativas" in d2["erro"].lower()
    _reset(app_db, "cons_l1")


def test_login_certo_antes_do_limite_nao_bloqueia_e_zera_contador(http_client_factory, seed, app_db):
    _reset(app_db, "dir_l1")
    c = http_client_factory()
    for _ in range(_auth._LOGIN_MAX_TENTATIVAS - 1):
        c.post("/api/auth/login", {"login": "dir_l1", "senha": "senha_errada"})

    c2 = http_client_factory()
    st, d = c2.post("/api/auth/login", {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and d["ok"] is True   # ainda dentro do limite — entra normal

    # login OK zera o contador: nova rodada de erros começa do zero, não herda os anteriores
    c3 = http_client_factory()
    for _ in range(_auth._LOGIN_MAX_TENTATIVAS - 1):
        st3, d3 = c3.post("/api/auth/login", {"login": "dir_l1", "senha": "senha_errada"})
        assert st3 == 401
    c4 = http_client_factory()
    st4, d4 = c4.post("/api/auth/login", {"login": "dir_l1", "senha": "senha123"})
    assert st4 == 200 and d4["ok"] is True
    _reset(app_db, "dir_l1")


def test_bloqueio_e_por_conta_nao_vaza_para_outra(http_client_factory, seed, app_db):
    _reset(app_db, "cons_l1")
    _reset(app_db, "dir_l2")
    c = http_client_factory()
    for _ in range(_auth._LOGIN_MAX_TENTATIVAS):
        c.post("/api/auth/login", {"login": "cons_l1", "senha": "errada"})

    # cons_l1 está bloqueado agora...
    st_bloq, _ = c.post("/api/auth/login", {"login": "cons_l1", "senha": "senha123"})
    assert st_bloq == 401

    # ...mas dir_l2 (outra conta) não é afetado
    c2 = http_client_factory()
    st2, d2 = c2.post("/api/auth/login", {"login": "dir_l2", "senha": "senha123"})
    assert st2 == 200 and d2["ok"] is True
    _reset(app_db, "cons_l1")


def test_identificador_inexistente_tambem_e_limitado(http_client_factory, seed, app_db):
    """Conta que não existe: sem usuario.id pra chavear, cai no fallback por string — impede
    varredura ilimitada de nomes de usuário (achado 3 cobre login válido E inválido)."""
    ident = "conta-que-nao-existe-xyz"
    _auth._login_limpar_falhas("s:%s" % ident)
    c = http_client_factory()
    for _ in range(_auth._LOGIN_MAX_TENTATIVAS):
        st, d = c.post("/api/auth/login", {"login": ident, "senha": "qualquer"})
        assert st == 401
    st2, d2 = c.post("/api/auth/login", {"login": ident, "senha": "qualquer"})
    assert st2 == 401 and "tentativas" in d2["erro"].lower()
    _auth._login_limpar_falhas("s:%s" % ident)


def test_alternar_entre_login_e_email_cai_no_mesmo_balde(http_client_factory, seed, app_db):
    """Login e e-mail da MESMA conta compartilham o lockout — alternar entre as duas formas não
    dobra o orçamento de tentativas do atacante."""
    _reset(app_db, "cons_l1")
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    u.email = "ConsCase@Loja.com"
    db.commit(); db.close()

    c = http_client_factory()
    metade = _auth._LOGIN_MAX_TENTATIVAS // 2
    for _ in range(metade):
        c.post("/api/auth/login", {"login": "cons_l1", "senha": "errada"})
    for _ in range(_auth._LOGIN_MAX_TENTATIVAS - metade):
        c.post("/api/auth/login", {"login": "CONSCASE@LOJA.COM", "senha": "errada"})

    st, d = c.post("/api/auth/login", {"login": "cons_l1", "senha": "senha123"})
    assert st == 401 and "tentativas" in d["erro"].lower()
    _reset(app_db, "cons_l1")
