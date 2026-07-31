# -*- coding: utf-8 -*-
"""mod_chat_externo.py — canais externos do chat (Fatias 6-7: e-mail e WhatsApp).

Spec: docs/superpowers/specs/_geral/2026-07-25-…-design.md (seção 6c/6d).

FUNDAÇÃO construída e testada agora: modelo EnvioExterno, resolução de destino pelo seletor
(decisão 19), roteamento de resposta de entrada (decisão 14) e o CONFIG-GATING dos transportes
(mesmo padrão da chave do modo privado). Os TRANSPORTES AO VIVO (SMTP/Meta Cloud API) são gated
por credencial de ambiente — sem elas, o envio nasce 'pendente_config' e a rede não é tocada.
Ativar é ação de deploy do usuário (variáveis por ambiente), fora deste código.
"""
import json
import os
import re
from datetime import datetime, timedelta

from database import (EnvioExterno, Conversa, ConversaMensagem, ConversaParticipante,
                      ConversaParticipanteExterno, Cliente, Parceiro, Fornecedor, Usuario,
                      UsuarioPresenca, TriagemEntrada, Loja, Projeto)

MEIOS = ("email", "whatsapp")
# Canais externos (segmentos) — 'interno' NÃO é externo.
CANAIS_EXTERNOS = ("comercial", "financeiro", "logistica", "suporte_tecnico", "sac",
                   "compras", "parceiros")

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
    elif destinatario_tipo == "fornecedor":
        obj = db.get(Fornecedor, destinatario_id)   # RF-03: Compras fala com Fornecedor
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


def _erro_meta(he):
    """Extrai a mensagem REAL da Meta de um HTTPError (`error.message`/`error.code`) em vez do genérico
    'HTTP Error 400' — ex.: código 131047 = janela de 24h fechada, exige template (G5/RF-06)."""
    import json as _json
    try:
        d = _json.loads(he.read() or b"{}")
        err = d.get("error") or {}
        msg = (err.get("message") or "").strip()
        if msg:
            code = err.get("code")
            return "Meta %s: %s" % (code if code is not None else getattr(he, "code", "?"), msg)
    except Exception:
        pass
    return "Meta HTTP %s" % getattr(he, "code", "?")


def _enviar_whatsapp(env, corpo):
    import json as _json
    import urllib.request as _u
    import urllib.error as _ue
    token = (os.environ.get("ORIZON_WA_TOKEN") or "").strip()
    phone = _env_por_canal("ORIZON_WA_PHONE_ID", env.canal)
    url = "https://graph.facebook.com/v20.0/%s/messages" % phone
    payload = {"messaging_product": "whatsapp", "to": _digitos(env.destino),
               "type": "text", "text": {"body": corpo or ""}}
    req = _u.Request(url, data=_json.dumps(payload).encode("utf-8"), method="POST",
                     headers={"Authorization": "Bearer " + token,
                              "Content-Type": "application/json"})
    try:
        with _u.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read() or b"{}")
    except _ue.HTTPError as he:
        raise RuntimeError(_erro_meta(he))   # despachar captura e grava em EnvioExterno.erro
    wamid = ((data.get("messages") or [{}])[0]).get("id")
    return True, wamid, (None if wamid else "resposta da Meta sem id de mensagem")


