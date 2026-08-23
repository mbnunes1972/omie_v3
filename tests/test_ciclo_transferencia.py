# -*- coding: utf-8 -*-
"""Concluir/Transferir responsabilidade da etapa do Ciclo (2026-08-23): "Concluir" preserva os
gates específicos de cada fase (não testados aqui de novo) — este endpoint só entra DEPOIS que a
etapa já está concluída, decidindo o que acontece com a responsabilidade da etapa SEGUINTE
(etapa_alvo_codigo, calculada no frontend). Handshake: destino com login fica 'pendente' até
"Receber Projeto"; destino sem login vira aceite automático na hora."""

from sqlalchemy import create_engine, inspect

from conftest import _test_database_url, _reset_schema_pg
import database


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _mk_func(db, app_db, loja_id, nome_pessoa, funcao="Conferente", usuario_id=None):
    fn = db.query(app_db.Funcao).filter_by(loja_id=loja_id, nome=funcao).first()
    if fn is None:
        fn = app_db.Funcao(loja_id=loja_id, nome=funcao); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja_id, nome=nome_pessoa, funcao_id=fn.id,
                           status="ativo", usuario_id=usuario_id)
    db.add(f); db.flush()
    return f


def _mk_terc(db, app_db, loja_id, nome_pessoa, usuario_id=None):
    t = app_db.Terceiro(loja_id=loja_id, nome=nome_pessoa, status="ativo", usuario_id=usuario_id)
    db.add(t); db.flush()
    return t


def _mk_usuario_login(db, app_db, loja_id, nome, login):
    u = app_db.Usuario(nome=nome, login=login, nivel="operador", loja_id=loja_id, ativo=1)
    u.set_senha("senha123")
    db.add(u); db.flush()
    return u


def _mk_etapa(db, app_db, nome, codigo, status="pendente"):
    e = db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo=codigo).first()
    if e is None:
        e = app_db.CicloEtapa(projeto_nome=nome, etapa_codigo=codigo, status=status)
        db.add(e); db.flush()
    else:
        e.status = status
    return e


# ── schema (Fase 1) ───────────────────────────────────────────────────────────

def test_colunas_de_transferencia_em_ciclo_etapas():
    eng = create_engine(_test_database_url())
    _reset_schema_pg(eng)
    database.Base.metadata.create_all(eng)
    cols = {c["name"] for c in inspect(eng).get_columns("ciclo_etapas")}
    assert {"transferencia_status", "transferencia_destino_funcionario_id",
            "transferencia_destino_terceiro_id", "transferencia_solicitada_por_usuario_id",
            "transferencia_solicitada_em"} <= cols


# ── pos-conclusao: não transferir ────────────────────────────────────────────

def test_pos_conclusao_sem_transferir_posta_no_chat_e_nao_muda_estado(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "19", status="concluido")
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/ciclo/19/pos-conclusao",
                       {"etapa_alvo_codigo": "20", "transferir": False})
    assert st == 200 and body["ok"], body
    assert body["transferencia_status"] == "nenhuma"

    st, body = c.get("/api/projetos/Proj_L1/conversa")
    autos = [m for m in body["mensagens"] if m.get("evento") == "etapa_concluida"]
    assert autos, body
    assert "19" in [m.get("etapa_codigo") for m in autos] or "concluída" in autos[-1]["corpo"].lower()

    db = app_db.get_session()
    e20 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1", etapa_codigo="20").first()
    assert e20 is not None and e20.transferencia_status == "nenhuma"
    db.close()


def test_pos_conclusao_exige_etapa_ja_concluida(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "19", status="em_andamento")
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/ciclo/19/pos-conclusao",
                       {"etapa_alvo_codigo": "20", "transferir": False})
    assert st == 400, body


# ── pos-conclusao: transferir para quem TEM login (pendente) ────────────────

