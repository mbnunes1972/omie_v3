"""super_admin = acesso pleno e irrestrito (god-mode): ignora todos os gates de
capacidade e de módulo/painel; opera dentro de qualquer loja (loja do header)."""
from auth import perfis
import mod_tenancy


def test_super_admin_pode_qualquer_capacidade():
    # capacidades reais e uma inexistente — super_admin nunca é barrado
    for cap in ("gerir_usuarios", "gerir_perfis", "acesso_operacional",
                "acesso_financeiro", "acesso_fiscal", "autorizar",
                "ver_parametros", "editar_dados_loja", "capacidade_que_nao_existe"):
        assert perfis.pode("super_admin", cap) is True, cap


def test_super_admin_acessa_todo_modulo_e_painel():
    for mod in ("cadastro", "comercial", "financeiro", "folha", "fiscal",
                "estoque", "expedicao", "montagem", "assistencias"):
        assert perfis.acessa_modulo("super_admin", mod) is True, mod
    assert perfis.acessa_painel("super_admin", "admin") is True
    assert perfis.acessa_painel("super_admin", "config") is True


def test_bypass_nao_vaza_para_outros_perfis():
    # operador continua barrado onde já era barrado (não abre buraco lateral)
    assert perfis.pode("operador", "gerir_perfis") is False
    assert perfis.acessa_modulo("operador", "financeiro") is False
    assert perfis.acessa_painel("operador", "admin") is False


def test_super_admin_adota_loja_do_header():
    # sem membership e sem loja própria, mas com header → loja ativa = header
    assert mod_tenancy.resolver_loja_ativa([], 5, None, is_super=True) == 5
    # sem header → sem loja ativa (precisa escolher uma loja no console)
    assert mod_tenancy.resolver_loja_ativa([], None, None, is_super=True) is None


def test_resolver_loja_ativa_nao_super_inalterado():
    # comportamento pré-existente preservado p/ usuário de loja
    assert mod_tenancy.resolver_loja_ativa([], 5, None) is None          # header sem acesso → None
    assert mod_tenancy.resolver_loja_ativa([7], None, 7) == 7            # default acessível
    assert mod_tenancy.resolver_loja_ativa([7], 7, None) == 7            # header acessível


def test_super_admin_cria_e_le_perfil_na_loja_escolhida(http_client_factory, seed, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    c.loja_ativa = l1                                   # "entra" na loja L1
    # cria um perfil de acesso NA loja L1
    st, out = c.post("/api/admin/perfis", {"nome": "Vendas Plus", "base": "operador",
                                           "modulos": ["cadastro", "comercial"]})
    assert st == 201 and out["ok"], (st, out)
    # a matriz da loja L1 agora inclui o perfil recém-criado
    st, m = c.get("/api/admin/perfis")
    assert st == 200 and m["ok"]
    nomes = {p["nome"] for p in m["perfis"]}
    assert "Vendas Plus" in nomes, nomes


def test_super_admin_sem_loja_selecionada_erro_ao_criar_perfil(http_client_factory, seed):
    c = http_client_factory(); c.login("super", "senha123")   # sem c.loja_ativa
    st, out = c.post("/api/admin/perfis", {"nome": "X", "base": "operador", "modulos": []})
    assert out["ok"] is False and "loja" in (out.get("erro", "").lower())


def test_super_admin_cria_usuario_de_loja(http_client_factory, seed, app_db):
    """Desbloqueio reportado ('criar usuários'): super_admin cria conta numa loja."""
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    c.loja_ativa = l1
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Vendedor Novo", "login": "vend_novo@l1.com", "senha": "senha123",
        "nivel": "operador", "loja_id": l1,
    })
    assert st == 200 and body["ok"] is True, (st, body)
    db2 = app_db.get_session()
    novo = db2.query(app_db.Usuario).filter_by(login="vend_novo@l1.com").first()
    lid = novo.loja_id if novo else None
    db2.close()
    assert novo is not None and lid == l1


def test_super_admin_acessa_cadastro_ao_entrar_na_loja(http_client_factory, seed, app_db):
    """'parece não acessar o cadastro': sem loja ativa → 403; ao entrar numa loja
    (header X-Loja-Ativa) o Cadastro (GET /api/funcionarios) abre (200)."""
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    st_sem, _ = c.get("/api/funcionarios")          # sem loja escolhida → operacional barrado
    assert st_sem == 403
    c.loja_ativa = l1                               # "entra" na loja L1
    st_com, body = c.get("/api/funcionarios")
    assert st_com == 200 and body["ok"] is True, (st_com, body)


# ── Correções da auditoria (Vera, 2026-07-16) ──────────────────────────────────

