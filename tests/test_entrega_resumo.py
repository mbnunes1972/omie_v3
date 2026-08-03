"""Faixa de entrega do fichário (etapas 9→16): GET /api/projetos/<nome>/entrega-resumo.

Enquanto previsão → Projeto.data_entrega (global) ou CicloLogistico.prazo_entrega (por fase);
entregue → CicloLogistico.data_entrega (por fase / card projeto-wide) ou etapa 16 concluída
(global). Cada fase lista os ambientes (ParcelaAmbiente → PoolAmbiente); sem desmembramento,
uma "fase única" com os ambientes do orçamento contratado."""
from datetime import date, datetime

from database import (CicloEtapa, CicloLogistico, OrcamentoAmbiente, ParcelaAmbiente,
                      ParcelaProjeto, PoolAmbiente, Projeto)


def _mk_pool(app_db, seed, nomes):
    """Cria PoolAmbiente + vínculo no orçamento contratado do Proj_L1. Retorna ids."""
    db = app_db.get_session()
    try:
        ids = []
        for n in nomes:
            pa = PoolAmbiente(projeto_id=seed["projeto_l1"], nome=n, nome_exibicao=n,
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


def _set_data_entrega(app_db, nome, dt):
    db = app_db.get_session()
    try:
        db.get(Projeto, nome).data_entrega = dt
        db.commit()
    finally:
        db.close()


def test_sem_desmembramento_previsao(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _mk_pool(app_db, seed, ["Cozinha", "Suite"])
    _set_data_entrega(app_db, nome, datetime(2026, 9, 12))
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/projetos/%s/entrega-resumo" % nome)
    assert st == 200 and d["ok"], (st, d)
    assert d["desmembrado"] is False
    assert (d["previsao"] or "").startswith("2026-09-12")
    assert d["entregue_em"] is None
    assert len(d["fases"]) == 1
    f = d["fases"][0]
    assert sorted(f["ambientes"]) == ["Cozinha", "Suite"]
    assert (f["previsao"] or "").startswith("2026-09-12")
    assert f["entregue_em"] is None


def test_entregue_pela_etapa_16(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _mk_pool(app_db, seed, ["Cozinha"])
    _set_data_entrega(app_db, nome, datetime(2026, 9, 12))
    db = app_db.get_session()
    try:
        e16 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="16").first()
        if not e16:
            e16 = CicloEtapa(projeto_nome=nome, etapa_codigo="16"); db.add(e16)
        e16.status = "concluido"; e16.concluido_em = datetime(2026, 9, 15, 10, 0)
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/projetos/%s/entrega-resumo" % nome)
    assert st == 200 and d["ok"], (st, d)
    assert (d["entregue_em"] or "").startswith("2026-09-15")
    assert (d["fases"][0]["entregue_em"] or "").startswith("2026-09-15")


def test_desmembrado_previsao_e_entrega_por_fase(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids = _mk_pool(app_db, seed, ["Cozinha", "Suite", "Home"])
    _set_data_entrega(app_db, nome, datetime(2026, 9, 12))
    db = app_db.get_session()
    try:
        # estado completo, independente da ordem: etapa 16 aberta (outro teste a conclui)
        e16 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="16").first()
        if e16:
            e16.status = "pendente"; e16.concluido_em = None
        p1 = ParcelaProjeto(projeto_nome=nome, ordem=1, status="aguardando",
                            fracao_val_cont=0.5, val_cont_congelado=500.0,
                            orcamento_id=seed["orcamento_l1_id"])
        p2 = ParcelaProjeto(projeto_nome=nome, ordem=2, status="retido",
                            fracao_val_cont=0.5, val_cont_congelado=500.0,
                            orcamento_id=seed["orcamento_l1_id"])
        db.add_all([p1, p2]); db.flush()
        db.add(ParcelaAmbiente(parcela_id=p1.id, pool_ambiente_id=ids[0]))
        db.add(ParcelaAmbiente(parcela_id=p1.id, pool_ambiente_id=ids[1]))
        db.add(ParcelaAmbiente(parcela_id=p2.id, pool_ambiente_id=ids[2]))
        # fase 1 tem card de expedição ENTREGUE; fase 2 não tem card → cai na previsão global
        db.add(CicloLogistico(projeto_nome=nome, parcela_id=p1.id, status_atual="Entregue",
                              prazo_entrega=date(2026, 8, 30), data_entrega=date(2026, 9, 1)))
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/projetos/%s/entrega-resumo" % nome)
    assert st == 200 and d["ok"], (st, d)
    assert d["desmembrado"] is True
    assert len(d["fases"]) == 2
    f1, f2 = d["fases"]
    assert f1["ordem"] == 1 and (f1["entregue_em"] or "").startswith("2026-09-01")
    assert sorted(f1["ambientes"]) == ["Cozinha", "Suite"]
    assert f2["ordem"] == 2 and f2["status"] == "retido"
    assert f2["entregue_em"] is None
    assert (f2["previsao"] or "").startswith("2026-09-12")   # fallback: data global
    assert f2["ambientes"] == ["Home"]
    # global segue não entregue (etapa 16 aberta)
    assert d["entregue_em"] is None


def test_tenancy_projeto_de_outra_loja_404(app_db, seed, http_client_factory):
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, d = c.get("/api/projetos/%s/entrega-resumo" % seed["projeto_l1"])
    assert st == 404, (st, d)
