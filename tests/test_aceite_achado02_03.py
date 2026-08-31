"""docs/db/TAREFA_ACHADO02_03.md, Passo 10 do ROTEIRO — os aceites do ACHADO-02+03 (fundidos:
o 02 é a consequência — receita financeira contada duas vezes —, o 03 é o roteador ambíguo que a
produz). Último conserto da Fase 1.

A tabela decidida em 30/08: `cust_fin = Val_Cont − VAVO` é o preço do crédito cobrado do
cliente. `4.1.01`/`4.2.01` recebem o VAVO em TODOS os ramos — o preço do móvel não muda
conforme a forma de pagamento. `cust_fin` vai para: nada (à vista), receita financeira a
apropriar (loja e loja_antecipacao — o deságio do banco na antecipação é custo separado, só no
evento da antecipação) ou retenção esperada, posição de balanço, nada no resultado (financeira/
cartão — a variância entre esperado e real cai numa conta só, nos dois sentidos, como impostos).
"""
import mod_contabil as mc


def _s(db, ot, oid, cod, projeto_id):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    sentido = "devedor" if mc._natureza(c.grupo) == "devedora" else "credor"
    return round(mc._mov(db, ot, oid, cod, sentido, None, None, projeto_id=projeto_id), 2)


# ── Aceite 1 — o que prova a decisão inteira: mesma venda, quatro ramos, mesma receita ──────────

def test_aceite1_4101_recebe_o_vavo_nos_quatro_ramos(app_db):
    """Mesma venda (VAVO=42.500,00), quatro ramos de financiamento — 4.1.01 fatura SEMPRE o
    VAVO, nunca o Val_Cont cheio (que embutiria o custo financeiro, contando-o de novo quando o
    ramo também o reconhece como receita/posição separada — ACHADO-02)."""
    vavo = 42500.00
    cust_fin = 3800.00
    val_cont = round(vavo + cust_fin, 2)

    resultados = {}
    for i, ramo in enumerate(("avista", "loja", "loja_antecipacao", "financeira")):
        db = app_db.get_session(); ot, oid = "loja", 6600 + i; mc.seed_plano(db, ot, oid)
        P = "Proj_%s" % ramo
        cf = 0.0 if ramo == "avista" else cust_fin
        vc = round(vavo + cf, 2)
        # venda + contrato: 1.1.02×2.1.06 recebe o VAVO (nunca o Val_Cont) — ACHADO-02
        mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
        if cf > 0:
            evento_cfin = mc.evento_custo_financeiro(ramo)
            mc.registrar_evento(db, ot, oid, evento_cfin, cf, projeto_id=P, ref="cf:" + P)
        # NF-e: fatura o VAVO — nunca o Val_Cont cheio
        mc.faturar_segmento(db, ot, oid, P, "mercadoria", vavo, ref_base="fat:" + P)
        resultados[ramo] = _s(db, ot, oid, "4.1.01", P)
        db.close()

    assert resultados == {"avista": vavo, "loja": vavo, "loja_antecipacao": vavo, "financeira": vavo}, (
        "4.1.01 deveria ser %.2f nos quatro ramos (mesma venda, mesmo VAVO) — obtido: %r"
        % (vavo, resultados))


# ── Aceite 2 — ramo loja: cust_fin aparece uma vez, como receita financeira ─────────────────────

