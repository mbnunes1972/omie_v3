# -*- coding: utf-8 -*-
"""mod_retido.py — Desmembramento OPERACIONAL: ambientes retidos pela obra (Fatia 1).

Spec: docs/superpowers/specs/ciclo/2026-07-27-desmembramento-operacional-desde-medicao-design.md.

Fluxo: o MEDIDOR sinaliza ambientes retidos pela obra (por AMBIENTE — SinalRetido); a GERÊNCIA
confirma → cria as parcelas (PRONTA que segue × RETIDA que aguarda), reusando as regras puras de
`mod_parcelas` (particionar_por_selecao + congelar_parcelas). NÃO toca no razão contábil (é a Fatia 4).
A parcela retida nasce `status='retido'`; ao liberar (Fatia 3) volta a `'aguardando'`.
"""
import json
from datetime import datetime

import mod_parcelas
from database import (CicloLogistico, ParcelaAmbiente, ParcelaProjeto, PoolAmbiente,
                      RetencaoObra, SinalRetido)

STATUS_RETIDO = "retido"


def sinalizar(db, projeto_nome, pool_ambiente_ids, medidor_id, motivo=None):
    """Marca ambientes como retidos (upsert; NÃO confirmado). Ignora ids fora do pool do projeto.
    Não commita. Retorna a lista de ids efetivamente marcados."""
    validos = {p.id for p in db.query(PoolAmbiente).filter_by(projeto_id=projeto_nome).all()}
    marcados = []
    for aid in (pool_ambiente_ids or []):
        try:
            aid = int(aid)
        except (TypeError, ValueError):
            continue
        if aid not in validos:
            continue
        s = (db.query(SinalRetido)
               .filter_by(projeto_nome=projeto_nome, pool_ambiente_id=aid).first())
        if s is None:
            db.add(SinalRetido(projeto_nome=projeto_nome, pool_ambiente_id=aid,
                               sinalizado_por_id=medidor_id, motivo=motivo, confirmado=0))
        elif not s.confirmado:
            s.sinalizado_por_id = medidor_id
            if motivo is not None:
                s.motivo = motivo
        marcados.append(aid)
    db.flush()
    return marcados


def limpar_sinal(db, projeto_nome, pool_ambiente_id):
    """Remove um sinal AINDA NÃO confirmado (o medidor desmarca). Retorna True se removeu."""
    s = (db.query(SinalRetido)
           .filter_by(projeto_nome=projeto_nome, pool_ambiente_id=int(pool_ambiente_id),
                      confirmado=0).first())
    if s is None:
        return False
    db.delete(s); db.flush()
    return True


def listar_sinais(db, projeto_nome, confirmado=0):
    return [{"pool_ambiente_id": s.pool_ambiente_id, "motivo": s.motivo,
             "sinalizado_por_id": s.sinalizado_por_id}
            for s in db.query(SinalRetido)
                       .filter_by(projeto_nome=projeto_nome, confirmado=confirmado).all()]


def ja_desmembrado(db, projeto_nome):
    return db.query(ParcelaProjeto).filter_by(projeto_nome=projeto_nome).first() is not None


