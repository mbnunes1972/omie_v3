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


# ── terceiros na equipe (participante externo) ─────────────────────────────────

def _terceiro(app_db, loja_id, funcao_id, nome):
    db = app_db.get_session()
    try:
        t = app_db.Terceiro(nome=nome, loja_id=loja_id, funcao_id=funcao_id)
        db.add(t); db.commit(); return t.id
    finally:
        db.close()


def test_terceiro_resolvido_como_externo(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqTer")
    fid = _funcao(app_db, lid, "Montador QA3")
    tid = _terceiro(app_db, lid, fid, "Terça Montador")       # 1 candidato terceiro
    _etapa(app_db, p, "17", fid)
    r = _resolver(app_db, p, lid)
    assert r["membros"] == [] and r["lacunas"] == []          # auto, sem lacuna, sem funcionário
    assert any(e["terceiro_id"] == tid and e["tipo"] == "terceiro" for e in r["externos"])


def test_lacuna_conta_funcionario_e_terceiro(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqMix")
    fid = _funcao(app_db, lid, "Medidor QA2")
    _func(app_db, lid, fid, "Med Func"); _terceiro(app_db, lid, fid, "Med Terça")
    _etapa(app_db, p, "10", fid)
    r = _resolver(app_db, p, lid)
    assert len(r["lacunas"]) == 1
    assert {c["tipo"] for c in r["lacunas"][0]["candidatos"]} == {"funcionario", "terceiro"}


# ── gate de execução (bloqueador invertido) ────────────────────────────────────

def _gate(app_db, nome_safe, codigo, loja_id):
    db = app_db.get_session()
    try:
        et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
        return mod_equipe.etapa_executavel(db, loja_id, et)
    finally:
        db.close()


def test_gate_execucao_por_etapa(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqGate")
    f1 = _funcao(app_db, lid, "Medidor Gate1"); _func(app_db, lid, f1, "Único")
    _etapa(app_db, p, "10", f1)                               # 1 candidato → executável
    assert _gate(app_db, p, "10", lid) is True
    f2 = _funcao(app_db, lid, "Montador Gate2")
    a = _func(app_db, lid, f2, "A"); _terceiro(app_db, lid, f2, "B")
    _etapa(app_db, p, "17", f2)                               # 2 candidatos (lacuna) → travado
    assert _gate(app_db, p, "17", lid) is False
    f3 = _funcao(app_db, lid, "Vazia Gate3")
    _etapa(app_db, p, "18", f3)                               # 0 candidatos → travado
    assert _gate(app_db, p, "18", lid) is False
    _etapa(app_db, p, "19", f2, resp_func=a)                  # definido (apesar de vários) → executável
    assert _gate(app_db, p, "19", lid) is True


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_gate_bloqueia_execucao_no_endpoint(http_client_factory, app_db, seed):
    lid = seed["loja1_id"]
    fid = _funcao(app_db, lid, "Logistica Gate EP")
    _func(app_db, lid, fid, "L1"); _func(app_db, lid, fid, "L2")      # 2 candidatos → lacuna
    _etapa(app_db, "Proj_L1", "13", fid)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post_multipart("/api/projetos/Proj_L1/ciclo/13/pedido-xml",
                             files={"arquivo": ("p.xml", b"<xml/>")})
    assert st == 409 and isinstance(b, dict) and "responsável" in b.get("erro", "")


def test_montar_equipe_persiste_autos_e_apura_lacunas(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqFech")
    f1 = _funcao(app_db, lid, "Medidor Fech1"); u1 = _func(app_db, lid, f1, "Único Fech")
    _etapa(app_db, p, "10", f1)                             # 1 candidato → auto
    f2 = _funcao(app_db, lid, "Logistica Fech2")
    _func(app_db, lid, f2, "A"); _func(app_db, lid, f2, "B")
    _etapa(app_db, p, "13", f2)                             # 2 candidatos → lacuna
    db = app_db.get_session()
    try:
        res = mod_equipe.montar_equipe_no_fechamento(db, p, lid); db.commit()
    finally:
        db.close()
    assert any(d["etapa_codigo"] == "10" and d["tipo"] == "funcionario" and d["id"] == u1
               for d in res["definidos"])
    assert any(l["etapa_codigo"] == "13" for l in res["lacunas"])
    db = app_db.get_session()
    try:
        et10 = db.query(app_db.CicloEtapa).filter_by(projeto_nome=p, etapa_codigo="10").first()
        et13 = db.query(app_db.CicloEtapa).filter_by(projeto_nome=p, etapa_codigo="13").first()
        assert et10.responsavel_funcionario_id == u1        # auto persistido
        assert et13.responsavel_funcionario_id is None      # lacuna não persistida
    finally:
        db.close()


def test_terceiro_definido_e_auto_persistido(app_db, seed):
    lid = seed["loja1_id"]; p = _proj(app_db, seed, "EqTerFech")
    # etapa com 1 candidato TERCEIRO → auto (persiste em responsavel_terceiro_id)
    f1 = _funcao(app_db, lid, "Montador TerFech")
    tid = _terceiro(app_db, lid, f1, "Terça Única")
    _etapa(app_db, p, "13", f1)
    db = app_db.get_session()
    try:
        res = mod_equipe.montar_equipe_no_fechamento(db, p, lid); db.commit()
    finally:
        db.close()
    assert any(d["tipo"] == "terceiro" and d["id"] == tid for d in res["definidos"])
    db = app_db.get_session()
    try:
        et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=p, etapa_codigo="13").first()
        assert et.responsavel_terceiro_id == tid and et.responsavel_funcionario_id is None
        # responsável DEFINIDO como terceiro + etapa executável (gate liberado)
        r = mod_equipe.responsavel_da_etapa(db, lid, et)
        assert r["resolvido"] and r["tipo"] == "terceiro" and r["motivo"] == "definido"
        assert mod_equipe.etapa_executavel(db, lid, et) is True
    finally:
        db.close()
