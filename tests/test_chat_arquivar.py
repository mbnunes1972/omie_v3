# -*- coding: utf-8 -*-
"""Arquivamento por usuário + filtro 'Pendentes' (revisão UX da F7/Chat Interno, 2026-07-31).

Conceitos do usuário: abas Pessoais/Grupos/Arquivadas iguais nos dois canais; PENDENTE é
mensagem recebida sem resposta (FILTRO, não estado); arquivar é ação reversível por usuário
(flag no ConversaParticipante — a coluna existia sem uso)."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _direct(db, app_db, loja_id, a_login, b_login):
    import mod_chat
    ua = db.query(app_db.Usuario).filter_by(login=a_login).first()
    ub = db.query(app_db.Usuario).filter_by(login=b_login).first()
    c = mod_chat.get_or_create_direct(db, loja_id, ua.id, ub.id)
    db.commit()
    return c, ua, ub


def test_arquivar_por_usuario_e_reversivel(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    conv, ua, ub = _direct(db, app_db, seed["loja1_id"], "dir_l1", "cons_l1")
    assert mod_chat.arquivar_conversa(db, conv, ua.id) is True
    db.commit()
    inbox_a = mod_chat.listar_inbox(db, seed["loja1_id"], ua.id)
    inbox_b = mod_chat.listar_inbox(db, seed["loja1_id"], ub.id)
    item_a = [x for x in inbox_a if x["id"] == conv.id][0]
    item_b = [x for x in inbox_b if x["id"] == conv.id][0]
    assert item_a["arquivada"] is True
    assert item_b["arquivada"] is False        # a flag é POR usuário — o outro não é afetado
    assert mod_chat.arquivar_conversa(db, conv, ua.id, arquivar=False) is False
    db.commit()
    inbox_a = mod_chat.listar_inbox(db, seed["loja1_id"], ua.id)
    assert [x for x in inbox_a if x["id"] == conv.id][0]["arquivada"] is False
    db.close()


def test_mural_nao_arquiva_e_nao_participante_erro(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    mural = mod_chat.get_or_create_mural(db, seed["loja1_id"]); db.commit()
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    with pytest.raises(ValueError, match="[Mm]ural"):
        mod_chat.arquivar_conversa(db, mural, u.id)
    conv, _ua, _ub = _direct(db, app_db, seed["loja1_id"], "dir_l1", "cons_l1")
    u2 = db.query(app_db.Usuario).filter_by(login="dir_l2").first()
    with pytest.raises(ValueError, match="participa"):
        mod_chat.arquivar_conversa(db, conv, u2.id)   # não-participante não arquiva
    db.close()


def test_pendente_e_cliente_sem_resposta_independente_do_viewer(app_db, seed):
    """pendente (revisão 2026-08-05): reflete o ATENDIMENTO — última mensagem SEM autor
    interno (veio de fora) —, não mais "não fui eu que mandei" por viewer. Mensagem entre
    dois usuários internos nunca é pendente (não tem cliente esperando); mensagem externa é
    pendente pros DOIS lados até alguém da loja responder."""
    import mod_chat
    db = app_db.get_session()
    conv, ua, ub = _direct(db, app_db, seed["loja1_id"], "dir_l1", "cons_l1")
    mod_chat.enviar_mensagem(db, conv, ua.id, "oi, tudo bem?"); db.commit()
    item_a = [x for x in mod_chat.listar_inbox(db, seed["loja1_id"], ua.id) if x["id"] == conv.id][0]
    item_b = [x for x in mod_chat.listar_inbox(db, seed["loja1_id"], ub.id) if x["id"] == conv.id][0]
    assert item_a["pendente"] is False and item_b["pendente"] is False
    # mensagem EXTERNA (autor_usuario_id NULL) → pendente pros dois lados, sem depender de quem olha
    mod_chat.enviar_mensagem(db, conv, None, "mensagem de fora", canal="comercial",
                             _permitir_externo=True); db.commit()
    item_a = [x for x in mod_chat.listar_inbox(db, seed["loja1_id"], ua.id) if x["id"] == conv.id][0]
    item_b = [x for x in mod_chat.listar_inbox(db, seed["loja1_id"], ub.id) if x["id"] == conv.id][0]
    assert item_a["pendente"] is True and item_b["pendente"] is True
    # qualquer um da loja responde → deixa de ser pendente pros dois
    mod_chat.enviar_mensagem(db, conv, ub.id, "tudo!"); db.commit()
    item_a = [x for x in mod_chat.listar_inbox(db, seed["loja1_id"], ua.id) if x["id"] == conv.id][0]
    item_b = [x for x in mod_chat.listar_inbox(db, seed["loja1_id"], ub.id) if x["id"] == conv.id][0]
    assert item_a["pendente"] is False and item_b["pendente"] is False
    db.close()


def test_endpoint_arquivar_tenancy(http_client_factory, app_db, seed):
    db = app_db.get_session()
    conv, _ua, _ub = _direct(db, app_db, seed["loja1_id"], "dir_l1", "cons_l1")
    cid = conv.id; db.close()
    c1 = _login(http_client_factory, "dir_l1")
    st, body = c1.post("/api/comunicacao/conversas/%d/arquivar" % cid, {"arquivar": True})
    assert st == 200 and body["ok"] and body["arquivada"] is True
    st, body = c1.post("/api/comunicacao/conversas/%d/arquivar" % cid, {"arquivar": False})
    assert st == 200 and body["arquivada"] is False
    c2 = _login(http_client_factory, "dir_l2")
    st, _body = c2.post("/api/comunicacao/conversas/%d/arquivar" % cid, {"arquivar": True})
    assert st == 404                                   # conversa de outra loja não existe p/ ele
    db.close()
