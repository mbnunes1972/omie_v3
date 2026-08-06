"""mod_assistencias.py — módulo de domínio Assistências (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6).

Atendimento pós-execução com DUAS dimensões independentes por caso:
  - sub_tipo: Assistência Montagem × Assistência Pós-Conclusão
  - tipo_custo: Paga (cliente) · Loja · Fábrica — DERIVADO do motivo (tabela abaixo)

Realizar um caso dispara o lançamento contábil (motor v7 §6):
  Loja    -> realiza a Provisão de Assistência Técnica (execucao_assistencia)
  Fábrica -> realiza a Provisão de Garantia (execucao_reparo_garantia) + relatório "a cobrar da fábrica"
  Paga    -> gera venda ao cliente (venda_assistencia), sem tocar provisão
"""
from datetime import datetime

import mod_contabil
from database import (AssistenciaCaso, AssistenciaExecutor, AssistenciaAnexo, PoolAmbiente,
                      Funcionario, Terceiro)

SUB_TIPOS = {"montagem": "Assistência Montagem", "pos_conclusao": "Assistência Pós-Conclusão"}

# Funções elegíveis pra executar uma assistência (2026-08-06) — mesmo catálogo que
# mod_escopo.PAPEL_FUNCOES["montagem"], mas COPIADO (não importado): a Assistência tem
# agendamento próprio agora, desacoplado do papel do Mapa (que não existe mais pra ela).
FUNCOES_ELEGIVEIS = ("Montador", "Supervisor de Montagem")

# motivo -> (rótulo, tipo_custo). Tabela do doc (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6).
MOTIVOS = {
    "alteracao_projeto":  ("Alteração de projeto solicitada pelo cliente", "paga"),
    "complemento":        ("Complemento", "paga"),
    "erro_projeto":       ("Erro de projeto", "loja"),
    "erro_montagem":      ("Erro de montagem", "loja"),
    "defeito_fabricacao": ("Defeito de fabricação", "fabrica"),
    "empenamento":        ("Empenamento / mau funcionamento", "fabrica"),
}
TIPO_CUSTO_LABEL = {"paga": "Paga (cliente)", "loja": "Loja", "fabrica": "Fábrica"}

# tipo_custo -> evento contábil (mod_contabil.EVENTOS)
EVENTO_POR_CUSTO = {
    "loja":    "execucao_assistencia",
    "fabrica": "execucao_reparo_garantia",
    "paga":    "venda_assistencia",
}


def tipo_custo_de(motivo):
    m = MOTIVOS.get(motivo)
    return m[1] if m else None


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def criar_caso(db, loja_id, projeto_nome, sub_tipo, motivo, descricao, valor, usuario_id, quando=None,
               pool_ambiente_id=None, data_inicio=None, data_fim=None):
    tc = tipo_custo_de(motivo)
    if sub_tipo not in SUB_TIPOS:
        raise ValueError("sub_tipo inválido")
    if tc is None:
        raise ValueError("motivo inválido")
    if (data_inicio and not data_fim) or (data_fim and not data_inicio):
        raise ValueError("Informe início e fim da janela, ou nenhum dos dois.")
    if data_inicio and data_fim and data_inicio > data_fim:
        raise ValueError("Data de início não pode ser depois da data de fim.")
    caso = AssistenciaCaso(loja_id=loja_id, projeto_nome=(projeto_nome or None), sub_tipo=sub_tipo,
                           motivo=motivo, tipo_custo=tc, descricao=(descricao or None),
                           valor=_num(valor), status="aberto", pool_ambiente_id=pool_ambiente_id,
                           data_inicio=data_inicio, data_fim=data_fim,
                           criado_em=quando or datetime.utcnow(), criado_por_id=usuario_id)
    db.add(caso)
    db.flush()
    return caso


def definir_equipe(db, caso, executores):
    """Substitui a equipe do caso (delete-all + insert-many — mesmo padrão do Montagem
    multi-executor). `executores` = [(tipo, id)], tipo em 'funcionario'|'terceiro'."""
    db.query(AssistenciaExecutor).filter_by(caso_id=caso.id).delete()
    for tipo, oid in executores:
        reg = AssistenciaExecutor(caso_id=caso.id)
        if tipo == "funcionario":
            reg.funcionario_id = oid
        else:
            reg.terceiro_id = oid
        db.add(reg)
    db.flush()


