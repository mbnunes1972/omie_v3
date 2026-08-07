def test_projetos_dre_endpoint(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 600, "projeto_id": "ProjMarg"})
    st, d = c.get("/api/financeiro/projetos-dre")
    assert st == 200 and d["ok"] is True
    p = next((x for x in d["projetos"] if x["projeto_id"] == "ProjMarg"), None)
    assert p is not None and p["receita"] == 600.0 and p["margem_contribuicao"] == 600.0


def test_projetos_dre_endpoint_modo_simulado(http_client_factory, seed, app_db):
    """2026-08-07: ?modo=competencia_estimada|antecipacao_contrato liga margem_projeto_simulada por
    projeto; modo inválido devolve 400."""
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 700, "projeto_id": "ProjMarg2"})
    st, d = c.get("/api/financeiro/projetos-dre?modo=competencia_estimada")
    assert st == 200 and d["ok"] is True
    p = next((x for x in d["projetos"] if x["projeto_id"] == "ProjMarg2"), None)
    assert p is not None and p["modo"] == "competencia_estimada"
    st, d = c.get("/api/financeiro/projetos-dre?modo=xpto")
    assert st == 400 and d["ok"] is False, d
