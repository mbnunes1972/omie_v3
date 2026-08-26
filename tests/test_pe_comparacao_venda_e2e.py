"""Fatia venda da Revisão de PE (2026-07-21) — E2E HTTP.

A 11c passa a comparar VENDA À VISTA: o VBVA extraído do XML de PE percorre o MESMO
motor de negociação (parâmetros/descontos salvos, motor inalterado) e o endpoint de
comparação devolve VAVA original × VAVA do PE por ambiente + flag Renegociar.
"""


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _seed_amb(app_db, oid, budget=80000.0, order=30000.0):
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    nome = orc.projeto_id
    pa = app_db.PoolAmbiente(nome="Cozinha", nome_exibicao="Cozinha", xml_path="fake/coz.xml",
                             ambientes_json="{}", projeto_id=nome,
                             budget_total=budget, order_total=order)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit()
    pid = pa.id
    db.close()
    return nome, pid


def test_comparacao_venda_via_motor_e_renegociar(http_client_factory, seed, app_db):
    oid = seed["orcamento_l1_id"]
    nome, pid = _seed_amb(app_db, oid, budget=80000.0)
    db = app_db.get_session()
    db.add(app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pid, formato="xml_pe",
                            valor_atualizado=32000.0, valor_venda=84000.0))
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.get(f"/api/projetos/{nome}/pe/comparacao")
    assert st == 200 and body["ok"], body
    lv = [l for l in body["comparacao_venda"] if l["pool_ambiente_id"] == pid][0]
    # desconto 0 e sem custos configurados → VAVA == VBVA nas duas rodadas do motor
    assert abs(lv["vava_original"] - 80000.0) < 0.5
    assert abs(lv["vava_pe"] - 84000.0) < 0.5
    assert lv["pe_carregado"] is True and lv["renegociar"] is False
    assert abs((body["venda_totais"]["vavo_pe"] - body["venda_totais"]["vavo_original"]) - 4000.0) < 1.0
    # a comparação de CFO segue no payload (consumida pela AF2)
    assert any(l.get("pool_ambiente_id") == pid for l in body["comparacao"])

    # marca Renegociar e confere o round-trip
    st, body = c.post(f"/api/projetos/{nome}/pe/renegociar",
                      {"pool_ambiente_id": pid, "renegociar": True})
    assert st == 200 and body["ok"] and body["renegociar"] is True
    st, body = c.get(f"/api/projetos/{nome}/pe/comparacao")
    lv = [l for l in body["comparacao_venda"] if l["pool_ambiente_id"] == pid][0]
    assert lv["renegociar"] is True


def test_renegociar_rejeita_ambiente_de_outro_projeto(http_client_factory, seed, app_db):
    oid = seed["orcamento_l1_id"]
    nome, _pid = _seed_amb(app_db, oid)
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{nome}/pe/renegociar",
                      {"pool_ambiente_id": 999999, "renegociar": True})
    assert st == 400 and not body["ok"]


def test_conclusao_11c_ignora_ambiente_fora_do_orcamento(http_client_factory, seed, app_db):
    # QA Vera (achado alto): ambiente no pool mas FORA do orçamento do contrato (fluxo real de
    # "remover ambiente") não aparece na tabela da 11c — não pode contar no gate de conclusão.
    oid = seed["orcamento_l1_id"]
    nome, pid = _seed_amb(app_db, oid, budget=80000.0)
    db = app_db.get_session()
    orf = app_db.PoolAmbiente(nome="Orfao", nome_exibicao="Órfão", xml_path="fake/orf.xml",
                              ambientes_json="{}", projeto_id=nome,
                              budget_total=10000.0, order_total=4000.0)
    db.add(orf)   # órfão: sem OrcamentoAmbiente e sem PE
    # PE carregado para TODOS os ambientes vinculados ao orçamento (o seed/os testes anteriores
    # trazem outros além do nosso; upsert — o módulo compartilha o banco)
    for oa in db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).all():
        ja = (db.query(app_db.ArquivoPE)
                .filter_by(projeto_nome=nome, pool_ambiente_id=oa.pool_ambiente_id,
                           formato="xml_pe").first())
        if ja is None:
            db.add(app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=oa.pool_ambiente_id,
                                    formato="xml_pe", valor_atualizado=30000.0, valor_venda=80000.0))
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{nome}/ciclo/11c/concluir",
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"], body   # órfão não trava; o ambiente vendido tem PE


# Achado da Vera (2026-08-26, E2E): ambiente RETIDO bloqueia upload de PE (correto), mas antes
# também travava a conclusão da 11c, que exigia PE de TODOS os ambientes do orçamento — deadlock
# entre as duas features. Mesmo princípio do teste acima (ambiente fora do orçamento): retido não
# entra no universo, não trava a conclusão.
def test_conclusao_11c_ignora_ambiente_retido(http_client_factory, seed, app_db):
    import mod_retido
    oid = seed["orcamento_l1_id"]
    nome, pid = _seed_amb(app_db, oid, budget=80000.0)
    db = app_db.get_session()
    # 2º ambiente do orçamento — vai ficar RETIDO, sem PE.
    pa2 = app_db.PoolAmbiente(nome="Suite", nome_exibicao="Suíte", xml_path="fake/suite.xml",
                              ambientes_json="{}", projeto_id=nome,
                              budget_total=50000.0, order_total=20000.0)
    db.add(pa2); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa2.id, ordem=2))
    parcela = app_db.ParcelaProjeto(projeto_nome=nome, ordem=1, status=mod_retido.STATUS_RETIDO,
                                    fracao_val_cont=1.0, val_cont_congelado=50000.0,
                                    orcamento_id=oid)
    db.add(parcela); db.flush()
    db.add(app_db.ParcelaAmbiente(parcela_id=parcela.id, pool_ambiente_id=pa2.id))
    # PE só pro ambiente NÃO retido (pid) — pa2 (retido) fica sem PE de propósito.
    for oa in db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).all():
        if oa.pool_ambiente_id == pa2.id:
            continue
        ja = (db.query(app_db.ArquivoPE)
                .filter_by(projeto_nome=nome, pool_ambiente_id=oa.pool_ambiente_id,
                           formato="xml_pe").first())
        if ja is None:
            db.add(app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=oa.pool_ambiente_id,
                                    formato="xml_pe", valor_atualizado=30000.0, valor_venda=80000.0))
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{nome}/ciclo/11c/concluir",
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"], body   # retido não trava; o ambiente não-retido tem PE
