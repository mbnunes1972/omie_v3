# -*- coding: utf-8 -*-
"""mod_retido.py — Desmembramento OPERACIONAL: ambientes retidos pela obra (Fatia 1).

Spec: docs/superpowers/specs/ciclo/2026-07-27-desmembramento-operacional-desde-medicao-design.md.

Fluxo: o MEDIDOR sinaliza ambientes retidos pela obra (por AMBIENTE — SinalRetido); a GERÊNCIA
confirma → cria as parcelas (PRONTA que segue × RETIDA que aguarda), reusando as regras puras de
`mod_parcelas` (particionar_por_selecao + congelar_parcelas). NÃO toca no razão contábil (é a Fatia 4).
A parcela retida nasce `status='retido'`; ao liberar (Fatia 3) volta a `'aguardando'`.
"""
import mod_parcelas
from database import SinalRetido, ParcelaProjeto, ParcelaAmbiente, PoolAmbiente

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


def confirmar(db, projeto_nome, orcamento_id, valores_por_ambiente, val_cont, criado_por_id):
    """Gerência confirma o desmembramento: parcela PRONTA (segue) × RETIDA (aguarda obra). Reusa
    mod_parcelas (partição + congelamento do val_cont). NÃO toca no razão. Não commita.
    Retorna (ok, erro, parcelas)."""
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
    grupos = [prontos, retidos]                # ordem 1 = pronta (segue); ordem 2 = retida
    grupos_valores = [[float(valores_por_ambiente.get(aid, 0.0)) for aid in g] for g in grupos]
    congeladas = mod_parcelas.congelar_parcelas(grupos_valores, val_cont)
    parcelas = []
    for grupo, cong, status in zip(grupos, congeladas, ["aguardando", STATUS_RETIDO]):
        p = ParcelaProjeto(projeto_nome=projeto_nome, ordem=cong["ordem"], status=status,
                           fracao_val_cont=cong["fracao_val_cont"],
                           val_cont_congelado=cong["val_cont_congelado"],
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
        # A parcela existente vira a LIBERADA (segue); cria uma nova RETIDA para o resto.
        nova_ordem = (db.query(ParcelaProjeto)
                        .filter_by(projeto_nome=projeto_nome).count()) + 1
        r = ParcelaProjeto(projeto_nome=projeto_nome, ordem=nova_ordem, status=STATUS_RETIDO,
                           fracao_val_cont=round((parc.fracao_val_cont or 0.0) - fr_lib, 6),
                           val_cont_congelado=v_resto, orcamento_id=parc.orcamento_id,
                           criado_por_id=liberado_por_id)
        db.add(r); db.flush()
        for m in membros:
            if m.pool_ambiente_id in resto:
                m.parcela_id = r.id
        parc.status = "aguardando"
        parc.fracao_val_cont = fr_lib
        parc.val_cont_congelado = v_lib
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
    parts = db.query(ParcelaProjeto).filter_by(projeto_nome=projeto_nome).all()
    if not parts:
        return None
    total = round(sum(p.val_cont_congelado or 0.0 for p in parts), 2)
    if total <= 0:
        return 0.0
    disp = round(sum(p.val_cont_congelado or 0.0 for p in parts if p.status != STATUS_RETIDO), 2)
    return round(disp / total, 6)