def confirmar(db, projeto_nome, orcamento_id, valores_por_ambiente, val_cont, criado_por_id,
              liquidos_por_ambiente=None, val_liq=0.0):
    """Gerência confirma o desmembramento: parcela PRONTA (segue) × RETIDA (aguarda obra). Reusa
    mod_parcelas (partição + congelamento do val_cont — e do val_liq, Agenda Fatia 1). NÃO toca
    no razão. Não commita. Retorna (ok, erro, parcelas)."""
    if ja_desmembrado(db, projeto_nome):
        return (False, "Projeto já desmembrado.", None)
    sinais = db.query(SinalRetido).filter_by(projeto_nome=projeto_nome, confirmado=0).all()
    retido_ids = [s.pool_ambiente_id for s in sinais]
    if not retido_ids:
        return (False, "Nenhum ambiente sinalizado como retido.", None)
    pool_ids = list(valores_por_ambiente.keys())
    ok, erro, retidos, prontos = mod_parcelas.particionar_por_selecao(pool_ids, retido_ids)
    if not ok:
        return (False, erro, None)             # ex.: todos retidos → nada a desmembrar
    liq = liquidos_por_ambiente or {}
    grupos = [prontos, retidos]                # ordem 1 = pronta (segue); ordem 2 = retida
    grupos_valores = [[float(valores_por_ambiente.get(aid, 0.0)) for aid in g] for g in grupos]
    congeladas = mod_parcelas.congelar_parcelas(grupos_valores, val_cont)
    cong_liq = mod_parcelas.congelar_parcelas(
        [[float(liq.get(aid, 0.0)) for aid in g] for g in grupos], val_liq)
    parcelas = []
    for i, (grupo, cong, status) in enumerate(zip(grupos, congeladas, ["aguardando", STATUS_RETIDO])):
        p = ParcelaProjeto(projeto_nome=projeto_nome, ordem=cong["ordem"], status=status,
                           fracao_val_cont=cong["fracao_val_cont"],
                           val_cont_congelado=cong["val_cont_congelado"],
                           val_liq_congelado=cong_liq[i]["val_cont_congelado"],
                           orcamento_id=orcamento_id, criado_por_id=criado_por_id)
        db.add(p); db.flush()
        for aid in grupo:
            db.add(ParcelaAmbiente(parcela_id=p.id, pool_ambiente_id=aid,
                                   valor_ambiente=float(valores_por_ambiente.get(aid, 0.0))))
        parcelas.append({"id": p.id, "ordem": p.ordem, "status": status,
                         "val_cont_congelado": p.val_cont_congelado, "ambientes": grupo})
    for s in sinais:
        s.confirmado = 1
    db.flush()
    return (True, None, parcelas)


# ── Retenção RECORRENTE (decisão 2026-08-02): evento direto, em qualquer etapa 9→17 ─────────────
# A retenção deixa de ser um ato único da Medição: pode ser acionada na Solicitação de Medição,
# na Medição, no PE e durante a Montagem — VÁRIAS vezes. Cada evento é registrado em
# `RetencaoObra` (quando, etapa do ciclo, ambientes, motivo, data prevista de liberação).

# Catálogo de motivos (rev 2026-08-03 — auditoria): o SELETOR do modal; a descrição livre do
# fato vai em `motivo` (detalhe). "Outros" cobre o que não se encaixa.
MOTIVOS_RETENCAO = ["Atraso da Obra", "Aprovação do Arquiteto", "Aprovação do Cliente",
                    "Financeiro", "Definição de Projeto", "Fábrica", "Outros"]


