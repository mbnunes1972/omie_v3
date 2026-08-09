# -*- coding: utf-8 -*-
"""mod_indicadores.py — Snapshot de indicadores financeiros/comerciais (PURO, sem I/O).

Fórmulas clássicas sobre os agregados que o mod_contabil já produz (balanco()/dre()) e sobre
contagens comerciais levantadas pelo composition root (main.py). Toda divisão tem guarda:
denominador zero → None (a tela renderiza "—", nunca um número enganoso).

Adaptações ao plano de contas da casa (documentadas):
- Liquidez AJUSTADA: exclui do ativo circulante os DIFERIDOS (1.1.05 impostos a apropriar +
  1.1.06 custos a apropriar) — não são conversíveis em caixa; a liquidez corrente clássica os
  contaria e inflaria o índice.
- PMP usa como "fornecedores" o 2.1.01 (Fornecedores a Pagar) + 2.1.04.06 (Provisão de Custo de
  Fábrica) — no fluxo da casa, o "a pagar à fábrica" vive na provisão até o pagamento.
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _div(num, den, nd=4):
    den = _f(den)
    if abs(den) < 0.005:
        return None
    return round(_f(num) / den, nd)


def liquidez(ativo_circ, passivo_circ, caixa, diferidos):
    """Índices de liquidez + capital de giro líquido."""
    ac, pc = _f(ativo_circ), _f(passivo_circ)
    return {
        "corrente": _div(ac, pc),
        "imediata": _div(caixa, pc),
        "ajustada": _div(ac - _f(diferidos), pc),   # sem os ativos diferidos
        "capital_giro": round(ac - pc, 2),
    }


def margens(dre):
    """Margens da DRE do período (frações; a tela formata em %)."""
    rl = _f((dre or {}).get("receita_liquida"))
    return {
        "bruta": _div((dre or {}).get("lucro_bruto"), rl),
        "ebitda": _div((dre or {}).get("ebitda"), rl),
        "liquida": _div((dre or {}).get("lucro_liquido"), rl),
    }


def prazos_giro(receber, fornecedores, receita_periodo, cmv_periodo, dias):
    """PMR/PMP (dias) e giro de carteira (quantas vezes a carteira de recebíveis 'girou'
    no período = receita ÷ saldo a receber)."""
    pmr = _div(_f(receber) * _f(dias), receita_periodo, nd=1)
    pmp = _div(_f(fornecedores) * _f(dias), cmv_periodo, nd=1)
    return {
        "pmr_dias": pmr,
        "pmp_dias": pmp,
        "giro_carteira": _div(receita_periodo, receber, nd=2),
    }


def tendencia(serie):
    """Direção da série (último vs penúltimo): alta | queda | estavel (< ±1%).
    Base zero ou série curta → pct None (sem % enganoso)."""
    s = [_f(x) for x in (serie or [])]
    if len(s) < 2:
        return {"dir": "estavel", "pct": None}
    ant, ult = s[-2], s[-1]
    if abs(ant) < 0.005:
        if abs(ult) < 0.005:
            return {"dir": "estavel", "pct": None}
        return {"dir": "alta" if ult > 0 else "queda", "pct": None}
    pct = round((ult - ant) / abs(ant) * 100.0, 1)
    if abs(pct) < 1.0:
        return {"dir": "estavel", "pct": pct}
    return {"dir": "alta" if pct > 0 else "queda", "pct": pct}


def janela_periodo(tipo, ref):
    """(ini, fim, ini_anterior, fim_anterior), todos `date`, do período que contém `ref` (date)
    pro tipo 'mes'|'trimestre'|'ano' — 'anterior' é o período imediatamente anterior de mesmo
    tamanho, pra comparação automática (Painel Estratégico, pedido do usuário 2026-08-09)."""
    from datetime import date, timedelta

    def _fim_mes(y, m):
        return (date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)) - timedelta(days=1)

    if tipo == "ano":
        ini, fim = date(ref.year, 1, 1), date(ref.year, 12, 31)
        ini_ant, fim_ant = date(ref.year - 1, 1, 1), date(ref.year - 1, 12, 31)
    elif tipo == "trimestre":
        tri = (ref.month - 1) // 3   # 0..3
        mes_ini = tri * 3 + 1
        ini, fim = date(ref.year, mes_ini, 1), _fim_mes(ref.year, mes_ini + 2)
        tri_ant, ano_ant = (tri - 1, ref.year) if tri > 0 else (3, ref.year - 1)
        mes_ini_ant = tri_ant * 3 + 1
        ini_ant, fim_ant = date(ano_ant, mes_ini_ant, 1), _fim_mes(ano_ant, mes_ini_ant + 2)
    else:   # "mes" (default)
        ini, fim = date(ref.year, ref.month, 1), _fim_mes(ref.year, ref.month)
        ini_ant, fim_ant = (ini - timedelta(days=1)).replace(day=1), ini - timedelta(days=1)
    return ini, fim, ini_ant, fim_ant


def variacao_pct(atual, anterior):
    """% de variação de `atual` sobre `anterior` (período corrente vs anterior). Base zero →
    None (sem % enganoso), espelha a guarda de `_div`.

    Denominador usa `abs(anterior)`, não `anterior` puro (achado do usuário, Painel Estratégico
    2026-08-09): em métrica que pode ficar negativa (lucro líquido, EBITDA, margem), uma base
    anterior negativa INVERTE o sinal da fórmula clássica — prejuízo encolhendo (ex.: -30000 →
    -2660, uma melhora real) dava -91% (lido como piora, seta ▼ vermelha). Com `abs()` no
    denominador o sinal do resultado sempre acompanha o sinal de `atual − anterior` (delta real),
    em qualquer combinação de sinais dos dois períodos — só muda a magnitude marginal quando a
    base é negativa, não a leitura de melhora/piora."""
    return _div(_f(atual) - _f(anterior), abs(_f(anterior)), nd=1)


def media(valores):
    """Média simples de uma lista de números (ou None se vazia) — usada pra 'X médio' que não é
    fração de duas somas (markup médio, margem de contribuição média): cada Orcamento já tem o
    índice PRÓPRIO calculado (motor de negociação); aqui só tira a média entre os do período."""
    vs = [_f(v) for v in (valores or [])]
    return round(sum(vs) / len(vs), 4) if vs else None


def custo_fixo_stats(serie_mensal):
    """Custo fixo médio da série + variação do último mês sobre a média dos ANTERIORES (não
    inclui o próprio último mês na média de comparação, senão a variação se dilui)."""
    vs = [_f(v) for v in (serie_mensal or [])]
    if not vs:
        return {"media": None, "ultimo": None, "variacao_pct": None}
    media_total = round(sum(vs) / len(vs), 2)
    if len(vs) < 2:
        return {"media": media_total, "ultimo": vs[-1], "variacao_pct": None}
    anteriores = vs[:-1]
    media_ant = sum(anteriores) / len(anteriores)
    return {"media": media_total, "ultimo": vs[-1],
            "variacao_pct": variacao_pct(vs[-1], media_ant)}


def ponto_equilibrio(custo_fixo, margem_contribuicao_pct):
    """Receita necessária pra cobrir os custos fixos: Custo Fixo ÷ % Margem de Contribuição.
    Margem de contribuição <= 0 → None (não existe ponto de equilíbrio financeiramente válido:
    cada venda adicional aumentaria o prejuízo, não reduziria)."""
    mc = _f(margem_contribuicao_pct)
    if mc <= 0:
        return None
    return round(_f(custo_fixo) / mc, 2)


def endividamento(passivo_total, ativo_total):
    """Passivo total ÷ Ativo total (fração; a tela formata em %)."""
    return _div(passivo_total, ativo_total, nd=4)


def kpis_comerciais(status_counts, contratos_periodo):
    """KPIs do funil comercial. status_counts: {status: n} dos projetos;
    contratos_periodo: lista de valores (R$) dos contratos gerados no período."""
    sc = status_counts or {}
    ativos = sum(sc.get(k, 0) for k in ("quente", "morno", "frio"))
    conv, perd = sc.get("convertido", 0), sc.get("perdido", 0)
    vals = [_f(v) for v in (contratos_periodo or [])]
    return {
        "pipeline_ativo": ativos,
        "quentes": sc.get("quente", 0),
        "convertidos": conv,
        "perdidos": perd,
        "taxa_conversao": _div(conv, conv + perd),
        "n_vendas_periodo": len(vals),
        "vendas_periodo": round(sum(vals), 2),
        "ticket_medio": _div(sum(vals), len(vals), nd=2),
    }
