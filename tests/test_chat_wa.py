# -*- coding: utf-8 -*-
"""Orizon Chat — Fatia 6: ponte WhatsApp do funcionário (presença, identidade por celular,
janela 24h, notificação config-gated e roteamento de entrada). Spec 2026-07-27 §3/§5.

Sem credencial Meta no ambiente de teste → os envios nascem 'pendente_config' (a rede não é
tocada). Aqui testamos a LÓGICA (presença/resolução/janela/registro/entrada)."""
from datetime import datetime, timedelta
import mod_chat
import mod_chat_externo as wa


def _u(app_db, login):
    db = app_db.get_session()
    try:
        return db.query(app_db.Usuario).filter_by(login=login).first().id
    finally:
        db.close()


def test_presenca_online_e_expira(app_db, seed):
    db = app_db.get_session()
    uid = _u(app_db, "dir_l1")
    wa.registrar_presenca(db, uid); db.commit()
    assert wa.esta_online(db, uid)
    p = db.get(app_db.UsuarioPresenca, uid)
    p.visto_em = datetime.utcnow() - timedelta(minutes=30); db.commit()
    assert not wa.esta_online(db, uid)
    db.close()


def test_usuario_por_telefone(app_db, seed):
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    u.whatsapp = "(12) 98888-7766"; db.commit()
    assert wa.usuario_por_telefone(db, "55 12 98888-7766").id == u.id   # tolera DDI/DDD/máscara
    assert wa.usuario_por_telefone(db, "123") is None                   # curto demais
    db.close()


def test_janela_24h(app_db, seed):
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    u.whatsapp = "11991112233"; db.commit()
    assert not wa.dentro_da_janela_24h(db, u.id)
    conv = mod_chat.get_or_create_mural(db, u.loja_id); db.flush()
    msg = mod_chat.enviar_mensagem(db, conv, u.id, "oi")
    db.add(app_db.EnvioExterno(mensagem_id=msg.id, meio="whatsapp", direcao="entrada",
                               destino="+55 11 99111-2233", status="recebido")); db.commit()
    assert wa.dentro_da_janela_24h(db, u.id)
    db.close()


def test_deve_notificar_preferencia_e_presenca(app_db, seed):
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    u.notificar_whatsapp = "nunca"; db.commit()
    assert not wa.deve_notificar_usuario(db, u)
    u.notificar_whatsapp = "sempre"; db.commit()
    assert wa.deve_notificar_usuario(db, u)
    u.notificar_whatsapp = "quando_offline"; db.commit()
    wa.registrar_presenca(db, u.id); db.commit()
    assert not wa.deve_notificar_usuario(db, u)   # online → não incomoda
    db.close()


def test_notificar_conversa_registra_pendente(app_db, seed):
    db = app_db.get_session()
    a = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    b = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    b.whatsapp = "11970001122"; b.notificar_whatsapp = "sempre"; db.commit()
    conv = mod_chat.get_or_create_direct(db, a.loja_id, a.id, b.id); db.flush()
    msg = mod_chat.enviar_mensagem(db, conv, a.id, "ping"); db.flush()
    ids = wa.notificar_conversa(db, conv, msg, a.id); db.commit()
    assert ids                                    # notificou o destinatário
    env = (db.query(app_db.EnvioExterno)
             .filter_by(destinatario_tipo="usuario", destinatario_id=b.id).first())
    assert env is not None and env.status == "pendente_config"   # sem credencial Meta
    db.close()


def test_entrada_do_funcionario_roteia_como_ele(app_db, seed):
    db = app_db.get_session()
    a = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    b = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    b.whatsapp = "11960002233"; db.commit()
    conv = mod_chat.get_or_create_direct(db, a.loja_id, a.id, b.id); db.flush()
    msg = mod_chat.enviar_mensagem(db, conv, a.id, "te chamei"); db.flush()
    wa.notificar_usuario(db, conv, msg, b, autor_nome="Diretor"); db.commit()  # cria a saída p/ b
    res = wa.processar_entrada_usuario(db, "55 11 96000-2233", "respondo pelo zap"); db.commit()
    assert res and res["status"] == "roteado" and res["conversa_id"] == conv.id
    msgs = mod_chat.listar_mensagens(db, conv.id)
    assert msgs[-1]["corpo"] == "respondo pelo zap"
    assert msgs[-1]["autor_usuario_id"] == b.id      # atribuída ao funcionário
    db.close()


def test_entrada_de_numero_desconhecido_none(app_db, seed):
    db = app_db.get_session()
    assert wa.processar_entrada_usuario(db, "55 00 00000-0000", "quem sou eu") is None
    db.close()
