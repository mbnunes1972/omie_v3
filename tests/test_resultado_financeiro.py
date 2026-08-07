"""Fatia B (resultado da venda) — RESULTADO FINANCEIRO, ramo FINANCEIRA.

Quando o financiamento corre por uma financeira (Aymoré/Cartão), o Cust_Fin é DESPESA
financeira (taxa/deságio absorvido). Tratada como rubrica provisionada:
- constituída no contrato (ativo diferido 1.1.06.19 × provisão 2.1.04.19), sem tocar a DRE;
- reconhecida por rota PRÓPRIA (5.5.04 Custo Financeiro × baixa do ativo) — NÃO entra no matching
  operacional da NF-e (como impostos);
- ajustável na AF via ajustar_provisao_delta (#11).

(O ramo LOJA — receita financeira a apropriar por parcela — vem na etapa seguinte.)
"""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_custo_financeiro_constitui_provisao_sem_tocar_dre(app_db):
    db = app_db.get_session(); ot, oid = "loja", 960; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 500.0}, ref_base="pf:P")
    assert _s(db, ot, oid, "1.1.06.19") == 500.0
    assert _s(db, ot, oid, "2.1.04.19") == 500.0
    assert _s(db, ot, oid, "5.5.04") == 0.0     # despesa financeira NÃO reconhecida no contrato
    db.close()


def test_custo_financeiro_fica_fora_do_reconhecimento_generico(app_db):
    """Custo Financeiro tem rota própria (reconhecer_custo_financeiro) — nem o reconhecimento genérico
    de despesa (usado por efetivar_provisao/mod_assistencias) nem a efetivação manual tocam
    5.5.04/1.1.06.19, senão duplicaria com a rota própria."""
    db = app_db.get_session(); ot, oid = "loja", 961; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 500.0}, ref_base="pf:P")
    assert mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.19", 500.0, ref="ef:P") is None
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.19", 500.0, ref="ef2:P")   # só passivo, sem despesa
    assert _s(db, ot, oid, "1.1.06.19") == 500.0   # ativo intacto — rota própria não foi acionada
    assert _s(db, ot, oid, "5.5.04") == 0.0
    db.close()


def test_custo_financeiro_reconhecimento_por_rota_propria(app_db):
    db = app_db.get_session(); ot, oid = "loja", 962; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 500.0}, ref_base="pf:P")
    mc.registrar_evento(db, ot, oid, "reconhecimento_despesa_custo_financeiro", 500.0, projeto_id="P", ref="rf:P")
    assert _s(db, ot, oid, "5.5.04") == 500.0      # despesa financeira reconhecida (resultado financeiro)
    assert _s(db, ot, oid, "1.1.06.19") == 0.0     # ativo diferido baixado
    assert _s(db, ot, oid, "2.1.04.19") == 500.0   # provisão sobrevive (paga à financeira depois)
    db.close()


def test_custo_financeiro_ajuste_delta_af(app_db):
    db = app_db.get_session(); ot, oid = "loja", 963; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 500.0}, ref_base="pf:P")
    mc.ajustar_provisao_delta(db, ot, oid, "P", "custo_financeiro", 500.0, 620.0, ref="af:P:1:custo_financeiro:rev1")
    assert _s(db, ot, oid, "2.1.04.19") == 620.0   # +120
    assert _s(db, ot, oid, "1.1.06.19") == 620.0
    assert _s(db, ot, oid, "5.5.04") == 0.0        # ajuste NÃO toca a DRE (#11)
    db.close()


# ── Ramo LOJA (financiamento direto) — recebíveis com juros a apropriar, SEM despesa ──

def test_financiamento_direto_juros_a_apropriar_no_contrato(app_db):
    db = app_db.get_session(); ot, oid = "loja", 964; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 300.0, projeto_id="P", ref="jd:P")
    assert _s(db, ot, oid, "1.1.07") == 300.0    # recebível dos juros (só juros; VAVO fica no 1.1.02)
    assert _s(db, ot, oid, "2.1.07") == 300.0    # receita financeira a apropriar (diferida)
    assert _s(db, ot, oid, "4.4.03") == 0.0      # ainda não realizada
    db.close()