def test_super_admin_edita_perfil_na_loja_escolhida(http_client_factory, seed, app_db):
    """🔴 Bloqueante: o PUT de edição usava usuario.loja_id (None p/ super_admin) e nunca
    casava (PerfilAcesso.loja_id é NOT NULL). Deve escopar pela loja do header, como o POST."""
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    c.loja_ativa = l1
    st, out = c.post("/api/admin/perfis", {"nome": "Vendas Edita", "base": "operador",
                                           "modulos": ["cadastro"]})
    assert st == 201 and out["ok"], (st, out)
    db = app_db.get_session()
    slug = db.query(app_db.PerfilAcesso).filter_by(nome="Vendas Edita").first().slug
    db.close()
    # a UI edita perfil via PATCH /api/admin/perfis/<slug> (index.html) — não PUT
    st2, out2 = c._req("PATCH", "/api/admin/perfis/%s" % slug,
                       {"nome": "Vendas Edita 2", "modulos": ["cadastro", "comercial"]})
    assert st2 == 200 and out2.get("ok"), (st2, out2)
    assert out2["perfil"]["nome"] == "Vendas Edita 2"


def test_super_admin_loja_inexistente_no_header_barra_operacional(http_client_factory, seed):
    """🟠 #1: header X-Loja-Ativa apontando loja inexistente não deve virar loja ativa
    'válida' (tela vazia silenciosa) — o operacional fecha (403), como sem loja."""
    c = http_client_factory(); c.login("super", "senha123")
    c.loja_ativa = 999999                            # loja que não existe
    st, _ = c.get("/api/funcionarios")
    assert st == 403


def test_loja_admin_alvo_header_zero_nao_cai_para_loja_propria(servidor, monkeypatch):
    """🟠 #2: distinguir header AUSENTE (None) de header PRESENTE porém 0 — usar
    `is not None`, não `or` (0 é falsy). Header presente é respeitado verbatim.
    _REQ_LOJA_ATIVA virou _req_local (threading.local, 2026-08-08) — o estado por-requisição
    agora mora num atributo da thread atual, não num global do módulo."""
    import main
    monkeypatch.setattr(main._req_local, "loja_ativa", 0, raising=False)
    assert main._loja_admin_alvo({"nivel": "super_admin", "loja_id": 9}) == 0
    monkeypatch.setattr(main._req_local, "loja_ativa", None, raising=False)
    assert main._loja_admin_alvo({"nivel": "super_admin", "loja_id": 9}) == 9


def test_auth_me_super_admin_reflete_modulos_da_loja_ativa(http_client_factory, seed, app_db):
    """🟠 #3: /api/auth/me deve ler X-Loja-Ativa p/ super_admin, refletindo os
    modulos_ativos da loja em que ele entrou — não sempre 'tudo ligado'."""
    import json as _json
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    loja = db.get(app_db.Loja, l1)
    orig = loja.modulos_ativos
    loja.modulos_ativos = _json.dumps(["cadastro", "comercial"])   # financeiro desligado
    db.commit(); db.close()
    try:
        c = http_client_factory(); c.login("super", "senha123")
        c.loja_ativa = l1
        st, body = c.get("/api/auth/me")
        assert st == 200 and body["ok"], (st, body)
        mods = set(body["usuario"]["modulos_ativos"])
        assert "cadastro" in mods, mods
        assert "financeiro" not in mods, mods
    finally:
        db = app_db.get_session()
        db.get(app_db.Loja, l1).modulos_ativos = orig
        db.commit(); db.close()


def test_super_admin_abre_financeiro_da_loja_ativa(http_client_factory, seed, app_db):
    """🔴 achado da Vera (2026-08-08): _contabil_ctx resolvia owner pela sessão BRUTA
    (usuario.loja_id) antes de olhar X-Loja-Ativa — super_admin nunca tem loja_id na
    sessão, então TODO painel financeiro explodia (ValueError) pra esse perfil, com ou
    sem header. Fix: usa active_loja_id (já resolvido via X-Loja-Ativa, mesmo mecanismo
    que o resto do Admin já usa pra super_admin "entrar" numa loja)."""
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    c.loja_ativa = l1
    st, body = c.get("/api/financeiro/balanco")
    assert st == 200 and body["ok"], (st, body)


def test_super_admin_sem_loja_ativa_ainda_barra_com_erro_claro(http_client_factory, seed):
    """Sem X-Loja-Ativa não tem como saber DE QUAL loja mostrar o Financeiro — preserva o
    erro 400 de hoje (não regride pra 500 nem finge sucesso)."""
    c = http_client_factory(); c.login("super", "senha123")
    st, body = c.get("/api/financeiro/balanco")
    assert st == 400 and body["ok"] is False
