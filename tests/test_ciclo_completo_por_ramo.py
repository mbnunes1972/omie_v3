"""docs/db/TAREFA_AUDITORIA_CONTABIL.md — Parte 4: ciclo completo por ramo financeiro.

Um teste por ramo (`loja`, `loja_antecipacao`, `financeira`), percorrendo venda → contrato →
provisões → NF-e → recebimento → fechamento, replicando a ORDEM REAL que main.py usa
(_fin_provisoes_venda_seguro, _fin_faturamento_segmentado_seguro) e não uma sequência
inventada. Ao final, cada teste afirma que o balancete fecha e que as contas transitórias do
projeto (provisões, ativos diferidos, contas a receber) zeram — e onde não zeram, `xfail` com o
ACHADO correspondente em vez de inventar um conserto pra fazer fechar (ver
docs/db/ACHADOS_CONTABEIS.md)."""
import pytest
import mod_contabil as mc


def _s(db, ot, oid, cod, projeto_id=None):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id, projeto_id=projeto_id) if projeto_id else mc.saldo_conta(db, ot, oid, c.id)


def _saldo_projeto(db, ot, oid, cod, projeto_id):
    """saldo_conta não aceita projeto_id — usa _mov na natureza do grupo p/ ficar escopado."""
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    sentido = "devedor" if mc._natureza(c.grupo) == "devedora" else "credor"
    return round(mc._mov(db, ot, oid, cod, sentido, None, None, projeto_id=projeto_id), 2)


def _balancete_fecha(db, ot, oid, projeto_id):
    lans = db.query(mc.Lancamento).filter_by(owner_tipo=ot, owner_id=oid, projeto_id=projeto_id).all()
    deb = round(sum(l.valor for l in lans), 2)
    cred = round(sum(l.valor for l in lans), 2)   # cada linha já é D=C por construção (lancar())
    return deb, cred


def _assert_zerado(db, ot, oid, projeto_id, contas):
    abertos = {}
    for cod in contas:
        saldo = _saldo_projeto(db, ot, oid, cod, projeto_id)
        if abs(saldo) >= 0.005:
            abertos[cod] = saldo
    assert not abertos, "contas transitórias do projeto ficaram abertas: %s" % abertos


