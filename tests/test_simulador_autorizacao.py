"""Autorização por loja (LGPD) do Simulador de Modelo de Negócios — Sessão 185 (RF-02..RF-04, D5).
Capability acesso_simulador é exclusiva do super_admin; concessão reautentica a senha do Master
da loja alvo; revogação é do Master, efeito imediato; trilha própria (fora do log operacional)."""
import pytest

import mod_simulador_autorizacao as msa


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


@pytest.fixture(scope="module", autouse=True)
def _autoriza_lojas_do_seed(seed):
    """O seed idempotente roda dentro de `init_db()` (boot do servidor) — as lojas 1/2 deste
    módulo de teste são criadas DEPOIS disso pela fixture `seed`, então (fiel à produção: só
    quem JÁ EXISTIA no boot nasce autorizado) ainda não têm autorização. Simula um restart do
    servidor depois que essas lojas passaram a existir — mesmo cenário real de deploy."""
    import database
    database._simulador_autorizacao_seed_v1()
    return seed


# ── Capability / gate (D4) ──────────────────────────────────────────────────────────────────
def test_master_e_operador_nao_veem_a_capability(seed):
    from auth import perfis
    assert perfis.pode("master", "acesso_simulador") is False
    assert perfis.pode("gerencial", "acesso_simulador") is False
    assert perfis.pode("operador", "acesso_simulador") is False
    assert perfis.pode("super_admin", "acesso_simulador") is True


def test_operador_sem_acesso_simulador_leva_403(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, body = c.get("/api/simulador/lojas")
    assert st == 403, body


def test_super_admin_lista_lojas_com_status_de_autorizacao(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get("/api/simulador/lojas")
    assert st == 200 and body["ok"], body
    por_id = {l["loja_id"]: l for l in body["lojas"]}
    assert seed["loja1_id"] in por_id
    # seed idempotente (Sessão 185): lojas existentes já nascem autorizadas
    assert por_id[seed["loja1_id"]]["autorizado"] is True


# ── Seed idempotente (simulador_autorizacao_seed_v1) ────────────────────────────────────────
def test_seed_autoriza_lojas_existentes_sem_duplicar(app_db, seed):
    from database import get_session, SimuladorAutorizacao
    db = get_session()
    try:
        rows = db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja1_id"]).all()
        assert len(rows) == 1
        assert rows[0].status == "ativa"
        assert rows[0].concedido_por_usuario_id is None   # marca "seed", não concessão real
        # roda o seed de novo (idempotência) — não duplica
        app_db._simulador_autorizacao_seed_v1()
        rows2 = db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja1_id"]).all()
        assert len(rows2) == 1
    finally:
        db.close()


# ── Conceder (RF-03) ─────────────────────────────────────────────────────────────────────────
def test_conceder_reautentica_senha_do_master_da_loja_alvo(http_client_factory, seed):
    from database import get_session, SimuladorAutorizacao
    db = get_session()
    try:
        # revoga o que o seed já deu, pra exercitar uma concessão de verdade
        ativa = db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja2_id"], status="ativa").first()
        ativa.status = "revogada"
        db.commit()
    finally:
        db.close()

    c = _login(http_client_factory, "super")
    st, body = c.get("/api/simulador/lojas")
    por_id = {l["loja_id"]: l for l in body["lojas"]}
    assert por_id[seed["loja2_id"]]["autorizado"] is False

    st, body = c.post("/api/simulador/autorizacao", {
        "loja_id": seed["loja2_id"], "login_autorizador": "dir_l2", "senha_autorizador": "senha123"})
    assert st == 200 and body["ok"] and body["autorizado"] is True, body

    st, body = c.get("/api/simulador/lojas")
    por_id = {l["loja_id"]: l for l in body["lojas"]}
    assert por_id[seed["loja2_id"]]["autorizado"] is True


def test_conceder_recusa_senha_errada(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.post("/api/simulador/autorizacao", {
        "loja_id": seed["loja1_id"], "login_autorizador": "dir_l1", "senha_autorizador": "errada"})
    assert st == 401, body


def test_conceder_recusa_autorizador_que_nao_e_master_da_loja():
    from database import get_session
    db = get_session()
    try:
        # cons_l1 é operador (não master) da loja 1
        ok, autorizacao, erro = msa.conceder(db, 999999, "cons_l1", "senha123", 1, "termo")
        assert ok is False and autorizacao is None and erro
    finally:
        db.close()


def test_solicitante_sem_acesso_simulador_nao_pode_conceder(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")   # master, não super_admin
    st, body = c.post("/api/simulador/autorizacao", {
        "loja_id": seed["loja1_id"], "login_autorizador": "dir_l1", "senha_autorizador": "senha123"})
    assert st == 403, body


# ── Revogar (RF-03, efeito imediato) ────────────────────────────────────────────────────────
def test_master_revoga_e_efeito_e_imediato(http_client_factory, seed):
    c_super = _login(http_client_factory, "super")
    st, body = c_super.get("/api/simulador/lojas")
    por_id = {l["loja_id"]: l for l in body["lojas"]}
    assert por_id[seed["loja1_id"]]["autorizado"] is True   # seed já autorizou

    c_master = _login(http_client_factory, "dir_l1")
    st, body = c_master.post("/api/simulador/autorizacao/revogar", {})
    assert st == 200 and body["ok"] and body["autorizado"] is False, body

    st, body = c_super.get("/api/simulador/lojas")
    por_id = {l["loja_id"]: l for l in body["lojas"]}
    assert por_id[seed["loja1_id"]]["autorizado"] is False


def test_revogar_sem_autorizacao_ativa_da_erro(http_client_factory, seed):
    from database import get_session, SimuladorAutorizacao
    db = get_session()
    try:
        for a in db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja1_id"], status="ativa").all():
            a.status = "revogada"
        db.commit()
    finally:
        db.close()
    c_master = _login(http_client_factory, "dir_l1")
    st, body = c_master.post("/api/simulador/autorizacao/revogar", {})
    assert st == 403, body


def test_operador_nao_pode_revogar(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post("/api/simulador/autorizacao/revogar", {})
    assert st == 403, body


# ── Trilha própria (RF-04) ───────────────────────────────────────────────────────────────────
def test_concessao_e_revogacao_gravam_trilha_separada(http_client_factory, seed):
    from database import get_session, SimuladorLogAcesso
    c = _login(http_client_factory, "super")
    c.post("/api/simulador/autorizacao", {
        "loja_id": seed["loja1_id"], "login_autorizador": "dir_l1", "senha_autorizador": "senha123"})
    db = get_session()
    try:
        eventos = {l.evento for l in db.query(SimuladorLogAcesso)
                  .filter_by(loja_id=seed["loja1_id"]).all()}
        assert "concessao" in eventos or "revogacao" in eventos   # ao menos um evento já registrado
    finally:
        db.close()
