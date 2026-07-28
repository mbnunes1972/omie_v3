# -*- coding: utf-8 -*-
"""Revisão do Orizon Chat (Meta/WhatsApp) — Fatia 1: fundação de backend.
Plan: docs/superpowers/plans/2026-07-28-orizon-chat-revisao-meta.md.

Cobre G1 (fornecedor em resolver_destino), G2 (canais compras/parceiros + anti-drift), G4 (janela por
conversa RF-04), G5 (HTTPError da Meta → erro real), G6 (transferência ADICIONA responsável ao grupo)."""
import io
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pytest

import mod_chat
import mod_chat_externo as mce
from database import EnvioExterno, ConversaParticipante


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


# ── G1 — Fornecedor como destinatário externo (RF-03) ──────────────────────────
def test_resolver_destino_fornecedor(app_db, seed):
    db = app_db.get_session()
    try:
        f = app_db.Fornecedor(nome="Forn X", telefone="11988887777")
        db.add(f); db.flush()
        dest, err = mce.resolver_destino(db, "whatsapp", "fornecedor", f.id, None)
        assert err is None and "11988887777" in dest
        f2 = app_db.Fornecedor(nome="Sem tel"); db.add(f2); db.flush()
        dest2, err2 = mce.resolver_destino(db, "whatsapp", "fornecedor", f2.id, None)
        assert dest2 is None and "WhatsApp" in (err2 or "")
    finally:
        db.close()


# ── G2 — canais compras/parceiros + anti-drift ─────────────────────────────────
def test_canais_compras_parceiros_e_anti_drift():
    assert {"compras", "parceiros"} <= set(mod_chat.CANAIS)
    assert {"compras", "parceiros"} <= set(mce.CANAIS_EXTERNOS)
    assert set(mce.CANAIS_EXTERNOS) <= (set(mod_chat.CANAIS) - {"interno"})   # anti-drift


# ── G4 — janela de 24h por conversa (RF-04) ────────────────────────────────────
def test_janela_da_conversa(app_db, seed):
    db = app_db.get_session()
    try:
        crid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G jan", [], exige_dois=False); db.flush()
        assert mce.janela_da_conversa(db, conv)["aberta"] is False           # sem externo/entrada
        mod_chat.adicionar_externo(db, conv, "Cli", telefone="11912345678", meio="whatsapp"); db.flush()
        msg = mod_chat.enviar_mensagem(db, conv, None, "oi", canal="comercial", _permitir_externo=True); db.flush()
        env = EnvioExterno(mensagem_id=msg.id, meio="whatsapp", direcao="entrada",
                           destino="5511912345678", status="recebido",
                           criado_em=datetime.utcnow() - timedelta(hours=1))
        db.add(env); db.flush()
        j1 = mce.janela_da_conversa(db, conv)
        assert j1["aberta"] is True and j1["restante_seg"] > 0 and j1["excedido_seg"] is None
        env.criado_em = datetime.utcnow() - timedelta(hours=30); db.flush()
        j2 = mce.janela_da_conversa(db, conv)
        assert j2["aberta"] is False and j2["excedido_seg"] > 0
    finally:
        db.close()


# ── G5 — HTTPError da Meta vira o erro real (não "HTTP 400") ────────────────────
def test_erro_meta_extrai_mensagem_real():
    he = urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(
        b'{"error":{"message":"Message failed to send because more than 24 hours have passed","code":131047}}'))
    msg = mce._erro_meta(he)
    assert "131047" in msg and "24 hours" in msg


def test_enviar_whatsapp_httperror(monkeypatch):
    def _boom(req, timeout=15):
        raise urllib.error.HTTPError(getattr(req, "full_url", "u"), 400, "Bad Request", {},
                                     io.BytesIO(b'{"error":{"message":"janela fechada","code":131047}}'))
    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    class _Env:
        destino = "5511999998888"; canal = "comercial"
    with pytest.raises(RuntimeError) as ei:
        mce._enviar_whatsapp(_Env(), "oi")
    assert "131047" in str(ei.value) and "janela fechada" in str(ei.value)


