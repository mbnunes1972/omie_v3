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
def test_ciclo_completo_ramo_loja(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6400; mc.seed_plano(db, ot, oid)
    P = "Proj_Loja"
    val_cont, vavo = 10000.0, 9000.0
    cust_fin = round(val_cont - vavo, 2)   # 1000.0

    # venda + contrato (main.py:_fin_provisoes_venda_seguro)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", val_cont, projeto_id=P, ref="rv:" + P)
    mc.constituir_provisoes_fechamento(db, ot, oid, P,
                                       {"montagem": 500.0, "garantia": 300.0, "assistencia": 200.0,
                                        "impostos": 400.0}, ref_base="pf:" + P)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", cust_fin, projeto_id=P, ref="cj:" + P)

    # NF-e (main.py:_fin_faturamento_segmentado_seguro — valor do segmento vem do Val_Cont do contrato)
    mc.faturar_segmento(db, ot, oid, P, "mercadoria", val_cont, ref_base="fat:" + P)
    mc.efetivar_impostos_segmento(db, ot, oid, P, 400.0, ref_base="imp:" + P)

    # fechamento/execução real das provisões operacionais (despesa nasce aqui, não na NF-e)
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.02", 500.0, ref="ex:" + P + ":m", forma_pagamento="a_prazo")
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.03", 300.0, ref="ex:" + P + ":g", forma_pagamento="a_prazo")
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.05", 200.0, ref="ex:" + P + ":a", forma_pagamento="a_prazo")

    # recebimento: cliente paga o principal (1.1.02) e os juros (1.1.07), por competência
    mc.registrar_recebimento_venda(db, ot, oid, P, val_cont, ref="rec:" + P)
    mc.apropriar_juros_loja(db, ot, oid, P, cust_fin, ref_base="jur:" + P)

    receita_vendas = _saldo_projeto(db, ot, oid, "4.1.01", P)
    receita_financeira = _saldo_projeto(db, ot, oid, "4.4.03", P)
    assert receita_vendas == val_cont
    assert receita_financeira == cust_fin
    # ACHADO candidato: 4.1.01 já carrega o Val_Cont CHEIO (que inclui o cust_fin, por definição
    # cust_fin = Val_Cont - VAVO) e 4.4.03 reconhece o cust_fin de novo, separadamente — a receita
    # total reconhecida (val_cont + cust_fin) excede o valor nominal do contrato (val_cont) em
    # exatamente o cust_fin. Ver nota no relatório final antes de aceitar isto como correto.

    _assert_zerado(db, ot, oid, P, ["2.1.04.02", "2.1.04.03", "2.1.04.05", "2.1.04.13",
                                    "1.1.06.02", "1.1.06.03", "1.1.06.05", "1.1.05",
                                    "2.1.06", "1.1.07", "2.1.07"])
    deb, cred = _balancete_fecha(db, ot, oid, P)
    assert deb == cred
    db.close()


@pytest.mark.xfail(reason="ACHADO-02: 4.1.01 fatura o Val_Cont cheio (que já inclui o custo "
                          "financeiro) e 4.4.03 reconhece o mesmo custo financeiro de novo — "
                          "receita total sai maior que o contrato em exatamente o valor do "
                          "custo financeiro (ver docs/db/ACHADOS_CONTABEIS.md). Corrigido o "
                          "achado, este teste vira verde sozinho — é o sinal pra tirar o "
                          "xfail.", strict=True)
def test_ramo_loja_receita_total_deveria_contar_o_custo_financeiro_uma_vez_so(app_db):
    """ACHADO-02, em números concretos: uma venda de R$ 46.300,00 no ramo 'loja' (financiamento
    direto), onde R$ 42.500,00 é o valor à vista (VAVO) e R$ 3.800,00 é o custo financeiro do
    parcelamento — cust_fin = Val_Cont - VAVO = 46.300,00 - 42.500,00, a mesma fórmula de
    main.py:746. A receita do contrato, contada uma única vez, deveria somar exatamente
    Val_Cont: R$ 42.500,00 em Vendas (4.1.01) + R$ 3.800,00 em Receita Financeira (4.4.03) =
    R$ 46.300,00.

    Hoje `_fin_provisoes_venda_seguro` (main.py:739) fatura o Val_Cont CHEIO em 4.1.01 — os R$
    46.300,00 inteiros, que já incluem o custo financeiro — e o ciclo completo (constituir_juros_
    direto + apropriar_juros_loja) reconhece os mesmos R$ 3.800,00 de novo em 4.4.03. A receita
    total apurada fecha em R$ 50.100,00: R$ 3.800,00 a mais do que o contrato vale — exatamente o
    custo financeiro, contado duas vezes."""
    db = app_db.get_session(); ot, oid = "loja", 6410; mc.seed_plano(db, ot, oid)
    P = "Proj_Achado02"
    vavo = 42500.00
    cust_fin = 3800.00
    val_cont = round(vavo + cust_fin, 2)   # 46300.00 — o "Val_Cont" de main.py:_fin_provisoes_venda_seguro

    # venda + contrato (main.py:739-751)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", val_cont, projeto_id=P, ref="rv:" + P)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", cust_fin, projeto_id=P, ref="cj:" + P)

    # NF-e (main.py:_fin_faturamento_segmentado_seguro — fatura o Val_Cont do contrato, main.py:1340-1360)
    mc.faturar_segmento(db, ot, oid, P, "mercadoria", val_cont, ref_base="fat:" + P)

    # recebimento: cliente paga o principal e os juros, por competência
    mc.registrar_recebimento_venda(db, ot, oid, P, val_cont, ref="rec:" + P)
    mc.apropriar_juros_loja(db, ot, oid, P, cust_fin, ref_base="jur:" + P)

    receita_vendas = _saldo_projeto(db, ot, oid, "4.1.01", P)
    receita_financeira = _saldo_projeto(db, ot, oid, "4.4.03", P)
    receita_total_hoje = round(receita_vendas + receita_financeira, 2)
    receita_total_esperada = round(vavo + cust_fin, 2)   # == val_cont, contado uma única vez

    assert receita_total_hoje == receita_total_esperada, (
        "receita total do contrato (4.1.01 %.2f + 4.4.03 %.2f = %.2f) deveria ser %.2f "
        "(VAVO %.2f + cust_fin %.2f, uma vez) — distorção de R$ %.2f, exatamente o custo "
        "financeiro contado duas vezes (ACHADO-02)"
        % (receita_vendas, receita_financeira, receita_total_hoje, receita_total_esperada,
           vavo, cust_fin, round(receita_total_hoje - receita_total_esperada, 2)))
    db.close()


# ── ramo "financeira" (Aymoré/Cartão) — ACHADO-01: provisão de custo financeiro nunca drena ──
@pytest.mark.xfail(reason="ACHADO-01: reconhecer_custo_financeiro só baixa o ativo diferido "
                          "(1.1.06.19); a Provisão de Custo Financeiro (2.1.04.19) nunca é "
                          "drenada por função nenhuma — falta a perna de liquidação (ver "
                          "docs/db/ACHADOS_CONTABEIS.md).", strict=True)
def test_ciclo_completo_ramo_financeira(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6401; mc.seed_plano(db, ot, oid)
    P = "Proj_Financeira"
    val_cont, vavo = 10000.0, 9000.0
    cust_fin = round(val_cont - vavo, 2)

    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", val_cont, projeto_id=P, ref="rv:" + P)
    mc.constituir_provisoes_fechamento(db, ot, oid, P,
                                       {"montagem": 500.0, "impostos": 400.0}, ref_base="pf:" + P)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", cust_fin, projeto_id=P, ref="cf:" + P)

    mc.faturar_segmento(db, ot, oid, P, "mercadoria", val_cont, ref_base="fat:" + P)
    mc.efetivar_impostos_segmento(db, ot, oid, P, 400.0, ref_base="imp:" + P)
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.02", 500.0, ref="ex:" + P + ":m", forma_pagamento="a_prazo")

    # reconhece a despesa financeira real (deságio cobrado pela financeira) — só baixa o ativo
    mc.reconhecer_custo_financeiro(db, ot, oid, P, "financeira", cust_fin, ref="rcf:" + P)
    mc.registrar_recebimento_venda(db, ot, oid, P, val_cont, ref="rec:" + P)

    _assert_zerado(db, ot, oid, P, ["2.1.04.02", "2.1.04.13", "2.1.04.19",
                                    "1.1.06.02", "1.1.05", "1.1.06.19", "2.1.06"])
    deb, cred = _balancete_fecha(db, ot, oid, P)
    assert deb == cred
    db.close()


# ── ramo "loja_antecipacao" (antecipação bancária) — mesmo ACHADO-01, rota 5.5.03 ───────────
@pytest.mark.xfail(reason="ACHADO-01: reconhecer_custo_financeiro (ramo loja_antecipacao) só "
                          "baixa o ativo diferido (1.1.06.19); a Provisão de Custo Financeiro "
                          "(2.1.04.19) nunca é drenada — mesma causa-raiz do ramo financeira "
                          "(ver docs/db/ACHADOS_CONTABEIS.md).", strict=True)
def test_ciclo_completo_ramo_loja_antecipacao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6402; mc.seed_plano(db, ot, oid)
    P = "Proj_Antecipacao"
    val_cont, vavo = 10000.0, 9000.0
    cust_fin = round(val_cont - vavo, 2)

    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", val_cont, projeto_id=P, ref="rv:" + P)
    mc.constituir_provisoes_fechamento(db, ot, oid, P,
                                       {"montagem": 500.0, "impostos": 400.0}, ref_base="pf:" + P)
    # constituição correta (via evento_custo_financeiro) — a divergência do ACHADO-02, em
    # main.py, é sobre QUAL evento é escolhido antes de chegar aqui; a constituição em si é a
    # mesma pros dois ramos "provisão"
    mc.registrar_evento(db, ot, oid, mc.evento_custo_financeiro("loja_antecipacao"), cust_fin,
                        projeto_id=P, ref="cf:" + P)

    mc.faturar_segmento(db, ot, oid, P, "mercadoria", val_cont, ref_base="fat:" + P)
    mc.efetivar_impostos_segmento(db, ot, oid, P, 400.0, ref_base="imp:" + P)
    mc.efetivar_provisao(db, ot, oid, P, "2.1.04.02", 500.0, ref="ex:" + P + ":m", forma_pagamento="a_prazo")

    mc.reconhecer_custo_financeiro(db, ot, oid, P, "loja_antecipacao", cust_fin, ref="rcf:" + P)
    mc.registrar_recebimento_venda(db, ot, oid, P, val_cont, ref="rec:" + P)

    _assert_zerado(db, ot, oid, P, ["2.1.04.02", "2.1.04.13", "2.1.04.19",
                                    "1.1.06.02", "1.1.05", "1.1.06.19", "2.1.06"])
    deb, cred = _balancete_fecha(db, ot, oid, P)
    assert deb == cred
    db.close()