def reter(db, projeto_nome, amb_ids, orcamento_id, valores_por_ambiente, val_cont,
          criado_por_id, motivo=None, liberacao_prevista=None, etapa_codigo=None,
          liquidos_por_ambiente=None, val_liq=0.0, motivo_tipo=None):
    """Retenção DIRETA de ambientes (gerência), em cima do estado atual das fases.

    - Projeto NÃO desmembrado: cria [fase que segue, fase retida] (retida por último; se TODOS
      os ambientes forem retidos, nasce uma fase única retida).
    - Projeto desmembrado: para cada fase afetada — se todos os seus ambientes foram
      selecionados, a fase inteira vira `retido`; senão SPLIT (a fase original segue com o
      resto, a nova fase retida vai para o fim), preservando exatamente os congelados da mãe
      (mod_parcelas.desmembrar_fase). Fase liquidada ou já em expedição não pode ser retida.
    - Grava `liberacao_prevista` nas fases retidas, marca sinais pendentes como confirmados e
      registra o evento em RetencaoObra. Não commita. Retorna (ok, erro, resumo).
    """
    pedidos = set()
    for aid in (amb_ids or []):
        try:
            pedidos.add(int(aid))
        except (TypeError, ValueError):
            continue
    validos = {p.id for p in db.query(PoolAmbiente).filter_by(projeto_id=projeto_nome).all()}
    pedidos &= validos
    if not pedidos:
        return (False, "Nenhum ambiente válido informado.", None)
    ja_retidos = pedidos & ambientes_retidos(db, projeto_nome)
    if ja_retidos:
        return (False, "Ambiente(s) já retido(s): %s." % ", ".join(str(x) for x in sorted(ja_retidos)), None)

    liq = liquidos_por_ambiente or {}
    afetadas = []
    if not ja_desmembrado(db, projeto_nome):
        prontos = sorted(set(valores_por_ambiente.keys()) - pedidos)
        retidos = sorted(pedidos)
        grupos = ([prontos, retidos] if prontos else [retidos])
        grupos_valores = [[float(valores_por_ambiente.get(a, 0.0)) for a in g] for g in grupos]
        congeladas = mod_parcelas.congelar_parcelas(grupos_valores, val_cont)
        # Agenda Fatia 1: congela também o Val_Liq (mesma partição, Σ exata)
        cong_liq = mod_parcelas.congelar_parcelas(
            [[float(liq.get(a, 0.0)) for a in g] for g in grupos], val_liq)
        for i, (grupo, cong) in enumerate(zip(grupos, congeladas)):
            eh_retida = (grupo is retidos)
            p = ParcelaProjeto(projeto_nome=projeto_nome, ordem=cong["ordem"],
                               status=(STATUS_RETIDO if eh_retida else "aguardando"),
                               fracao_val_cont=cong["fracao_val_cont"],
                               val_cont_congelado=cong["val_cont_congelado"],
                               val_liq_congelado=cong_liq[i]["val_cont_congelado"],
                               orcamento_id=orcamento_id, criado_por_id=criado_por_id,
                               liberacao_prevista=(liberacao_prevista if eh_retida else None))
            db.add(p); db.flush()
            for aid in grupo:
                db.add(ParcelaAmbiente(parcela_id=p.id, pool_ambiente_id=aid,
                                       valor_ambiente=float(valores_por_ambiente.get(aid, 0.0))))
            afetadas.append({"id": p.id, "ordem": p.ordem, "status": p.status,
                             "val_cont_congelado": p.val_cont_congelado, "ambientes": grupo})
    else:
        fases = (db.query(ParcelaProjeto).filter_by(projeto_nome=projeto_nome)
                   .order_by(ParcelaProjeto.ordem.asc()).all())
        for fase in fases:
            membros = db.query(ParcelaAmbiente).filter_by(parcela_id=fase.id).all()
            ids_fase = {m.pool_ambiente_id for m in membros}
            sel = pedidos & ids_fase
            if not sel:
                continue
            if fase.status == "liquidada":
                return (False, "Fase %d já liquidada — não pode ser retida." % fase.ordem, None)
            if db.query(CicloLogistico).filter_by(projeto_nome=projeto_nome,
                                                  parcela_id=fase.id).first():
                return (False, "Fase %d já em expedição — não pode ser retida." % fase.ordem, None)
            if sel == ids_fase:
                fase.status = STATUS_RETIDO
                fase.liberacao_prevista = liberacao_prevista
                afetadas.append({"id": fase.id, "ordem": fase.ordem, "status": STATUS_RETIDO,
                                 "val_cont_congelado": fase.val_cont_congelado,
                                 "ambientes": sorted(ids_fase)})
                continue
            # SPLIT: a fase original segue com o resto; a retida (nova) vai para o fim.
            resto = sorted(ids_fase - sel)
            sel_ord = sorted(sel)
            ok, erro, novas = mod_parcelas.desmembrar_fase(
                sorted(ids_fase), [resto, sel_ord], fase.val_cont_congelado,
                fase.fracao_val_cont, valores_por_ambiente)
            if not ok:
                return (False, erro, None)
            # Agenda Fatia 1: reparte também o Val_Liq congelado (mãe legada → rateio atual)
            mae_liq = (fase.val_liq_congelado if fase.val_liq_congelado is not None
                       else round(sum(float(liq.get(a, 0.0)) for a in ids_fase), 2))
            _okl, _errl, novas_liq = mod_parcelas.desmembrar_fase(
                sorted(ids_fase), [resto, sel_ord], mae_liq, 0.0, liq)
            nova_ordem = (db.query(ParcelaProjeto)
                            .filter_by(projeto_nome=projeto_nome).count()) + 1
            r = ParcelaProjeto(projeto_nome=projeto_nome, ordem=nova_ordem, status=STATUS_RETIDO,
                               fracao_val_cont=novas[1]["fracao_val_cont"],
                               val_cont_congelado=novas[1]["val_cont_congelado"],
                               val_liq_congelado=novas_liq[1]["val_cont_congelado"],
                               orcamento_id=fase.orcamento_id, criado_por_id=criado_por_id,
                               liberacao_prevista=liberacao_prevista,
                               entrega_prevista=fase.entrega_prevista)
            db.add(r); db.flush()
            fase.fracao_val_cont = novas[0]["fracao_val_cont"]
            fase.val_cont_congelado = novas[0]["val_cont_congelado"]
            fase.val_liq_congelado = novas_liq[0]["val_cont_congelado"]
            for m in membros:
                m.valor_ambiente = float(valores_por_ambiente.get(m.pool_ambiente_id,
                                                                  m.valor_ambiente or 0.0))
                if m.pool_ambiente_id in sel:
                    m.parcela_id = r.id
            afetadas.append({"id": fase.id, "ordem": fase.ordem, "status": fase.status,
                             "val_cont_congelado": fase.val_cont_congelado, "ambientes": resto})
            afetadas.append({"id": r.id, "ordem": r.ordem, "status": STATUS_RETIDO,
                             "val_cont_congelado": r.val_cont_congelado, "ambientes": sel_ord})

    # sinais pendentes dos ambientes retidos ficam confirmados (integração com o fluxo do medidor)
    for s in db.query(SinalRetido).filter_by(projeto_nome=projeto_nome, confirmado=0).all():
        if s.pool_ambiente_id in pedidos:
            s.confirmado = 1
    reg = RetencaoObra(projeto_nome=projeto_nome, etapa_codigo=etapa_codigo,
                       motivo_tipo=motivo_tipo, motivo=motivo,
                       liberacao_prevista=liberacao_prevista,
                       ambientes_json=json.dumps(sorted(pedidos)),
                       criado_por_id=criado_por_id)
    db.add(reg); db.flush()
    return (True, None, {"registro_id": reg.id, "parcelas": afetadas})


