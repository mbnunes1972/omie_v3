# -*- coding: utf-8 -*-
"""mod_chat_externo.py — canais externos do chat (Fatias 6-7: e-mail e WhatsApp).

Spec: docs/superpowers/specs/_geral/2026-07-25-…-design.md (seção 6c/6d).

FUNDAÇÃO construída e testada agora: modelo EnvioExterno, resolução de destino pelo seletor
(decisão 19), roteamento de resposta de entrada (decisão 14) e o CONFIG-GATING dos transportes
(mesmo padrão da chave do modo privado). Os TRANSPORTES AO VIVO (SMTP/Meta Cloud API) são gated
por credencial de ambiente — sem elas, o envio nasce 'pendente_config' e a rede não é tocada.
Ativar é ação de deploy do usuário (variáveis por ambiente), fora deste código.
"""
import os
import re

from database import EnvioExterno, Conversa, ConversaMensagem, Cliente, Parceiro, Usuario

MEIOS = ("email", "whatsapp")
# Canais externos (segmentos) — 'interno' NÃO é externo.
CANAIS_EXTERNOS = ("comercial", "financeiro", "logistica", "suporte_tecnico", "sac")

_ENV_POR_MEIO = {
    "email":    ("ORIZON_SMTP_HOST", "ORIZON_SMTP_PORT", "ORIZON_SMTP_USER",
                 "ORIZON_SMTP_PASS", "ORIZON_SMTP_FROM"),
    "whatsapp": ("ORIZON_WA_TOKEN", "ORIZON_WA_PHONE_ID"),
}


def meio_configurado(meio):
    """True se TODAS as variáveis de ambiente do transporte estão presentes. Sem elas, o envio
    ao vivo é impossível → o envio fica 'pendente_config' (nunca um 'enviado' fantasma)."""
    envs = _ENV_POR_MEIO.get(meio)
    if not envs:
        return False
    return all((os.environ.get(e) or "").strip() for e in envs)


# ── resolução de destino (decisão 19: seletor interno/parceiro/cliente/avulso) ───────────────

def _digitos(s):
    return re.sub(r"\D", "", s or "")


def resolver_destino(db, meio, destinatario_tipo, destinatario_id, avulso):
    """Retorna (destino, erro). `avulso` (número/e-mail digitado à mão) vence o cadastro. Para
    cadastro, lê do vivo (decisão 12): Cliente/Parceiro têm whatsapp+email; interno = Usuario
    (e-mail; WhatsApp de usuário interno não é padrão — erro claro se pedirem)."""
    if destinatario_tipo == "avulso":
        v = (avulso or "").strip()
        if not v:
            return None, "Informe o contato avulso (número ou e-mail)."
        if meio == "email" and "@" not in v:
            return None, "E-mail avulso inválido."
        if meio == "whatsapp" and len(_digitos(v)) < 10:
            return None, "Número de WhatsApp avulso inválido."
        return v, None
    obj = None
    if destinatario_tipo == "cliente":
        obj = db.get(Cliente, destinatario_id)
    elif destinatario_tipo == "parceiro":
        obj = db.get(Parceiro, destinatario_id)
    elif destinatario_tipo == "interno":
        obj = db.get(Usuario, destinatario_id)
    else:
        return None, "Tipo de destinatário inválido."
    if obj is None:
        return None, "Destinatário não encontrado."
    if meio == "email":
        v = (getattr(obj, "email", "") or "").strip()
        return (v, None) if v else (None, "%s sem e-mail no cadastro." % obj.nome)
    # whatsapp
    v = (getattr(obj, "whatsapp", "") or getattr(obj, "telefone", "") or "").strip()
    return (v, None) if v else (None, "%s sem WhatsApp no cadastro." % obj.nome)


# ── registro do envio (dispatch gated) ───────────────────────────────────────

def registrar_envio(db, mensagem, meio, canal, destinatario_tipo, destinatario_id, destino):
    """Cria o EnvioExterno de SAÍDA. Se o meio não está configurado, status 'pendente_config'
    (a rede não é tocada); configurado, 'enfileirado' (o disparo real é _despachar, isolado)."""
    status = "enfileirado" if meio_configurado(meio) else "pendente_config"
    env = EnvioExterno(mensagem_id=mensagem.id, meio=meio, direcao="saida", canal=canal,
                       destinatario_tipo=destinatario_tipo, destinatario_id=destinatario_id,
                       destino=destino, status=status)
    db.add(env)
    db.flush()
    return env


def despachar(env, corpo):
    """Disparo REAL — só chamado quando meio_configurado(env.meio). Isolado de propósito: é a
    única parte que toca a rede e não roda nos testes (precisa de credencial). Prontos-para-
    ativar: implementar SMTP (email) e Meta Cloud API (whatsapp) aqui quando as credenciais
    existirem. Retorna (ok, id_externo, erro)."""
    if not meio_configurado(env.meio):
        return False, None, "Transporte não configurado."
    # NOTE: implementação ao vivo pendente de credenciais (ação de deploy do usuário).
    # email  -> smtplib.SMTP(host, port).login(user, pass).sendmail(from, [destino], msg)
    # whatsapp -> POST https://graph.facebook.com/v20.0/<PHONE_ID>/messages (Bearer TOKEN)
    return False, None, "Transporte ao vivo ainda não ativado neste ambiente."


# ── roteamento da resposta de entrada (decisão 14) ───────────────────────────

def rotear_entrada(db, meio, id_externo_ref=None, remetente=None):
    """Conversa-alvo de uma resposta EXTERNA, ou None quando é ambíguo (→ fila de triagem
    humana). Ordem: (1) reply CITANDO um envio nosso (id_externo) → determinístico; (2) sem
    citação, número/e-mail com UMA única conversa ativa → vai direto; (3) várias → None."""
    if id_externo_ref:
        env = (db.query(EnvioExterno)
                 .filter(EnvioExterno.id_externo == id_externo_ref).first())
        if env is not None:
            msg = db.get(ConversaMensagem, env.mensagem_id)
            return db.get(Conversa, msg.conversa_id) if msg else None
    if remetente:
        alvo_norm = _digitos(remetente) if meio == "whatsapp" else remetente.strip().lower()
        conv_ids = set()
        q = (db.query(EnvioExterno, ConversaMensagem.conversa_id)
               .join(ConversaMensagem, EnvioExterno.mensagem_id == ConversaMensagem.id)
               .filter(EnvioExterno.meio == meio))
        for env, conv_id in q.all():
            dnorm = _digitos(env.destino) if meio == "whatsapp" else (env.destino or "").strip().lower()
            if dnorm and dnorm == alvo_norm:
                conv_ids.add(conv_id)
        if len(conv_ids) == 1:
            return db.get(Conversa, conv_ids.pop())
    return None   # ambíguo ou desconhecido → triagem humana
