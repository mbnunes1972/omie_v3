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


def test_marco_inclui_responsavel():
    """Coluna "Responsável" da Agenda (2026-08-24, pedido do usuário). mod_agenda é PURO — só
    repassa o que o endpoint já resolveu em etapas[cod]["responsavel"]; sem override, "" (nunca
    inventa um default aqui, ver comentário em main._agenda_dados_projetos)."""
    p = _proj(etapas={
        "9":  {"prevista": datetime(2026, 9, 1), "concluida_em": None, "responsavel": "Fulano"},
        "10": {"prevista": datetime(2026, 9, 5), "concluida_em": None},
    })
    por = {m["etapa"]: m["responsavel"] for m in mod_agenda.marcos([p])}
    assert por["9"] == "Fulano"
    assert por["10"] == ""


def test_marco_entrega_por_fase_inclui_responsavel():
    p = _proj(etapas={"16": {"prevista": None, "concluida_em": None, "responsavel": "Ciclana"}},
              fases=[{"ordem": 1, "status": None, "val_liq": 100.0,
                      "entrega_prevista": datetime(2026, 9, 20),
                      "card_prazo_entrega": None, "card_data_entrega": None,
                      "responsavel": "Ciclana"}])
    ms = mod_agenda.marcos([p])
    assert ms and ms[0]["responsavel"] == "Ciclana"


def test_medicao_fallback_previsao_do_gate():
    p = _proj(previsao_medicao=datetime(2026, 9, 8), etapas={"10": {}})
    ms = mod_agenda.marcos([p])
    assert [(m["etapa"], m["data"]) for m in ms] == [("10", date(2026, 9, 8))]


def test_setores_das_subfases_pe():
    p = _proj(etapas={c: {"prevista": datetime(2026, 9, 10)} for c in
                      ("11a", "11c", "11e")})
    por = {m["etapa"]: m["setor"] for m in mod_agenda.marcos([p])}
    assert por["11a"] == por["11c"] == por["11e"] == "pe"
    titulos = {m["etapa"]: m["titulo"] for m in mod_agenda.marcos([p])}
    assert titulos["11a"] == "Planta de pontos de PE"


def test_financeiro_nao_gera_mais_marco():
    """2026-08-07 (pedido do usuário): Financeiro saiu da Agenda — a agenda financeira corre
    separada. 8/11d/21 não geram marco nenhum (saíram de ETAPAS_MARCO)."""
    p = _proj(etapas={c: {"prevista": datetime(2026, 9, 10)} for c in ("8", "11d", "21")})
    assert mod_agenda.marcos([p]) == []
    assert "financeiro" not in dict(mod_agenda.SETORES)


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


def test_cadeia_canonica_data_entrega_projeto_vence_prevista_16():
    # Vera 🟠2: a ÂNCORA formal (Projeto.data_entrega) prevalece sobre o progressivo da 16;
    # a prevista da 16 é só último recurso — MESMA cadeia da faixa de entrega (entrega-resumo).
    p = _proj(data_entrega=datetime(2026, 12, 1),
              etapas={"16": {"prevista": datetime(2026, 11, 25)}})
    ms = [m for m in mod_agenda.marcos([p]) if m["etapa"] == "16"]
    assert ms[0]["data"] == date(2026, 12, 1)
    p2 = _proj(data_entrega=None, etapas={"16": {"prevista": datetime(2026, 11, 25)}})
    ms2 = [m for m in mod_agenda.marcos([p2]) if m["etapa"] == "16"]
    assert ms2[0]["data"] == date(2026, 11, 25)   # sem âncora → último recurso


def test_marcos_assistencia_previsto_e_realizado():
    casos = [
        {"projeto_nome": "P1", "data_inicio": date(2026, 9, 10), "status": "aberto",
         "realizado_em": None, "valor": 300.0, "titulo": "Erro de montagem"},
        {"projeto_nome": "P1", "data_inicio": date(2026, 9, 1), "status": "realizado",
         "realizado_em": datetime(2026, 9, 3), "valor": 500.0, "titulo": "Defeito de fabricação"},
        {"projeto_nome": None, "data_inicio": None, "status": "aberto",
         "realizado_em": None, "valor": 100.0, "titulo": "Sem data — fora"},
    ]
    ms = mod_agenda.marcos_assistencia(casos)
    assert len(ms) == 2
    assert all(m["setor"] == "assistencia" for m in ms)
    por_titulo = {m["titulo"]: m for m in ms}
    assert por_titulo["Erro de montagem"]["data"] == date(2026, 9, 10)
    assert por_titulo["Erro de montagem"]["realizado"] is False
    assert por_titulo["Defeito de fabricação"]["data"] == date(2026, 9, 3)   # realizado_em, não previsto
    assert por_titulo["Defeito de fabricação"]["realizado"] is True


