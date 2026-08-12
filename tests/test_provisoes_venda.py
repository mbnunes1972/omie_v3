import mod_contabil as mc


def test_pcts_assistencia_herda_assist_pct(app_db):
    cfg = {"provisoes": {"assist_pct": 3.0}, "provisoes_contabeis": {"montagem_pct": 5.0, "garantia_pct": 2.0}}
    p = mc.pcts_provisao_venda(cfg)
    assert p == {"montagem": 5.0, "assistencia": 3.0, "garantia": 2.0}


def test_constituir_provisoes_venda(app_db):
    db = app_db.get_session()
    cfg = {"provisoes": {"assist_pct": 3.0}, "provisoes_contabeis": {"montagem_pct": 5.0, "garantia_pct": 2.0}}
    lans = mc.constituir_provisoes_venda(db, "loja", 90, "PV", 10000.0, cfg, ref_base="prov:1")
    # 3 provisões: 500 (montagem 5%), 300 (assist 3%), 200 (garantia 2%)
    vals = sorted(l["valor"] for l in lans)
    assert vals == [200.0, 300.0, 500.0]
    # idempotente: repetir com mesmo ref não duplica
    lans2 = mc.constituir_provisoes_venda(db, "loja", 90, "PV", 10000.0, cfg, ref_base="prov:1")
    n = db.query(mc.Lancamento).filter_by(owner_tipo="loja", owner_id=90).count()
    assert n == 3
    db.close()


def test_pct_zero_nao_constitui(app_db):
    db = app_db.get_session()
    cfg = {"provisoes": {"assist_pct": 0.0}, "provisoes_contabeis": {"montagem_pct": 5.0, "garantia_pct": 0.0}}
    lans = mc.constituir_provisoes_venda(db, "loja", 91, "P", 1000.0, cfg, ref_base="prov:2")
    assert len(lans) == 1 and lans[0]["valor"] == 50.0     # só montagem
    db.close()
