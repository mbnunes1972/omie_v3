import mod_provisoes
import mod_orcamento_params


def test_default_tem_estrutura_completa():
    c = mod_provisoes.config_financeira_default()
    assert set(c.keys()) == {"defaults_negociacao", "provisoes", "provisoes_contabeis",
                             "comissao_vendas", "cronograma_padrao", "cronograma_formato",
                             "aprovacao_financeira",   # Fatia C: limites AF1/AF2
                             "folha",                  # Fase 5: adiantamento oficial
                             "prazo_contratual_dias_uteis",   # Fatia 3: promessa formal (dias úteis)
                             "agenda",                 # Agenda da Loja Fatia 0: capacidade + calendário útil
                             "prazo_antecipacao",      # Recebimento de Venda (2026-08-07): dias Cartão/Aymoré
                             "amortizacoes", "juros_mensal",   # Simulador de Modelo de Negócios (Sessão 185)
                             "fuso_horario"}   # ACHADO-48: fuso do dono do livro, default America/Sao_Paulo
    assert c["aprovacao_financeira"] == {"limite_af1_pct": 1.0, "limite_af2_pct": 2.0}
    assert c["provisoes"]["frete_fab_pct"] == 0.0
    assert c["provisoes_contabeis"] == {"montagem_pct": 0.0, "garantia_pct": 0.0, "comissao_pct": 0.0}   # v6 §6.4 / v8 Config
    assert c["comissao_vendas"]["limitador_desconto"]["ativo"] is False


def test_default_tem_prazo_contratual_dias_uteis():
    import mod_provisoes
    cfg = mod_provisoes.config_financeira_default()
    assert cfg.get("prazo_contratual_dias_uteis") == 50


def test_validar_aceita_default():
    assert mod_provisoes.validar_config_financeira(mod_provisoes.config_financeira_default()) == []


def test_validar_rejeita_percentual_negativo():
    c = mod_provisoes.config_financeira_default()
    c["provisoes"]["com_adm_pct"] = -1.0
    erros = mod_provisoes.validar_config_financeira(c)
    assert erros and any("negativ" in e.lower() for e in erros)


def test_validar_rejeita_faixa_sem_pct():
    c = mod_provisoes.config_financeira_default()
    c["comissao_vendas"]["faixas_comissao"] = [{"venda_ate": 1000.0}]
    erros = mod_provisoes.validar_config_financeira(c)
    assert erros


def _cfg_comissao():
    c = mod_provisoes.config_financeira_default()
    c["comissao_vendas"]["faixas_comissao"] = [
        {"venda_ate": 10000.0, "pct": 1.0},   # < 10k
        {"venda_ate": 30000.0, "pct": 2.0},   # 10k–30k
        {"venda_ate": None,    "pct": 3.0},   # ≥ 30k
    ]
    c["comissao_vendas"]["limitador_desconto"] = {
        "ativo": True, "base_desconto": "Desc_Orc",
        "limites": [{"desconto_acima_de": 5.0, "redutor_pct": 50.0},
                    {"desconto_acima_de": 10.0, "redutor_pct": 80.0}],
    }
    return c


def test_faixa_por_venda():
    c = _cfg_comissao()
    assert mod_provisoes.resolver_comissao_venda(c, 5000.0, 0.0) == 1.0
    assert mod_provisoes.resolver_comissao_venda(c, 20000.0, 0.0) == 2.0
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 0.0) == 3.0


def test_redutor_por_desconto():
    c = _cfg_comissao()
    # faixa 3% (venda 50k), desconto 12% > 10% → redutor 80% → 3 × 0.2 = 0.6
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 12.0) == 0.6
    # desconto 7% → redutor 50% → 3 × 0.5 = 1.5
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 7.0) == 1.5


def test_limitador_desligado_nao_reduz():
    c = _cfg_comissao()
    c["comissao_vendas"]["limitador_desconto"]["ativo"] = False
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 12.0) == 3.0


