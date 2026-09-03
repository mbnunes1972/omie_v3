"""mod_comissao.py — Comissão por papel (Fase 4). Ao concluir uma etapa operacional, prepara a
comissão do executor na folha do mês de conclusão. Base = Σ order_total dos ambientes atribuídos no
Mapa (projeto inteiro se atribuição = NULL) × % da Função. Itens em comissao_folha, somados na Folha."""
import json

import mod_folha
from database import (ComissaoFolha, Funcao, Funcionario, PoolAmbiente, AtribuicaoAmbiente, Orcamento)

# Etapa operacional → papel do Mapa (só estas geram comissão de papel). A etapa 18 (Assistência
# pós Montagem) SAIU daqui (2026-08-06): a comissão de papel é calculada a partir de quem está
# atribuído no Mapa (atribuicoes_ambiente) — 'assistencia' deixou de ser um papel do Mapa (ver
# mod_escopo.PAPEIS), então a base sempre daria zero. Sem substituto automático por ora
# (comissão de assistência, se vier a existir, precisa de desenho próprio a partir dos CASOS).
PAPEL_POR_ETAPA = {
    "10": "medicao",
    "11": "projeto_executivo", "11a": "projeto_executivo", "11b": "projeto_executivo",
    "11c": "projeto_executivo", "11d": "projeto_executivo", "11e": "projeto_executivo",
    "17": "montagem",
}


def papel_da_etapa(codigo):
    return PAPEL_POR_ETAPA.get(str(codigo))


def _ambientes_da_base(db, projeto_nome, papel, funcionario_id):
    """Ambientes (PoolAmbiente) que compõem a base de (papel, funcionario) no Mapa. Atribuição
    projeto-inteiro (pool_ambiente_id NULL) → TODOS os ambientes do projeto."""
    atrs = (db.query(AtribuicaoAmbiente)
            .filter_by(projeto_nome=projeto_nome, papel=papel, funcionario_id=funcionario_id).all())
    if not atrs:
        return []
    if any(a.pool_ambiente_id is None for a in atrs):     # projeto inteiro
        return db.query(PoolAmbiente).filter_by(projeto_id=projeto_nome).all()
    ids = {a.pool_ambiente_id for a in atrs if a.pool_ambiente_id}
    return db.query(PoolAmbiente).filter(PoolAmbiente.id.in_(ids)).all() if ids else []


