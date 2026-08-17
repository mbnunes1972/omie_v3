"""Achado do usuário 2026-08-17: adicionar/remover ambiente de um orçamento já existente
gravava valor_total = soma BRUTA dos ambientes (sem desconto, sem financiamento), sem passar
pelo motor (mod_negociacao.calcular_orcamento) e sem tocar vavo/vbno/val_cont — que ficavam
stale. Sintomas relatados: "valor total do contrato com erros estranhos", orçamento trocado
mas alguns campos continuavam com valor antigo, e um multiplicador de ~3,26x entre a coluna à
vista e a financiada num orçamento (causado por Val_Cont, calculado sobre um total_cliente
antigo, dividido por um VAVO recém-recalculado).

Corrigido: os 3 endpoints (sobrescrita de XML, adicionar ambiente, remover ambiente) agora
chamam `_recalcular_orcamento` (o mesmo caminho já usado por outros 6 pontos do código) e zeram
`forma_pagamento`/`negociacao_json` (mesmo padrão já usado em "Negociar Complemento") — uma
forma de pagamento escolhida antes da mudança de ambientes fica calculada sobre o VAVO antigo.
"""
import json


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_adicionar_ambiente_passa_pelo_motor_respeita_desconto(http_client_factory, seed, app_db):
    # orçamento PRÓPRIO deste teste (não reaproveita seed["orcamento_l1_id"]) — a fixture `seed`
    # não é limpa por função neste módulo, e o l1 é compartilhado entre os 3 testes aqui.
    db = app_db.get_session()
    orc = app_db.Orcamento(projeto_id="Proj_L1", nome="Orçamento teste 1", ordem=2,
                           loja_id=seed["loja1_id"], desconto_pct=10.0)
    db.add(orc); db.commit(); oid = orc.id
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Cozinha", nome_exibicao="Cozinha",
                             xml_path="x.xml", ambientes_json="{}",
                             budget_total=1000.0, order_total=800.0)
    db.add(pa); db.commit(); pid = pa.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/orcamentos/{oid}/ambientes/{pid}", {})
    assert body.get("ok") is True
    out = body["orcamento"]
    # regressão: sem o fix, valor_total viria 1000.0 (soma bruta, ignorando o desconto de 10%)
    assert out["valor_total"] < 1000.0
    assert out["valor_total"] > 0
    assert out["sombra"]["vbvo"] == 1000.0
    # sem financiamento escolhido: à vista ⇒ Val_Cont == VAVO
    assert out["sombra"]["val_cont"] == out["sombra"]["vavo"] == out["valor_total"]


def test_adicionar_ambiente_zera_forma_pagamento_desatualizada(http_client_factory, seed, app_db):
    db = app_db.get_session()
    orc = app_db.Orcamento(projeto_id="Proj_L1", nome="Orçamento teste 2", ordem=3,
                           loja_id=seed["loja1_id"])
    db.add(orc); db.flush()
    pa1 = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Sala", nome_exibicao="Sala",
                              xml_path="s.xml", ambientes_json="{}",
                              budget_total=1000.0, order_total=800.0)
    db.add(pa1); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=orc.id, pool_ambiente_id=pa1.id, ordem=1))
    # financiamento escolhido em cima do VAVO atual (≈1000) — fica stale ao mudar os ambientes
    orc.forma_pagamento = json.dumps({"total_cliente": 5000.0})
    db.commit(); oid = orc.id
    pa2 = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Quarto", nome_exibicao="Quarto",
                              xml_path="q.xml", ambientes_json="{}",
                              budget_total=200.0, order_total=150.0)
    db.add(pa2); db.commit(); pid2 = pa2.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/orcamentos/{oid}/ambientes/{pid2}", {})
    assert body.get("ok") is True
    out = body["orcamento"]
    # regressão: sem o fix, forma_pagamento continuaria com total_cliente=5000 (stale) e
    # val_cont sairia desproporcional ao VAVO novo (~1200) — foi o multiplicador de 3,26x.
    assert out["forma_pagamento"] == ""
    assert out["sombra"]["val_cont"] == out["sombra"]["vavo"]


def test_remover_ambiente_passa_pelo_motor_respeita_desconto(http_client_factory, seed, app_db):
    db = app_db.get_session()
    orc = app_db.Orcamento(projeto_id="Proj_L1", nome="Orçamento teste 3", ordem=4,
                           loja_id=seed["loja1_id"], desconto_pct=10.0)
    db.add(orc); db.flush()
    pa1 = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Sala", nome_exibicao="Sala",
                              xml_path="s.xml", ambientes_json="{}",
                              budget_total=1000.0, order_total=800.0)
    pa2 = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Quarto", nome_exibicao="Quarto",
                              xml_path="q.xml", ambientes_json="{}",
                              budget_total=200.0, order_total=150.0)
    db.add_all([pa1, pa2]); db.flush()
    db.add_all([app_db.OrcamentoAmbiente(orcamento_id=orc.id, pool_ambiente_id=pa1.id, ordem=1),
                app_db.OrcamentoAmbiente(orcamento_id=orc.id, pool_ambiente_id=pa2.id, ordem=2)])
    db.commit(); oid = orc.id; pid1 = pa1.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/orcamentos/{oid}/ambientes/{pid1}/remover", {})
    assert body.get("ok") is True
    out = body["orcamento"]
    # só o Quarto (200) resta — regressão: sem o fix, valor_total viria 200.0 (bruto, sem desconto)
    assert out["sombra"]["vbvo"] == 200.0
    assert out["valor_total"] < 200.0
    assert out["valor_total"] > 0
    assert out["sombra"]["val_cont"] == out["sombra"]["vavo"] == out["valor_total"]