def test_provisoes_e_margem():
    siglas = {"CFO": 1000.0, "Val_Liq": 2000.0, "VAVO": 2500.0, "Prov_Imp": 0.0}
    c = mod_provisoes.config_financeira_default()
    c["provisoes"].update({"frete_fab_pct": 10.0, "com_adm_pct": 5.0,
                           "frete_loc_pct": 2.0})
    r = mod_provisoes.provisoes_orcamento(siglas, c, out_forn=300.0, com_venda_pct=1.0)
    assert r["Frete_Fab_Orc"] == 100.0      # 10% × 1000 CFO
    assert r["Com_Adm_Orc"] == 100.0        # 5% × 2000 Val_Liq
    assert r["Com_Venda_Orc"] == 20.0       # 1% × 2000 Val_Liq
    assert r["Frete_Loc_Orc"] == 50.0       # 2% × 2500 VAVO
    assert r["Out_Forn"] == 300.0
    # Cust_Var = 1000 CFO + 300 Out + 100 + 100 + 20 + 0 + 0 + 50 + 0 + 0 + 0 Prov_Imp = 1570
    assert r["Cust_Var"] == 1570.0
    # Marg_Cont = (2000 - 1570)/2000 = 0.215
    assert r["Marg_Cont"] == 0.215


def test_margem_negativa_e_val_liq_zero():
    siglas = {"CFO": 5000.0, "Val_Liq": 1000.0, "VAVO": 1000.0, "Prov_Imp": 0.0}
    c = mod_provisoes.config_financeira_default()
    r = mod_provisoes.provisoes_orcamento(siglas, c)
    assert r["Marg_Cont"] < 0                       # Cust_Var (5000) > Val_Liq (1000)
    siglas0 = {"CFO": 0.0, "Val_Liq": 0.0, "VAVO": 0.0, "Prov_Imp": 0.0}
    assert mod_provisoes.provisoes_orcamento(siglas0, c)["Marg_Cont"] == 0.0


def test_parametros_default_loja_usa_config():
    cfg = {"defaults_negociacao": {"comissao_arq_pct": 12.0, "fidelidade_pct": 3.0, "carga_trib_pct": 8.0}}
    p = mod_orcamento_params.parametros_default_loja(cfg)
    assert p["comissao_arq_pct"] == 12.0
    assert p["fidelidade_pct"] == 3.0
    assert p["carga_trib"] == 8.0
    # chaves do PARAMETROS_DEFAULT preservadas
    assert "incluir_custos" in p


def test_parametros_default_loja_sem_config_cai_no_default():
    p = mod_orcamento_params.parametros_default_loja(None)
    # incluir_custos nasce True (padrão inicial do projeto); o resto segue o PARAMETROS_DEFAULT
    assert p == dict(mod_orcamento_params.PARAMETROS_DEFAULT, incluir_custos=True)


def test_validar_rejeita_redutor_acima_de_100():
    c = mod_provisoes.config_financeira_default()
    c["comissao_vendas"]["limitador_desconto"] = {
        "ativo": True, "base_desconto": "Desc_Orc",
        "limites": [{"desconto_acima_de": 5.0, "redutor_pct": 150.0}],
    }
    erros = mod_provisoes.validar_config_financeira(c)
    assert erros and any("100" in e for e in erros)


def test_itens_provisao_mapeia_rubricas():
    # 12 rubricas após o fold (Prov_Mont/Prov_Gar). Breakdown ANTIGO (sem as 2 novas) → 0.0 (retro-compat).
    d = {"Frete_Fab_Orc": 100.0, "Com_Adm_Orc": 200.0, "Com_Venda_Orc": 0.0,
         "Com_Med_Orc": 0.0, "Com_Proj_Exec_Orc": 0.0, "Frete_Loc_Orc": 50.0,
         "Assist_Orc": 0.0, "Ins_Loc_Orc": 0.0, "Prov_Imp": 0.0, "Out_Forn": 300.0}
    itens = mod_provisoes.itens_provisao(d)
    assert set(itens.keys()) == {"frete_fab","com_adm","com_venda","com_med",
        "com_proj_exec","frete_loc","assist","ins_loc","prov_imp","out_forn","prov_mont","prov_gar",
        # F0: + custos adicionais + custo financeiro (viram linha; chave ausente no d antigo → 0)
        "com_arq","pro_fid","cust_via","brinde","cust_esp","custo_financeiro"}
    assert itens["frete_fab"] == 100.0 and itens["out_forn"] == 300.0 and itens["frete_loc"] == 50.0
    assert itens["com_arq"] == 0.0 and itens["custo_financeiro"] == 0.0   # d antigo sem as chaves → 0
    assert itens["prov_mont"] == 0.0 and itens["prov_gar"] == 0.0   # chave ausente no d antigo → 0


