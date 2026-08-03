# -*- coding: utf-8 -*-
"""mod_calendario.py — utilitário GENÉRICO de dias úteis (PURO, sem I/O).

Nasceu na Fatia 0 da Agenda da Loja (spec docs/superpowers/specs/agenda/
2026-08-03-agenda-da-loja-design.md §7) mas é deliberadamente genérico: o prazo contratual e
os prazos de etapa podem migrar para cá no futuro.

`cfg` é a seção `agenda` da config da loja (ou qualquer dict com as chaves):
    {"sabado_util": bool, "feriados": ["AAAA-MM-DD", ...]}
Default (cfg ausente/vazia): seg–sex úteis, sem feriados. Feriado malformado é IGNORADO
(config de loja pode vir suja do banco — nunca lançar por causa dela).
"""
from datetime import date, datetime, timedelta


def _feriados(cfg):
    out = set()
    for f in ((cfg or {}).get("feriados") or []):
        if isinstance(f, date) and not isinstance(f, datetime):
            out.add(f)
            continue
        try:
            out.add(datetime.strptime(str(f)[:10], "%Y-%m-%d").date())
        except (ValueError, TypeError):
            continue
    return out


def eh_dia_util(d, cfg=None):
    """True se `d` é dia útil: seg–sex (sábado se `sabado_util`), fora feriados."""
    limite = 5 if (cfg or {}).get("sabado_util") else 4   # weekday(): 5=sáb, 6=dom
    if d.weekday() > limite:
        return False
    return d not in _feriados(cfg)


def proximo_dia_util(d, cfg=None):
    """O próprio `d` se já for útil; senão o primeiro dia útil seguinte."""
    feriados = _feriados(cfg)
    limite = 5 if (cfg or {}).get("sabado_util") else 4
    while d.weekday() > limite or d in feriados:
        d += timedelta(days=1)
    return d


def adicionar_dias_uteis(d, n, cfg=None):
    """Data `n` dias úteis após `d`. n=0 → o próprio `d` normalizado a útil (rola pra frente)."""
    d = proximo_dia_util(d, cfg)
    for _ in range(max(0, int(n))):
        d = proximo_dia_util(d + timedelta(days=1), cfg)
    return d


def dias_uteis_entre(a, b, cfg=None):
    """Nº de dias úteis no intervalo [a, b] INCLUSIVO. a > b → 0."""
    if a > b:
        return 0
    n, d = 0, a
    while d <= b:
        if eh_dia_util(d, cfg):
            n += 1
        d += timedelta(days=1)
    return n


def espalhar(valor, inicio, n_dias_uteis, cfg=None):
    """Reparte `valor` em `n_dias_uteis` fatias iguais a partir de `inicio` (normalizado a
    útil), pulando fds/feriados. A ÚLTIMA fatia absorve o resíduo do arredondamento →
    Σ fatias == valor exato ao centavo (padrão da casa). Retorna dict {date: fatia} em ordem.
    n < 1 é tratado como 1."""
    n = max(1, int(n_dias_uteis))
    valor = round(float(valor or 0.0), 2)
    fatia = round(valor / n, 2)
    out, d, acumulado = {}, proximo_dia_util(inicio, cfg), 0.0
    for i in range(n):
        v = fatia if i < n - 1 else round(valor - acumulado, 2)
        out[d] = v
        acumulado = round(acumulado + v, 2)
        if i < n - 1:
            d = proximo_dia_util(d + timedelta(days=1), cfg)
    return out
