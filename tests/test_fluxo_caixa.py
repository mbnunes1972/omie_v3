"""Fluxo de Caixa (2026-08-07): dia a dia de crédito/débito/saldo, consolidado (Caixa/Bancos
1.1.01 + filhos criados via "Adicionar Conta") ou por conta específica."""
from datetime import date, datetime

import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return c


def test_contas_caixa_so_a_raiz_quando_nao_desmembrada(app_db):
    db = app_db.get_session(); ot, oid = "loja", 971; mc.seed_plano(db, ot, oid)
    contas = mc.contas_caixa(db, ot, oid)
    assert [c.codigo for c in contas] == ["1.1.01"]
    db.close()


def test_contas_caixa_inclui_filhos_criados(app_db):
    db = app_db.get_session(); ot, oid = "loja", 972; mc.seed_plano(db, ot, oid)
    raiz = _s(db, ot, oid, "1.1.01")
    banco = mc.criar_conta(db, ot, oid, raiz.id, "Banco Itaú")   # devolve dict (_serial)
    db.commit()
    contas = mc.contas_caixa(db, ot, oid)
    codigos = sorted(c.codigo for c in contas)
    # raiz virou sintética (ganhou filho) — só ANALÍTICAS entram (raiz sai, o filho entra)
    assert banco["codigo"] in codigos
    assert "1.1.01" not in codigos
    db.close()


def test_fluxo_caixa_uma_linha_por_dia_mesmo_sem_movimento(app_db):
    db = app_db.get_session(); ot, oid = "loja", 973; mc.seed_plano(db, ot, oid)
    caixa = _s(db, ot, oid, "1.1.01")
    receita = _s(db, ot, oid, "4.1.02")   # qualquer conta credora pra contrapartida
    mc.lancar(db, ot, oid, caixa.id, receita.id, 500.0, data=datetime(2026, 9, 2))
    db.commit()
    r = mc.fluxo_caixa(db, ot, oid, [caixa.id], date(2026, 9, 1), date(2026, 9, 5))
    assert [d["data"] for d in r["dias"]] == ["2026-09-01", "2026-09-02", "2026-09-03",
                                              "2026-09-04", "2026-09-05"]
    assert r["saldo_inicial"] == 0.0
    d1, d2 = r["dias"][0], r["dias"][1]
    assert d1["credito"] == 0.0 and d1["debito"] == 0.0 and d1["saldo"] == 0.0
    assert d2["credito"] == 0.0 and d2["debito"] == 500.0 and d2["saldo"] == 500.0
    # dias seguintes carregam o saldo (sem novo movimento)
    assert r["dias"][2]["saldo"] == 500.0 and r["dias"][4]["saldo"] == 500.0
    assert r["saldo_final"] == 500.0
    db.close()


def test_fluxo_caixa_debito_entra_credito_sai(app_db):
    """Caixa é conta DEVEDORA (Ativo): débito = dinheiro entrando, crédito = saindo."""
    db = app_db.get_session(); ot, oid = "loja", 974; mc.seed_plano(db, ot, oid)
    caixa = _s(db, ot, oid, "1.1.01")
    receita = _s(db, ot, oid, "4.1.02")
    despesa = _s(db, ot, oid, "5.3.01")
    mc.lancar(db, ot, oid, caixa.id, receita.id, 1000.0, data=datetime(2026, 9, 10))   # entra
    mc.lancar(db, ot, oid, despesa.id, caixa.id, 300.0, data=datetime(2026, 9, 10))    # sai
    db.commit()
    r = mc.fluxo_caixa(db, ot, oid, [caixa.id], date(2026, 9, 10), date(2026, 9, 10))
    d = r["dias"][0]
    assert d["debito"] == 1000.0 and d["credito"] == 300.0 and d["saldo"] == 700.0
    db.close()


