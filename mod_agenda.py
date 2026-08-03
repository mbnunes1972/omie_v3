# -*- coding: utf-8 -*-
"""mod_agenda.py — Agenda da Loja: motor de MARCOS (PURO, sem I/O).

Fatia 2 da spec docs/superpowers/specs/agenda/2026-08-03-agenda-da-loja-design.md.
A Agenda é DERIVADA: este módulo só transforma dados já carregados (cronograma, fases,
expedição) em marcos por Setor. Unidade de valor = Val_Liq (congelado por fase; do orçamento
contratado no projeto não desmembrado) — Fatia 1.

Entrada (por projeto, montada pelo endpoint):
    {"nome_safe", "cliente", "val_liq", "previsao_medicao", "data_entrega",
     "etapas": {codigo: {"prevista": dt|None, "concluida_em": dt|None}},
     "fases": [{"ordem", "status", "val_liq", "entrega_prevista",
                "card_prazo_entrega", "card_data_entrega"}]}   # [] = não desmembrado

Saída (marco): {"data": date, "setor", "etapa", "titulo", "projeto", "cliente",
                "fase": ordem|None, "valor": float|None, "realizado": bool, "retida": bool}
"""
from datetime import date, datetime

import mod_ciclo

# Setor (Agenda, spec §3) — refinamento DE EXIBIÇÃO de mod_ciclo.FAIXA_POR_ETAPA.
SETOR_POR_ETAPA = {
    "9": "medicao", "10": "medicao",
    "11": "pe", "11a": "pe", "11b": "pe", "11c": "pe", "11e": "pe",
    "12": "expedicao", "13": "expedicao", "14": "expedicao", "15": "expedicao", "16": "expedicao",
    "17": "montagem", "18": "montagem", "19": "montagem", "20": "montagem",
    "8": "financeiro", "11d": "financeiro", "21": "financeiro",
}
SETORES = [("medicao", "Medição"), ("pe", "Projeto Executivo"), ("expedicao", "Expedição"),
           ("montagem", "Montagem"), ("financeiro", "Financeiro")]

# Etapas que viram marco direto (a 16 tem tratamento por FASE; Comercial 1–7 fora da v1).
ETAPAS_MARCO = ["8", "9", "10", "11a", "11b", "11c", "11d", "11e",
                "12", "13", "14", "15", "17", "18", "19", "20", "21"]


def nome_etapa(codigo):
    if codigo in mod_ciclo.ETAPA_NOME:
        return mod_ciclo.ETAPA_NOME[codigo]
    sf = mod_ciclo.SUBFASES_PE.get(codigo)
    if sf:
        return sf["nome"]
    if codigo == "11d":
        return "Aprovação financeira II"
    return "Etapa " + str(codigo)


def _d(v):
    """datetime|date|None → date|None."""
    if v is None:
        return None
    return v.date() if isinstance(v, datetime) else v


def marcos_do_projeto(p):
    """Marcos de UM projeto (lista, sem ordenação). Executado substitui previsto
    (concluida_em → realizado=True); etapa sem nenhuma data não gera marco."""
    out = []
    et = p.get("etapas") or {}
    base = {"projeto": p.get("nome_safe"), "cliente": p.get("cliente")}
    val_proj = p.get("val_liq")
    for cod in ETAPAS_MARCO:
        e = et.get(cod) or {}
        conc = _d(e.get("concluida_em"))
        prev = _d(e.get("prevista"))
        if cod == "10" and prev is None:                    # medição: fallback na previsão do gate
            prev = _d(p.get("previsao_medicao"))
        data = conc or prev
        if not data:
            continue
        out.append({**base, "data": data, "setor": SETOR_POR_ETAPA[cod], "etapa": cod,
                    "titulo": nome_etapa(cod), "fase": None, "valor": val_proj,
                    "realizado": conc is not None, "retida": False})
    # Entrega no cliente (16) — por FASE (mesma regra da faixa de entrega, Sessão 136):
    # card da expedição > previsão da fase > previsto da 16 > data de entrega do projeto.
    e16 = et.get("16") or {}
    fases = p.get("fases") or [{"ordem": None, "status": None, "val_liq": val_proj,
                                "entrega_prevista": None, "card_prazo_entrega": None,
                                "card_data_entrega": _d(e16.get("concluida_em"))}]
    for f in fases:
        entregue = _d(f.get("card_data_entrega"))
        data = (entregue or _d(f.get("card_prazo_entrega")) or _d(f.get("entrega_prevista"))
                or _d(e16.get("prevista")) or _d(p.get("data_entrega")))
        if not data:
            continue
        out.append({**base, "data": data, "setor": "expedicao", "etapa": "16",
                    "titulo": mod_ciclo.ETAPA_NOME["16"], "fase": f.get("ordem"),
                    "valor": f.get("val_liq"), "realizado": entregue is not None,
                    "retida": f.get("status") == "retido"})
    return out


def marcos(projetos, de=None, ate=None, setor=None):
    """Marcos de VÁRIOS projetos, filtrados por período [de, ate] (inclusivo) e Setor,
    ordenados por (data, projeto, etapa)."""
    out = []
    for p in (projetos or []):
        for m in marcos_do_projeto(p):
            if de and m["data"] < de:
                continue
            if ate and m["data"] > ate:
                continue
            if setor and m["setor"] != setor:
                continue
            out.append(m)
    out.sort(key=lambda m: (m["data"], m["projeto"] or "", m["etapa"]))
    return out
