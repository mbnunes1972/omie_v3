"""Gantt de Montagem + espelho de atribuições + conflitos (rev 2026-08-03).

- mod_agenda.itens_montagem: janela por fase (dia útil após a ENTREGA → prevista/realizada 17).
- mod_agenda.conflitos_montagem: mesmo montador em janelas SOBREPOSTAS de projetos distintos.
- GET /api/agenda/montagem: itens + ambientes com Val_Liq + montador do Mapa + conflitos.
- POST /atribuicoes: LOTE (pool_ambiente_ids), notificação via Orizon Chat e aviso de conflito."""
from datetime import date, datetime

import mod_agenda
from database import (AtribuicaoAmbiente, CicloEtapa, Contrato, ConversaMensagem, Funcao,
                      Funcionario, Orcamento, OrcamentoAmbiente, PoolAmbiente, Projeto, Usuario)


# ── motor puro ───────────────────────────────────────────────────────────────────

def _proj(nome, entrega, fim17, **kw):
    base = {"nome_safe": nome, "cliente": None, "val_liq": 3000.0, "orcamento_id": None,
            "previsao_medicao": None, "data_entrega": entrega,
            "etapas": {"17": {"prevista": fim17, "concluida_em": None}}, "fases": []}
    base.update(kw)
    return base


def test_itens_montagem_janela_e_retida():
    p = _proj("P1", datetime(2026, 9, 11), datetime(2026, 9, 17))   # entrega sex → inicia seg 14
    its = mod_agenda.itens_montagem([p])
    assert [(i["inicio"], i["fim"], i["realizado"]) for i in its] == \
        [(date(2026, 9, 14), date(2026, 9, 17), False)]
    p2 = _proj("P2", datetime(2026, 9, 11), None,
               fases=[{"id": 1, "ordem": 1, "status": "retido", "val_liq": 1000.0,
                       "entrega_prevista": date(2026, 10, 2), "card_prazo_entrega": None,
                       "card_data_entrega": None}])
    its2 = mod_agenda.itens_montagem([p2])
    assert its2[0]["retida"] and its2[0]["inicio"] == date(2026, 10, 5)   # seg após sex 02/10
    assert mod_agenda.itens_montagem([_proj("P3", None, None)]) == []     # sem entrega → fora


def test_conflitos_montagem_sobreposicao_entre_projetos():
    m = [{"chave": "f:1", "nome": "João"}]
    a = {"projeto": "A", "fase": None, "inicio": date(2026, 9, 14), "fim": date(2026, 9, 18),
         "realizado": False, "montadores": m}
    b = {"projeto": "B", "fase": None, "inicio": date(2026, 9, 17), "fim": date(2026, 9, 22),
         "realizado": False, "montadores": m}
    c = {"projeto": "C", "fase": None, "inicio": date(2026, 9, 23), "fim": date(2026, 9, 25),
         "realizado": False, "montadores": m}
    confs = mod_agenda.conflitos_montagem([a, b, c])
    assert len(confs) == 1 and confs[0]["chave"] == "f:1"
    assert sorted(x["projeto"] for x in confs[0]["itens"]) == ["A", "B"]   # C não sobrepõe
    # fases do MESMO projeto não conflitam; realizado fica fora
    a2 = dict(a, fase=1); b2 = dict(a, fase=2, projeto="A")
    assert mod_agenda.conflitos_montagem([a2, b2]) == []
    assert mod_agenda.conflitos_montagem([a, dict(b, realizado=True)]) == []


def test_itens_pe_janela_10_a_11():
    p = {"nome_safe": "P1", "cliente": None, "val_liq": 3000.0, "orcamento_id": None,
         "previsao_medicao": None, "data_entrega": None,
         "etapas": {"10": {"concluida_em": datetime(2026, 9, 4)},     # sex → PE inicia seg 07
                    "11": {"prevista": datetime(2026, 9, 18)}}, "fases": []}
    its = mod_agenda.itens_pe([p])
    assert [(i["inicio"], i["fim"], i["realizado"]) for i in its] == \
        [(date(2026, 9, 7), date(2026, 9, 18), False)]
    # sem a janela definida (falta 11) → fora
    p2 = dict(p, etapas={"10": {"concluida_em": datetime(2026, 9, 4)}})
    assert mod_agenda.itens_pe([p2]) == []


