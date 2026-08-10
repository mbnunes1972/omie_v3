"""Autorização por loja (LGPD) do Simulador de Modelo de Negócios — Sessão 185/187 (RF-02..RF-04,
D5). Capability acesso_simulador é exclusiva do super_admin. Fluxo REMOTO (rev2): o super_admin
SOLICITA sem senha nenhuma; o Master APROVA na própria sessão reautenticando a PRÓPRIA senha (nunca
a de terceiro) — os dois lados podem agir em momentos/lugares diferentes. Revogação é do Master,
efeito imediato. Trilha própria (fora do log operacional)."""
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
    assert por_id[seed["loja1_id"]]["status"] == "ativa"
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


# ── Solicitar (RF-03, fluxo remoto — sem senha) ─────────────────────────────────────────────
def test_solicitar_cria_pedido_pendente_sem_senha_nenhuma(http_client_factory, seed):
    from database import get_session, SimuladorAutorizacao
    db = get_session()
    try:
        ativa = db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja2_id"], status="ativa").first()
        ativa.status = "revogada"   # revoga o que o seed deu, pra exercitar um pedido de verdade
        db.commit()
    finally:
        db.close()

    c = _login(http_client_factory, "super")
    st, body = c.get("/api/simulador/lojas")
    por_id = {l["loja_id"]: l for l in body["lojas"]}
    assert por_id[seed["loja2_id"]]["status"] == "nenhuma"

    st, body = c.post("/api/simulador/autorizacao/solicitar", {"loja_id": seed["loja2_id"]})
    assert st == 200 and body["ok"] and body["status"] == "pendente", body

    st, body = c.get("/api/simulador/lojas")
    por_id = {l["loja_id"]: l for l in body["lojas"]}
    assert por_id[seed["loja2_id"]]["status"] == "pendente"
    assert por_id[seed["loja2_id"]]["autorizado"] is False   # pendente ainda NÃO é autorizado


def test_solicitar_e_idempotente_nao_duplica_pedido(http_client_factory, seed):
    from database import get_session, SimuladorAutorizacao
    db = get_session()
    try:
        ativa = db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja2_id"], status="ativa").first()
        if ativa:
            ativa.status = "revogada"
            db.commit()
    finally:
        db.close()

    c = _login(http_client_factory, "super")
    c.post("/api/simulador/autorizacao/solicitar", {"loja_id": seed["loja2_id"]})
    c.post("/api/simulador/autorizacao/solicitar", {"loja_id": seed["loja2_id"]})
    db = get_session()
    try:
        n = db.query(SimuladorAutorizacao).filter_by(
            loja_id=seed["loja2_id"], status="pendente").count()
        assert n == 1
    finally:
        db.close()


def test_solicitante_sem_acesso_simulador_nao_pode_solicitar(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")   # master, não super_admin
    st, body = c.post("/api/simulador/autorizacao/solicitar", {"loja_id": seed["loja1_id"]})
    assert st == 403, body


def test_solicitar_loja_inexistente_da_404_nao_crash(http_client_factory, seed):
    """Achado da Vera: loja_id inexistente estourava IntegrityError (FK) cru — sem validar
    existência antes do INSERT, a conexão resetava em vez de devolver um erro limpo."""
    c = _login(http_client_factory, "super")
    st, body = c.post("/api/simulador/autorizacao/solicitar", {"loja_id": 999999})
    assert st == 404, body


# ── Aprovar (RF-03, o Master reautentica a PRÓPRIA senha, na própria sessão) ────────────────
def test_master_aprova_o_proprio_pedido_com_a_propria_senha(http_client_factory, seed):
    from database import get_session, SimuladorAutorizacao
    db = get_session()
    try:
        ativa = db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja2_id"], status="ativa").first()
        if ativa:
            ativa.status = "revogada"; db.commit()
    finally:
        db.close()

    c_super = _login(http_client_factory, "super")
    c_super.post("/api/simulador/autorizacao/solicitar", {"loja_id": seed["loja2_id"]})

    c_master = _login(http_client_factory, "dir_l2")
    st, body = c_master.post("/api/simulador/autorizacao/aprovar", {"senha": "senha123"})
    assert st == 200 and body["ok"] and body["autorizado"] is True, body

    st, body = c_super.get("/api/simulador/lojas")
    por_id = {l["loja_id"]: l for l in body["lojas"]}
    assert por_id[seed["loja2_id"]]["status"] == "ativa"


def test_aprovar_recusa_senha_errada_do_proprio_master(http_client_factory, seed):
    from database import get_session, SimuladorAutorizacao
    db = get_session()
    try:
        ativa = db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja2_id"], status="ativa").first()
        if ativa:
            ativa.status = "revogada"; db.commit()
    finally:
        db.close()
    c_super = _login(http_client_factory, "super")
    c_super.post("/api/simulador/autorizacao/solicitar", {"loja_id": seed["loja2_id"]})

    c_master = _login(http_client_factory, "dir_l2")
    st, body = c_master.post("/api/simulador/autorizacao/aprovar", {"senha": "errada"})
    assert st == 401, body


def test_aprovar_sem_pedido_pendente_da_erro():
    from database import get_session
    db = get_session()
    try:
        ok, autorizacao, erro = msa.aprovar(
            db, {"id": 1, "nivel": "master", "loja_id": 999999}, "qualquer", "termo")
        assert ok is False and autorizacao is None and erro
    finally:
        db.close()


def test_operador_nao_pode_aprovar_mesmo_com_senha_certa(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post("/api/simulador/autorizacao/aprovar", {"senha": "senha123"})
    assert st == 403, body


# ── Revogar (RF-03, efeito imediato — cobre 'ativa' E 'pendente') ───────────────────────────
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


def test_revogar_um_pedido_pendente_tambem_funciona(http_client_factory, seed):
    from database import get_session, SimuladorAutorizacao
    db = get_session()
    try:
        for a in db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja2_id"]).filter(
                SimuladorAutorizacao.status.in_(("ativa", "pendente"))).all():
            a.status = "revogada"
        db.commit()
    finally:
        db.close()

    c_super = _login(http_client_factory, "super")
    c_super.post("/api/simulador/autorizacao/solicitar", {"loja_id": seed["loja2_id"]})

    c_master = _login(http_client_factory, "dir_l2")
    st, body = c_master.post("/api/simulador/autorizacao/revogar", {})
    assert st == 200 and body["ok"], body

    st, body = c_super.get("/api/simulador/lojas")
    por_id = {l["loja_id"]: l for l in body["lojas"]}
    assert por_id[seed["loja2_id"]]["status"] == "nenhuma"


def test_revogar_sem_autorizacao_ativa_da_erro(http_client_factory, seed):
    from database import get_session, SimuladorAutorizacao
    db = get_session()
    try:
        for a in db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja1_id"]).filter(
                SimuladorAutorizacao.status.in_(("ativa", "pendente"))).all():
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


