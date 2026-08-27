import mod_contabil as mc


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_dashboard_provisoes_dre_cobertura(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 60); c = _q(db, 60)
    cfg = {"provisoes": {"assist_pct": 3.0}, "provisoes_contabeis": {"montagem_pct": 5.0, "garantia_pct": 2.0}}
    mc.constituir_provisoes_venda(db, "loja", 60, "PV", 10000.0, cfg, ref_base="prov:1")   # 500/300/200
    mc.registrar_evento(db, "loja", 60, "faturamento", 1000.0, projeto_id="PV")             # receita
    mc.registrar_evento(db, "loja", 60, "recebimento", 700.0, projeto_id="PV")              # caixa 700
    dash = mc.dashboard_financeiro(db, "loja", 60)
    db.close()
    saldos = {p["nome"]: p["saldo_em_aberto"] for p in dash["provisoes"]}
    assert saldos["Provisão de Montagem"] == 500.0
    assert saldos["Provisão de Assistência Técnica"] == 300.0
    assert saldos["Provisão de Garantia"] == 200.0
    assert dash["total_provisoes_abertas"] == 1000.0
    assert dash["dre_resumo"]["receita_liquida"] == 1000.0
    # cobertura: caixa 700 / provisões 1000 = 0.70
    assert dash["cobertura_caixa"]["caixa"] == 700.0
    assert dash["cobertura_caixa"]["indice"] == 0.7


def test_dashboard_endpoint(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/dashboard")
    assert st == 200 and d["ok"] is True
    cods = {p["codigo"] for p in d["dashboard"]["provisoes"]}
    assert {"2.1.04.02", "2.1.04.03", "2.1.04.05", "2.1.04.06"} <= cods   # 3 antigas + Custo Fábrica (FASE A)
    assert "2.1.04.01" not in cods and "2.1.04.04" not in cods            # comissão/devolução excluídas


def test_dashboard_provisoes_data_driven(app_db):
    """O painel é um loop sobre o Plano de Contas, não 3 componentes fixos: hoje mostra as 3
    provisões da venda (comissão e devolução ficam de fora); criar uma provisão nova no plano
    faz surgir um 4º card automaticamente, sem tocar no código do painel (Diagramacao_v4 §1.3)."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 61)
    dash = mc.dashboard_financeiro(db, "loja", 61)
    cods = {p["codigo"] for p in dash["provisoes"]}
    assert {"2.1.04.02", "2.1.04.03", "2.1.04.05"} <= cods       # provisões da venda (B)
    assert {"2.1.04.06", "2.1.04.12"} <= cods                    # provisões novas (FASE A) aparecem sozinhas
    assert "2.1.04.01" not in cods and "2.1.04.04" not in cods   # comissão/devolução: tratamento próprio
    # nova provisão CRIADA no Plano de Contas (código fora do PLANO_PADRAO) -> novo card, sem tocar a tela
    db.add(mc.Conta(owner_tipo="loja", owner_id=61, codigo="2.1.04.99", nome="Provisão Ad Hoc",
                    grupo=2, tipo="analitica", natureza=mc._natureza(2), ativa=1, ordem=999))
    db.commit()
    dash2 = mc.dashboard_financeiro(db, "loja", 61)
    db.close()
    novo = {p["codigo"]: p for p in dash2["provisoes"]}.get("2.1.04.99")
    assert novo is not None
    assert novo["nome"] == "Provisão Ad Hoc"          # nome vem do plano, não hardcoded
    assert novo["saldo_em_aberto"] == 0.0
    assert novo["sub"] == "Saldo provisionado em aberto"   # descrição genérica (não estava no mapa)


# ── T6 (27/08/2026, revisão do banco): alertas das contas de escape ─────────────────────────────
def test_alertas_contas_escape_vazio_sem_lancamento(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 62)
    dash = mc.dashboard_financeiro(db, "loja", 62)
    db.close()
    assert dash["alertas"] == []


def test_alertas_5610_dispara_com_qualquer_lancamento(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 63); c = _q(db, 63)
    mc.lancar(db, "loja", 63, c("5.6.10"), c("1.1.01"), 42.0, historico="ajuste sem origem")
    alertas = mc.alertas_contas_escape(db, "loja", 63)
    db.close()
    a = next(x for x in alertas if x["codigo"] == "5.6.10")
    assert a["tipo"] == "qualquer_lancamento" and a["valor_mes"] == 42.0


def test_alertas_5420_dispara_acima_de_1pct_do_custo_fixo_do_mes(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 64); c = _q(db, 64)
    aluguel = db.get(mc.Conta, c("5.4.01")); aluguel.natureza_custo = "fixo"   # 5.4.01 Aluguel
    outras = db.get(mc.Conta, c("5.4.20")); outras.natureza_custo = "fixo"    # não conta pra si mesma no limite (mesmo prefixo 5.4, mas soma TODO fixo, incl. 5.4.20 — decisão simples: "custo fixo do mês" é bruto, sem excluir a própria escape)
    db.commit()
    mc.lancar(db, "loja", 64, c("5.4.01"), c("1.1.01"), 10000.0, historico="aluguel do mês")
    mc.lancar(db, "loja", 64, c("5.4.20"), c("1.1.01"), 200.0, historico="despesa avulsa")   # > 1% de 10200
    alertas = mc.alertas_contas_escape(db, "loja", 64)
    db.close()
    a = next(x for x in alertas if x["codigo"] == "5.4.20")
    assert a["tipo"] == "limite_pct_custo_fixo" and a["valor_mes"] == 200.0


def test_alertas_5420_nao_dispara_abaixo_de_1pct(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 65); c = _q(db, 65)
    aluguel = db.get(mc.Conta, c("5.4.01")); aluguel.natureza_custo = "fixo"
    db.commit()
    mc.lancar(db, "loja", 65, c("5.4.01"), c("1.1.01"), 10000.0, historico="aluguel do mês")
    mc.lancar(db, "loja", 65, c("5.4.20"), c("1.1.01"), 50.0, historico="despesa avulsa")   # < 1% de 10000
    alertas = mc.alertas_contas_escape(db, "loja", 65)
    db.close()
    assert not any(a["codigo"] == "5.4.20" for a in alertas)
