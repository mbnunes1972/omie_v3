"""FASE B2 — eventos de dupla-partida: Adiantamento de Clientes → receita segmentada
(Mercadoria 4.1.01 / Serviço 4.2.01) → CMV=CFO (5.1.01×2.1.04.06) → pagamento fábrica.
Núcleo do razão (sem HTTP). Design do Fable 5 (2026-07-11)."""
import mod_contabil as mc


def _saldo(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


_EVENTOS_B2 = {
    "registro_venda_contrato":          ("1.1.02", "2.1.06"),   # FASE D2: venda cheia → Receita a Realizar
    "recebimento_venda":                ("1.1.01", "1.1.02"),   # FASE D2: recebimento abate Contas a Receber
    "faturamento_mercadoria_adiantado": ("2.1.06", "4.1.01"),
    "faturamento_mercadoria_a_receber": ("1.1.02", "4.1.01"),
    "faturamento_servico_adiantado":    ("2.1.06", "4.2.01"),
    "faturamento_servico_a_receber":    ("1.1.02", "4.2.01"),
    "pagamento_fabrica":                ("2.1.04.06", "1.1.01"),
}


def test_eventos_b2_existem_com_par_correto():
    for ev, (d, c) in _EVENTOS_B2.items():
        assert ev in mc.EVENTOS, ev
        assert mc.EVENTOS[ev][0] == d and mc.EVENTOS[ev][1] == c, ev


def test_registro_venda_e_recebimento_abate_receber(app_db):
    """FASE D2: o contrato registra a venda cheia em Receita a Realizar (2.1.06); o recebimento abate
    Contas a Receber (1.1.02), não a Receita a Realizar."""
    db = app_db.get_session(); ot, oid = "loja", 300; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 100000.0, projeto_id="P", ref="venda:P")
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 30000.0, projeto_id="P", ref="rcb:P:1")
    assert _saldo(db, ot, oid, "2.1.06") == 100000.0   # Receita a Realizar (passivo) intocada
    assert _saldo(db, ot, oid, "1.1.01") == 30000.0    # caixa recebido
    assert _saldo(db, ot, oid, "1.1.02") == 70000.0    # Contas a Receber abatido (100k − 30k)
    db.close()


def test_faturar_segmento_pool_cheio_so_adiantado(app_db):
    db = app_db.get_session(); ot, oid = "loja", 301; mc.seed_plano(db, ot, oid)
    # FASE D2: a Receita a Realizar (2.1.06) é populada pelo registro da venda no contrato (Val_Cont cheio)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 100000.0, projeto_id="P", ref="venda:P")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    assert _saldo(db, ot, oid, "4.1.01") == 65000.0    # receita reconhecida na NF-e
    assert _saldo(db, ot, oid, "2.1.06") == 35000.0    # pool baixado pela parcela mercadoria
    assert _saldo(db, ot, oid, "1.1.02") == 100000.0   # Contas a Receber = venda cheia (faturar_segmento não a altera)
    db.close()


def test_faturar_segmento_split_parcial(app_db):
    db = app_db.get_session(); ot, oid = "loja", 302; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 40000.0, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    assert _saldo(db, ot, oid, "2.1.06") == 0.0        # pool esgotado
    assert _saldo(db, ot, oid, "4.1.01") == 65000.0
    assert _saldo(db, ot, oid, "1.1.02") == 25000.0    # resto a receber
    db.close()


def test_faturar_segmento_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 303; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 100000.0, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")   # 2ª vez
    assert _saldo(db, ot, oid, "4.1.01") == 65000.0    # não duplica
    db.close()


def test_adiantamento_nunca_negativo_dois_segmentos(app_db):
    db = app_db.get_session(); ot, oid = "loja", 304; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 100000.0, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    mc.faturar_segmento(db, ot, oid, "P", "servico", 35000.0, ref_base="fat:NFSE-P-1")
    assert mc.saldo_adiantamento_projeto(db, ot, oid, "P") == 0.0
    assert _saldo(db, ot, oid, "2.1.06") == 0.0
    db.close()


def test_cmv_fabrica_reconhecido_na_efetivacao(app_db):
    """2026-08-07: a provisão de fábrica nasce no CONTRATO (2.1.04.06); o CMV entra no resultado só na
    EFETIVAÇÃO (5.1.01 × baixa do ativo diferido 1.1.06.06) — antes era "só na NF-e" (matching pleno,
    extinto: as despesas de projeto de móveis planejados ocorrem espalhadas ao longo do ciclo, muitas
    depois da própria NF-e, que só sai no fim, na entrega). A provisão SOBREVIVE p/ ser paga depois."""
    db = app_db.get_session(); ot, oid = "loja", 305; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 40000.0}, ref_base="pf:P")
    assert _saldo(db, ot, oid, "5.1.01") == 0.0           # antes da efetivação: nada no resultado
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.06", 40000.0, ref="ef:P")
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.06", 40000.0, ref="ef:P")   # reproc. (idempotente)
    assert _saldo(db, ot, oid, "5.1.01") == 40000.0       # CMV 1× no resultado
    assert _saldo(db, ot, oid, "1.1.06.06") == 0.0        # ativo diferido baixado
    assert _saldo(db, ot, oid, "2.1.04.06") == 40000.0    # provisão sobrevive
    db.close()


