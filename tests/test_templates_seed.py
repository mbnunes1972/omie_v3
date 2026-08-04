# -*- coding: utf-8 -*-
"""Modelos INICIAIS das 9 mensagens obrigatórias (2026-08-04): loja virgem de templates ganha os
9 rascunhos prontos (conteúdo do TEMPLATES_INICIAIS); loja que já mexeu em templates — inclusive
só removeu — NÃO é tocada de novo."""
import mod_chat
from database import TemplateMensagem


def _limpar(db, loja_id):
    db.query(TemplateMensagem).filter_by(loja_id=loja_id).delete()
    db.flush()


def test_seed_cria_os_9_rascunhos(app_db, seed):
    db = app_db.get_session()
    try:
        _limpar(db, seed["loja1_id"])
        assert mod_chat.seed_templates_iniciais(db, seed["loja1_id"]) == 9
        db.commit()
        tpls = mod_chat.listar_templates(db, seed["loja1_id"])
        assert len(tpls) == 9
        assert {t["slot_obrigatorio"] for t in tpls} == set(range(1, 10))
        assert all(t["status"] == "rascunho" for t in tpls)
        assert all("{{1}}" in t["corpo"] for t in tpls)
        # segmento/categoria espelham o catálogo dos slots
        por_slot = {t["slot_obrigatorio"]: t for t in tpls}
        for s in mod_chat.SLOTS_OBRIGATORIOS:
            assert por_slot[s["num"]]["segmento"] == s["segmento"]
            assert por_slot[s["num"]]["categoria"] == s["categoria"]
        # RF-17a: reengajamentos assinados carregam a posição da variável do responsável
        assert por_slot[4]["assinatura_var"] == 2
    finally:
        db.close()


def test_seed_idempotente_e_respeita_remocao(app_db, seed):
    db = app_db.get_session()
    try:
        _limpar(db, seed["loja1_id"])
        mod_chat.seed_templates_iniciais(db, seed["loja1_id"])
        db.commit()
        assert mod_chat.seed_templates_iniciais(db, seed["loja1_id"]) == 0   # 2ª chamada: nada
        # loja removeu um modelo (soft-delete mantém a linha) → seed continua sem recriar
        t1 = db.query(TemplateMensagem).filter_by(loja_id=seed["loja1_id"],
                                                  slot_obrigatorio=1).first()
        mod_chat.remover_template(db, seed["loja1_id"], t1.id)
        db.commit()
        assert mod_chat.seed_templates_iniciais(db, seed["loja1_id"]) == 0
        assert len(mod_chat.listar_templates(db, seed["loja1_id"])) == 8
    finally:
        db.close()
