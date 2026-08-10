# -*- coding: utf-8 -*-
"""mod_simulador.py — Simulador de Modelo de Negócios (PURO, sem I/O — padrão mod_indicadores).

Único ponto de entrada: `simular(modelo, ajustes) -> resultado`. `modelo` é o contrato
`ModeloLoja` (JSON serializável, único acoplamento com o hospedeiro — RF-06/D2); `ajustes` são
as mudanças que o usuário fez na tela (RF-16..RF-20). Nenhuma query aqui — quem monta o
`ModeloLoja` a partir do sistema real é `mod_simulador_dados.py` (adapter, D3).

RN-01: "Faturamento" = Val_Liq (valor líquido). RN-02: markup exibido em % ADICIONAL sobre a
base (2,18× = 118%) — `_markup_pct_adicional`. Markups (seco/com frete) NÃO entram na cadeia de
consequências das demais variáveis: iniciam pela média do período e só mudam por edição direta
(RF-18) — nunca são recalculados a partir do faturamento/variáveis simulados.

Toda divisão usa `_div` (mod_indicadores): denominador zero → None ("—" na tela), nunca número
enganoso (RNF-02).

`ModeloLoja` (dict):
{
  "vendedores": [{"nome", "atual", "meta", "ativo"}, ...],
  "medias_janela": {"mes"|"d30"|"tri"|"sem"|"ano": float, ...},   # valor médio por posto (RF-11)
  "variaveis": [{"chave", "nome", "pct"}, ...],                   # provisões % s/ faturamento (RF-17)
  "markups_medios": {"seco": {janela: mult}, "com_frete": {janela: mult}},
  "folha": [
      {"nome", "cargo", "salario_fixo", "comissao_fixa", "pro_labore",
       "comissionamento": "none"|"pct_fat"|"faixa_loja"|"faixa_vendedor",
       "vendedor_idx": int|None, "pct_fixo": float|None, "ativo": bool}, ...
  ],
  "encargos_pct": float,                       # 35.0 default (CLT; pró-labore isento)
  "faixas_consultor": [[limite, pct, rotulo], ...],
  "faixas_gerente":   [[limite, pct, rotulo], ...],
  "custos_fixos": [{"nome", "valor"}, ...],                       # todas as contas, mesmo zeradas (RF-21)
  "amortizacoes": [{"nome", "valor", "prazo_meses"}, ...],
  "juros": float, "impostos_pct": float, "divida": float,
  "rotulos": dict|None,                        # RF-08, não usado na v1
}

`ajustes` (dict, tudo opcional):
{
  "cenario": "atual"|"historico"|"futuro" (default "atual"),
  "janela": "mes"|"d30"|"tri"|"sem"|"ano" (default "mes"),
  "trava": bool,
  "vendedores_ativos": {"<idx>": bool},        # override do ativo por índice
  "variaveis_pct": {"<chave>": float},         # override do % editado por chave
  "markup_seco": float|None, "markup_com_frete": float|None,   # edição direta (RN-02, RF-18)
  "folha_salarios": {"<idx>": float},          # override de salario_fixo por índice
  "folha_ativos": {"<idx>": bool},             # override de ativo (ignorado p/ comissionamento=faixa_vendedor)
}
"""
from mod_indicadores import _div


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def media_historica(valores_mensais):
    """Média de uma série mensal DESCARTANDO os meses zerados (RF-13: zero por inexistência
    distorceria a média). None se não sobrar nenhum mês com dado."""
    vs = [_f(v) for v in (valores_mensais or []) if _f(v) != 0.0]
    return round(sum(vs) / len(vs), 2) if vs else None


def _markup_pct_adicional(mult):
    """RN-02: percentual exibido é o ADICIONAL sobre a base — 2,18× = 118%."""
    return round((_f(mult) - 1.0) * 100.0)


def _faixa(faixas, atingimento):
    """Primeira [limite, pct, rótulo] cujo limite é MAIOR que o atingimento (mockup: `at < lim`).
    Sem faixas → (None, 0.0, None)."""
    for lim, pct, rot in (faixas or []):
        if lim is None or atingimento < _f(lim):
            return lim, _f(pct), rot
    if faixas:
        lim, pct, rot = faixas[-1]
        return lim, _f(pct), rot
    return None, 0.0, None


