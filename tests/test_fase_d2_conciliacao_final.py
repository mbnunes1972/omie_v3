"""FASE D2 · Fase 6 — Conciliação Final. ACHADO-16 (docs/db/TAREFA_ACHADO16.md, passo 8, 30/08):
NÃO resolve mais saldo de provisão sozinha — cada rubrica aberta exige um VEREDITO NOMEADO
('absorver' | 'receber' | 'encerrar' | 'adiar' — F2-27, docs/db/MODELO_CONTABIL.md, renomeados
de 'efetivada'/'encerrada_valor_menor'+'nao_se_aplica' (colapsados)/'ainda_vai_chegar'). Pras
rubricas com despesa em tempo real, a despesa já nasceu INTEIRA na emissão
(`reconhecer_provisoes_segmento`) — o veredito só decide pra onde vai o resíduo entre o
reconhecido e o pago: 'absorver' (FALTA) vira Despesa de Conciliação; 'receber' (SOBRA) vira
Receita de Conciliação. Impostos e Custo Financeiro ficam fora (rota própria, fora da regra de
veredito — ACHADO-01). Idempotente por ref."""
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
    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 100.0, ref_base="rec:doc1")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 900.0, ref="ef06")   # pagou 900, reconhecido 1000 (sobra 100)
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.07", 450.0, ref="ef07")   # pagou 450, reconhecido 400 (falta 50)
    # "2.1.04.06" (sobra): reverte o resíduo de 100 pra Receita de Conciliação ('receber').
    # "2.1.04.07" (falta): o excedente de 50 vira Despesa de Conciliação ('absorver').
    out = mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos={
        "2.1.04.06": {"veredito": "receber"},
        "2.1.04.07": {"veredito": "absorver"},
    })
    assert out["2.1.04.06"]["veredito"] == "receber"
    assert out["2.1.04.06"]["valor_revertido"] == 100.0
    assert out["2.1.04.07"]["veredito"] == "absorver"
    assert out["2.1.04.07"]["valor_revertido"] == 50.0
    assert _s(db, ot, oid, "2.1.04.06") == 0.0 and _s(db, ot, oid, "2.1.04.07") == 0.0   # zeradas
    assert _s(db, ot, oid, "1.1.06.06") == 0.0 and _s(db, ot, oid, "1.1.06.07") == 0.0   # ativos já zerados na emissão
    # destinos ANTIGOS — aposentados, nunca mais tocados pra esta família
    assert _s(db, ot, oid, "4.4.02") == 0.0
    assert _s(db, ot, oid, "5.6.10") == 0.0
    # destinos NOVOS (F2-27) — Conciliação, em bloco próprio
    assert _s(db, ot, oid, "4.5.01") == 100.0    # Receita de Conciliação — sobra do Custo de Fábrica
    assert _s(db, ot, oid, "5.7.01") == 50.0     # Despesa de Conciliação — falta do Frete de Fábrica
    assert _s(db, ot, oid, "5.1.01") == 1000.0   # custo de fábrica = o PROVISIONADO INTEGRAL
    assert _s(db, ot, oid, "5.1.02") == 400.0    # frete de fábrica = o PROVISIONADO INTEGRAL
    # impostos NÃO são tocados pela conciliação (rota fiscal própria) — nem aparecem nos vereditos
    assert "2.1.04.13" not in out and _s(db, ot, oid, "2.1.04.13") == 5000.0
    db.close()


def test_veredito_receber_nao_exige_motivo_mas_aceita(app_db):
    """F2-27: 'receber' (renomeado, colapso de 'encerrada_valor_menor'+'nao_se_aplica') reverte o
    saldo inteiro pra Receita de Conciliação SEM exigir motivo — a distinção "custou menos" ×
    "nunca incidiu" perdeu significado contábil (a despesa já nasceu na emissão, não há mais nada
    a diferenciar aqui). `motivo` continua aceito, como rastro opcional."""
    db = app_db.get_session(); ot, oid = "loja", 743; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"cust_esp": 120.0}, ref_base="pf:P")
    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 100.0, ref_base="rec:doc1")
    out = mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos={
        "2.1.04.20": {"veredito": "receber"},   # sem motivo — não é mais exigido
    })
    assert out["2.1.04.20"]["valor_revertido"] == 120.0
    assert _s(db, ot, oid, "2.1.04.20") == 0.0
    assert _s(db, ot, oid, "4.5.01") == 120.0
    db.close()


def test_veredito_encerrar_so_vale_com_saldo_zerado(app_db):
    """F2-27, novo: 'encerrar' (bateu exato) não lança nada — não há resíduo a levar a lugar
    nenhum. Só é oferecido quando o saldo já está zerado (vereditos_validos_para_saldo)."""
    db = app_db.get_session(); ot, oid = "loja", 746; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"cust_esp": 120.0}, ref_base="pf:P")
    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 100.0, ref_base="rec:doc1")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.20", 120.0, ref="ef:esp")   # pagou exatamente o reconhecido
    assert mc.vereditos_validos_para_saldo(0.0) == ["adiar", "encerrar"]
    v = mc.resolver_veredito_provisao(db, ot, oid, "P", "2.1.04.20", "encerrar", ref="x:encerra")
    assert v.veredito == "encerrar" and v.valor_revertido is None
    assert _s(db, ot, oid, "4.5.01") == 0.0 and _s(db, ot, oid, "5.7.01") == 0.0   # nada lançado
    db.close()


def test_veredito_adiar_mantem_projeto_aberto(app_db):
    """ACHADO-16: 'adiar' (F2-27, renomeado de 'ainda_vai_chegar') não resolve nada — a
    Conciliação Final inteira é recusada (tudo ou nada) e o projeto continua aberto até a
    despesa real ser lançada."""
    db = app_db.get_session(); ot, oid = "loja", 744; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"cust_esp": 120.0}, ref_base="pf:P")
    with pytest.raises(ValueError, match="ainda vai chegar"):
        mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos={
            "2.1.04.20": {"veredito": "adiar"},
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
        mc.resolver_veredito_provisao(db, ot, oid, "P", "2.1.04.19", "receber",
                                      ref="x", motivo="tentativa direta")
    db.close()


def test_conciliar_final_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 741; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 100.0, ref_base="rec:doc1")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 900.0, ref="ef06")
    vereditos = {"2.1.04.06": {"veredito": "receber"}}
    mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos=vereditos)
    out2 = mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P", vereditos=vereditos)   # 2ª vez
    assert out2 == {}                             # nada mais a resolver — já não há rubrica aberta
    assert _s(db, ot, oid, "1.1.06.06") == 0.0    # não duplicou (ativo continua zerado)
    assert _s(db, ot, oid, "5.1.01") == 1000.0    # despesa real = provisionado integral, intocada
    assert _s(db, ot, oid, "4.5.01") == 100.0     # não duplicou a Receita de Conciliação
    db.close()
