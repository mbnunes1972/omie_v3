"""Ajuste pós-FASE D2 — reconciliacao() expõe `saldo_aberto` (líquido) = o que ainda falta resolver,
descontando o `resolvido` na direção certa (resolvido é magnitude positiva nos dois casos):
  sobra (saldo>0): saldo_aberto = saldo − resolvido
  falta (saldo<0): saldo_aberto = saldo + resolvido
O `saldo` bruto e o `resolvido` continuam disponíveis para auditoria."""
import mod_contabil as mc


def _linhas(db, ot, oid, proj="P"):
    return {l["codigo"]: l for l in mc.reconciliacao(db, ot, oid, projeto_id=proj)["provisoes"]}


def test_sobra_resolvida_total_zera_saldo_aberto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 760; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef")   # sobra 100
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.07", ref="rs")     # resolve sobra
    l = _linhas(db, ot, oid)["2.1.04.07"]
    assert l["saldo"] == 100.0 and l["resolvido"] == 100.0                  # bruto/resolvido preservados
    assert l["saldo_aberto"] == 0.0                                         # líquido zerado (nada em aberto)
    db.close()


def test_falta_resolvida_total_zera_saldo_aberto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 761; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 1200.0, ref="ef")   # falta -200
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.07", ref="rs")     # resolve falta
    l = _linhas(db, ot, oid)["2.1.04.07"]
    assert l["saldo"] == -200.0 and l["resolvido"] == 200.0
    assert l["saldo_aberto"] == 0.0                                         # -200 + 200 = 0
    db.close()


def test_nao_resolvido_saldo_aberto_igual_bruto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 762; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0, "montagem": 500.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef7")   # sobra 100, NÃO resolvida
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.02", 700.0, ref="ef2")   # falta -200, NÃO resolvida
    ls = _linhas(db, ot, oid)
    assert ls["2.1.04.07"]["saldo_aberto"] == 100.0 and ls["2.1.04.07"]["resolvido"] == 0.0
    assert ls["2.1.04.02"]["saldo_aberto"] == -200.0 and ls["2.1.04.02"]["resolvido"] == 0.0
    db.close()


def test_sobra_resolvida_parcial(app_db):
    """resolve a sobra e DEPOIS constitui mais da mesma rubrica → parte resolvida, parte ainda em aberto."""
    db = app_db.get_session(); ot, oid = "loja", 763; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0}, ref_base="pf1:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef")    # sobra 100
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.07", ref="rs")     # resolvido 100
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 500.0}, ref_base="pf2:P")  # + 500
    l = _linhas(db, ot, oid)["2.1.04.07"]
    assert l["saldo"] == 600.0 and l["resolvido"] == 100.0                  # bruto 1500-900, 100 já resolvido
    assert l["saldo_aberto"] == 500.0                                       # 600 − 100 ainda em aberto
    db.close()


def test_apos_conciliar_final_saldo_aberto_zerado(app_db):
    """Projeto encerrado (etapa 21 → status concluido): conciliar_final fecha tudo, saldo_aberto = 0 em
    TODAS as rubricas, mesmo com o saldo bruto/resolvido ainda visíveis para auditoria."""
    db = app_db.get_session(); ot, oid = "loja", 765; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P",
        {"custo_fabrica": 1000.0, "frete_fabrica": 400.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 900.0, ref="ef06")   # sobra 100
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 450.0, ref="ef07")   # falta -50
    mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos={
        "2.1.04.06": {"veredito": "receber"},
        "2.1.04.07": {"veredito": "absorver"},
    })
    for l in mc.reconciliacao(db, ot, oid, projeto_id="P")["provisoes"]:
        assert l["saldo_aberto"] == 0.0, l["codigo"]
    assert mc.reconciliacao(db, ot, oid, projeto_id="P")["totais"]["saldo_aberto"] == 0.0
    db.close()


def test_totais_saldo_aberto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 764; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"frete_fabrica": 1000.0, "montagem": 500.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 900.0, ref="ef7")   # sobra 100 (aberto)
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.07", ref="rs7")    # resolve → aberto 0
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.02", 300.0, ref="ef2")   # sobra 200 (aberto)
    tot = mc.reconciliacao(db, ot, oid, projeto_id="P")["totais"]
    assert tot["saldo_aberto"] == 200.0                                     # só a montagem segue em aberto
    db.close()