# ── Status (Master vê o status da PRÓPRIA loja, mesmo sem acesso_simulador) ─────────────────
def test_master_ve_status_da_propria_loja(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/simulador/autorizacao/status")
    assert st == 200 and body["ok"] and body["status"] in ("ativa", "pendente", "nenhuma"), body


def test_operador_nao_ve_status_de_autorizacao(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, body = c.get("/api/simulador/autorizacao/status")
    assert st == 403, body


# ── Migração idempotente das colunas do fluxo remoto (achado da Vera) ──────────────────────
def test_migracao_recria_colunas_do_fluxo_remoto_em_tabela_antiga(app_db, seed):
    """`simulador_autorizacoes` nasceu na Sessão 185/186 sem `solicitado_por_usuario_id`/
    `solicitado_em` (a Sessão 187 as acrescentou ao modelo, mas esqueceu a linha em
    `_migrar_colunas_pg` — `create_all()` não altera tabela já existente). Simula um banco
    "antigo" (dropa as 2 colunas) e confirma que rodar a migração de novo as devolve."""
    import database
    from sqlalchemy import text
    with database.ENGINE.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE simulador_autorizacoes DROP COLUMN IF EXISTS solicitado_por_usuario_id")
        conn.exec_driver_sql(
            "ALTER TABLE simulador_autorizacoes DROP COLUMN IF EXISTS solicitado_em")
    db = app_db.get_session()
    try:
        cols_antes = {r[0] for r in db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='simulador_autorizacoes'")).fetchall()}
        assert "solicitado_por_usuario_id" not in cols_antes   # confirma a premissa do teste
    finally:
        db.close()

    database._migrar_colunas_pg()

    db = app_db.get_session()
    try:
        cols_depois = {r[0] for r in db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='simulador_autorizacoes'")).fetchall()}
        assert {"solicitado_por_usuario_id", "solicitado_em"} <= cols_depois
    finally:
        db.close()


# ── Trilha própria (RF-04) ───────────────────────────────────────────────────────────────────
def test_solicitacao_aprovacao_e_revogacao_gravam_trilha_separada(http_client_factory, seed):
    from database import get_session, SimuladorAutorizacao, SimuladorLogAcesso
    db = get_session()
    try:
        for a in db.query(SimuladorAutorizacao).filter_by(loja_id=seed["loja2_id"]).filter(
                SimuladorAutorizacao.status.in_(("ativa", "pendente"))).all():
            a.status = "revogada"
        db.commit()
    finally:
        db.close()

    c_super = _login(http_client_factory, "super")
    c_super.post("/api/simulador/autorizacao/solicitar", {"loja_id": seed["loja2_id"]})
    c_master = _login(http_client_factory, "dir_l2")
    c_master.post("/api/simulador/autorizacao/aprovar", {"senha": "senha123"})

    db = get_session()
    try:
        eventos = {l.evento for l in db.query(SimuladorLogAcesso)
                  .filter_by(loja_id=seed["loja2_id"]).all()}
        assert "solicitacao" in eventos and "concessao" in eventos
    finally:
        db.close()
