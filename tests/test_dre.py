from datetime import datetime

import mod_contabil as mc

# app_db module-scoped -> uso owner distinto por teste para isolar os lançamentos.


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_dre_estrutura_e_sinais(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 10); c = _q(db, 10)
    # Receita bruta 1000 (faturamento)
    mc.registrar_evento(db, "loja", 10, "faturamento", 1000.0, projeto_id="P1")
    # Dedução 80 (Simples Nacional s/ Vendas: D 4.3.01 / C Caixa)
    mc.lancar(db, "loja", 10, conta_debito_id=c("4.3.01"), conta_credito_id=c("1.1.01"), valor=80.0)
    # Despesa administrativa 200 (Aluguel: D 5.4.01 / C Caixa)
    mc.lancar(db, "loja", 10, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=200.0)
    d = mc.dre(db, "loja", 10)
    db.close()
    assert d["receita_bruta"] == 1000.0
    assert d["deducoes"] == 80.0                 # dedução com sinal certo (D−C positivo, subtraído)
    assert d["receita_liquida"] == 920.0
    assert d["despesas_administrativas"] == 200.0
    assert d["ebitda"] == 720.0
    assert d["lucro_liquido"] == 720.0


def test_dre_com_cmv_e_provisao(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 11); c = _q(db, 11)
    mc.registrar_evento(db, "loja", 11, "faturamento", 500.0, projeto_id="P2")   # receita 500
    mc.lancar(db, "loja", 11, conta_debito_id=c("5.1.01"), conta_credito_id=c("2.1.01"), valor=150.0)  # CMV 150
    mc.registrar_evento(db, "loja", 11, "fechamento_venda_garantia", 30.0, projeto_id="P2")  # FASE D2: constituição DIFERIDA (1.1.06), não toca DRE
    d = mc.dre(db, "loja", 11)
    db.close()
    assert d["receita_liquida"] == 500.0
    assert d["cmv_csp"] == 150.0
    assert d["lucro_bruto"] == 350.0
    assert d["constituicao_provisoes"] == 0.0   # FASE D2: despesa da provisão só entra na DRE na NF-e (matching pleno)
    assert d["ebitda"] == 350.0 and d["lucro_liquido"] == 350.0


def test_dre_vazio_zerado(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 12)
    d = mc.dre(db, "loja", 12)
    db.close()
    assert d["receita_bruta"] == 0.0 and d["lucro_liquido"] == 0.0


# ── meses_do_periodo (achado do usuário 2026-08-15: DRE em colunas mês a mês) ────────────────────

def test_meses_do_periodo_mes_unico():
    out = mc.meses_do_periodo(datetime(2026, 8, 1), datetime(2026, 8, 31))
    assert len(out) == 1
    ini, fim = out[0]
    assert ini == datetime(2026, 8, 1, 0, 0, 0)
    assert fim.date() == datetime(2026, 8, 31).date() and fim.hour == 23 and fim.minute == 59


def test_meses_do_periodo_mesmo_ano():
    out = mc.meses_do_periodo(datetime(2026, 6, 15), datetime(2026, 9, 3))
    assert [(i.year, i.month) for i, f in out] == [(2026, 6), (2026, 7), (2026, 8), (2026, 9)]
    # cada mês termina no ÚLTIMO dia dele, não no dia de `fim` original
    assert out[0][1].day == 30 and out[-1][1].day == 30   # jun/set têm 30 dias


def test_meses_do_periodo_cruza_ano():
    out = mc.meses_do_periodo(datetime(2025, 12, 1), datetime(2026, 2, 28))
    assert [(i.year, i.month) for i, f in out] == [(2025, 12), (2026, 1), (2026, 2)]


def test_meses_do_periodo_fevereiro_bissexto():
    out = mc.meses_do_periodo(datetime(2024, 2, 1), datetime(2024, 2, 1))
    assert out[0][1].day == 29


# ── dre_serie_mensal ──────────────────────────────────────────────────────────────────────────

def test_dre_serie_mensal_bate_com_chamadas_individuais(app_db):
    db = app_db.get_session(); ot, oid = "loja", 13; mc.seed_plano(db, ot, oid); c = _q(db, 13)
    mc.lancar(db, ot, oid, c("5.4.01"), c("1.1.01"), 100.0, data=datetime(2026, 6, 10))
    mc.lancar(db, ot, oid, c("5.4.01"), c("1.1.01"), 200.0, data=datetime(2026, 7, 10))
    mc.registrar_evento(db, ot, oid, "faturamento", 900.0, projeto_id="P", data=datetime(2026, 7, 20))
    serie = mc.dre_serie_mensal(db, ot, oid, datetime(2026, 6, 1), datetime(2026, 7, 31))
    jun = mc.dre(db, ot, oid, datetime(2026, 6, 1), datetime(2026, 6, 30, 23, 59, 59))
    jul = mc.dre(db, ot, oid, datetime(2026, 7, 1), datetime(2026, 7, 31, 23, 59, 59))
    total = mc.dre(db, ot, oid, datetime(2026, 6, 1), datetime(2026, 7, 31))
    db.close()
    assert len(serie["meses"]) == 2
    assert serie["meses"][0]["despesas_administrativas"] == jun["despesas_administrativas"] == 100.0
    assert serie["meses"][1]["despesas_administrativas"] == jul["despesas_administrativas"] == 200.0
    assert serie["meses"][1]["receita_bruta"] == jul["receita_bruta"] == 900.0
    assert serie["total"]["despesas_administrativas"] == total["despesas_administrativas"] == 300.0
    assert serie["total"]["receita_bruta"] == total["receita_bruta"] == 900.0


def test_dre_serie_mensal_modo_simulado(app_db):
    from datetime import datetime as _dt
    db = app_db.get_session(); ot, oid = "loja", 14; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 50000.0, projeto_id="P",
                        ref="venda:P", data=_dt(2026, 5, 1))
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"montagem": 500.0}, ref_base="pf:P")
    serie = mc.dre_serie_mensal(db, ot, oid, _dt(2026, 5, 1), _dt(2026, 5, 31), modo="antecipacao_contrato")
    db.close()
    assert len(serie["meses"]) == 1
    assert serie["meses"][0]["modo"] == "antecipacao_contrato"
    assert serie["meses"][0]["receita_bruta"] == 50000.0
    assert serie["total"]["receita_bruta"] == 50000.0
