# -*- coding: utf-8 -*-
"""mod_chat.py — Chat do Orizon, Fatia 1 (Fundação).

Spec: docs/superpowers/specs/_geral/2026-07-25-chat-projeto-porta-externa-whatsapp-email-design.md
(decisões de produto 1-10 FECHADAS lá — não reabrir aqui).

Nesta fatia: Conversa por projeto (âncora flexível) + mensagem interna, cronológica.
CANAIS espelha o modelo consolidado da spec desde já, mas só 'interno' circula — os
externos (comercial/financeiro/logistica/suporte_tecnico/sac) entram nas fatias 6-7,
e natureza/transferência/bloqueador/privada nas fatias 2-4.
"""
from database import Conversa, ConversaMensagem, Usuario

CANAIS = ("interno", "comercial", "financeiro", "logistica", "suporte_tecnico", "sac")
_CANAIS_FATIA_1 = ("interno",)


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
