"""Assistência ganha agendamento próprio (2026-08-06): ambiente + janela + equipe, anexos, e
conflito de agenda CRUZADO com Montagem (mesma pessoa não pode estar nos dois ao mesmo tempo).
A Assistência saiu do Mapa de Atribuições — este arquivo cobre o que substituiu aquele mecanismo."""
from datetime import date, datetime

import pytest

import mod_assistencias as ma
from database import (AssistenciaCaso, AssistenciaExecutor, AssistenciaAnexo, CicloEtapa,
                      Contrato, Funcao, Funcionario, Orcamento, OrcamentoAmbiente, PoolAmbiente,
                      Projeto, Usuario)


def _montador(app_db, db, loja_id, nome, login):
    u = db.query(Usuario).filter_by(login=login).first()
    if not u:
        u = Usuario(nome=nome, login=login, nivel="operador", loja_id=loja_id, ativo=1)
        u.set_senha("senha123"); db.add(u); db.flush()
    f = db.query(Funcao).filter_by(loja_id=loja_id, nome="Montador").first()
    if not f:
        f = Funcao(loja_id=loja_id, nome="Montador", status="ativo"); db.add(f); db.flush()
    func = db.query(Funcionario).filter_by(usuario_id=u.id).first()
    if not func:
        func = Funcionario(loja_id=loja_id, nome=nome, funcao_id=f.id, usuario_id=u.id)
        db.add(func); db.flush()
    else:
        func.funcao_id = f.id
    return func.id


def _ambiente(db, projeto_nome, orcamento_id, nome="Cozinha"):
    pa = PoolAmbiente(projeto_id=projeto_nome, nome=nome, nome_exibicao=nome,
                      xml_path="/dev/null", ambientes_json="[]",
                      budget_total=1000.0, order_total=500.0)
    db.add(pa); db.flush()
    db.add(OrcamentoAmbiente(orcamento_id=orcamento_id, pool_ambiente_id=pa.id))
    return pa.id


def _projeto_b(db, loja_id, cliente_id, nome="Proj_L1_B"):
    p2 = db.get(Projeto, nome)
    if not p2:
        p2 = Projeto(nome_safe=nome, cliente_id=cliente_id, status="quente", loja_id=loja_id)
        db.add(p2); db.flush()
    o2 = db.query(Orcamento).filter_by(projeto_id=nome).first()
    if not o2:
        o2 = Orcamento(projeto_id=nome, nome="Orçamento 1", ordem=1, loja_id=loja_id)
        db.add(o2); db.flush()
    if not db.query(Contrato).filter_by(projeto_nome=nome).first():
        db.add(Contrato(projeto_nome=nome, orcamento_id=o2.id, loja_id=loja_id))
    return p2, o2


def _janela_montagem(db, nome_safe, entrega, fim17):
    """Cronograma mínimo pra itens_montagem calcular uma janela (mesmo padrão de
    test_montagem_gantt.py::_setup): entrega + etapa 17 prevista."""
    p = db.get(Projeto, nome_safe)
    p.data_entrega = entrega
    e17 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="17").first()
    if not e17:
        e17 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="17"); db.add(e17)
    e17.data_prevista_conclusao = fim17
    e17.status = "pendente"; e17.concluido_em = None


# ── mod_assistencias: modelo + serialize ──────────────────────────────────────────────────

def test_criar_caso_com_agendamento_e_equipe(app_db, seed):
    db = app_db.get_session()
    try:
        nome = seed["projeto_l1"]
        amb_id = _ambiente(db, nome, seed["orcamento_l1_id"])
        func_id = _montador(app_db, db, seed["loja1_id"], "Montador X", "mont_x")
        db.commit()
        caso = ma.criar_caso(db, seed["loja1_id"], nome, "montagem", "erro_montagem", "porta solta",
                             200.0, None, pool_ambiente_id=amb_id,
                             data_inicio=date(2026, 9, 10), data_fim=date(2026, 9, 11))
        ma.definir_equipe(db, caso, [("funcionario", func_id)])
        db.commit()
        d = ma.serialize(db, caso)
        assert d["ambiente_nome"] == "Cozinha"
        assert d["data_inicio"] == "2026-09-10" and d["data_fim"] == "2026-09-11"
        assert d["equipe"] == [{"chave": "f:%d" % func_id, "nome": "Montador X"}]
        assert d["anexos"] == []
    finally:
        db.close()


