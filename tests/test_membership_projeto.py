# -*- coding: utf-8 -*-
"""Conversa do Projeto — membership derivada + override manual (spec
conversa-projeto-no-orizon-chat, 2026-07-27). A conversa `tipo=projeto` sincroniza seus
participantes com a equipe derivada; adição/remoção manual do gerente PREVALECEM."""
import mod_chat
from database import Conversa, ConversaParticipante


def _users(app_db, *logins):
    db = app_db.get_session()
    try:
        return [db.query(app_db.Usuario).filter_by(login=l).first().id for l in logins]
    finally:
        db.close()


def _conv_proj(app_db, seed, nome):
    db = app_db.get_session()
    try:
        c = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], nome)
        db.commit(); return c.id
    finally:
        db.close()


def _sync(app_db, conv_id, membros):
    db = app_db.get_session()
    try:
        res = mod_chat.sincronizar_participantes_projeto(db, db.get(Conversa, conv_id), membros)
        db.commit(); return res
    finally:
        db.close()


def _parts(app_db, conv_id):
    db = app_db.get_session()
    try:
        return {(p.usuario_id, p.origem, p.removido) for p in
                db.query(ConversaParticipante).filter_by(conversa_id=conv_id).all()}
    finally:
        db.close()


def test_sync_adiciona_derivados_como_auto(app_db, seed):
    a, b = _users(app_db, "dir_l1", "cons_l1")
    cid = _conv_proj(app_db, seed, "MP_add")
    assert set(_sync(app_db, cid, [a, b])) == {a, b}
    assert _parts(app_db, cid) == {(a, "auto", 0), (b, "auto", 0)}


def test_sync_remove_auto_que_saiu_do_time(app_db, seed):
    a, b = _users(app_db, "dir_l1", "cons_l1")
    cid = _conv_proj(app_db, seed, "MP_rem")
    _sync(app_db, cid, [a, b])
    assert set(_sync(app_db, cid, [a])) == {a}
    assert _parts(app_db, cid) == {(a, "auto", 0)}


def test_remocao_manual_prevalece(app_db, seed):
    (a,) = _users(app_db, "dir_l1")
    cid = _conv_proj(app_db, seed, "MP_manrem")
    _sync(app_db, cid, [a])
    db = app_db.get_session()                          # simula remoção manual (tombstone)
    try:
        p = db.query(ConversaParticipante).filter_by(conversa_id=cid, usuario_id=a).first()
        p.removido = 1; db.commit()
    finally:
        db.close()
    _sync(app_db, cid, [a])                             # a segue derivado, mas removido manual
    assert _parts(app_db, cid) == {(a, "auto", 1)}      # NÃO readiciona
    db = app_db.get_session()
    try:
        assert mod_chat.eh_participante(db, cid, a) is False
    finally:
        db.close()


def test_adicao_manual_fica(app_db, seed):
    a, b = _users(app_db, "dir_l1", "cons_l1")
    cid = _conv_proj(app_db, seed, "MP_manadd")
    db = app_db.get_session()                          # b entra à mão (não é da equipe)
    try:
        db.add(ConversaParticipante(conversa_id=cid, usuario_id=b, papel="membro",
                                    origem="manual", removido=0)); db.commit()
    finally:
        db.close()
    _sync(app_db, cid, [a])                             # só a derivado
    assert _parts(app_db, cid) == {(a, "auto", 0), (b, "manual", 0)}


def test_inbox_inclui_conversa_projeto(app_db, seed):
    (a,) = _users(app_db, "dir_l1")
    cid = _conv_proj(app_db, seed, "MP_inbox")
    _sync(app_db, cid, [a])
    db = app_db.get_session()
    try:
        itens = mod_chat.listar_inbox(db, seed["loja1_id"], a)
    finally:
        db.close()
    proj = [x for x in itens if x["id"] == cid]
    assert proj and proj[0]["tipo"] == "projeto" and proj[0]["titulo"].startswith("📁")
