# -*- coding: utf-8 -*-
"""Equipe do Projeto — FONTE ÚNICA por função (spec conversa-projeto-no-orizon-chat, 2026-07-27).

A origem dos integrantes é a FUNÇÃO responsável de cada etapa (CicloEtapa.funcao_responsavel_id).
O funcionário é derivado: 1 candidato → auto; >1 → lacuna; 0 → sem responsável. O criador sempre
entra. `responsavel_funcionario_id` já definido é respeitado."""
import mod_equipe


def _proj(app_db, seed, nome, criador_login=None):
    db = app_db.get_session()
    try:
        crid = (db.query(app_db.Usuario).filter_by(login=criador_login).first().id
                if criador_login else None)
        db.add(app_db.Projeto(nome_safe=nome, loja_id=seed["loja1_id"],
                              status="fechado", criado_por_id=crid))
        db.commit()
    finally:
        db.close()
    return nome


def _funcao(app_db, loja_id, nome):
    db = app_db.get_session()
    try:
        f = app_db.Funcao(nome=nome, loja_id=loja_id); db.add(f); db.commit(); return f.id
    finally:
        db.close()


def _func(app_db, loja_id, funcao_id, nome, usuario_id=None):
    db = app_db.get_session()
    try:
        x = app_db.Funcionario(nome=nome, loja_id=loja_id, funcao_id=funcao_id,
                               status="ativo", usuario_id=usuario_id)
        db.add(x); db.commit(); return x.id
    finally:
        db.close()


def _etapa(app_db, nome_safe, codigo, funcao_id, resp_func=None):
    db = app_db.get_session()
    try:
        db.add(app_db.CicloEtapa(projeto_nome=nome_safe, etapa_codigo=codigo,
                                 funcao_responsavel_id=funcao_id,
                                 responsavel_funcionario_id=resp_func))
        db.commit()
    finally:
        db.close()


def _resolver(app_db, nome_safe, loja_id):
    db = app_db.get_session()
    try:
        return mod_equipe.equipe_do_projeto(db, nome_safe, loja_id)
    finally:
        db.close()


def test_auto_um_candidato(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqAuto")
    fid = _funcao(app_db, lid, "Medidor QA1")
    func = _func(app_db, lid, fid, "Med Um")
    _etapa(app_db, p, "10", fid)
    r = _resolver(app_db, p, lid)
    assert r["lacunas"] == []
    assert any(m["funcionario_id"] == func and m["via"] == "auto" for m in r["membros"])


def test_lacuna_mais_de_um(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqLac")
    fid = _funcao(app_db, lid, "Montador QA")
    _func(app_db, lid, fid, "M1"); _func(app_db, lid, fid, "M2")
    _etapa(app_db, p, "17", fid)
    r = _resolver(app_db, p, lid)
    assert r["membros"] == []                                  # nenhum auto
    assert len(r["lacunas"]) == 1 and r["lacunas"][0]["etapa_codigo"] == "17"
    assert len(r["lacunas"][0]["candidatos"]) == 2


def test_definido_respeita_e_sem_lacuna(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqDef")
    fid = _funcao(app_db, lid, "Montador QA2")
    a = _func(app_db, lid, fid, "A"); _func(app_db, lid, fid, "B")     # 2 candidatos
    _etapa(app_db, p, "17", fid, resp_func=a)                          # mas já definido
    r = _resolver(app_db, p, lid)
    assert r["lacunas"] == []
    assert any(m["funcionario_id"] == a and m["via"] == "definido" for m in r["membros"])


def test_criador_sempre_entra(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqCri", criador_login="dir_l1")
    db = app_db.get_session()
    crid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id; db.close()
    r = _resolver(app_db, p, lid)
    assert r["criador_usuario_id"] == crid and crid in r["membros_usuarios"]


def test_zero_candidatos_nem_membro_nem_lacuna(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqZero")
    fid = _funcao(app_db, lid, "FuncVazia QA")                 # sem funcionários
    _etapa(app_db, p, "13", fid)
    r = _resolver(app_db, p, lid)
    assert r["membros"] == [] and r["lacunas"] == []


def test_funcionario_mapeia_para_usuario(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqUsr")
    db = app_db.get_session()
    uid = db.query(app_db.Usuario).filter_by(login="cons_l1").first().id; db.close()
    fid = _funcao(app_db, lid, "Conferente QA")
    _func(app_db, lid, fid, "Conf", usuario_id=uid)
    _etapa(app_db, p, "12", fid)
    r = _resolver(app_db, p, lid)
    assert uid in r["membros_usuarios"]
