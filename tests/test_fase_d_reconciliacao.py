"""FASE D1 — reconciliação de provisões (Provisionado × Efetivado × Saldo × Destino) + Contas a Pagar.
Efetivado = competência (2.1.04.x × 2.1.01 Fornecedores a Pagar). Destino: sobra→4.4.02 (receita),
falta→5.6.10 (despesa). Fonte única = razão; reconciliacao(projeto_id) serve granular e consolidado."""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_contas_e_evento_d1_existem(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 600)
    cods = {c.codigo for c in db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=600).all()}
    assert "4.4.02" in cods and "5.6.10" in cods
    assert mc.EVENTOS["pagamento_fornecedor"][:2] == ("2.1.01", "1.1.01")
    db.close()


def test_efetivar_provisao_reconhece_obrigacao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 601; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef:P:07")
    assert _s(db, ot, oid, "2.1.04.07") == 100.0    # provisão em aberto (1000 − 900)
    assert _s(db, ot, oid, "2.1.01") == 900.0        # Fornecedores a Pagar (competência)
    assert _s(db, ot, oid, "1.1.01") == 0.0          # caixa intocado (ainda não pagou)
    db.close()


def test_efetivar_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6011; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef:P:07")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef:P:07")   # 2ª vez
    assert _s(db, ot, oid, "2.1.01") == 900.0        # não duplica
    db.close()


def test_efetivar_provisao_forma_pagamento_direto_baixa_caixa(app_db):
    """2026-08-07: forma_pagamento='direto' (módulo Assistências, loja paga na hora) credita Caixa
    em vez de Fornecedores a Pagar."""
    db = app_db.get_session(); ot, oid = "loja", 6012; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef:P:07", forma_pagamento="direto")
    assert _s(db, ot, oid, "2.1.04.07") == 100.0
    assert _s(db, ot, oid, "1.1.01") == -900.0        # baixou direto do caixa (crédito)
    assert _s(db, ot, oid, "2.1.01") == 0.0           # Fornecedores intocado
    assert _s(db, ot, oid, "5.1.02") == 900.0         # despesa real (Frete de Fábrica) reconhecida
    db.close()


def test_efetivar_provisao_origem_e_motivo_customizados(app_db):
    """2026-08-07: origem/motivo parametrizáveis — mod_assistencias precisa preservar a tag
    'execucao_reparo_garantia'+motivo='defeito_fabrica' pro relatório 'a cobrar da fábrica'."""
    db = app_db.get_session(); ot, oid = "loja", 6013; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"garantia": 500.0}, ref_base="pf:P")
    lan = mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.03", 300.0, ref="ef:P:03",
                               forma_pagamento="direto", origem="execucao_reparo_garantia",
                               motivo="defeito_fabrica")
    assert lan["origem"] == "execucao_reparo_garantia"
    rel = mc.total_a_cobrar_fabrica(db, ot, oid)
    assert rel["total"] == 300.0 and rel["qtd"] == 1
    db.close()


def test_despesa_avulsa_direto_e_a_prazo(app_db):
    """2026-08-07: Assistência/Garantia avulsa (sem projeto) — despesa direta, sem provisão."""
    db = app_db.get_session(); ot, oid = "loja", 6014; mc.seed_plano(db, ot, oid)
    mc.despesa_avulsa(db, ot, oid, "5.2.13", 200.0, "direto", ref="av:1")
    assert _s(db, ot, oid, "5.2.13") == 200.0
    assert _s(db, ot, oid, "1.1.01") == -200.0
    mc.despesa_avulsa(db, ot, oid, "5.3.21", 150.0, "a_prazo", ref="av:2")   # concessão, faturada
    assert _s(db, ot, oid, "5.3.21") == 150.0
    assert _s(db, ot, oid, "2.1.01") == 150.0
    # idempotente
    mc.despesa_avulsa(db, ot, oid, "5.2.13", 200.0, "direto", ref="av:1")
    assert _s(db, ot, oid, "5.2.13") == 200.0
    db.close()


