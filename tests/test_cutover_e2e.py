# tests/test_cutover_e2e.py
# Task 2: testes E2E para o endpoint POST /api/orcamentos/<id>/negociacao-preview
# Task 3: _recalcular_orcamento + persistência autoritativa

def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c

def test_preview_devolve_valores_do_motor(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    st, body = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
    assert st == 200 and body["ok"]
    s = body["sombra"]
    # chaves da cadeia completa presentes
    for k in ("VBVO", "VAVO", "Val_Liq", "Markup", "Desc_Tot", "Com_Arq", "Pro_Fid", "Cust_Ad", "Val_Cont"):
        assert k in s
    # ACHADO-63/F2-32 (06/09): Fatias 2/3 da tela consomem estas quatro direto do motor, nunca
    # recalculadas em JS — a rota tem que entregá-las no sombra (_negociacao_breakdown devolve o
    # dict do motor inteiro, sem filtro de chaves).
    for k in ("Desc_Efetivo", "Cust_Via_Recup", "Bri_Recup", "Cust_Esp_Recup"):
        assert k in s
    assert "ambientes" in body

def test_preview_fora_do_escopo_404(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")           # loja 2
    st, body = c.post(f"/api/orcamentos/{seed['orcamento_l1_id']}/negociacao-preview", {})
    assert st == 404 and body.get("ok") is False


# ── Task 3 ─────────────────────────────────────────────────────────────────────

def test_save_margens_grava_valor_do_motor(http_client_factory, seed, app_db):
    """Garante que POST /margens grava valor_total/valor_liquido pelo motor com
    valores não-zero (asserção significativa — o orçamento tem ambiente real)."""
    oid = seed["orcamento_l1_id"]

    # ── 1. Semear um PoolAmbiente e vinculá-lo ao orçamento ──────────────────
    db = app_db.get_session()
    orc_seed = db.get(app_db.Orcamento, oid)
    projeto_id = orc_seed.projeto_id
    pa = app_db.PoolAmbiente(
        nome="Cozinha",
        nome_exibicao="Cozinha",
        xml_path="fake/path.xml",
        ambientes_json="{}",
        projeto_id=projeto_id,
        budget_total=10000.0,
        order_total=4000.0,
    )
    db.add(pa); db.flush()
    oa = app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1)
    db.add(oa)
    db.commit()
    db.close()

    # ── 2. Salvar margens (desconto 0, sem custos) ───────────────────────────
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 0})
    assert st == 200, f"esperado 200, obtido {st}: {body}"

    # ── 3. Verificar persistência com valores reais (não-zero) ───────────────
    db2 = app_db.get_session()
    o = db2.get(app_db.Orcamento, oid)
    # VAVO deve refletir o budget_total do ambiente semeado
    assert abs((o.vavo or 0) - 10000.0) < 0.5, f"vavo={o.vavo} esperado ≈10000"
    # val_liq > 0 prova que o motor rodou com dados reais (não retornou 0 trivialmente)
    assert (o.val_liq or 0) > 0, f"val_liq={o.val_liq} deveria ser > 0"
    # valor_liquido == val_liq (consistência: motor grava autoritativamente)
    assert abs((o.valor_liquido or 0) - (o.val_liq or 0)) < 0.02, (
        f"valor_liquido={o.valor_liquido} != val_liq={o.val_liq}")
    # valor_total == val_cont (consistência)
    assert abs((o.valor_total or 0) - (o.val_cont or 0)) < 0.02, (
        f"valor_total={o.valor_total} != val_cont={o.val_cont}")
    db2.close()

def test_patch_nao_aceita_valor_total_do_frontend(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    c.patch(f"/orcamentos/{oid}/valor", {"valor_total": 999999.0, "valor_liquido": 888888.0})
    db = app_db.get_session(); o = db.get(app_db.Orcamento, oid)
    assert (o.valor_total or 0) != 999999.0      # ignorado/recalculado
    db.close()

def test_preview_ambientes_tem_id_e_vava(http_client_factory, seed, app_db):
    """O preview devolve, por ambiente, o pool_ambiente_id (para o frontend casar as
    células) e o VAVA (à vista por ambiente)."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    projeto_id = db.get(app_db.Orcamento, oid).projeto_id
    pa = app_db.PoolAmbiente(nome="Sala", nome_exibicao="Sala", xml_path="x.xml",
                             ambientes_json="{}", projeto_id=projeto_id,
                             budget_total=8000.0, order_total=3000.0)
    db.add(pa); db.flush()
    pid = pa.id
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pid, ordem=1))
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
    assert st == 200 and body["ok"]
    # robusto a poluição de seed entre testes: localiza O MEU ambiente pelo id
    mine = [a for a in body["ambientes"] if a.get("id") == pid]
    assert len(mine) == 1, f"ambiente {pid} não encontrado em {body['ambientes']}"
    assert abs(mine[0]["VAVA"] - 8000.0) < 0.5      # desconto 0 ⇒ VAVA = budget


def test_preview_ignora_overrides_do_corpo(http_client_factory, seed, app_db):
    """O preview lê só dos salvos: enviar params/desc_orc no corpo NÃO altera o resultado."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    pj = db.get(app_db.Orcamento, oid).projeto_id
    pa = app_db.PoolAmbiente(nome="A", nome_exibicao="A", xml_path="a.xml",
                             ambientes_json="{}", projeto_id=pj, budget_total=10000.0, order_total=4000.0)
    db.add(pa); db.flush(); db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, base = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
    st2, comov = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {"desc_orc": 50, "params": {"comissao_arq_ativa": True, "comissao_arq_pct": 99}})
    assert st == 200 and st2 == 200
    assert base["sombra"]["VAVO"] == comov["sombra"]["VAVO"]   # overrides ignorados


