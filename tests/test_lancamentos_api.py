def _find(nodes, cod):
    for n in nodes:
        if n["codigo"] == cod:
            return n
        r = _find(n["filhos"], cod)
        if r:
            return r
    return None


def _ids(c):
    _, d = c.get("/api/financeiro/contas")
    return {cod: _find(d["contas"], cod)["id"] for cod in ("1.1.01", "4.1.01", "5")}


def test_post_lancamento_e_lista(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ids = _ids(c)
    st, r = c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["1.1.01"], "conta_credito_id": ids["4.1.01"],
        "valor": 250.0, "projeto_id": "Proj_L1", "historico": "faturamento"})
    assert st == 201 and r["lancamento"]["valor"] == 250.0
    st2, d2 = c.get("/api/financeiro/lancamentos?projeto=Proj_L1")
    assert st2 == 200 and any(l["valor"] == 250.0 for l in d2["lancamentos"])


def test_lancamento_sintetica_400(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ids = _ids(c)
    st, _ = c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["5"], "conta_credito_id": ids["1.1.01"], "valor": 10})
    assert st == 400   # conta sintética não recebe lançamento


def test_get_lancamentos_fim_do_dia_inclui_lancamento_de_hoje(http_client_factory, seed, app_db):
    """`fim` vindo de <input type=date> chega à meia-noite; sem levar pro fim do dia, um
    lançamento feito mais tarde no mesmo dia ficava fora do range [hoje, hoje] — achado ao
    testar o filtro combinado projeto+período em Lançamentos (2026-08-07)."""
    from datetime import datetime
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ids = _ids(c)
    st, _ = c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["1.1.01"], "conta_credito_id": ids["4.1.01"],
        "valor": 42.0, "projeto_id": "Proj_FimDia"})
    assert st == 201
    hoje = datetime.utcnow().date().isoformat()
    st2, d2 = c.get("/api/financeiro/lancamentos?projeto=Proj_FimDia&ini=" + hoje + "&fim=" + hoje)
    assert st2 == 200 and any(l["valor"] == 42.0 for l in d2["lancamentos"]), d2


def test_razao_endpoint(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ids = _ids(c)
    c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["1.1.01"], "conta_credito_id": ids["4.1.01"], "valor": 70})
    st, d = c.get("/api/financeiro/contas/" + str(ids["1.1.01"]) + "/razao")
    assert st == 200 and d["razao"]["saldo_final"] >= 70
