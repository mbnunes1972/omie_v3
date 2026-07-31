# -*- coding: utf-8 -*-
"""Fila de triagem persistente (spec _geral/2026-07-31-triagem-pipeline-entrada-design.md).

Regra de ouro: mensagem nenhuma é descartada em silêncio — o que a automação não roteia
cai numa TriagemEntrada `pendente`, idempotente por `id_externo` (a Meta reentrega 5-6x).
Cobre os casos obrigatórios da seção 4 da spec."""
import json

import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


@pytest.fixture(scope="module", autouse=True)
def numero_da_loja1(app_db, seed):
    """Fiel à produção: a loja operante tem NumeroConectado configurado — é ele que ancora a
    loja das entradas de número DESCONHECIDO (fallback do _loja_da_entrada)."""
    db = app_db.get_session()
    db.add(app_db.NumeroConectado(loja_id=seed["loja1_id"], numero="+55 12 90000-0000"))
    db.commit(); db.close()


def _conversa_com_saida(db, app_db, loja_id, projeto, cliente_id, numero):
    """Conversa de projeto com um EnvioExterno de SAÍDA para `numero` (habilita o roteamento)."""
    import mod_chat, mod_chat_externo as ext
    conv = mod_chat.get_or_create_conversa_projeto(db, loja_id, projeto); db.flush()
    m = mod_chat.enviar_mensagem(db, conv, None, "saida", canal="comercial", _permitir_externo=True)
    ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente", cliente_id, numero)
    db.commit()
    return conv


# ── 1. primeiro contato nunca visto → fila persistida ────────────────────────

def test_primeiro_contato_persiste_na_fila(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    res = ext.processar_entrada(db, "whatsapp", remetente="(11) 97777-0001",
                                texto="olá, quero um orçamento", id_externo="wamid.NOVO1")
    db.commit()
    assert res["status"] == "triagem" and res.get("triagem_id")
    ent = db.get(app_db.TriagemEntrada, res["triagem_id"])
    assert ent is not None and ent.status == "pendente"
    assert ent.texto == "olá, quero um orçamento"
    assert ent.id_externo == "wamid.NOVO1"
    assert ent.loja_id == seed["loja1_id"]      # fallback: primeira loja
    db.close()


# ── 2. reentrega Meta do mesmo id_externo → não duplica (fila E mensagem) ────

def test_reentrega_nao_duplica_fila(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    r1 = ext.processar_entrada(db, "whatsapp", remetente="(11) 97777-0002",
                               texto="oi", id_externo="wamid.DUP")
    db.commit()
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(11) 97777-0002",
                               texto="oi", id_externo="wamid.DUP")
    db.commit()
    assert r1["status"] == r2["status"] == "triagem"
    assert r1["triagem_id"] == r2["triagem_id"]
    n = db.query(app_db.TriagemEntrada).filter_by(id_externo="wamid.DUP").count()
    assert n == 1
    db.close()


def test_reentrega_nao_duplica_mensagem_roteada(app_db, seed):
    import mod_chat_externo as ext
    from database import ConversaMensagem
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                               seed["cliente_l1_id"], "(12) 90000-1111")
    r1 = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-1111",
                               texto="resposta", id_externo="wamid.RESP")
    db.commit()
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-1111",
                               texto="resposta", id_externo="wamid.RESP")
    db.commit()
    assert r1["status"] == r2["status"] == "roteado"
    assert r1["conversa_id"] == r2["conversa_id"] == conv.id
    n = (db.query(ConversaMensagem)
           .filter_by(conversa_id=conv.id, corpo="resposta").count())
    assert n == 1                                   # a reentrega não duplicou a mensagem
    db.close()


# ── 3. ambíguo (2+ conversas) → fila com os candidatos preservados ───────────