def test_marcos_assistencia_avulso_projeto_none():
    casos = [{"projeto_nome": None, "data_inicio": date(2026, 9, 5), "status": "aberto",
             "realizado_em": None, "valor": 200.0, "titulo": "Concessão"}]
    ms = mod_agenda.marcos_assistencia(casos)
    assert len(ms) == 1 and ms[0]["projeto"] is None


def test_marcos_assistencia_filtro_periodo():
    casos = [{"projeto_nome": "P1", "data_inicio": date(2026, 9, 1), "status": "aberto",
             "realizado_em": None, "valor": 10.0, "titulo": "A"},
            {"projeto_nome": "P1", "data_inicio": date(2026, 10, 1), "status": "aberto",
             "realizado_em": None, "valor": 20.0, "titulo": "B"}]
    assert [m["titulo"] for m in mod_agenda.marcos_assistencia(casos, de=date(2026, 9, 15))] == ["B"]


def test_filtros_periodo_e_setor():
    p = _proj(etapas={"9": {"prevista": datetime(2026, 9, 1)},
                      "13": {"prevista": datetime(2026, 10, 10)}})
    assert [m["etapa"] for m in mod_agenda.marcos([p], de=date(2026, 10, 1))] == ["13"]
    assert [m["etapa"] for m in mod_agenda.marcos([p], setor="medicao")] == ["9"]


# ── Fatia 3: cargas (catálogo de itens com valor, spec §5 rev 2) ─────────────────

def test_carga_pe_espalhada_em_dias_uteis():
    # 10 concluída sex 04/09 → PE começa seg 07/09; 11 prevista qui 10/09 → 4 dias úteis
    p = _proj(etapas={"10": {"concluida_em": datetime(2026, 9, 4)},
                      "11": {"prevista": datetime(2026, 9, 10)}})
    pe = [c for c in mod_agenda.cargas([p]) if c["item"] == "pe"]
    assert [c["data"] for c in pe] == [date(2026, 9, 7), date(2026, 9, 8),
                                       date(2026, 9, 9), date(2026, 9, 10)]
    assert round(sum(c["valor"] for c in pe), 2) == 3000.0
    assert pe[0]["valor"] == 750.0


def test_carga_fase_retida_fica_fora():
    p = _proj(etapas={"10": {"concluida_em": datetime(2026, 9, 4)},
                      "11": {"prevista": datetime(2026, 9, 10)}},
              fases=[{"ordem": 1, "status": "retido", "val_liq": 3000.0,
                      "entrega_prevista": None, "card_prazo_entrega": None,
                      "card_data_entrega": None}])
    assert mod_agenda.cargas([p]) == []


def test_producao_e_entrega_sao_marcos_valorados():
    p = _proj(etapas={"13": {"prevista": datetime(2026, 9, 29)}},
              data_entrega=datetime(2026, 10, 2))
    cs = mod_agenda.cargas([p])
    por = {c["item"]: c for c in cs}
    assert por["producao"]["data"] == date(2026, 9, 29) and por["producao"]["valor"] == 3000.0
    assert por["entrega"]["data"] == date(2026, 10, 2) and por["entrega"]["valor"] == 3000.0


def test_carga_montagem_da_entrega_ate_a_17():
    # entrega sex 11/09 → montagem começa seg 14/09; 17 prevista qui 17/09 → 4 dias úteis
    p = _proj(data_entrega=datetime(2026, 9, 11),
              etapas={"17": {"prevista": datetime(2026, 9, 17)}})
    mo = [c for c in mod_agenda.cargas([p]) if c["item"] == "montagem"]
    assert [c["data"] for c in mo] == [date(2026, 9, 14), date(2026, 9, 15),
                                       date(2026, 9, 16), date(2026, 9, 17)]
    assert round(sum(c["valor"] for c in mo), 2) == 3000.0


def test_carga_filtro_de_periodo():
    p = _proj(etapas={"13": {"prevista": datetime(2026, 9, 29)}},
              data_entrega=datetime(2026, 10, 2))
    cs = mod_agenda.cargas([p], de=date(2026, 10, 1))
    assert {c["item"] for c in cs} == {"entrega", "montagem"}


