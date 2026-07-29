# -*- coding: utf-8 -*-
"""Revisão do Orizon Chat (Meta/WhatsApp) — Fatia 1: fundação de backend.
Plan: docs/superpowers/plans/2026-07-28-orizon-chat-revisao-meta.md.

Cobre G1 (fornecedor em resolver_destino), G2 (canais compras/parceiros + anti-drift), G4 (janela por
conversa RF-04), G5 (HTTPError da Meta → erro real), G6 (transferência ADICIONA responsável ao grupo)."""
import io
import json
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


def test_janela_escopada_por_conversa(app_db, seed):
    """Achado da Vera 🟠: a janela é da CONVERSA — não vaza entre conversas/lojas com o mesmo número."""
    db = app_db.get_session()
    try:
        cr1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        cr2 = db.query(app_db.Usuario).filter_by(login="dir_l2").first().id
        convA = mod_chat.criar_grupo(db, seed["loja1_id"], cr1, "JA", [], exige_dois=False)
        convB = mod_chat.criar_grupo(db, seed["loja2_id"], cr2, "JB", [], exige_dois=False); db.flush()
        msg = mod_chat.enviar_mensagem(db, convB, None, "oi", canal="comercial", _permitir_externo=True); db.flush()
        db.add(EnvioExterno(mensagem_id=msg.id, meio="whatsapp", direcao="entrada",
                            destino="5511912345678", status="recebido",
                            criado_em=datetime.utcnow() - timedelta(hours=1))); db.flush()
        assert mce.janela_da_conversa(db, convB)["aberta"] is True
        assert mce.janela_da_conversa(db, convA)["aberta"] is False        # entrada de B não vaza p/ A
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


# ── Fatia 6 (backend) — config de triagem (RF-08) ──────────────────────────────
def test_triagem_config_default_e_salvar(app_db, seed):
    db = app_db.get_session()
    try:
        d = mod_chat.triagem_config_get(db, seed["loja1_id"])                # default
        assert d["formato"] == "lista"
        segs = {i["segmento"] for i in d["itens"]}
        assert segs == set(mod_chat.SEGMENTOS) and len(d["itens"]) == 7      # os 7 segmentos, incl. SAC
        porseg = {i["segmento"]: i for i in d["itens"]}
        assert porseg["sac"]["ativo"] is True and porseg["compras"]["ativo"] is False
        cfg = mod_chat.triagem_config_salvar(db, seed["loja1_id"], {
            "formato": "livre", "mensagem_livre": "Oi!",
            "itens": [{"segmento": "comercial", "rotulo": "Vendas", "ativo": True},
                      {"segmento": "xpto", "rotulo": "ignora", "ativo": True}]}); db.commit()
        assert cfg["formato"] == "livre" and cfg["mensagem_livre"] == "Oi!"
        itens = mod_chat.triagem_config_get(db, seed["loja1_id"])["itens"]
        assert len(itens) == 1 and itens[0]["rotulo"] == "Vendas"           # segmento inválido descartado
    finally:
        db.close()


def test_triagem_endpoint_e_tenancy(http_client_factory, app_db, seed):
    ger = _login(http_client_factory, "dir_l1")
    st, b = ger.get("/api/comunicacao/triagem")
    assert st == 200 and b["triagem"]["formato"] in ("lista", "livre")
    st, b = ger.post("/api/comunicacao/triagem",
                     {"formato": "lista", "itens": [{"segmento": "financeiro", "rotulo": "Fin", "ativo": True}]})
    assert st == 200 and b["triagem"]["itens"][0]["segmento"] == "financeiro"
    outro = _login(http_client_factory, "dir_l2")                           # loja 2 = config própria (default)
    assert any(i["segmento"] == "comercial" for i in outro.get("/api/comunicacao/triagem")[1]["triagem"]["itens"])
    op = _login(http_client_factory, "cons_l1")                             # operador não gere
    assert op.get("/api/comunicacao/triagem")[0] == 403
    assert op.post("/api/comunicacao/triagem", {})[0] == 403


# ── Config de segmentos (RF-02) ────────────────────────────────────────────────
def test_segmentos_config_get_e_salvar(app_db, seed):
    db = app_db.get_session()
    try:
        lid = seed["loja1_id"]
        d = mod_chat.segmentos_config_get(db, lid)
        assert len(d) == 7 and all(s["ativo"] for s in d)                   # default: 7 ativos
        t = mod_chat.criar_template(db, lid, {"nome_meta": "c1", "segmento": "comercial"}); db.commit()  # sem slot
        mod_chat.segmentos_config_salvar(db, lid, [
            {"segmento": "comercial", "rotulo": "Vendas", "ativo": True, "template_padrao_id": t.id},
            {"segmento": "compras", "ativo": False},
            {"segmento": "xpto", "ativo": True}]); db.commit()              # inválido ignorado
        by = {s["segmento"]: s for s in mod_chat.segmentos_config_get(db, lid)}
        assert by["comercial"]["rotulo"] == "Vendas" and by["comercial"]["template_padrao_id"] == t.id
        assert by["compras"]["ativo"] is False
        cfg2 = mod_chat.segmentos_config_salvar(db, lid, [{"segmento": "financeiro", "template_padrao_id": t.id}])
        assert {s["segmento"]: s for s in cfg2}["financeiro"]["template_padrao_id"] is None  # template de outro segmento
        # achado da Vera: template INATIVO (soft-deletado) não vira padrão
        mod_chat.remover_template(db, lid, t.id); db.commit()
        cfg3 = mod_chat.segmentos_config_salvar(db, lid, [{"segmento": "comercial", "template_padrao_id": t.id}])
        assert {s["segmento"]: s for s in cfg3}["comercial"]["template_padrao_id"] is None
    finally:
        db.close()