def listar_retencoes(db, projeto_nome):
    """Histórico de eventos de retenção (mais recente primeiro), com os ids de ambientes."""
    out = []
    for r in (db.query(RetencaoObra).filter_by(projeto_nome=projeto_nome)
                .order_by(RetencaoObra.id.desc()).all()):
        try:
            ambs = json.loads(r.ambientes_json or "[]")
        except ValueError:
            ambs = []
        out.append({"id": r.id, "etapa_codigo": r.etapa_codigo,
                    "motivo_tipo": r.motivo_tipo, "motivo": r.motivo,
                    "liberacao_prevista": r.liberacao_prevista.isoformat() if r.liberacao_prevista else None,
                    "criado_em": r.criado_em.isoformat() if r.criado_em else None,
                    "liberado_em": r.liberado_em.isoformat() if r.liberado_em else None,
                    "ambientes": ambs})
    return out


def estampar_liberacoes(db, projeto_nome, liberado_por_id=None, agora=None):
    """Fecha os registros de retenção cujos ambientes JÁ não estão mais retidos (liberação em
    ondas: o registro fecha quando o ÚLTIMO ambiente dele sai de fase retida). Não commita."""
    retidos = ambientes_retidos(db, projeto_nome)
    abertos = (db.query(RetencaoObra)
                 .filter_by(projeto_nome=projeto_nome, liberado_em=None).all())
    fechados = []
    for r in abertos:
        try:
            ambs = set(json.loads(r.ambientes_json or "[]"))
        except ValueError:
            ambs = set()
        if ambs and not (ambs & retidos):
            r.liberado_em = agora or datetime.utcnow()
            r.liberado_por_id = liberado_por_id
            fechados.append(r.id)
    db.flush()
    return fechados


