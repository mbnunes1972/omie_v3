# -*- coding: utf-8 -*-
"""Chat do Orizon — Fatia 1 (Fundação), spec
docs/superpowers/specs/_geral/2026-07-25-chat-projeto-porta-externa-whatsapp-email-design.md.

Escopo DESTA fatia: Conversa com âncora FLEXÍVEL (projeto e/ou cliente, ambos opcionais —
decisão da seção 2 da spec) + Mensagem interna (autor, corpo, canal, criado_em) + endpoints
da aba "Conversa" do projeto. FORA (fatias 2-7): natureza/transferência, bloqueador, modo
privado, EnvioExterno, canais externos — a Fatia 1 só aceita canal 'interno'."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


# ── modelo ───────────────────────────────────────────────────────────────────

def test_conversa_ancora_flexivel(app_db, seed):
    """Projeto, só cliente, ou NENHUM dos dois (reclamação institucional) — todas válidas."""
    import mod_chat
    db = app_db.get_session()
    l1 = seed["loja1_id"]
    com_projeto = mod_chat.get_or_create_conversa_projeto(db, l1, "Proj_L1",
                                                          cliente_id=seed["cliente_l1_id"])
    assert com_projeto.projeto_nome == "Proj_L1" and com_projeto.cliente_id == seed["cliente_l1_id"]
    so_cliente = app_db.Conversa(loja_id=l1, cliente_id=seed["cliente_l1_id"])
    sem_vinculo = app_db.Conversa(loja_id=l1)          # institucional: os dois em branco
    db.add_all([so_cliente, sem_vinculo]); db.commit()
    assert so_cliente.id and so_cliente.projeto_nome is None
    assert sem_vinculo.id and sem_vinculo.projeto_nome is None and sem_vinculo.cliente_id is None
    db.close()


def test_get_or_create_e_idempotente(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    a = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1")
    db.commit()
    b = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1")
    assert a.id == b.id                                 # NÃO duplica a conversa do projeto
    db.close()


def test_mensagem_validacoes(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1")
    db.flush()
    with pytest.raises(ValueError):
        mod_chat.enviar_mensagem(db, conv, None, "   ")            # corpo vazio
    with pytest.raises(ValueError):
        mod_chat.enviar_mensagem(db, conv, None, "oi", canal="zap")  # canal inexistente
    with pytest.raises(ValueError):
        mod_chat.enviar_mensagem(db, conv, None, "oi", canal="sac")  # externo: fatia futura
    db.rollback(); db.close()


# ── endpoints da aba Conversa ────────────────────────────────────────────────

def test_get_conversa_cria_e_repete_o_mesmo_id(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/projetos/Proj_L1/conversa")
    assert st == 200 and body["ok"], body
    cid = body["conversa"]["id"]
    assert body["conversa"]["projeto_nome"] == "Proj_L1"
    assert body["conversa"]["cliente_id"] == seed["cliente_l1_id"]   # herdado do projeto
    assert body["mensagens"] == []
    st, body = c.get("/api/projetos/Proj_L1/conversa")
    assert body["conversa"]["id"] == cid                             # idempotente


def test_enviar_e_listar_cronologico(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens", {"corpo": "primeira"})
    assert st == 201 and body["ok"], body
    assert body["mensagem"]["canal"] == "interno"
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens", {"corpo": "segunda"})
    assert st == 201, body
    st, body = c.get("/api/projetos/Proj_L1/conversa")
    corpos = [m["corpo"] for m in body["mensagens"]]
    assert corpos == ["primeira", "segunda"]                         # cronológico ASC
    m = body["mensagens"][0]
    assert m["autor_nome"] == "Diretor L1" and m["criado_em"]


def test_corpo_vazio_da_400(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens", {"corpo": "  "})
    assert st == 400 and body["ok"] is False


def test_tenancy_projeto_de_outra_loja_404(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    assert c.get("/api/projetos/Proj_L1/conversa")[0] == 404
    assert c.post("/api/projetos/Proj_L1/conversa/mensagens", {"corpo": "x"})[0] == 404


def test_exige_login(http_client_factory, seed):
    c = http_client_factory()
    assert c.get("/api/projetos/Proj_L1/conversa")[0] == 401
