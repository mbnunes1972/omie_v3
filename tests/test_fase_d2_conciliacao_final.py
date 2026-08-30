"""FASE D2 · Fase 6 — Conciliação Final. ACHADO-16 (docs/db/TAREFA_ACHADO16.md, passo 8, 30/08):
NÃO resolve mais saldo de provisão sozinha — cada rubrica aberta exige um VEREDITO NOMEADO
('efetivada' | 'encerrada_valor_menor' | 'nao_se_aplica' | 'ainda_vai_chegar'). Pras rubricas com
despesa em tempo real, o veredito aplica o mesmo mecanismo de 2026-08-07 (cancela o residual
mecânico contra o ativo diferido, SEM TOCAR A DRE quando a despesa real já foi reconhecida —
'efetivada', para FALTA — ou reconhece o real e SÓ ENTÃO reverte a sobra genuína —
'encerrada_valor_menor', para SOBRA). Impostos e Custo Financeiro ficam fora (rota própria, fora
da regra de veredito — ACHADO-01). Idempotente por ref."""
import pytest

import mod_contabil as mc
import mod_ciclo


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_etapa_21_conciliacao_final_no_ciclo():
    assert "21" in mod_ciclo.ETAPAS_PRINCIPAIS
    assert mod_ciclo.ETAPA_NOME["21"] == "Conciliação Final"
    assert mod_ciclo.ETAPAS_PRINCIPAIS[-1] == "21"           # depois da 20 (Aprovação final)


def test_conciliar_final_sem_vereditos_recusa(app_db):
    """ACHADO-16: sem veredito para uma rubrica aberta, a Conciliação Final recusa — não resolve
    mais nada sozinha."""
    db = app_db.get_session(); ot, oid = "loja", 742; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    with pytest.raises(ValueError, match="falta veredito"):
        mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos={})
    assert _s(db, ot, oid, "2.1.04.06") == 1000.0   # nada foi tocado — recusa é tudo ou nada
    db.close()


def test_conciliar_final_resolve_sobra_e_falta_com_veredito(app_db):
    db = app_db.get_session(); ot, oid = "loja", 740; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P",
        {"custo_fabrica": 1000.0, "frete_fabrica": 400.0, "impostos": 5000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 900.0, ref="ef06")   # sobra 100 — despesa real já reconhecida
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 450.0, ref="ef07")   # falta 50 — idem
    # "2.1.04.06" (sobra): já efetivado 900 ANTES desta chamada — nada novo a efetivar agora, só
    # reverter o resíduo de 100 (encerrada_valor_menor com valor_efetivado=0, a rubrica que já foi
    # efetivada mais cedo no projeto). "2.1.04.07" (falta): despesa real já reconhecida a cada
    # efetivação — 'efetivada'.
    out = mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos={
        "2.1.04.06": {"veredito": "encerrada_valor_menor", "valor_efetivado": 0},
        "2.1.04.07": {"veredito": "efetivada"},
    })
    assert out["2.1.04.06"]["veredito"] == "encerrada_valor_menor"
    assert out["2.1.04.06"]["valor_revertido"] == 100.0
    assert out["2.1.04.07"]["veredito"] == "efetivada"
    assert _s(db, ot, oid, "2.1.04.06") == 0.0 and _s(db, ot, oid, "2.1.04.07") == 0.0   # zeradas
    assert _s(db, ot, oid, "1.1.06.06") == 0.0 and _s(db, ot, oid, "1.1.06.07") == 0.0   # ativos cancelados junto
    # SEM tocar DRE de novo — a despesa real (900/450) já tinha sido reconhecida na própria
    # efetivação; sobra/falta aqui são só o residual mecânico entre ativo e provisão.
    assert _s(db, ot, oid, "4.4.02") == 0.0
    assert _s(db, ot, oid, "5.6.10") == 0.0
    assert _s(db, ot, oid, "5.1.01") == 900.0    # custo de fábrica, real, intocado
    assert _s(db, ot, oid, "5.1.02") == 450.0    # frete de fábrica, real, intocado
    # impostos NÃO são tocados pela conciliação (rota fiscal própria) — nem aparecem nos vereditos
    assert "2.1.04.13" not in out and _s(db, ot, oid, "2.1.04.13") == 5000.0
    db.close()


def test_veredito_nao_se_aplica_sem_motivo_recusa(app_db):
    """ACHADO-16: 'não se aplica' reverte o saldo inteiro, mas exige motivo escrito — sem ele é
    recusado, e nada é tocado (mesma regra tudo-ou-nada de conciliar_final)."""
    db = app_db.get_session(); ot, oid = "loja", 743; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"cust_esp": 120.0}, ref_base="pf:P")
    with pytest.raises(ValueError, match="motivo"):
        mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos={
            "2.1.04.20": {"veredito": "nao_se_aplica"},
        })
    assert _s(db, ot, oid, "2.1.04.20") == 120.0   # recusa não toca nada
    out = mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos={
        "2.1.04.20": {"veredito": "nao_se_aplica", "motivo": "não incidiu neste projeto"},
    })
    assert out["2.1.04.20"]["valor_revertido"] == 120.0
    assert _s(db, ot, oid, "2.1.04.20") == 0.0
    db.close()


def test_veredito_ainda_vai_chegar_mantem_projeto_aberto(app_db):
    """ACHADO-16: 'ainda vai chegar' não resolve nada — a Conciliação Final inteira é recusada
    (tudo ou nada) e o projeto continua aberto até a despesa real ser lançada."""
    db = app_db.get_session(); ot, oid = "loja", 744; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"cust_esp": 120.0}, ref_base="pf:P")
    with pytest.raises(ValueError, match="ainda vai chegar"):
        mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos={
            "2.1.04.20": {"veredito": "ainda_vai_chegar"},
        })
    assert _s(db, ot, oid, "2.1.04.20") == 120.0   # nada resolvido — projeto segue aberto
    db.close()


def test_custo_financeiro_nao_segue_regra_de_reversao(app_db):
    """ACHADO-01 (guarda): custo financeiro (2.1.04.19) fica fora da regra de veredito/reversão —
    nem exige veredito na Conciliação Final, nem aceita um diretamente em
    resolver_veredito_provisao."""
    db = app_db.get_session(); ot, oid = "loja", 745; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 1000.0, projeto_id="P", ref="cf:P")
    out = mc.conciliar_final(db, ot, oid, "P", ref_base="conc:P", vereditos={})
    assert "2.1.04.19" not in out
    assert _s(db, ot, oid, "2.1.04.19") == 1000.0   # provisão intacta, aguarda o custo real
    with pytest.raises(ValueError, match="ACHADO-01"):
        mc.resolver_veredito_provisao(db, ot, oid, "P", "2.1.04.19", "nao_se_aplica",
                                      ref="x", motivo="tentativa direta")
    db.close()


def test_conciliar_final_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 741; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 900.0, ref="ef06")
    vereditos = {"2.1.04.06": {"veredito": "encerrada_valor_menor", "valor_efetivado": 0}}
    mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos=vereditos)
    out2 = mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos=vereditos)   # 2ª vez
    assert out2 == {}                             # nada mais a resolver — já não há rubrica aberta
    assert _s(db, ot, oid, "1.1.06.06") == 0.0    # não duplicou (ativo continua zerado)
    assert _s(db, ot, oid, "5.1.01") == 900.0     # despesa real, intocada
    db.close()