def test_criar_caso_janela_incompleta_rejeitada(app_db, seed):
    db = app_db.get_session()
    try:
        with pytest.raises(ValueError):
            ma.criar_caso(db, seed["loja1_id"], None, "montagem", "erro_montagem", "x", 10.0, None,
                         data_inicio=date(2026, 9, 10))   # sem data_fim
    finally:
        db.close()


def test_definir_equipe_substitui(app_db, seed):
    db = app_db.get_session()
    try:
        nome = seed["projeto_l1"]
        f1 = _montador(app_db, db, seed["loja1_id"], "Montador Y", "mont_y")
        f2 = _montador(app_db, db, seed["loja1_id"], "Montador Z", "mont_z")
        db.commit()
        caso = ma.criar_caso(db, seed["loja1_id"], nome, "montagem", "erro_montagem", "x", 10.0, None)
        ma.definir_equipe(db, caso, [("funcionario", f1)])
        db.commit()
        assert len(ma.equipe_do_caso(db, caso.id)) == 1
        ma.definir_equipe(db, caso, [("funcionario", f1), ("funcionario", f2)])
        db.commit()
        assert len(ma.equipe_do_caso(db, caso.id)) == 2
        ma.definir_equipe(db, caso, [])
        db.commit()
        assert ma.equipe_do_caso(db, caso.id) == []
    finally:
        db.close()


# ── HTTP: criar com ambiente/datas/equipe ─────────────────────────────────────────────────

def test_endpoint_cria_com_ambiente_datas_equipe(http_client_factory, app_db, seed):
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        amb_id = _ambiente(db, nome, seed["orcamento_l1_id"], "Suíte")
        func_id = _montador(app_db, db, seed["loja1_id"], "Montador Ana", "mont_ana")
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/assistencias/casos", {
        "projeto_nome": nome, "pool_ambiente_id": amb_id, "sub_tipo": "montagem",
        "motivo": "erro_montagem", "descricao": "gaveta emperrada", "valor": 150,
        "data_inicio": "2026-09-20", "data_fim": "2026-09-21",
        "executores": [{"tipo": "funcionario", "id": func_id}],
    })
    assert st == 201, d
    st, lst = c.get("/api/assistencias/casos")
    item = next(x for x in lst["casos"] if x["id"] == d["id"])
    assert item["ambiente_nome"] == "Suíte"
    assert item["data_inicio"] == "2026-09-20" and item["data_fim"] == "2026-09-21"
    assert item["equipe"] == [{"chave": "f:%d" % func_id, "nome": "Montador Ana"}]


def test_endpoint_ambiente_de_outro_projeto_rejeitado(http_client_factory, app_db, seed):
    db = app_db.get_session()
    try:
        p2, o2 = _projeto_b(db, seed["loja1_id"], seed["cliente_l1_id"])
        amb_id = _ambiente(db, "Proj_L1_B", o2.id, "Sala")
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/assistencias/casos", {
        "projeto_nome": seed["projeto_l1"], "pool_ambiente_id": amb_id,
        "sub_tipo": "montagem", "motivo": "erro_montagem", "valor": 10,
    })
    assert st == 404, d


