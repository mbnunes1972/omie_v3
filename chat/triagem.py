# -*- coding: utf-8 -*-
"""chat/triagem.py — resolução humana da FILA DE TRIAGEM (spec
_geral/2026-07-31-triagem-pipeline-entrada-design.md). A persistência da fila acontece em
externo.processar_entrada (idempotente por wamid); aqui vivem a listagem (tenancy por loja)
e as 3 saídas: vincular · criar (lead novo) · descartar (registro, não delete)."""
import json
from datetime import datetime

from database import EnvioExterno, Cliente, Usuario, TriagemEntrada

from .externo import _canal_do_thread, registrar_envio  # noqa: F401  (canal do fio externo)


def serializar_triagem(e):
    return {"id": e.id, "meio": e.meio, "remetente": e.remetente, "texto": e.texto,
            "status": e.status,
            "candidatos": (json.loads(e.candidatos_json) if e.candidatos_json else []),
            "segmento_sugerido": e.segmento_sugerido,
            "conversa_id": e.conversa_id,
            "criado_em": e.criado_em.isoformat() if e.criado_em else None}


def triagem_listar(db, loja_id, status="pendente"):
    """Entradas da fila da LOJA (tenancy), mais antigas primeiro (ordem de chegada)."""
    q = db.query(TriagemEntrada).filter_by(loja_id=loja_id)
    if status:
        q = q.filter(TriagemEntrada.status == status)
    return [serializar_triagem(e) for e in q.order_by(TriagemEntrada.id.asc()).all()]


def _triagem_marcar(db, entrada, status, usuario_id, conversa_id=None):
    entrada.status = status
    entrada.resolvido_por_id = usuario_id
    entrada.resolvido_em = datetime.utcnow()
    entrada.conversa_id = conversa_id
    db.flush()


def _triagem_postar_na_conversa(db, entrada, conversa, usuario_id):
    """Entrega a mensagem original na conversa (autor NULL = externa) + EnvioExterno de entrada
    com o wamid (mantém idempotência e janela) + EVENTO inline do vínculo (decisão 5)."""
    from . import core as _mc
    canal = _canal_do_thread(db, conversa.id, entrada.meio, entrada.remetente)
    msg = _mc.enviar_mensagem(db, conversa, None, entrada.texto or "(sem texto)", canal=canal,
                              _permitir_externo=True)
    db.add(EnvioExterno(mensagem_id=msg.id, meio=entrada.meio, direcao="entrada", canal=canal,
                        destino=entrada.remetente, status="recebido",
                        id_externo=entrada.id_externo, id_externo_ref=entrada.id_externo_ref))
    u = db.get(Usuario, usuario_id) if usuario_id else None
    corpo_ev = "Contato %s vinculado por %s via triagem" % (
        entrada.remetente, (u.nome if u else "—"))
    _mc.enviar_mensagem(db, conversa, usuario_id, corpo_ev, evento="triagem_vinculo")
    db.flush()
    return msg


def triagem_resolver_vincular(db, entrada, conversa, usuario_id):
    """Vincula a entrada a uma conversa EXISTENTE (candidata ou escolhida). Não commita."""
    if entrada.status != "pendente":
        raise ValueError("Esta entrada já foi resolvida.")
    if conversa is None or conversa.loja_id != entrada.loja_id:
        raise ValueError("Conversa inexistente nesta loja.")
    msg = _triagem_postar_na_conversa(db, entrada, conversa, usuario_id)
    _triagem_marcar(db, entrada, "resolvido", usuario_id, conversa_id=conversa.id)
    return msg


def triagem_resolver_criar(db, entrada, usuario_id, nome_cliente):
    """Lead NOVO por WhatsApp: cria o Cliente (contato no cadastro — decisão 12) + uma conversa
    de GRUPO com o resolvedor dentro e o contato como participante EXTERNO (as respostas da
    equipe espelham pelo transporte). A mensagem original entra na conversa. Não commita."""
    from . import core as _mc
    if entrada.status != "pendente":
        raise ValueError("Esta entrada já foi resolvida.")
    nome_cliente = (nome_cliente or "").strip()
    if not nome_cliente:
        raise ValueError("Dê um nome ao novo cliente.")
    cli = Cliente(nome=nome_cliente, loja_id=entrada.loja_id,
                  whatsapp=(entrada.remetente if entrada.meio == "whatsapp" else None),
                  email=(entrada.remetente if entrada.meio == "email" else None))
    db.add(cli); db.flush()
    conv = _mc.criar_grupo(db, entrada.loja_id, usuario_id, "Lead — %s" % nome_cliente,
                           [usuario_id], exige_dois=False)
    _mc.adicionar_externo(db, conv, nome_cliente,
                          telefone=(entrada.remetente if entrada.meio == "whatsapp" else None),
                          email=(entrada.remetente if entrada.meio == "email" else None),
                          meio=entrada.meio, criado_por_id=usuario_id)
    _triagem_postar_na_conversa(db, entrada, conv, usuario_id)
    _triagem_marcar(db, entrada, "resolvido", usuario_id, conversa_id=conv.id)
    return conv


def triagem_descartar(db, entrada, usuario_id):
    """Descarta (spam/engano) — é REGISTRO, não delete: a entrada fica auditável. Não commita."""
    if entrada.status != "pendente":
        raise ValueError("Esta entrada já foi resolvida.")
    _triagem_marcar(db, entrada, "descartado", usuario_id)
    return entrada
