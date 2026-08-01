# -*- coding: utf-8 -*-
"""r3 da revisão UX (2026-07-31): segmento como SELETOR (manual vence derivado; triagem indica;
sem segmento a gerência trata) + "Adicionar Contato" (cadastro vira fonte de contatos, associado
ao projeto, com MOTIVO como evento inline)."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_segmento_manual_vence_derivado(app_db, seed):
    import mod_chat, mod_chat_externo as ext
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_Seg"); db.flush()
    m = mod_chat.enviar_mensagem(db, conv, None, "externa", canal="comercial", _permitir_externo=True)
    ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente", seed["cliente_l1_id"], "(12) 91111-0001")
    db.commit()
    seg, _j = mod_chat._atendimento_meta(db, conv)
    assert seg == "comercial"                       # derivado do tráfego
    mod_chat.definir_segmento(db, conv, "financeiro"); db.commit()
    seg, _j = mod_chat._atendimento_meta(db, conv)
    assert seg == "financeiro"                      # manual vence
    mod_chat.definir_segmento(db, conv, ""); db.commit()
    seg, _j = mod_chat._atendimento_meta(db, conv)
    assert seg == "comercial"                       # limpar volta ao derivado
    with pytest.raises(ValueError):
        mod_chat.definir_segmento(db, conv, "marketing")   # fora dos 7
    db.close()


def test_triagem_aplica_segmento_indicado_ou_escolhido(app_db, seed):
    import mod_chat_externo as ext
    from database import Conversa
    db = app_db.get_session()
    r = ext.processar_entrada(db, "whatsapp", remetente="(11) 92222-0001",
                              texto="quero falar do boleto", id_externo="wamid.SEG1")
    db.commit()
    ent = db.get(app_db.TriagemEntrada, r["triagem_id"])
    ent.segmento_sugerido = "financeiro"; db.commit()   # a triagem automática INDICOU
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    conv = ext.triagem_resolver_criar(db, ent, u.id, "Cliente do Boleto")
    db.commit()
    assert db.get(Conversa, conv.id).segmento == "financeiro"
    # escolhido na resolução VENCE o indicado
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(11) 92222-0002",
                               texto="segunda entrada", id_externo="wamid.SEG2")
    db.commit()
    ent2 = db.get(app_db.TriagemEntrada, r2["triagem_id"])
    ent2.segmento_sugerido = "comercial"; db.commit()
    conv2 = ext.triagem_resolver_criar(db, ent2, u.id, "Outro Lead", segmento="sac")
    db.commit()
    assert db.get(Conversa, conv2.id).segmento == "sac"
    db.close()


def test_adicionar_contato_com_projeto_e_motivo(app_db, seed):
    import mod_chat, mod_chat_externo as ext
    from database import ConversaMensagem
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    conv, cli = mod_chat.adicionar_contato(
        db, seed["loja1_id"], u.id, "Síndico do Prédio", telefone="(12) 93333-0001",
        motivo="Autorização de entrega na portaria", projeto_nome="Proj_L1",
        segmento="logistica")
    db.commit()
    assert conv.projeto_nome == "Proj_L1"           # associado ao projeto
    assert cli.loja_id == seed["loja1_id"]          # virou fonte de contatos (Cliente)
    assert "933330001" in (cli.whatsapp or "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    ev = (db.query(ConversaMensagem)
            .filter_by(conversa_id=conv.id, evento="contato_adicionado").first())
    assert ev is not None and "Autorização de entrega" in ev.corpo   # motivo registrado
    assert conv.segmento == "logistica"
    ext_p = db.query(app_db.ConversaParticipanteExterno).filter_by(conversa_id=conv.id).first()
    assert ext_p is not None and ext_p.nome == "Síndico do Prédio"
    # a resposta do número roteia para a conversa do projeto (fonte de contatos ativa)
    m = mod_chat.enviar_mensagem(db, conv, None, "saida", canal="logistica", _permitir_externo=True)
    ext.registrar_envio(db, m, "whatsapp", "logistica", "avulso", ext_p.id, "(12) 93333-0001")
    db.commit()
    r = ext.processar_entrada(db, "whatsapp", remetente="(12) 93333-0001",
                              texto="pode entregar", id_externo="wamid.CT1")
    db.commit()
    assert r["status"] == "roteado" and r["conversa_id"] == conv.id
    db.close()


def test_adicionar_contato_tipos_de_cadastro(app_db, seed):
    """r3 (revisão): o formulário define o destino — cliente | parceiro | fornecedor |
    convidado (convidado NÃO entra em cadastro nenhum, só participa da conversa)."""
    import mod_chat
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    # parceiro → Parceiro + vínculo ParceiroLoja com a loja
    conv, reg = mod_chat.adicionar_contato(
        db, seed["loja1_id"], u.id, "Arquiteta Ana", telefone="(12) 96666-1001",
        motivo="Parceria de indicação", tipo="parceiro")
    db.commit()
    assert isinstance(reg, app_db.Parceiro)
    vinc = db.query(app_db.ParceiroLoja).filter_by(parceiro_id=reg.id,
                                                   loja_id=seed["loja1_id"]).first()
    assert vinc is not None
    # fornecedor → Fornecedor (telefone no campo telefone — não há whatsapp no model)
    _c2, reg2 = mod_chat.adicionar_contato(
        db, seed["loja1_id"], u.id, "Transportadora XYZ", telefone="(12) 96666-1002",
        motivo="Cotação de frete", tipo="fornecedor")
    db.commit()
    assert isinstance(reg2, app_db.Fornecedor) and reg2.telefone
    # convidado → SEM cadastro; só o participante externo na conversa
    antes = db.query(app_db.Cliente).count()
    conv3, reg3 = mod_chat.adicionar_contato(
        db, seed["loja1_id"], u.id, "Esposa do Cliente", telefone="(12) 96666-1003",
        motivo="Acompanhar a obra", tipo="convidado")
    db.commit()
    assert reg3 is None
    assert db.query(app_db.Cliente).count() == antes          # cadastro intocado
    ext_p = db.query(app_db.ConversaParticipanteExterno).filter_by(conversa_id=conv3.id).first()
    assert ext_p is not None and ext_p.nome == "Esposa do Cliente"
    # o evento nomeia o tipo
    from database import ConversaMensagem
    ev = (db.query(ConversaMensagem)
            .filter_by(conversa_id=conv.id, evento="contato_adicionado").first())
    assert "(Parceiro)" in (ev.corpo or "")
    with pytest.raises(ValueError, match="[Tt]ipo"):
        mod_chat.adicionar_contato(db, seed["loja1_id"], u.id, "X",
                                   telefone="(12) 96666-1004", motivo="m", tipo="inimigo")
    db.rollback()
    db.close()


def test_adicionar_contato_sem_projeto_vira_lead(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    conv, cli = mod_chat.adicionar_contato(
        db, seed["loja1_id"], u.id, "Lead da Feira", telefone="(12) 94444-0001",
        motivo="Conheceu o estande na feira de decoração")
    db.commit()
    assert conv.tipo == "grupo" and "Lead da Feira" in (conv.titulo or "")
    with pytest.raises(ValueError, match="motivo"):
        mod_chat.adicionar_contato(db, seed["loja1_id"], u.id, "Sem Motivo",
                                   telefone="(12) 94444-0002", motivo="")
    db.rollback()
    with pytest.raises(ValueError, match="WhatsApp"):
        mod_chat.adicionar_contato(db, seed["loja1_id"], u.id, "Sem Contato", motivo="x")
    db.rollback()
    db.close()


def test_endpoints_segmento_e_contato(http_client_factory, app_db, seed):
    import mod_chat
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1"); db.commit()
    cid = conv.id; db.close()
    c1 = _login(http_client_factory, "dir_l1")
    st, body = c1.post("/api/comunicacao/conversas/%d/segmento" % cid, {"segmento": "sac"})
    assert st == 200 and body["ok"] and body["segmento"] == "sac"
    # operador não define segmento (gerência trata)
    cop = _login(http_client_factory, "cons_l1")
    st, _b = cop.post("/api/comunicacao/conversas/%d/segmento" % cid, {"segmento": "comercial"})
    assert st == 403
    # Adicionar Contato via endpoint
    st, body = c1.post("/api/comunicacao/contatos",
                       {"nome": "Contato Endpoint", "telefone": "(12) 95555-0009",
                        "motivo": "Indicação de arquiteto", "projeto_nome": "Proj_L1",
                        "segmento": "comercial"})
    assert st == 201 and body["ok"] and body["conversa_id"] == cid
    st, body = c1.post("/api/comunicacao/contatos",
                       {"nome": "X", "telefone": "(12) 95555-0010", "motivo": ""})
    assert st == 400                                   # motivo é obrigatório
    db.close()
