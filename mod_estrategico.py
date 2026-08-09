# -*- coding: utf-8 -*-
"""mod_estrategico.py — Painel Estratégico (2026-08-09, pedido do usuário): consolida o modelo de
negócio da rede/loja num único snapshot — custo fixo, indicadores econômico-financeiros,
rentabilidade/precificação e comercial/operacional, com comparação automática ao período anterior
e (quando o owner é uma rede) o comparativo entre lojas.

Escopo desta 1ª entrega (decisão do usuário): só os indicadores cujo dado já existe hoje no
sistema. Ficam de fora, pra uma leva futura: Orçado×Realizado de despesa, Alertas/notificação,
PMP real por título de fornecedor, e Estoque (módulo inteiro ainda não existe). "Taxa de conversão
por volume" também fica de fora desta entrega — o denominador ("valor orçado no período") não tem
uma definição inequívoca no modelo de dados atual (Orcamento não tem timestamp de criação); precisa
de uma decisão de produto antes de implementar, pra não expor um número que pareça oficial sem ser.

Reaproveita mod_contabil (razão/DRE/balanço/natureza de custo) e mod_indicadores (fórmulas puras);
este módulo só FAZ o levantamento (queries) e monta o payload por bloco."""
from datetime import datetime, timedelta

import mod_contabil
import mod_indicadores as mi
from database import Loja, Projeto, Contrato, ContratoAssinatura, Orcamento, Briefing


def _dt(d):
    """date -> datetime (início do dia) — mod_contabil trabalha com datetime, não date."""
    return datetime.combine(d, datetime.min.time())


def _dt_fim(d):
    return datetime.combine(d, datetime.max.time())


def _lojas_do_owner(db, ot, oid):
    if ot == "rede":
        return [l.id for l in db.query(Loja).filter_by(rede_id=oid).all()]
    return [oid]


def _par(atual, anterior, nd=1):
    """{atual, anterior, variacao_pct} — o formato comum da maioria dos blocos (comparação
    automática ao período anterior, pedida na spec)."""
    return {"atual": atual, "anterior": anterior,
            "variacao_pct": mi.variacao_pct(atual, anterior) if atual is not None and anterior is not None else None}


def _vendas_no_periodo(db, lojas_owner, ini_dt, fim_dt):
    """Orçamentos com VENDA (1ª assinatura de contrato, projeto não cancelado) dentro da janela —
    mesmo critério já usado no snapshot de /api/financeiro/indicadores. Devolve lista de
    {orcamento, valor_total, markup, data_venda}."""
    cancelados = {p.nome_safe for p in db.query(Projeto)
                  .filter(Projeto.loja_id.in_(lojas_owner), Projeto.status == "cancelado").all()}
    rows_ass = (db.query(ContratoAssinatura, Contrato)
                  .join(Contrato, ContratoAssinatura.contrato_id == Contrato.id)
                  .filter(Contrato.loja_id.in_(lojas_owner)).all())
    primeira_ass, ct_por_id = {}, {}
    for ass, ct in rows_ass:
        if ct.projeto_nome in cancelados:
            continue
        ct_por_id[ct.id] = ct
        atual = primeira_ass.get(ct.id)
        if atual is None or (ass.assinado_em and ass.assinado_em < atual):
            primeira_ass[ct.id] = ass.assinado_em
    orc_ids = [c.orcamento_id for c in ct_por_id.values()]
    orcs = {o.id: o for o in db.query(Orcamento).filter(Orcamento.id.in_(orc_ids)).all()} if orc_ids else {}
    out = []
    for cid, dt in primeira_ass.items():
        if dt is None or not (ini_dt <= dt <= fim_dt):
            continue
        orc = orcs.get(ct_por_id[cid].orcamento_id)
        if orc is None:
            continue
        out.append({"valor_total": orc.valor_total or 0.0, "markup": orc.markup or 0.0,
                    "data_venda": dt, "projeto_nome": ct_por_id[cid].projeto_nome})
    return out


def _prazo_medio_ciclo(db, lojas_owner, etapa_de, etapa_ate, ini_dt, fim_dt):
    """Dias médios entre `concluido_em` da etapa_de e `concluido_em` da etapa_ate, pros projetos
    cujo evento ATE caiu dentro da janela. None se não houver nenhum par completo no período."""
    from database import CicloEtapa
    projetos_owner = [p.nome_safe for p in db.query(Projeto.nome_safe)
                      .filter(Projeto.loja_id.in_(lojas_owner)).all()]
    if not projetos_owner:
        return None
    rows = (db.query(CicloEtapa.projeto_nome, CicloEtapa.etapa_codigo, CicloEtapa.concluido_em)
              .filter(CicloEtapa.projeto_nome.in_(projetos_owner),
                      CicloEtapa.etapa_codigo.in_([etapa_de, etapa_ate]),
                      CicloEtapa.concluido_em.isnot(None)).all())
    de, ate = {}, {}
    for nome, cod, quando in rows:
        (de if cod == etapa_de else ate)[nome] = quando
    dias = [(ate[n] - de[n]).total_seconds() / 86400.0
            for n in ate if n in de and ini_dt <= ate[n] <= fim_dt and ate[n] >= de[n]]
    return round(sum(dias) / len(dias), 1) if dias else None