# ── Fatia 4: capacidade (duplas de montagem + ocupação do PE) ────────────────────

def test_capacidade_duplas_e_ocupacao_pe():
    cargas = [
        {"data": date(2026, 9, 14), "item": "montagem", "valor": 9000.0},
        {"data": date(2026, 9, 14), "item": "montagem", "valor": 6000.0},   # Σ 15k → 3 duplas
        {"data": date(2026, 9, 14), "item": "pe", "valor": 10000.0},        # 50% de 20k
        {"data": date(2026, 9, 15), "item": "montagem", "valor": 7000.0},   # exato → 1 dupla
        {"data": date(2026, 9, 16), "item": "pe", "valor": 30000.0},        # 150% → estouro
        {"data": date(2026, 9, 16), "item": "entrega", "valor": 999.0},     # ignorado
    ]
    cfg = {"produtividade_montagem_rs_dupla_dia": 7000.0, "produtividade_pe_rs_dia": 20000.0}
    cap = mod_agenda.capacidade(cargas, cfg)
    assert [(c["data"], c["duplas"], c["pe_pct"]) for c in cap] == [
        (date(2026, 9, 14), 3, 50.0),
        (date(2026, 9, 15), 1, 0.0),
        (date(2026, 9, 16), 0, 150.0)]
    assert cap[0]["montagem"] == 15000.0


def test_capacidade_vazia_sem_cargas():
    assert mod_agenda.capacidade([], {}) == []


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


def test_backfill_subfases_pe_em_cronograma_legado(app_db, seed):
    import mod_cronograma
    nome = seed["projeto_l2"]          # projeto sem interferência dos outros testes
    db = app_db.get_session()
    try:
        for cod in ("10", "11", "11a", "11b", "11c", "11d", "11e"):
            e = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo=cod).first()
            if e:
                db.delete(e)
        db.flush()
        db.add(CicloEtapa(projeto_nome=nome, etapa_codigo="10",
                          data_prevista_conclusao=datetime(2026, 9, 1)))
        db.add(CicloEtapa(projeto_nome=nome, etapa_codigo="11",
                          data_prevista_conclusao=datetime(2026, 9, 11)))   # janela de 10 dias
        db.commit()
        n = mod_cronograma.backfill_subfases_pe(db)
        db.commit()
        assert n >= 5
        prev = {e.etapa_codigo: e.data_prevista_conclusao
                for e in db.query(CicloEtapa).filter_by(projeto_nome=nome).all()}
        assert prev["11a"] == datetime(2026, 9, 3)    # 20% de 10 dias
        assert prev["11e"] == datetime(2026, 9, 11)   # 100%
        assert mod_cronograma.backfill_subfases_pe(db) == 0 or \
            all(prev[c] is not None for c in ("11a", "11b", "11c", "11d", "11e"))  # idempotente p/ ESTE projeto
    finally:
        db.close()


# ── endpoint GET /api/agenda ─────────────────────────────────────────────────────

def _setup_projeto(app_db, seed):
    from database import Orcamento
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        db.query(ParcelaAmbiente).delete()
        db.query(ParcelaProjeto).filter_by(projeto_nome=nome).delete()
        db.get(Orcamento, seed["orcamento_l1_id"]).valor_liquido = 3000.0   # Val_Liq do projeto
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
    assert {s["id"] for s in d["setores"]} == {"medicao", "pe", "expedicao", "montagem", "assistencia"}
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
    # Fatia 3: CARGAS no payload (catálogo de itens) — entrega valorada na data do projeto
    assert {i["id"] for i in d["itens"]} == {"pe", "conferencia", "producao", "montagem", "entrega"}
    entregas = [cg for cg in d["cargas"] if cg["item"] == "entrega" and cg["projeto"] == nome]
    assert entregas and entregas[0]["data"] == "2026-12-01" and entregas[0]["valor"] > 0
    mont = [cg for cg in d["cargas"] if cg["item"] == "montagem" and cg["projeto"] == nome]
    assert mont and mont[0]["data"] > "2026-12-01"    # montagem começa após a entrega
    # Fatia 4: CAPACIDADE no payload (dias com carga de montagem/PE → duplas/ocupação)
    assert d["capacidade_cfg"]["produtividade_montagem"] == 7000.0
    dias_mont = {cg["data"] for cg in mont}
    cap_mont = [cp for cp in d["capacidade"] if cp["data"] in dias_mont]
    assert cap_mont and all(cp["duplas"] >= 1 for cp in cap_mont)