def test_custos_adicionais_e_cust_fin_aparecem_sem_dobrar_no_cust_var():
    # F0 (bug ①): os 4 custos adicionais (Com.Arquiteto/Fidelidade/Viagem/Brinde) + Custo Financeiro
    # entram em itens_provisao → viram LINHA no painel da AF. Mas cust_var_marg_cont NÃO os soma no
    # Cust_Var (são Cust_Ad, já descontados do Val_Liq) — senão DOBRAM o custo e corrompem a margem.
    d = {"Frete_Fab_Orc": 100.0, "Com_Adm_Orc": 0.0, "Com_Venda_Orc": 0.0, "Com_Med_Orc": 0.0,
         "Com_Proj_Exec_Orc": 0.0, "Frete_Loc_Orc": 0.0, "Assist_Orc": 0.0, "Ins_Loc_Orc": 0.0,
         "Prov_Imp": 0.0, "Out_Forn": 0.0, "Prov_Mont": 0.0, "Prov_Gar": 0.0,
         "Com_Arq": 500.0, "Pro_Fid": 300.0, "Cust_Via": 200.0, "Bri": 100.0,
         "Cust_Esp": 400.0, "Cust_Fin": 700.0}
    itens = mod_provisoes.itens_provisao(d)
    # (a) aparecem como rubricas
    assert itens["com_arq"] == 500.0 and itens["pro_fid"] == 300.0
    assert itens["cust_via"] == 200.0 and itens["brinde"] == 100.0
    assert itens["cust_esp"] == 400.0
    assert itens["custo_financeiro"] == 700.0
    # (b) NÃO entram no Cust_Var: CFO 1000 + frete_fab 100 = 1100 (sem os 1800 de adicionais/fin)
    cv, _ = mod_provisoes.cust_var_marg_cont(cfo=1000.0, val_liq=5000.0, itens=itens)
    assert cv == 1100.0


# ── FASE 2: fold de Montagem/Garantia no Cust_Var/Marg_Cont (base = VAVO, convenção canônica) ──
def _cfg_fold():
    c = mod_provisoes.config_financeira_default()
    c["provisoes"].update({"frete_fab_pct": 10.0, "com_adm_pct": 5.0, "frete_loc_pct": 2.0})
    c["provisoes_contabeis"].update({"montagem_pct": 8.0, "garantia_pct": 0.5})
    return c


def test_fold_montagem_garantia_no_cust_var():
    # base = VAVO (2500), NÃO Val_Cont — mesmo com Cust_Fin>0 (Val_Cont=2600), o fold usa VAVO.
    siglas = {"CFO": 1000.0, "Val_Liq": 2000.0, "VAVO": 2500.0, "Prov_Imp": 0.0, "Val_Cont": 2600.0}
    r = mod_provisoes.provisoes_orcamento(siglas, _cfg_fold(), out_forn=300.0, com_venda_pct=1.0)
    assert r["Prov_Mont"] == 200.0          # 8%   × 2500 VAVO
    assert r["Prov_Gar"] == 12.5            # 0,5% × 2500 VAVO
    assert r["Cust_Var"] == 1782.5          # 1570 (pré-fold) + 200 + 12,5
    assert r["Marg_Cont"] == round((2000.0 - r["Cust_Var"]) / 2000.0, 4)


def test_fold_decomposicao_aditiva():
    siglas = {"CFO": 1000.0, "Val_Liq": 2000.0, "VAVO": 2500.0, "Prov_Imp": 0.0, "Val_Cont": 2600.0}
    com = mod_provisoes.provisoes_orcamento(siglas, _cfg_fold(), out_forn=300.0, com_venda_pct=1.0)
    c_sem = _cfg_fold(); c_sem["provisoes_contabeis"].update({"montagem_pct": 0.0, "garantia_pct": 0.0})
    sem = mod_provisoes.provisoes_orcamento(siglas, c_sem, out_forn=300.0, com_venda_pct=1.0)
    assert com["Cust_Var"] == round(sem["Cust_Var"] + com["Prov_Mont"] + com["Prov_Gar"], 2)
    assert sem["Prov_Mont"] == 0.0 and sem["Prov_Gar"] == 0.0
    assert sem["Cust_Var"] == 1570.0 and sem["Marg_Cont"] == 0.215   # idêntico ao mundo pré-fold


