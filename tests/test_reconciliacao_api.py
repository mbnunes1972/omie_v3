def test_reconciliar_e_fechar_periodo(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 1000, "projeto_id": "PA"})
    c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 1000, "projeto_id": "PB"})
    # despesa fixa 5.4 (Aluguel) 400 sem projeto
    _, contas = c.get("/api/financeiro/contas")

    def find(nodes, cod):
        for n in nodes:
            if n["codigo"] == cod:
                return n
            r = find(n["filhos"], cod)
            if r:
                return r
    aluguel = find(contas["contas"], "5.4.01")["id"]
    caixa = find(contas["contas"], "1.1.01")["id"]
    c.post("/api/financeiro/lancamentos", {"conta_debito_id": aluguel, "conta_credito_id": caixa, "valor": 400})

    st, d = c.post("/api/financeiro/reconciliar", {"metodologia": "proporcional_receita"})
    assert st == 200 and d["ok"] is True
    rec = d["reconciliacao"]
    aloc = {a["projeto_id"]: a for a in rec["alocacao_por_projeto"]}
    assert aloc["PA"]["valor_rateado"] == 200.0 and aloc["PB"]["valor_rateado"] == 200.0  # 50/50
    assert rec["divergencia_residual"] == 0.0

    st2, d2 = c.post("/api/financeiro/periodos", {"metodologia": "proporcional_receita"})
    assert st2 == 201 and d2["periodo"]["id"]
    st3, d3 = c.get("/api/financeiro/periodos")
    assert st3 == 200 and len(d3["periodos"]) == 1


def test_reconciliar_metodologia_invalida_400(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/financeiro/reconciliar", {"metodologia": "xyz"})
    assert st == 400


# ── Frente 2 (spec 2026-08-25): fechar com ini/fim congela o relatório desse intervalo ──────────
def test_fechar_periodo_com_intervalo_congela_relatorio_natureza(http_client_factory, seed, app_db):
    import mod_contabil as mc
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, contas = c.get("/api/financeiro/contas")

    def find(nodes, cod):
        for n in nodes:
            if n["codigo"] == cod:
                return n
            r = find(n["filhos"], cod)
            if r:
                return r
    aluguel_id = find(contas["contas"], "5.4.01")["id"]
    caixa_id = find(contas["contas"], "1.1.01")["id"]

    db = app_db.get_session()
    db.get(mc.Conta, aluguel_id).natureza_custo = "fixo"
    db.commit(); db.close()

    c.post("/api/financeiro/lancamentos", {"conta_debito_id": aluguel_id, "conta_credito_id": caixa_id,
                                           "valor": 500, "data": "2026-08-15"})

    ini, fim = "2026-08-01", "2026-08-31"
    st, d = c.post("/api/financeiro/periodos", {"metodologia": "proporcional_receita",
                                                "ini": ini, "fim": fim})
    assert st == 201 and d["periodo"]["id"]

    # reclassifica a conta DEPOIS do fechamento
    db = app_db.get_session()
    db.get(mc.Conta, aluguel_id).natureza_custo = "variavel"
    db.commit(); db.close()

    # (checagem por CÓDIGO na lista, não por total exato — o owner/período é compartilhado com
    # outros testes deste módulo, `seed` é module-scoped, e um lançamento sem data explícita em
    # OUTRO teste cairia no mesmo mês corrente e infiltraria o total)
    st2, d2 = c.get(f"/api/financeiro/plano-contas/natureza-relatorio?ini={ini}&fim={fim}")
    assert st2 == 200 and d2["ok"]
    assert any(c2["codigo"] == "5.4.01" for c2 in d2["fixo"]["contas"])         # snapshot: continua Fixo
    assert not any(c2["codigo"] == "5.4.01" for c2 in d2["variavel"]["contas"])

    # sem filtro (visão padrão) reflete a reclassificação atual — não ficou preso no snapshot
    st3, d3 = c.get("/api/financeiro/plano-contas/natureza-relatorio")
    assert st3 == 200 and d3["ok"]
    assert any(c3["codigo"] == "5.4.01" for c3 in d3["variavel"]["contas"])