def test_endpoint_executor_sem_funcao_elegivel_rejeitado(http_client_factory, app_db, seed):
    db = app_db.get_session()
    try:
        u = Usuario(nome="Consultor Q", login="cons_q", nivel="operador",
                   loja_id=seed["loja1_id"], ativo=1)
        u.set_senha("senha123"); db.add(u); db.flush()
        fq = db.query(Funcao).filter_by(loja_id=seed["loja1_id"], nome="Consultor de Vendas").first()
        if not fq:
            fq = Funcao(loja_id=seed["loja1_id"], nome="Consultor de Vendas", status="ativo")
            db.add(fq); db.flush()
        func = Funcionario(loja_id=seed["loja1_id"], nome="Consultor Q", funcao_id=fq.id, usuario_id=u.id)
        db.add(func); db.flush()
        func_id = func.id
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/assistencias/casos", {
        "projeto_nome": seed["projeto_l1"], "sub_tipo": "montagem", "motivo": "erro_montagem",
        "valor": 10, "executores": [{"tipo": "funcionario", "id": func_id}],
    })
    assert st == 400, d


# ── Conflito CRUZADO Montagem × Assistência (o reforço explícito do usuário) ──────────────

def test_assistencia_bloqueia_contra_montagem_existente(http_client_factory, app_db, seed):
    """Montador já responde por Montagem no Proj_L1 (14–17/09). Criar uma Assistência no
    Proj_L1_B pro MESMO montador com janela sobreposta tem que ser BLOQUEADO (409), nada salvo."""
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        amb_ids = [_ambiente(db, nome, seed["orcamento_l1_id"], "Cozinha")]
        func_id = _montador(app_db, db, seed["loja1_id"], "Montador Conflito 1", "mont_c1")
        _janela_montagem(db, nome, datetime(2026, 9, 11), datetime(2026, 9, 17))
        p2, o2 = _projeto_b(db, seed["loja1_id"], seed["cliente_l1_id"])
        amb2_id = _ambiente(db, "Proj_L1_B", o2.id, "Sala")
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _d = c.post("/api/projetos/%s/atribuicoes" % nome,
                    {"papel": "montagem", "pool_ambiente_ids": amb_ids, "funcionario_id": func_id})
    assert st == 200, _d
    n_antes = None
    db = app_db.get_session()
    try:
        n_antes = db.query(AssistenciaCaso).filter_by(loja_id=seed["loja1_id"]).count()
    finally:
        db.close()
    st, d = c.post("/api/assistencias/casos", {
        "projeto_nome": "Proj_L1_B", "pool_ambiente_id": amb2_id, "sub_tipo": "montagem",
        "motivo": "erro_montagem", "valor": 10,
        "data_inicio": "2026-09-15", "data_fim": "2026-09-16",   # dentro de 14–17/09
        "executores": [{"tipo": "funcionario", "id": func_id}],
    })
    assert st == 409 and d["ok"] is False, d
    assert "onflito" in d["erro"] and nome in d["erro"]
    db = app_db.get_session()
    try:
        assert db.query(AssistenciaCaso).filter_by(loja_id=seed["loja1_id"]).count() == n_antes
    finally:
        db.close()


def test_montagem_bloqueia_contra_assistencia_existente(http_client_factory, app_db, seed):
    """Inverso: montador já tem uma Assistência agendada no Proj_L1_B. Atribuir Montagem pro
    MESMO montador no Proj_L1 com janela sobreposta tem que ser BLOQUEADO."""
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        amb_ids = [_ambiente(db, nome, seed["orcamento_l1_id"], "Cozinha")]
        func_id = _montador(app_db, db, seed["loja1_id"], "Montador Conflito 2", "mont_c2")
        _janela_montagem(db, nome, datetime(2026, 9, 11), datetime(2026, 9, 17))
        p2, o2 = _projeto_b(db, seed["loja1_id"], seed["cliente_l1_id"])
        db.commit()
        caso = ma.criar_caso(db, seed["loja1_id"], "Proj_L1_B", "montagem", "erro_montagem", "x", 10.0,
                             None, data_inicio=date(2026, 9, 15), data_fim=date(2026, 9, 16))
        ma.definir_equipe(db, caso, [("funcionario", func_id)])
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/atribuicoes" % nome,
                   {"papel": "montagem", "pool_ambiente_ids": amb_ids, "funcionario_id": func_id})
    assert st == 409 and d["ok"] is False, d
    assert "onflito" in d["erro"] and "Proj_L1_B" in d["erro"]


