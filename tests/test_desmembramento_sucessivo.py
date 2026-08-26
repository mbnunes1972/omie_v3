"""Desmembramento SUCESSIVO (decisão do usuário, 2026-08-02): uma fase já criada (ex.: na
Medição) pode ser dividida de novo (ex.: no PE) em ≥2 novas fases.

POST /api/projetos/<nome>/parcelas/<id>/desmembrar — a partição vale sobre os ambientes DA
fase; os congelados da mãe são preservados exatamente (última nova fase absorve o resíduo);
a mãe sai e as fases são renumeradas 1..N. Fase liquidada ou já em expedição não desmembra."""
from datetime import date

from database import (CicloLogistico, ConciliacaoPeFase, OrcamentoAmbiente, ParcelaAmbiente,
                       ParcelaProjeto, PoolAmbiente)

import mod_parcelas


# ── unidade: mod_parcelas.desmembrar_fase ────────────────────────────────────────

def test_desmembrar_fase_preserva_congelados():
    ok, erro, novas = mod_parcelas.desmembrar_fase(
        [1, 2, 3], [[1], [2, 3]], 1000.01, 0.5, {1: 300.0, 2: 300.0, 3: 400.0})
    assert ok and erro is None
    assert [n["val_cont_congelado"] for n in novas] == [300.0, 700.01]   # última absorve
    assert abs(sum(n["fracao_val_cont"] for n in novas) - 0.5) < 1e-9


def test_desmembrar_fase_valores_zerados_divide_igual():
    ok, _, novas = mod_parcelas.desmembrar_fase([1, 2], [[1], [2]], 100.0, 0.4, {})
    assert ok
    assert [n["val_cont_congelado"] for n in novas] == [50.0, 50.0]


def test_desmembrar_fase_guardas():
    ok, erro, _ = mod_parcelas.desmembrar_fase([1, 2], [[1, 2]], 100.0, 0.4, {})
    assert not ok and "2" in erro                       # exige ≥2 grupos
    ok, erro, _ = mod_parcelas.desmembrar_fase([1, 2], [[1], [99]], 100.0, 0.4, {})
    assert not ok                                       # ambiente fora da fase


# ── endpoint ─────────────────────────────────────────────────────────────────────

def _setup_fases(app_db, seed, nomes=("Cozinha", "Suite", "Home")):
    """Pool + vínculo no orçamento contratado + 2 fases congeladas no Proj_L1."""
    db = app_db.get_session()
    try:
        db.query(ParcelaAmbiente).delete()
        db.query(CicloLogistico).filter_by(projeto_nome=seed["projeto_l1"]).delete()
        # ConciliacaoPeFase referencia parcela_id — precisa sair ANTES de apagar ParcelaProjeto,
        # senão a fixture (app_db module-scoped) quebra num teste que deixou uma decisão de AF2
        # presa (mesma classe de FK que o fix da Sessão 218 trata no endpoint).
        db.query(ConciliacaoPeFase).filter_by(projeto_nome=seed["projeto_l1"]).delete()
        db.query(ParcelaProjeto).filter_by(projeto_nome=seed["projeto_l1"]).delete()
        ids = []
        for n in nomes:
            pa = PoolAmbiente(projeto_id=seed["projeto_l1"], nome=n, nome_exibicao=n,
                              xml_path="/dev/null", ambientes_json="[]",
                              budget_total=1000.0, order_total=400.0)
            db.add(pa); db.flush()
            db.add(OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                     pool_ambiente_id=pa.id))
            ids.append(pa.id)
        p1 = ParcelaProjeto(projeto_nome=seed["projeto_l1"], ordem=1, status="aguardando",
                            fracao_val_cont=2.0 / 3, val_cont_congelado=2000.0,
                            orcamento_id=seed["orcamento_l1_id"])
        p2 = ParcelaProjeto(projeto_nome=seed["projeto_l1"], ordem=2, status="aguardando",
                            fracao_val_cont=1.0 / 3, val_cont_congelado=1000.0,
                            orcamento_id=seed["orcamento_l1_id"])
        db.add_all([p1, p2]); db.flush()
        db.add(ParcelaAmbiente(parcela_id=p1.id, pool_ambiente_id=ids[0]))
        db.add(ParcelaAmbiente(parcela_id=p1.id, pool_ambiente_id=ids[1]))
        db.add(ParcelaAmbiente(parcela_id=p2.id, pool_ambiente_id=ids[2]))
        db.commit()
        return ids, p1.id, p2.id
    finally:
        db.close()