def test_despesa_avulsa_forma_pagamento_invalida(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6015; mc.seed_plano(db, ot, oid)
    try:
        mc.despesa_avulsa(db, ot, oid, "5.2.13", 100.0, "xpto", ref="av:x")
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass
    db.close()


def test_reconciliacao_projeto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 602; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0, "montagem": 500.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef:P:07")
    linhas = {l["codigo"]: l for l in mc.reconciliacao(db, ot, oid, projeto_id="P")["provisoes"]}
    assert linhas["2.1.04.07"]["provisionado"] == 1000.0 and linhas["2.1.04.07"]["efetivado"] == 900.0
    assert linhas["2.1.04.07"]["saldo"] == 100.0 and linhas["2.1.04.07"]["tipo"] == "C"
    assert linhas["2.1.04.02"]["provisionado"] == 500.0 and linhas["2.1.04.02"]["efetivado"] == 0.0
    assert linhas["2.1.04.02"]["saldo"] == 500.0
    db.close()


def test_resolver_saldo_sobra_cancela_sem_receita(app_db):
    """2026-08-07: frete_fabrica tem despesa em tempo real (reconhecida na própria efetivação) — a
    sobra CANCELA contra o ativo diferido, sem virar receita (nada a reverter)."""
    db = app_db.get_session(); ot, oid = "loja", 603; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef:P:07")   # despesa real já reconhecida
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.07", ref="rs:P:07")
    assert _s(db, ot, oid, "2.1.04.07") == 0.0       # provisão zerada
    assert _s(db, ot, oid, "1.1.06.07") == 0.0       # ativo diferido cancelado junto
    assert _s(db, ot, oid, "4.4.02") == 0.0          # SEM virar receita
    assert _s(db, ot, oid, "5.1.02") == 900.0        # despesa real (frete fábrica), intocada
    # reconciliação: efetivado NÃO conta a resolução; expõe resolvido à parte
    rec = {l["codigo"]: l for l in mc.reconciliacao(db, ot, oid, projeto_id="P")["provisoes"]}
    assert rec["2.1.04.07"]["provisionado"] == 1000.0 and rec["2.1.04.07"]["efetivado"] == 900.0
    assert rec["2.1.04.07"]["saldo"] == 100.0 and rec["2.1.04.07"]["resolvido"] == 100.0
    db.close()


def test_resolver_saldo_falta_cancela_sem_despesa_extra(app_db):
    """2026-08-07: custo real (1200) > provisionado (1000) — a despesa JÁ foi reconhecida por inteiro
    na própria efetivação; a falta só cancela o residual, sem despesa NOVA (senão duplicaria)."""
    db = app_db.get_session(); ot, oid = "loja", 604; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 1200.0, ref="ef:P:07")   # custo real > provisão
    assert _s(db, ot, oid, "2.1.04.07") == -200.0    # falta (saldo negativo)
    assert _s(db, ot, oid, "5.1.02") == 1200.0       # despesa real JÁ reconhecida por inteiro
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.07", ref="rs:P:07")
    assert _s(db, ot, oid, "2.1.04.07") == 0.0       # zerada
    assert _s(db, ot, oid, "5.6.10") == 0.0          # SEM despesa extra
    assert _s(db, ot, oid, "5.1.02") == 1200.0       # despesa real, intocada
    db.close()


def test_pagamento_fornecedor_baixa_2101(app_db):
    db = app_db.get_session(); ot, oid = "loja", 605; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef:P:07")
    mc.registrar_evento(db, ot, oid, "pagamento_fornecedor", 900.0, projeto_id="P", ref="pg:P:07")
    assert _s(db, ot, oid, "2.1.01") == 0.0          # obrigação quitada
    assert mc.contas_a_pagar(db, ot, oid, projeto_id="P")["total_em_aberto"] == 0.0
    db.close()


def test_reconciliacao_consolidada_soma_projetos(app_db):
    db = app_db.get_session(); ot, oid = "loja", 606; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "A", {"frete_fabrica": 1000.0}, ref_base="pf:A")
    mc.constituir_provisoes_fechamento(db, ot, oid, "B", {"frete_fabrica": 500.0}, ref_base="pf:B")
    linhas = {l["codigo"]: l for l in mc.reconciliacao(db, ot, oid, projeto_id=None)["provisoes"]}
    assert linhas["2.1.04.07"]["provisionado"] == 1500.0   # consolidado A+B
    db.close()