def test_transferir_para_funcionario_com_login_fica_pendente(http_client_factory, seed, app_db):
    db = app_db.get_session()
    u_dest = _mk_usuario_login(db, app_db, seed["loja1_id"], "Destino Com Login", "dest_login1")
    f_dest = _mk_func(db, app_db, seed["loja1_id"], "Destino Com Login", usuario_id=u_dest.id)
    _mk_etapa(db, app_db, "Proj_L1", "19", status="concluido")
    db.commit(); fid = f_dest.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/ciclo/19/pos-conclusao",
                       {"etapa_alvo_codigo": "20", "transferir": True, "funcionario_id": fid})
    assert st == 200 and body["ok"], body
    assert body["transferencia_status"] == "pendente"
    assert body["destino_nome"] == "Destino Com Login"

    db = app_db.get_session()
    e20 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1", etapa_codigo="20").first()
    assert e20.transferencia_status == "pendente"
    assert e20.transferencia_destino_funcionario_id == fid
    assert e20.responsavel_funcionario_id != fid   # ainda NÃO efetivou — só após aceite
    db.close()

    st, body = c.get("/api/projetos/Proj_L1/conversa")
    autos = [m for m in body["mensagens"] if m.get("evento") == "transferencia_pendente"]
    assert autos, body


# ── pos-conclusao: transferir para quem NÃO tem login (aceite automático) ───

def test_transferir_para_terceiro_sem_login_aceita_automatico(http_client_factory, seed, app_db):
    db = app_db.get_session()
    t_dest = _mk_terc(db, app_db, seed["loja1_id"], "Terceiro Sem Login")
    _mk_etapa(db, app_db, "Proj_L1", "19", status="concluido")
    db.commit(); tid = t_dest.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/ciclo/19/pos-conclusao",
                       {"etapa_alvo_codigo": "20", "transferir": True, "terceiro_id": tid})
    assert st == 200 and body["ok"], body
    assert body["transferencia_status"] == "aceita"
    assert body.get("automatica") is True

    db = app_db.get_session()
    e20 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1", etapa_codigo="20").first()
    assert e20.transferencia_status == "nenhuma"
    assert e20.responsavel_terceiro_id == tid
    db.close()

    st, body = c.get("/api/projetos/Proj_L1/conversa")
    autos = [m for m in body["mensagens"] if m.get("evento") == "transferencia_aceita"]
    assert autos and "automático" in autos[-1]["corpo"].lower()


# ── aceitar ("Receber Projeto") ──────────────────────────────────────────────

def test_aceitar_por_quem_nao_e_o_destino_devolve_403(http_client_factory, seed, app_db):
    db = app_db.get_session()
    u_dest = _mk_usuario_login(db, app_db, seed["loja1_id"], "Destino", "dest_login2")
    f_dest = _mk_func(db, app_db, seed["loja1_id"], "Destino", usuario_id=u_dest.id)
    e20 = _mk_etapa(db, app_db, "Proj_L1", "20", status="pendente")
    e20.transferencia_status = "pendente"
    e20.transferencia_destino_funcionario_id = f_dest.id
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")   # não é o destino
    st, body = c.post("/api/projetos/Proj_L1/ciclo/20/transferencia/aceitar")
    assert st == 403, body


def test_aceitar_pelo_destino_certo_efetiva_responsavel(http_client_factory, seed, app_db):
    db = app_db.get_session()
    u_dest = _mk_usuario_login(db, app_db, seed["loja1_id"], "Destino Aceita", "dest_login3")
    f_dest = _mk_func(db, app_db, seed["loja1_id"], "Destino Aceita", usuario_id=u_dest.id)
    e20 = _mk_etapa(db, app_db, "Proj_L1", "20", status="pendente")
    e20.transferencia_status = "pendente"
    e20.transferencia_destino_funcionario_id = f_dest.id
    db.commit(); fid = f_dest.id; db.close()

    c = _login(http_client_factory, "dest_login3")
    st, body = c.post("/api/projetos/Proj_L1/ciclo/20/transferencia/aceitar")
    assert st == 200 and body["ok"], body
    assert body["responsavel_funcionario_id"] == fid

    db = app_db.get_session()
    e20 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1", etapa_codigo="20").first()
    assert e20.transferencia_status == "nenhuma"
    assert e20.responsavel_funcionario_id == fid
    db.close()

    st, body = c.get("/api/projetos/Proj_L1/conversa")
    autos = [m for m in body["mensagens"] if m.get("evento") == "transferencia_aceita"]
    assert autos


