"""Agenda da Loja — Fatia 2: motor de marcos (mod_agenda, puro), offsets default das subfases
do PE no cronograma e o endpoint agregador GET /api/agenda.

Spec: docs/superpowers/specs/agenda/2026-08-03-agenda-da-loja-design.md §3/§9/§10."""
from datetime import date, datetime

import mod_agenda
from database import CicloEtapa, Contrato, OrcamentoAmbiente, ParcelaAmbiente, ParcelaProjeto, \
    PoolAmbiente, Projeto


# ── mod_agenda puro ──────────────────────────────────────────────────────────────

def _proj(**kw):
    base = {"nome_safe": "P1", "cliente": "Cliente X", "val_liq": 3000.0,
            "previsao_medicao": None, "data_entrega": None, "etapas": {}, "fases": []}
    base.update(kw)
    return base


def test_marco_previsto_e_realizado():
    p = _proj(etapas={"9": {"prevista": datetime(2026, 9, 1), "concluida_em": None},
                      "10": {"prevista": datetime(2026, 9, 5),
                             "concluida_em": datetime(2026, 9, 4)}})
    ms = mod_agenda.marcos([p])
    assert [(m["etapa"], m["data"], m["realizado"]) for m in ms if m["etapa"] in ("9", "10")] == \
        [("9", date(2026, 9, 1), False), ("10", date(2026, 9, 4), True)]
    assert all(m["setor"] == "medicao" for m in ms if m["etapa"] in ("9", "10"))


def test_medicao_fallback_previsao_do_gate():
    p = _proj(previsao_medicao=datetime(2026, 9, 8), etapas={"10": {}})
    ms = mod_agenda.marcos([p])
    assert [(m["etapa"], m["data"]) for m in ms] == [("10", date(2026, 9, 8))]


def test_setores_das_subfases_pe_e_financeiro():
    p = _proj(etapas={c: {"prevista": datetime(2026, 9, 10)} for c in
                      ("11a", "11c", "11d", "11e", "8", "21")})
    por = {m["etapa"]: m["setor"] for m in mod_agenda.marcos([p])}
    assert por["11a"] == por["11c"] == por["11e"] == "pe"
    assert por["11d"] == por["8"] == por["21"] == "financeiro"
    titulos = {m["etapa"]: m["titulo"] for m in mod_agenda.marcos([p])}
    assert titulos["11a"] == "Planta de pontos de PE"
    assert titulos["11d"] == "Aprovação financeira II"


def test_entrega_por_fase_com_prioridade_e_retida():
    p = _proj(data_entrega=datetime(2026, 12, 1),
              etapas={"16": {"prevista": datetime(2026, 11, 28)}},
              fases=[
                  {"ordem": 1, "status": "aguardando", "val_liq": 2000.0,
                   "entrega_prevista": None, "card_prazo_entrega": date(2026, 11, 20),
                   "card_data_entrega": None},
                  {"ordem": 2, "status": "retido", "val_liq": 1000.0,
                   "entrega_prevista": date(2026, 12, 15), "card_prazo_entrega": None,
                   "card_data_entrega": None}])
    ms = [m for m in mod_agenda.marcos([p]) if m["etapa"] == "16"]
    assert [(m["fase"], m["data"], m["valor"], m["retida"]) for m in ms] == [
        (1, date(2026, 11, 20), 2000.0, False),     # card da expedição vence
        (2, date(2026, 12, 15), 1000.0, True)]      # previsão da fase; retida marcada


def test_entrega_sem_desmembramento_usa_projeto():
    p = _proj(data_entrega=datetime(2026, 12, 1))
    ms = mod_agenda.marcos([p])
    assert [(m["etapa"], m["data"], m["fase"], m["valor"]) for m in ms] == \
        [("16", date(2026, 12, 1), None, 3000.0)]


def test_filtros_periodo_e_setor():
    p = _proj(etapas={"9": {"prevista": datetime(2026, 9, 1)},
                      "13": {"prevista": datetime(2026, 10, 10)}})
    assert [m["etapa"] for m in mod_agenda.marcos([p], de=date(2026, 10, 1))] == ["13"]
    assert [m["etapa"] for m in mod_agenda.marcos([p], setor="medicao")] == ["9"]


# ── offsets default das subfases do PE no cronograma ─────────────────────────────