def test_fluxo_completo_balanco_fecha_e_dre(app_db):
    """FASE D2 — Cenário A: Val_Cont 100k (65/35), CFO 40k. Contrato: registra a venda cheia + constitui a
    fábrica (ativo diferido). NF-e: reconhece só a receita (2026-08-07: despesa não é mais aqui). Custo
    real conhecido → efetivação reconhece o CMV. Recebe e paga a fábrica. Balanço fecha; DRE mostra
    receita 100k, CMV 40k, sem duplicar."""
    db = app_db.get_session(); ot, oid = "loja", 306; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 100000.0, projeto_id="P", ref="venda:P")
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 40000.0}, ref_base="pf:P")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    mc.faturar_segmento(db, ot, oid, "P", "servico", 35000.0, ref_base="fat:NFSE-P-1")
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.06", 40000.0, ref="ef:P")
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 100000.0, projeto_id="P", ref="rcb:P:1")
    mc.registrar_evento(db, ot, oid, "pagamento_fabrica", 40000.0, projeto_id="P", ref="pgf:P:1")
    assert mc.balanco(db, ot, oid)["confere"] is True
    assert _saldo(db, ot, oid, "1.1.01") == 60000.0       # 100k recebido − 40k fábrica
    assert _saldo(db, ot, oid, "1.1.02") == 0.0           # Contas a Receber quitado
    assert _saldo(db, ot, oid, "2.1.06") == 0.0           # Receita a Realizar baixada ao faturar
    assert _saldo(db, ot, oid, "1.1.06.06") == 0.0        # ativo diferido baixado na NF-e
    assert _saldo(db, ot, oid, "2.1.04.06") == 0.0        # provisão fábrica paga
    d = mc.dre(db, ot, oid)
    assert d["receita_bruta"] == 100000.0                 # 65k + 35k, sem duplicar
    assert d["cmv_csp"] == 40000.0                        # CFO 1× (só na NF-e)
    assert d["lucro_bruto"] == 60000.0
    db.close()


def test_soma_receitas_igual_val_cont_via_orquestrador(app_db):
    """Σ(4.1.01 + 4.2.01) == Val_Cont exato, com segmentação que gera dízima."""
    from mod_orcamento_params import segmentar
    db = app_db.get_session(); ot, oid = "loja", 307; mc.seed_plano(db, ot, oid)
    val_cont = 100000.01
    merc, serv = segmentar(val_cont, 65.0)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", val_cont, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", merc, ref_base="fat:NFE-P-9")
    mc.faturar_segmento(db, ot, oid, "P", "servico", serv, ref_base="fat:NFSE-P-1")
    assert round(_saldo(db, ot, oid, "4.1.01") + _saldo(db, ot, oid, "4.2.01"), 2) == round(val_cont, 2)
    db.close()


# ── Congelamento da segmentação na assinatura (A6) ────────────────────────────────────────────
def test_congelar_segmentacao_grava_default_da_loja(app_db):
    import json as _j, main
    from database import Loja, Projeto
    db = app_db.get_session()
    lj = Loja(nome="Loja Cong 1", pct_mercadoria=65.0, pct_servico=35.0)
    db.add(lj); db.flush()
    db.add(Projeto(nome_safe="Proj_Cong_1", loja_id=lj.id, status="quente")); db.commit()
    seg = main._congelar_segmentacao_no_projeto(db, lj.id, "Proj_Cong_1")
    db.commit()
    assert seg == {"pct_mercadoria": 65.0, "pct_servico": 35.0}
    par = _j.loads(db.query(Projeto).filter_by(nome_safe="Proj_Cong_1").first().parametros_json)
    assert par["pct_mercadoria"] == 65.0 and par["pct_servico"] == 35.0
    db.close()


def test_congelar_segmentacao_override_vence_e_preserva_params(app_db):
    import json as _j, main
    from database import Loja, Projeto
    db = app_db.get_session()
    lj = Loja(nome="Loja Cong 2", pct_mercadoria=65.0, pct_servico=35.0)
    db.add(lj); db.flush()
    db.add(Projeto(nome_safe="Proj_Cong_2", loja_id=lj.id, status="quente",
                   parametros_json=_j.dumps({"pct_mercadoria": 80.0, "pct_servico": 20.0, "carga_trib": 9.0})))
    db.commit()
    seg = main._congelar_segmentacao_no_projeto(db, lj.id, "Proj_Cong_2")
    db.commit()
    assert seg == {"pct_mercadoria": 80.0, "pct_servico": 20.0}   # override do projeto vence a loja
    par = _j.loads(db.query(Projeto).filter_by(nome_safe="Proj_Cong_2").first().parametros_json)
    assert par["carga_trib"] == 9.0                               # não apaga os demais parâmetros
    db.close()