def _vendas_base(modelo, ajustes):
    """Grupo A: linhas de venda + faturamento (RN-01/RF-15/RF-16). Devolve lista de linhas
    {nome, valor, ativo, redistribuido} e o faturamento total (Val_Liq simulado)."""
    vendedores = modelo.get("vendedores") or []
    cenario = ajustes.get("cenario") or "atual"
    janela = ajustes.get("janela") or "mes"
    trava = bool(ajustes.get("trava"))
    ativos_override = ajustes.get("vendedores_ativos") or {}

    def ativo(i, v):
        key = str(i)
        if key in ativos_override:
            return bool(ativos_override[key])
        return bool(v.get("ativo", True))

    if cenario == "atual":
        media_janela = modelo.get("medias_janela") or {}
        fator = 0.97 if janela == "d30" else 1.0   # mesma aproximação do protótipo aprovado
        base_valores = [_f(v.get("atual")) * fator for v in vendedores]
    else:
        valor_medio = _f((modelo.get("medias_janela") or {}).get(janela))
        base_valores = [valor_medio for _ in vendedores]

    total_pleno = sum(base_valores)
    ativos_idx = [i for i, v in enumerate(vendedores) if ativo(i, v)]
    soma_ativos = sum(base_valores[i] for i in ativos_idx)

    linhas = []
    fat = 0.0
    for i, v in enumerate(vendedores):
        on = ativo(i, v)
        redistribuido = False
        if trava and ativos_idx and soma_ativos > 0:
            valor = (base_valores[i] * (total_pleno / soma_ativos)) if on else 0.0
            redistribuido = on and soma_ativos < total_pleno
        elif trava and ativos_idx:
            # soma_ativos == 0 (os que sobraram ativos têm base zerada, ex.: consultor novo sem
            # venda ainda) — redistribuição PROPORCIONAL não tem base pra funcionar (seria 0/0).
            # Trava promete manter o faturamento constante; sem proporção possível, o volume
            # retirado é dividido IGUALMENTE entre os que continuam ativos (achado da Vera).
            valor = (total_pleno / len(ativos_idx)) if on else 0.0
            redistribuido = on and total_pleno > 0
        else:
            valor = base_valores[i] if on else 0.0
        linhas.append({"nome": v.get("nome"), "valor": round(valor, 2), "ativo": on,
                       "redistribuido": redistribuido})
        fat += valor
    fat = round(fat, 2)
    for linha in linhas:
        linha["pct_do_total"] = _div(linha["valor"], fat, nd=4)
    return linhas, fat


def _variaveis(modelo, ajustes, fat):
    """Grupo B: provisões % sobre o faturamento (RF-17) + markups (RF-18/RN-02, fora da cadeia)."""
    overrides = ajustes.get("variaveis_pct") or {}
    linhas = []
    total_pct = 0.0
    for item in (modelo.get("variaveis") or []):
        chave = item.get("chave")
        pct = _f(overrides[chave]) if chave in overrides else _f(item.get("pct"))
        valor = round(fat * pct / 100.0, 2)
        linhas.append({"chave": chave, "nome": item.get("nome"), "pct": round(pct, 4), "valor": valor})
        total_pct += pct

    cenario = ajustes.get("cenario") or "atual"
    janela = ajustes.get("janela") or "mes"
    markups_medios = modelo.get("markups_medios") or {}

    def _resolver_markup(qual, override_key):
        override = ajustes.get(override_key)
        if override is not None:
            mult = _f(override)
        else:
            medios = markups_medios.get(qual) or {}
            mult = _f(medios.get(janela) if janela in medios else medios.get("mes"))
        return {"multiplicador": round(mult, 4), "pct_adicional": _markup_pct_adicional(mult)}

    markup_seco = _resolver_markup("seco", "markup_seco")
    markup_com_frete = _resolver_markup("com_frete", "markup_com_frete")

    return {
        "linhas": linhas, "total_pct": round(total_pct, 4),
        "total_valor": round(fat * total_pct / 100.0, 2),
        "markup_seco": markup_seco, "markup_com_frete": markup_com_frete,
    }, cenario


