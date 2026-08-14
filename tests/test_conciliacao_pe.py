"""Conciliação de Custo de Fábrica do PE na AF2 (11d) — motor puro, sem banco/contabilidade.
Spec: docs/superpowers/specs/financeiro/2026-08-14-conciliacao-pe-af2-complemento-credito-design.md
"""
import pytest

from mod_conciliacao_pe import (
    sinal_diferenca, decisao_valida, diferenca_valor_contrato, montar_decisao,
    decisao_ambiente_novo, fase_completa, agregar_complemento, agregar_estorno,
)


def test_sinal_diferenca():
    assert sinal_diferenca(300.0) == "alta"
    assert sinal_diferenca(-300.0) == "baixa"
    assert sinal_diferenca(0.0) == "zero"
    assert sinal_diferenca(None) == "zero"


def test_decisao_valida_custo_subiu_so_absorver_ou_cobrar():
    assert decisao_valida(300.0, "absorver") is True
    assert decisao_valida(300.0, "cobrar") is True
    assert decisao_valida(300.0, "manter") is False
    assert decisao_valida(300.0, "estornar") is False


def test_decisao_valida_custo_caiu_so_manter_ou_estornar():
    assert decisao_valida(-300.0, "manter") is True
    assert decisao_valida(-300.0, "estornar") is True
    assert decisao_valida(-300.0, "absorver") is False
    assert decisao_valida(-300.0, "cobrar") is False


def test_decisao_valida_zero_so_manter_ou_absorver():
    assert decisao_valida(0.0, "manter") is True
    assert decisao_valida(0.0, "absorver") is True
    assert decisao_valida(0.0, "cobrar") is False
    assert decisao_valida(0.0, "estornar") is False


def test_decisao_valida_tipo_desconhecido_falso():
    assert decisao_valida(300.0, "sei_la") is False


def test_diferenca_valor_contrato_grossup_por_markup():
    assert diferenca_valor_contrato(1000.0, 2.5) == 2500.0
    assert diferenca_valor_contrato(-1000.0, 2.5) == -2500.0
    assert diferenca_valor_contrato(1000.0, None) == 0.0


def test_montar_decisao_cobrar_custo_subiu():
    d = montar_decisao(pool_ambiente_id=7, diferenca_cfo=1000.0, markup=2.0, tipo_decisao="cobrar")
    assert d == {
        "pool_ambiente_id": 7,
        "diferenca_cfo": 1000.0,
        "diferenca_valor_contrato": 2000.0,
        "tipo_decisao": "cobrar",
        "valor_aprovado": 2000.0,   # default = módulo da diferença de valor de contrato
    }


def test_montar_decisao_estornar_valor_editado_pelo_gerente():
    # gerente edita o valor do estorno pra um número diferente do calculado
    d = montar_decisao(pool_ambiente_id=9, diferenca_cfo=-1000.0, markup=2.0,
                       tipo_decisao="estornar", valor_aprovado=1500.0)
    assert d["diferenca_valor_contrato"] == -2000.0   # cálculo original preservado (auditoria)
    assert d["valor_aprovado"] == 1500.0              # valor que de fato vai pro lançamento


def test_montar_decisao_incompativel_levanta_erro():
    with pytest.raises(ValueError):
        montar_decisao(pool_ambiente_id=1, diferenca_cfo=-500.0, markup=2.0, tipo_decisao="cobrar")
    with pytest.raises(ValueError):
        montar_decisao(pool_ambiente_id=1, diferenca_cfo=500.0, markup=2.0, tipo_decisao="estornar")


def test_decisao_ambiente_novo_sempre_cobrar_valor_cheio():
    d = decisao_ambiente_novo(pool_ambiente_id=42, valor_venda_xml=8000.0)
    assert d == {
        "pool_ambiente_id": 42,
        "diferenca_cfo": None,
        "diferenca_valor_contrato": 8000.0,
        "tipo_decisao": "cobrar",
        "valor_aprovado": 8000.0,
    }


def test_fase_completa_true_quando_todo_ambiente_tem_decisao():
    ok, faltam = fase_completa(ambientes_com_pe=[1, 2, 3], decisoes_registradas=[1, 2, 3])
    assert ok is True and faltam == []


def test_fase_completa_false_com_faltantes_ordenados():
    ok, faltam = fase_completa(ambientes_com_pe=[3, 1, 2], decisoes_registradas=[2])
    assert ok is False and faltam == [1, 3]


def test_agregar_complemento_so_soma_cobrar():
    decisoes = [
        {"tipo_decisao": "cobrar", "valor_aprovado": 2000.0},
        {"tipo_decisao": "cobrar", "valor_aprovado": 500.0},
        {"tipo_decisao": "manter", "valor_aprovado": 999.0},
        {"tipo_decisao": "estornar", "valor_aprovado": 300.0},
    ]
    assert agregar_complemento(decisoes) == 2500.0


def test_agregar_estorno_so_soma_estornar_nunca_compensa_com_cobrar():
    decisoes = [
        {"tipo_decisao": "cobrar", "valor_aprovado": 2000.0},
        {"tipo_decisao": "estornar", "valor_aprovado": 300.0},
        {"tipo_decisao": "estornar", "valor_aprovado": 150.0},
        {"tipo_decisao": "absorver", "valor_aprovado": 0.0},
    ]
    assert agregar_estorno(decisoes) == 450.0
    # os dois agregados juntos, na mesma fase, permanecem INDEPENDENTES (nunca se subtraem)
    assert agregar_complemento(decisoes) == 2000.0