# ── B2.2: margem_projeto expõe custo_servico → destrava reconciliar(proporcional_custo_direto) ──
def test_margem_projeto_expoe_custo_servico(app_db):
    db = app_db.get_session(); ot, oid = "loja", 322; mc.seed_plano(db, ot, oid)
    c = lambda cod: db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first().id
    # FASE D2: os custos de serviço viram DESPESA (5.6.x) só na NF-e (matching, baixa do ativo 1.1.06);
    # a margem lê o custo REALIZADO — simulando aqui 500/300/200 já reconhecidos na emissão.
    mc.lancar(db, ot, oid, conta_debito_id=c("5.2.01"), conta_credito_id=c("1.1.06.02"), valor=500.0, projeto_id="P")  # montagem
    mc.lancar(db, ot, oid, conta_debito_id=c("5.2.13"), conta_credito_id=c("1.1.06.05"), valor=300.0, projeto_id="P")  # assistência
    mc.lancar(db, ot, oid, conta_debito_id=c("5.2.12"), conta_credito_id=c("1.1.06.03"), valor=200.0, projeto_id="P")  # garantia
    m = mc.margem_projeto(db, ot, oid, "P")
    assert m["custo_servico"] == 1000.0     # 500 montagem + 300 assistência + 200 garantia (5.6.x do projeto)
    # expor custo_servico NÃO altera a margem (as provisões já são subtraídas individualmente)
    assert m["margem_contribuicao"] == -1000.0
    db.close()


def test_reconciliar_proporcional_custo_direto_nao_quebra(app_db):
    db = app_db.get_session(); ot, oid = "loja", 323; mc.seed_plano(db, ot, oid)
    c = lambda cod: db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first().id
    # custo direto (CMV 5.1): A=900, B=300 → 75%/25% (constitui a fábrica e reconhece na efetivação)
    mc.constituir_provisoes_fechamento(db, ot, oid, "A", {"custo_fabrica": 900.0}, ref_base="pf:A")
    mc.constituir_provisoes_fechamento(db, ot, oid, "B", {"custo_fabrica": 300.0}, ref_base="pf:B")
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "A", "2.1.04.06", 900.0, ref="ef:A")
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "B", "2.1.04.06", 300.0, ref="ef:B")
    mc.lancar(db, ot, oid, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=400.0)
    rec = mc.reconciliar(db, ot, oid, metodologia="proporcional_custo_direto")   # antes: KeyError
    aloc = {a["projeto_id"]: a for a in rec["alocacao_por_projeto"]}
    assert aloc["A"]["valor_rateado"] == 300.0    # 75% de 400
    assert aloc["B"]["valor_rateado"] == 100.0    # 25% de 400
    db.close()


# ── B2.4/B2.5: constituição de TODAS as provisões rastreadas + custo financeiro ────────────────
_EVENTOS_FECH = {
    # FASE D2: constituição debita o ATIVO DIFERIDO (1.1.06.0X), não mais 5.6.0X (despesa só na NF-e)
    "fechamento_venda_frete_fabrica":       ("1.1.06.07", "2.1.04.07"),
    "fechamento_venda_frete_local":         ("1.1.06.08", "2.1.04.08"),
    "fechamento_venda_insumos":             ("1.1.06.09", "2.1.04.09"),
    "fechamento_venda_com_medidor":         ("1.1.06.10", "2.1.04.10"),
    "fechamento_venda_com_proj_exec":       ("1.1.06.11", "2.1.04.11"),
    "fechamento_venda_retencao_com_vendas": ("1.1.06.12", "2.1.04.12"),
    "fechamento_venda_impostos":            ("1.1.05", "2.1.04.13"),   # B2.6: ativo diferido × provisão
    "faturamento_impostos_deducao":         ("4.3.01", "1.1.05"),
    "faturamento_impostos_obrigacao":       ("2.1.04.13", "2.1.03"),
    "custo_financeiro":                     ("5.5.03", "2.1.05"),
}


def test_eventos_e_contas_b24_existem(app_db):
    for ev, (d, c) in _EVENTOS_FECH.items():
        assert ev in mc.EVENTOS and mc.EVENTOS[ev][0] == d and mc.EVENTOS[ev][1] == c, ev
    db = app_db.get_session(); mc.seed_plano(db, "loja", 400)
    cods = {x.codigo for x in db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=400).all()}
    for cod in ("5.1.02", "5.2.08", "5.2.09", "5.3.18", "5.3.19", "5.3.20"):
        assert cod in cods, cod
    db.close()


