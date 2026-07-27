"""FASE D2 · Fase 3 — matching pleno na NF-e: reconhecer_despesas_nfe reconhece TODAS as despesas
planejadas (10 rubricas) de uma vez, debitando a conta FORMAL da rubrica (formalismo S109: CMV
5.1.x, Custo de Serviço 5.2.x ou Despesas Comerciais 5.3.x) × baixa do ativo diferido 1.1.06.0X.
A Provisão (2.1.04.0X) SOBREVIVE à NF-e. Idempotente. Impostos NÃO entram (têm rota própria)."""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


# rubrica -> (ativo diferido 1.1.06, provisão 2.1.04, despesa reconhecida na NF-e)
RUBRICAS = {
    "montagem":            ("1.1.06.02", "2.1.04.02", "5.2.01"),
    "garantia":            ("1.1.06.03", "2.1.04.03", "5.2.12"),
    "assistencia":         ("1.1.06.05", "2.1.04.05", "5.2.13"),
    "custo_fabrica":       ("1.1.06.06", "2.1.04.06", "5.1.01"),
    "frete_fabrica":       ("1.1.06.07", "2.1.04.07", "5.1.02"),
    "frete_local":         ("1.1.06.08", "2.1.04.08", "5.2.08"),
    "insumos":             ("1.1.06.09", "2.1.04.09", "5.2.09"),
    "com_medidor":         ("1.1.06.10", "2.1.04.10", "5.3.18"),
    "com_proj_exec":       ("1.1.06.11", "2.1.04.11", "5.3.19"),
    "retencao_com_vendas": ("1.1.06.12", "2.1.04.12", "5.3.20"),
}
VALORES = {"montagem": 1000.0, "garantia": 200.0, "assistencia": 300.0, "custo_fabrica": 60000.0,
           "frete_fabrica": 400.0, "frete_local": 150.0, "insumos": 100.0, "com_medidor": 250.0,
           "com_proj_exec": 350.0, "retencao_com_vendas": 500.0}


def _contrato(db, ot, oid, proj):
    mc.constituir_provisoes_fechamento(db, ot, oid, proj, dict(VALORES, impostos=5000.0), ref_base="pf:" + proj)


def test_matching_reconhece_todas_as_despesas_uma_vez(app_db):
    db = app_db.get_session(); ot, oid = "loja", 720; mc.seed_plano(db, ot, oid)
    _contrato(db, ot, oid, "P")
    # antes da NF-e: nada de despesa no resultado
    d0 = mc.dre(db, ot, oid)
    assert d0["cmv_csp"] == 0.0 and d0["constituicao_provisoes"] == 0.0
    out = mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P")
    assert out == VALORES
    for chave, (ativo, prov, desp) in RUBRICAS.items():
        assert _s(db, ot, oid, desp) == VALORES[chave]                       # despesa reconhecida (conta formal)
        assert _s(db, ot, oid, ativo) == 0.0                                 # ativo diferido baixado
        assert _s(db, ot, oid, prov) == VALORES[chave]                       # PROVISÃO sobrevive
    # 5.1.01 é o CMV da fábrica (pode somar outras origens; aqui só a fábrica)
    assert _s(db, ot, oid, "5.1.01") == 60000.0
    # DRE agora reflete os custos, cada um UMA vez — nos grupos FORMAIS (S109):
    # CMV+CSP = fábrica + frete fáb + montagem/garantia/assistência/frete local/insumos;
    # as comissões vão para Despesas Comerciais; a 5.6 (só ajustes) fica zerada.
    d = mc.dre(db, ot, oid)
    assert d["cmv_csp"] == 62150.0                                           # 60000+400+1000+200+300+150+100
    assert d["despesas_comerciais"] == 1100.0                                # 250+350+500 (comissões)
    assert d["constituicao_provisoes"] == 0.0                                # 5.6 = só Ajustes de Provisões
    assert d["deducoes"] == 0.0                                              # impostos NÃO entram no matching
    assert _s(db, ot, oid, "1.1.05") == 5000.0 and _s(db, ot, oid, "2.1.04.13") == 5000.0
    db.close()


def test_matching_por_fracao_difere_a_retida(app_db):
    """Desmembramento operacional (Fatia 4): com `fracao` < 1 (parte não retida), a NF-e reconhece só
    a fração ELEGÍVEL; o resto fica DIFERIDO no ativo 1.1.06. Ao LIBERAR (fração maior), a re-emissão
    reconhece só o DELTA. Σ ao final == constituído; mesma fração re-emitida é idempotente."""
    db = app_db.get_session(); ot, oid = "loja", 730; mc.seed_plano(db, ot, oid)
    _contrato(db, ot, oid, "P")
    # 1ª NF-e com 80% elegível (uma parcela retida vale 20%)
    out1 = mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P", fracao=0.8)
    for chave, (ativo, prov, desp) in RUBRICAS.items():
        assert round(out1[chave], 2) == round(VALORES[chave] * 0.8, 2)        # reconhece 80%
        assert round(_s(db, ot, oid, ativo), 2) == round(VALORES[chave] * 0.2, 2)  # 20% DIFERIDO
    # re-emitir a MESMA fração não reconhece de novo (idempotente por ref)
    assert mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P", fracao=0.8) == {}
    # obra libera → 100% elegível: a re-emissão reconhece só o DELTA (20%)
    out2 = mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P", fracao=1.0)
    for chave, (ativo, prov, desp) in RUBRICAS.items():
        assert round(out2[chave], 2) == round(VALORES[chave] * 0.2, 2)        # delta 20%
        assert round(_s(db, ot, oid, ativo), 2) == 0.0                        # ativo zerado
        assert round(_s(db, ot, oid, desp), 2) == VALORES[chave]              # total reconhecido
    db.close()


def test_matching_fracoes_proximas_nao_colidem(app_db):
    """Achado da Vera (🟠): frações próximas que antes caíam no mesmo bucket de ref (`f%04d`) agora
    reconhecem cada delta — o ref é pelo ALVO acumulado em centavos, não por fração truncada."""
    db = app_db.get_session(); ot, oid = "loja", 731; mc.seed_plano(db, ot, oid)
    _contrato(db, ot, oid, "P")
    a = mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P", fracao=0.59996)
    b = mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P", fracao=0.60004)
    # custo_fabrica = 60000 → 0.59996×60000=35997.60 ; 0.60004×60000=36002.40 → delta 4.80
    assert round(a["custo_fabrica"], 2) == 35997.60
    assert round(b["custo_fabrica"], 2) == 4.80                            # delta posta, não engolido
    assert round(_s(db, ot, oid, "5.1.01"), 2) == 36002.40                 # razão reflete o total
    db.close()


def test_matching_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 721; mc.seed_plano(db, ot, oid)
    _contrato(db, ot, oid, "P")
    mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P")
    out2 = mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P")   # 2ª vez (reproc. NF-e)
    assert out2 == {}                                                        # nada a reconhecer de novo
    assert _s(db, ot, oid, "5.1.01") == 60000.0                              # não duplicou o CMV
    assert _s(db, ot, oid, "5.2.01") == 1000.0                               # nem a montagem
    db.close()


def test_faturamento_cmv_foi_retirado():
    """O evento antigo faturamento_cmv (5.1.01 × 2.1.04.06) foi substituído pelo matching (× 1.1.06.06)."""
    assert "faturamento_cmv" not in mc.EVENTOS
    assert mc.EVENTOS["reconhecimento_despesa_custo_fabrica"][:2] == ("5.1.01", "1.1.06.06")