def _enviar_whatsapp_documento(env, caminho_abs, nome, mime):
    """Documento como MÍDIA pela Cloud API (2 passos): upload em /{phone}/media (multipart) →
    mensagem type=document com o media id. Config-gated pelo chamador (despachar_documento)."""
    import json as _json
    import urllib.request as _u
    import urllib.error as _ue
    token = (os.environ.get("ORIZON_WA_TOKEN") or "").strip()
    phone = _env_por_canal("ORIZON_WA_PHONE_ID", env.canal)
    with open(caminho_abs, "rb") as f:
        binario = f.read()
    fronteira = "orizonwa%s" % abs(hash(nome))
    corpo_mp = b""
    def _campo(n, v):
        return (("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (fronteira, n, v)).encode("utf-8"))
    corpo_mp += _campo("messaging_product", "whatsapp")
    corpo_mp += _campo("type", mime or "application/octet-stream")
    corpo_mp += (("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
                  "Content-Type: %s\r\n\r\n" % (fronteira, nome, mime or "application/octet-stream"))
                 .encode("utf-8")) + binario + b"\r\n"
    corpo_mp += ("--%s--\r\n" % fronteira).encode("utf-8")
    req = _u.Request("https://graph.facebook.com/v20.0/%s/media" % phone, data=corpo_mp,
                     method="POST",
                     headers={"Authorization": "Bearer " + token,
                              "Content-Type": "multipart/form-data; boundary=%s" % fronteira})
    try:
        with _u.urlopen(req, timeout=30) as resp:
            media = _json.loads(resp.read() or b"{}")
    except _ue.HTTPError as he:
        raise RuntimeError(_erro_meta(he))
    media_id = media.get("id")
    if not media_id:
        return False, None, "upload de mídia sem id na resposta da Meta"
    payload = {"messaging_product": "whatsapp", "to": _digitos(env.destino),
               "type": "document", "document": {"id": media_id, "filename": nome}}
    req2 = _u.Request("https://graph.facebook.com/v20.0/%s/messages" % phone,
                      data=_json.dumps(payload).encode("utf-8"), method="POST",
                      headers={"Authorization": "Bearer " + token,
                               "Content-Type": "application/json"})
    try:
        with _u.urlopen(req2, timeout=30) as resp:
            data = _json.loads(resp.read() or b"{}")
    except _ue.HTTPError as he:
        raise RuntimeError(_erro_meta(he))
    wamid = ((data.get("messages") or [{}])[0]).get("id")
    return True, wamid, (None if wamid else "resposta da Meta sem id de mensagem")


def despachar_documento(env, caminho_abs, nome, mime):
    """Disparo REAL de um DOCUMENTO por WhatsApp — só quando meio_configurado. Mesmo contrato de
    despachar: (ok, id_externo, erro); exceção vira (False, None, erro)."""
    if not meio_configurado("whatsapp"):
        return False, None, "Transporte não configurado neste ambiente."
    try:
        return _enviar_whatsapp_documento(env, caminho_abs, nome, mime)
    except Exception as e:
        return False, None, str(e)


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


def _loja_da_entrada(db, remetente=None, meio="whatsapp"):
    """Loja da entrada externa: (1) o remetente é um Cliente cadastrado → a loja dele (mais
    específico); (2) NumeroConectado ÚNICO na instalação → a loja do número; (3) primeira loja.
    Multi-número por loja fica p/ quando o webhook repassar o phone_number_id do payload."""
    if remetente and meio == "whatsapp":
        tail = _digitos(remetente)[-8:]
        if len(tail) == 8:
            for c in db.query(Cliente).filter(Cliente.loja_id.isnot(None)).all():
                for campo in (c.whatsapp, c.telefone):
                    d = _digitos(campo)
                    if len(d) >= 8 and d[-8:] == tail:
                        return c.loja_id
    elif remetente and meio == "email":
        alvo = remetente.strip().lower()
        if alvo:
            for c in db.query(Cliente).filter(Cliente.loja_id.isnot(None)).all():
                if (c.email or "").strip().lower() == alvo:
                    return c.loja_id
    from database import NumeroConectado
    nums = db.query(NumeroConectado).all()
    if len(nums) == 1:
        return nums[0].loja_id
    l = db.query(Loja).order_by(Loja.id.asc()).first()
    return l.id if l else None


def processar_entrada(db, meio, remetente, texto, id_externo_ref=None, id_externo=None):
    """Recebe uma resposta EXTERNA já normalizada (o webhook faz o parse específico do provedor)
    e a persiste na conversa certa — ou na FILA DE TRIAGEM (spec 2026-07-31: mensagem nenhuma é
    descartada em silêncio). Idempotente por `id_externo` (a Meta reentrega o mesmo webhook até
    o 200): reentrega de mensagem já roteada OU já enfileirada é no-op que devolve o mesmo
    resultado. Retorna {status: 'roteado'|'triagem', conversa_id, [triagem_id]}. Autor NULL =
    veio de fora. NÃO commita (o chamador decide)."""
    from . import core as _mc
    if id_externo:
        ja = (db.query(EnvioExterno)
                .filter_by(id_externo=id_externo, direcao="entrada").first())
        if ja is not None:                        # reentrega de mensagem já ROTEADA
            m0 = db.get(ConversaMensagem, ja.mensagem_id)
            return {"status": "roteado", "conversa_id": m0.conversa_id if m0 else None}
        ent_ja = db.query(TriagemEntrada).filter_by(id_externo=id_externo).first()
        if ent_ja is not None:                    # reentrega de entrada já na FILA
            return {"status": "triagem", "conversa_id": ent_ja.conversa_id,
                    "triagem_id": ent_ja.id}
    conv, candidatos = _rotear_com_candidatos(db, meio, id_externo_ref=id_externo_ref,
                                              remetente=remetente)
    if conv is None:
        ent = TriagemEntrada(
            loja_id=_loja_da_entrada(db, remetente=remetente, meio=meio), meio=meio,
            remetente=(_digitos(remetente) if meio == "whatsapp"
                       else (remetente or "").strip().lower()),
            texto=texto, id_externo=id_externo, id_externo_ref=id_externo_ref,
            candidatos_json=(json.dumps(sorted(candidatos)) if candidatos else None))
        db.add(ent); db.flush()
        return {"status": "triagem", "conversa_id": None, "triagem_id": ent.id}
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


JANELA_SEG = JANELA_HORAS * 3600


def janela_da_conversa(db, conversa):
    """RF-04: estado da janela de atendimento de 24h DESTA conversa, a partir da última mensagem de
    ENTRADA DO CLIENTE persistida NELA. Escopado pela conversa (join EnvioExterno→ConversaMensagem→
    conversa_id) — achado da Vera: NÃO varrer o histórico global casando só por telefone (vazava entre
    lojas da mesma rede com o mesmo número). 2º achado da Vera: a resposta do FUNCIONÁRIO pela ponte de
    WhatsApp (`processar_entrada_usuario`) também grava uma EnvioExterno de entrada, mas com
    `canal='interno'` — ela NÃO reabre a janela do cliente, então é excluída aqui (mantendo entradas do
    cliente com canal=segmento ou NULL). Retorna {aberta, ultima_entrada(ISO|None), restante_seg, excedido_seg}."""
    fechada = {"aberta": False, "ultima_entrada": None, "restante_seg": 0, "excedido_seg": None}
    row = (db.query(EnvioExterno.criado_em)
             .join(ConversaMensagem, EnvioExterno.mensagem_id == ConversaMensagem.id)
             .filter(ConversaMensagem.conversa_id == conversa.id,
                     EnvioExterno.meio == "whatsapp", EnvioExterno.direcao == "entrada",
                     (EnvioExterno.canal.is_(None)) | (EnvioExterno.canal != "interno"))
             .order_by(EnvioExterno.criado_em.desc()).first())
    if row is None or row[0] is None:
        return fechada
    ult = row[0]
    decorrido = (datetime.utcnow() - ult).total_seconds()
    if decorrido < JANELA_SEG:
        return {"aberta": True, "ultima_entrada": ult.isoformat(),
                "restante_seg": int(JANELA_SEG - decorrido), "excedido_seg": None}
    return {"aberta": False, "ultima_entrada": ult.isoformat(),
            "restante_seg": 0, "excedido_seg": int(decorrido - JANELA_SEG)}


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


def espelhar_para_externos(db, conversa, mensagem, autor_nome=None):
    """Espelha uma mensagem da conversa para os participantes EXTERNOS (contatos WhatsApp/e-mail sem
    Usuario) — Orizon Chat 2026-07-28. Um EnvioExterno por externo, CONFIG-GATED (sem credencial →
    'pendente_config', a rede não é tocada). Best-effort: nunca quebra o envio interno. Retorna os ids
    dos envios criados."""
    externos = (db.query(ConversaParticipanteExterno)
                  .filter_by(conversa_id=conversa.id, removido=0).all())
    if not externos:
        return []
    corpo = "💬 %s: %s" % (autor_nome or "Nova mensagem",
                           (mensagem.corpo or "").strip() or "(anexo)")
    enviados = []
    for e in externos:
        destino = (e.telefone if e.meio == "whatsapp" else e.email or "").strip() if (e.telefone or e.email) else ""
        if not destino:
            continue
        try:
            env = registrar_envio(db, mensagem, e.meio, "comercial", "avulso", e.id, destino)
            if env.status == "enfileirado":
                ok, ext_id, err = despachar(env, corpo)
                env.status = "enviado" if ok else "falhou"
                env.id_externo = ext_id if ok else None
                if err:
                    env.erro = err
                db.flush()
            enviados.append(env.id)
        except Exception:
            pass   # best-effort
    return enviados


def encaminhar_documento_externo(db, conversa, documento, usuario_id, caminho_abs, mime=None):
    """Decisão 3 da spec 2026-07-31 (portas): encaminha um CicloDocumento pelo WhatsApp da
    conversa aos participantes EXTERNOS. DENTRO da janela de 24h → mídia (despachar_documento,
    config-gated: sem credencial nasce 'pendente_config'); FORA da janela a Meta exige TEMPLATE
    aprovado → erro claro (o ramo por template é a F3, pendente). Gera EVENTO inline
    'documento_encaminhado' + um EnvioExterno por externo. Não commita."""
    from . import core as _mc
    j = janela_da_conversa(db, conversa)
    if not j["aberta"]:
        raise ValueError("Janela de 24h fechada — o encaminhamento livre não é permitido pela "
                         "Meta; use um template aprovado (envio por template ainda não "
                         "disponível).")
    externos = [e for e in db.query(ConversaParticipanteExterno)
                  .filter_by(conversa_id=conversa.id, removido=0).all()
                if e.meio == "whatsapp" and (e.telefone or "").strip()]
    if not externos:
        raise ValueError("A conversa não tem contato externo de WhatsApp — adicione o contato "
                         "antes de encaminhar.")
    corpo_ev = "Documento %s encaminhado ao cliente por WhatsApp" % (
        documento.nome_original or documento.tipo)
    msg = _mc.enviar_mensagem(db, conversa, usuario_id, corpo_ev,
                              documento_ref_id=documento.id, evento="documento_encaminhado")
    canal = _canal_do_thread(db, conversa.id, "whatsapp", externos[0].telefone)
    envios = []
    for e in externos:
        env = registrar_envio(db, msg, "whatsapp", canal, "avulso", e.id, e.telefone.strip())
        if env.status == "enfileirado":
            ok, wamid, err = despachar_documento(env, caminho_abs,
                                                 documento.nome_original or "documento", mime)
            env.status = "enviado" if ok else "falhou"
            env.id_externo = wamid if ok else None
            if err:
                env.erro = err
            db.flush()
        envios.append(env)
    return msg, envios


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
    from . import core as _mc
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


def _rotear_com_candidatos(db, meio, id_externo_ref=None, remetente=None):
    """Roteamento da entrada externa com os CANDIDATOS preservados (spec 2026-07-31): retorna
    (conversa, candidatos). Ordem: (1) reply CITANDO um envio nosso (id_externo) → determinístico
    (vence inclusive projeto concluído); (2) sem citação, número/e-mail com UMA única conversa
    ATIVA → vai direto — conversa de projeto CONCLUÍDO não é reaberta sozinha, vira candidata;
    (3) várias/nenhuma ativa → (None, candidatos) e a lista NÃO se perde (vai à fila)."""
    if id_externo_ref:
        env = (db.query(EnvioExterno)
                 .filter(EnvioExterno.id_externo == id_externo_ref).first())
        if env is not None:
            msg = db.get(ConversaMensagem, env.mensagem_id)
            conv = db.get(Conversa, msg.conversa_id) if msg else None
            if conv is not None:
                return conv, [conv.id]
    if not remetente:
        return None, []
    alvo_norm = _digitos(remetente) if meio == "whatsapp" else remetente.strip().lower()
    conv_ids = set()
    q = (db.query(EnvioExterno, ConversaMensagem.conversa_id)
           .join(ConversaMensagem, EnvioExterno.mensagem_id == ConversaMensagem.id)
           .filter(EnvioExterno.meio == meio))
    for env, conv_id in q.all():
        dnorm = _digitos(env.destino) if meio == "whatsapp" else (env.destino or "").strip().lower()
        if dnorm and dnorm == alvo_norm:
            conv_ids.add(conv_id)
    if not conv_ids:
        return None, []
    ativas = []
    for cid in conv_ids:
        c = db.get(Conversa, cid)
        if c is not None and c.projeto_nome:
            p = db.query(Projeto).filter_by(nome_safe=c.projeto_nome).first()
            if p is not None and p.status == "concluido":
                continue                     # projeto encerrado → decisão humana, não reabertura
        ativas.append(cid)
    if len(ativas) == 1:
        return db.get(Conversa, ativas[0]), ativas
    return None, sorted(conv_ids)


def rotear_entrada(db, meio, id_externo_ref=None, remetente=None):
    """Conversa-alvo de uma resposta EXTERNA, ou None quando é ambíguo/desconhecido (→ fila de
    triagem persistida — processar_entrada guarda os candidatos)."""
    conv, _cand = _rotear_com_candidatos(db, meio, id_externo_ref=id_externo_ref,
                                         remetente=remetente)
    return conv

# Re-export de compatibilidade: a fila de triagem vive em chat/triagem.py (spec de portas).
from .triagem import (serializar_triagem, triagem_listar,            # noqa: E402,F401
                      triagem_resolver_vincular, triagem_resolver_criar,
                      triagem_descartar)
