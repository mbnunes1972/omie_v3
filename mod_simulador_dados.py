# -*- coding: utf-8 -*-
"""mod_simulador_dados.py — Adapter Orizon do Simulador de Modelo de Negócios (Sessão 185, D3).

Levanta o `ModeloLoja` (contrato de `mod_simulador.py`) a partir do que já existe no sistema:
config financeira/provisões da implantação, folha e remunerações (faixas de comissão),
plano de contas + razão (custos fixos, dívida), perfil fiscal (carga tributária) e o histórico
de vendas (médias de faturamento/markup por janela — RF-13 descarta meses zerados).

NENHUMA fórmula de simulação mora aqui — só levantamento (queries) + montagem do JSON.
`montar_modelo` é o único ponto de entrada; o resto é privado.

Decisões documentadas (v1, sem fonte real melhor disponível hoje):
- "Amortizações" e "juros mensal" não têm registro histórico no sistema → vêm de config nova
  da loja (`config_financeira_json["amortizacoes"/"juros_mensal"]`, mod_provisoes), editável.
- "Dívida nominal" (RF-24) vem do saldo REAL das contas de dívida (2.1.08/2.1.09/2.1.10 —
  AcordoFabrica/AcordoMovimento) no razão PRÓPRIO da loja (`mod_contabil.resolver_owner` — desde
  o corte da Sessão 187, toda loja tem razão próprio, nunca mais o da rede consolidada).
- Comissionamento de colaborador NÃO-consultor: `usa_comissao_vendas` → "faixa_vendedor" (real);
  `comissao_json.por_meta=True` → aproximado como "faixa_loja" (atingimento fat/meta da loja,
  mesmas faixas de comissao_vendas — não há faixas distintas de gerência no sistema hoje);
  `comissao_json` com pct fixo → "pct_fat". "Pró-labore" não tem flag própria no cadastro — é
  inferido pelo nome da Função conter "diretor"/"sócio"/"socio"/"proprietár" (heurística v1).
- "Markup com frete" não é uma métrica persistida por orçamento → estimado aplicando o
  `frete_fab_pct` ATUAL da loja sobre o CFO histórico de cada venda (Orcamento.cfo).
"""
import json
from datetime import datetime, timedelta

import mod_contabil
import mod_provisoes
from mod_simulador import media_historica
from database import (Funcionario, Funcao, Conta, Contrato, ContratoAssinatura, Orcamento,
                      Projeto, Usuario)

_PRO_LABORE_MARCADORES = ("diretor", "sócio", "socio", "proprietár")

_VARIAVEIS_PROVISOES = [
    ("frete_fab_pct", "Frete Fábrica"), ("com_adm_pct", "Comissão Administrativa"),
    ("com_med_pct", "Comissão de Medição"), ("com_proj_exec_pct", "Comissão Projeto Executivo"),
    ("frete_loc_pct", "Frete Local"), ("assist_pct", "Assistência Técnica"),
    ("ins_loc_pct", "Instalação Local"),
]
_VARIAVEIS_CONTABEIS = [("montagem_pct", "Montagem"), ("garantia_pct", "Garantia")]

_JANELA_MESES = {"mes": 1, "tri": 3, "sem": 6, "ano": 12}
_CONTAS_DIVIDA = ("2.1.08", "2.1.09", "2.1.10")   # dívida com fábrica/empresa/banco (AcordoFabrica)


def _cfg_financeira(loja):
    if loja.config_financeira_json:
        try:
            stored = mod_provisoes.normalizar_cronograma_formato(json.loads(loja.config_financeira_json))
            return {**mod_provisoes.config_financeira_default(), **stored}
        except (ValueError, TypeError):
            pass
    return mod_provisoes.config_financeira_default()


def _mes_fechado(ref=None):
    """(ini, fim) do último mês FECHADO antes de `ref` (default: agora)."""
    ref = ref or datetime.utcnow()
    primeiro_atual = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ultimo_dia_ant = primeiro_atual - timedelta(days=1)
    return ultimo_dia_ant.replace(day=1, hour=0, minute=0, second=0, microsecond=0), \
        datetime.combine(ultimo_dia_ant.date(), datetime.max.time())


def _competencia(dt):
    return dt.strftime("%Y-%m")


def _vendas_fechadas_da_loja(db, loja_id):
    """[{'val_liq','cfo','markup','data_venda'}] — mesma regra do Painel Estratégico (1ª
    assinatura de contrato, projeto não cancelado), mas trazendo cfo/val_liq (RN-01/RF-18)."""
    cancelados = {p.nome_safe for p in db.query(Projeto)
                  .filter(Projeto.loja_id == loja_id, Projeto.status == "cancelado").all()}
    rows_ass = (db.query(ContratoAssinatura, Contrato)
                  .join(Contrato, ContratoAssinatura.contrato_id == Contrato.id)
                  .filter(Contrato.loja_id == loja_id).all())
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
        if dt is None:
            continue
        orc = orcs.get(ct_por_id[cid].orcamento_id)
        if orc is None:
            continue
        out.append({"val_liq": orc.val_liq or orc.valor_liquido or 0.0, "cfo": orc.cfo or 0.0,
                    "markup": orc.markup or 0.0, "data_venda": dt})
    return out


