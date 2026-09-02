# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-42 — medição pedida pelo Marcelo para fechar o risco
residual anotado no ACHADO-39: markup pode ser <= 0? SEM CONSERTO — é medição pura.

`comissao_arq_pct`/`fidelidade_pct` não têm limite (ao contrário de `desconto_pct`, que passa por
`limite_desconto` + autorização de gerente). Uma comissão de 150% (erro de digitação plausível —
150 em vez de 15) já derruba `Val_Liq` abaixo de zero, e com CFO > 0 o markup vira negativo."""
import mod_negociacao as mn


def test_comissao_sem_limite_derruba_markup_abaixo_de_zero():
    d = mn.calcular_orcamento(
        [{"VBVA": 10000.0, "CFA": 5000.0, "desc_amb_pct": 0.0}],
        {"incluir_custos": False, "comissao_arq_ativa": True, "comissao_arq_pct": 150.0},
        desc_orc_pct=0.0)
    assert d["Val_Liq"] == -5000.0, "VAVO 10000 - comissão 15000 (150% de 10000) = -5000"
    assert d["Markup"] == -1.0, "markup negativo — não é só zero, o teto teórico é ilimitado pra baixo"


def test_diferenca_valor_contrato_inverte_sinal_com_markup_negativo():
    """A consequência prática pro B4/ACHADO-39: com markup negativo, a rota fallback de
    diferenca_valor_contrato_estimada calcula Δ a cobrar de sinal OPOSTO a Δ custo."""
    import mod_conciliacao_pe as mc_pe
    diferenca_cfo = 1000.0   # custo SUBIU
    markup = -1.0
    dvc = mc_pe.diferenca_valor_contrato_estimada(diferenca_cfo=diferenca_cfo, markup=markup)
    assert dvc == -1000.0, "Δ a cobrar negativo enquanto Δ custo é positivo — sinais opostos"

    # o backend (decisao_valida) segue ancorado em Δ CUSTO — pra este ambiente só aceita
    # absorver/cobrar; a tela (B4, correta) ofereceria manter/estornar (Δ a cobrar negativo) —
    # QUALQUER clique seria recusado.
    assert mc_pe.decisao_valida(diferenca_cfo, "absorver") is True
    assert mc_pe.decisao_valida(diferenca_cfo, "cobrar") is True
    assert mc_pe.decisao_valida(diferenca_cfo, "manter") is False
    assert mc_pe.decisao_valida(diferenca_cfo, "estornar") is False