def _comissao_de(item, idx, vendedores_linhas, vendedores_modelo, fat, modelo):
    tipo = item.get("comissionamento") or "none"
    if tipo == "none":
        return {"valor": 0.0, "sub": "sem comissionamento", "sem_comissionamento": True}
    if tipo == "pct_fat":
        pct = _f(item.get("pct_fixo"))
        return {"valor": round(fat * pct / 100.0, 2), "sub": "%.1f%% do faturamento" % pct,
                "sem_comissionamento": False}
    if tipo == "faixa_loja":
        meta_loja = sum(_f(v.get("meta")) for v in vendedores_modelo)
        at = _div(fat, meta_loja) or 0.0
        _, pct, rot = _faixa(modelo.get("faixas_gerente"), at)
        return {"valor": round(fat * pct / 100.0, 2),
                "sub": "%.1f%% do fat. · %s" % (pct, rot or ""), "sem_comissionamento": False}
    if tipo == "faixa_vendedor":
        vi = item.get("vendedor_idx")
        if vi is None or vi >= len(vendedores_linhas):
            return {"valor": 0.0, "sub": "—", "sem_comissionamento": True}
        linha = vendedores_linhas[vi]
        if not linha["ativo"]:
            return {"valor": 0.0, "sub": "—", "sem_comissionamento": True}
        meta = _f(vendedores_modelo[vi].get("meta"))
        at = _div(linha["valor"], meta) or 0.0
        _, pct, rot = _faixa(modelo.get("faixas_consultor"), at)
        return {"valor": round(linha["valor"] * pct / 100.0, 2),
                "sub": "%.1f%% · %s" % (pct, rot or ""), "sem_comissionamento": False}
    return {"valor": 0.0, "sub": "—", "sem_comissionamento": True}


def _folha(modelo, ajustes, vendedores_linhas, fat):
    """Grupo C: folha de pagamento — fixo (salário + comissão fixa + encargos) e variável
    (comissão pela faixa de meta / % fixo). Encargos 35% só sobre o salário CLT (RF-19/RF-19b)."""
    vendedores_modelo = modelo.get("vendedores") or []
    salarios_override = ajustes.get("folha_salarios") or {}
    ativos_override = ajustes.get("folha_ativos") or {}
    encargos_pct = _f(modelo.get("encargos_pct", 35.0))

    colaboradores = []
    sal_fixo_total = enc_total = com_total = 0.0
    for i, item in enumerate(modelo.get("folha") or []):
        key = str(i)
        salario = _f(salarios_override[key]) if key in salarios_override else _f(item.get("salario_fixo"))
        pro_labore = bool(item.get("pro_labore"))
        comissao_fixa = _f(item.get("comissao_fixa"))
        if item.get("comissionamento") == "faixa_vendedor":
            vi = item.get("vendedor_idx")
            on = bool(vendedores_linhas[vi]["ativo"]) if (vi is not None and vi < len(vendedores_linhas)) else False
        elif key in ativos_override:
            on = bool(ativos_override[key])
        else:
            on = bool(item.get("ativo", True))

        encargos = 0.0 if (pro_labore or not on) else round(salario * encargos_pct / 100.0, 2)
        comissao = (_comissao_de(item, i, vendedores_linhas, vendedores_modelo, fat, modelo)
                    if on else {"valor": 0.0, "sub": "—", "sem_comissionamento": True})
        if on:
            sal_fixo_total += salario + comissao_fixa
            enc_total += encargos
            com_total += comissao["valor"]

        colaboradores.append({
            "nome": item.get("nome"), "cargo": item.get("cargo"), "ativo": on,
            "salario_fixo": round(salario, 2), "comissao_fixa": round(comissao_fixa, 2),
            "pro_labore": pro_labore, "encargos": encargos, "comissao": comissao,
        })

    folha_fixa = round(sal_fixo_total + enc_total, 2)
    com_total = round(com_total, 2)
    total = round(folha_fixa + com_total, 2)
    return {"colaboradores": colaboradores, "fixo": folha_fixa, "variavel": com_total,
            "total": total, "pct_fixo": _div(folha_fixa, fat, nd=4),
            "pct_variavel": _div(com_total, fat, nd=4), "pct_total": _div(total, fat, nd=4)}