def test_segmentos_endpoint_e_tenancy(http_client_factory, app_db, seed):
    ger = _login(http_client_factory, "dir_l1")
    assert len(ger.get("/api/comunicacao/segmentos")[1]["segmentos"]) == 7
    op = _login(http_client_factory, "cons_l1")
    assert op.get("/api/comunicacao/segmentos")[0] == 403
    assert op.post("/api/comunicacao/segmentos", {"itens": []})[0] == 403


def test_numero_conectado_get_e_salvar(app_db, seed, monkeypatch):
    db = app_db.get_session()
    try:
        lid = seed["loja1_id"]
        # sem linha salva → número/rótulo vazios, mas o status do transporte é informado
        d = mod_chat.numero_conectado_get(db, lid)
        assert d["numero"] == "" and d["rotulo"] == ""
        assert set(("conectado", "estado", "token_presente", "phone_id_presente")).issubset(d["transporte"])
        # sem credencial de ambiente → pendente_config (a rede não é tocada)
        monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
        monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
        d0 = mod_chat.numero_conectado_get(db, lid)
        assert d0["transporte"]["conectado"] is False and d0["transporte"]["estado"] == "pendente_config"
        # com as duas variáveis → conectado (mas NUNCA devolve os valores)
        monkeypatch.setenv("ORIZON_WA_TOKEN", "tok-secreto")
        monkeypatch.setenv("ORIZON_WA_PHONE_ID", "123456")
        d1 = mod_chat.numero_conectado_get(db, lid)
        assert d1["transporte"]["conectado"] is True and d1["transporte"]["estado"] == "conectado"
        assert "tok-secreto" not in json.dumps(d1) and "123456" not in json.dumps(d1)
        # salvar o número exibível da loja (RF-01)
        r = mod_chat.numero_conectado_salvar(db, lid, "+55 12 99604-9888", "Dalmóbile"); db.commit()
        assert r["numero"] == "+55 12 99604-9888" and r["rotulo"] == "Dalmóbile"
        assert mod_chat.numero_conectado_get(db, lid)["numero"] == "+55 12 99604-9888"
    finally:
        db.close()


def test_numero_endpoint_e_tenancy(http_client_factory, app_db, seed):
    ger = _login(http_client_factory, "dir_l1")
    st, bd = ger.get("/api/comunicacao/numeros")
    assert st == 200 and "transporte" in bd["numero"]
    assert ger.post("/api/comunicacao/numeros", {"numero": "+55 12 99604-9888", "rotulo": "Loja"})[0] == 200
    assert ger.get("/api/comunicacao/numeros")[1]["numero"]["numero"] == "+55 12 99604-9888"
    op = _login(http_client_factory, "cons_l1")
    assert op.get("/api/comunicacao/numeros")[0] == 403
    assert op.post("/api/comunicacao/numeros", {"numero": "x"})[0] == 403


def test_consumo_por_segmento(app_db, seed):
    db = app_db.get_session()
    try:
        lid = seed["loja1_id"]
        cr = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        conv = mod_chat.criar_grupo(db, lid, cr, "Consumo", [], exige_dois=False); db.flush()
        m = mod_chat.enviar_mensagem(db, conv, None, "x", canal="comercial", _permitir_externo=True); db.flush()
        for st in ("enviado", "enviado", "pendente_config"):     # 2 enviados + 1 pendente (comercial)
            db.add(EnvioExterno(mensagem_id=m.id, meio="whatsapp", direcao="saida", canal="comercial", status=st))
        db.add(EnvioExterno(mensagem_id=m.id, meio="whatsapp", direcao="saida", canal="financeiro", status="erro"))
        db.add(EnvioExterno(mensagem_id=m.id, meio="whatsapp", direcao="entrada", canal="comercial", status="recebido"))  # entrada não conta
        db.add(EnvioExterno(mensagem_id=m.id, meio="email", direcao="saida", canal="comercial", status="enviado"))        # e-mail não conta
        db.flush()
        d = mod_chat.consumo_por_segmento(db, lid)
        by = {s["segmento"]: s for s in d["segmentos"]}
        assert len(d["segmentos"]) == 7
        assert by["comercial"]["enviado"] == 2 and by["comercial"]["pendente_config"] == 1
        assert by["comercial"]["total"] == 3                    # só saída WhatsApp
        assert by["financeiro"]["erro"] == 1 and by["financeiro"]["total"] == 1
        assert d["totais"]["enviado"] == 2 and d["totais"]["total"] == 4
        # tenancy: envio da loja 2 não entra no consumo da loja 1
        cr2 = db.query(app_db.Usuario).filter_by(login="dir_l2").first().id
        conv2 = mod_chat.criar_grupo(db, seed["loja2_id"], cr2, "C2", [], exige_dois=False)
        m2 = mod_chat.enviar_mensagem(db, conv2, None, "y", canal="comercial", _permitir_externo=True); db.flush()
        db.add(EnvioExterno(mensagem_id=m2.id, meio="whatsapp", direcao="saida", canal="comercial", status="enviado")); db.flush()
        assert mod_chat.consumo_por_segmento(db, lid)["totais"]["total"] == 4   # inalterado
    finally:
        db.close()


def test_consumo_endpoint_e_tenancy(http_client_factory, app_db, seed):
    ger = _login(http_client_factory, "dir_l1")
    st, bd = ger.get("/api/comunicacao/consumo")
    assert st == 200 and len(bd["consumo"]["segmentos"]) == 7 and "totais" in bd["consumo"]
    op = _login(http_client_factory, "cons_l1")
    assert op.get("/api/comunicacao/consumo")[0] == 403