def test_financiamento_direto_recebe_e_apropria_por_parcela(app_db):
    db = app_db.get_session(); ot, oid = "loja", 965; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 300.0, projeto_id="P", ref="jd:P")
    mc.registrar_evento(db, ot, oid, "receber_parcela_direto", 100.0, projeto_id="P", ref="rp:P:1")
    assert _s(db, ot, oid, "1.1.01") == 100.0    # caixa
    assert _s(db, ot, oid, "1.1.07") == 200.0    # recebível baixado
    mc.registrar_evento(db, ot, oid, "apropriar_receita_financeira", 100.0, projeto_id="P", ref="ap:P:1")
    assert _s(db, ot, oid, "2.1.07") == 200.0    # a apropriar reduz na competência
    assert _s(db, ot, oid, "4.4.03") == 100.0    # receita financeira realizada
    db.close()


def test_financiamento_direto_ciclo_completo_fecha_sem_despesa(app_db):
    db = app_db.get_session(); ot, oid = "loja", 966; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 300.0, projeto_id="P", ref="jd:P")
    for i in (1, 2, 3):
        mc.registrar_evento(db, ot, oid, "receber_parcela_direto", 100.0, projeto_id="P", ref="rp:P:%d" % i)
        mc.registrar_evento(db, ot, oid, "apropriar_receita_financeira", 100.0, projeto_id="P", ref="ap:P:%d" % i)
    assert _s(db, ot, oid, "1.1.07") == 0.0      # recebível zerado
    assert _s(db, ot, oid, "2.1.07") == 0.0      # tudo apropriado
    assert _s(db, ot, oid, "4.4.03") == 300.0    # receita financeira total realizada
    assert _s(db, ot, oid, "1.1.01") == 300.0    # caixa recebido
    assert _s(db, ot, oid, "5.5.04") == 0.0      # ramo loja NÃO tem despesa financeira (capital próprio)
    db.close()


# ── Troca de ramo na AF (box) — reverte um ramo e constitui o outro (Fatia B.2) ──

def test_troca_loja_para_antecipacao_reverte_receita_e_constitui_provisao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 970; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 1000.0, projeto_id="P", ref="jd:P")
    novo = mc.trocar_ramo_custo_financeiro(db, ot, oid, "P", "loja", "loja_antecipacao", 1000.0, ref_base="troca:P")
    assert novo == "loja_antecipacao"
    assert _s(db, ot, oid, "1.1.07") == 0.0 and _s(db, ot, oid, "2.1.07") == 0.0     # receita revertida
    assert _s(db, ot, oid, "1.1.06.19") == 1000.0 and _s(db, ot, oid, "2.1.04.19") == 1000.0  # provisão constituída
    db.close()


def test_troca_financeira_para_loja_reverte_provisao_e_constitui_receita(app_db):
    db = app_db.get_session(); ot, oid = "loja", 971; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 1000.0, projeto_id="P", ref="cf:P")
    mc.trocar_ramo_custo_financeiro(db, ot, oid, "P", "financeira", "loja", 1000.0, ref_base="troca:P")
    assert _s(db, ot, oid, "1.1.06.19") == 0.0 and _s(db, ot, oid, "2.1.04.19") == 0.0  # provisão revertida
    assert _s(db, ot, oid, "1.1.07") == 1000.0 and _s(db, ot, oid, "2.1.07") == 1000.0  # receita constituída
    db.close()


def test_troca_financeira_para_antecipacao_e_noop_contabil(app_db):
    db = app_db.get_session(); ot, oid = "loja", 972; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 1000.0, projeto_id="P", ref="cf:P")
    novo = mc.trocar_ramo_custo_financeiro(db, ot, oid, "P", "financeira", "loja_antecipacao", 1000.0, ref_base="troca:P")
    assert novo == "loja_antecipacao"
    # ambos usam a mesma provisão → nada muda no razão (só a conta de despesa no reconhecimento futuro)
    assert _s(db, ot, oid, "1.1.06.19") == 1000.0 and _s(db, ot, oid, "2.1.04.19") == 1000.0
    db.close()


def test_custo_financeiro_fora_da_conciliacao_final(app_db):
    # 🔴 (Vera): a Provisão de Custo Financeiro tem rota própria (custo real apurado depois) — NÃO pode
    # ser resolvida à força na Conciliação Final como "sobra" → viraria receita fictícia em 4.4.02.
    db = app_db.get_session(); ot, oid = "loja", 973; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 1000.0, projeto_id="P", ref="cf:P")
    out = mc.conciliar_final(db, ot, oid, "P", ref_base="conc:P")
    assert "2.1.04.19" not in out                   # fora da conciliação (como impostos)
    assert _s(db, ot, oid, "2.1.04.19") == 1000.0    # provisão intacta (aguarda o custo real)
    assert _s(db, ot, oid, "4.4.02") == 0.0          # SEM receita fictícia
    db.close()


