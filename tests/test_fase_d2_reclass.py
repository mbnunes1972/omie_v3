"""FASE D2 · Fase 4 — reclassificar_provisao espelha o ativo diferido (1.1.06) NA PROPORÇÃO ainda não
baixada na NF-e; o matching reconhece a parte Outros Fornecedores (1.1.06.14 → 5.1.01); sobra/falta
(resolver_saldo_provisao) valem p/ as 10 rubricas (incl. Custo de Fábrica)."""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def _constitui_fabrica(db, ot, oid, proj, valor):
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_fabrica", valor, projeto_id=proj, ref="cf:" + proj)


def test_reclassificar_espelha_ativo_antes_da_nfe(app_db):
    """Reclass ANTES da NF-e: o ativo diferido ainda está cheio → move junto com a provisão."""
    db = app_db.get_session(); ot, oid = "loja", 730; mc.seed_plano(db, ot, oid)
    _constitui_fabrica(db, ot, oid, "P", 1000.0)
    assert _s(db, ot, oid, "1.1.06.06") == 1000.0 and _s(db, ot, oid, "2.1.04.06") == 1000.0
    mc.reclassificar_provisao(db, ot, oid, "P", "2.1.04.06", "2.1.04.14", 200.0, ref="rc:P")
    # provisão movida (passivo × passivo)
    assert _s(db, ot, oid, "2.1.04.06") == 800.0 and _s(db, ot, oid, "2.1.04.14") == 200.0
    # ativo diferido ESPELHADO (ativo × ativo) — some da fábrica, aparece em outros fornecedores
    assert _s(db, ot, oid, "1.1.06.06") == 800.0 and _s(db, ot, oid, "1.1.06.14") == 200.0
    db.close()


def test_efetivacao_reconhece_despesa_outros_fornecedores(app_db):
    """Após reclass, cada provisão (fábrica remanescente + outros fornecedores) reconhece despesa na
    PRÓPRIA efetivação (2026-08-07 — antes era o matching pleno na NF-e), no MESMO 5.1.01; as provisões
    (2.1.04.06/2.1.04.14) sobrevivem p/ pagamento/reconciliação."""
    db = app_db.get_session(); ot, oid = "loja", 731; mc.seed_plano(db, ot, oid)
    _constitui_fabrica(db, ot, oid, "P", 1000.0)
    mc.reclassificar_provisao(db, ot, oid, "P", "2.1.04.06", "2.1.04.14", 200.0, ref="rc:P")
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.06", 800.0, ref="ef:fab")
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.14", 200.0, ref="ef:out")
    assert _s(db, ot, oid, "5.1.01") == 1000.0                          # 800 fábrica + 200 outros
    assert _s(db, ot, oid, "1.1.06.06") == 0.0 and _s(db, ot, oid, "1.1.06.14") == 0.0
    assert _s(db, ot, oid, "2.1.04.06") == 800.0 and _s(db, ot, oid, "2.1.04.14") == 200.0
    db.close()


def test_reclassificar_depois_da_efetivacao_nao_espelha_ativo_baixado(app_db):
    """Reclass DEPOIS da efetivação (2026-08-07 — antes era "depois da NF-e"): o ativo diferido já foi
    baixado (=0). A reclass move só a provisão; não há ativo a espelhar (evita saldo negativo). O custo
    já foi reconhecido; a granularidade fica no passivo."""
    db = app_db.get_session(); ot, oid = "loja", 732; mc.seed_plano(db, ot, oid)
    _constitui_fabrica(db, ot, oid, "P", 1000.0)
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.06", 1000.0, ref="ef:P")   # baixa 1.1.06.06 → 0
    mc.reclassificar_provisao(db, ot, oid, "P", "2.1.04.06", "2.1.04.14", 200.0, ref="rc:P")
    assert _s(db, ot, oid, "2.1.04.06") == 800.0 and _s(db, ot, oid, "2.1.04.14") == 200.0  # provisão movida
    assert _s(db, ot, oid, "1.1.06.06") == 0.0 and _s(db, ot, oid, "1.1.06.14") == 0.0       # nada a espelhar
    assert _s(db, ot, oid, "5.1.01") == 1000.0                                               # custo já reconhecido
    db.close()


def test_sobra_custo_fabrica_cancela_sem_dre(app_db):
    """Sobra/falta vale p/ as rubricas com despesa em tempo real (Custo de Fábrica incluso, 2026-08-07):
    custo real < planejado → cancela ativo × provisão SEM virar receita — a despesa real (900) já foi
    reconhecida na própria efetivação; os 100 nunca gastos não geram ganho nenhum a "reverter"."""
    db = app_db.get_session(); ot, oid = "loja", 733; mc.seed_plano(db, ot, oid)
    _constitui_fabrica(db, ot, oid, "P", 1000.0)
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 900.0, ref="ef:P")   # custo real 900 < 1000
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.06", ref="rs:P")
    assert _s(db, ot, oid, "2.1.04.06") == 0.0        # provisão zerada
    assert _s(db, ot, oid, "1.1.06.06") == 0.0        # ativo diferido zerado junto (cancelamento)
    assert _s(db, ot, oid, "4.4.02") == 0.0           # SEM virar receita — nada a reverter
    assert _s(db, ot, oid, "5.1.01") == 900.0         # a despesa REAL (900) já estava lá, intocada
    db.close()


def test_reconciliacao_cobre_as_10_rubricas(app_db):
    db = app_db.get_session(); ot, oid = "loja", 734; mc.seed_plano(db, ot, oid)
    valores = {"montagem": 1000.0, "garantia": 200.0, "assistencia": 300.0, "custo_fabrica": 60000.0,
               "frete_fabrica": 400.0, "frete_local": 150.0, "insumos": 100.0, "com_medidor": 250.0,
               "com_proj_exec": 350.0, "retencao_com_vendas": 500.0}
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", valores, ref_base="pf:P")
    linhas = {l["codigo"]: l for l in mc.reconciliacao(db, ot, oid, projeto_id="P")["provisoes"]}
    for cod, val in [("2.1.04.02", 1000.0), ("2.1.04.06", 60000.0), ("2.1.04.12", 500.0)]:
        assert linhas[cod]["provisionado"] == val and linhas[cod]["efetivado"] == 0.0
        assert linhas[cod]["saldo"] == val
    db.close()