def test_ambiguo_preserva_candidatos(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    c1 = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                             seed["cliente_l1_id"], "(12) 90000-3333")
    c2 = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_Ambiguo",
                             seed["cliente_l1_id"], "(12) 90000-3333")
    res = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-3333",
                                texto="sobre meu projeto", id_externo="wamid.AMB")
    db.commit()
    assert res["status"] == "triagem"
    ent = db.get(app_db.TriagemEntrada, res["triagem_id"])
    cand = set(json.loads(ent.candidatos_json))
    assert cand == {c1.id, c2.id}                   # a lista que o código calculou não se perde
    db.close()


# ── 4. reply citando envio antigo → roteia determinístico (não cai na fila) ──

def test_reply_citado_roteia_mesmo_com_ambiguidade(app_db, seed):
    import mod_chat, mod_chat_externo as ext
    db = app_db.get_session()
    c1 = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                             seed["cliente_l1_id"], "(12) 90000-4444")
    _c2 = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_Outro",
                              seed["cliente_l1_id"], "(12) 90000-4444")
    env = (db.query(app_db.EnvioExterno)
             .join(app_db.ConversaMensagem,
                   app_db.EnvioExterno.mensagem_id == app_db.ConversaMensagem.id)
             .filter(app_db.ConversaMensagem.conversa_id == c1.id).first())
    env.id_externo = "wamid.ANTIGA"; db.commit()
    res = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-4444",
                                texto="sobre aquilo", id_externo="wamid.R1",
                                id_externo_ref="wamid.ANTIGA")
    db.commit()
    assert res["status"] == "roteado" and res["conversa_id"] == c1.id
    db.close()


# ── 5. fora da janela de 24h ainda roteia (janela restringe RESPOSTA, não entrada) ─

def test_fora_da_janela_ainda_roteia(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                               seed["cliente_l1_id"], "(12) 90000-5555")
    res = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-5555",
                                texto="voltei depois de dias", id_externo="wamid.TARDE")
    db.commit()
    assert res["status"] == "roteado" and res["conversa_id"] == conv.id
    db.close()


# ── 6. funcionário que também é cliente: a ponte do funcionário VENCE ────────

def test_funcionario_vence_fluxo_de_cliente(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    u.whatsapp = "(12) 96666-0001"
    cli = db.get(app_db.Cliente, seed["cliente_l1_id"])
    cli.whatsapp = "(12) 96666-0001"                # mesmo número nos dois cadastros
    db.commit()
    res = ext.processar_entrada_usuario(db, "(12) 96666-0001", "oi da ponte")
    assert res is not None                          # ponte reconhece → cliente nem é tentado
    db.close()


# ── 7. projeto concluído não reabre sozinho → cai na fila com candidato ──────

def test_projeto_concluido_cai_na_fila(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                               seed["cliente_l1_id"], "(12) 90000-7777")
    proj = db.query(app_db.Projeto).filter_by(nome_safe="Proj_L1").first()
    proj.status = "concluido"; db.commit()
    res = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-7777",
                                texto="tenho um problema no móvel", id_externo="wamid.POS")
    db.commit()
    assert res["status"] == "triagem"               # decisão humana, não reabertura silenciosa
    ent = db.get(app_db.TriagemEntrada, res["triagem_id"])
    assert conv.id in set(json.loads(ent.candidatos_json))
    proj.status = "quente"; db.commit()             # seed é module-scoped — restaura p/ os demais
    db.close()


# ── resolução humana: vincular · criar · descartar ───────────────────────────