def test_fluxo_caixa_saldo_inicial_considera_lancamentos_anteriores(app_db):
    db = app_db.get_session(); ot, oid = "loja", 975; mc.seed_plano(db, ot, oid)
    caixa = _s(db, ot, oid, "1.1.01")
    receita = _s(db, ot, oid, "4.1.02")
    mc.lancar(db, ot, oid, caixa.id, receita.id, 2000.0, data=datetime(2026, 8, 15))   # antes do período
    mc.lancar(db, ot, oid, caixa.id, receita.id, 100.0, data=datetime(2026, 9, 3))     # dentro do período
    db.commit()
    r = mc.fluxo_caixa(db, ot, oid, [caixa.id], date(2026, 9, 1), date(2026, 9, 5))
    assert r["saldo_inicial"] == 2000.0
    assert r["dias"][2]["data"] == "2026-09-03" and r["dias"][2]["saldo"] == 2100.0
    assert r["dias"][0]["saldo"] == 2000.0   # carrega o inicial no 1º dia sem movimento
    db.close()


def test_fluxo_caixa_consolidado_soma_varias_contas(app_db):
    """Raiz 1.1.01 desmembrada em 2 "Adicionar Conta" — vira sintética, só as folhas recebem
    lançamento (regra do razão). Consolidado = soma das duas; conta específica = só a fatia dela."""
    db = app_db.get_session(); ot, oid = "loja", 976; mc.seed_plano(db, ot, oid)
    raiz = _s(db, ot, oid, "1.1.01")
    caixa = mc.criar_conta(db, ot, oid, raiz.id, "Caixa")
    banco = mc.criar_conta(db, ot, oid, raiz.id, "Banco Itaú")
    db.commit()
    receita = _s(db, ot, oid, "4.1.02")
    mc.lancar(db, ot, oid, caixa["id"], receita.id, 100.0, data=datetime(2026, 9, 1))
    mc.lancar(db, ot, oid, banco["id"], receita.id, 250.0, data=datetime(2026, 9, 1))
    db.commit()
    contas = mc.contas_caixa(db, ot, oid)
    assert sorted(c.codigo for c in contas) == sorted([caixa["codigo"], banco["codigo"]])
    r = mc.fluxo_caixa(db, ot, oid, [c.id for c in contas], date(2026, 9, 1), date(2026, 9, 1))
    assert r["dias"][0]["debito"] == 350.0 and r["dias"][0]["saldo"] == 350.0
    # e por conta específica isolada, só a fatia dela
    r_banco = mc.fluxo_caixa(db, ot, oid, [banco["id"]], date(2026, 9, 1), date(2026, 9, 1))
    assert r_banco["dias"][0]["debito"] == 250.0
    db.close()


def test_fluxo_caixa_sem_contas_devolve_vazio(app_db):
    db = app_db.get_session(); ot, oid = "loja", 977; mc.seed_plano(db, ot, oid)
    r = mc.fluxo_caixa(db, ot, oid, [], date(2026, 9, 1), date(2026, 9, 5))
    assert r == {"saldo_inicial": 0.0, "dias": [], "saldo_final": 0.0}
    db.close()


# ── HTTP ──────────────────────────────────────────────────────────────────────────────────

def test_endpoint_fluxo_caixa_consolidado(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/fluxo-caixa?de=2026-09-01&ate=2026-09-03")
    assert st == 200 and d["ok"], d
    assert [x["data"] for x in d["dias"]] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert any(x["codigo"] == "1.1.01" for x in d["contas"])


def test_endpoint_fluxo_caixa_exige_periodo(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/fluxo-caixa")
    assert st == 400


def test_endpoint_fluxo_caixa_filtra_por_conta(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, raiz = c.get("/api/financeiro/contas")
    no = next(n for n in raiz["contas"] if n["codigo"] == "1"); # ATIVO
    def _find(nos, codigo):
        for n in nos:
            if n["codigo"] == codigo: return n
            r = _find(n.get("filhos") or [], codigo)
            if r: return r
        return None
    caixa = _find(raiz["contas"], "1.1.01")
    st, d = c.post("/api/financeiro/contas", {"pai_id": caixa["id"], "nome": "Banco Inter"})
    assert st == 201 and d["ok"], d
    novo_id = d["conta"]["id"]
    st, d2 = c.get("/api/financeiro/fluxo-caixa?de=2026-09-01&ate=2026-09-01&contas=%d" % novo_id)
    assert st == 200 and d2["ok"], d2
    assert d2["dias"][0]["debito"] == 0.0
