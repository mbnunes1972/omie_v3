# -*- coding: utf-8 -*-
"""Chat — revisão do teste (decisões 16-17, 2026-07-25): mantém Funcionário-based; o CRIADOR do
projeto é o dono-base da tag "com a bola" (nunca "não atribuído"); concluir uma fase posta uma
mensagem AUTOMÁTICA de passagem oficial apontando a próxima etapa e seu responsável."""


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _mk_func(db, app_db, loja_id, nome_pessoa, funcao="Conferente"):
    fn = db.query(app_db.Funcao).filter_by(loja_id=loja_id, nome=funcao).first()
    if fn is None:
        fn = app_db.Funcao(loja_id=loja_id, nome=funcao); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja_id, nome=nome_pessoa, funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    return f


def _mk_etapa(db, app_db, nome, codigo, status="pendente", resp_fid=None):
    e = db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo=codigo).first()
    if e is None:
        e = app_db.CicloEtapa(projeto_nome=nome, etapa_codigo=codigo, status=status)
        db.add(e); db.flush()
    else:
        e.status = status
    if resp_fid is not None:
        e.responsavel_funcionario_id = resp_fid
    return e


# ── item 1: criador é o dono-base da tag ─────────────────────────────────────

def test_com_a_bola_cai_no_criador_com_funcionario(http_client_factory, seed, app_db):
    db = app_db.get_session()
    f_criador = _mk_func(db, app_db, seed["loja1_id"], "Criador Funcionário")
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    u.funcionario_id = f_criador.id
    proj = db.query(app_db.Projeto).filter_by(nome_safe="Proj_L1").first()
    proj.criado_por_id = u.id
    _mk_etapa(db, app_db, "Proj_L1", "19")     # etapa sem papel/faixa/override → cai no criador
    db.commit(); fid = f_criador.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/projetos/Proj_L1/ciclo")
    assert st == 200, body
    e19 = next(e for e in body["ciclo"] if e["etapa_codigo"] == "19")
    assert e19["responsavel_efetivo_id"] == fid
    assert e19["responsavel_efetivo_nome"] == "Criador Funcionário"
    assert body["criado_por_nome"] == "Diretor L1"


def test_criador_sem_funcionario_exibe_nome_do_usuario(http_client_factory, seed, app_db):
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    u.funcionario_id = None
    proj = db.query(app_db.Projeto).filter_by(nome_safe="Proj_L1").first()
    proj.criado_por_id = u.id
    _mk_etapa(db, app_db, "Proj_L1", "20")
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/projetos/Proj_L1/ciclo")
    e20 = next(e for e in body["ciclo"] if e["etapa_codigo"] == "20")
    assert e20["responsavel_efetivo_id"] is None          # sem funcionário, sem responsável formal
    assert body["criado_por_nome"] == "Diretor L1"        # mas a tag tem o nome do criador


def test_override_ainda_vence_o_criador(http_client_factory, seed, app_db):
    db = app_db.get_session()
    f_criador = _mk_func(db, app_db, seed["loja1_id"], "Criador X")
    f_resp = _mk_func(db, app_db, seed["loja1_id"], "Responsável Direto")
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    u.funcionario_id = f_criador.id
    db.query(app_db.Projeto).filter_by(nome_safe="Proj_L1").first().criado_por_id = u.id
    _mk_etapa(db, app_db, "Proj_L1", "19", resp_fid=f_resp.id)
    db.commit(); resp_id = f_resp.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/projetos/Proj_L1/ciclo")
    e19 = next(e for e in body["ciclo"] if e["etapa_codigo"] == "19")
    assert e19["responsavel_efetivo_id"] == resp_id       # override > criador


# ── item 2: mensagem automática na transição de fase ─────────────────────────

def test_concluir_fase_posta_mensagem_de_passagem(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L2", "1", status="concluido")
    _mk_etapa(db, app_db, "Proj_L2", "2", status="em_andamento")
    f_prox = _mk_func(db, app_db, seed["loja2_id"], "Dono da Fase 3")
    _mk_etapa(db, app_db, "Proj_L2", "3", resp_fid=f_prox.id)   # próxima principal
    db.commit(); fid = f_prox.id; db.close()

    c = _login(http_client_factory, "dir_l2")
    st, body = c.patch("/api/projetos/Proj_L2/ciclo/2", {"status": "concluido"})
    assert st == 200 and body["ok"], body

    st, body = c.get("/api/projetos/Proj_L2/conversa")
    autos = [m for m in body["mensagens"]
             if m["natureza"] == "transferencia" and m["etapa_codigo"] == "3"]
    assert autos, body
    m = autos[-1]
    assert m["transferido_para_funcionario_id"] == fid
    assert m["transferido_para_nome"] == "Dono da Fase 3"
    assert "automática" in m["corpo"].lower() or "passagem" in m["corpo"].lower()
    assert m["bloqueador"] is False


def test_concluir_ultima_fase_nao_quebra(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "20", status="concluido")
    _mk_etapa(db, app_db, "Proj_L1", "21", status="em_andamento")
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    # concluir a 21 (última principal): não há próxima → nenhuma mensagem, nenhum erro
    st, body = c.patch("/api/projetos/Proj_L1/ciclo/21", {"status": "concluido"})
    assert st in (200, 400), body        # pode ter gate próprio; o que importa é NÃO estourar 500
    assert st != 500