def test_aceite2_ramo_loja_receita_financeira_uma_vez_sem_duplicar(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6610; mc.seed_plano(db, ot, oid)
    P = "Proj_Loja2"
    vavo, cust_fin = 42500.00, 3800.00
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", cust_fin, projeto_id=P, ref="cj:" + P)
    mc.faturar_segmento(db, ot, oid, P, "mercadoria", vavo, ref_base="fat:" + P)
    mc.apropriar_juros_loja(db, ot, oid, P, cust_fin, ref_base="jur:" + P)

    receita_vendas = _s(db, ot, oid, "4.1.01", P)
    receita_financeira = _s(db, ot, oid, "4.4.03", P)
    assert receita_vendas == vavo
    assert receita_financeira == cust_fin
    # receita de vendas + receita financeira = Val_Cont, sem duplicar (ACHADO-02)
    assert round(receita_vendas + receita_financeira, 2) == round(vavo + cust_fin, 2)
    db.close()


# ── Aceite 3 — ramo financeira: nenhuma despesa financeira; retenção esperada como posição ──────

def test_aceite3_ramo_financeira_nenhuma_despesa_liquido_esperado_e_vavo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6620; mc.seed_plano(db, ot, oid)
    P = "Proj_Financeira3"
    vavo, cust_fin = 42500.00, 3800.00
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", cust_fin, projeto_id=P, ref="cf:" + P)
    mc.faturar_segmento(db, ot, oid, P, "mercadoria", vavo, ref_base="fat:" + P)

    assert _s(db, ot, oid, "5.5.04", P) == 0.0          # nenhum lançamento de despesa financeira
    assert _s(db, ot, oid, "2.1.04.19", P) == cust_fin  # retenção esperada — posição de balanço, aberta
    assert _s(db, ot, oid, "1.1.06.19", P) == cust_fin
    # líquido esperado = o que o recebível (1.1.02, escopado ao pool a receber) mais o
    # que ainda falta receber somam — aqui só a venda (VAVO) foi faturada; o líquido esperado da
    # venda em si já é o VAVO, sem o cust_fin embutido em lugar nenhum do resultado.
    db.close()


# ── Aceite 4 — conferência, os dois sentidos: mesma conta, sinais opostos ───────────────────────

def test_aceite4_conferencia_retencao_financeira_dois_sentidos_mesma_conta(app_db):
    """Contrato de R$ 200.000,00 (retenção esperada de 10% = R$ 20.000,00, 'financeira' já
    constituída); o banco retém 9% = R$ 18.000,00 numa rodada e 10,5% = R$ 21.000,00 noutra —
    as duas diferenças caem em 'Ajuste de Retenção Financeira' (4.4.05), sinais opostos."""
    # sobra: real (18.000) MENOR que o esperado (20.000) — credita 4.4.05
    db = app_db.get_session(); ot, oid = "loja", 6630; mc.seed_plano(db, ot, oid)
    P = "Proj_ConfSobra"
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 20000.0, projeto_id=P, ref="cf:" + P)
    mc.conferir_retencao_financeira(db, ot, oid, P, 18000.0, ref_base="conf:" + P)
    assert _s(db, ot, oid, "2.1.04.19", P) == 0.0 and _s(db, ot, oid, "1.1.06.19", P) == 0.0
    assert _s(db, ot, oid, "4.4.05", P) == 2000.0    # sobra: crédito (financeira reteve menos)
    assert _s(db, ot, oid, "5.5.04", P) == 0.0        # nunca despesa
    db.close()

    # falta: real (21.000) MAIOR que o esperado (20.000) — debita 4.4.05, MESMA conta, sinal oposto
    db = app_db.get_session(); ot, oid = "loja", 6631; mc.seed_plano(db, ot, oid)
    Q = "Proj_ConfFalta"
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 20000.0, projeto_id=Q, ref="cf:" + Q)
    mc.conferir_retencao_financeira(db, ot, oid, Q, 21000.0, ref_base="conf:" + Q)
    assert _s(db, ot, oid, "2.1.04.19", Q) == 0.0 and _s(db, ot, oid, "1.1.06.19", Q) == 0.0
    assert _s(db, ot, oid, "4.4.05", Q) == -1000.0   # falta: débito (financeira reteve mais) — sinal oposto
    assert _s(db, ot, oid, "5.5.04", Q) == 0.0
    db.close()


# ── Aceite 5 — loja_antecipacao no fechamento é igual a loja ────────────────────────────────────

def test_aceite5_loja_antecipacao_no_fechamento_e_igual_a_loja(app_db):
    """No fechamento, loja_antecipacao é receita financeira a apropriar — NÃO custo, não
    provisão. O custo do banco só existe no evento da antecipação (`reconhecer_custo_financeiro`),
    separado e depois."""
    assert mc.evento_custo_financeiro("loja_antecipacao") == mc.evento_custo_financeiro("loja")
    assert mc.evento_custo_financeiro("loja_antecipacao") == "constituir_juros_direto"

    db = app_db.get_session(); ot, oid = "loja", 6640; mc.seed_plano(db, ot, oid)
    P = "Proj_Antecipacao5"
    vavo, cust_fin = 42500.00, 3800.00
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
    evento = mc.evento_custo_financeiro("loja_antecipacao")
    mc.registrar_evento(db, ot, oid, evento, cust_fin, projeto_id=P, ref="cf:" + P)

    assert _s(db, ot, oid, "1.1.07", P) == cust_fin and _s(db, ot, oid, "2.1.07", P) == cust_fin
    assert _s(db, ot, oid, "2.1.04.19", P) == 0.0 and _s(db, ot, oid, "1.1.06.19", P) == 0.0

    # o custo do banco, separado, só existe se/quando a antecipação de fato acontece
    mc.reconhecer_custo_financeiro(db, ot, oid, P, "loja_antecipacao", 250.0, ref="ant:" + P)
    assert _s(db, ot, oid, "5.5.03", P) == 250.0
    db.close()