# ── Reconhecimento do custo financeiro (gatilho quando o custo real é apurado) ──

def test_reconhecer_antecipacao_debita_5_5_03_e_baixa_ativo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 974; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 1000.0, projeto_id="P", ref="cf:P")
    mc.reconhecer_custo_financeiro(db, ot, oid, "P", "loja_antecipacao", 1000.0, ref="ant:P")
    assert _s(db, ot, oid, "5.5.03") == 1000.0     # Custo de Antecipação de Recebíveis (DRE)
    assert _s(db, ot, oid, "1.1.06.19") == 0.0     # ativo diferido baixado
    assert _s(db, ot, oid, "2.1.04.19") == 1000.0  # provisão SOBREVIVE (paga ao banco depois)
    db.close()


def test_reconhecer_financeira_usa_5_5_04(app_db):
    db = app_db.get_session(); ot, oid = "loja", 975; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 800.0, projeto_id="P", ref="cf:P")
    mc.reconhecer_custo_financeiro(db, ot, oid, "P", "financeira", 800.0, ref="fin:P")
    assert _s(db, ot, oid, "5.5.04") == 800.0
    assert _s(db, ot, oid, "1.1.06.19") == 0.0
    db.close()


def test_reconhecer_capado_ao_ativo_em_aberto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 976; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 1000.0, projeto_id="P", ref="cf:P")
    mc.reconhecer_custo_financeiro(db, ot, oid, "P", "loja_antecipacao", 1500.0, ref="ant:P")  # pede 1500
    assert _s(db, ot, oid, "5.5.03") == 1000.0     # reconhece só até o ativo constituído
    assert _s(db, ot, oid, "1.1.06.19") == 0.0
    db.close()


def test_reconhecer_ramo_loja_nao_tem_despesa(app_db):
    db = app_db.get_session(); ot, oid = "loja", 977; mc.seed_plano(db, ot, oid)
    out = mc.reconhecer_custo_financeiro(db, ot, oid, "P", "loja", 1000.0, ref="x:P")
    assert out is None
    assert _s(db, ot, oid, "5.5.03") == 0.0 and _s(db, ot, oid, "5.5.04") == 0.0
    db.close()


def test_antecipacao_ponta_a_ponta_sem_receita_ficticia(app_db):
    # ciclo completo: constitui → reconhece antecipação → conciliar_final NÃO gera receita fictícia
    db = app_db.get_session(); ot, oid = "loja", 978; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 1000.0, projeto_id="P", ref="cf:P")
    mc.reconhecer_custo_financeiro(db, ot, oid, "P", "loja_antecipacao", 1000.0, ref="ant:P")
    mc.conciliar_final(db, ot, oid, "P", ref_base="conc:P")
    assert _s(db, ot, oid, "5.5.03") == 1000.0     # despesa reconhecida (DRE)
    assert _s(db, ot, oid, "4.4.02") == 0.0        # SEM receita fictícia
    assert _s(db, ot, oid, "2.1.04.19") == 1000.0  # provisão (a pagar ao banco) segue aberta
    db.close()


# ── Ramo loja: apropriação da receita de juros por parcela recebida ──

def test_apropriar_juros_loja_baixa_recebivel_e_realiza_receita(app_db):
    db = app_db.get_session(); ot, oid = "loja", 979; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 300.0, projeto_id="P", ref="jd:P")
    mv = mc.apropriar_juros_loja(db, ot, oid, "P", 100.0, ref_base="par:P:1")
    assert mv == 100.0
    assert _s(db, ot, oid, "1.1.01") == 100.0    # caixa
    assert _s(db, ot, oid, "1.1.07") == 200.0    # recebível baixado
    assert _s(db, ot, oid, "2.1.07") == 200.0    # receita a apropriar reduz
    assert _s(db, ot, oid, "4.4.03") == 100.0    # receita financeira realizada (competência)
    db.close()


def test_apropriar_juros_loja_capado_ao_recebivel(app_db):
    db = app_db.get_session(); ot, oid = "loja", 980; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 300.0, projeto_id="P", ref="jd:P")
    mv = mc.apropriar_juros_loja(db, ot, oid, "P", 500.0, ref_base="par:P:1")  # pede 500, só há 300
    assert mv == 300.0
    assert _s(db, ot, oid, "1.1.07") == 0.0 and _s(db, ot, oid, "4.4.03") == 300.0
    db.close()

