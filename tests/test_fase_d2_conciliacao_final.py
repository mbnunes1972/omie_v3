"""FASE D2 · Fase 6 — Conciliação Final: resolve à força TODO saldo remanescente das 10 provisões do
projeto, sem pendência. 2026-08-07: pras rubricas com despesa em tempo real (reconhecida na própria
efetivação, não mais estimada de uma vez na NF-e) o saldo remanescente CANCELA contra o ativo
diferido, SEM TOCAR A DRE — a despesa real já foi reconhecida quando efetivada; sobra/falta aqui são
só o residual mecânico entre ativo e provisão. Impostos (2.1.04.13) ficam fora (têm rota fiscal
própria). Idempotente."""
import mod_contabil as mc
import mod_ciclo


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_etapa_21_conciliacao_final_no_ciclo():
    assert "21" in mod_ciclo.ETAPAS_PRINCIPAIS
    assert mod_ciclo.ETAPA_NOME["21"] == "Conciliação Final"
    assert mod_ciclo.ETAPAS_PRINCIPAIS[-1] == "21"           # depois da 20 (Aprovação final)


def test_conciliar_final_resolve_sobra_e_falta(app_db):
    db = app_db.get_session(); ot, oid = "loja", 740; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P",
        {"custo_fabrica": 1000.0, "frete_fabrica": 400.0, "impostos": 5000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 900.0, ref="ef06")   # sobra 100 — despesa real já reconhecida
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 450.0, ref="ef07")   # falta 50 — idem
    out = mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P")
    assert out.get("2.1.04.06") == 100.0 and out.get("2.1.04.07") == -50.0
    assert _s(db, ot, oid, "2.1.04.06") == 0.0 and _s(db, ot, oid, "2.1.04.07") == 0.0   # zeradas
    assert _s(db, ot, oid, "1.1.06.06") == 0.0 and _s(db, ot, oid, "1.1.06.07") == 0.0   # ativos cancelados junto
    # SEM tocar DRE — a despesa real (900/450) já tinha sido reconhecida na própria efetivação;
    # sobra/falta aqui são só o residual mecânico entre ativo e provisão.
    assert _s(db, ot, oid, "4.4.02") == 0.0
    assert _s(db, ot, oid, "5.6.10") == 0.0
    assert _s(db, ot, oid, "5.1.01") == 900.0    # custo de fábrica, real, intocado
    assert _s(db, ot, oid, "5.1.02") == 450.0    # frete de fábrica, real, intocado
    # impostos NÃO são tocados pela conciliação (rota fiscal própria)
    assert "2.1.04.13" not in out and _s(db, ot, oid, "2.1.04.13") == 5000.0
    db.close()


def test_conciliar_final_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 741; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 900.0, ref="ef06")
    mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P")
    out2 = mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P")   # 2ª vez
    assert out2 == {}                             # nada mais a resolver
    assert _s(db, ot, oid, "1.1.06.06") == 0.0    # não duplicou (ativo continua zerado)
    assert _s(db, ot, oid, "5.1.01") == 900.0     # despesa real, intocada
    db.close()