def _medias_janela_e_markups(vendas, ref, n_vendedores_ativos, frete_fab_pct):
    """RF-11/RF-12/RF-13: para cada janela (mes/tri/sem/ano), média mensal de faturamento POR
    POSTO (Σ vendas do mês ÷ nº de vendedores ativos) e média dos markups (seco/com frete),
    descartando meses sem venda (`media_historica`)."""
    n_postos = max(1, n_vendedores_ativos)
    medias_janela, markups_seco, markups_frete = {}, {}, {}
    for chave, n_meses in _JANELA_MESES.items():
        totais_mes, seco_mes, frete_mes = [], [], []
        ancora = ref.replace(day=1)
        for _ in range(n_meses):
            ultimo_dia_ant = ancora - timedelta(days=1)
            ini_mes = ultimo_dia_ant.replace(day=1)
            fim_mes = datetime.combine(ultimo_dia_ant.date(), datetime.max.time())
            do_mes = [v for v in vendas if v["data_venda"] and ini_mes <= v["data_venda"] <= fim_mes]
            totais_mes.append(sum(v["val_liq"] for v in do_mes))
            for v in do_mes:
                if v["cfo"]:
                    seco_mes.append(v["val_liq"] / v["cfo"])
                    base_frete = v["cfo"] * (1 + frete_fab_pct / 100.0)
                    if base_frete:
                        frete_mes.append(v["val_liq"] / base_frete)
            ancora = ini_mes
        media_total = media_historica(totais_mes)
        medias_janela[chave] = round(media_total / n_postos, 2) if media_total is not None else 0.0
        markups_seco[chave] = media_historica(seco_mes) or 0.0
        markups_frete[chave] = media_historica(frete_mes) or 0.0
    return medias_janela, markups_seco, markups_frete


def _custos_fixos(db, ot, oid):
    """RF-21: todas as contas analíticas do grupo 5 (despesa), inclusive sem lançamento — valor
    = média dos últimos 3 meses fechados (descartando meses zerados; conta sem NENHUM
    movimento nos 3 meses fica 0.0, estado real válido — RF-21 "atenuada")."""
    mod_contabil.seed_plano(db, ot, oid)
    contas = (db.query(Conta).filter_by(owner_tipo=ot, owner_id=oid, grupo=5, tipo="analitica", ativa=1)
              .order_by(Conta.codigo).all())
    ids = [c.id for c in contas]
    if not ids:
        return []
    ref = datetime.utcnow()
    series = {cid: [] for cid in ids}
    ancora = ref.replace(day=1)
    for _ in range(3):
        ultimo_dia_ant = ancora - timedelta(days=1)
        ini_mes = ultimo_dia_ant.replace(day=1)
        fim_mes = datetime.combine(ultimo_dia_ant.date(), datetime.max.time())
        debs = mod_contabil._somas_por_conta(db, ot, oid, ids, "debito", ini_mes, fim_mes)
        creds = mod_contabil._somas_por_conta(db, ot, oid, ids, "credito", ini_mes, fim_mes)
        for cid in ids:
            series[cid].append(debs.get(cid, 0.0) - creds.get(cid, 0.0))
        ancora = ini_mes
    return [{"nome": "%s — %s" % (c.codigo, c.nome), "valor": media_historica(series[c.id]) or 0.0}
            for c in contas]


def _divida_nominal(db, ot, oid):
    total = 0.0
    for codigo in _CONTAS_DIVIDA:
        conta = db.query(Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=codigo).first()
        if conta:
            total += mod_contabil.saldo_conta(db, ot, oid, conta.id)
    return round(total, 2)


def _e_pro_labore(nome_funcao):
    n = (nome_funcao or "").strip().lower()
    return any(m in n for m in _PRO_LABORE_MARCADORES)


def _faixas(lista_faixas):
    return [[fx.get("venda_ate"), fx.get("pct") or 0.0, None] for fx in (lista_faixas or [])]


_STATUS_VENDA = ("fechado", "convertido")


def _vendas_liquido_consultor(db, loja_id, usuario_id, competencia):
    """Réplica minimalista de mod_folha.vendas_liquido_consultor — não importada porque o
    domínio `folha` já depende de `financeiro` (importar de volta criaria dependência
    declarada em ciclo entre os dois no manifesto)."""
    if not usuario_id:
        return 0.0
    total = 0.0
    projs = (db.query(Projeto).filter(Projeto.loja_id == loja_id, Projeto.criado_por_id == usuario_id,
                                      Projeto.status.in_(_STATUS_VENDA)).all())
    for p in projs:
        if p.status_at is None or p.status_at.strftime("%Y-%m") != competencia:
            continue
        orcs = db.query(Orcamento).filter_by(projeto_id=p.nome_safe).all()
        if orcs:
            total += max((o.valor_liquido or o.valor_total or 0.0) for o in orcs)
    return round(total, 2)


