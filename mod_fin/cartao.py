"""
mod_fin/cartao.py — cálculo de parcelamento Cartão de Crédito (Visa/Mastercard Itaú)

Lógica com entrada:
  financiado   = (valor_avista - entrada) / (1 - taxa_retencao)
  parcela      = financiado / n
  total_cliente = entrada + financiado
  loja_recebe   = valor_avista sempre

Teste rápido:
  python3 -c "
  from mod_fin.cartao import calcular
  r = calcular(10000, 0, 6, '2026-06-01')
  print(r['valor_liberado'], r['total_cliente'])  # 10000, 10598.83
  r2 = calcular(10000, 2000, 6, '2026-06-01')
  print(r2['valor_liberado'], r2['total_cliente'])  # 10000, 10479.07
  "
"""
from datetime import timedelta
from .base import carregar_json, parse_data, linha_contrato, linha_entrada, linha_parcela

PARCELAS_MAX = 21

_FAIXAS_FALLBACK = {
    1:  2.85,  2:  3.65,  3:  4.15,  4:  4.65,  5:  5.15,
    6:  5.65,  7:  6.16,  8:  6.66,  9:  7.16, 10:  7.66,
   11:  8.16, 12:  8.66, 13:  9.16, 14:  9.66, 15: 10.16,
   16: 10.66, 17: 11.16, 18: 11.66, 19: 12.16, 20: 12.66,
   21: 13.16,
}


def _faixas(codigo: str = "cartao_credito") -> dict:
    tab = carregar_json(codigo)
    if not tab or "faixas" not in tab:
        return _FAIXAS_FALLBACK if codigo == "cartao_credito" else {}
    return {int(f["parcelas"]): float(f["taxa_retencao_pct"])
            for f in tab["faixas"]}


def calcular(valor_avista: float, entrada: float,
             n_parcelas: int, data_contrato: str,
             codigo: str = "cartao_credito") -> dict:
    """
    Calcula parcelamento Cartão de Crédito.

    Parâmetros:
        valor_avista — O que a loja quer receber (valor após desconto)
        entrada      — Valor pago na assinatura, sem juros
        n_parcelas   — Número de parcelas (1 a 21)
        data_contrato — Data da assinatura 'AAAA-MM-DD'
    """
    n      = int(n_parcelas)
    avista = float(valor_avista)
    ent    = float(entrada or 0)

    if n < 1 or n > PARCELAS_MAX:
        return {"ok": False, "erro": f"n_parcelas deve ser entre 1 e {PARCELAS_MAX}"}
    if ent < 0:
        return {"ok": False, "erro": "Entrada não pode ser negativa"}
    if ent >= avista:
        return {"ok": False, "erro": "Entrada deve ser menor que o valor à vista"}

    faixas = _faixas(codigo)
    if n not in faixas:
        return {"ok": False, "erro": f"Sem taxa cadastrada para {n} parcelas"}

    taxa_pct  = faixas[n]
    taxa_dec  = taxa_pct / 100

    # Financiado = o que a operadora paga (só sobre o que excede a entrada)
    loja_da_operadora = round(avista - ent, 2)
    financiado        = round(loja_da_operadora / (1 - taxa_dec), 2)
    retencao_rs       = round(financiado * taxa_dec, 2)
    valor_parcela     = round(financiado / n, 2)
    total_cliente     = round(ent + financiado, 2)

    # última parcela absorve o resíduo do arredondamento (mesma regra da venda
    # programada): entrada + Σ parcelas = total_cliente exato ao centavo
    ajuste_ultimo = round(financiado - valor_parcela * n, 2)

    dc   = parse_data(data_contrato)
    plan = [linha_contrato(dc)]
    if ent > 0:
        plan.append(linha_entrada(dc, ent))
    for i in range(1, n + 1):
        data_venc = dc + timedelta(days=30 * i)
        valor = valor_parcela + (ajuste_ultimo if i == n else 0)
        plan.append(linha_parcela(i, data_venc, valor))

    return {
        "ok":                True,
        "valor_avista":      avista,
        "valor_negociado":   total_cliente,
        "entrada":           ent,
        "financiado":        financiado,
        "taxa_retencao_pct": taxa_pct,
        "valor_liberado":    avista,         # loja recebe = valor_avista sempre
        "retencao_rs":       retencao_rs,
        "valor_parcela":     valor_parcela,
        "n_parcelas":        n,
        "total_cliente":     total_cliente,
        "liquidacao":        "1 dia útil",
        "parcelas":          plan,
    }
