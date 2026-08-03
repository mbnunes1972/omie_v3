"""
mod_fin/aymore.py — cálculo de parcelamento Aymoré (Santander)

Lógica:
  A entrada é paga diretamente à loja, sem retenção da operadora.
  Os juros incidem apenas sobre o valor que a operadora financia.

  financiado   = (valor_avista - entrada) / (1 - taxa_retencao)
  parcela      = financiado / n
  total_cliente = entrada + financiado
  loja_recebe   = entrada + (financiado × (1 - taxa_ret)) = valor_avista ✓

Teste rápido:
  python3 -c "
  from mod_fin.aymore import calcular
  r = calcular(100000, 0, 8, 20, '2026-06-01')
  print(r['valor_liberado'], r['total_cliente'])  # 100000, 110223.82
  r2 = calcular(100000, 20000, 8, 20, '2026-06-01')
  print(r2['valor_liberado'], r2['total_cliente'])  # 100000, 108179.05
  "
"""
from datetime import timedelta
from .base import carregar_json, pmt, parse_data, linha_contrato, linha_entrada, linha_parcela

_TAXAS_FALLBACK = {
    1: 0.043891, 2: 0.031261, 3: 0.024500, 4: 0.024500,
    5: 0.024500, 6: 0.024500, 7: 0.024000, 8: 0.024000,
    9: 0.024000,10: 0.024000,11: 0.024000,12: 0.024000,
   13: 0.024500,14: 0.024500,15: 0.024500,16: 0.024500,
   17: 0.024500,18: 0.024500,19: 0.024500,20: 0.024500,
   21: 0.024500,22: 0.024500,23: 0.024500,24: 0.025157,
}
PARCELAS_MIN = 1; PARCELAS_MAX = 24
CARENCIA_MIN = 15; CARENCIA_MAX = 120


def _taxas() -> dict:
    tab = carregar_json("aymore")
    if not tab or "taxas_mensais" not in tab:
        return _TAXAS_FALLBACK
    return {int(t["parcelas"]): float(t["taxa_mensal_pct"]) / 100
            for t in tab["taxas_mensais"]}


def calcular(valor_avista: float, entrada: float, n_parcelas: int,
             carencia_dias: int, data_contrato: str) -> dict:
    """
    Calcula parcelamento Aymoré.

    Parâmetros:
        valor_avista    — O que a loja quer receber (valor após desconto, sem gross-up)
        entrada         — Valor pago na assinatura, sem juros, vai direto para a loja
        n_parcelas      — Número de parcelas (1 a 24)
        carencia_dias   — Dias até a 1ª parcela (15 a 120, múltiplos de 5)
        data_contrato   — Data da assinatura no formato 'AAAA-MM-DD'

    Retorna:
        valor_liberado  = valor_avista (loja recebe exatamente isso)
        total_cliente   = entrada + financiado (o que o cliente paga ao total)
        valor_parcela   = financiado / n
        retencao_rs     = custo financeiro (taxa sobre o financiado)
    """
    n        = int(n_parcelas)
    carencia = int(carencia_dias)
    avista   = float(valor_avista)
    ent      = float(entrada or 0)

    if n < PARCELAS_MIN or n > PARCELAS_MAX:
        return {"ok": False, "erro": f"n_parcelas deve ser entre {PARCELAS_MIN} e {PARCELAS_MAX}"}
    if carencia < CARENCIA_MIN or carencia > CARENCIA_MAX:
        return {"ok": False, "erro": f"carencia_dias deve ser entre {CARENCIA_MIN} e {CARENCIA_MAX}"}
    if ent < 0:
        return {"ok": False, "erro": "Entrada não pode ser negativa"}
    if ent >= avista:
        return {"ok": False, "erro": "Entrada deve ser menor que o valor à vista"}

    taxas = _taxas()
    if n not in taxas:
        return {"ok": False, "erro": f"Sem taxa cadastrada para {n} parcelas"}

    taxa = taxas[n]

    # Taxa de retenção com ajuste de carência
    pmt_val       = pmt(taxa, n)
    coef          = pmt_val * ((1 + taxa) ** ((carencia - 30) / 30))
    taxa_retencao = round(1 - (1.0 / n) / coef, 8)

    # Financiado = o que a operadora paga (só sobre o que excede a entrada)
    # loja_recebe_da_operadora = avista - entrada
    # financiado = (avista - entrada) / (1 - taxa_ret)
    loja_da_operadora = round(avista - ent, 2)
    financiado        = round(loja_da_operadora / (1 - taxa_retencao), 2)
    retencao_rs       = round(financiado * taxa_retencao, 2)
    valor_parcela     = round(financiado / n, 2)
    total_cliente     = round(ent + financiado, 2)

    # Plano de parcelas — última absorve o resíduo do arredondamento (mesma regra
    # da venda programada): entrada + Σ parcelas = total_cliente exato ao centavo
    ajuste_ultimo = round(financiado - valor_parcela * n, 2)
    dc   = parse_data(data_contrato)
    plan = [linha_contrato(dc)]
    if ent > 0:
        plan.append(linha_entrada(dc, ent))
    for i in range(1, n + 1):
        data_venc = dc + timedelta(days=carencia + (i - 1) * 30)
        valor = valor_parcela + (ajuste_ultimo if i == n else 0)
        plan.append(linha_parcela(i, data_venc, valor))

    return {
        "ok":                True,
        "valor_avista":      avista,          # o que a loja recebe
        "valor_negociado":   total_cliente,   # compatibilidade
        "entrada":           ent,
        "financiado":        financiado,      # o que o cliente financia com a operadora
        "taxa_mensal_pct":   round(taxa * 100, 4),
        "taxa_retencao_pct": round(taxa_retencao * 100, 4),
        "valor_liberado":    avista,          # loja recebe = valor_avista sempre
        "retencao_rs":       retencao_rs,
        "valor_parcela":     valor_parcela,
        "n_parcelas":        n,
        "carencia_dias":     carencia,
        "total_cliente":     total_cliente,
        "parcelas":          plan,
    }
