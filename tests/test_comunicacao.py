# -*- coding: utf-8 -*-
"""Central de Comunicação — Fatia 1 (núcleo interno), spec
docs/superpowers/specs/_geral/2026-07-27-central-comunicacao-omnichannel-design.md.

Escopo DESTA fatia: conversa `direct` (1:1, idempotente pela dupla) e `grupo` (N + título),
inbox por usuário, envio/listagem de mensagens com auth por participante, seletor de usuários
da loja e segmento derivado da função. Tenancy: nada cruza loja. FORA: público, não-lidos,
anexos, ponte WhatsApp (fatias 2-4)."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _uid(app_db, login):
    db = app_db.get_session()
    try:
        return db.query(app_db.Usuario).filter_by(login=login).first().id
    finally:
        db.close()


# ── direct ────────────────────────────────────────────────────────────────────

def test_criar_direct_idempotente(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    st, b = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": alvo})
    assert st == 201 and b["ok"], b
    assert b["conversa"]["tipo"] == "direct"
    cid = b["conversa"]["id"]
    st, b2 = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": alvo})
    assert st == 201 and b2["conversa"]["id"] == cid          # não duplica a dupla


def test_direct_consigo_mesmo_400(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    eu = _uid(app_db, "dir_l1")
    st, b = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": eu})
    assert st == 400 and b["ok"] is False


def test_direct_com_usuario_de_outra_loja_400(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    outro = _uid(app_db, "dir_l2")                            # loja 2
    st, b = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": outro})
    assert st == 400 and b["ok"] is False                     # não vaza entre lojas


# ── grupo ───────────────────────────────────────────────────────────────────--

def test_criar_grupo(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    st, b = c.post("/api/comunicacao/conversas",
                   {"tipo": "grupo", "titulo": "Equipe Obra", "participante_ids": [alvo]})
    assert st == 201 and b["conversa"]["tipo"] == "grupo"
    assert b["conversa"]["titulo"] == "Equipe Obra"


def test_grupo_sem_titulo_400(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    st, b = c.post("/api/comunicacao/conversas",
                   {"tipo": "grupo", "titulo": "  ", "participante_ids": [alvo]})
    assert st == 400 and b["ok"] is False


# ── mensagens + auth por participante ──────────────────────────────────────────

def test_enviar_e_listar(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    st, b = dono.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "olá"})
    assert st == 201 and b["mensagem"]["corpo"] == "olá", b
    # o outro participante lê
    outro = _login(http_client_factory, "cons_l1")
    st, b = outro.get("/api/comunicacao/conversas/%d/mensagens" % cid)
    assert st == 200 and [m["corpo"] for m in b["mensagens"]] == ["olá"]


def test_nao_participante_nao_le_nem_posta(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    # 3º usuário da MESMA loja, mas fora da conversa
    db = app_db.get_session()
    u = app_db.Usuario(nome="Fulano L1", login="fulano_l1", nivel="operador",
                       loja_id=seed["loja1_id"], ativo=1)
    u.set_senha("senha123"); db.add(u); db.commit(); db.close()
    terceiro = _login(http_client_factory, "fulano_l1")
    assert terceiro.get("/api/comunicacao/conversas/%d/mensagens" % cid)[0] == 404
    assert terceiro.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "x"})[0] == 404


def test_conversa_de_outra_loja_404(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    forasteiro = _login(http_client_factory, "dir_l2")
    assert forasteiro.get("/api/comunicacao/conversas/%d/mensagens" % cid)[0] == 404


# ── inbox ──────────────────────────────────────────────────────────────────────

def test_inbox_lista_conversas_do_usuario(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    dono.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "oi inbox"})
    st, b = dono.get("/api/comunicacao/inbox")
    assert st == 200 and b["ok"]
    achou = [x for x in b["conversas"] if x["id"] == cid]
    assert achou and achou[0]["ultima_previa"] == "oi inbox"
    # direct: o título mostrado é o nome do OUTRO
    assert achou[0]["titulo"] == "Consultor L1"


# ── seletor de usuários da loja ────────────────────────────────────────────────

def test_usuarios_da_loja_exclui_o_proprio(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    st, b = c.get("/api/comunicacao/usuarios")
    assert st == 200 and b["ok"]
    logins_nomes = [u["nome"] for u in b["usuarios"]]
    assert "Consultor L1" in logins_nomes
    assert "Diretor L1" not in logins_nomes                   # não se lista
    assert "Diretor L2" not in logins_nomes                   # outra loja não aparece


# ── segmento derivado da função ────────────────────────────────────────────────

def test_canal_segmento_vem_da_funcao(http_client_factory, app_db, seed):
    # dá a cons_l1 uma função "Financeiro" na loja 1
    db = app_db.get_session()
    fn = app_db.Funcao(nome="Financeiro", loja_id=seed["loja1_id"])
    db.add(fn); db.flush()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    u.funcao_id = fn.id
    db.commit(); db.close()

    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    autor = _login(http_client_factory, "cons_l1")
    st, b = autor.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "fin"})
    assert st == 201 and b["mensagem"]["canal_segmento"] == "financeiro", b


# ── auth ────────────────────────────────────────────────────────────────────---

def test_inbox_exige_login(http_client_factory, seed):
    c = http_client_factory()
    assert c.get("/api/comunicacao/inbox")[0] == 401
