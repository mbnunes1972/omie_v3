"""Conciliação de Custo de Fábrica do PE na AF2 (11d) — decisão por ambiente/fase.

Lógica PURA (sem I/O, sem banco, sem contabilidade). Decide o tratamento de cada diferença de
CFO revelada pelo PE (`mod_pe_comparacao.montar_comparacao_pe`) e agrega por fase pros dois
mecanismos financeiros: Complemento de Projeto (Cobrar) e Crédito a Clientes (Estornar) — que
NUNCA se compensam automaticamente entre si (decisão do usuário).

Duas grandezas de "diferença de valor de contrato" coexistem de propósito, cada uma pro seu uso:
- `diferenca_valor_contrato` (CFO × Markup, esta função): estimativa rápida pra DECISÃO na AF2
  ("vale a pena repassar isso ao cliente?") e o default editável do Estorno (que não tem outra
  grandeza melhor à disposição, por ser mecanismo manual/simples).
- O valor que de fato entra no Complemento de Projeto (Cobrar) vem depois, do motor de venda
  (`_complemento_diferencas`, fator proporcional VAVA/VBVA) — mais preciso, mas calculado só na
  montagem do complemento (Fatia 2), não aqui.

Spec: docs/superpowers/specs/financeiro/2026-08-14-conciliacao-pe-af2-complemento-credito-design.md
"""

TIPOS_DECISAO = ("manter", "absorver", "cobrar", "estornar")

# tipo_decisao válido por sinal de `diferenca_cfo` (= cfo_pe - cfo_original; positivo = custo
# SUBIU, negativo = custo CAIU — mesma convenção de mod_pe_comparacao.montar_comparacao_pe).
_VALIDOS_POR_SINAL = {
    "alta":  ("absorver", "cobrar"),    # custo subiu: loja assume, ou repassa
    "baixa": ("manter", "estornar"),    # custo caiu: loja fica com a economia, ou devolve
    "zero":  ("manter", "absorver"),    # sem diferença: nada a repassar, só registrar
}


def sinal_diferenca(diferenca_cfo):
    """'alta' (custo subiu) | 'baixa' (custo caiu) | 'zero'."""
    d = round(float(diferenca_cfo or 0), 2)
    if d > 0:
        return "alta"
    if d < 0:
        return "baixa"
    return "zero"


def decisao_valida(diferenca_cfo, tipo_decisao):
    """True se `tipo_decisao` é compatível com o sinal de `diferenca_cfo`.

    Regra dura (decisão do usuário, 2026-08-14): diferença negativa (custo caiu) NUNCA pode virar
    'cobrar' — só 'manter' ou 'estornar'. Diferença positiva (custo subiu) nunca pode virar
    'estornar' — só 'absorver' ou 'cobrar'. Evita duas rotas concorrentes pra mexer no bolso do
    cliente na mesma direção errada.
    """
    if tipo_decisao not in TIPOS_DECISAO:
        return False
    return tipo_decisao in _VALIDOS_POR_SINAL[sinal_diferenca(diferenca_cfo)]


def diferenca_valor_contrato(diferenca_cfo, markup):
    """Diferença de Valor de Contrato = Diferença de Custo de Fábrica × Markup — o quanto o
    cliente pagaria a mais/menos se o ambiente tivesse sido vendido pelo custo real do PE."""
    return round(float(diferenca_cfo or 0) * float(markup or 0), 2)


def montar_decisao(pool_ambiente_id, diferenca_cfo, markup, tipo_decisao, valor_aprovado=None):
    """Monta uma linha de decisão pronta pra persistir em `ConciliacaoPeFase`.

    `valor_aprovado`: valor editável pelo gerente (tipicamente usado no Estorno); default é o
    módulo da diferença de valor de contrato calculada. Levanta ValueError se a decisão não bate
    com o sinal da diferença (ver `decisao_valida`).
    """
    if not decisao_valida(diferenca_cfo, tipo_decisao):
        raise ValueError(
            "decisão '%s' incompatível com diferença de CFO %.2f"
            % (tipo_decisao, float(diferenca_cfo or 0)))
    dvc = diferenca_valor_contrato(diferenca_cfo, markup)
    valor = round(float(valor_aprovado), 2) if valor_aprovado is not None else abs(dvc)
    return {
        "pool_ambiente_id": pool_ambiente_id,
        "diferenca_cfo": round(float(diferenca_cfo or 0), 2),
        "diferenca_valor_contrato": dvc,
        "tipo_decisao": tipo_decisao,
        "valor_aprovado": valor,
    }


def decisao_ambiente_novo(pool_ambiente_id, valor_venda_xml):
    """Ambiente/peça nova sem contratado correspondente (sem `diferenca_cfo` — não é uma
    variação, é uma venda nova). Entra sempre como 'cobrar', pelo valor cheio do XML de venda
    (não pelo fator CFO×Markup, que não se aplica a algo sem baseline)."""
    valor = round(float(valor_venda_xml or 0), 2)
    return {
        "pool_ambiente_id": pool_ambiente_id,
        "diferenca_cfo": None,
        "diferenca_valor_contrato": valor,
        "tipo_decisao": "cobrar",
        "valor_aprovado": valor,
    }


def fase_completa(ambientes_com_pe, decisoes_registradas):
    """`ambientes_com_pe`: iterável de `pool_ambiente_id` com PE carregado nesta fase.
    `decisoes_registradas`: iterável de `pool_ambiente_id` que já têm decisão registrada.

    Retorna `(True, [])` se toda fase tem decisão pra todo ambiente com PE; senão
    `(False, [faltantes ordenados])` — alimenta a checagem derivada de conclusão da AF2 (11d).
    """
    faltam = sorted(set(ambientes_com_pe) - set(decisoes_registradas))
    return (not faltam, faltam)


def agregar_complemento(decisoes):
    """Soma `valor_aprovado` de todas as decisões 'cobrar' — alimenta o Complemento de Projeto
    da fase. `decisoes`: lista de dicts com `tipo_decisao`/`valor_aprovado`."""
    return round(sum(d["valor_aprovado"] for d in decisoes if d["tipo_decisao"] == "cobrar"), 2)


def agregar_estorno(decisoes):
    """Soma `valor_aprovado` de todas as decisões 'estornar' — alimenta o lançamento de Crédito a
    Clientes da fase. Separado de `agregar_complemento` por decisão do usuário: Cobrar e Estornar
    NUNCA se compensam automaticamente, mesmo dentro da mesma fase."""
    return round(sum(d["valor_aprovado"] for d in decisoes if d["tipo_decisao"] == "estornar"), 2)
