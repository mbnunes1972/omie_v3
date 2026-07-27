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


_CANAL_ROTULO = {"comercial": "Comercial", "financeiro": "Financeiro", "logistica": "Logística",
                 "suporte_tecnico": "Suporte Técnico", "sac": "SAC"}


def _env_por_canal(base, canal):
    """Override por canal (os 5 endereços/números são CONFIG, não código — spec Fatia 6):
    ORIZON_SMTP_FROM_FINANCEIRO, ORIZON_WA_PHONE_ID_SAC, etc.; fallback à base."""
    if canal:
        v = (os.environ.get("%s_%s" % (base, canal.upper())) or "").strip()
        if v:
            return v
    return (os.environ.get(base) or "").strip()


def _enviar_email(env, corpo):
    import smtplib
    from email.message import EmailMessage
    from email.utils import make_msgid
    host = (os.environ.get("ORIZON_SMTP_HOST") or "").strip()
    port = int((os.environ.get("ORIZON_SMTP_PORT") or "587").strip())
    user = (os.environ.get("ORIZON_SMTP_USER") or "").strip()
    pw   = (os.environ.get("ORIZON_SMTP_PASS") or "").strip()
    frm  = _env_por_canal("ORIZON_SMTP_FROM", env.canal)
    msgid = make_msgid()   # threading por Message-ID (decisão 14, e-mail)
    msg = EmailMessage()
    msg["From"] = frm
    msg["To"] = env.destino
    msg["Subject"] = "[Orizon] %s — Projeto" % _CANAL_ROTULO.get(env.canal, "Comunicação")
    msg["Message-ID"] = msgid
    if env.id_externo_ref:                 # resposta encadeia no thread original
        msg["In-Reply-To"] = env.id_externo_ref
        msg["References"] = env.id_externo_ref
    msg.set_content(corpo or "")
    with smtplib.SMTP(host, port, timeout=15) as s:
        s.starttls()
        if user:
            s.login(user, pw)
        s.send_message(msg)
    return True, msgid, None


def _enviar_whatsapp(env, corpo):
    import json as _json
    import urllib.request as _u
    token = (os.environ.get("ORIZON_WA_TOKEN") or "").strip()
    phone = _env_por_canal("ORIZON_WA_PHONE_ID", env.canal)
    url = "https://graph.facebook.com/v20.0/%s/messages" % phone
    payload = {"messaging_product": "whatsapp", "to": _digitos(env.destino),
               "type": "text", "text": {"body": corpo or ""}}
    req = _u.Request(url, data=_json.dumps(payload).encode("utf-8"), method="POST",
                     headers={"Authorization": "Bearer " + token,
                              "Content-Type": "application/json"})
    with _u.urlopen(req, timeout=15) as resp:
        data = _json.loads(resp.read() or b"{}")
    wamid = ((data.get("messages") or [{}])[0]).get("id")
    return True, wamid, (None if wamid else "resposta da Meta sem id de mensagem")


def despachar(env, corpo):
    """Disparo REAL do envio externo — só quando meio_configurado(env.meio). SMTP (e-mail) e Meta
    Cloud API (WhatsApp). A rede é a única parte não coberta por credencial nos testes (os testes
    mockam o boundary smtplib/urlopen). Retorna (ok, id_externo, erro); exceção de rede vira
    (False, None, erro) — o chamador marca o envio como 'falhou' com a mensagem."""
    if not meio_configurado(env.meio):
        return False, None, "Transporte não configurado neste ambiente."
    try:
        if env.meio == "email":
            return _enviar_email(env, corpo)
        if env.meio == "whatsapp":
            return _enviar_whatsapp(env, corpo)
    except Exception as e:
        return False, None, str(e)
    return False, None, "Meio de envio desconhecido: %r" % env.meio


# ── roteamento da resposta de entrada (decisão 14) ───────────────────────────

def _canal_do_thread(db, conversa_id, meio, remetente):
    """Canal (segmento) do fio externo desta conversa: o do envio de SAÍDA mais recente para
    o mesmo destino/meio; fallback 'comercial'."""
    alvo = _digitos(remetente) if meio == "whatsapp" else (remetente or "").strip().lower()
    q = (db.query(EnvioExterno, ConversaMensagem.conversa_id)
           .join(ConversaMensagem, EnvioExterno.mensagem_id == ConversaMensagem.id)
           .filter(ConversaMensagem.conversa_id == conversa_id,
                   EnvioExterno.meio == meio, EnvioExterno.direcao == "saida")
           .order_by(EnvioExterno.id.desc()))
    for env, _cid in q.all():
        dnorm = _digitos(env.destino) if meio == "whatsapp" else (env.destino or "").strip().lower()
        if dnorm == alvo and env.canal:
            return env.canal
    return "comercial"


def processar_entrada(db, meio, remetente, texto, id_externo_ref=None, id_externo=None):
    """Recebe uma resposta EXTERNA já normalizada (o webhook faz o parse específico do provedor)
    e a persiste na conversa certa. Roteia por rotear_entrada (decisão 14). Retorna
    {status: 'roteado'|'triagem', conversa_id}. Autor NULL = veio de fora. Ambíguo → triagem
    (não cria mensagem; um humano roteia depois). NÃO commita (o chamador decide)."""
    import mod_chat as _mc
    conv = rotear_entrada(db, meio, id_externo_ref=id_externo_ref, remetente=remetente)
    if conv is None:
        return {"status": "triagem", "conversa_id": None}
    canal = _canal_do_thread(db, conv.id, meio, remetente)
    msg = _mc.enviar_mensagem(db, conv, None, texto or "(sem texto)", canal=canal,
                              _permitir_externo=True)
    ev = EnvioExterno(mensagem_id=msg.id, meio=meio, direcao="entrada", canal=canal,
                      destino=remetente, status="recebido",
                      id_externo=id_externo, id_externo_ref=id_externo_ref)
    db.add(ev); db.flush()
    return {"status": "roteado", "conversa_id": conv.id}


def iter_mensagens_whatsapp(payload):
    """Extrai as mensagens de um payload de entrada da Meta WhatsApp Cloud API, normalizadas em
    {from, texto, id, ref}. Tolerante à forma aninhada (entry[].changes[].value.messages[])."""
    for entry in (payload or {}).get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            val = change.get("value", {}) or {}
            for msg in val.get("messages", []) or []:
                yield {"from": msg.get("from", ""),
                       "texto": ((msg.get("text") or {}).get("body")
                                 or "(mensagem sem texto)"),
                       "id": msg.get("id"),
                       "ref": (msg.get("context") or {}).get("id")}


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