# ── Fatia 2: gate operacional por parcela (parcela retida NÃO avança) ────────────────────────────
# O status operacional segue por PARCELA (ParcelaProjeto.status). Uma parcela `retido` fica FORA do
# fluxo de execução — nenhuma operação por ambiente (PE, etc.) roda nos seus ambientes até a obra
# liberar (Fatia 3). Ambiente sem parcela (legado / não desmembrado) ou em parcela que segue ⇒ livre.

def parcela_do_ambiente(db, projeto_nome, pool_ambiente_id):
    """A ParcelaProjeto que contém o ambiente (via ParcelaAmbiente), ou None (legado/não desmembrado)."""
    return (db.query(ParcelaProjeto)
              .join(ParcelaAmbiente, ParcelaAmbiente.parcela_id == ParcelaProjeto.id)
              .filter(ParcelaProjeto.projeto_nome == projeto_nome,
                      ParcelaAmbiente.pool_ambiente_id == int(pool_ambiente_id))
              .first())


def ambiente_retido(db, projeto_nome, pool_ambiente_id):
    """True se o ambiente está numa parcela RETIDA (a obra ainda não liberou)."""
    p = parcela_do_ambiente(db, projeto_nome, pool_ambiente_id)
    return bool(p is not None and p.status == STATUS_RETIDO)


def ambientes_retidos(db, projeto_nome):
    """Conjunto de pool_ambiente_id em parcelas retidas do projeto."""
    q = (db.query(ParcelaAmbiente.pool_ambiente_id)
           .join(ParcelaProjeto, ParcelaProjeto.id == ParcelaAmbiente.parcela_id)
           .filter(ParcelaProjeto.projeto_nome == projeto_nome,
                   ParcelaProjeto.status == STATUS_RETIDO))
    return {r[0] for r in q.all()}


def gate_operacao_ambiente(db, projeto_nome, pool_ambiente_id):
    """Gate de execução por parcela: bloqueia operação sobre ambiente de parcela RETIDA (obra não
    liberou). Retorna (ok, erro). Legado/não desmembrado/parcela que segue ⇒ (True, None)."""
    if ambiente_retido(db, projeto_nome, pool_ambiente_id):
        return (False, "Ambiente retido pela obra: a parcela aguarda liberação para executar.")
    return (True, None)


# ── Fatia 3: liberação / continuação de onde parou (a obra libera, em ondas) ─────────────────────

def _split_fracao(fracao_pai, valor_pai, valor_filho):
    """Fração do FILHO relativa ao projeto, proporcional ao pai (Σ filhos == fração do pai)."""
    if not valor_pai:
        return 0.0
    return round(float(fracao_pai) * float(valor_filho) / float(valor_pai), 6)