def test_assistencia_nao_conflita_dentro_do_mesmo_projeto(http_client_factory, app_db, seed):
    """Mesmo projeto: montagem num ambiente + assistência noutro ambiente do MESMO projeto,
    mesmo montador, janelas sobrepostas — filosofia existente (equipe pode se dividir dentro
    do mesmo projeto) preservada, não bloqueia."""
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        amb_ids = [_ambiente(db, nome, seed["orcamento_l1_id"], "Cozinha")]
        amb2_id = _ambiente(db, nome, seed["orcamento_l1_id"], "Sala")
        func_id = _montador(app_db, db, seed["loja1_id"], "Montador Mesmo Proj", "mont_mp")
        _janela_montagem(db, nome, datetime(2026, 9, 11), datetime(2026, 9, 17))
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _d = c.post("/api/projetos/%s/atribuicoes" % nome,
                    {"papel": "montagem", "pool_ambiente_ids": amb_ids, "funcionario_id": func_id})
    assert st == 200, _d
    st, d = c.post("/api/assistencias/casos", {
        "projeto_nome": nome, "pool_ambiente_id": amb2_id, "sub_tipo": "montagem",
        "motivo": "erro_montagem", "valor": 10,
        "data_inicio": "2026-09-15", "data_fim": "2026-09-16",
        "executores": [{"tipo": "funcionario", "id": func_id}],
    })
    assert st == 201, d


# ── GET /api/agenda/disponibilidade (linha de headcount, 2026-08-06) ──────────────────────

def test_disponibilidade_desconta_montagem_e_assistencia(http_client_factory, app_db, seed):
    # Projetos/datas EXCLUSIVOS deste teste (novembro/2026, "Proj_Disp_*") — o schema de teste
    # reseta por ARQUIVO, não por teste, então reusar Proj_L1/setembro colidiria com marcações
    # de outros testes deste módulo (o item é por FASE: "montadores" é a UNIÃO de todos os
    # ambientes daquela fase, então sobras de outro teste inflariam a contagem de ocupados).
    db = app_db.get_session()
    try:
        p1 = Projeto(nome_safe="Proj_Disp_A", cliente_id=seed["cliente_l1_id"],
                    status="quente", loja_id=seed["loja1_id"])
        db.add(p1); db.flush()
        o1 = Orcamento(projeto_id="Proj_Disp_A", nome="Orçamento 1", ordem=1, loja_id=seed["loja1_id"])
        db.add(o1); db.flush()
        db.add(Contrato(projeto_nome="Proj_Disp_A", orcamento_id=o1.id, loja_id=seed["loja1_id"]))
        amb_ids = [_ambiente(db, "Proj_Disp_A", o1.id, "Cozinha")]
        f1 = _montador(app_db, db, seed["loja1_id"], "Montador Disp 1", "mont_d1")
        f2 = _montador(app_db, db, seed["loja1_id"], "Montador Disp 2", "mont_d2")
        _janela_montagem(db, "Proj_Disp_A", datetime(2026, 11, 11), datetime(2026, 11, 17))   # 14–17/11
        p2, o2 = _projeto_b(db, seed["loja1_id"], seed["cliente_l1_id"], "Proj_Disp_B")
        amb2_id = _ambiente(db, "Proj_Disp_B", o2.id, "Sala")
        db.commit()
        caso = ma.criar_caso(db, seed["loja1_id"], "Proj_Disp_B", "montagem", "erro_montagem", "x", 10.0,
                             None, pool_ambiente_id=amb2_id,
                             data_inicio=date(2026, 11, 14), data_fim=date(2026, 11, 15))
        ma.definir_equipe(db, caso, [("funcionario", f2)])
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _d = c.post("/api/projetos/Proj_Disp_A/atribuicoes",
                    {"papel": "montagem", "pool_ambiente_ids": amb_ids, "funcionario_id": f1})
    assert st == 200, _d
    st, d = c.get("/api/agenda/disponibilidade?de=2026-11-14&ate=2026-11-17")
    assert st == 200 and d["ok"], d
    assert d["total"] >= 2
    por_dia = {x["data"]: x["disponivel"] for x in d["dias"]}
    # 14 e 15/11: os DOIS montadores ocupados (f1 na montagem, f2 na assistência)
    assert por_dia["2026-11-14"] == d["total"] - 2
    assert por_dia["2026-11-15"] == d["total"] - 2
    # 16 e 17/11: só f1 (assistência já acabou em 15)
    assert por_dia["2026-11-16"] == d["total"] - 1
    assert por_dia["2026-11-17"] == d["total"] - 1


