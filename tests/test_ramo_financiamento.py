"""Fatia B — classificação do ramo de financiamento por modalidade (mod_fin.ramo_financiamento).
financeira (Aymoré/Cartão) = despesa; loja (Venda Programada/Total Flex) = receita própria; avista = nada.
"""
import json
from types import SimpleNamespace
import mod_fin


def test_aymore_e_cartao_sao_financeira():
    assert mod_fin.ramo_financiamento("aymore") == "financeira"
    assert mod_fin.ramo_financiamento("cartao_credito") == "financeira"
    assert mod_fin.ramo_financiamento("cartao_credito_x") == "financeira"


def test_venda_programada_e_total_flex_sao_loja():
    assert mod_fin.ramo_financiamento("venda_programada") == "loja"
    assert mod_fin.ramo_financiamento("total_flex") == "loja"


def test_a_vista_e_avista():
    assert mod_fin.ramo_financiamento("a_vista") == "avista"


def test_codigo_desconhecido_default_loja_conservador():
    # default 'loja' = sem despesa (conservador: não inventa despesa financeira)
    assert mod_fin.ramo_financiamento("modalidade_nova_qualquer") == "loja"


# ── mod_recebiveis.ramo_por_tipo — vocabulário REAL do frontend (achado do usuário 2026-08-13) ──
# `mod_fin.ramo_financiamento` acima só é chamado, hoje, pelos próprios testes deste arquivo — os
# dois call sites reais (main._fin_provisoes_venda_seguro/_ramo_financeiro_efetivo) liam uma chave
# "codigo" que `Orcamento.forma_pagamento` nunca tem (o frontend grava "tipo", com valores
# abreviados: static/index.html:8560/8671/8822/9203/9411). Efeito: toda venda Aymoré/Cartão caía no
# default "loja" e nunca reconhecia a despesa financeira real. Fix: os dois call sites passaram a
# usar `mod_recebiveis.ramo_por_tipo`, que já é a tabela correta pro vocabulário do frontend.

def test_ramo_por_tipo_aymore_e_cartao_sao_financeira():
    import mod_recebiveis
    assert mod_recebiveis.ramo_por_tipo("aymore") == "financeira"
    assert mod_recebiveis.ramo_por_tipo("cartao") == "financeira"


def test_ramo_por_tipo_vp_e_tf_sao_loja():
    import mod_recebiveis
    assert mod_recebiveis.ramo_por_tipo("vp") == "loja"
    assert mod_recebiveis.ramo_por_tipo("tf") == "loja"


def test_ramo_por_tipo_avista_e_vazio():
    import mod_recebiveis
    assert mod_recebiveis.ramo_por_tipo("avista") == "avista"
    assert mod_recebiveis.ramo_por_tipo(None) == "avista"
    assert mod_recebiveis.ramo_por_tipo("") == "avista"


def test_ramo_financeiro_efetivo_le_forma_pagamento_real_do_frontend():
    """Regressão do bug: forma_pagamento no formato EXATO que o frontend grava (chave "tipo",
    não "codigo") precisa resolver pro ramo certo, não cair no default 'loja'."""
    import main
    orc_aymore = SimpleNamespace(ramo_financeiro=None,
                                 forma_pagamento=json.dumps({"tipo": "aymore", "nome_forma": "Financiamento Aymoré"}))
    assert main._ramo_financeiro_efetivo(orc_aymore) == "financeira"
    orc_cartao = SimpleNamespace(ramo_financeiro=None,
                                 forma_pagamento=json.dumps({"tipo": "cartao", "nome_forma": "Cartão de Crédito"}))
    assert main._ramo_financeiro_efetivo(orc_cartao) == "financeira"
    orc_tf = SimpleNamespace(ramo_financeiro=None,
                             forma_pagamento=json.dumps({"tipo": "tf", "nome_forma": "Total Flex"}))
    assert main._ramo_financeiro_efetivo(orc_tf) == "loja"


def test_ramo_financeiro_efetivo_respeita_override_da_af():
    """Override manual (Aprovação Financeira) sempre vence o default automático."""
    import main
    orc = SimpleNamespace(ramo_financeiro="loja",
                          forma_pagamento=json.dumps({"tipo": "aymore"}))
    assert main._ramo_financeiro_efetivo(orc) == "loja"