# ── G6 — transferência ADICIONA o responsável ao grupo (RF-11 / §7) ────────────
def test_transferencia_adiciona_responsavel_ao_grupo(app_db, seed):
    db = app_db.get_session()
    try:
        crid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
        func = app_db.Funcionario(nome="Medidor", loja_id=seed["loja1_id"], usuario_id=u.id, status="ativo")
        db.add(func); db.flush()
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G transf", [], exige_dois=False); db.flush()
        mod_chat.enviar_mensagem(db, conv, crid, "passa pro medidor", natureza="transferencia",
                                 etapa_codigo="10", transferido_para_funcionario_id=func.id); db.flush()
        ativos = {p.usuario_id for p in db.query(ConversaParticipante)
                  .filter_by(conversa_id=conv.id, removido=0).all()}
        assert u.id in ativos and crid in ativos                             # destino ENTRA, criador PERMANECE
        # idempotente: transferir de novo não duplica
        mod_chat.enviar_mensagem(db, conv, crid, "de novo", natureza="transferencia",
                                 etapa_codigo="10", transferido_para_funcionario_id=func.id); db.flush()
        assert db.query(ConversaParticipante).filter_by(conversa_id=conv.id, usuario_id=u.id).count() == 1
    finally:
        db.close()


# ── Fatia 2 — biblioteca de templates (RF-07) ──────────────────────────────────
def test_slots_obrigatorios_sao_nove():
    assert len(mod_chat.SLOTS_OBRIGATORIOS) == 9
    assert {s["num"] for s in mod_chat.SLOTS_OBRIGATORIOS} == set(range(1, 10))


def test_template_crud_e_slot_unico(app_db, seed):
    db = app_db.get_session()
    try:
        lid = seed["loja1_id"]
        t = mod_chat.criar_template(db, lid, {"nome_meta": "reeng_comercial", "segmento": "comercial",
                                              "slot_obrigatorio": 4, "categoria": "utility"}); db.commit()
        assert t.slot_obrigatorio == 4
        with pytest.raises(ValueError):                                      # slot 4 já ocupado
            mod_chat.criar_template(db, lid, {"nome_meta": "outro", "slot_obrigatorio": 4})
        mod_chat.editar_template(db, lid, t.id, {"status": "aprovado"}); db.commit()
        assert mod_chat.listar_templates(db, lid, segmento="comercial")[0]["status"] == "aprovado"
        mod_chat.remover_template(db, lid, t.id); db.commit()               # remover libera o slot
        mod_chat.criar_template(db, lid, {"nome_meta": "novo4", "slot_obrigatorio": 4}); db.commit()
    finally:
        db.close()


def test_template_endpoint_e_tenancy(http_client_factory, app_db, seed):
    ger = _login(http_client_factory, "dir_l1")
    st, b = ger.post("/api/comunicacao/templates",   # slot 5 (o de CRUD usa o 4 — evita colisão no módulo)
                     {"nome_meta": "t_suporte", "segmento": "suporte_tecnico", "slot_obrigatorio": 5})
    assert st == 201, b
    tid = b["template"]["id"]
    st, b = ger.get("/api/comunicacao/templates")
    assert st == 200 and len(b["slots"]) == 9 and any(t["id"] == tid for t in b["templates"])
    op = _login(http_client_factory, "cons_l1")                             # operador não gere
    assert op.post("/api/comunicacao/templates", {"nome_meta": "x"})[0] == 403
    assert op.get("/api/comunicacao/templates")[0] == 403
    outro = _login(http_client_factory, "dir_l2")                           # loja 2 não vê/edita
    st, b = outro.get("/api/comunicacao/templates")
    assert st == 200 and all(t["id"] != tid for t in b["templates"])
    assert outro.post("/api/comunicacao/templates/%d" % tid, {"status": "aprovado"})[0] == 404
