def _find(nodes, cod):
    for n in nodes:
        if n["codigo"] == cod:
            return n
        r = _find(n["filhos"], cod)
        if r:
            return r
    return None


def test_dre_endpoint(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 800, "projeto_id": "Proj_L1"})
    _, contas = c.get("/api/financeiro/contas")
    aluguel = _find(contas["contas"], "5.4.01")["id"]
    caixa = _find(contas["contas"], "1.1.01")["id"]
    c.post("/api/financeiro/lancamentos", {"conta_debito_id": aluguel, "conta_credito_id": caixa, "valor": 300})
    st, d = c.get("/api/financeiro/dre")
    assert st == 200 and d["ok"] is True
    dre = d["dre"]
    assert dre["receita_bruta"] == 800.0
    assert dre["despesas_administrativas"] == 300.0
    assert dre["ebitda"] == 500.0


def test_dre_endpoint_modo_simulado(http_client_factory, seed, app_db):
    """2026-08-07: ?modo=competencia_estimada|antecipacao_contrato liga a visão simulada
    (dre_simulada); modo inválido devolve 400."""
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/dre?modo=competencia_estimada")
    assert st == 200 and d["ok"] is True and d["dre"]["modo"] == "competencia_estimada"
    st, d = c.get("/api/financeiro/dre?modo=antecipacao_contrato")
    assert st == 200 and d["ok"] is True and d["dre"]["modo"] == "antecipacao_contrato"
    st, d = c.get("/api/financeiro/dre?modo=xpto")
    assert st == 400 and d["ok"] is False, d