def test_reclassificacao_outros_fornecedores(app_db):
    """FASE D: substituição — reclassifica parte do Custo Fábrica p/ Outros Fornecedores; cada linha
    reconcilia com o seu efetivado (soma dos saldos = economia total). Passivo × passivo, não toca DRE."""
    db = app_db.get_session(); ot, oid = "loja", 620; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_fabrica", 1000.0, projeto_id="P", ref="pf:P:cf")   # FASE D2: provisão fábrica 1000 (no contrato)
    mc.reclassificar_provisao(db, ot, oid, "P", "2.1.04.06", "2.1.04.14", 200.0, ref="rc:P")   # 20% → outros
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 760.0, ref="ef:fab")                   # NF fábrica
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.14", 95.0, ref="ef:out")                    # NF outros
    rec = {l["codigo"]: l for l in mc.reconciliacao(db, ot, oid, projeto_id="P")["provisoes"]}
    assert rec["2.1.04.06"]["provisionado"] == 800.0 and rec["2.1.04.06"]["efetivado"] == 760.0 and rec["2.1.04.06"]["saldo"] == 40.0
    assert rec["2.1.04.14"]["provisionado"] == 200.0 and rec["2.1.04.14"]["efetivado"] == 95.0 and rec["2.1.04.14"]["saldo"] == 105.0
    assert rec["2.1.04.14"]["tipo"] == "C"
    assert mc.dre(db, ot, oid)["deducoes"] == 0.0   # reclassificação não toca o resultado
    db.close()


def test_balanco_tem_detalhe_analitico(app_db):
    db = app_db.get_session(); ot, oid = "loja", 630; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 1000.0, projeto_id="P", ref="venda")
    b = mc.balanco(db, ot, oid)
    assert "detalhe" in b
    assert "1.1.02" in [x["codigo"] for x in b["detalhe"]["ativo_circulante"]]      # Contas a Receber
    assert "2.1.06" in [x["codigo"] for x in b["detalhe"]["passivo_circulante"]]    # Receita a Realizar
    db.close()


def test_provisao_projetos(app_db):
    db = app_db.get_session(); ot, oid = "loja", 631; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_fabrica", 1000.0, projeto_id="A", ref="cfA")   # FASE D2: provisão no contrato
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_fabrica", 500.0, projeto_id="B", ref="cfB")
    mc.efetivar_provisao(db, ot, oid, "A", "2.1.04.06", 800.0, ref="efA")
    pp = mc.provisao_projetos(db, ot, oid, "2.1.04.06")
    projs = {p["projeto_id"]: p for p in pp["projetos"]}
    assert projs["A"]["provisionado"] == 1000.0 and projs["A"]["efetivado"] == 800.0 and projs["A"]["saldo"] == 200.0
    assert projs["B"]["provisionado"] == 500.0 and projs["B"]["efetivado"] == 0.0
    assert "fechamento_venda_custo_fabrica" in projs["A"]["por_origem"] and "efetivacao_provisao" in projs["A"]["por_origem"]
    assert pp["totais"]["provisionado"] == 1500.0
    db.close()


def test_dre_inclui_reversao_de_provisao(app_db):
    """A SOBRA de uma provisão SEM despesa em tempo real (rota própria — aqui Custo Financeiro) entra
    na DRE via Outras Receitas (não fica órfã). Pras rubricas com despesa em tempo real (2026-08-07),
    ver test_resolver_saldo_sobra_cancela_sem_receita — essas NÃO tocam a DRE."""
    db = app_db.get_session(); ot, oid = "loja", 610; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.19", 600.0, ref="ef")   # sobra 400
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.19", ref="rs")
    d = mc.dre(db, ot, oid)
    assert d["outras_receitas"] == 400.0
    assert d["resultado_antes_impostos"] == round(d["ebit"] + d["resultado_financeiro"] + 400.0, 2)
    db.close()


def test_contas_a_pagar_em_aberto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 607; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0, "insumos": 300.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef:P:07")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.09", 250.0, ref="ef:P:09")
    assert mc.contas_a_pagar(db, ot, oid, projeto_id="P")["total_em_aberto"] == 1150.0   # 900 + 250
    db.close()