def liberar(db, projeto_nome, pool_ambiente_ids, liberado_por_id=None):
    """Obra LIBERA ambientes retidos → a parcela retoma o ciclo (`retido` → `aguardando`,
    continuação de onde parou — decisão #4). Se a obra libera só PARTE de uma parcela retida
    (ondas), faz SPLIT: os liberados viram uma parcela `aguardando`, o restante fica `retido`.
    Reusa `mod_parcelas.congelar_parcelas` para manter `Σ val_cont_congelado` exato ao centavo.
    NÃO toca no razão. Não commita. Retorna (ok, erro, parcelas_afetadas)."""
    pedidos = set()
    for aid in (pool_ambiente_ids or []):
        try:
            pedidos.add(int(aid))
        except (TypeError, ValueError):
            continue
    if not pedidos:
        return (False, "Nenhum ambiente informado.", None)

    retidas = (db.query(ParcelaProjeto)
                 .filter_by(projeto_nome=projeto_nome, status=STATUS_RETIDO).all())
    afetadas = []
    tratou_algum = False
    for parc in retidas:
        membros = db.query(ParcelaAmbiente).filter_by(parcela_id=parc.id).all()
        ids_parc = {m.pool_ambiente_id for m in membros}
        libs = pedidos & ids_parc
        if not libs:
            continue
        tratou_algum = True
        resto = ids_parc - libs
        if not resto:
            # Liberação TOTAL da parcela — retoma sem repartir.
            parc.status = "aguardando"
            parc.liberacao_prevista = None
            afetadas.append({"id": parc.id, "status": "aguardando",
                             "val_cont_congelado": parc.val_cont_congelado,
                             "ambientes": sorted(ids_parc)})
            continue
        # Liberação PARCIAL → split. Ordena membros: liberados primeiro, resto depois.
        por_amb = {m.pool_ambiente_id: (m.valor_ambiente or 0.0) for m in membros}
        libs_ord, resto_ord = sorted(libs), sorted(resto)
        cong = mod_parcelas.congelar_parcelas(
            [[por_amb[a] for a in libs_ord], [por_amb[a] for a in resto_ord]],
            parc.val_cont_congelado)
        v_lib, v_resto = cong[0]["val_cont_congelado"], cong[1]["val_cont_congelado"]
        fr_lib = _split_fracao(parc.fracao_val_cont, parc.val_cont_congelado, v_lib)
        # Agenda Fatia 1: Val_Liq congelado acompanha o split na MESMA proporção do Val_Cont
        # (última fatia absorve o resíduo). Mãe legada sem o campo → segue None (backfill cobre).
        if parc.val_liq_congelado is not None and (parc.val_cont_congelado or 0) > 0:
            liq_lib = round(parc.val_liq_congelado * v_lib / parc.val_cont_congelado, 2)
            liq_resto = round(parc.val_liq_congelado - liq_lib, 2)
        else:
            liq_lib = liq_resto = None
        # A parcela existente vira a LIBERADA (segue); cria uma nova RETIDA para o resto.
        nova_ordem = (db.query(ParcelaProjeto)
                        .filter_by(projeto_nome=projeto_nome).count()) + 1
        r = ParcelaProjeto(projeto_nome=projeto_nome, ordem=nova_ordem, status=STATUS_RETIDO,
                           fracao_val_cont=round((parc.fracao_val_cont or 0.0) - fr_lib, 6),
                           val_cont_congelado=v_resto, orcamento_id=parc.orcamento_id,
                           criado_por_id=liberado_por_id,
                           liberacao_prevista=parc.liberacao_prevista,
                           entrega_prevista=parc.entrega_prevista,
                           val_liq_congelado=liq_resto)
        db.add(r); db.flush()
        for m in membros:
            if m.pool_ambiente_id in resto:
                m.parcela_id = r.id
        parc.status = "aguardando"
        parc.liberacao_prevista = None
        parc.fracao_val_cont = fr_lib
        parc.val_cont_congelado = v_lib
        parc.val_liq_congelado = liq_lib
        db.flush()
        afetadas.append({"id": parc.id, "status": "aguardando", "val_cont_congelado": v_lib,
                         "ambientes": libs_ord})
        afetadas.append({"id": r.id, "status": STATUS_RETIDO, "val_cont_congelado": v_resto,
                         "ambientes": resto_ord})
    if not tratou_algum:
        return (False, "Nenhum ambiente retido entre os informados.", None)
    db.flush()
    return (True, None, afetadas)


# ── Fatia 4: reconhecimento contábil dirigido pela execução (retida fica DIFERIDA) ───────────────

def fracao_reconhecivel(db, projeto_nome):
    """Fração do projeto ELEGÍVEL a reconhecimento contábil na NF-e = parcelas que NÃO estão
    retidas (`Σ val_cont_congelado das não-retidas / Σ de todas`, exato por #5). A parcela retida
    fica DIFERIDA (segue como ativo diferido 1.1.06 até liberar). Retorna None se o projeto não
    foi desmembrado → o chamador reconhece o projeto inteiro (comportamento legado intacto)."""
    parts = (db.query(ParcelaProjeto).filter_by(projeto_nome=projeto_nome)
               .order_by(ParcelaProjeto.id.asc()).all())   # ordem fixa → soma float determinística
    if not parts:
        return None
    total = round(sum(p.val_cont_congelado or 0.0 for p in parts), 2)
    if total <= 0:
        return 0.0
    disp = round(sum(p.val_cont_congelado or 0.0 for p in parts if p.status != STATUS_RETIDO), 2)
    return round(disp / total, 6)