def test_disponibilidade_exige_de_ate(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/agenda/disponibilidade")
    assert st == 400


# ── GET /api/agenda/assistencia (Gantt) ───────────────────────────────────────────────────

def test_endpoint_agenda_assistencia_lista_apenas_abertos(http_client_factory, app_db, seed):
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        amb_id = _ambiente(db, nome, seed["orcamento_l1_id"], "Cozinha")
        func_id = _montador(app_db, db, seed["loja1_id"], "Montador Gantt", "mont_g")
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/assistencias/casos", {
        "projeto_nome": nome, "pool_ambiente_id": amb_id, "sub_tipo": "montagem",
        "motivo": "erro_montagem", "valor": 10,
        "data_inicio": "2026-09-20", "data_fim": "2026-09-21",
        "executores": [{"tipo": "funcionario", "id": func_id}],
    })
    assert st == 201
    cid = d["id"]
    # caso SEM agendamento (sem datas) — não deve aparecer no Gantt
    st2, d2 = c.post("/api/assistencias/casos", {"sub_tipo": "montagem", "motivo": "erro_montagem",
                                                 "valor": 10})
    assert st2 == 201
    st, g = c.get("/api/agenda/assistencia?de=2026-09-01&ate=2026-09-30")
    assert st == 200 and g["ok"]
    ids = {i["caso_id"] for i in g["itens"]}
    assert cid in ids and d2["id"] not in ids
    item = next(i for i in g["itens"] if i["caso_id"] == cid)
    assert item["projeto"] == nome and item["ambiente_nome"] == "Cozinha"
    assert item["inicio"] == "2026-09-20" and item["fim"] == "2026-09-21"
    assert item["montadores"] == [{"chave": "f:%d" % func_id, "nome": "Montador Gantt"}]
    # realizar o caso tira ele do Gantt (só 'aberto' agenda recurso)
    st, _ = c.post("/api/assistencias/casos/%d/realizar" % cid, {"valor": 10})
    assert st == 200
    st, g2 = c.get("/api/agenda/assistencia?de=2026-09-01&ate=2026-09-30")
    assert cid not in {i["caso_id"] for i in g2["itens"]}


# ── Anexos ─────────────────────────────────────────────────────────────────────────────────

def test_anexo_upload_e_download(http_client_factory, app_db, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/assistencias/casos", {"sub_tipo": "montagem", "motivo": "erro_montagem",
                                               "valor": 10})
    assert st == 201
    cid = d["id"]
    st, up = c.post_multipart("/api/assistencias/casos/%d/anexo" % cid,
                              files={"arquivo": ("foto.jpg", b"conteudo-fake-jpg")})
    assert st == 201, up
    st, lst = c.get("/api/assistencias/casos")
    item = next(x for x in lst["casos"] if x["id"] == cid)
    assert len(item["anexos"]) == 1 and item["anexos"][0]["nome_original"] == "foto.jpg"
    st2, body2 = c.get("/api/assistencias/casos/%d/anexo/%d" % (cid, item["anexos"][0]["id"]))
    assert st2 == 200 and body2 == b"conteudo-fake-jpg"


def test_anexo_de_caso_de_outra_loja_bloqueado(http_client_factory, app_db, seed):
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    st, d = c1.post("/api/assistencias/casos", {"sub_tipo": "montagem", "motivo": "erro_montagem",
                                                "valor": 10})
    cid = d["id"]
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    st, up = c2.post_multipart("/api/assistencias/casos/%d/anexo" % cid,
                               files={"arquivo": ("x.jpg", b"y")})
    assert st == 404