def equipe_do_caso(db, caso_id):
    """[{chave, nome}] da equipe atual do caso."""
    out = []
    for e in db.query(AssistenciaExecutor).filter_by(caso_id=caso_id).all():
        alvo = db.get(Funcionario, e.funcionario_id) if e.funcionario_id else db.get(Terceiro, e.terceiro_id)
        if alvo:
            chave = ("f:%d" % e.funcionario_id) if e.funcionario_id else ("t:%d" % e.terceiro_id)
            out.append({"chave": chave, "nome": alvo.nome})
    return out


def realizar_caso(db, owner_tipo, owner_id, caso, valor=None, quando=None):
    """Executa/conclui o caso: posta o lançamento conforme o tipo de custo e marca 'realizado'.
    Idempotente por ref ('assist:<id>'). Retorna (ok, erro)."""
    if caso.status == "realizado":
        return True, None
    nv = _num(valor)
    if nv is not None:
        caso.valor = nv
    if not caso.valor or caso.valor <= 0:
        return False, "Informe o valor do caso antes de realizar."
    evento = EVENTO_POR_CUSTO[caso.tipo_custo]
    ref = "assist:%d" % caso.id
    motivo = caso.motivo if caso.tipo_custo == "fabrica" else None   # §6.2: motivo carimba o reparo em garantia
    mod_contabil.registrar_evento(db, owner_tipo, owner_id, evento, caso.valor,
                                  projeto_id=caso.projeto_nome, ref=ref, motivo=motivo)
    caso.status = "realizado"
    caso.ref_lancamento = ref
    caso.realizado_em = quando or datetime.utcnow()
    return True, None


def anexos_do_caso(db, caso_id):
    """[{id, nome_original, enviado_em}] do caso, mais recente primeiro."""
    return [{"id": a.id, "nome_original": a.nome_original,
             "enviado_em": a.enviado_em.isoformat() if a.enviado_em else None}
            for a in db.query(AssistenciaAnexo).filter_by(caso_id=caso_id)
                        .order_by(AssistenciaAnexo.id.desc()).all()]


def serialize(db, caso):
    amb = db.get(PoolAmbiente, caso.pool_ambiente_id) if caso.pool_ambiente_id else None
    return {
        "id": caso.id, "projeto_nome": caso.projeto_nome or "",
        "pool_ambiente_id": caso.pool_ambiente_id,
        "ambiente_nome": (amb.nome_exibicao or amb.nome) if amb else "",
        "data_inicio": caso.data_inicio.isoformat() if caso.data_inicio else None,
        "data_fim": caso.data_fim.isoformat() if caso.data_fim else None,
        "equipe": equipe_do_caso(db, caso.id),
        "anexos": anexos_do_caso(db, caso.id),
        "sub_tipo": caso.sub_tipo, "sub_tipo_label": SUB_TIPOS.get(caso.sub_tipo, caso.sub_tipo),
        "motivo": caso.motivo, "motivo_label": (MOTIVOS.get(caso.motivo) or ["", ""])[0],
        "tipo_custo": caso.tipo_custo, "tipo_custo_label": TIPO_CUSTO_LABEL.get(caso.tipo_custo, caso.tipo_custo),
        "descricao": caso.descricao or "", "valor": caso.valor,
        "status": caso.status, "reembolsado_fabrica": bool(caso.reembolsado_fabrica),
    }


def listar(db, loja_id, tipo=None, apenas_abertos=False):
    q = db.query(AssistenciaCaso).filter_by(loja_id=loja_id)
    if tipo in ("paga", "loja", "fabrica"):
        q = q.filter(AssistenciaCaso.tipo_custo == tipo)
    if apenas_abertos:
        q = q.filter(AssistenciaCaso.status == "aberto")
    return [serialize(db, c) for c in q.order_by(AssistenciaCaso.id.desc()).all()]


def a_cobrar_fabrica(db, loja_id):
    """Relatório 'a cobrar da fábrica' (v7 §6.2): casos de tipo Fábrica ainda não reembolsados, com o
    custo real documentado. NÃO é Contas a Receber formal — controle p/ negociação com a fábrica."""
    casos = [c for c in db.query(AssistenciaCaso).filter_by(loja_id=loja_id, tipo_custo="fabrica").all()
             if not c.reembolsado_fabrica]
    return {"total": round(sum(c.valor or 0 for c in casos), 2), "qtd": len(casos),
            "itens": [serialize(db, c) for c in casos]}


def meta():
    return {
        "sub_tipos": [{"id": k, "label": v} for k, v in SUB_TIPOS.items()],
        "motivos": [{"id": k, "label": v[0], "tipo_custo": v[1]} for k, v in MOTIVOS.items()],
        "tipo_custo_label": TIPO_CUSTO_LABEL,
    }
