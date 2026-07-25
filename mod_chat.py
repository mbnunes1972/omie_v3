# -*- coding: utf-8 -*-
"""mod_chat.py — Chat do Orizon, Fatia 1 (Fundação).

Spec: docs/superpowers/specs/_geral/2026-07-25-chat-projeto-porta-externa-whatsapp-email-design.md
(decisões de produto 1-10 FECHADAS lá — não reabrir aqui).

Nesta fatia: Conversa por projeto (âncora flexível) + mensagem interna, cronológica.
CANAIS espelha o modelo consolidado da spec desde já, mas só 'interno' circula — os
externos (comercial/financeiro/logistica/suporte_tecnico/sac) entram nas fatias 6-7,
e natureza/transferência/bloqueador/privada nas fatias 2-4.
"""
import json

from database import Conversa, ConversaMensagem, ContatoConfirmacao, Usuario, Cliente, Parceiro

CANAIS = ("interno", "comercial", "financeiro", "logistica", "suporte_tecnico", "sac")
_CANAIS_FATIA_1 = ("interno",)

# ── Confirmação de contatos na fase de contrato (decisão 13, mini-frente 2026-07-25) ──────
MODOS_CONFIRMACAO = ("confirmado", "sem_whatsapp")


def contatos_do_projeto(db, cliente_id=None, parceiro_id=None):
    """Contatos de comunicação dos participantes externos, SEMPRE lidos do cadastro no
    momento da leitura (decisão 12). Cliente ainda não tem campo WhatsApp próprio — o
    telefone é o candidato exibido (a UI rotula e avisa); Parceiro tem whatsapp de verdade."""
    contatos = []
    if cliente_id:
        c = db.get(Cliente, cliente_id)
        if c is not None:
            contatos.append({"papel": "cliente", "nome": c.nome,
                             "whatsapp": (c.telefone or "").strip(),
                             "email": (c.email or "").strip()})
    if parceiro_id:
        p = db.get(Parceiro, parceiro_id)
        if p is not None:
            contatos.append({"papel": "arquiteto", "nome": p.nome,
                             "whatsapp": (p.whatsapp or p.telefone or "").strip(),
                             "email": (p.email or "").strip()})
    return contatos


def confirmacao_vigente(db, loja_id, projeto_nome):
    """A confirmação mais recente do projeto (append-only), ou None."""
    return (db.query(ContatoConfirmacao)
              .filter_by(loja_id=loja_id, projeto_nome=projeto_nome)
              .order_by(ContatoConfirmacao.id.desc())
              .first())


def registrar_confirmacao(db, loja_id, projeto_nome, usuario_id, modo, contatos):
    if modo not in MODOS_CONFIRMACAO:
        raise ValueError("modo inválido: %r (aceitos: %s)" % (modo, ", ".join(MODOS_CONFIRMACAO)))
    reg = ContatoConfirmacao(loja_id=loja_id, projeto_nome=projeto_nome, modo=modo,
                             contatos_json=json.dumps(contatos or [], ensure_ascii=False),
                             confirmado_por_id=usuario_id)
    db.add(reg)
    db.flush()
    return reg


def serializar_confirmacao(reg, confirmado_por_nome=None):
    if reg is None:
        return None
    return {"modo": reg.modo,
            "confirmado_por_id": reg.confirmado_por_id,
            "confirmado_por_nome": confirmado_por_nome or "—",
            "confirmado_em": reg.confirmado_em.isoformat() if reg.confirmado_em else None}


def get_or_create_conversa_projeto(db, loja_id, projeto_nome, cliente_id=None):
    """Conversa ÚNICA do projeto na loja (get-or-create; a primeira criada é a canônica).
    `cliente_id` só é gravado na criação — vínculo de nascença, não sincronização."""
    c = (db.query(Conversa)
           .filter_by(loja_id=loja_id, projeto_nome=projeto_nome)
           .order_by(Conversa.id.asc())
           .first())
    if c is None:
        c = Conversa(loja_id=loja_id, projeto_nome=projeto_nome, cliente_id=cliente_id)
        db.add(c)
        db.flush()
    return c


def enviar_mensagem(db, conversa, autor_usuario_id, corpo, canal="interno"):
    """Grava uma mensagem na conversa. Levanta ValueError com mensagem de usuário.
    Fatia 1: canal externo é recusado aqui (não só escondido na UI) — quando as fatias
    6-7 chegarem, é ESTA validação que relaxa, com o EnvioExterno junto."""
    corpo = (corpo or "").strip()
    if not corpo:
        raise ValueError("Escreva a mensagem antes de enviar.")
    if canal not in CANAIS:
        raise ValueError("canal inválido: %r (aceitos: %s)" % (canal, ", ".join(CANAIS)))
    if canal not in _CANAIS_FATIA_1:
        raise ValueError("Canal externo ainda não disponível — por ora a conversa é interna.")
    m = ConversaMensagem(conversa_id=conversa.id, autor_usuario_id=autor_usuario_id,
                         corpo=corpo, canal=canal)
    db.add(m)
    db.flush()
    return m


def serializar_mensagem(m, autor_nome=None):
    return {"id": m.id, "autor_usuario_id": m.autor_usuario_id,
            "autor_nome": autor_nome or "—", "corpo": m.corpo, "canal": m.canal,
            "criado_em": m.criado_em.isoformat() if m.criado_em else None}


def listar_mensagens(db, conversa_id):
    """Histórico cronológico ASC, com o nome do autor resolvido (outerjoin: autor NULL —
    resposta externa das fatias futuras — não derruba a listagem)."""
    rows = (db.query(ConversaMensagem, Usuario.nome)
              .outerjoin(Usuario, ConversaMensagem.autor_usuario_id == Usuario.id)
              .filter(ConversaMensagem.conversa_id == conversa_id)
              .order_by(ConversaMensagem.criado_em.asc(), ConversaMensagem.id.asc())
              .all())
    return [serializar_mensagem(m, nome) for m, nome in rows]
