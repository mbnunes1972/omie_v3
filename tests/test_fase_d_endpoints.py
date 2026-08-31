"""FASE D2 — endpoints da reconciliação de provisões + contas a pagar."""


def test_reconciliacao_endpoint_ok(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/reconciliacao-provisoes")
    assert st == 200 and d["ok"] is True
    assert "provisoes" in d["reconciliacao"] and "totais" in d["reconciliacao"]


def test_efetivar_reconciliacao_pagar_fluxo(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # efetiva o custo real de uma provisão (competência → Fornecedores a Pagar)
    st, d = c.post("/api/financeiro/efetivar-provisao",
                   {"conta": "2.1.04.07", "valor": 900.0, "ref": "eftest1"})
    assert st == 200 and d["ok"] is True, d
    # reconciliação reflete o efetivado
    st, d = c.get("/api/financeiro/reconciliacao-provisoes")
    linhas = {l["codigo"]: l for l in d["reconciliacao"]["provisoes"]}
    assert linhas["2.1.04.07"]["efetivado"] == 900.0
    # contas a pagar mostra a obrigação
    st, d = c.get("/api/financeiro/contas-a-pagar")
    assert d["contas_a_pagar"]["total_em_aberto"] == 900.0
    # paga o fornecedor → zera
    st, d = c.post("/api/financeiro/pagar-fornecedor", {"valor": 900.0, "ref": "pgtest1"})
    assert st == 200 and d["ok"] is True, d
    st, d = c.get("/api/financeiro/contas-a-pagar")
    assert d["contas_a_pagar"]["total_em_aberto"] == 0.0


def test_efetivar_sem_ref_e_idempotente_no_mesmo_dia(http_client_factory, seed):
    """Achado da Vera (2026-08-07): sem `ref` explícito, o endpoint gerava um uuid aleatório a cada
    chamada — duas ações GENUINAMENTE separadas do operador (duplo-clique, retry após timeout) tinham
    refs diferentes e a despesa duplicava. Agora o ref auto-gerado é determinístico por
    projeto+conta+valor+dia: repetir a MESMA chamada no mesmo dia é idempotente."""
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st1, d1 = c.post("/api/financeiro/efetivar-provisao", {"conta": "2.1.04.09", "valor": 300.0})
    assert st1 == 200 and d1["ok"] is True, d1
    st2, d2 = c.post("/api/financeiro/efetivar-provisao", {"conta": "2.1.04.09", "valor": 300.0})
    assert st2 == 200 and d2["ok"] is True, d2
    assert d1["lancamento"]["id"] == d2["lancamento"]["id"]   # mesmo lançamento, não duplicou
    st, d = c.get("/api/financeiro/reconciliacao-provisoes")
    linhas = {l["codigo"]: l for l in d["reconciliacao"]["provisoes"]}
    assert linhas["2.1.04.09"]["efetivado"] == 300.0   # não 600


def test_efetivar_bloqueado_para_assistencia_e_garantia(http_client_factory, seed):
    """2026-08-07 (achado da Vera): Assistência Técnica/Garantia só pelo módulo Assistências —
    "Efetivar" genérico devolve 409 pras duas."""
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/financeiro/efetivar-provisao", {"conta": "2.1.04.05", "valor": 100.0})
    assert st == 409 and d["ok"] is False, d
    st, d = c.post("/api/financeiro/efetivar-provisao", {"conta": "2.1.04.03", "valor": 100.0})
    assert st == 409 and d["ok"] is False, d
    # outras rubricas continuam funcionando normalmente
    st, d = c.post("/api/financeiro/efetivar-provisao", {"conta": "2.1.04.02", "valor": 100.0})
    assert st == 200 and d["ok"] is True, d


def test_resolver_saldo_endpoint(http_client_factory, seed):
    # F2-3 (docs/db/TAREFA_FILA_PROVISOES.md, ACHADO-26): 2.1.04.08 (Provisão de Frete Local) é
    # matching pleno — exige veredito nomeado, não zera mais pelo desvio direto. A porta da
    # frente é a fila (`veredito=efetivada`, mesmo caso de FALTA do teste original) — a fila é
    # sempre POR PROJETO, então precisa de um (o teste original efetivava sem nenhum).
    nome = seed["projeto_l1"]
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # efetiva 900 numa provisão sem constituição → saldo negativo (falta) → resolver manda p/ despesa
    c.post("/api/financeiro/efetivar-provisao",
           {"conta": "2.1.04.08", "valor": 300.0, "ref": "ef8", "projeto": nome})
    st, d = c.post("/api/financeiro/fila-provisoes/veredito",
                   {"projeto": nome, "conta": "2.1.04.08", "veredito": "efetivada"})
    assert st == 200 and d["ok"] is True, d
    # idempotente: 2º veredito não faz nada (saldo já zero, mesma ref)
    st, d = c.post("/api/financeiro/fila-provisoes/veredito",
                   {"projeto": nome, "conta": "2.1.04.08", "veredito": "efetivada"})
    assert st == 200 and d["ok"] is True


def test_resolver_saldo_endpoint_recusa_rubrica_que_exige_veredito(http_client_factory, seed):
    """A porta dos fundos (ACHADO-26): resolver-saldo-provisao direto não zera mais uma rubrica
    de matching pleno — só Impostos/Custo Financeiro continuam por aqui."""
    nome = seed["projeto_l1"]
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/efetivar-provisao",
           {"conta": "2.1.04.08", "valor": 300.0, "ref": "ef8b", "projeto": nome})
    st, d = c.post("/api/financeiro/resolver-saldo-provisao", {"conta": "2.1.04.08", "projeto": nome})
    assert not (st == 200 and d.get("ok")), (
        "2.1.04.08 exige veredito nomeado — o desvio genérico não pode mais zerar essa rubrica: "
        "st=%r d=%r" % (st, d))


def test_efetivar_gate_operador_403(http_client_factory, seed):
    c = http_client_factory(); c.login("cons_l1", "senha123")   # operador: sem acesso ao Financeiro
    st, d = c.post("/api/financeiro/efetivar-provisao", {"conta": "2.1.04.07", "valor": 900.0})
    assert st == 403 and d["ok"] is False