def test_endpoint_agenda_inclui_assistencia(app_db, seed, http_client_factory):
    """2026-08-07: caso de Assistência (com projeto e avulso) aparece no /api/agenda, setor
    'assistencia'; filtro server-side por setor funciona; avulso (sem projeto) também entra."""
    import mod_assistencias as ma
    nome = seed["projeto_l1"]
    _setup_projeto(app_db, seed)
    db = app_db.get_session()
    try:
        caso_proj = ma.criar_caso(db, seed["loja1_id"], nome, "montagem", "erro_montagem",
                                  "porta empenou", 300.0, None, data_inicio=date(2026, 9, 12),
                                  data_fim=date(2026, 9, 12))
        caso_avulso = ma.criar_caso(db, seed["loja1_id"], None, "pos_conclusao", "defeito_fabricacao",
                                    "cliente ligou", 150.0, None, classificacao_avulsa="garantia",
                                    data_inicio=date(2026, 9, 20), data_fim=date(2026, 9, 20))
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31")
    assert st == 200 and d["ok"]
    assist = [m for m in d["marcos"] if m["setor"] == "assistencia"]
    assert {m["projeto"] for m in assist} == {nome, None}
    com_proj = next(m for m in assist if m["projeto"] == nome)
    assert com_proj["data"] == "2026-09-12" and com_proj["valor"] == 300.0
    avulso = next(m for m in assist if m["projeto"] is None)
    assert avulso["data"] == "2026-09-20" and avulso["valor"] == 150.0
    # filtro de setor no servidor
    st2, d2 = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31&setor=assistencia")
    assert st2 == 200 and d2["marcos"] and all(m["setor"] == "assistencia" for m in d2["marcos"])


def test_endpoint_agenda_meus_filtra_por_posse_ou_atribuicao(app_db, seed, http_client_factory):
    """Botão "Minha Agenda" (2026-08-24, pedido do usuário): meus=1 força escopo pessoal (criei
    OU estou atribuído) pra QUALQUER nível — inclusive master, que por padrão vê tudo."""
    nome = seed["projeto_l1"]
    _setup_projeto(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # sem meus: master (padrão) vê tudo, inclusive projeto que não criou
    st, d = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31")
    assert st == 200 and any(m["projeto"] == nome for m in d["marcos"])
    # meus=1, sem posse nem atribuição: o projeto some (marcos de OUTROS testes do módulo, como
    # a assistência avulsa de test_endpoint_agenda_inclui_assistencia, continuam — app_db é
    # scope="module" — mas "avulso sem posse" é uma exceção deliberada, não afeta este projeto)
    st2, d2 = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31&meus=1")
    assert st2 == 200 and not any(m["projeto"] == nome for m in d2["marcos"])
    # vira o criador do projeto → meus=1 volta a mostrar
    db = app_db.get_session()
    try:
        uid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        db.get(app_db.Projeto, nome).criado_por_id = uid
        db.commit()
    finally:
        db.close()
    st3, d3 = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31&meus=1")
    assert st3 == 200 and any(m["projeto"] == nome for m in d3["marcos"])


def test_endpoint_agenda_responsavel_resolve_nome(app_db, seed, http_client_factory):
    """Responsável (2026-08-24): override explícito em CicloEtapa.responsavel_funcionario_id
    resolve pro nome do Funcionário no payload do /api/agenda; sem override, "" ."""
    nome = seed["projeto_l1"]
    _setup_projeto(app_db, seed)
    db = app_db.get_session()
    try:
        func = app_db.Funcionario(nome="Fulano de Tal", loja_id=seed["loja1_id"])
        db.add(func); db.flush()
        e9 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="9").first()
        e9.responsavel_funcionario_id = func.id
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/agenda?de=2026-09-01&ate=2026-12-31")
    assert st == 200
    por_etapa = {m["etapa"]: m for m in d["marcos"] if m["projeto"] == nome}
    assert por_etapa["9"]["responsavel"] == "Fulano de Tal"
    assert por_etapa["13"]["responsavel"] == ""


def test_endpoint_agenda_isola_loja(app_db, seed, http_client_factory):
    _setup_projeto(app_db, seed)
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, d = c.get("/api/agenda?de=2026-01-01&ate=2027-12-31")
    assert st == 200 and d["ok"]
    assert all(m["projeto"] != seed["projeto_l1"] for m in d["marcos"])