def test_aceitar_sem_transferencia_pendente_devolve_400(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "20", status="pendente")
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/ciclo/20/transferencia/aceitar")
    assert st == 400, body


# ── Fase 4: /api/me/ciclo/pendencias e /responsabilidades ───────────────────

def test_pendencias_so_aparecem_para_o_destino_certo_e_somem_apos_aceite(http_client_factory, seed, app_db):
    db = app_db.get_session()
    u_dest = _mk_usuario_login(db, app_db, seed["loja1_id"], "Fulano Pendente", "pend_dest1")
    f_dest = _mk_func(db, app_db, seed["loja1_id"], "Fulano Pendente", usuario_id=u_dest.id)
    e20 = _mk_etapa(db, app_db, "Proj_L1", "20", status="pendente")
    e20.transferencia_status = "pendente"
    e20.transferencia_destino_funcionario_id = f_dest.id
    db.commit(); db.close()

    c_dest = _login(http_client_factory, "pend_dest1")
    st, body = c_dest.get("/api/me/ciclo/pendencias")
    assert st == 200 and body["ok"], body
    assert any(i["projeto_nome"] == "Proj_L1" and i["etapa_codigo"] == "20" for i in body["itens"])

    c_outro = _login(http_client_factory, "dir_l1")
    st, body = c_outro.get("/api/me/ciclo/pendencias")
    assert st == 200
    assert not any(i["projeto_nome"] == "Proj_L1" and i["etapa_codigo"] == "20" for i in body["itens"])

    st, body = c_dest.post("/api/projetos/Proj_L1/ciclo/20/transferencia/aceitar")
    assert st == 200 and body["ok"], body
    st, body = c_dest.get("/api/me/ciclo/pendencias")
    assert not any(i["projeto_nome"] == "Proj_L1" and i["etapa_codigo"] == "20" for i in body["itens"])


def test_responsabilidades_refletem_overrides_e_transferencias_aceitas(http_client_factory, seed, app_db):
    db = app_db.get_session()
    u = _mk_usuario_login(db, app_db, seed["loja1_id"], "Fulano Responsável", "resp_dest1")
    f = _mk_func(db, app_db, seed["loja1_id"], "Fulano Responsável", usuario_id=u.id)
    e = _mk_etapa(db, app_db, "Proj_L1", "19", status="em_andamento")
    e.responsavel_funcionario_id = f.id
    db.commit(); db.close()

    c = _login(http_client_factory, "resp_dest1")
    st, body = c.get("/api/me/ciclo/responsabilidades")
    assert st == 200 and body["ok"], body
    assert any(i["projeto_nome"] == "Proj_L1" and i["etapa_codigo"] == "19" for i in body["itens"])


def test_responsabilidades_isolam_por_loja_mesmo_com_funcionario_id_batendo(http_client_factory, seed, app_db):
    # Anomalia proposital: funcionário da loja 1 aparece como responsavel_funcionario_id numa
    # etapa de um projeto da loja 2 (não deveria acontecer via UI, mas o endpoint tem que ser
    # defensivo). O filtro por ator["lojas_ids"] é a fronteira de segurança real aqui.
    db = app_db.get_session()
    u = _mk_usuario_login(db, app_db, seed["loja1_id"], "Fulano Cross", "cross_dest1")
    f = _mk_func(db, app_db, seed["loja1_id"], "Fulano Cross", usuario_id=u.id)
    e = _mk_etapa(db, app_db, "Proj_L2", "19", status="em_andamento")   # projeto da LOJA 2
    e.responsavel_funcionario_id = f.id
    db.commit(); db.close()

    c = _login(http_client_factory, "cross_dest1")
    st, body = c.get("/api/me/ciclo/responsabilidades")
    assert st == 200
    assert not any(i["projeto_nome"] == "Proj_L2" for i in body["itens"])
