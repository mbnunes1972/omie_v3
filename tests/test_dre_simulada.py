"""dre_simulada (2026-08-07) — DRE em modo simulado (leitura pura, nunca escreve no razão): reproduz
o antigo "matching pleno" ('competencia_estimada', despesa=constituído na data da NF-e) e uma nova
visão ('antecipacao_contrato', receita e despesa simuladas na data da venda/contrato)."""
from datetime import date, datetime

import mod_contabil as mc


def _venda_e_nfe(db, ot, oid, proj, val_cont, valores_prov, data_venda, data_nfe):
    # constituir_provisoes_fechamento não aceita `data` (a constituição em si não é usada como
    # "marco" de período no dre_simulada — só o valor CONSTITUÍDO importa; o marco de período é a
    # data do registro_venda_contrato/faturamento, ambos com `data` explícita abaixo).
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", val_cont, projeto_id=proj,
                        ref="venda:" + proj, data=data_venda)
    mc.constituir_provisoes_fechamento(db, ot, oid, proj, valores_prov, ref_base="pf:" + proj)
    mc.registrar_evento(db, ot, oid, "faturamento", val_cont, projeto_id=proj, ref="fat:" + proj, data=data_nfe)


def test_modo_invalido_levanta_erro(app_db):
    db = app_db.get_session(); ot, oid = "loja", 850; mc.seed_plano(db, ot, oid)
    try:
        mc.dre_simulada(db, ot, oid, "xpto")
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass
    db.close()


def test_competencia_estimada_usa_constituido_na_data_da_nfe(app_db):
    db = app_db.get_session(); ot, oid = "loja", 851; mc.seed_plano(db, ot, oid)
    _venda_e_nfe(db, ot, oid, "P", 100000.0, {"montagem": 1000.0, "assistencia": 300.0},
                data_venda=datetime(2026, 5, 1), data_nfe=datetime(2026, 8, 10))
    # real: nada foi efetivado ainda -> despesa real = 0
    real = mc.dre(db, ot, oid)
    assert real["cmv_csp"] == 0.0
    d = mc.dre_simulada(db, ot, oid, "competencia_estimada")
    assert d["modo"] == "competencia_estimada"
    assert d["receita_bruta"] == real["receita_bruta"] == 100000.0   # receita = a real (NF-e)
    # montagem (5.2.01) + assistência (5.2.13) -> ambas no grupo 5.2.x -> cmv_csp (S109)
    assert d["cmv_csp"] == 1300.0
    assert d["despesas_comerciais"] == 0.0
    assert d["lucro_bruto"] == round(d["receita_liquida"] - 1300.0, 2)
    db.close()


def test_competencia_estimada_respeita_periodo_pela_data_da_nfe(app_db):
    db = app_db.get_session(); ot, oid = "loja", 852; mc.seed_plano(db, ot, oid)
    _venda_e_nfe(db, ot, oid, "P", 50000.0, {"montagem": 500.0},
                data_venda=datetime(2026, 5, 1), data_nfe=datetime(2026, 8, 10))
    # fora do período (NF-e em agosto, filtro em julho) -> nada entra
    fora = mc.dre_simulada(db, ot, oid, "competencia_estimada", ini=date(2026, 7, 1), fim=date(2026, 7, 31))
    assert fora["receita_bruta"] == 0.0 and fora["cmv_csp"] == 0.0
    dentro = mc.dre_simulada(db, ot, oid, "competencia_estimada", ini=date(2026, 8, 1), fim=date(2026, 8, 31))
    assert dentro["cmv_csp"] == 500.0
    db.close()


def test_antecipacao_contrato_usa_val_cont_e_constituido_na_data_da_venda(app_db):
    db = app_db.get_session(); ot, oid = "loja", 853; mc.seed_plano(db, ot, oid)
    _venda_e_nfe(db, ot, oid, "P", 100000.0, {"montagem": 1000.0, "com_medidor": 250.0},
                data_venda=datetime(2026, 5, 1), data_nfe=datetime(2026, 8, 10))
    d = mc.dre_simulada(db, ot, oid, "antecipacao_contrato")
    assert d["receita_bruta"] == 100000.0   # Val_Cont, na data da venda (não da NF-e)
    assert d["cmv_csp"] == 1000.0
    assert d["despesas_comerciais"] == 250.0
    db.close()


def test_antecipacao_contrato_respeita_periodo_pela_data_da_venda(app_db):
    db = app_db.get_session(); ot, oid = "loja", 854; mc.seed_plano(db, ot, oid)
    _venda_e_nfe(db, ot, oid, "P", 50000.0, {"garantia": 200.0},
                data_venda=datetime(2026, 5, 1), data_nfe=datetime(2026, 8, 10))
    # dentro do período da VENDA (maio) -> entra, mesmo a NF-e sendo em agosto
    maio = mc.dre_simulada(db, ot, oid, "antecipacao_contrato", ini=date(2026, 5, 1), fim=date(2026, 5, 31))
    assert maio["receita_bruta"] == 50000.0 and maio["cmv_csp"] == 200.0
    agosto = mc.dre_simulada(db, ot, oid, "antecipacao_contrato", ini=date(2026, 8, 1), fim=date(2026, 8, 31))
    assert agosto["receita_bruta"] == 0.0 and agosto["cmv_csp"] == 0.0
    db.close()


def test_deducoes_e_outras_linhas_vem_do_real_nos_dois_modos(app_db):
    """Deduções/despesas administrativas/financeiras/outras receitas/impostos NÃO fazem parte da
    simulação — vêm sempre do dre() real, mesmo período."""
    db = app_db.get_session(); ot, oid = "loja", 855; mc.seed_plano(db, ot, oid)
    _venda_e_nfe(db, ot, oid, "P", 50000.0, {"montagem": 500.0},
                data_venda=datetime(2026, 5, 1), data_nfe=datetime(2026, 8, 10))
    c_adm = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="5.4.01").first()
    c_caixa = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="1.1.01").first()
    mc.lancar(db, ot, oid, c_adm.id, c_caixa.id, 800.0, data=datetime(2026, 8, 5), historico="aluguel")
    real = mc.dre(db, ot, oid)
    for modo in ("competencia_estimada", "antecipacao_contrato"):
        d = mc.dre_simulada(db, ot, oid, modo)
        assert d["despesas_administrativas"] == real["despesas_administrativas"] == 800.0
        assert d["deducoes"] == real["deducoes"]
        assert d["outras_receitas"] == real["outras_receitas"]
        assert d["impostos"] == real["impostos"]
    db.close()


def test_projeto_sem_provisao_ou_sem_venda_nao_quebra(app_db):
    db = app_db.get_session(); ot, oid = "loja", 856; mc.seed_plano(db, ot, oid)
    d1 = mc.dre_simulada(db, ot, oid, "competencia_estimada")
    d2 = mc.dre_simulada(db, ot, oid, "antecipacao_contrato")
    assert d1["receita_bruta"] == 0.0 and d1["cmv_csp"] == 0.0
    assert d2["receita_bruta"] == 0.0 and d2["cmv_csp"] == 0.0
    db.close()