def test_sucessivo_divide_fase_e_renumera(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids, p1_id, p2_id = _setup_fases(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/parcelas/%d/desmembrar" % (nome, p1_id),
                   {"parcelas": [[ids[0]], [ids[1]]]})
    assert st == 200 and d["ok"], (st, d)
    st, lst = c.get("/api/projetos/%s/parcelas" % nome)
    assert st == 200 and lst["desmembrado"]
    fases = lst["parcelas"]
    assert len(fases) == 3
    assert [f["ordem"] for f in fases] == [1, 2, 3]
    # novas fases herdam a posição da mãe (1 e 2); a antiga fase 2 vira 3
    assert [f["ambientes"][0]["nome"] for f in fases] == ["Cozinha", "Suite", "Home"]
    # congelados da mãe preservados exatamente (invariante #5 no total)
    assert round(fases[0]["val_cont_congelado"] + fases[1]["val_cont_congelado"], 2) == 2000.0
    assert fases[2]["val_cont_congelado"] == 1000.0
    assert p1_id not in [f["id"] for f in fases]


def test_sucessivo_bloqueia_fase_em_expedicao(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids, p1_id, _ = _setup_fases(app_db, seed)
    db = app_db.get_session()
    try:
        db.add(CicloLogistico(projeto_nome=nome, parcela_id=p1_id,
                              status_atual="Em Produção", prazo_entrega=date(2026, 9, 1)))
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/parcelas/%d/desmembrar" % (nome, p1_id),
                   {"parcelas": [[ids[0]], [ids[1]]]})
    assert st == 409, (st, d)
    assert "expedi" in d.get("erro", "").lower()


# Achado da Vera (2026-08-26, E2E rodada 2/3): desmembrar de novo uma fase que já tem decisão de
# AF2 (ConciliacaoPeFase) estourava IntegrityError sem tratamento no `db.delete(mae)` — FK
# `conciliacao_pe_fase.parcela_id` — e o servidor derrubava a conexão sem resposta nenhuma
# (ERR_EMPTY_RESPONSE no navegador). Mesma trava das outras 2 guardas desta função (liquidada /
# em expedição), aplicada ANTES de tentar apagar a mãe.
def test_sucessivo_bloqueia_fase_com_decisao_af2(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids, p1_id, _ = _setup_fases(app_db, seed)
    db = app_db.get_session()
    try:
        db.add(ConciliacaoPeFase(projeto_nome=nome, parcela_id=p1_id, pool_ambiente_id=ids[0],
                                 tipo_decisao="manter"))
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/parcelas/%d/desmembrar" % (nome, p1_id),
                   {"parcelas": [[ids[0]], [ids[1]]]})
    assert st == 409, (st, d)
    assert "af2" in d.get("erro", "").lower() or "aprovação financeira" in d.get("erro", "").lower()
    # a fase-mãe continua intacta (não foi parcialmente apagada)
    db = app_db.get_session()
    try:
        assert db.get(ParcelaProjeto, p1_id) is not None
    finally:
        db.close()


def test_sucessivo_bloqueia_liquidada_e_particao_errada(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    ids, p1_id, p2_id = _setup_fases(app_db, seed)
    db = app_db.get_session()
    try:
        db.get(ParcelaProjeto, p2_id).status = "liquidada"
        db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/parcelas/%d/desmembrar" % (nome, p2_id),
                   {"parcelas": [[ids[2]], [ids[2]]]})
    assert st == 409, (st, d)                                   # liquidada
    # partição com ambiente de OUTRA fase → 400
    st, d = c.post("/api/projetos/%s/parcelas/%d/desmembrar" % (nome, p1_id),
                   {"parcelas": [[ids[0]], [ids[2]]]})
    assert st == 400, (st, d)


def test_sucessivo_tenancy_404(app_db, seed, http_client_factory):
    _, p1_id, _ = _setup_fases(app_db, seed)
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, d = c.post("/api/projetos/%s/parcelas/%d/desmembrar" % (seed["projeto_l1"], p1_id),
                   {"parcelas": [[1], [2]]})
    assert st == 404, (st, d)