def _custos_fixos(modelo, fat):
    """Grupo D: todas as contas (inclusive zeradas — RF-21) + amortizações (RF-23)."""
    contas = []
    subtotal = 0.0
    for c in (modelo.get("custos_fixos") or []):
        valor = round(_f(c.get("valor")), 2)
        contas.append({"nome": c.get("nome"), "valor": valor, "pct": _div(valor, fat, nd=4)})
        subtotal += valor

    amortizacoes = []
    impacto_total = 0.0
    for a in (modelo.get("amortizacoes") or []):
        valor, prazo = _f(a.get("valor")), _f(a.get("prazo_meses"))
        impacto = round(valor / prazo, 2) if prazo else 0.0
        amortizacoes.append({"nome": a.get("nome"), "valor": valor, "prazo_meses": a.get("prazo_meses"),
                             "impacto_mensal": impacto})
        impacto_total += impacto

    total = round(subtotal + impacto_total, 2)
    return {"contas": contas, "subtotal": round(subtotal, 2), "subtotal_pct": _div(subtotal, fat, nd=4),
            "amortizacoes": amortizacoes, "impacto_mensal_total": round(impacto_total, 2),
            "total": total, "pct_total": _div(total, fat, nd=4)}


def _juros_impostos_divida(modelo, fat):
    """Grupo E: juros + impostos (carga do perfil fiscal sobre o faturamento simulado) + dívida
    (saldo — não entra no resultado mensal, RF-24)."""
    juros = round(_f(modelo.get("juros")), 2)
    impostos = round(fat * _f(modelo.get("impostos_pct")) / 100.0, 2)
    divida = round(_f(modelo.get("divida")), 2)
    total_mensal = round(juros + impostos, 2)
    return {"juros": juros, "juros_pct": _div(juros, fat, nd=4),
            "impostos": impostos, "impostos_pct_fat": _div(impostos, fat, nd=4),
            "divida": divida, "total_mensal": total_mensal, "pct_total": _div(total_mensal, fat, nd=4)}


def _snapshot(fat, variaveis, folha, custos_fixos, jid):
    """Grupo F: MC = fat − variáveis − comissões; Lucro = MC − folha fixa − custos fixos − juros
    − impostos. Margens em % do faturamento (guardadas por `_div` — RNF-02)."""
    mc_valor = round(fat - variaveis["total_valor"] - folha["variavel"], 2)
    lucro_valor = round(mc_valor - folha["fixo"] - custos_fixos["total"] - jid["juros"] - jid["impostos"], 2)
    return {
        "faturamento": fat,
        "margem_contribuicao": {"valor": mc_valor, "pct": _div(mc_valor, fat, nd=4)},
        "margem_lucro_liquido": {"valor": lucro_valor, "pct": _div(lucro_valor, fat, nd=4)},
        "markup_seco": variaveis["markup_seco"], "markup_com_frete": variaveis["markup_com_frete"],
    }


def simular(modelo, ajustes=None):
    """Ponto de entrada único do motor — recebe o `ModeloLoja` + os ajustes da tela e devolve o
    resultado calculado dos 6 grupos (A-F). Nunca grava nada (RNF-01: somente leitura)."""
    modelo = modelo or {}
    ajustes = ajustes or {}

    linhas_vendas, fat = _vendas_base(modelo, ajustes)
    variaveis, cenario = _variaveis(modelo, ajustes, fat)
    folha = _folha(modelo, ajustes, linhas_vendas, fat)
    custos_fixos = _custos_fixos(modelo, fat)
    jid = _juros_impostos_divida(modelo, fat)
    snapshot = _snapshot(fat, variaveis, folha, custos_fixos, jid)

    return {
        "cenario": cenario, "janela": ajustes.get("janela") or "mes", "trava": bool(ajustes.get("trava")),
        "vendas": {"linhas": linhas_vendas, "faturamento": fat},
        "variaveis": variaveis, "folha": folha, "custos_fixos": custos_fixos,
        "juros_impostos_divida": jid, "snapshot": snapshot,
    }