def test_fold_vavo_zero_e_pct_zero():
    base = {"CFO": 1000.0, "Val_Liq": 2000.0, "VAVO": 2500.0, "Prov_Imp": 0.0, "Val_Cont": 2600.0}
    r_zero_vavo = mod_provisoes.provisoes_orcamento(dict(base, VAVO=0.0), _cfg_fold())
    c0 = _cfg_fold(); c0["provisoes_contabeis"].update({"montagem_pct": 0.0, "garantia_pct": 0.0})
    r_zero_pct = mod_provisoes.provisoes_orcamento(base, c0, out_forn=300.0, com_venda_pct=1.0)
    assert r_zero_vavo["Prov_Mont"] == 0.0 and r_zero_vavo["Prov_Gar"] == 0.0   # VAVO 0 → fold 0
    assert r_zero_pct["Prov_Mont"] == 0.0 and r_zero_pct["Prov_Gar"] == 0.0     # pct 0 → fold 0
    assert r_zero_pct["Cust_Var"] == 1570.0


def test_fold_bate_com_constituicao_contabil():
    import mod_contabil
    V = 12345.67   # VAVO "feio"
    r = mod_provisoes.provisoes_orcamento({"CFO": 0.0, "Val_Liq": 1.0, "VAVO": V, "Prov_Imp": 0.0,
                                           "Val_Cont": 99999.0}, _cfg_fold())
    # base VAVO e MESMO arredondamento da constituição no razão (round(VAVO*pct/100, 2))
    pcts = mod_contabil.pcts_provisao_venda(_cfg_fold())
    assert r["Prov_Mont"] == round(V * pcts["montagem"] / 100.0, 2)
    assert r["Prov_Gar"] == round(V * pcts["garantia"] / 100.0, 2)


def test_provisoes_base_vavo_todas():
    # convenção canônica: Montagem/Garantia/Assistência/Frete Local/Insumos Locais → base VAVO
    siglas = {"CFO": 1000.0, "Val_Liq": 2000.0, "VAVO": 2000.0, "Prov_Imp": 0.0, "Val_Cont": 3000.0}
    c = mod_provisoes.config_financeira_default()
    c["provisoes"].update({"assist_pct": 3.0, "frete_loc_pct": 2.0, "ins_loc_pct": 1.0})
    c["provisoes_contabeis"].update({"montagem_pct": 8.0, "garantia_pct": 0.5})
    r = mod_provisoes.provisoes_orcamento(siglas, c)
    assert r["Assist_Orc"] == 60.0      # 3%   × 2000 VAVO
    assert r["Frete_Loc_Orc"] == 40.0   # 2%   × 2000 VAVO
    assert r["Ins_Loc_Orc"] == 20.0     # 1%   × 2000 VAVO
    assert r["Prov_Mont"] == 160.0      # 8%   × 2000 VAVO
    assert r["Prov_Gar"] == 10.0        # 0,5% × 2000 VAVO


def test_cust_var_marg_cont_soma_prov_mont_gar():
    # o recálculo do Revisa (aprovador editou rubricas) inclui montagem/garantia
    itens = {"frete_fab": 100.0, "prov_mont": 208.0, "prov_gar": 13.0}   # Σ = 321
    cv, mc = mod_provisoes.cust_var_marg_cont(cfo=1000.0, val_liq=2000.0, itens=itens)
    assert cv == 1321.0
    assert mc == round((2000.0 - 1321.0) / 2000.0, 4)


def test_cust_var_marg_cont_recalcula():
    itens = {"frete_fab": 100.0, "com_adm": 200.0, "out_forn": 300.0}  # Σ = 600
    cv, mc = mod_provisoes.cust_var_marg_cont(cfo=4000.0, val_liq=9000.0, itens=itens)
    assert cv == 4600.0                      # 4000 + 600
    assert mc == round((9000.0 - 4600.0)/9000.0, 4)
    # val_liq 0 -> margem 0
    assert mod_provisoes.cust_var_marg_cont(0.0, 0.0, {})[1] == 0.0