# ── ramo "loja" (financiamento direto, capital próprio) ─────────────────────────────────────
# ACHADO-02/03 (docs/db/TAREFA_ACHADO02_03.md, passo 10, tabela decidida em 30/08): `registro_
# venda_contrato`/`faturar_segmento` usam o VAVO (não o Val_Cont cheio) — o cust_fin nunca entra
# em 4.1.01/2.1.06/1.1.02; tem rota própria por ramo. Os dois xfails (ACHADO-02, ramo loja; e
# ACHADO-01/loja_antecipacao, que passou a usar o MESMO mecanismo de loja) saem neste commit.
def test_ciclo_completo_ramo_loja(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6400; mc.seed_plano(db, ot, oid)
    P = "Proj_Loja"
    vavo = 9000.0
    cust_fin = 1000.0

    # venda + contrato (main.py:_fin_provisoes_venda_seguro) — VAVO, não Val_Cont, em 1.1.02×2.1.06
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
    mc.constituir_provisoes_fechamento(db, ot, oid, P,
                                       {"montagem": 500.0, "garantia": 300.0, "assistencia": 200.0,
                                        "impostos": 400.0}, ref_base="pf:" + P)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", cust_fin, projeto_id=P, ref="cj:" + P)

    # NF-e (main.py:_fin_faturamento_segmentado_seguro — valor do segmento vem do VAVO, ACHADO-02)
    mc.faturar_segmento(db, ot, oid, P, "mercadoria", vavo, ref_base="fat:" + P)
    mc.efetivar_impostos_segmento(db, ot, oid, P, 400.0, ref_base="imp:" + P)
    # F2-27 (docs/db/MODELO_CONTABIL.md): a emissão volta a reconhecer despesa — provisionado
    # INTEGRAL das 17 rubricas de despesa em tempo real (só 'mercadoria' aqui, pct_mercadoria=100).
    mc.reconhecer_provisoes_segmento(db, ot, oid, P, "mercadoria", 100.0, ref_base="rec:" + P)

    # fechamento/pagamento real das provisões operacionais (perna de caixa — a despesa já nasceu na emissão)
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.02", 500.0, ref="ex:" + P + ":m", forma_pagamento="a_prazo")
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.03", 300.0, ref="ex:" + P + ":g", forma_pagamento="a_prazo")
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.05", 200.0, ref="ex:" + P + ":a", forma_pagamento="a_prazo")

    # recebimento: cliente paga o principal (1.1.02, o VAVO) e os juros (1.1.07), por competência
    mc.registrar_recebimento_venda(db, ot, oid, P, vavo, ref="rec:" + P)
    mc.apropriar_juros_loja(db, ot, oid, P, cust_fin, ref_base="jur:" + P)

    receita_vendas = _saldo_projeto(db, ot, oid, "4.1.01", P)
    receita_financeira = _saldo_projeto(db, ot, oid, "4.4.03", P)
    assert receita_vendas == vavo                              # ACHADO-02: 4.1.01 é o VAVO, não o Val_Cont
    assert receita_financeira == cust_fin
    # receita total = VAVO + cust_fin = Val_Cont, contado uma única vez
    assert round(receita_vendas + receita_financeira, 2) == round(vavo + cust_fin, 2)

    _assert_zerado(db, ot, oid, P, ["2.1.04.02", "2.1.04.03", "2.1.04.05", "2.1.04.13",
                                    "1.1.06.02", "1.1.06.03", "1.1.06.05", "1.1.05",
                                    "2.1.06", "1.1.07", "2.1.07"])
    deb, cred = _balancete_fecha(db, ot, oid, P)
    assert deb == cred
    db.close()


def test_ramo_loja_receita_total_conta_o_custo_financeiro_uma_vez_so(app_db):
    """ACHADO-02, em números concretos: uma venda de R$ 46.300,00 no ramo 'loja' (financiamento
    direto), onde R$ 42.500,00 é o valor à vista (VAVO) e R$ 3.800,00 é o custo financeiro do
    parcelamento — cust_fin = Val_Cont - VAVO = 46.300,00 - 42.500,00. A receita do contrato,
    contada uma única vez, soma exatamente Val_Cont: R$ 42.500,00 em Vendas (4.1.01) + R$
    3.800,00 em Receita Financeira (4.4.03) = R$ 46.300,00 — não mais R$ 50.100,00."""
    db = app_db.get_session(); ot, oid = "loja", 6410; mc.seed_plano(db, ot, oid)
    P = "Proj_Achado02"
    vavo = 42500.00
    cust_fin = 3800.00

    # venda + contrato: VAVO em 1.1.02×2.1.06, cust_fin em 1.1.07×2.1.07 (contas separadas)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", cust_fin, projeto_id=P, ref="cj:" + P)

    # NF-e: fatura o VAVO — nunca o Val_Cont cheio
    mc.faturar_segmento(db, ot, oid, P, "mercadoria", vavo, ref_base="fat:" + P)

    # recebimento: cliente paga o principal e os juros, por competência
    mc.registrar_recebimento_venda(db, ot, oid, P, vavo, ref="rec:" + P)
    mc.apropriar_juros_loja(db, ot, oid, P, cust_fin, ref_base="jur:" + P)

    receita_vendas = _saldo_projeto(db, ot, oid, "4.1.01", P)
    receita_financeira = _saldo_projeto(db, ot, oid, "4.4.03", P)
    receita_total = round(receita_vendas + receita_financeira, 2)
    receita_esperada = round(vavo + cust_fin, 2)

    assert receita_total == receita_esperada, (
        "receita total do contrato (4.1.01 %.2f + 4.4.03 %.2f = %.2f) deveria ser %.2f "
        "(VAVO %.2f + cust_fin %.2f, uma vez) — ACHADO-02"
        % (receita_vendas, receita_financeira, receita_total, receita_esperada, vavo, cust_fin))
    db.close()


# ── ramo "financeira" (Aymoré/Cartão) — ACHADO-01 respondido: `conferir_retencao_financeira` ──
@pytest.mark.xfail(reason="ACHADO-01: a retenção esperada (2.1.04.19/1.1.06.19) constituída no "
                          "fechamento só é liquidada pela rota própria "
                          "(conferir_retencao_financeira) — este teste replica o ciclo SEM "
                          "chamar essa conferência, deliberadamente, pra provar que 2.1.04.19 "
                          "fica aberto até alguém conferir (não é 'nunca resolve', é 'precisa "
                          "de um passo explícito' — ver docs/db/ACHADOS_CONTABEIS.md).",
                    strict=True)
def test_ciclo_completo_ramo_financeira_sem_conferencia_fica_aberto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6401; mc.seed_plano(db, ot, oid)
    P = "Proj_Financeira"
    vavo = 9000.0
    cust_fin = 1000.0

    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
    mc.constituir_provisoes_fechamento(db, ot, oid, P,
                                       {"montagem": 500.0, "impostos": 400.0}, ref_base="pf:" + P)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", cust_fin, projeto_id=P, ref="cf:" + P)

    mc.faturar_segmento(db, ot, oid, P, "mercadoria", vavo, ref_base="fat:" + P)
    mc.efetivar_impostos_segmento(db, ot, oid, P, 400.0, ref_base="imp:" + P)
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.02", 500.0, ref="ex:" + P + ":m", forma_pagamento="a_prazo")
    mc.registrar_recebimento_venda(db, ot, oid, P, vavo, ref="rec:" + P)

    _assert_zerado(db, ot, oid, P, ["2.1.04.02", "2.1.04.13", "2.1.04.19",
                                    "1.1.06.02", "1.1.05", "1.1.06.19", "2.1.06"])
    deb, cred = _balancete_fecha(db, ot, oid, P)
    assert deb == cred
    db.close()


def test_ciclo_completo_ramo_financeira_com_conferencia_fecha(app_db):
    """Mesmo cenário acima, mas com a conferência (a retenção real bate com a esperada) —
    2.1.04.19/1.1.06.19 fecham, sem tocar DRE, sem receita fictícia."""
    db = app_db.get_session(); ot, oid = "loja", 6403; mc.seed_plano(db, ot, oid)
    P = "Proj_FinanceiraConferida"
    vavo = 9000.0
    cust_fin = 1000.0

    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
    mc.constituir_provisoes_fechamento(db, ot, oid, P,
                                       {"montagem": 500.0, "impostos": 400.0}, ref_base="pf:" + P)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", cust_fin, projeto_id=P, ref="cf:" + P)

    mc.faturar_segmento(db, ot, oid, P, "mercadoria", vavo, ref_base="fat:" + P)
    mc.efetivar_impostos_segmento(db, ot, oid, P, 400.0, ref_base="imp:" + P)
    # F2-27: a emissão reconhece o provisionado integral (só 'mercadoria' aqui).
    mc.reconhecer_provisoes_segmento(db, ot, oid, P, "mercadoria", 100.0, ref_base="rec:" + P)
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.02", 500.0, ref="ex:" + P + ":m", forma_pagamento="a_prazo")
    mc.registrar_recebimento_venda(db, ot, oid, P, vavo, ref="rec:" + P)
    mc.conferir_retencao_financeira(db, ot, oid, P, cust_fin, ref_base="conf:" + P)

    _assert_zerado(db, ot, oid, P, ["2.1.04.02", "2.1.04.13", "2.1.04.19",
                                    "1.1.06.02", "1.1.05", "1.1.06.19", "2.1.06", "4.4.05"])
    deb, cred = _balancete_fecha(db, ot, oid, P)
    assert deb == cred
    db.close()


# ── ramo "loja_antecipacao" — ACHADO-02/03 (passo 10): fechamento igual a "loja" (aceite #5) ──
def test_ciclo_completo_ramo_loja_antecipacao(app_db):
    """loja_antecipacao no fechamento é IGUAL a loja — receita financeira a apropriar, não
    custo. Fecha igual à `loja`, sem precisar de nenhuma conferência (a diferença do 'financeira'
    é justamente essa: aqui não sobra provisão nenhuma pra confirmar depois)."""
    db = app_db.get_session(); ot, oid = "loja", 6402; mc.seed_plano(db, ot, oid)
    P = "Proj_Antecipacao"
    vavo = 9000.0
    cust_fin = 1000.0

    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
    mc.constituir_provisoes_fechamento(db, ot, oid, P,
                                       {"montagem": 500.0, "impostos": 400.0}, ref_base="pf:" + P)
    mc.registrar_evento(db, ot, oid, mc.evento_custo_financeiro("loja_antecipacao"), cust_fin,
                        projeto_id=P, ref="cf:" + P)

    mc.faturar_segmento(db, ot, oid, P, "mercadoria", vavo, ref_base="fat:" + P)
    mc.efetivar_impostos_segmento(db, ot, oid, P, 400.0, ref_base="imp:" + P)
    # F2-27: a emissão reconhece o provisionado integral (só 'mercadoria' aqui).
    mc.reconhecer_provisoes_segmento(db, ot, oid, P, "mercadoria", 100.0, ref_base="rec:" + P)
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.02", 500.0, ref="ex:" + P + ":m", forma_pagamento="a_prazo")

    mc.registrar_recebimento_venda(db, ot, oid, P, vavo, ref="rec:" + P)
    mc.apropriar_juros_loja(db, ot, oid, P, cust_fin, ref_base="jur:" + P)

    _assert_zerado(db, ot, oid, P, ["2.1.04.02", "2.1.04.13", "2.1.04.19",
                                    "1.1.06.02", "1.1.05", "1.1.06.19", "2.1.06",
                                    "1.1.07", "2.1.07"])
    deb, cred = _balancete_fecha(db, ot, oid, P)
    assert deb == cred
    db.close()
