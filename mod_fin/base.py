"""
mod_fin/base.py — funções compartilhadas do módulo financeiro
"""
import os, json
from datetime import datetime, timedelta

# Diretório das tabelas JSON (relativo ao diretório do app)
_TABELAS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tabelas_financeiras")


def carregar_json(codigo: str) -> dict:
    """Lê tabelas_financeiras/<codigo>.json. Retorna {} se não encontrar."""
    path = os.path.join(_TABELAS_DIR, f"{codigo}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pmt(taxa: float, n: int) -> float:
    """Coeficiente PMT: pagamento periódico que liquida n períodos à taxa dada."""
    if taxa == 0:
        return 1.0 / n
    return taxa * (1 + taxa) ** n / ((1 + taxa) ** n - 1)


def parse_data(data_str: str) -> datetime:
    """Converte string 'AAAA-MM-DD' para datetime. Usa hoje se inválida."""
    try:
        return datetime.strptime(data_str, "%Y-%m-%d")
    except Exception:
        return datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)


def linha_contrato(data: datetime) -> dict:
    return {"num": 0, "tipo": "contrato", "data": data.strftime("%d/%m/%Y"), "valor": None}


def linha_entrada(data: datetime, valor: float) -> dict:
    return {"num": 0, "tipo": "entrada", "data": data.strftime("%d/%m/%Y"), "valor": round(valor, 2)}


def linha_parcela(num: int, data: datetime, valor: float) -> dict:
    tipo = "primeira" if num == 1 else "parcela"
    return {"num": num, "tipo": tipo, "data": data.strftime("%d/%m/%Y"), "valor": round(valor, 2)}


def validar_plano_pagamento(plano):
    """Valida o plano de pagamento a persistir (dict do forma_pagamento JSON do orçamento).
    Nenhuma parcela nem a entrada pode ser negativa — um plano Parcelamento Loja recalculado sobre
    um total defasado (ex.: ambiente removido do orçamento) fecha a última parcela negativa,
    e isso nunca deve chegar ao banco. Retorna mensagem de erro, ou None se o plano é válido
    (None/sem lista de parcelas = formatos legados, aceitos)."""
    if not isinstance(plano, dict):
        return None

    def _num(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return None   # não-numérico → inválido (erro 400, não 500)

    ent = plano.get("entrada_valor")
    if ent is not None:
        ev = _num(ent)
        if ev is None:
            return "Plano de pagamento inválido: entrada não numérica."
        if ev < 0:
            return "Plano de pagamento inválido: entrada negativa."
    for p in (plano.get("parcelas") or []):
        v = (p or {}).get("valor")
        if v is None:
            continue
        pv = _num(v)
        if pv is None:
            return ("Plano de pagamento inválido: parcela %s com valor não numérico."
                    % ((p or {}).get("num") or "?"))
        if pv < 0:
            return ("Plano de pagamento inválido: parcela %s com valor negativo — "
                    "refaça o parcelamento para o total atual do orçamento."
                    % (p.get("num") or "?"))
    return None
