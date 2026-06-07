"""
mod_fin/total_flex.py — Total Flex: parcelamento livre, juros compostos por dias reais

Regras:
  - Parcelas 1..n-1: valor digitado livremente pelo consultor
  - Parcela n (última): fecha automaticamente o saldo devedor + juros do periodo
  - Juros compostos calculados pelos dias reais entre datas
  - Taxa lida exclusivamente do config/total_flex.json — nunca exposta ao frontend
"""
import os, json, calendar
from datetime import timedelta, date as _date
from .base import parse_data, pmt as _pmt_coef, linha_contrato, linha_entrada

_CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "total_flex.json")


def _cfg() -> dict:
    with open(_CFG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _adicionar_meses(d: _date, m: int) -> _date:
    mes = d.month + m
    ano = d.year + (mes - 1) // 12
    mes = ((mes - 1) % 12) + 1
    dia = min(d.day, calendar.monthrange(ano, mes)[1])
    return _date(ano, mes, dia)


def _juros(saldo: float, taxa: float, dt: _date, ref: _date) -> float:
    dias = (dt - ref).days
    return round(saldo * ((1 + taxa) ** (dias / 30) - 1), 2)


def _parcela(num: int, dt: _date, val_dig, saldo: float,
             taxa: float, ref: _date, ultima: bool) -> dict:
    j = _juros(saldo, taxa, dt, ref)
    if ultima:
        val_ef = round(saldo + j, 2)
        amort  = round(saldo, 2)
        sal_ap = 0.0
        val_d  = val_ef
    else:
        val_d  = round(float(val_dig or 0), 2)
        val_ef = val_d
        amort  = round(val_d - j, 2)
        sal_ap = round(saldo + j - val_d, 2)
    return {
        "numero":         num,
        "data":           dt.strftime("%d/%m/%Y"),
        "data_iso":       dt.strftime("%Y-%m-%d"),
        "valor_digitado": val_d,
        "valor_efetivo":  val_ef,
        "saldo_anterior": round(saldo, 2),
        "juros":          j,
        "amortizacao":    amort,
        "saldo_apos":     sal_ap,
        "ultima":         ultima,
        "editavel_valor": not ultima,
        "editavel_data":  True,
    }


def _resumo(valor_financiado: float, parcelas: list, dc: _date, prazo_max: int) -> dict:
    lim        = _adicionar_meses(dc, prazo_max)
    total_j    = round(sum(p["juros"] for p in parcelas), 2)
    total_pago = round(float(valor_financiado) + total_j, 2)
    return {
        "valor_financiado": round(float(valor_financiado), 2),
        "total_juros":      total_j,
        "total_pago":       total_pago,
        "data_limite":      lim.strftime("%Y-%m-%d"),
        "status":           "equilibrado",
    }


def inicializar(valor_financiado: float, n_parcelas: int,
                prazo_meses: int, data_contrato: str,
                taxa_override: float = None) -> dict:
    c       = _cfg()
    taxa    = float(taxa_override) if taxa_override is not None else c["taxa_juros_mensal"]
    p_min   = c.get("parcelas_min", 2)
    p_max   = c.get("parcelas_max", 12)
    prz_abs = c.get("prazo_maximo_meses", 12)
    prz     = min(int(prazo_meses or prz_abs), prz_abs)

    n = int(n_parcelas)
    if not (p_min <= n <= p_max):
        return {"ok": False, "erro": f"n_parcelas deve ser entre {p_min} e {p_max}"}

    dc      = parse_data(data_contrato).date()
    pmt_val = round(_pmt_coef(taxa, n) * float(valor_financiado), 2)
    saldo   = float(valor_financiado)
    ref     = dc
    plano   = []

    for i in range(n):
        dt     = dc + timedelta(days=30 * (i + 1))
        ultima = (i == n - 1)
        p      = _parcela(i + 1, dt, pmt_val, saldo, taxa, ref, ultima)
        plano.append(p)
        saldo = p["saldo_apos"]
        ref   = dt

    return {
        "ok":      True,
        "parcelas": plano,
        "resumo":  _resumo(float(valor_financiado), plano, dc, prz),
    }


def recalcular(valor_financiado: float, data_contrato: str,
               prazo_maximo_meses: int, parcelas_input: list,
               taxa_override: float = None) -> dict:
    c       = _cfg()
    taxa    = float(taxa_override) if taxa_override is not None else c["taxa_juros_mensal"]
    prz_max = int(prazo_maximo_meses or c.get("prazo_maximo_meses", 12))

    dc    = parse_data(data_contrato).date()
    lim   = _adicionar_meses(dc, prz_max)
    n     = len(parcelas_input)
    saldo = float(valor_financiado)
    ref   = dc
    plano = []
    avisos, erros = [], []

    for i, pi in enumerate(parcelas_input):
        ultima = (i == n - 1)
        dt     = parse_data(pi.get("data") or pi.get("data_iso", "")).date()
        val_d  = None if ultima else pi.get("valor_digitado")

        p = _parcela(i + 1, dt, val_d, saldo, taxa, ref, ultima)
        plano.append(p)

        if dt > lim:
            erros.append(
                f"Parcela {i+1}: vencimento {p['data']} excede o prazo limite ({lim.strftime('%d/%m/%Y')})"
            )
        if i > 0:
            prev_iso = parcelas_input[i - 1].get("data") or parcelas_input[i - 1].get("data_iso", "")
            prev_dt  = parse_data(prev_iso).date()
            if dt <= prev_dt:
                erros.append(f"Parcela {i+1}: data deve ser posterior a parcela anterior")
        if not ultima and p["valor_digitado"] < 0:
            erros.append(f"Parcela {i+1}: valor nao pode ser negativo")
        if not ultima and p["saldo_apos"] < 0:
            avisos.append(
                f"Parcela {i+1}: valor excede o saldo — ultima parcela ficara negativa"
            )

        saldo = p["saldo_apos"]
        ref   = dt

    ultima_neg = plano and plano[-1]["valor_efetivo"] < 0
    return {
        "ok":             len(erros) == 0 and not ultima_neg,
        "ultima_negativa": ultima_neg,
        "parcelas":        plano,
        "resumo":          _resumo(float(valor_financiado), plano, dc, prz_max),
        "avisos":          avisos,
        "erros":           erros,
    }


def calcular(valor_avista: float, entrada: float, n_parcelas: int,
             taxa_mensal_pct: float, data_contrato: str,
             valores_parcelas: list = None,
             datas_parcelas: list = None) -> dict:
    """Wrapper legado — taxa lida do config, taxa_mensal_pct do request ignorada."""
    from datetime import datetime as _dt
    c       = _cfg()
    taxa    = c["taxa_juros_mensal"]
    p_min   = c.get("parcelas_min", 2)
    p_max   = c.get("parcelas_max", 12)
    prz_max = c.get("prazo_maximo_meses", 12)

    n      = int(n_parcelas)
    avista = float(valor_avista)
    ent    = float(entrada or 0)

    if n < p_min or n > p_max:
        return {"ok": False, "erro": f"n_parcelas deve ser entre {p_min} e {p_max}"}
    if ent < 0:
        return {"ok": False, "erro": "Entrada nao pode ser negativa"}
    if ent >= avista:
        return {"ok": False, "erro": "Entrada deve ser menor que o valor a vista"}

    dc         = parse_data(data_contrato).date()
    financiado = round(avista - ent, 2)
    pmt_val    = round(_pmt_coef(taxa, n) * financiado, 2)
    lim        = _adicionar_meses(dc, prz_max)

    if datas_parcelas and len(datas_parcelas) >= n:
        datas = [parse_data(d).date() for d in datas_parcelas[:n]]
    else:
        datas = [dc + timedelta(days=30 * (i + 1)) for i in range(n)]

    if valores_parcelas and len(valores_parcelas) >= max(n - 1, 1):
        vals = [float(v) for v in valores_parcelas[:n - 1]]
    else:
        vals = [pmt_val] * (n - 1)

    inp = [
        {"data": datas[i].strftime("%Y-%m-%d"),
         "valor_digitado": vals[i] if i < n - 1 else None}
        for i in range(n)
    ]

    res    = recalcular(financiado, dc.strftime("%Y-%m-%d"), prz_max, inp)
    dc_dt  = _dt.combine(dc, _dt.min.time())
    plan   = [linha_contrato(dc_dt)]
    if ent > 0:
        plan.append(linha_entrada(dc_dt, ent))

    for p in res["parcelas"]:
        tipo = "ultima" if p["ultima"] else ("primeira" if p["numero"] == 1 else "parcela")
        plan.append({
            "num":            p["numero"],
            "tipo":           tipo,
            "data":           p["data"],
            "data_iso":       p["data_iso"],
            "valor":          p["valor_efetivo"],
            "valor_editavel": p["valor_digitado"],
            "juros":          p["juros"],
            "amortizacao":    p["amortizacao"],
            "saldo_apos":     p["saldo_apos"],
        })

    r          = res["resumo"]
    total_j    = r["total_juros"]
    total_parc = sum(p["valor"] for p in plan if p.get("tipo") not in ("contrato", "entrada"))
    total_cli  = round(ent + total_parc, 2)
    taxa_ef    = round(total_j / avista * 100, 4) if avista > 0 else 0.0
    ultima     = next(p for p in reversed(plan) if p.get("tipo") == "ultima")
    excede     = any(p["data_iso"] > lim.strftime("%Y-%m-%d") for p in res["parcelas"])

    return {
        "ok":                True,
        "valor_avista":      avista,
        "valor_negociado":   total_cli,
        "entrada":           ent,
        "financiado":        financiado,
        "taxa_mensal_pct":   round(taxa * 100, 4),
        "taxa_efetiva_pct":  taxa_ef,
        "taxa_retencao_pct": taxa_ef,
        "valor_liberado":    avista,
        "total_juros":       total_j,
        "valor_parcela":     pmt_val,
        "valor_ultima":      ultima["valor"],
        "n_parcelas":        n,
        "total_cliente":     total_cli,
        "prazo_limite_dias": prz_max * 30,
        "data_limite":       lim.strftime("%d/%m/%Y"),
        "data_limite_iso":   lim.strftime("%Y-%m-%d"),
        "excede_prazo":      excede,
        "avisos":            res.get("erros", []) + res.get("avisos", []),
        "parcelas":          plan,
    }
