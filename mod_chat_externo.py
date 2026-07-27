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
from datetime import datetime, timedelta

from database import (EnvioExterno, Conversa, ConversaMensagem, ConversaParticipante,
                      Cliente, Parceiro, Usuario, UsuarioPresenca)

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
    # Message-ID no domínio do remetente (não no hostname da máquina) — threading da decisão 14
    # + entregabilidade (filtros anti-spam olham o alinhamento do domínio do Message-ID).
    _dom = frm.split("@")[-1].strip() if "@" in (frm or "") else None
    msgid = make_msgid(domain=_dom) if _dom else make_msgid()
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


# ═══ Ponte WhatsApp do funcionário (Fatia 6) ═════════════════════════════════
# A web é a casa; o WhatsApp (número da EMPRESA) alcança/recebe do funcionário pelo celular
# CADASTRADO, dentro das regras da Meta: janela de 24h (livre) ou template (fora dela). Não há
# acesso ao WhatsApp pessoal — funcionário↔funcionário não viaja pelo WhatsApp deles.
JANELA_HORAS = 24
PRESENCA_ONLINE_MIN = 5


def registrar_presenca(db, usuario_id):
    """Heartbeat da web: marca o usuário como visto agora."""
    p = db.get(UsuarioPresenca, usuario_id)
    if p is None:
        p = UsuarioPresenca(usuario_id=usuario_id, visto_em=datetime.utcnow())
        db.add(p)
    else:
        p.visto_em = datetime.utcnow()
    db.flush()
    return p


def esta_online(db, usuario_id, minutos=PRESENCA_ONLINE_MIN):
    p = db.get(UsuarioPresenca, usuario_id)
    if p is None or p.visto_em is None:
        return False
    return (datetime.utcnow() - p.visto_em) <= timedelta(minutes=minutos)


def usuario_por_telefone(db, telefone, loja_id=None):
    """Casa um número (entrada do WhatsApp) com um USUÁRIO pelo celular cadastrado (whatsapp ou
    telefone), comparando os últimos 8 dígitos (tolera DDI/DDD). Match único ou None (ambíguo)."""
    d = _digitos(telefone)
    if len(d) < 8:
        return None
    tail = d[-8:]
    achados = []
    q = db.query(Usuario).filter(Usuario.ativo == 1)
    if loja_id:
        q = q.filter(Usuario.loja_id == loja_id)
    for u in q.all():
        for campo in (u.whatsapp, u.telefone):
            du = _digitos(campo)
            if len(du) >= 8 and du[-8:] == tail:
                achados.append(u); break
    return achados[0] if len(achados) == 1 else None


def dentro_da_janela_24h(db, usuario_id):
    """True se há uma mensagem de ENTRADA do celular do usuário nas últimas 24h — nesse caso o
    envio ao vivo é livre (texto). Fora da janela, a Meta exige TEMPLATE aprovado."""
    u = db.get(Usuario, usuario_id)
    if u is None:
        return False
    tail = _digitos(u.whatsapp or u.telefone)[-8:]
    if len(tail) < 8:
        return False
    limite = datetime.utcnow() - timedelta(hours=JANELA_HORAS)
    for env in (db.query(EnvioExterno)
                  .filter(EnvioExterno.meio == "whatsapp", EnvioExterno.direcao == "entrada",
                          EnvioExterno.criado_em >= limite).all()):
        if _digitos(env.destino)[-8:] == tail:
            return True
    return False


def deve_notificar_usuario(db, usuario):
    """Regra da preferência + presença: 'nunca' não notifica; 'sempre' sempre; 'quando_offline'
    (default) só se estiver offline."""
    pref = (getattr(usuario, "notificar_whatsapp", None) or "quando_offline")
    if pref == "nunca":
        return False
    if pref == "sempre":
        return True
    return not esta_online(db, usuario.id)