def snapshot(db, ot, oid, tipo_periodo, ref_date, loja_id=None):
    """Snapshot completo do Painel Estratégico. `loja_id`, quando informado (drill-down dentro de
    uma rede), restringe o comercial/operacional a UMA loja — o razão (DRE/balanço/natureza) segue
    pelo owner (rede consolidada ou loja avulsa), que é como o Plano de Contas já funciona hoje."""
    ini, fim, ini_ant, fim_ant = mi.janela_periodo(tipo_periodo, ref_date)
    ini_dt, fim_dt = _dt(ini), _dt_fim(fim)
    ini_ant_dt, fim_ant_dt = _dt(ini_ant), _dt_fim(fim_ant)

    lojas_owner = _lojas_do_owner(db, ot, oid)
    lojas_comercial = [loja_id] if loja_id else lojas_owner

    # ── Custos fixos (bloco A) ──────────────────────────────────────────────
    rn_atual = mod_contabil.relatorio_natureza(db, ot, oid, ini=ini_dt, fim=fim_dt)
    rn_ant = mod_contabil.relatorio_natureza(db, ot, oid, ini=ini_ant_dt, fim=fim_ant_dt)
    custo_fixo_atual = rn_atual["fixo"]["total"]
    custo_fixo_ant = rn_ant["fixo"]["total"]
    # série trailing de 6 meses fechados até `fim`, pra "evolução histórica" — independente do
    # tipo de período escolhido (mês/trimestre/ano só mudam a janela de COMPARAÇÃO, não o gráfico)
    labels, serie_fixo = [], []
    ancora = fim.replace(day=1)
    meses_janela = []
    for _ in range(6):
        meses_janela.append(ancora)
        ancora = (ancora - timedelta(days=1)).replace(day=1)
    meses_janela.reverse()
    for i, mi_ in enumerate(meses_janela):
        mf_ = (meses_janela[i + 1] - timedelta(days=1)) if i + 1 < len(meses_janela) else fim
        rn_mes = mod_contabil.relatorio_natureza(db, ot, oid, ini=_dt(mi_), fim=_dt_fim(mf_))
        labels.append(mi_.strftime("%m/%y"))
        serie_fixo.append(rn_mes["fixo"]["total"])
    stats_fixo = mi.custo_fixo_stats(serie_fixo)

    # ── Econômico-financeiro (bloco C) ──────────────────────────────────────
    dre_atual = mod_contabil.dre(db, ot, oid, ini=ini_dt, fim=fim_dt)
    dre_ant = mod_contabil.dre(db, ot, oid, ini=ini_ant_dt, fim=fim_ant_dt)
    bal_atual = mod_contabil.balanco(db, ot, oid, data_corte=fim_dt)
    bal_ant = mod_contabil.balanco(db, ot, oid, data_corte=fim_ant_dt)
    marg_atual = mi.margens(dre_atual)

    def _pe(dre_x, rn_x, marg_x):
        return mi.ponto_equilibrio(rn_x["fixo"]["total"], marg_x["bruta"])

    econ = {
        "faturamento_bruto": _par(dre_atual.get("receita_bruta"), dre_ant.get("receita_bruta"), 2),
        "faturamento_liquido": _par(dre_atual.get("receita_liquida"), dre_ant.get("receita_liquida"), 2),
        "lucro_liquido": _par(dre_atual.get("lucro_liquido"), dre_ant.get("lucro_liquido"), 2),
        "ebitda": _par(dre_atual.get("ebitda"), dre_ant.get("ebitda"), 2),
        "ponto_equilibrio": _par(_pe(dre_atual, rn_atual, marg_atual),
                                 _pe(dre_ant, rn_ant, mi.margens(dre_ant)), 2),
        "liquidez_corrente": _par(mi.liquidez(bal_atual["ativo"]["circulante"],
                                              bal_atual["passivo"]["circulante"], 0, 0)["corrente"],
                                  mi.liquidez(bal_ant["ativo"]["circulante"],
                                             bal_ant["passivo"]["circulante"], 0, 0)["corrente"], 2),
        "capital_giro": _par(round(bal_atual["ativo"]["circulante"] - bal_atual["passivo"]["circulante"], 2),
                             round(bal_ant["ativo"]["circulante"] - bal_ant["passivo"]["circulante"], 2), 2),
        "endividamento": _par(mi.endividamento(bal_atual["passivo"]["total"], bal_atual["ativo"]["total"]),
                              mi.endividamento(bal_ant["passivo"]["total"], bal_ant["ativo"]["total"]), 2),
    }

    # ── Rentabilidade e precificação (bloco D) ──────────────────────────────
    vendas_atual = _vendas_no_periodo(db, lojas_owner, ini_dt, fim_dt)
    vendas_ant = _vendas_no_periodo(db, lojas_owner, ini_ant_dt, fim_ant_dt)
    # margem de contribuição = (Receita líquida − CMV − despesas variáveis) ÷ Receita líquida —
    # definição clássica; CMV vem da DRE, despesas variáveis do relatório de natureza (grupo 5).
    def _mc(dre_x, rn_x):
        rl = dre_x.get("receita_liquida") or 0.0
        if not rl:
            return None
        custos_var = (dre_x.get("cmv_csp") or 0.0) + rn_x["variavel"]["total"]
        return round((rl - custos_var) / rl, 4)

    rent = {
        "markup_medio": _par(mi.media([v["markup"] for v in vendas_atual]),
                             mi.media([v["markup"] for v in vendas_ant]), 4),
        "margem_contribuicao_media": _par(_mc(dre_atual, rn_atual), _mc(dre_ant, rn_ant), 4),
        "margem_bruta": _par(marg_atual["bruta"], mi.margens(dre_ant)["bruta"], 4),
        "margem_liquida": _par(marg_atual["liquida"], mi.margens(dre_ant)["liquida"], 4),
    }

    # ── Comercial e operacional (bloco E) ───────────────────────────────────
    vals_atual = [v["valor_total"] for v in vendas_atual]
    vals_ant = [v["valor_total"] for v in vendas_ant]
    consultores_atual = {r[0] for r in db.query(Briefing.consultor_id)
                         .join(Projeto, Projeto.nome_safe == Briefing.projeto_nome)
                         .filter(Projeto.loja_id.in_(lojas_comercial),
                                 Briefing.consultor_id.isnot(None)).all()}
    receita_comercial = dre_atual.get("receita_liquida") or 0.0  # nível owner; drill-down por loja é aproximação quando loja_id é passado dentro de uma rede

    com = {
        "ticket_medio": _par(mi.media(vals_atual), mi.media(vals_ant), 2),
        "taxa_conversao_projetos": None,   # preenchido abaixo (precisa do funil por status)
        "prazo_venda_producao_dias": _par(
            _prazo_medio_ciclo(db, lojas_comercial, "7", "13", ini_dt, fim_dt),
            _prazo_medio_ciclo(db, lojas_comercial, "7", "13", ini_ant_dt, fim_ant_dt), 1),
        "prazo_entrega_montagem_dias": _par(
            _prazo_medio_ciclo(db, lojas_comercial, "16", "17", ini_dt, fim_dt),
            _prazo_medio_ciclo(db, lojas_comercial, "16", "17", ini_ant_dt, fim_ant_dt), 1),
        "produtividade_por_loja": (round(receita_comercial / len(consultores_atual), 2)
                                   if consultores_atual else None),
    }
    status_counts = {}
    for p in db.query(Projeto).filter(Projeto.loja_id.in_(lojas_comercial)).all():
        st_p = (p.status or "").strip().lower() or "quente"
        status_counts[st_p] = status_counts.get(st_p, 0) + 1
    kpis = mi.kpis_comerciais(status_counts, vals_atual)
    com["taxa_conversao_projetos"] = _par(kpis["taxa_conversao"], None, 4)

    resultado = {
        "periodo": {"tipo": tipo_periodo, "ini": ini.isoformat(), "fim": fim.isoformat(),
                    "ini_anterior": ini_ant.isoformat(), "fim_anterior": fim_ant.isoformat()},
        "loja_id": loja_id,
        "custos_fixos": {"medio_6m": stats_fixo["media"], "ultimo_mes": stats_fixo["ultimo"],
                         "variacao_pct": stats_fixo["variacao_pct"],
                         "atual_periodo": custo_fixo_atual,
                         "serie": {"labels": labels, "valores": serie_fixo}},
        "economico_financeiro": econ,
        "rentabilidade": rent,
        "comercial_operacional": com,
    }

    # ── Comparativo entre lojas (bloco F) — só faz sentido pra owner=rede ───
    if ot == "rede" and len(lojas_owner) > 1:
        ranking = []
        for lid in lojas_owner:
            loja = db.get(Loja, lid)
            dre_loja = mod_contabil.dre(db, "loja", lid, ini=ini_dt, fim=fim_dt)
            vendas_loja = _vendas_no_periodo(db, [lid], ini_dt, fim_dt)
            ranking.append({
                "loja_id": lid, "nome": loja.nome if loja else str(lid),
                "faturamento_liquido": dre_loja.get("receita_liquida") or 0.0,
                "lucro_liquido": dre_loja.get("lucro_liquido") or 0.0,
                "margem_liquida": mi.margens(dre_loja)["liquida"],
                "ticket_medio": mi.media([v["valor_total"] for v in vendas_loja]),
            })
        ranking.sort(key=lambda r: r["faturamento_liquido"], reverse=True)
        media_fat = mi.media([r["faturamento_liquido"] for r in ranking])
        for r in ranking:
            r["benchmark_vs_media_pct"] = mi.variacao_pct(r["faturamento_liquido"], media_fat)
        resultado["comparativo_lojas"] = ranking
    else:
        resultado["comparativo_lojas"] = None

    return resultado