def test_cronograma_data_subfases_do_pe(app_db, seed):
    import mod_cronograma, mod_provisoes
    nome = seed["projeto_l1"]
    cfg = mod_provisoes.config_financeira_default()   # etapa 11: prazo 10 dias
    db = app_db.get_session()
    try:
        for e in db.query(CicloEtapa).filter_by(projeto_nome=nome).all():
            e.data_prevista_conclusao = None
        db.flush()
        mod_cronograma.gerar_cronograma_projeto(db, nome, cfg, datetime(2026, 9, 1))
        db.commit()
        prev = {e.etapa_codigo: e.data_prevista_conclusao
                for e in db.query(CicloEtapa).filter_by(projeto_nome=nome).all()}
        ini_11 = prev["10"]                             # fim da 10 = início da janela da 11
        dur = (prev["11"] - ini_11).days
        assert dur == 10
        assert (prev["11a"] - ini_11).days == 2         # 20%
        assert (prev["11b"] - ini_11).days == 4         # 40%
        assert (prev["11c"] - ini_11).days == 7         # 70%
        assert (prev["11d"] - ini_11).days == 8         # 85% → round(8.5) = 8
        assert prev["11e"] == prev["11"]                # 100%
        # edição manual NUNCA é sobrescrita ao regerar
        manual = datetime(2026, 10, 20)
        db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="11c") \
          .first().data_prevista_conclusao = manual
        db.flush()
        mod_cronograma.gerar_cronograma_projeto(db, nome, cfg, datetime(2026, 9, 1))
        db.commit()
        assert (db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="11c")
                  .first().data_prevista_conclusao == manual)
    finally:
        db.close()


# ── endpoint GET /api/agenda ─────────────────────────────────────────────────────

def _setup_projeto(app_db, seed):
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        db.query(ParcelaAmbiente).delete()
        db.query(ParcelaProjeto).filter_by(projeto_nome=nome).delete()
        p = db.get(Projeto, nome)
        p.data_entrega = datetime(2026, 12, 1)
        p.previsao_medicao = datetime(2026, 9, 8)
        for cod, dt in (("9", datetime(2026, 9, 5)), ("13", datetime(2026, 10, 10))):
            e = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo=cod).first()
            if not e:
                e = CicloEtapa(projeto_nome=nome, etapa_codigo=cod); db.add(e)
            e.data_prevista_conclusao = dt; e.status = "pendente"; e.concluido_em = None
        # estado completo, independente da ordem: outro teste gera cronograma p/ o projeto —
        # a 16 sem data prevista garante que a entrega caia no fallback (data do projeto)
        e16 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="16").first()
        if e16:
            e16.data_prevista_conclusao = None; e16.status = "pendente"; e16.concluido_em = None
        db.commit()
    finally:
        db.close()


def test_endpoint_agenda(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _setup_projeto(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31")
    assert st == 200 and d["ok"], (st, d)
    assert d["visao"] == "comercial"
    assert {s["id"] for s in d["setores"]} == {"medicao", "pe", "expedicao", "montagem", "financeiro"}
    meus = [m for m in d["marcos"] if m["projeto"] == nome]
    por_etapa = {m["etapa"]: m for m in meus}
    assert por_etapa["9"]["data"] == "2026-09-05" and por_etapa["9"]["setor"] == "medicao"
    assert por_etapa["13"]["setor"] == "expedicao"
    assert por_etapa["16"]["data"] == "2026-12-01"          # entrega: data do projeto
    assert por_etapa["9"]["cliente"] == "Cliente L1"
    # filtro de setor no servidor
    st, d2 = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31&setor=medicao")
    assert st == 200 and all(m["setor"] == "medicao" for m in d2["marcos"])
    # filtro de PROJETO (agenda específica / cronograma do projeto)
    st, d3 = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31&projeto=%s" % nome)
    assert st == 200 and d3["marcos"] and all(m["projeto"] == nome for m in d3["marcos"])
    st, d4 = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31&projeto=Nao_Existe")
    assert st == 200 and d4["marcos"] == []


def test_endpoint_agenda_isola_loja(app_db, seed, http_client_factory):
    _setup_projeto(app_db, seed)
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, d = c.get("/api/agenda?de=2026-01-01&ate=2027-12-31")
    assert st == 200 and d["ok"]
    assert all(m["projeto"] != seed["projeto_l1"] for m in d["marcos"])
