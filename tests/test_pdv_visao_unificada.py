# -*- coding: utf-8 -*-
"""PDV — Fatia 2: visão unificada (spec _geral/2026-07-22-ponto-de-venda-design.md).

A área SENSÍVEL da frente: escopo. Cobre por perfil:
- razão PRÓPRIO do PDV (resolver_owner) mesmo com rede herdada;
- seletor de unidade (?unidade=) restrito a _lojas_do_escopo (mãe + PDVs dela),
  opt-in painel a painel — o escopo_operacional global fica intocado;
- painel financeiro oculto/bloqueado no PDV, com o razão dele operável pela mãe.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from conftest import HttpClient


@pytest.fixture(scope="module")
def pdv(servidor, app_db, seed):
    c = HttpClient(servidor); c.login("super", "senha123")
    st, out = c.post("/api/admin/lojas/%d/pdvs" % seed["loja1_id"],
                     {"nome": "PDV Litoral", "codigo": "LIT"})
    assert st == 200 and out.get("ok"), (st, out)
    return out["pdv"]


@pytest.fixture(scope="module")
def pdv_user(app_db, pdv):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Diretor PDV", login="dir_pdv2", nivel="master",
                       loja_id=pdv["id"], ativo=1)
    u.set_senha("senha123")
    db.add(u); db.flush()
    db.add(app_db.UsuarioLoja(usuario_id=u.id, loja_id=pdv["id"]))
    db.commit(); db.close()
    return "dir_pdv2"


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, "login falhou para %s" % who
    return c


# ── Razão próprio do PDV ─────────────────────────────────────────────────────

def test_razao_do_pdv_e_proprio_mesmo_com_rede(app_db, pdv, seed):
    import mod_contabil
    db = app_db.get_session()
    try:
        assert mod_contabil.resolver_owner(db, {"loja_id": pdv["id"], "rede_id": None}) == \
            ("loja", pdv["id"])
        # loja plena da rede também tem razão próprio (corte S187 — antes ia pro razão da rede)
        assert mod_contabil.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None}) == \
            ("loja", seed["loja1_id"])
    finally:
        db.close()


# ── Seletor de unidade: escopo por perfil ────────────────────────────────────

def test_unidades_para_diretor_da_mae(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.get("/api/financeiro/unidades")
    assert st == 200 and out["ok"], (st, out)
    assert [u["id"] for u in out["unidades"]] == [seed["loja1_id"], pdv["id"]]
    assert out["consolidado_disponivel"] is True
    tipos = {u["id"]: u["tipo"] for u in out["unidades"]}
    assert tipos[pdv["id"]] == "ponto_venda"


def test_unidades_para_loja_sem_pdv(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l2")
    st, out = c.get("/api/financeiro/unidades")
    assert st == 200 and out["ok"]
    assert [u["id"] for u in out["unidades"]] == [seed["loja2_id"]]
    assert out["consolidado_disponivel"] is False


def test_operador_nao_abre_o_seletor(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "cons_l1")           # operador: sem acesso_financeiro
    st, out = c.get("/api/financeiro/unidades")
    assert st == 403


def test_unidade_fora_do_escopo_403(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l2")            # outra loja: PDV não é dela
    st, out = c.get("/api/financeiro/contas?unidade=%d" % pdv["id"])
    assert st == 403 and "escopo" in (out.get("erro") or "")
    c1 = _login(http_client_factory, "dir_l1")           # mãe não alcança OUTRA loja
    st, out = c1.get("/api/financeiro/contas?unidade=%d" % seed["loja2_id"])
    assert st == 403


def test_consolidado_ainda_nao_neste_painel(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.get("/api/financeiro/contas?unidade=consolidado")
    assert st == 400


# ── A mãe opera o razão do PDV; os razões não se misturam ────────────────────

def test_mae_lanca_e_le_no_razao_do_pdv(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.post("/api/financeiro/eventos?unidade=%d" % pdv["id"],
                     {"tipo": "faturamento", "valor": 500.0, "projeto_id": "Proj_PDV_X"})
    assert st == 201 and out["ok"], (st, out)
    # aparece na unidade PDV…
    st, out = c.get("/api/financeiro/lancamentos?unidade=%d" % pdv["id"])
    assert st == 200 and any(l["projeto_id"] == "Proj_PDV_X" for l in out["lancamentos"])
    # …e NÃO no razão da própria mãe (sem unidade)
    st, out = c.get("/api/financeiro/lancamentos")
    assert st == 200 and not any(l["projeto_id"] == "Proj_PDV_X" for l in out["lancamentos"])


def test_unidade_da_propria_loja_e_neutra(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l1")
    st1, o1 = c.get("/api/financeiro/contas")
    st2, o2 = c.get("/api/financeiro/contas?unidade=%d" % seed["loja1_id"])
    assert st1 == st2 == 200
    assert [x["codigo"] for x in o1["contas"]] == [x["codigo"] for x in o2["contas"]]


# ── PDV: painel financeiro oculto, razão vivo ────────────────────────────────

def test_pdv_user_bloqueado_no_painel_financeiro(http_client_factory, pdv, pdv_user):
    c = _login(http_client_factory, pdv_user)
    st, out = c.get("/api/financeiro/contas")
    assert st == 403 and "loja-mãe" in (out.get("erro") or "")


def test_ui_do_pdv_esconde_o_modulo_financeiro(http_client_factory, pdv, pdv_user):
    c = _login(http_client_factory, pdv_user)
    st, out = c.get("/api/auth/me")
    assert st == 200 and out["ok"]
    assert "financeiro" not in out["usuario"]["modulos_ativos"]
    assert "comercial" in out["usuario"]["modulos_ativos"]   # ciclo comercial segue pleno


def test_pdv_user_bloqueado_na_folha(http_client_factory, pdv, pdv_user):
    """Folha acompanha o Financeiro (depende dele na topologia — QA Vera 🟠):
    some da UI do PDV e a API nega, mesmo para master do PDV, sem step-up."""
    c = _login(http_client_factory, pdv_user)
    st, out = c.get("/api/folha?competencia=2026-07")
    assert st == 403
    st, out = c.get("/api/auth/me")
    assert st == 200 and "folha" not in out["usuario"]["modulos_ativos"]


def test_wiring_de_eventos_do_pdv_continua(app_db, pdv):
    """O que se esconde é a TELA: lançamentos no razão do PDV seguem normais."""
    import main as _main, mod_contabil
    _main._fin_evento_seguro(pdv["id"], "faturamento", 111.0, "Proj_PDV_Wiring", "pdvwire:1")
    db = app_db.get_session()
    try:
        lans = mod_contabil.listar_lancamentos(db, "loja", pdv["id"], projeto_id="Proj_PDV_Wiring")
        assert len(lans) == 1 and lans[0]["ref"] == "pdvwire:1"
    finally:
        db.close()


# ── Auditoria Contábil do projeto: tenant pelo OWNER resolvido, não por loja_id cru ──────────

@pytest.fixture(scope="module")
def projeto_pdv(app_db, pdv):
    db = app_db.get_session()
    try:
        db.add(app_db.Projeto(nome_safe="Proj_PDV_Auditoria", status="quente", loja_id=pdv["id"]))
        db.commit()
    finally:
        db.close()
    return "Proj_PDV_Auditoria"


def test_auditoria_contabil_do_projeto_do_pdv_pela_mae(http_client_factory, pdv, projeto_pdv):
    """Achado do usuário (2026-08-13): o endpoint checava usuario.get('loja_id') cru em vez do
    owner (ot, oid) que _contabil_ctx já resolve — pra mãe vendo um projeto do PDV via
    ?unidade=, isso sempre dava 404 mesmo com acesso legítimo (mesma classe de bug da Sessão 196
    de tenant scope, mas fail-closed — bloqueia quem tem acesso, em vez de vazar pra quem não tem;
    por isso não apareceu naquela auditoria, focada em bypass)."""
    c = _login(http_client_factory, "dir_l1")
    st, out = c.get("/api/projetos/%s/auditoria-contabil?unidade=%d" % (projeto_pdv, pdv["id"]))
    assert st == 200 and out["ok"], (st, out)
    assert out["lancamentos"] == []


def test_auditoria_contabil_nega_projeto_de_outra_unidade(http_client_factory, projeto_pdv):
    """Sem ?unidade=, o razão da mãe é o dela própria — projeto do PDV não aparece (404), não
    vaza. Defende contra o fix acima virar bypass."""
    c = _login(http_client_factory, "dir_l1")
    st, out = c.get("/api/projetos/%s/auditoria-contabil" % projeto_pdv)
    assert st == 404
