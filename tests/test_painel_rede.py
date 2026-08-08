"""Painel da Rede (2026-08-08): tela própria do Gestor de Rede (admin_rede) — antes ele caía no
mesmo aterrissamento quebrado do super_admin (Admin de LOJA, "Loja não identificada", já que
nenhum dos dois tem loja própria). Cobre os dois endpoints novos/ampliados: GET de UMA rede
(antes só existia o GET de TODAS, exclusivo de gerir_redes) e o PUT ampliado pro dono da rede
editar nome/CNPJ (mas não `ativo` — isso segue exclusivo de plataforma)."""


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_admin_rede_ve_dados_da_propria_rede(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "adm_rede")
    st, out = c.get("/api/admin/redes/%d" % seed["rede_id"])
    assert st == 200 and out["ok"], (st, out)
    assert out["rede"]["id"] == seed["rede_id"]
    assert out["rede"]["nome"] == "Rede Teste"


def test_super_admin_ve_dados_de_qualquer_rede(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "super")
    st, out = c.get("/api/admin/redes/%d" % seed["rede_id"])
    assert st == 200 and out["ok"], (st, out)


def test_usuario_de_loja_nao_acessa_get_rede(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")   # master de loja, sem rede_id/gerir_redes
    st, out = c.get("/api/admin/redes/%d" % seed["rede_id"])
    assert st == 403


def test_sem_login_401_get_rede(http_client_factory, seed):
    c = http_client_factory()
    st, out = c.get("/api/admin/redes/%d" % seed["rede_id"])
    assert st == 401


def test_admin_rede_edita_nome_e_cnpj_da_propria_rede(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "adm_rede")
    st, out = c.patch("/api/admin/redes/%d" % seed["rede_id"],
                    {"nome": "Rede Teste Renomeada", "cnpj": "11.222.333/0001-81"})
    assert st == 200 and out["ok"], (st, out)
    assert out["rede"]["nome"] == "Rede Teste Renomeada"
    assert out["rede"]["cnpj"] == "11.222.333/0001-81"

    db = app_db.get_session()
    rede = db.get(app_db.Rede, seed["rede_id"])
    assert rede.nome == "Rede Teste Renomeada"
    db.close()


def test_admin_rede_nao_consegue_desativar_a_propria_rede(http_client_factory, seed, app_db):
    """`ativo` é decisão de plataforma — o dono da rede não pode se autodesativar. O PATCH não
    falha (fail-soft: os outros campos do corpo ainda aplicam), só ignora esse campo específico."""
    c = _login(http_client_factory, "adm_rede")
    st, out = c.patch("/api/admin/redes/%d" % seed["rede_id"], {"nome": "Ainda Ativa", "ativo": False})
    assert st == 200 and out["ok"], (st, out)
    assert out["rede"]["ativo"] is True

    db = app_db.get_session()
    rede = db.get(app_db.Rede, seed["rede_id"])
    assert bool(rede.ativo) is True
    db.close()


def test_super_admin_pode_desativar_rede(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "super")
    st, out = c.patch("/api/admin/redes/%d" % seed["rede_id"], {"ativo": False})
    assert st == 200 and out["ok"], (st, out)
    assert out["rede"]["ativo"] is False
    # restaura pro resto da suíte não herdar estado sujo (fixture é module-scoped)
    c.patch("/api/admin/redes/%d" % seed["rede_id"], {"ativo": True})


def test_usuario_de_loja_nao_edita_rede(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.patch("/api/admin/redes/%d" % seed["rede_id"], {"nome": "Hackeada"})
    assert st == 403