# ── Task 4 (task-3-brief): saves recalculam e devolvem o breakdown maiúsculo ──

def _seed_amb(app_db, oid, budget=10000.0):
    db = app_db.get_session()
    pj = db.get(app_db.Orcamento, oid).projeto_id
    pa = app_db.PoolAmbiente(nome="Z", nome_exibicao="Z", xml_path="z.xml", ambientes_json="{}",
                             projeto_id=pj, budget_total=budget, order_total=budget*0.4)
    db.add(pa); db.flush(); pid = pa.id
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pid, ordem=1))
    db.commit(); db.close(); return pid

def test_save_margens_retorna_breakdown_maiusculo(http_client_factory, seed, app_db):
    oid = seed["orcamento_l1_id"]; _seed_amb(app_db, oid)
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 10})
    assert st == 200
    s = body["sombra"]
    for k in ("VBNO", "VAVO", "Cust_Via", "Bri", "Val_Liq", "ambientes"):
        assert k in s, f"falta {k} no breakdown: {list(s)}"
    assert s["ambientes"][0]["id"] is not None

def test_save_descontos_retorna_breakdown(http_client_factory, seed, app_db):
    oid = seed["orcamento_l1_id"]; pid = _seed_amb(app_db, oid)
    c = _login(http_client_factory, "dir_l1")
    st, body = c.put(f"/api/orcamentos/{oid}/descontos", {"descontos": {str(pid): 5}})
    assert st == 200 and "VAVO" in body["sombra"]


def test_breakdown_distribui_brinde_viagem_pelo_pool(http_client_factory, seed, app_db):
    """Projeto com 7 ambientes no pool; orçamento com 3 → Bri = 3/7 do total; viagem proporcional."""
    import json
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    o = db.get(app_db.Orcamento, oid); pj = o.projeto_id
    proj = db.query(app_db.Projeto).filter_by(nome_safe=pj).first()
    pj_orig = proj.parametros_json                  # captura antes de alterar
    proj.parametros_json = json.dumps({"incluir_custos": False, "fora_da_sede": True,
        "custo_viagem": 700, "brinde_ativo": True, "brinde": 700})
    # limpa PoolAmbiente + vínculos anteriores (testes anteriores do módulo usam _seed_amb)
    for lk in db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).all():
        db.delete(lk)
    for pa in db.query(app_db.PoolAmbiente).filter_by(projeto_id=pj).all():
        db.delete(pa)
    db.flush()
    pool = []
    for i in range(7):
        pa = app_db.PoolAmbiente(nome=f"A{i}", nome_exibicao=f"A{i}", xml_path="x.xml",
            ambientes_json="{}", projeto_id=pj, budget_total=10000.0, order_total=4000.0)
        db.add(pa); db.flush(); pool.append(pa.id)
    for pid in pool[:3]:                              # orçamento = 3 dos 7
        db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pid, ordem=1))
    db.commit(); db.close()

    try:
        c = _login(http_client_factory, "dir_l1")
        st, body = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
        assert st == 200
        s = body["sombra"]
        assert abs(s["Bri"] - 300.0) < 0.5            # 3/7 × 700
        assert abs(s["Cust_Via"] - 300.0) < 0.5       # 700 × 30000/70000
    finally:
        # teardown: remove os 7 PoolAmbiente e 3 OrcamentoAmbiente criados por este
        # teste, e restaura parametros_json — deixa o banco como estava antes
        db2 = app_db.get_session()
        for lk in db2.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).all():
            db2.delete(lk)
        for pa in db2.query(app_db.PoolAmbiente).filter_by(projeto_id=pj).all():
            db2.delete(pa)
        proj2 = db2.query(app_db.Projeto).filter_by(nome_safe=pj).first()
        proj2.parametros_json = pj_orig
        db2.commit(); db2.close()
