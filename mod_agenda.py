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


def data_entrega_da_fase(card_data, card_prazo, entrega_prevista_fase,
                         data_entrega_projeto, prevista_16=None):
    """Cadeia CANÔNICA da data de entrega de uma fase — COMPARTILHADA pela faixa de entrega
    (entrega-resumo) e pela Agenda (achado 🟠2 da Vera, 2026-08-03: as duas divergiam).
    Ordem: entrega realizada (card) > prazo da expedição > previsão da fase > DATA DE ENTREGA
    do projeto (âncora formal, definida na assinatura) > prevista da etapa 16 (último recurso
    — o progressivo do cronograma pode divergir da promessa formal, que prevalece)."""
    return (_d(card_data) or _d(card_prazo) or _d(entrega_prevista_fase)
            or _d(data_entrega_projeto) or _d(prevista_16))


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
        data = data_entrega_da_fase(entregue, f.get("card_prazo_entrega"),
                                    f.get("entrega_prevista"), p.get("data_entrega"),
                                    e16.get("prevista"))
        if not data:
            continue
        out.append({**base, "data": data, "setor": "expedicao", "etapa": "16",
                    "titulo": mod_ciclo.ETAPA_NOME["16"], "fase": f.get("ordem"),
                    "valor": f.get("val_liq"), "realizado": entregue is not None,
                    "retida": f.get("status") == "retido"})
    return out


# ── Fatia 3: CARGAS — catálogo de itens com valor (spec §5 rev 2) ────────────────────────────
# Cada item é uma LENTE sobre o Val_Liq da fase: cargas distribuídas usam a janela do
# CRONOGRAMA espalhada em dias úteis (mod_calendario); marcos valorados caem num dia.
# Fase RETIDA fica fora das cargas (não avança — não ocupa agenda até liberar).
ITENS_VALOR = [("pe", "Projeto Executivo"),
               ("conferencia", "Conferência e Implantação"),
               ("producao", "Produção (saída da fábrica)"),
               ("montagem", "Montagem"),
               ("entrega", "Entrega ao cliente")]


def _dia_seguinte_util(d, cfg):
    import mod_calendario
    from datetime import timedelta
    return mod_calendario.proximo_dia_util(d + timedelta(days=1), cfg)


def _janela_espalhada(valor, inicio, fim, cfg):
    """Espalha `valor` nos dias úteis de [inicio, fim] (fim < inicio → tudo no inicio)."""
    import mod_calendario
    inicio = mod_calendario.proximo_dia_util(inicio, cfg)
    n = mod_calendario.dias_uteis_entre(inicio, fim, cfg) if fim and fim >= inicio else 1
    return mod_calendario.espalhar(valor, inicio, max(1, n), cfg)


def cargas_do_projeto(p, cfg_agenda=None):
    """Cargas de UM projeto: [{data, item, valor, projeto, fase}]. Datas do CRONOGRAMA
    (executado substitui previsto no fim da janela)."""
    cfg = cfg_agenda or {}
    et = p.get("etapas") or {}

    def _fim(cod):
        e = et.get(cod) or {}
        return _d(e.get("concluida_em")) or _d(e.get("prevista"))

    e16 = et.get("16") or {}
    val_proj = p.get("val_liq")
    fases = p.get("fases") or [{"ordem": None, "status": None, "val_liq": val_proj,
                                "entrega_prevista": None, "card_prazo_entrega": None,
                                "card_data_entrega": _d(e16.get("concluida_em"))}]
    out = []

    def _add_espalhado(item, valor, inicio, fim, fase):
        if valor is None or not inicio:
            return
        for dia, fatia in _janela_espalhada(valor, inicio, fim, cfg).items():
            out.append({"data": dia, "item": item, "valor": fatia,
                        "projeto": p.get("nome_safe"), "fase": fase})

    def _add_marco(item, valor, dia, fase):
        if valor is None or not dia:
            return
        out.append({"data": dia, "item": item, "valor": valor,
                    "projeto": p.get("nome_safe"), "fase": fase})

    fim10, fim11, fim12, fim13, fim17 = (_fim(c) for c in ("10", "11", "12", "13", "17"))
    for f in fases:
        if f.get("status") == "retido":
            continue
        vl = f.get("val_liq")
        # Projeto Executivo: conclusão da 10 → prevista da 11
        if fim10 and fim11:
            _add_espalhado("pe", vl, _dia_seguinte_util(fim10, cfg), fim11, f.get("ordem"))
        # Conferência e Implantação: prevista da 11 → prevista da 12
        if fim11 and fim12:
            _add_espalhado("conferencia", vl, _dia_seguinte_util(fim11, cfg), fim12, f.get("ordem"))
        # Produção: marco valorado na SAÍDA da fábrica (prevista/realizada da 13)
        _add_marco("producao", vl, fim13, f.get("ordem"))
        # Entrega ao cliente: marco valorado na data de entrega da fase (cadeia canônica)
        entrega = data_entrega_da_fase(f.get("card_data_entrega"), f.get("card_prazo_entrega"),
                                       f.get("entrega_prevista"), p.get("data_entrega"),
                                       e16.get("prevista"))
        _add_marco("entrega", vl, entrega, f.get("ordem"))
        # Montagem: dia útil seguinte à entrega da fase → prevista da 17
        if entrega:
            _add_espalhado("montagem", vl, _dia_seguinte_util(entrega, cfg),
                           (fim17 if (fim17 and fim17 > entrega) else None), f.get("ordem"))
    return out


def cargas(projetos, cfg_agenda=None, de=None, ate=None):
    """Cargas de VÁRIOS projetos filtradas por período, ordenadas por (data, item, projeto)."""
    out = []
    for p in (projetos or []):
        for c in cargas_do_projeto(p, cfg_agenda):
            if de and c["data"] < de:
                continue
            if ate and c["data"] > ate:
                continue
            out.append(c)
    out.sort(key=lambda c: (c["data"], c["item"], c["projeto"] or ""))
    return out


# ── Fatia 4: CAPACIDADE — dimensionamento diário (spec §6 rev) ───────────────────────────────
# A janela de trabalho vem do CRONOGRAMA (cargas acima); a produtividade converte a
# necessidade diária em recurso: Montagem em DUPLAS (⌈Σ/produtividade⌉ × disponíveis) e
# Projeto Executivo em OCUPAÇÃO (% da produtividade diária de PE da loja).

def capacidade(cargas_lista, cfg_agenda=None):
    """[{data, montagem, duplas, pe, pe_pct}] por dia com carga de montagem/PE (ordenado)."""
    import math
    cfg = cfg_agenda or {}
    prod_m = float(cfg.get("produtividade_montagem_rs_dupla_dia") or 7000.0)
    prod_pe = float(cfg.get("produtividade_pe_rs_dia") or 20000.0)
    por_dia = {}
    for c in (cargas_lista or []):
        if c.get("item") not in ("montagem", "pe"):
            continue
        d = por_dia.setdefault(c["data"], {"montagem": 0.0, "pe": 0.0})
        d[c["item"]] += float(c.get("valor") or 0.0)
    out = []
    for data in sorted(por_dia):
        m = round(por_dia[data]["montagem"], 2)
        p = round(por_dia[data]["pe"], 2)
        out.append({"data": data, "montagem": m,
                    "duplas": (math.ceil(m / prod_m) if m > 0 else 0),
                    "pe": p, "pe_pct": (round(p / prod_pe * 100.0, 1) if p > 0 else 0.0)})
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