def _breakdown_projeto(db, projeto_nome):
    """(breakdown do orçamento vencedor via mod_negociacao, [pool_ambiente_id por índice]).
    Espelha main._negociacao_breakdown (lê só os insumos salvos) para obter o VAVA POR AMBIENTE,
    VAVO e Val_Liq — respeitando o toggle 'incluir_custos'. (None, []) se não há orçamento."""
    import mod_negociacao, mod_provisoes, mod_orcamento_params
    from database import Loja, Projeto, OrcamentoAmbiente
    orcs = db.query(Orcamento).filter_by(projeto_id=projeto_nome).all()
    if not orcs:
        return None, []
    orc = max(orcs, key=lambda o: (o.valor_liquido or o.valor_total or 0.0))
    proj = db.query(Projeto).filter_by(nome_safe=projeto_nome).first()
    loja = db.get(Loja, orc.loja_id) if getattr(orc, "loja_id", None) else None
    cfg = {}
    if loja and loja.config_financeira_json:
        try:
            cfg = json.loads(loja.config_financeira_json)
        except Exception:
            cfg = {}
    if not cfg:
        cfg = mod_provisoes.config_financeira_default()
    params = (json.loads(proj.parametros_json) if (proj and proj.parametros_json)
              else mod_orcamento_params.parametros_default_loja(cfg))
    desc_orc = orc.desconto_pct or 0.0
    ambs, ids = [], []
    for lk in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all():
        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
        if pa:
            ambs.append({"VBVA": pa.budget_total or 0.0, "CFA": pa.order_total or 0.0,
                         "desc_amb_pct": float(lk.desconto_individual_pct or 0.0)})
            ids.append(lk.pool_ambiente_id)
    total_cliente = None
    try:
        fp = json.loads(orc.forma_pagamento) if orc.forma_pagamento else None
        if isinstance(fp, dict) and fp.get("total_cliente"):
            total_cliente = float(fp["total_cliente"])
    except Exception:
        total_cliente = None
    pool_proj = db.query(PoolAmbiente).filter_by(projeto_id=projeto_nome).all()
    n_total_proj = len(pool_proj) or None
    vbvo_proj = sum((pa.budget_total or 0.0) for pa in pool_proj) or None
    d0 = mod_negociacao.calcular_orcamento(ambs, params, desc_orc,
                                           n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    cust_fin = 0.0 if total_cliente is None else max(0.0, total_cliente - d0["VAVO"])
    d = mod_negociacao.calcular_orcamento(ambs, params, desc_orc, cust_fin=cust_fin,
                                          n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    return d, ids


def _liquidos_por_ambiente(db, projeto_nome):
    """{pool_ambiente_id: Val_Liq_Amb}, onde Val_Liq_Amb = VAVA − Cust_Ad × (VAVA/VAVO), isto é, o VAVA
    do ambiente menos a fatia (proporcional ao VAVA) dos custos adicionais. Σ = Val_Liq do projeto."""
    d, ids = _breakdown_projeto(db, projeto_nome)
    if not d:
        return {}
    vavo = d.get("VAVO") or 0.0
    val_liq = d.get("Val_Liq") or 0.0
    fator = (val_liq / vavo) if vavo > 0 else 0.0     # (VAVO − Cust_Ad)/VAVO
    out = {}
    for i, a in enumerate(d.get("ambientes", [])):
        aid = ids[i] if i < len(ids) else None
        if aid is not None:
            out[aid] = round(float(a.get("VAVA") or 0.0) * fator, 2)
    return out


def base_ambientes(db, projeto_nome, papel, funcionario_id):
    """Base = Σ do Valor Líquido POR AMBIENTE (VAVA − fatia dos custos adicionais) dos ambientes
    atribuídos a (papel, funcionario). Projeto inteiro → base = Val_Liq do projeto."""
    pools = _ambientes_da_base(db, projeto_nome, papel, funcionario_id)
    if not pools:
        return 0.0
    liq = _liquidos_por_ambiente(db, projeto_nome)
    return round(sum(liq.get(p.id, 0.0) for p in pools), 2)


def base_detalhe(db, item):
    """Composição da base de um item de comissão:
    - venda (Consultor): sem detalhe — o item JÁ é um projeto/contrato só (2026-08-12, fonte
      única: um item por venda, valendo o saldo da provisão daquele contrato específico);
    - papel: por ambiente atribuído (Valor Líquido de cada ambiente)."""
    if item.origem == "venda":
        return []
    if item.origem != "papel" or not item.projeto_nome or not item.papel:
        return []
    pools = _ambientes_da_base(db, item.projeto_nome, item.papel, item.funcionario_id)
    if not pools:
        return []
    liq = _liquidos_por_ambiente(db, item.projeto_nome)
    return [{"nome": p.nome_exibicao, "valor": round(liq.get(p.id, 0.0), 2)} for p in pools]


def _pct_funcao(funcao, base):
    if not funcao or not funcao.comissao_json:
        return 0.0
    try:
        com = json.loads(funcao.comissao_json)
    except (ValueError, TypeError):
        return 0.0
    return mod_folha._resolver_pct_funcao(com, base)


def _executores_do_papel(db, projeto_nome, papel):
    """funcionario_ids DISTINTOS atribuídos a esse papel no Mapa (atribuicoes_ambiente)."""
    rows = (db.query(AtribuicaoAmbiente.funcionario_id)
            .filter_by(projeto_nome=projeto_nome, papel=papel)
            .filter(AtribuicaoAmbiente.funcionario_id.isnot(None)).all())
    out = []
    for (fid,) in rows:
        if fid not in out:
            out.append(fid)
    return out


def preparar_comissao_etapa(db, loja_id, etapa):
    """Prepara a(s) comissão(ões) do(s) executor(es) da etapa concluída. O(s) executor(es) vêm do MAPA
    de Atribuições (atribuicoes_ambiente) por papel; se o Mapa estiver vazio, cai no
    responsavel_funcionario_id da etapa. A função (e o % da comissão) vem do próprio Funcionário.
    Idempotente por ref_etapa. Retorna o 1º item criado, ou None."""
    papel = papel_da_etapa(etapa.etapa_codigo)
    if not papel or not etapa.concluido_em:
        return None
    execs = _executores_do_papel(db, etapa.projeto_nome, papel)
    if not execs and etapa.responsavel_funcionario_id:
        execs = [etapa.responsavel_funcionario_id]
    comp = etapa.concluido_em.strftime("%Y-%m")
    itens = []
    for func_id in execs:
        f = db.get(Funcionario, func_id)
        funcao = db.get(Funcao, f.funcao_id) if (f and f.funcao_id) else None
        base = base_ambientes(db, etapa.projeto_nome, papel, func_id)
        pct = _pct_funcao(funcao, base)
        if pct <= 0:                    # função do executor sem comissão → sem item
            continue
        # ACHADO-47 (DECIDIDO 02/09) — Adicional de comissão: soma sobre a comissão da função
        # PRIMÁRIA (aqui já confirmada > 0, pela checagem acima) e provisiona JUNTO — mesmo
        # item, mesmo alimentador, sem rubrica nova. A guarda "função já comissionada" é a
        # própria condição `pct <= 0` logo acima: só chega aqui quem já tem comissão de papel.
        pct_efetivo = pct + float(getattr(f, "adicional_comissao_pct", 0.0) or 0.0)
        ref = "%s:%s:%d" % (etapa.projeto_nome, etapa.etapa_codigo, func_id)
        item = db.query(ComissaoFolha).filter_by(ref_etapa=ref).first()
        if item is None:
            item = ComissaoFolha(loja_id=loja_id, funcionario_id=func_id, origem="papel", papel=papel,
                                 projeto_nome=etapa.projeto_nome, etapa_codigo=etapa.etapa_codigo, ref_etapa=ref)
            db.add(item)
        if item.status == "confirmado":     # já foi para folha paga — não recalcula
            itens.append(item); continue
        base_ef = item.base_ajustada if item.base_ajustada is not None else base
        item.competencia = comp; item.base = base; item.pct = pct_efetivo
        item.valor = round(float(base_ef) * pct_efetivo / 100.0, 2); item.status = "previsto"
        db.flush()
        itens.append(item)
    return itens[0] if itens else None


def cancelar_comissao_etapa(db, projeto_nome, etapa_codigo, funcionario_id):
    """Cancela o item (reabertura de etapa), se não confirmado (folha não paga)."""
    ref = "%s:%s:%d" % (projeto_nome, etapa_codigo, funcionario_id)
    item = db.query(ComissaoFolha).filter_by(ref_etapa=ref).first()
    if item and item.status != "confirmado":
        item.status = "cancelado"; db.flush()
    return item


_NAO_INFORMADO = object()   # sentinela: distingue "campo ausente do request" de "None explícito"


def editar_item(db, item, base_ajustada=_NAO_INFORMADO, pct_ajustado=_NAO_INFORMADO):
    """Override manual da base e/ou do % de um item (status != confirmado) e recalcula o valor
    (achado do usuário 2026-08-17: pra venda, editar SÓ a base não bastava mais — o % também
    precisa ser ajustável no ato do pagamento). Cada parâmetro só é tocado se vier explicitamente
    (`_NAO_INFORMADO` = não mexe; `None` = limpa o override e volta ao valor do sistema)."""
    if item.status == "confirmado":
        return False, "comissão já confirmada"
    if base_ajustada is not _NAO_INFORMADO:
        item.base_ajustada = float(base_ajustada) if base_ajustada is not None else None
    if pct_ajustado is not _NAO_INFORMADO:
        item.pct_ajustado = float(pct_ajustado) if pct_ajustado is not None else None
    if item.origem == "venda" and item.projeto_nome:
        import mod_contabil
        ot, oid = mod_contabil.resolver_owner(db, {"loja_id": item.loja_id, "rede_id": None})
        valor_sistema = mod_folha.saldo_provisao_venda(db, ot, oid, item.projeto_nome)
    else:
        valor_sistema = round(float(item.base or 0.0) * float(item.pct or 0.0) / 100.0, 2)
    mod_folha._recalcular_valor_item(item, valor_sistema)
    db.flush()
    return True, None
