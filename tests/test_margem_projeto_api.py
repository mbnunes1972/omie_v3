"""GET /api/financeiro/margem-projeto?projeto=<nome> — Visão Geral do Projeto (achado do usuário
2026-08-25): margem real + totais de reconciliação de UM projeto, num round-trip só. Não repete o
custo O(n) de /api/financeiro/projetos-dre (que roda margem_todos_projetos pra loja inteira)."""


def test_margem_projeto_endpoint_ok(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 800, "projeto_id": "ProjMargVG"})
    st, d = c.get("/api/financeiro/margem-projeto?projeto=ProjMargVG")
    assert st == 200 and d["ok"] is True, d
    assert d["margem"]["receita"] == 800.0 and d["margem"]["margem_contribuicao"] == 800.0
    assert "provisionado" in d["reconciliacao_totais"] and "saldo_aberto" in d["reconciliacao_totais"]


def test_margem_projeto_exige_projeto(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/margem-projeto")
    assert st == 400 and d["ok"] is False


def test_margem_projeto_gate_operador_403(http_client_factory, seed):
    c = http_client_factory(); c.login("cons_l1", "senha123")   # operador: sem acesso ao Financeiro
    st, d = c.get("/api/financeiro/margem-projeto?projeto=ProjMargVG")
    assert st == 403 and d["ok"] is False
