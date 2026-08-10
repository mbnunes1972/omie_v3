# -*- coding: utf-8 -*-
"""PDV — Fatia 3: consolidação (mãe+PDVs com eliminações) e Rateio ao PDV.

Spec _geral/2026-07-22-ponto-de-venda-design.md §"Integração das contas":
- Consolidado = soma dos saldos/DRE de [mãe]+PDVs; o saldo intercompany pendente
  (1.1.09 credora × 2.1.09 devedora) é eliminado e exibido em linha própria.
- Rateio ao PDV: par com ref espelhada rateio:<n> (mãe DR 1.1.09 × CR 1.1.01;
  PDV DR 5.x × CR 2.1.09), reversível em par.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from conftest import HttpClient


@pytest.fixture(scope="module")
def pdv(servidor, app_db, seed):
    c = HttpClient(servidor); c.login("super", "senha123")
    st, out = c.post("/api/admin/lojas/%d/pdvs" % seed["loja1_id"],
                     {"nome": "PDV Consolida", "codigo": "CON"})
    assert st == 200 and out.get("ok"), (st, out)
    return out["pdv"]


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, "login falhou para %s" % who
    return c


@pytest.fixture(scope="module")
def rateio(servidor, app_db, seed, pdv):
    """Receita na mãe + receita no PDV + um rateio de R$ 300 (aluguel 5.4.01) mãe→PDV."""
    c = HttpClient(servidor); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/financeiro/eventos",
                   {"tipo": "faturamento", "valor": 1000.0, "projeto_id": "Proj_Mae_C"})
    assert st == 201
    st, _ = c.post("/api/financeiro/eventos?unidade=%d" % pdv["id"],
                   {"tipo": "faturamento", "valor": 400.0, "projeto_id": "Proj_PDV_C"})
    assert st == 201
    st, out = c.post("/api/financeiro/rateio-pdv",
                     {"pdv_id": pdv["id"], "valor": 300.0, "conta_despesa": "5.4.01",
                      "historico": "Aluguel — quota do PDV"})
    assert st == 201 and out["ok"], (st, out)
    return out


# ── Rateio: par espelhado nos dois razões ────────────────────────────────────

def test_rateio_lanca_o_par_com_ref_espelhada(app_db, seed, pdv, rateio):
    import mod_contabil
    assert rateio["ref"].startswith("rateio:")
    db = app_db.get_session()
    try:
        mae = mod_contabil.lancamento_por_ref(db, "loja", seed["loja1_id"], rateio["ref"])
        leg = mod_contabil.lancamento_por_ref(db, "loja", pdv["id"], rateio["ref"])
        assert mae is not None and leg is not None
        assert mae["valor"] == leg["valor"] == 300.0
    finally:
        db.close()


def test_rateio_vira_despesa_no_pdv_e_conta_corrente_na_mae(app_db, seed, pdv, rateio):
    import mod_contabil
    db = app_db.get_session()
    try:
        # PDV: despesa 5.4.01 devedora 300 e 2.1.09 credora 300
        c_desp = mod_contabil._conta_por_codigo(db, "loja", pdv["id"], "5.4.01")
        c_cc = mod_contabil._conta_por_codigo(db, "loja", pdv["id"], "2.1.09")
        assert mod_contabil.saldo_conta(db, "loja", pdv["id"], c_desp.id) == 300.0
        assert mod_contabil.saldo_conta(db, "loja", pdv["id"], c_cc.id) == 300.0
        # mãe (razão da rede): 1.1.09 devedora com os 300 a receber
        c_rec = mod_contabil._conta_por_codigo(db, "loja", seed["loja1_id"], "1.1.09")
        assert mod_contabil.saldo_conta(db, "loja", seed["loja1_id"], c_rec.id) == 300.0
    finally:
        db.close()


def test_rateio_exige_pdv_do_escopo(http_client_factory, seed, pdv, rateio):
    c = _login(http_client_factory, "dir_l2")
    st, out = c.post("/api/financeiro/rateio-pdv",
                     {"pdv_id": pdv["id"], "valor": 50.0, "conta_despesa": "5.4.01"})
    assert st == 403
    c1 = _login(http_client_factory, "dir_l1")   # loja plena não é PDV
    st, out = c1.post("/api/financeiro/rateio-pdv",
                      {"pdv_id": seed["loja2_id"], "valor": 50.0, "conta_despesa": "5.4.01"})
    assert st == 403


def test_rateio_recusa_conta_que_nao_e_despesa(http_client_factory, pdv, rateio):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.post("/api/financeiro/rateio-pdv",
                     {"pdv_id": pdv["id"], "valor": 10.0, "conta_despesa": "1.1.01"})
    assert st == 400 and "grupo 5" in out["erro"]


# ── Consolidação com eliminações ─────────────────────────────────────────────

def test_dre_consolidada_soma_mae_e_pdv(http_client_factory, seed, pdv, rateio):
    c = _login(http_client_factory, "dir_l1")
    st, o_mae = c.get("/api/financeiro/dre")
    st2, o_pdv = c.get("/api/financeiro/dre?unidade=%d" % pdv["id"])
    st3, o_con = c.get("/api/financeiro/dre?unidade=consolidado")
    assert st == st2 == st3 == 200, (st, st2, st3)
    dre_c = o_con["dre"]
    assert dre_c["unidades"] == 2
    assert dre_c["receita_bruta"] == round(
        o_mae["dre"]["receita_bruta"] + o_pdv["dre"]["receita_bruta"], 2)
    # a despesa do rateio aparece UMA vez (no PDV) — a perna da mãe não toca a DRE
    assert dre_c["despesas_administrativas"] == round(
        o_mae["dre"]["despesas_administrativas"] + 300.0, 2)


def test_balanco_consolidado_elimina_intercompany(http_client_factory, seed, pdv, rateio):
    c = _login(http_client_factory, "dir_l1")
    st, o_mae = c.get("/api/financeiro/balanco")
    st2, o_pdv = c.get("/api/financeiro/balanco?unidade=%d" % pdv["id"])
    st3, o_con = c.get("/api/financeiro/balanco?unidade=consolidado")
    assert st == st2 == st3 == 200
    b = o_con["balanco"]
    assert b["eliminacoes"] == 300.0     # pendência do rateio ainda não liquidada
    soma_ativo = round(o_mae["balanco"]["ativo"]["total"] + o_pdv["balanco"]["ativo"]["total"], 2)
    assert b["ativo"]["total"] == round(soma_ativo - 300.0, 2)
    assert b["confere"] is True          # continua fechando após a eliminação dos dois lados


def test_consolidado_negado_para_loja_sem_pdv(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l2")
    st, out = c.get("/api/financeiro/balanco?unidade=consolidado")
    assert st == 400


# ── Estorno em par ───────────────────────────────────────────────────────────

def test_estorno_reverte_o_par_e_zera_a_pendencia(http_client_factory, app_db, seed, pdv, rateio):
    import mod_contabil
    c = _login(http_client_factory, "dir_l1")
    st, out = c.post("/api/financeiro/rateio-pdv/estorno", {"ref": rateio["ref"]})
    assert st == 200 and out["ok"] and len(out["lancamentos"]) == 2
    # idempotente
    st, out2 = c.post("/api/financeiro/rateio-pdv/estorno", {"ref": rateio["ref"]})
    assert st == 200 and out2["ja_estornado"] is True
    db = app_db.get_session()
    try:
        c_desp = mod_contabil._conta_por_codigo(db, "loja", pdv["id"], "5.4.01")
        assert mod_contabil.saldo_conta(db, "loja", pdv["id"], c_desp.id) == 0.0
        owners = [("loja", seed["loja1_id"]), ("loja", pdv["id"])]
        assert mod_contabil.eliminacoes_intercompany(db, owners) == 0.0
    finally:
        db.close()
    st, o_con = c.get("/api/financeiro/balanco?unidade=consolidado")
    assert st == 200 and o_con["balanco"]["eliminacoes"] == 0.0


def test_estorno_fora_do_escopo_negado(http_client_factory, seed, pdv, rateio):
    c = _login(http_client_factory, "dir_l2")
    st, out = c.post("/api/financeiro/rateio-pdv/estorno", {"ref": rateio["ref"]})
    assert st == 403


def test_lista_de_rateios_do_perimetro(http_client_factory, seed, pdv, rateio):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.get("/api/financeiro/rateios")
    assert st == 200 and out["ok"]
    item = next(r for r in out["rateios"] if r["ref"] == rateio["ref"])
    assert item["valor"] == 300.0 and item["unidade"] == "PDV Consolida"
    # Corte S187: dir_l2 (Master só de loja2, sem PDV) tem razão PRÓPRIO — o rateio mãe→PDV
    # de loja1 não é mais visível pra ela (antes do corte, era, por acidente do razão
    # compartilhado da rede). Perímetro vazio, sem quebrar (achado: eliminacoes_intercompany
    # lançava ValueError pra owner sem a conta 1.1.09 — corrigido junto).
    c2 = _login(http_client_factory, "dir_l2")
    st, out2 = c2.get("/api/financeiro/rateios")
    assert st == 200 and out2["ok"]
    assert not any(r["ref"] == rateio["ref"] for r in out2["rateios"])
