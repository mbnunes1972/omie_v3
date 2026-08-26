import pytest
import mod_contabil as mc


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_rateio_proporcional_receita(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 30); c = _q(db, 30)
    # Projeto A receita 900, projeto B receita 300 (75%/25%)
    mc.registrar_evento(db, "loja", 30, "faturamento", 900.0, projeto_id="A")
    mc.registrar_evento(db, "loja", 30, "faturamento", 300.0, projeto_id="B")
    # Despesa fixa (5.4 Aluguel) 400 — sem projeto
    mc.lancar(db, "loja", 30, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=400.0)
    rec = mc.reconciliar(db, "loja", 30, metodologia="proporcional_receita")
    db.close()
    assert rec["despesas_fixas_periodo"] == 400.0
    aloc = {a["projeto_id"]: a for a in rec["alocacao_por_projeto"]}
    assert aloc["A"]["valor_rateado"] == 300.0    # 75% de 400
    assert aloc["B"]["valor_rateado"] == 100.0    # 25% de 400
    assert aloc["A"]["margem_plena"] == 600.0     # 900 margem - 300 rateio
    # divergência = resultado societário − soma margem plena
    assert rec["resultado_societario_oficial"] == 800.0   # 1200 receita - 400 desp adm
    assert rec["soma_margem_plena"] == 800.0              # (900-300)+(300-100)=800
    assert rec["divergencia_residual"] == 0.0             # nada não-alocado neste cenário


def test_rateio_linear_e_metodologia_invalida(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 31); c = _q(db, 31)
    mc.registrar_evento(db, "loja", 31, "faturamento", 100.0, projeto_id="X")
    mc.registrar_evento(db, "loja", 31, "faturamento", 900.0, projeto_id="Y")
    mc.lancar(db, "loja", 31, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=200.0)
    rec = mc.reconciliar(db, "loja", 31, metodologia="linear_por_projeto")
    aloc = {a["projeto_id"]: a for a in rec["alocacao_por_projeto"]}
    assert aloc["X"]["valor_rateado"] == 100.0 and aloc["Y"]["valor_rateado"] == 100.0   # 200/2 cada
    with pytest.raises(ValueError):
        mc.reconciliar(db, "loja", 31, metodologia="chute")
    db.close()


def test_fechar_periodo_persiste(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 32)
    mc.registrar_evento(db, "loja", 32, "faturamento", 500.0, projeto_id="Z")
    r = mc.fechar_periodo(db, "loja", 32, metodologia="proporcional_receita")
    assert r["id"]
    periodos = mc.listar_periodos(db, "loja", 32)
    db.close()
    assert len(periodos) == 1 and periodos[0]["status"] == "fechado"
    assert periodos[0]["resultado_societario"] == 500.0


# ── Frente 2 (spec 2026-08-25, Centro de Custo/Natureza): snapshot no fechamento ─────────────────
def test_fechar_periodo_grava_snapshot_classificacao(app_db):
    import datetime as dt, json
    db = app_db.get_session(); ot, oid = "loja", 33
    mc.seed_plano(db, ot, oid); mc.seed_centro_custo(db, ot, oid)
    contas = {c.codigo: c for c in db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}
    contas["5.4.01"].natureza_custo = "fixo"
    db.commit()
    caixa = contas["1.1.01"]
    mc.lancar(db, ot, oid, contas["5.4.01"].id, caixa.id, 700.0,
              data=dt.datetime(2026, 8, 15))

    ini, fim = dt.datetime(2026, 8, 1), dt.datetime(2026, 8, 31, 23, 59, 59)
    r = mc.fechar_periodo(db, ot, oid, ini=ini, fim=fim)
    periodo = db.get(mc.PeriodoContabil, r["id"])
    assert periodo.classificacao_snapshot_json
    snap = json.loads(periodo.classificacao_snapshot_json)
    assert "natureza" in snap and "centro_custo" in snap
    assert snap["natureza"]["fixo"]["total"] == 700.0
    db.close()


def test_relatorio_periodo_congela_reclassificacao_depois_do_fechamento(app_db):
    import datetime as dt
    db = app_db.get_session(); ot, oid = "loja", 34
    mc.seed_plano(db, ot, oid); mc.seed_centro_custo(db, ot, oid)
    contas = {c.codigo: c for c in db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}
    contas["5.4.01"].natureza_custo = "fixo"
    db.commit()
    caixa = contas["1.1.01"]
    mc.lancar(db, ot, oid, contas["5.4.01"].id, caixa.id, 700.0, data=dt.datetime(2026, 8, 15))

    ini, fim = dt.datetime(2026, 8, 1), dt.datetime(2026, 8, 31, 23, 59, 59)
    mc.fechar_periodo(db, ot, oid, ini=ini, fim=fim)

    # reclassifica DEPOIS do fechamento — o relatório do período fechado não pode mudar
    contas = {c.codigo: c for c in db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}
    contas["5.4.01"].natureza_custo = "variavel"
    db.commit()

    congelado = mc.relatorio_natureza_periodo(db, ot, oid, ini=ini, fim=fim)
    assert congelado["fixo"]["total"] == 700.0             # snapshot: valor antigo
    assert congelado["variavel"]["contas"] == []

    ao_vivo = mc.relatorio_natureza(db, ot, oid, ini=ini, fim=fim)
    assert ao_vivo["variavel"]["total"] == 700.0            # sem período, reflete a reclassificação
    db.close()


def test_relatorio_periodo_sem_correspondencia_nunca_congela(app_db):
    """Achado crítico verificado antes de implementar: fechar_periodo SEM ini/fim (o fluxo atual
    da UI, antes desta frente) grava um PeriodoContabil com inicio=fim=None. Se a correspondência
    não exigisse ini/fim explícitos dos dois lados, TODA consulta sem filtro (a visão padrão,
    default da tela) passaria a devolver esse snapshot congelado pra sempre a partir do primeiro
    fechamento — escondendo lançamentos novos do dia a dia. Trava: sem ini/fim explícitos, nunca
    corresponde a período nenhum, mesmo havendo um fechado com (None, None)."""
    db = app_db.get_session(); ot, oid = "loja", 35
    mc.seed_plano(db, ot, oid); mc.seed_centro_custo(db, ot, oid)
    mc.fechar_periodo(db, ot, oid)   # sem ini/fim — comportamento legado
    contas = {c.codigo: c for c in db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}
    caixa = contas["1.1.01"]
    mc.lancar(db, ot, oid, contas["5.4.01"].id, caixa.id, 150.0)   # lançamento NOVO, depois do fechamento

    rel = mc.relatorio_natureza_periodo(db, ot, oid)   # sem filtro — a visão padrão
    total = sum(b["total"] for k, b in rel.items() if k != "periodo")
    assert total == 150.0   # o lançamento novo aparece — não ficou preso num snapshot velho
    db.close()
