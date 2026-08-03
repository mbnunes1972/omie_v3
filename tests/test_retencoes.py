"""Retenção por obra RECORRENTE (decisão 2026-08-02): pode ser acionada da Solicitação de
Medição à Montagem, várias vezes; cada evento registra quando/etapa do ciclo/ambientes/motivo e
a DATA PREVISTA DE LIBERAÇÃO (RetencaoObra). POST /api/projetos/<n>/retencoes retém direto
(cria fases ou faz split preservando congelados); GET lista o histórico; o liberar existente
estampa `liberado_em` quando todos os ambientes do evento saem de fase retida. O desmembramento
também aceita `previsoes` (liberação p/ prosseguimento + nova previsão de entrega por fase)."""
from datetime import date, datetime

from database import (CicloLogistico, OrcamentoAmbiente, ParcelaAmbiente, ParcelaProjeto,
                      PoolAmbiente, Projeto, RetencaoObra, SinalRetido)


def _setup_pool(app_db, seed, nomes=("Cozinha", "Suite", "Home")):
    """Estado limpo e completo: pool novo vinculado ao orçamento contratado do Proj_L1."""
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        db.query(RetencaoObra).filter_by(projeto_nome=nome).delete()
        db.query(SinalRetido).filter_by(projeto_nome=nome).delete()
        db.query(CicloLogistico).filter_by(projeto_nome=nome).delete()   # FK → parcela_projeto
        db.query(ParcelaAmbiente).delete()
        db.query(ParcelaProjeto).filter_by(projeto_nome=nome).delete()
        db.query(OrcamentoAmbiente).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
        for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome).all():
            db.delete(pa)
        db.flush()
        ids = []
        for n in nomes:
            pa = PoolAmbiente(projeto_id=nome, nome=n, nome_exibicao=n,
                              xml_path="/dev/null", ambientes_json="[]",
                              budget_total=1000.0, order_total=400.0)
            db.add(pa); db.flush()
            db.add(OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                     pool_ambiente_id=pa.id))
            ids.append(pa.id)
        db.commit()
        return ids
    finally:
        db.close()