def notificar_usuario(db, conversa, mensagem, usuario_dest, autor_nome=None):
    """Registra (config-gated) uma notificação WhatsApp para um usuário sobre uma mensagem. Dentro
    da janela 24h → ESPELHA o texto; fora → TEMPLATE (aviso 'abra o sistema'). Sem credencial Meta
    → nasce 'pendente_config' (a rede não é tocada). Retorna o EnvioExterno ou None (sem número)."""
    destino = (usuario_dest.whatsapp or usuario_dest.telefone or "").strip()
    if not destino:
        return None
    espelho = dentro_da_janela_24h(db, usuario_dest.id)
    if espelho:
        corpo = ("💬 %s: %s" % (autor_nome or "Nova mensagem", (mensagem.corpo or "").strip()
                                or "(anexo)"))
    else:
        corpo = ("Você tem uma nova mensagem no Orizon Chat. Abra o sistema para responder.")
    env = registrar_envio(db, mensagem, "whatsapp", "interno", "usuario", usuario_dest.id, destino)
    env.id_externo_ref = None
    # anota o modo no próprio registro (reusa 'erro' como nota quando pendente — não é falha)
    if env.status == "pendente_config":
        env.erro = "modo=%s (aguardando credencial Meta)" % ("espelho" if espelho else "template")
    db.flush()
    if env.status == "enfileirado":
        ok, wamid, err = despachar(env, corpo)
        env.status = "enviado" if ok else "falhou"
        env.id_externo = wamid if ok else None
        if err:
            env.erro = err
        db.flush()
    return env


def notificar_conversa(db, conversa, mensagem, autor_id):
    """Ao postar numa DIRECT/GRUPO, notifica no WhatsApp os participantes (menos o autor) conforme
    a preferência/presença de cada um. Canais públicos não notificam individualmente (audiência
    ampla). Best-effort: nunca quebra o envio da mensagem."""
    if conversa.tipo not in ("direct", "grupo"):
        return []
    dest_ids = [p.usuario_id for p in db.query(ConversaParticipante)
                .filter_by(conversa_id=conversa.id).all() if p.usuario_id != autor_id]
    enviados = []
    autor = db.get(Usuario, autor_id)
    autor_nome = autor.nome if autor else None
    for uid in dest_ids:
        u = db.get(Usuario, uid)
        if u is None or not deve_notificar_usuario(db, u):
            continue
        try:
            ev = notificar_usuario(db, conversa, mensagem, u, autor_nome=autor_nome)
            if ev is not None:
                enviados.append(ev.id)
        except Exception:
            pass   # best-effort
    return enviados


def notificar_gerentes_email(db, mensagem, destinatarios, corpo):
    """Envia (config-gated) um e-mail a cada destinatário [{id, email}] — ex.: gerentes/diretores
    avisados das lacunas no fechamento. Sem SMTP → 'pendente_config' (nada é enviado). Retorna os
    EnvioExterno criados. Não commita."""
    envs = []
    for d in (destinatarios or []):
        email = (d.get("email") or "").strip()
        if not email:
            continue
        env = registrar_envio(db, mensagem, "email", None, "usuario", d.get("id"), email)
        if env.status == "enfileirado":
            ok, mid, err = despachar(env, corpo)
            env.status = "enviado" if ok else "falhou"
            env.id_externo = mid if ok else None
            if err:
                env.erro = err
        envs.append(env)
    db.flush()
    return envs


def processar_entrada_usuario(db, remetente, texto):
    """Resposta do FUNCIONÁRIO pelo WhatsApp: casa o número com um usuário e a posta como ELE na
    conversa da última notificação que recebeu. Retorna {status, conversa_id} ou None se não é um
    usuário conhecido (aí o chamador cai no fluxo de contato externo)."""
    import mod_chat as _mc
    u = usuario_por_telefone(db, remetente)
    if u is None:
        return None
    env = (db.query(EnvioExterno)
             .filter(EnvioExterno.meio == "whatsapp", EnvioExterno.direcao == "saida",
                     EnvioExterno.destinatario_tipo == "usuario",
                     EnvioExterno.destinatario_id == u.id)
             .order_by(EnvioExterno.id.desc()).first())
    if env is None:
        return {"status": "sem_conversa", "conversa_id": None, "usuario_id": u.id}
    msg0 = db.get(ConversaMensagem, env.mensagem_id)
    conv = db.get(Conversa, msg0.conversa_id) if msg0 else None
    if conv is None:
        return {"status": "sem_conversa", "conversa_id": None, "usuario_id": u.id}
    msg = _mc.enviar_mensagem(db, conv, u.id, texto or "(sem texto)", permitir_vazio=True)
    ev = EnvioExterno(mensagem_id=msg.id, meio="whatsapp", direcao="entrada", canal="interno",
                      destino=remetente, status="recebido")
    db.add(ev); db.flush()
    return {"status": "roteado", "conversa_id": conv.id, "usuario_id": u.id}


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