# ── endpoint + POST em lote + notificação ────────────────────────────────────────

def _setup(app_db, seed):
    """Proj_L1 com entrega/17 previstas, 2 ambientes contratados e um MONTADOR com login."""
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        db.query(AtribuicaoAmbiente).filter_by(projeto_nome=nome).delete()
        db.query(OrcamentoAmbiente).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
        for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome).all():
            db.delete(pa)
        db.flush()
        p = db.get(Projeto, nome)
        p.data_entrega = datetime(2026, 9, 11)
        db.get(Orcamento, seed["orcamento_l1_id"]).valor_liquido = 3000.0
        e17 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="17").first()
        if not e17:
            e17 = CicloEtapa(projeto_nome=nome, etapa_codigo="17"); db.add(e17)
        e17.data_prevista_conclusao = datetime(2026, 9, 17)
        e17.status = "pendente"; e17.concluido_em = None
        ids = []
        for n in ("Cozinha", "Suite"):
            pa = PoolAmbiente(projeto_id=nome, nome=n, nome_exibicao=n, xml_path="/dev/null",
                              ambientes_json="[]", budget_total=1500.0, order_total=500.0)
            db.add(pa); db.flush()
            db.add(OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"], pool_ambiente_id=pa.id))
            ids.append(pa.id)
        u = db.query(Usuario).filter_by(login="mont_l1").first()
        if not u:
            u = Usuario(nome="Montador L1", login="mont_l1", nivel="operador",
                        loja_id=seed["loja1_id"], ativo=1)
            u.set_senha("senha123"); db.add(u); db.flush()
        f = db.query(Funcao).filter_by(loja_id=seed["loja1_id"], nome="Montador").first()
        if not f:
            f = Funcao(loja_id=seed["loja1_id"], nome="Montador", status="ativo")
            db.add(f); db.flush()
        func = db.query(Funcionario).filter_by(usuario_id=u.id).first()
        if not func:
            func = Funcionario(loja_id=seed["loja1_id"], nome="Montador L1",
                               funcao_id=f.id, usuario_id=u.id)
            db.add(func); db.flush()
        else:
            func.funcao_id = f.id
        db.commit()
        return ids, func.id, u.id
    finally:
        db.close()


def test_post_lote_notifica_e_gantt_espelha(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids, func_id, mont_uid = _setup(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # LOTE: "Todos os ambientes" → um POST, uma notificação
    st, d = c.post("/api/projetos/%s/atribuicoes" % nome,
                   {"papel": "montagem", "pool_ambiente_ids": ids, "funcionario_id": func_id})
    assert st == 200 and d["ok"], (st, d)
    assert d["notificado"] is True
    db = app_db.get_session()
    try:
        msgs = (db.query(ConversaMensagem)
                  .filter(ConversaMensagem.corpo.like("%atribuído%")).all())
        assert any("Montagem" in m.corpo and nome in m.corpo for m in msgs)
    finally:
        db.close()
    # Gantt/espelho: item com janela, ambientes com Val_Liq e o montador em cada ambiente
    st, g = c.get("/api/agenda/montagem?de=2026-09-01&ate=2026-09-30")
    assert st == 200 and g["ok"], (st, g)
    it = next(i for i in g["itens"] if i["projeto"] == nome)
    assert it["inicio"] == "2026-09-14" and it["fim"] == "2026-09-17"
    assert len(it["ambientes"]) == 2
    assert all(a["montador"] and a["montador"]["nome"] == "Montador L1" for a in it["ambientes"])
    assert round(sum(a["val_liq"] for a in it["ambientes"]), 2) == 3000.0   # Σ liq por ambiente
    assert g["conflitos"] == []


def test_endpoint_papel_projeto_executivo(app_db, seed, http_client_factory):
    """Aba PE do Operacional: mesmo endpoint com ?papel=projeto_executivo — janela 10→11 e o
    PROJETISTA do Mapa no espelho."""
    nome = seed["projeto_l1"]
    ids, _func_mont, _ = _setup(app_db, seed)
    db = app_db.get_session()
    try:
        for cod, dt in (("10", datetime(2026, 9, 4)), ("11", datetime(2026, 9, 18))):
            e = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo=cod).first()
            if not e:
                e = CicloEtapa(projeto_nome=nome, etapa_codigo=cod); db.add(e)
            e.data_prevista_conclusao = dt; e.status = "pendente"; e.concluido_em = None
        f = db.query(Funcao).filter_by(loja_id=seed["loja1_id"], nome="Projetista Executivo").first()
        if not f:
            f = Funcao(loja_id=seed["loja1_id"], nome="Projetista Executivo", status="ativo")
            db.add(f); db.flush()
        proj = Funcionario(loja_id=seed["loja1_id"], nome="Projetista L1", funcao_id=f.id)
        db.add(proj); db.flush()
        proj_id = proj.id
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/atribuicoes" % nome,
                   {"papel": "projeto_executivo", "pool_ambiente_ids": ids,
                    "funcionario_id": proj_id})
    assert st == 200 and d["ok"], (st, d)
    st, g = c.get("/api/agenda/montagem?papel=projeto_executivo&de=2026-09-01&ate=2026-09-30")
    assert st == 200 and g["ok"], (st, g)
    it = next(i for i in g["itens"] if i["projeto"] == nome)
    assert it["inicio"] == "2026-09-07" and it["fim"] == "2026-09-18"
    assert all(a["montador"] and a["montador"]["nome"] == "Projetista L1"
               for a in it["ambientes"])
    st, _bad = c.get("/api/agenda/montagem?papel=invalido")
    assert st == 400


def test_conflito_avisado_no_post(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids, func_id, _ = _setup(app_db, seed)
    # segundo projeto NA MESMA loja com janela sobreposta
    db = app_db.get_session()
    try:
        p2 = db.get(Projeto, "Proj_L1_B")
        if not p2:
            p2 = Projeto(nome_safe="Proj_L1_B", cliente_id=seed["cliente_l1_id"],
                         status="quente", loja_id=seed["loja1_id"])
            db.add(p2); db.flush()
        o2 = db.query(Orcamento).filter_by(projeto_id="Proj_L1_B").first()
        if not o2:
            o2 = Orcamento(projeto_id="Proj_L1_B", nome="Orçamento 1", ordem=1,
                           loja_id=seed["loja1_id"])
            db.add(o2); db.flush()
        if not db.query(Contrato).filter_by(projeto_nome="Proj_L1_B").first():
            db.add(Contrato(projeto_nome="Proj_L1_B", orcamento_id=o2.id,
                            loja_id=seed["loja1_id"]))
        p2.data_entrega = datetime(2026, 9, 14)          # janela 15..? sobrepõe 14–17
        pa = PoolAmbiente(projeto_id="Proj_L1_B", nome="Sala", nome_exibicao="Sala",
                          xml_path="/dev/null", ambientes_json="[]",
                          budget_total=800.0, order_total=300.0)
        db.add(pa); db.flush()
        db.add(OrcamentoAmbiente(orcamento_id=o2.id, pool_ambiente_id=pa.id))
        db.query(AtribuicaoAmbiente).filter_by(projeto_nome="Proj_L1_B").delete()
        db.commit()
        pa2_id = pa.id
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _d = c.post("/api/projetos/%s/atribuicoes" % nome,
                    {"papel": "montagem", "pool_ambiente_ids": ids, "funcionario_id": func_id})
    assert st == 200
    st, d = c.post("/api/projetos/Proj_L1_B/atribuicoes",
                   {"papel": "montagem", "pool_ambiente_ids": [pa2_id],
                    "funcionario_id": func_id})
    assert st == 200 and d["ok"], (st, d)
    assert d["aviso_conflito"] and "sobreposto" in d["aviso_conflito"]
    assert nome in d["aviso_conflito"]
    # GET também lista o conflito
    st, g = c.get("/api/agenda/montagem?de=2026-09-01&ate=2026-09-30")
    assert st == 200 and g["conflitos"]
    assert {x["projeto"] for x in g["conflitos"][0]["itens"]} == {nome, "Proj_L1_B"}