def test_reter_direto_e_registro(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids = _setup_pool(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/retencoes" % nome,
                   {"ambientes": [ids[2]], "motivo": "Obra sem contrapiso",
                    "liberacao_prevista": "2026-09-20", "etapa_codigo": "10"})
    assert st == 200 and d["ok"], (st, d)
    st, lst = c.get("/api/projetos/%s/parcelas" % nome)
    fases = lst["parcelas"]
    assert len(fases) == 2
    assert fases[0]["status"] == "aguardando" and len(fases[0]["ambientes"]) == 2
    assert fases[1]["status"] == "retido" and fases[1]["ambientes"][0]["nome"] == "Home"
    st, h = c.get("/api/projetos/%s/retencoes" % nome)
    assert st == 200 and len(h["retencoes"]) == 1
    reg = h["retencoes"][0]
    assert reg["etapa_codigo"] == "10"
    assert reg["motivo"] == "Obra sem contrapiso"
    assert reg["liberacao_prevista"] == "2026-09-20"
    assert reg["liberado_em"] is None
    assert reg["criado_em"]
    assert [a["nome"] for a in reg["ambientes"]] == ["Home"]


def test_segunda_retencao_faz_split_preservando_congelados(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids = _setup_pool(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/projetos/%s/retencoes" % nome,
                   {"ambientes": [ids[2]], "motivo": "1a", "etapa_codigo": "10"})
    assert st == 200
    st, lst = c.get("/api/projetos/%s/parcelas" % nome)
    val_fase1 = lst["parcelas"][0]["val_cont_congelado"]
    # 2ª retenção, no PE: retém a Cozinha, que está na fase 1 junto com a Suite → SPLIT
    st, d = c.post("/api/projetos/%s/retencoes" % nome,
                   {"ambientes": [ids[0]], "motivo": "Parede da cozinha atrasou",
                    "liberacao_prevista": "2026-10-05", "etapa_codigo": "11"})
    assert st == 200 and d["ok"], (st, d)
    st, lst = c.get("/api/projetos/%s/parcelas" % nome)
    fases = lst["parcelas"]
    assert len(fases) == 3
    por_amb = {f["ambientes"][0]["nome"]: f for f in fases if len(f["ambientes"]) == 1}
    assert por_amb["Cozinha"]["status"] == "retido"
    # congelados preservados: fase que seguiu + nova retida = fase 1 original
    soma = round(por_amb["Suite"]["val_cont_congelado"]
                 + por_amb["Cozinha"]["val_cont_congelado"], 2)
    assert soma == round(val_fase1, 2)
    st, h = c.get("/api/projetos/%s/retencoes" % nome)
    assert len(h["retencoes"]) == 2
    assert h["retencoes"][0]["etapa_codigo"] == "11"   # mais recente primeiro


def test_reter_ja_retido_e_fase_em_expedicao(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids = _setup_pool(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/projetos/%s/retencoes" % nome,
                   {"ambientes": [ids[2]], "etapa_codigo": "9"})
    assert st == 200
    st, d = c.post("/api/projetos/%s/retencoes" % nome, {"ambientes": [ids[2]]})
    assert st == 409 and "retido" in d["erro"].lower()
    # fase 1 (Cozinha+Suite) entra em expedição → reter Cozinha bloqueia
    db = app_db.get_session()
    try:
        f1 = (db.query(ParcelaProjeto).filter_by(projeto_nome=nome, status="aguardando")
                .order_by(ParcelaProjeto.ordem.asc()).first())
        db.add(CicloLogistico(projeto_nome=nome, parcela_id=f1.id, status_atual="Em Produção"))
        db.commit()
    finally:
        db.close()
    st, d = c.post("/api/projetos/%s/retencoes" % nome, {"ambientes": [ids[0]]})
    assert st == 409 and "expedi" in d["erro"].lower()


def test_liberar_estampa_registro(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids = _setup_pool(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/projetos/%s/retencoes" % nome,
                   {"ambientes": [ids[1], ids[2]], "liberacao_prevista": "2026-09-20",
                    "etapa_codigo": "10"})
    assert st == 200
    # onda 1: libera só a Suite → registro segue aberto
    st, d = c.post("/api/projetos/%s/retido/liberar" % nome, {"pool_ambiente_ids": [ids[1]]})
    assert st == 200 and d["ok"], (st, d)
    st, h = c.get("/api/projetos/%s/retencoes" % nome)
    assert h["retencoes"][0]["liberado_em"] is None
    # onda 2: libera o Home → registro fecha
    st, d = c.post("/api/projetos/%s/retido/liberar" % nome, {"pool_ambiente_ids": [ids[2]]})
    assert st == 200 and d["ok"], (st, d)
    st, h = c.get("/api/projetos/%s/retencoes" % nome)
    assert h["retencoes"][0]["liberado_em"] is not None


def test_previsoes_no_desmembramento_e_entrega_resumo(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids = _setup_pool(app_db, seed)
    db = app_db.get_session()
    try:
        db.get(Projeto, nome).data_entrega = datetime(2026, 12, 1)
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/parcelas" % nome,
                   {"parcelas": [[ids[0], ids[1]], [ids[2]]],
                    "previsoes": [{"liberacao": "2026-09-01", "entrega": "2026-10-15"},
                                  {"entrega": "2026-11-20"}]})
    assert st == 200 and d["ok"], (st, d)
    db = app_db.get_session()
    try:
        fases = (db.query(ParcelaProjeto).filter_by(projeto_nome=nome)
                   .order_by(ParcelaProjeto.ordem.asc()).all())
        assert fases[0].liberacao_prevista == date(2026, 9, 1)
        assert fases[0].entrega_prevista == date(2026, 10, 15)
        assert fases[1].liberacao_prevista is None
        assert fases[1].entrega_prevista == date(2026, 11, 20)
    finally:
        db.close()
    # entrega-resumo prefere a previsão da FASE à global
    st, r = c.get("/api/projetos/%s/entrega-resumo" % nome)
    assert st == 200 and r["ok"]
    assert (r["fases"][0]["previsao"] or "").startswith("2026-10-15")
    assert (r["fases"][1]["previsao"] or "").startswith("2026-11-20")
    assert (r["previsao"] or "").startswith("2026-12-01")
