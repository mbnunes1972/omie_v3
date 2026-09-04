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
    testar o filtro combinado projeto+período em Lançamentos (2026-08-07).

    LP-17 (03/09, rescaldo do ACHADO-48/F2-14): "hoje" tem que vir da MESMA fonte que
    `mod_contabil.lancar()` usa pra carimbar (`hoje_no_fuso`, fuso do dono do livro) — não de
    `datetime.utcnow()`. Os dois só concordavam por acidente de horário; na janela em que o
    relógio do processo (UTC) e o fuso configurado (America/Sao_Paulo, default) discordam de
    dia, o lançamento carimbado por `hoje_no_fuso` caía fora do range que `utcnow()` pedia."""
    import mod_contabil
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ids = _ids(c)
    st, _ = c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["1.1.01"], "conta_credito_id": ids["4.1.01"],
        "valor": 42.0, "projeto_id": "Proj_FimDia"})
    assert st == 201
    db = app_db.get_session()
    hoje = mod_contabil.hoje_no_fuso(db, "loja", seed["loja1_id"]).isoformat()
    db.close()
    st2, d2 = c.get("/api/financeiro/lancamentos?projeto=Proj_FimDia&ini=" + hoje + "&fim=" + hoje)
    assert st2 == 200 and any(l["valor"] == 42.0 for l in d2["lancamentos"]), d2


def test_razao_endpoint(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ids = _ids(c)
    c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["1.1.01"], "conta_credito_id": ids["4.1.01"], "valor": 70})
    st, d = c.get("/api/financeiro/contas/" + str(ids["1.1.01"]) + "/razao")
    assert st == 200 and d["razao"]["saldo_final"] >= 70


# ── filtro por conta (2026-08-09, aba Lançamentos Contábeis: "Conta" busca tudo associado) ──────
def test_get_lancamentos_filtra_por_conta_debito_ou_credito(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ids = _ids(c)
    c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["1.1.01"], "conta_credito_id": ids["4.1.01"],
        "valor": 111.0, "historico": "conta como débito"})
    c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["4.1.01"], "conta_credito_id": ids["1.1.01"],
        "valor": 222.0, "historico": "conta como crédito"})
    st, d = c.get("/api/financeiro/lancamentos?conta_id=" + str(ids["1.1.01"]))
    assert st == 200
    valores = {l["valor"] for l in d["lancamentos"]}
    assert 111.0 in valores and 222.0 in valores   # aparece nos dois lados


def test_get_lancamentos_conta_id_exclui_lancamentos_de_outra_conta(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ids = _ids(c)
    c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["1.1.01"], "conta_credito_id": ids["4.1.01"], "valor": 55.0})
    st, d = c.get("/api/financeiro/lancamentos?conta_id=" + str(ids["4.1.01"]))
    assert st == 200 and all(
        (l["conta_debito_id"] == ids["4.1.01"] or l["conta_credito_id"] == ids["4.1.01"])
        for l in d["lancamentos"])


# ── lista leve de projetos p/ o <select> da aba Lançamentos Contábeis (2026-08-09) ───────────────
# Achado do usuário: essa aba usava /projetos-dre (margem_todos_projetos — N+1 real, uma
# reconciliacao() por projeto) só pra montar a lista de nomes do filtro; numa loja com muito
# histórico isso levava ~16s e a aba parecia quebrada (em branco). Endpoint dedicado, direto de
# projetos_com_lancamento (já existente, já usado no modo simulado do próprio /projetos-dre).
def test_get_lancamentos_projetos_lista_so_ids_sem_calcular_margem(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ids = _ids(c)
    c.post("/api/financeiro/lancamentos", {
        "conta_debito_id": ids["1.1.01"], "conta_credito_id": ids["4.1.01"],
        "valor": 99.0, "projeto_id": "Proj_ListaLeve"})
    st, d = c.get("/api/financeiro/lancamentos/projetos")
    assert st == 200 and d["ok"]
    assert "Proj_ListaLeve" in d["projetos"]
    assert all(isinstance(p, str) for p in d["projetos"])   # ids crus, não objetos de margem


def test_get_lancamentos_projetos_sem_login_401(http_client_factory):
    c = http_client_factory()
    st, d = c.get("/api/financeiro/lancamentos/projetos")
    assert st == 401


def test_get_lancamentos_conta_id_invalido_ignora_o_filtro_em_vez_de_quebrar(http_client_factory, seed, app_db):
    """🟡 achado da Vera (2026-08-09): conta_id não-numérico na query derrubava a conexão (exceção
    não tratada) em vez de responder — não alcançável pela tela (o <select> só emite id numérico
    ou vazio), mas destoa do padrão do resto do arquivo de sempre guardar int(qs...) com try/except."""
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/lancamentos?conta_id=abc")
    assert st == 200 and d["ok"]
