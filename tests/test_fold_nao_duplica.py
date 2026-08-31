"""FASE 2 — prova de NÃO-DUPLICAÇÃO: foldar Montagem/Garantia na Marg_Cont (visão, mod_provisoes)
não altera DRE/Balanço nem cria lançamentos. mod_contabil é o único que escreve no razão."""
import mod_contabil as mc
import mod_provisoes as mp


def _cfg():
    return {"provisoes_contabeis": {"montagem_pct": 8.0, "garantia_pct": 0.5},
            "provisoes": {"assist_pct": 0.0}}


def test_fold_nao_altera_dre_nem_balanco(app_db):
    """DRE/Balanço fotografados antes e depois de rodar o fold (puro) são idênticos; nº de
    lançamentos inalterado. mod_provisoes não recebe db — não pode tocar o razão."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 80)
    V = 10000.0
    mc.registrar_evento(db, "loja", 80, "faturamento", V, projeto_id="PZ")           # receita
    mc.constituir_provisoes_venda(db, "loja", 80, "PZ", V, _cfg(), ref_base="p:1")    # 800 + 50
    db.commit()
    dre_antes = mc.dre(db, "loja", 80)
    bal_antes = mc.balanco(db, "loja", 80)
    n_antes = db.query(mc.Lancamento).filter_by(owner_tipo="loja", owner_id=80).count()

    # roda TODO o caminho de visão do fold (base VAVO = V, como a constituição)
    r = mp.provisoes_orcamento({"CFO": 3000.0, "Val_Liq": 6000.0, "VAVO": V,
                                "Prov_Imp": 0.0, "Val_Cont": 12000.0}, _cfg())
    mp.cust_var_marg_cont(3000.0, 6000.0, mp.itens_provisao(r))

    dre_depois = mc.dre(db, "loja", 80)
    bal_depois = mc.balanco(db, "loja", 80)
    n_depois = db.query(mc.Lancamento).filter_by(owner_tipo="loja", owner_id=80).count()
    db.close()
    assert dre_antes == dre_depois
    assert bal_antes == bal_depois
    assert n_antes == n_depois


def test_dre_ja_continha_montagem_garantia_e_fold_bate(app_db):
    """FASE D2: o fold não adiciona custo ao mundo. A constituição é DIFERIDA (não toca a DRE) — o valor
    exibido na visão (Prov_Mont+Prov_Gar) é exatamente o constituído no razão (Provisões 2.1.04.x)."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 81)
    s = lambda cod: mc.saldo_conta(db, "loja", 81, db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=81, codigo=cod).first().id)
    V = 10000.0
    mc.constituir_provisoes_venda(db, "loja", 81, "PY", V, _cfg(), ref_base="p:1")    # 800/50, assist 0
    db.commit()
    dre = mc.dre(db, "loja", 81)
    r = mp.provisoes_orcamento({"CFO": 0.0, "Val_Liq": 1.0, "VAVO": V, "Prov_Imp": 0.0,
                                "Val_Cont": 12000.0}, _cfg())   # base VAVO = V; Val_Cont diferente (Cust_Fin>0)
    db.close()
    assert r["Prov_Mont"] == 800.0 and r["Prov_Gar"] == 50.0    # 8% / 0,5% × 10000 VAVO
    assert dre["constituicao_provisoes"] == 0.0                 # FASE D2: constituição não toca a DRE (só a NF-e)
    # a visão bate com o constituído no razão (montagem 2.1.04.02, garantia 2.1.04.03)
    assert s("2.1.04.02") == r["Prov_Mont"] and s("2.1.04.03") == r["Prov_Gar"]


def test_constituicao_usa_vavo_nao_val_cont(app_db, seed, monkeypatch):
    """A constituição no fechamento reflete o breakdown do motor (base VAVO p/ montagem/assist/garantia,
    NÃO Val_Cont). O custo financeiro (Val_Cont − VAVO) é DIFERIDO pelo ramo (Fatia B): Total Flex é
    financiamento da loja (capital próprio) → juros a apropriar (1.1.07 × 2.1.07), sem despesa no contrato."""
    import main, types, json
    # (1) o motor usa VAVO (90000), não Val_Cont (99000): montagem 8%→7200, garantia 0,5%→450, assist 3%→2700
    r = mp.provisoes_orcamento({"CFO": 0.0, "Val_Liq": 1.0, "VAVO": 90000.0, "Prov_Imp": 0.0,
                                "Val_Cont": 99000.0},
                               {"provisoes": {"assist_pct": 3.0},
                                "provisoes_contabeis": {"montagem_pct": 8.0, "garantia_pct": 0.5}})
    assert r["Assist_Orc"] == 2700.0 and r["Prov_Mont"] == 7200.0 and r["Prov_Gar"] == 450.0

    # (2) o wire constitui EXATAMENTE os valores do motor + custo financeiro (Val_Cont − VAVO)
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    loja = db.get(app_db.Loja, seed["loja1_id"]); loja.modulos_ativos = None
    orcx = db.query(app_db.Orcamento).filter_by(loja_id=seed["loja1_id"]).first()
    orcx.valor_total = 99000.0   # Val_Cont → Cust_Fin = 99000 − 90000 = 9000
    # "tipo" (não "codigo") é a chave que o frontend de fato manda (mod_recebiveis.ramo_por_tipo,
    # achado do usuário 2026-08-13) — "tf" (Total Flex) mapeia pro ramo LOJA (financiamento direto).
    # Com "codigo" (chave morta), _ramo_financeiro_efetivo caía em "avista" e o achado ACHADO-02/03
    # (passo 10) expôs isso: main.py agora usa a tabela por ramo, que não trata mais "avista" como
    # sinônimo de "loja" (o `if`/`else` binário antigo tratava).
    orcx.forma_pagamento = json.dumps({"tipo": "tf"})   # ramo LOJA (financiamento direto)
    db.commit(); orc_id = orcx.id; db.close()
    brk = dict(r); brk["VAVO"] = 90000.0
    monkeypatch.setattr(main, "_negociacao_breakdown", lambda orc, db: brk)
    main._fin_provisoes_venda_seguro(types.SimpleNamespace(loja_id=seed["loja1_id"], id=orc_id),
                                     "PZproj", "prov:testvavo")
    db = app_db.get_session()
    def saldo(cod):
        c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
        return round(abs(mc.saldo_conta(db, ot, oid, c.id, None, None)), 2)
    assert saldo("2.1.04.05") == 2700.0 and saldo("2.1.04.02") == 7200.0 and saldo("2.1.04.03") == 450.0
    # custo financeiro (Val_Cont − VAVO = 9000) — ramo LOJA (Total Flex): juros a apropriar, DIFERIDO
    assert saldo("1.1.07") == 9000.0 and saldo("2.1.07") == 9000.0
    assert saldo("5.5.03") == 0.0   # não é mais despesa direta no contrato (Fatia B difere o cust_fin)
    db.close()
