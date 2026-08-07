# -*- coding: utf-8 -*-
"""mod_recebiveis.py — Recebimento de venda: materialização dos recebíveis previstos (PURO, sem I/O).

Achado da Vera (2026-08-07): `1.1.02 Contas a Receber` nasce cheia no contrato
(`mod_contabil.registrar_evento(..., "registro_venda_contrato", ...)`) mas nunca era baixada — o
evento `recebimento_venda` existia só como chave morta em `mod_contabil.EVENTOS`. Este módulo parseia
o JSON de pagamento capturado pelo frontend (`Orcamento.forma_pagamento`, formato de
`_capturarPagamento()`) e devolve as linhas de recebível a persistir — uma por entrada de caixa
PREVISTA. `main.py` é quem grava (`database.Recebivel`).

Dois ramos de comportamento, pelo campo `tipo` do JSON (`'avista'|'vp'|'tf'|'aymore'|'cartao'` —
strings do frontend, static/index.html:7942-8794; NÃO confundir com os códigos de
`mod_fin.ramo_financiamento`, que usam nomes diferentes):

  - **avista/loja** (à vista, Venda Programada, Total Flex): o cliente paga a LOJA diretamente, por
    parcela — 1 recebível por linha real do plano (entrada + cada parcela), valor e data exatamente
    como capturados. Para Total Flex a parcela mistura capital+juros (não há split persistido) — o
    valor de face é usado como previsto por ora (decisão do usuário 2026-08-07); a confirmação em
    `mod_contabil.registrar_recebimento_venda` capa ao saldo real em aberto, então nunca estoura a
    contabilidade mesmo com um previsto otimista.
  - **financeira** (Cartão/Aymoré): a operadora antecipa a loja em LOTE, não em parcelas — as parcelas
    do JSON são o que o CLIENTE deve à operadora (com juros), irrelevante pro caixa da loja. A loja
    recebe: a entrada (direta, sem retenção) + um único lote "financiado" = Val_Cont − entrada, com
    data prevista = data do contrato + prazo de antecipação (config por loja).
"""
from datetime import date, datetime, timedelta
import json

_RAMO = {"avista": "avista", "vp": "loja", "tf": "loja", "aymore": "financeira", "cartao": "financeira"}

# Espelha o default de mod_provisoes.config_financeira_default()["prazo_antecipacao"] — usado só se o
# chamador não passar a config da loja (defensivo; o caminho real sempre passa).
_PRAZO_ANTECIPACAO_FALLBACK = {"cartao": 1, "aymore": 2}


def _parse_data(s, padrao=None):
    """Aceita 'AAAA-MM-DD' (avista/tf/entrada) ou 'DD/MM/AAAA' (aymore/vp, vindo de mod_fin). Vazio/
    inválido → `padrao`."""
    s = (s or "").strip()
    if not s:
        return padrao
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return padrao


def materializar(pag_json_str, valor_total, data_contrato, ref_base, prazo_antecipacao=None):
    """Devolve a lista de recebíveis previstos para um orçamento assinado.

    `valor_total` = Val_Cont (`Orcamento.valor_total`), o mesmo valor já debitado em `1.1.02` por
    `registro_venda_contrato` — a soma dos recebíveis devolvidos aqui bate com ele.
    `data_contrato` = date, usada como fallback de data e base do prazo de antecipação.
    `prazo_antecipacao` = dict {"cartao": dias, "aymore": dias} (da config da loja); default se ausente.

    Retorna lista de dicts: {tipo, numero, forma, valor_previsto, data_prevista, ref}. Linhas de
    valor <= 0 são omitidas."""
    try:
        pag = json.loads(pag_json_str) if pag_json_str else {}
    except (TypeError, ValueError):
        pag = {}
    if not isinstance(pag, dict):
        pag = {}

    tipo = (pag.get("tipo") or "avista").strip().lower()
    ramo = _RAMO.get(tipo, "avista")
    prazos = prazo_antecipacao or _PRAZO_ANTECIPACAO_FALLBACK

    val_cont = round(float(valor_total or 0), 2)
    entrada_valor = round(float(pag.get("entrada_valor") or 0), 2)
    entrada_data = _parse_data(pag.get("entrada_data"), padrao=data_contrato)
    entrada_forma = pag.get("entrada_forma") or None

    linhas = []
    if entrada_valor > 0:
        linhas.append({"tipo": "entrada", "numero": None, "forma": entrada_forma,
                       "valor_previsto": entrada_valor, "data_prevista": entrada_data,
                       "ref": ref_base + ":e"})

    if ramo == "financeira":
        restante = round(val_cont - entrada_valor, 2)
        if restante > 0:
            dias = int((prazos or {}).get(tipo, _PRAZO_ANTECIPACAO_FALLBACK.get(tipo, 1)))
            data_prev = data_contrato + timedelta(days=dias)
            linhas.append({"tipo": "financiado", "numero": None, "forma": tipo,
                           "valor_previsto": restante, "data_prevista": data_prev,
                           "ref": ref_base + ":f"})
    else:
        for i, p in enumerate(pag.get("parcelas") or [], start=1):
            valor = round(float((p or {}).get("valor") or 0), 2)
            if valor <= 0:
                continue
            numero = (p or {}).get("num") or i
            data_prev = _parse_data((p or {}).get("data"), padrao=data_contrato)
            linhas.append({"tipo": "parcela", "numero": numero, "forma": (p or {}).get("forma"),
                           "valor_previsto": valor, "data_prevista": data_prev,
                           "ref": ref_base + ":p%s" % numero})

    return linhas
