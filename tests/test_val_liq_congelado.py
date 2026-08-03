"""Agenda Fatia 1 — `ParcelaProjeto.val_liq_congelado` (spec 2026-08-03 §4).

Val_Liq (VAVO − Cust_Ad, base das comissões e da Agenda) é congelado POR FASE no mesmo
instante do Val_Cont, em todos os caminhos (desmembramento, sucessivo, retenção com split,
liberação em ondas). Invariante: Σ val_liq_congelado == Val_Liq ao centavo, sempre.

Cenário: 3 ambientes de budget 1000 + comissão de arquiteto 10% repassada
(incluir_custos) → VAVA = 1111,11 cada (VAVO 3333,33), Val_Liq = 3000,00
(liq por ambiente = exatamente 1000,00 — números redondos de propósito)."""
import json

from database import (CicloLogistico, OrcamentoAmbiente, ParcelaAmbiente, ParcelaProjeto,
                      PoolAmbiente, Projeto, RetencaoObra, SinalRetido)


def _setup(app_db, seed, nomes=("Cozinha", "Suite", "Home")):
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    try:
        db.query(RetencaoObra).filter_by(projeto_nome=nome).delete()
        db.query(SinalRetido).filter_by(projeto_nome=nome).delete()
        db.query(CicloLogistico).filter_by(projeto_nome=nome).delete()
        db.query(ParcelaAmbiente).delete()
        db.query(ParcelaProjeto).filter_by(projeto_nome=nome).delete()
        db.query(OrcamentoAmbiente).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
        for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome).all():
            db.delete(pa)
        db.flush()
        db.get(Projeto, nome).parametros_json = json.dumps({
            "incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10.0})
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


def _soma_liq(app_db, nome):
    db = app_db.get_session()
    try:
        fases = db.query(ParcelaProjeto).filter_by(projeto_nome=nome).all()
        assert all(f.val_liq_congelado is not None for f in fases), "fase sem val_liq_congelado"
        return round(sum(f.val_liq_congelado for f in fases), 2), fases
    finally:
        db.close()


def test_desmembramento_congela_val_liq(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids = _setup(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/parcelas" % nome,
                   {"parcelas": [[ids[0], ids[1]], [ids[2]]]})
    assert st == 200 and d["ok"], (st, d)
    soma, fases = _soma_liq(app_db, nome)
    assert soma == 3000.00                       # Val_Liq exato (≠ Val_Cont 3333,33)
    por_ordem = sorted(fases, key=lambda f: f.ordem)
    assert por_ordem[0].val_liq_congelado == 2000.00
    assert por_ordem[1].val_liq_congelado == 1000.00
    # exposto no GET /parcelas, ao lado do val_cont_congelado
    st, lst = c.get("/api/projetos/%s/parcelas" % nome)
    assert st == 200
    assert [f["val_liq_congelado"] for f in lst["parcelas"]] == [2000.00, 1000.00]
    assert round(lst["parcelas"][0]["val_cont_congelado"], 2) != 2000.00   # Cont ≠ Liq de fato


def test_sucessivo_preserva_val_liq_da_mae(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids = _setup(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/projetos/%s/parcelas" % nome,
                   {"parcelas": [[ids[0], ids[1]], [ids[2]]]})
    assert st == 200
    db = app_db.get_session()
    try:
        mae = (db.query(ParcelaProjeto).filter_by(projeto_nome=nome)
                 .order_by(ParcelaProjeto.ordem.asc()).first())
        mae_id, mae_liq = mae.id, mae.val_liq_congelado
    finally:
        db.close()
    st, d = c.post("/api/projetos/%s/parcelas/%d/desmembrar" % (nome, mae_id),
                   {"parcelas": [[ids[0]], [ids[1]]]})
    assert st == 200 and d["ok"], (st, d)
    soma, fases = _soma_liq(app_db, nome)
    assert soma == 3000.00
    novas = [f for f in fases if f.id != mae_id and f.val_liq_congelado is not None
             and f.ordem <= 2]
    assert round(sum(f.val_liq_congelado for f in novas), 2) == round(mae_liq, 2)


def test_retencao_com_split_e_liberacao_em_ondas(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids = _setup(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # retenção direta em projeto NÃO desmembrado (cria [segue, retida]) — congela liq nos dois
    st, d = c.post("/api/projetos/%s/retencoes" % nome,
                   {"ambientes": [ids[1], ids[2]], "motivo_tipo": "Atraso da Obra", "etapa_codigo": "10"})
    assert st == 200 and d["ok"], (st, d)
    soma, _ = _soma_liq(app_db, nome)
    assert soma == 3000.00
    # liberação em ONDAS: libera só a Suite → split da fase retida; liq acompanha proporção
    st, d = c.post("/api/projetos/%s/retido/liberar" % nome, {"pool_ambiente_ids": [ids[1]]})
    assert st == 200 and d["ok"], (st, d)
    soma, fases = _soma_liq(app_db, nome)
    assert soma == 3000.00
    retidas = [f for f in fases if f.status == "retido"]
    assert len(retidas) == 1 and retidas[0].val_liq_congelado == 1000.00
    # segunda retenção (agora desmembrado, com SPLIT da fase que segue) preserva a soma
    st, d = c.post("/api/projetos/%s/retencoes" % nome,
                   {"ambientes": [ids[0]], "motivo_tipo": "Outros", "etapa_codigo": "11"})
    assert st == 200 and d["ok"], (st, d)
    soma, _ = _soma_liq(app_db, nome)
    assert soma == 3000.00


def test_backfill_preenche_fase_legada(app_db, seed, http_client_factory):
    import main as m
    nome = seed["projeto_l1"]
    ids = _setup(app_db, seed)
    db = app_db.get_session()
    try:
        p = ParcelaProjeto(projeto_nome=nome, ordem=1, status="aguardando",
                           fracao_val_cont=1.0, val_cont_congelado=3333.33,
                           orcamento_id=seed["orcamento_l1_id"], val_liq_congelado=None)
        db.add(p); db.flush()
        for a in ids:
            db.add(ParcelaAmbiente(parcela_id=p.id, pool_ambiente_id=a))
        db.commit()
        n = m._backfill_val_liq_fases(db)
        assert n == 1
        db.expire_all()
        assert db.get(ParcelaProjeto, p.id).val_liq_congelado == 3000.00
        assert m._backfill_val_liq_fases(db) == 0   # idempotente
    finally:
        db.close()
