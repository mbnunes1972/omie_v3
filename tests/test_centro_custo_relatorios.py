# -*- coding: utf-8 -*-
"""relatorio_centro_custo/relatorio_natureza (2026-08-08): relatórios de leitura pura em cima da
classificação Centro de Custo/Natureza já gravada — totais consolidados por nó/balde, período
opcional, contas com valor 0 no período ficam de fora, e nada some em silêncio (contas sem
classificação viram um bucket 'nao_classificado' à parte)."""
import mod_contabil as mc


def _contas(db, ot, oid):
    return {c.codigo: c for c in db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}


def _ccs(db, ot, oid):
    return {c.codigo: c for c in db.query(mc.CentroCusto).filter_by(owner_tipo=ot, owner_id=oid).all()}


def _find_no(nodes, codigo):
    for n in nodes:
        if n["codigo"] == codigo:
            return n
        f = _find_no(n["filhos"], codigo)
        if f:
            return f
    return None


def _preparar(db, ot, oid):
    mc.seed_plano(db, ot, oid)
    mc.seed_centro_custo(db, ot, oid)
    return _contas(db, ot, oid), _ccs(db, ot, oid)


# ── relatorio_centro_custo ──────────────────────────────────────────────────────────────────────
def test_relatorio_centro_custo_consolida_por_no(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1000
    contas, ccs = _preparar(db, ot, oid)
    caixa = contas["1.1.01"]
    # Montagem (1.3) é filha de Operacional (1) — 5.2.01 classificada em Montagem
    contas["5.2.01"].centro_custo_id = ccs["1.3"].id
    contas["5.4.01"].centro_custo_id = ccs["1.5"].id   # Instalações — também filha de Operacional
    db.commit()
    mc.lancar(db, ot, oid, contas["5.2.01"].id, caixa.id, 300.0, historico="montagem")
    mc.lancar(db, ot, oid, contas["5.4.01"].id, caixa.id, 700.0, historico="aluguel")

    rel = mc.relatorio_centro_custo(db, ot, oid)
    montagem_no = _find_no(rel["centros_custo"], "1.3")
    assert montagem_no["total"] == 300.0
    assert montagem_no["contas"] == [{"id": contas["5.2.01"].id, "codigo": "5.2.01",
                                       "nome": "Montagem", "valor": 300.0}]
    operacional_no = _find_no(rel["centros_custo"], "1")
    assert operacional_no["total"] == 1000.0     # soma recursiva dos filhos (Montagem + Instalações)
    db.close()


def test_relatorio_centro_custo_filtra_periodo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1001
    contas, ccs = _preparar(db, ot, oid)
    caixa = contas["1.1.01"]
    contas["5.2.01"].centro_custo_id = ccs["1.3"].id
    db.commit()
    mc.lancar(db, ot, oid, contas["5.2.01"].id, caixa.id, 100.0,
              data=__import__("datetime").datetime(2026, 1, 10))
    mc.lancar(db, ot, oid, contas["5.2.01"].id, caixa.id, 200.0,
              data=__import__("datetime").datetime(2026, 3, 10))

    import datetime as dt
    rel = mc.relatorio_centro_custo(db, ot, oid, ini=dt.datetime(2026, 3, 1), fim=dt.datetime(2026, 3, 31))
    no = _find_no(rel["centros_custo"], "1.3")
    assert no["total"] == 200.0          # só o lançamento de março
    db.close()


def test_relatorio_centro_custo_conta_zero_no_periodo_nao_aparece(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1002
    contas, ccs = _preparar(db, ot, oid)
    caixa = contas["1.1.01"]
    contas["5.2.01"].centro_custo_id = ccs["1.3"].id
    db.commit()
    # débito e crédito na MESMA conta (via 2 lançamentos que se cancelam) -> saldo líquido 0
    mc.lancar(db, ot, oid, contas["5.2.01"].id, caixa.id, 150.0, historico="ida")
    mc.lancar(db, ot, oid, caixa.id, contas["5.2.01"].id, 150.0, historico="estorno")

    rel = mc.relatorio_centro_custo(db, ot, oid)
    no = _find_no(rel["centros_custo"], "1.3")
    assert no["contas"] == [] and no["total"] == 0.0
    db.close()


def test_relatorio_centro_custo_nao_classificado_nao_some(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1003
    contas, ccs = _preparar(db, ot, oid)
    caixa = contas["1.1.01"]
    # 5.2.01 fica SEM centro_custo_id (unclassified)
    mc.lancar(db, ot, oid, contas["5.2.01"].id, caixa.id, 90.0, historico="sem cc")

    rel = mc.relatorio_centro_custo(db, ot, oid)
    assert rel["nao_classificado"]["total"] == 90.0
    assert rel["nao_classificado"]["contas"][0]["codigo"] == "5.2.01"
    db.close()


# ── relatorio_natureza ──────────────────────────────────────────────────────────────────────────
def test_relatorio_natureza_agrupa_e_totaliza(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1004
    contas, ccs = _preparar(db, ot, oid)
    caixa = contas["1.1.01"]
    contas["5.2.01"].natureza_custo = "variavel"
    contas["5.4.01"].natureza_custo = "fixo"
    db.commit()
    mc.lancar(db, ot, oid, contas["5.2.01"].id, caixa.id, 400.0)
    mc.lancar(db, ot, oid, contas["5.4.01"].id, caixa.id, 900.0)

    rel = mc.relatorio_natureza(db, ot, oid)
    assert rel["variavel"]["total"] == 400.0
    assert [c["codigo"] for c in rel["variavel"]["contas"]] == ["5.2.01"]
    assert rel["fixo"]["total"] == 900.0
    assert [c["codigo"] for c in rel["fixo"]["contas"]] == ["5.4.01"]
    db.close()


def test_relatorio_natureza_esconde_zero_e_mostra_nao_classificado(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1005
    contas, ccs = _preparar(db, ot, oid)
    caixa = contas["1.1.01"]
    contas["5.2.01"].natureza_custo = "variavel"
    db.commit()
    # 5.2.01 (classificada) net-zero -> não aparece
    mc.lancar(db, ot, oid, contas["5.2.01"].id, caixa.id, 50.0)
    mc.lancar(db, ot, oid, caixa.id, contas["5.2.01"].id, 50.0)
    # 5.4.01 (SEM natureza_custo) com valor -> vai pro balde nao_classificado, não some
    mc.lancar(db, ot, oid, contas["5.4.01"].id, caixa.id, 60.0)

    rel = mc.relatorio_natureza(db, ot, oid)
    assert rel["variavel"]["contas"] == []
    assert rel["nao_classificado"]["total"] == 60.0
    assert rel["nao_classificado"]["contas"][0]["codigo"] == "5.4.01"
    db.close()


# ── retrato_classificacao_grupo5 (Frente 0, spec 2026-08-25) ─────────────────────────────────────
def test_retrato_aponta_divergencia_de_natureza(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1006
    contas, ccs = _preparar(db, ot, oid)
    mc.migrar_classificacao_grupo5_v1(db)
    # 5.4.20 é ("4.5", "fixo") no mapa — reclassifica manualmente pra "variavel"
    contas = _contas(db, ot, oid)
    contas["5.4.20"].natureza_custo = "variavel"
    db.commit()

    itens = mc.retrato_classificacao_grupo5(db, ot, oid)
    item = next(i for i in itens if i["codigo"] == "5.4.20")
    assert item["natureza_atual"] == "variavel"
    assert item["natureza_esperada"] == "fixo"
    assert item["diverge"] is True
    # uma conta que bate com o mapa não diverge
    outro = next(i for i in itens if i["codigo"] == "5.1.01")
    assert outro["diverge"] is False
    db.close()


def test_retrato_conta_sem_classificacao_nao_diverge_ate_migrar(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1007
    _preparar(db, ot, oid)   # sem rodar migrar_classificacao_grupo5_v1 — tudo None ainda

    itens = mc.retrato_classificacao_grupo5(db, ot, oid)
    item = next(i for i in itens if i["codigo"] == "5.1.01")
    assert item["centro_custo_atual_codigo"] is None and item["natureza_atual"] is None
    assert item["centro_custo_esperado_codigo"] == "1.2" and item["natureza_esperada"] == "variavel"
    assert item["diverge"] is True   # None != o esperado — conta ainda não classificada É divergência
    db.close()


def test_retrato_conta_fora_do_mapa_marca_sem_mapa(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1008
    contas, ccs = _preparar(db, ot, oid)
    extra = mc.Conta(owner_tipo=ot, owner_id=oid, codigo="5.9.99", nome="Conta nova sem mapa",
                     grupo=5, tipo="analitica", natureza="devedora",
                     pai_id=contas["5.4.20"].pai_id, ativa=1, ordem=999)
    db.add(extra); db.commit()

    itens = mc.retrato_classificacao_grupo5(db, ot, oid)
    item = next(i for i in itens if i["codigo"] == "5.9.99")
    assert item["sem_mapa"] is True and item["diverge"] is False
    db.close()


# ── endpoints HTTP ──────────────────────────────────────────────────────────────────────────────
def test_endpoint_centro_custo_retrato(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/centro-custo/retrato")
    assert st == 200 and d["ok"]
    assert "contas" in d and "gerado_em" in d


def test_endpoint_centro_custo_relatorio(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/centro-custo/relatorio")
    assert st == 200 and d["ok"]
    assert "centros_custo" in d and "nao_classificado" in d


def test_endpoint_natureza_relatorio(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/plano-contas/natureza-relatorio")
    assert st == 200 and d["ok"]
    assert "fixo" in d and "variavel" in d and "nao_classificado" in d
