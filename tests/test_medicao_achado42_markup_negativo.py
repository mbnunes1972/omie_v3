# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-42 — medição original pedida pelo Marcelo (markup pode
ser <= 0?) e as DUAS metades do DECIDIDO 02/09 fechando o achado: o portão do desconto
(comissão/fidelidade travadas — ver tests/test_aceite_achado42_portao.py) e o realinhamento de
`decisao_valida` a Δ a cobrar (aqui).

Medição original: `comissao_arq_pct`/`fidelidade_pct` não tinham limite (ao contrário de
`desconto_pct`). Uma comissão de 150% já derrubava `Val_Liq` abaixo de zero, e com CFO > 0 o
markup virava negativo — com o portão (DECIDIDO 02/09), isso passa a exigir autorização (ou é
recusado de vez, se a margem for negativa)."""
import mod_negociacao as mn


def test_comissao_sem_limite_derruba_markup_abaixo_de_zero():
    d = mn.calcular_orcamento(
        [{"VBVA": 10000.0, "CFA": 5000.0, "desc_amb_pct": 0.0}],
        {"incluir_custos": False, "comissao_arq_ativa": True, "comissao_arq_pct": 150.0},
        desc_orc_pct=0.0)
    assert d["Val_Liq"] == -5000.0, "VAVO 10000 - comissão 15000 (150% de 10000) = -5000"
    assert d["Markup"] == -1.0, "markup negativo — não é só zero, o teto teórico é ilimitado pra baixo"


def test_montar_decisao_agora_segue_valor_contrato_mesmo_com_markup_negativo():
    """A 2ª metade do DECIDIDO 02/09: antes do realinhamento, com markup negativo Δ a cobrar
    invertia sinal contra Δ custo e `montar_decisao`/`decisao_valida` (ancorados em Δ custo)
    recusavam qualquer botão que a tela oferecesse (Δ a cobrar, B4/ACHADO-39). Realinhado: as
    duas pontas leem a MESMA grandeza — a divergência é IMPOSSÍVEL agora, não só protegida pelo
    portão do item 1. Via `montar_decisao` (não `decisao_valida` direto): é ali que o argumento
    passado mudou de Δ custo pra Δ a cobrar — testar `decisao_valida` isolada com um valor literal
    não pegaria uma regressão de QUAL argumento o chamador passa."""
    import mod_conciliacao_pe as mc_pe
    diferenca_cfo = 1000.0   # custo SUBIU
    markup = -1.0
    dvc = mc_pe.diferenca_valor_contrato_estimada(diferenca_cfo=diferenca_cfo, markup=markup)
    assert dvc == -1000.0, "Δ a cobrar negativo enquanto Δ custo é positivo — sinais opostos"

    # os mesmos botões que a tela ofereceria (manter/estornar, Δ a cobrar negativo) são os que
    # montar_decisao aceita agora.
    mc_pe.montar_decisao(pool_ambiente_id=1, diferenca_cfo=diferenca_cfo,
                         diferenca_valor_contrato=dvc, tipo_decisao="manter")
    mc_pe.montar_decisao(pool_ambiente_id=1, diferenca_cfo=diferenca_cfo,
                         diferenca_valor_contrato=dvc, tipo_decisao="estornar")
    import pytest
    with pytest.raises(ValueError):
        mc_pe.montar_decisao(pool_ambiente_id=1, diferenca_cfo=diferenca_cfo,
                             diferenca_valor_contrato=dvc, tipo_decisao="absorver")
    with pytest.raises(ValueError):
        mc_pe.montar_decisao(pool_ambiente_id=1, diferenca_cfo=diferenca_cfo,
                             diferenca_valor_contrato=dvc, tipo_decisao="cobrar")
