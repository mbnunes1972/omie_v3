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
            db.add(ParcelaAmbiente(parcela_id=p.id, pool_ambiente_id=aid))
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
