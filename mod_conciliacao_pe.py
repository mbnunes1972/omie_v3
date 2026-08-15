"""Conciliação de Custo de Fábrica do PE na AF2 (11d) — decisão por ambiente/fase.

Lógica PURA (sem I/O, sem banco, sem contabilidade). Decide o tratamento de cada diferença de
CFO revelada pelo PE (`mod_pe_comparacao.montar_comparacao_pe`) e agrega por fase pros dois
mecanismos financeiros: Complemento de Projeto (Cobrar) e Crédito a Clientes (Estornar) — que
NUNCA se compensam automaticamente entre si (decisão do usuário).

`diferenca_valor_contrato_estimada` decide qual grandeza usar pra decisão/exibição na AF2 e pro
default do valor aprovado — SEMPRE a mesma que vai virar o Complemento/Estorno de fato, pra não
divergir (achado do usuário 2026-08-15: a tela mostrava CFO×markup médio do orçamento enquanto o
Complemento gerado cobrava pelo fator VAVA/VBVA do ambiente, e os dois números divergiam sem o
gerente perceber ao aprovar a decisão):
- Caminho principal: `valor_complemento_por_fator` (fator proporcional VAVA/VBVA do ambiente
  contratado sobre o valor de venda do PE) — carrega o desconto e os custos adicionais exatamente
  como negociados naquele ambiente; MESMA fórmula usada em `main._complemento_diferencas_fase`
  pra gerar o Complemento de Projeto de fato.
- Fallback: `diferenca_valor_contrato` (CFO × Markup médio do orçamento) — só quando não há
  `valor_venda_pe` (PE carregado sem XML, ou registro anterior à Fatia venda 2026-07-21 sem o
  campo preenchido).

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


def montar_decisao(pool_ambiente_id, diferenca_cfo, diferenca_valor_contrato, tipo_decisao,
                   valor_aprovado=None):
    """Monta uma linha de decisão pronta pra persistir em `ConciliacaoPeFase`.

    `diferenca_valor_contrato`: já calculada pelo chamador (de preferência via
    `diferenca_valor_contrato_estimada`) — a MESMA grandeza mostrada na tela, pra não divergir do
    que efetivamente vira Complemento/Estorno depois.
    `valor_aprovado`: valor editável pelo gerente (tipicamente usado no Estorno); default é o
    módulo da diferença de valor de contrato recebida. Levanta ValueError se a decisão não bate
    com o sinal da diferença (ver `decisao_valida`).
    """
    if not decisao_valida(diferenca_cfo, tipo_decisao):
        raise ValueError(
            "decisão '%s' incompatível com diferença de CFO %.2f"
            % (tipo_decisao, float(diferenca_cfo or 0)))
    dvc = round(float(diferenca_valor_contrato or 0), 2)
    valor = round(float(valor_aprovado), 2) if valor_aprovado is not None else abs(dvc)
    return {
        "pool_ambiente_id": pool_ambiente_id,
        "diferenca_cfo": round(float(diferenca_cfo or 0), 2),
        "diferenca_valor_contrato": dvc,
        "tipo_decisao": tipo_decisao,
        "valor_aprovado": valor,
    }


def valor_complemento_por_fator(valor_venda_pe, vava_contratado, vbva_contratado,
                                fator_ca=1.0, desconto_orc_pct=0.0, desconto_amb_pct=0.0):
    """Valor à vista do ambiente no Complemento de Projeto — mesma fórmula de
    `main._complemento_diferencas` (Fatia 3, 2026-07-21), generalizada pra fase e alimentada
    direto pelo XML de PE (`ArquivoPE` formato `xml_pe`), sem exigir um 3º upload separado
    (`xml_compl`) como o mecanismo legado exigia.

    Caminho principal: `valor_venda_pe × (vava_contratado / vbva_contratado)` — a razão à
    vista÷bruto do PRÓPRIO ambiente contratado carrega o desconto (global+individual) e os custos
    adicionais exatamente como negociados, sem duplicar. Fallback (usado só quando o ambiente
    contratado não tem `vbva_contratado`/`vava_contratado` positivo, ex.: ambiente sem valor no
    contrato): `valor_venda_pe × (1 − desconto_orc) × (1 − desconto_amb) × fator_ca` — aproximação
    via os percentuais brutos.

    `diferenca = round(valor_complemento - vava_contratado, 2)` é responsabilidade do chamador
    (ele já tem os dois números). Retorna só o valor à vista do complemento, arredondado."""
    vc = round(float(vava_contratado or 0), 2)
    vb = round(float(vbva_contratado or 0), 2)
    vv = round(float(valor_venda_pe or 0), 2)
    if vb > 0 and vc > 0:
        return round(vv * (vc / vb), 2)
    d_orc = float(desconto_orc_pct or 0) / 100.0
    d_amb = float(desconto_amb_pct or 0) / 100.0
    return round(vv * (1 - d_orc) * (1 - d_amb) * float(fator_ca or 1.0), 2)


def diferenca_valor_contrato_estimada(diferenca_cfo, markup, valor_venda_pe=None,
                                      vava_contratado=0.0, vbva_contratado=0.0,
                                      fator_ca=1.0, desconto_orc_pct=0.0, desconto_amb_pct=0.0):
    """Diferença de Valor de Contrato pra decisão/exibição na AF2 — a MESMA grandeza que acaba
    virando o Complemento/Estorno de fato, calculada com o `valor_complemento_por_fator` sempre
    que possível (ver docstring do módulo). Fallback pro CFO×Markup só quando não há
    `valor_venda_pe` disponível."""
    if valor_venda_pe is not None:
        va = valor_complemento_por_fator(valor_venda_pe, vava_contratado, vbva_contratado,
                                         fator_ca, desconto_orc_pct, desconto_amb_pct)
        return round(va - float(vava_contratado or 0), 2)
    return diferenca_valor_contrato(diferenca_cfo, markup)


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