def montar_modelo(db, loja, cenario="atual", janela="mes"):
    """Monta o `ModeloLoja` (contrato de mod_simulador.simular) pra `loja` a partir das fontes
    reais. Somente leitura (RNF-01) — nenhuma query aqui grava nada."""
    cfg = _cfg_financeira(loja)
    ot, oid = mod_contabil.resolver_owner(db, {"loja_id": loja.id, "rede_id": None})
    ref = datetime.utcnow()
    ini_fechado, fim_fechado = _mes_fechado(ref)
    competencia_fechada = _competencia(ini_fechado)

    consultores = (db.query(Funcionario, Funcao)
                   .join(Funcao, Funcionario.funcao_id == Funcao.id)
                   .filter(Funcionario.loja_id == loja.id, Funcionario.status == "ativo",
                           Funcao.usa_comissao_vendas == 1).all())
    meta_mensal = float((cfg.get("comissao_vendas") or {}).get("meta_mensal") or 0.0)

    vendedores = []
    idx_por_funcionario = {}
    for f, fn in consultores:
        atual = _vendas_liquido_consultor(db, loja.id, f.usuario_id, competencia_fechada)
        idx_por_funcionario[f.id] = len(vendedores)
        vendedores.append({"nome": f.nome, "atual": atual, "meta": meta_mensal, "ativo": True})

    vendas_hist = _vendas_fechadas_da_loja(db, loja.id)
    frete_fab_pct = float((cfg.get("provisoes") or {}).get("frete_fab_pct") or 0.0)
    medias_janela, mk_seco, mk_frete = _medias_janela_e_markups(
        vendas_hist, ref, len(vendedores), frete_fab_pct)

    variaveis = []
    prov = cfg.get("provisoes") or {}
    for chave, nome in _VARIAVEIS_PROVISOES:
        variaveis.append({"chave": chave, "nome": nome, "pct": float(prov.get(chave) or 0.0)})
    provc = cfg.get("provisoes_contabeis") or {}
    for chave, nome in _VARIAVEIS_CONTABEIS:
        variaveis.append({"chave": chave, "nome": nome, "pct": float(provc.get(chave) or 0.0)})

    faixas_consultor = _faixas((cfg.get("comissao_vendas") or {}).get("faixas_comissao"))

    folha = []
    for f in db.query(Funcionario).filter_by(loja_id=loja.id, status="ativo").all():
        fn = db.get(Funcao, f.funcao_id) if f.funcao_id else None
        pro_labore = _e_pro_labore(fn.nome if fn else f.cargo)
        salario_fixo = float((fn.salario_fixo if fn else None) or 0.0)
        comissao_fixa = float((getattr(fn, "comissao_fixa", 0.0) if fn else 0.0) or 0.0)
        if fn and fn.usa_comissao_vendas:
            item = {"comissionamento": "faixa_vendedor", "vendedor_idx": idx_por_funcionario.get(f.id)}
        elif fn and fn.comissao_json:
            try:
                com = json.loads(fn.comissao_json)
            except (ValueError, TypeError):
                com = {}
            if com.get("por_meta"):
                item = {"comissionamento": "faixa_loja"}
            elif com.get("pct"):
                item = {"comissionamento": "pct_fat", "pct_fixo": float(com.get("pct") or 0.0)}
            else:
                item = {"comissionamento": "none"}
        else:
            item = {"comissionamento": "none"}
        folha.append({"nome": f.nome, "cargo": (fn.nome if fn else f.cargo) or "",
                      "salario_fixo": salario_fixo, "comissao_fixa": comissao_fixa,
                      "pro_labore": pro_labore, "ativo": True, **item})

    custos_fixos = _custos_fixos(db, ot, oid)
    amortizacoes = [{"nome": a.get("nome"), "valor": float(a.get("valor") or 0.0),
                     "prazo_meses": a.get("prazo_meses")} for a in (cfg.get("amortizacoes") or [])]

    return {
        "vendedores": vendedores, "medias_janela": medias_janela,
        "variaveis": variaveis,
        "markups_medios": {"seco": mk_seco, "com_frete": mk_frete},
        "folha": folha, "encargos_pct": 35.0,
        "faixas_consultor": faixas_consultor, "faixas_gerente": faixas_consultor,
        "custos_fixos": custos_fixos, "amortizacoes": amortizacoes,
        "juros": float(cfg.get("juros_mensal") or 0.0),
        "impostos_pct": float((cfg.get("defaults_negociacao") or {}).get("carga_trib_pct") or 0.0),
        "divida": _divida_nominal(db, ot, oid),
    }