def test_resolver_vincular_posta_mensagem_e_evento(app_db, seed):
    import mod_chat_externo as ext
    from database import ConversaMensagem
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                               seed["cliente_l1_id"], "(12) 90000-8888")
    _c2 = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_Dois",
                              seed["cliente_l1_id"], "(12) 90000-8888")
    res = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-8888",
                                texto="mensagem ambígua", id_externo="wamid.VINC")
    db.commit()
    ent = db.get(app_db.TriagemEntrada, res["triagem_id"])
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    ext.triagem_resolver_vincular(db, ent, conv, u.id)
    db.commit()
    assert ent.status == "resolvido" and ent.conversa_id == conv.id
    assert ent.resolvido_por_id == u.id and ent.resolvido_em is not None
    corpos = [m.corpo for m in db.query(ConversaMensagem)
              .filter_by(conversa_id=conv.id).order_by(ConversaMensagem.id).all()]
    assert "mensagem ambígua" in corpos             # o texto original entrou na conversa
    ev = (db.query(ConversaMensagem)
            .filter(ConversaMensagem.conversa_id == conv.id,
                    ConversaMensagem.evento.isnot(None)).first())
    assert ev is not None and ev.evento == "triagem_vinculo"
    assert "Diretor L1" in (ev.corpo or "")
    # a idempotência acompanha: o wamid agora está no EnvioExterno da conversa
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-8888",
                               texto="mensagem ambígua", id_externo="wamid.VINC")
    assert r2["status"] == "roteado" and r2["conversa_id"] == conv.id
    db.close()


def test_resolver_criar_lead_novo(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    res = ext.processar_entrada(db, "whatsapp", remetente="(11) 95555-0001",
                                texto="quero móveis planejados", id_externo="wamid.LEAD")
    db.commit()
    ent = db.get(app_db.TriagemEntrada, res["triagem_id"])
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    conv = ext.triagem_resolver_criar(db, ent, u.id, "Lead Novo da Silva")
    db.commit()
    assert ent.status == "resolvido" and ent.conversa_id == conv.id
    cli = db.query(app_db.Cliente).filter_by(nome="Lead Novo da Silva").first()
    assert cli is not None and cli.loja_id == seed["loja1_id"]
    assert "955550001" in (cli.whatsapp or "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    ext_part = (db.query(app_db.ConversaParticipanteExterno)
                  .filter_by(conversa_id=conv.id).first())
    assert ext_part is not None                     # o contato espelha por WhatsApp
    # a próxima mensagem do número roteia sozinha para a conversa nova
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(11) 95555-0001",
                               texto="e o prazo?", id_externo="wamid.LEAD2")
    db.commit()
    assert r2["status"] == "roteado" and r2["conversa_id"] == conv.id
    db.close()


def test_descartar_registra_sem_apagar(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    res = ext.processar_entrada(db, "whatsapp", remetente="(11) 94444-0001",
                                texto="spam", id_externo="wamid.SPAM")
    db.commit()
    ent = db.get(app_db.TriagemEntrada, res["triagem_id"])
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    ext.triagem_descartar(db, ent, u.id)
    db.commit()
    assert ent.status == "descartado" and ent.resolvido_por_id == u.id
    assert db.get(app_db.TriagemEntrada, ent.id) is not None   # registro fica (não é delete)
    db.close()


# ── 8. endpoints + tenancy: a fila é da loja (404/403 cross-loja) ────────────

def test_fila_endpoint_e_tenancy(http_client_factory, app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    res = ext.processar_entrada(db, "whatsapp", remetente="(11) 93333-0001",
                                texto="para a loja 1", id_externo="wamid.TEN")
    db.commit(); tid = res["triagem_id"]; db.close()

    c1 = _login(http_client_factory, "dir_l1")
    st, body = c1.get("/api/comunicacao/triagem/fila")
    assert st == 200 and body["ok"]
    assert any(e["id"] == tid for e in body["fila"])

    c2 = _login(http_client_factory, "dir_l2")
    st, body = c2.get("/api/comunicacao/triagem/fila")
    assert st == 200 and body["ok"]
    assert not any(e["id"] == tid for e in body["fila"])   # loja 2 não vê a fila da loja 1

    st, body = c2.post("/api/comunicacao/triagem/fila/%d/resolver" % tid,
                       {"acao": "descartar"})
    assert st in (403, 404)                                # nem resolve cross-loja

    st, body = c1.post("/api/comunicacao/triagem/fila/%d/resolver" % tid,
                       {"acao": "descartar"})
    assert st == 200 and body["ok"]
    db = app_db.get_session()
    assert db.get(app_db.TriagemEntrada, tid).status == "descartado"
    db.close()