def test_constituir_todas_provisoes_fechamento(app_db):
    db = app_db.get_session(); ot, oid = "loja", 401; mc.seed_plano(db, ot, oid)
    s = lambda cod: mc.saldo_conta(db, ot, oid, db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first().id)
    valores = {"montagem": 100.0, "garantia": 50.0, "assistencia": 0.0, "frete_fabrica": 30.0,
               "frete_local": 20.0, "insumos": 10.0, "com_medidor": 15.0, "com_proj_exec": 25.0,
               "retencao_com_vendas": 40.0, "impostos": 80.0}
    out = mc.constituir_provisoes_fechamento(db, ot, oid, "P", valores, ref_base="provf:P")
    assert "assistencia" not in out                 # valor 0 não lança
    assert s("2.1.04.02") == 100.0 and s("2.1.04.03") == 50.0
    assert s("2.1.04.07") == 30.0 and s("2.1.04.08") == 20.0 and s("2.1.04.09") == 10.0
    assert s("2.1.04.10") == 15.0 and s("2.1.04.11") == 25.0 and s("2.1.04.12") == 40.0
    # impostos (B2.6): PROVISÃO no contrato — ativo diferido (1.1.05) × provisão (2.1.04.13), SEM tocar
    # a DRE. A dedução/obrigação só ocorrem na emissão (efetivar_impostos_segmento).
    assert s("1.1.05") == 80.0 and s("2.1.04.13") == 80.0
    assert mc.dre(db, ot, oid)["deducoes"] == 0.0
    db.close()


def test_impostos_efetivacao_segmentada(app_db):
    """B2.6: provisão de impostos reservada no contrato; efetivada proporcional Merc/Serv na emissão."""
    from mod_orcamento_params import segmentar
    db = app_db.get_session(); ot, oid = "loja", 404; mc.seed_plano(db, ot, oid)
    s = lambda cod: mc.saldo_conta(db, ot, oid, db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first().id)
    imp_total = 15540.63
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"impostos": imp_total}, ref_base="provf:P")
    im_merc, im_serv = segmentar(imp_total, 65.0)
    # NF-e: efetiva a parcela mercadoria
    mc.efetivar_impostos_segmento(db, ot, oid, "P", im_merc, ref_base="imp:NFE-P-1")
    assert abs(mc._mov(db, ot, oid, "4.3", "devedor", None, None) - im_merc) < 0.01   # dedução na DRE
    assert abs(s("2.1.03") - im_merc) < 0.01                                          # obrigação real
    assert abs(s("2.1.04.13") - (imp_total - im_merc)) < 0.01                         # provisão parcial
    assert abs(s("1.1.05") - (imp_total - im_merc)) < 0.01                            # ativo diferido parcial
    # NFS-e: efetiva o resto → zera provisão e ativo, obrigação total
    mc.efetivar_impostos_segmento(db, ot, oid, "P", im_serv, ref_base="imp:NFSE-P-1")
    assert abs(s("2.1.04.13")) < 0.01 and abs(s("1.1.05")) < 0.01
    assert abs(s("2.1.03") - imp_total) < 0.01
    assert abs(mc.dre(db, ot, oid)["deducoes"] - imp_total) < 0.01
    db.close()


def test_efetivar_impostos_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 405; mc.seed_plano(db, ot, oid)
    s = lambda cod: mc.saldo_conta(db, ot, oid, db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first().id)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"impostos": 1000.0}, ref_base="provf:P")
    mc.efetivar_impostos_segmento(db, ot, oid, "P", 650.0, ref_base="imp:NFE-P-1")
    mc.efetivar_impostos_segmento(db, ot, oid, "P", 650.0, ref_base="imp:NFE-P-1")   # 2ª vez
    assert abs(s("2.1.03") - 650.0) < 0.01                                            # não duplica
    db.close()


def test_constituir_fechamento_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 402; mc.seed_plano(db, ot, oid)
    s = lambda cod: mc.saldo_conta(db, ot, oid, db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first().id)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 30.0}, ref_base="provf:P")
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 30.0}, ref_base="provf:P")
    assert s("2.1.04.07") == 30.0                   # não duplica
    db.close()


def test_custo_financeiro(app_db):
    db = app_db.get_session(); ot, oid = "loja", 403; mc.seed_plano(db, ot, oid)
    s = lambda cod: mc.saldo_conta(db, ot, oid, db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first().id)
    mc.registrar_evento(db, ot, oid, "custo_financeiro", 14880.15, projeto_id="P", ref="cfin:P")
    assert s("5.5.03") == 14880.15                  # despesa financeira
    assert s("2.1.05") == 14880.15                  # financiamento total flex a pagar
    db.close()
