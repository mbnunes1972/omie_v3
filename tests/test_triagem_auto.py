# -*- coding: utf-8 -*-
"""RF-08/09 — triagem AUTOMÁTICA (2026-08-04): contato novo no WhatsApp recebe a PERGUNTA de
triagem de volta (texto livre — janela de 24h recém-aberta; sem template) e a RESPOSTA dele
(número/nome do segmento) preenche `segmento_sugerido` na MESMA entrada da fila + envia a
confirmação. Sem credencial Meta o envio nasce `pendente_config` (a rede nunca é tocada em
teste). A resolução segue HUMANA na fila."""
import mod_chat_externo as wa
from chat import triagem as tri
from database import EnvioExterno, TriagemEntrada


# ── puros ────────────────────────────────────────────────────────────────────────

def test_interpretar_resposta():
    ops = [{"segmento": "comercial", "rotulo": "Comercial"},
           {"segmento": "financeiro", "rotulo": "Financeiro"},
           {"segmento": "suporte_tecnico", "rotulo": "Suporte Técnico"}]
    assert tri.interpretar_resposta_triagem("2", ops) == "financeiro"
    assert tri.interpretar_resposta_triagem(" 3. ", ops) == "suporte_tecnico"
    assert tri.interpretar_resposta_triagem("Financeiro", ops) == "financeiro"
    assert tri.interpretar_resposta_triagem("suporte tecnico", ops) == "suporte_tecnico"
    assert tri.interpretar_resposta_triagem("9", ops) is None
    assert tri.interpretar_resposta_triagem("quero comprar um armário", ops) is None
    assert tri.interpretar_resposta_triagem("", ops) is None


def test_montar_pergunta_lista(app_db, seed):
    db = app_db.get_session()
    try:
        texto, ops = tri.montar_pergunta_triagem(db, seed["loja1_id"])
        assert "NÚMERO" in texto and "1. " in texto
        assert ops and ops[0]["segmento"] == "comercial"
    finally:
        db.close()


# ── fluxo completo (sem credencial: pendente_config) ─────────────────────────────

def _limpar(app_db, remetente):
    db = app_db.get_session()
    try:
        for e in db.query(TriagemEntrada).filter_by(remetente=remetente).all():
            db.query(EnvioExterno).filter_by(triagem_id=e.id).delete()
            db.delete(e)
        db.commit()
    finally:
        db.close()


def test_contato_novo_recebe_pergunta_e_resposta_sugere_segmento(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)      # hermético: sem transporte real
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    tel = "5512999990001"
    _limpar(app_db, tel)
    db = app_db.get_session()
    try:
        # 1ª mensagem: cai na fila E dispara a pergunta (pendente_config sem credencial)
        r1 = wa.processar_entrada(db, "whatsapp", tel, "Oi, preciso de um orçamento",
                                  id_externo="wamid.auto.1")
        db.commit()
        assert r1["status"] == "triagem" and r1["triagem_id"]
        envs = db.query(EnvioExterno).filter_by(triagem_id=r1["triagem_id"],
                                                direcao="saida").all()
        assert len(envs) == 1
        assert envs[0].status == "pendente_config"      # sem ORIZON_WA_* no teste
        assert envs[0].mensagem_id is None              # ainda não há conversa
        # 2ª mensagem: escolha "1" → MESMA entrada ganha segmento_sugerido + confirmação
        r2 = wa.processar_entrada(db, "whatsapp", tel, "1", id_externo="wamid.auto.2")
        db.commit()
        assert r2["triagem_id"] == r1["triagem_id"]     # não duplica na fila
        assert r2["segmento_sugerido"] == "comercial"
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert ent.segmento_sugerido == "comercial" and ent.status == "pendente"
        envs = db.query(EnvioExterno).filter_by(triagem_id=ent.id, direcao="saida").all()
        assert len(envs) == 2                           # pergunta + confirmação
        # 3ª mensagem: texto livre depois da escolha → anexa na entrada, sem novo envio
        wa.processar_entrada(db, "whatsapp", tel, "é para uma cozinha",
                             id_externo="wamid.auto.3")
        db.commit()
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert "cozinha" in ent.texto
        assert db.query(EnvioExterno).filter_by(triagem_id=ent.id,
                                                direcao="saida").count() == 2
    finally:
        db.close()


def test_resposta_nao_reconhecida_nao_reenvia_pergunta(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    tel = "5512999990002"
    _limpar(app_db, tel)
    db = app_db.get_session()
    try:
        r1 = wa.processar_entrada(db, "whatsapp", tel, "olá", id_externo="wamid.auto.4")
        db.commit()
        r2 = wa.processar_entrada(db, "whatsapp", tel, "quero falar com alguém",
                                  id_externo="wamid.auto.5")
        db.commit()
        assert r2["triagem_id"] == r1["triagem_id"]
        assert r2["segmento_sugerido"] is None
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert "falar com alguém" in ent.texto          # anexado à mesma entrada
        assert db.query(EnvioExterno).filter_by(triagem_id=ent.id,
                                                direcao="saida").count() == 1   # só a pergunta
    finally:
        db.close()
