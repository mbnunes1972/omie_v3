# -*- coding: utf-8 -*-
"""Chat — Fatias 6-7 (canais externos e-mail/WhatsApp), FUNDAÇÃO testável (spec seção 6d).

Cobre o que NÃO depende de credencial: modelo EnvioExterno, resolução de destino pelo seletor
(interno/parceiro/cliente/avulso — decisão 19), roteamento de resposta de entrada (decisão 14:
reply citado > número com 1 conversa ativa > triagem humana) e o config-gating (sem credencial,
envio vira 'pendente_config', nunca 'enviado' fantasma). Os transportes ao vivo (SMTP/Meta) são
gated e não entram aqui."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


# ── config-gating ────────────────────────────────────────────────────────────

# ── Race de import do shim (achado real 2026-08-21) ────────────────────────────

def test_main_importa_mod_chat_externo_no_carregamento_do_modulo():
    """Guarda de regressão do AttributeError real em produção:
    'mod_chat_externo' has no attribute 'varrer_triagem_vencida'.

    mod_chat.py/mod_chat_externo.py são shims que fazem `sys.modules[__name__] = _core`
    (troca o PRÓPRIO objeto de módulo pelo de chat/ durante a execução — ver o docstring
    deles). Só é seguro sob concorrência (ThreadingHTTPServer, uma thread por request) se
    essa troca já tiver acontecido ANTES de qualquer request chegar: um `import
    mod_chat_externo` disparado ao mesmo tempo por duas threads, na primeiríssima vez
    (ex.: logo após um deploy/restart), pode fazer a thread perdedora do lock de import
    capturar o shim ANTIGO (vazio) em vez do módulo real — comprovado em produção.

    main.py precisa importar os dois, no nível do módulo (thread única, antes do
    ThreadingHTTPServer subir), pra fechar essa janela. Este teste trava que ninguém
    remova esse import "porque parecia redundante" sem entender o motivo."""
    import main
    import sys
    assert hasattr(sys.modules["mod_chat_externo"], "varrer_triagem_vencida")
    assert hasattr(sys.modules["mod_chat"], "listar_inbox")


def test_meio_configurado_por_env(monkeypatch):
    import mod_chat_externo as ext
    monkeypatch.delenv("ORIZON_SMTP_HOST", raising=False)
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    assert ext.meio_configurado("email") is False
    assert ext.meio_configurado("whatsapp") is False
    monkeypatch.setenv("ORIZON_SMTP_HOST", "smtp.x"); monkeypatch.setenv("ORIZON_SMTP_PORT", "587")
    monkeypatch.setenv("ORIZON_SMTP_USER", "u"); monkeypatch.setenv("ORIZON_SMTP_PASS", "p")
    monkeypatch.setenv("ORIZON_SMTP_FROM", "a@b.c")
    monkeypatch.setenv("ORIZON_WA_TOKEN", "tok"); monkeypatch.setenv("ORIZON_WA_PHONE_ID", "123")
    assert ext.meio_configurado("email") is True
    assert ext.meio_configurado("whatsapp") is True


# ── resolução de destino (decisão 19) ────────────────────────────────────────

def test_resolver_destino_cadastro_e_avulso(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    cli = db.get(app_db.Cliente, seed["cliente_l1_id"])
    cli.whatsapp = "(12) 90000-1111"; cli.email = "cli@ex.com"
    par = app_db.Parceiro(nome="Arq Teste", tipo="arquiteto", whatsapp="(12) 90000-2222",
                          email="arq@ex.com")
    db.add(par); db.commit()

    import re as _re
    d, err = ext.resolver_destino(db, "whatsapp", "cliente", seed["cliente_l1_id"], None)
    assert err is None and "12900001111" in _re.sub(r"\D", "", d)   # contém o número
    d, err = ext.resolver_destino(db, "email", "cliente", seed["cliente_l1_id"], None)
    assert err is None and d == "cli@ex.com"
    d, err = ext.resolver_destino(db, "email", "parceiro", par.id, None)
    assert err is None and d == "arq@ex.com"
    # avulso: número digitado à mão vence o cadastro
    d, err = ext.resolver_destino(db, "whatsapp", "avulso", None, "(11) 98888-7777")
    assert err is None and "8888-7777" in d
    # sem contato no cadastro → erro claro (não manda pra vazio)
    par2 = app_db.Parceiro(nome="Sem Contato", tipo="arquiteto")
    db.add(par2); db.commit()
    d, err = ext.resolver_destino(db, "email", "parceiro", par2.id, None)
    assert d is None and err
    db.close()


# ── roteamento da resposta de entrada (decisão 14) ───────────────────────────

def test_rotear_entrada_por_reply_citado(app_db, seed):
    import mod_chat_externo as ext, mod_chat
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1"); db.flush()
    m = mod_chat.enviar_mensagem(db, conv, None, "oi externo", canal="comercial",
                                 _permitir_externo=True)
    env = ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente",
                              seed["cliente_l1_id"], "(12) 90000-1111")
    env.id_externo = "wamid.ABC"; db.commit()
    # resposta citando o id → conversa exata, determinístico
    alvo = ext.rotear_entrada(db, "whatsapp", id_externo_ref="wamid.ABC",
                              remetente="(12) 90000-1111")
    assert alvo is not None and alvo.id == conv.id
    db.close()


def test_rotear_entrada_numero_uma_conversa_vs_triagem(app_db, seed):
    import mod_chat_externo as ext, mod_chat
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1"); db.flush()
    m = mod_chat.enviar_mensagem(db, conv, None, "msg", canal="comercial", _permitir_externo=True)
    ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente", seed["cliente_l1_id"],
                        "(12) 90000-1111"); db.commit()
    # sem reply citado, número com UMA conversa ativa → vai direto
    alvo = ext.rotear_entrada(db, "whatsapp", id_externo_ref=None, remetente="(12) 90000-1111")
    assert alvo is not None and alvo.id == conv.id
    # número que participa de DUAS conversas → triagem (None)
    conv2 = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L2"); db.flush()
    m2 = mod_chat.enviar_mensagem(db, conv2, None, "m2", canal="comercial", _permitir_externo=True)
    ext.registrar_envio(db, m2, "whatsapp", "comercial", "cliente", seed["cliente_l1_id"],
                        "(12) 90000-1111"); db.commit()
    alvo = ext.rotear_entrada(db, "whatsapp", id_externo_ref=None, remetente="(12) 90000-1111")
    assert alvo is None            # ambíguo → fila de triagem humana
    db.close()


# ── e2e: envio externo cria Mensagem + EnvioExterno pendente sem config ──────

def test_envio_externo_sem_config_fica_pendente(http_client_factory, seed, app_db, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    db = app_db.get_session()
    db.get(app_db.Cliente, seed["cliente_l1_id"]).whatsapp = "(12) 90000-1111"; db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens/externo",
                      {"corpo": "olá cliente", "meio": "whatsapp", "canal": "comercial",
                       "destinatario_tipo": "cliente", "destinatario_id": seed["cliente_l1_id"]})
    assert st == 201 and body["ok"], body
    assert body["envio"]["status"] == "pendente_config"     # sem credencial → pendente, claro
    assert body["envio"]["meio"] == "whatsapp"
    # a Mensagem foi criada no canal externo (não "interno") e aparece na conversa
    st, body = c.get("/api/projetos/Proj_L1/conversa")
    assert any(m["canal"] == "comercial" for m in body["mensagens"]), body


def test_envio_externo_canal_invalido_e_meio_invalido(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, _ = c.post("/api/projetos/Proj_L1/conversa/mensagens/externo",
                   {"corpo": "x", "meio": "pombo", "canal": "comercial",
                    "destinatario_tipo": "avulso", "destino_avulso": "x@y.z"})
    assert st == 400
    st, _ = c.post("/api/projetos/Proj_L1/conversa/mensagens/externo",
                   {"corpo": "x", "meio": "email", "canal": "interno",
                    "destinatario_tipo": "avulso", "destino_avulso": "x@y.z"})
    assert st == 400   # 'interno' não é canal externo


# ── entrada: processar resposta externa e persistir (decisão 14 aplicada) ─────

def test_processar_entrada_roteia_e_persiste(app_db, seed):
    import mod_chat_externo as ext, mod_chat
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1"); db.flush()
    m = mod_chat.enviar_mensagem(db, conv, None, "pergunta ao cliente", canal="comercial",
                                 _permitir_externo=True)
    env = ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente",
                              seed["cliente_l1_id"], "(12) 90000-1111")
    env.id_externo = "wamid.OUT"; db.commit()
    # resposta citando o envio → roteia e cria mensagem de ENTRADA (autor NULL = externo)
    out = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-1111",
                                texto="resposta do cliente", id_externo_ref="wamid.OUT",
                                id_externo="wamid.IN")
    db.commit()
    assert out["status"] == "roteado" and out["conversa_id"] == conv.id
    msgs = mod_chat.listar_mensagens(db, conv.id)
    entrada = [x for x in msgs if x["corpo"] == "resposta do cliente"]
    assert entrada and entrada[0]["autor_usuario_id"] is None and entrada[0]["canal"] == "comercial"
    ev = (db.query(ext.EnvioExterno).filter_by(direcao="entrada", id_externo="wamid.IN").first())
    assert ev is not None and ev.status == "recebido"
    db.close()


def test_processar_entrada_ambiguo_vai_para_triagem(app_db, seed):
    import mod_chat_externo as ext, mod_chat
    db = app_db.get_session()
    for proj in ("Proj_L1", "Proj_L2"):
        conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], proj); db.flush()
        m = mod_chat.enviar_mensagem(db, conv, None, "msg", canal="comercial", _permitir_externo=True)
        ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente", seed["cliente_l1_id"],
                            "(12) 90000-9999")
    db.commit()
    out = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-9999",
                                texto="oi", id_externo_ref=None, id_externo="wamid.X")
    db.commit()
    assert out["status"] == "triagem" and out["conversa_id"] is None
    db.close()


# ── webhook de entrada (Meta WhatsApp Cloud API) — testável no que não depende da rede ──

def _post_raw(client, path, body_bytes, headers=None):
    import urllib.request as u, urllib.error as ue
    req = u.Request(client.base + path, data=body_bytes, method="POST")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        r = u.urlopen(req, timeout=10); return r.status, r.read()
    except ue.HTTPError as e:
        return e.code, e.read()


def test_webhook_verify_handshake(http_client_factory, seed, monkeypatch):
    monkeypatch.setenv("ORIZON_WA_VERIFY_TOKEN", "segredo123")
    c = http_client_factory()
    import urllib.request as u
    r = u.urlopen(c.base + "/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=segredo123&hub.challenge=42", timeout=10)
    assert r.status == 200 and r.read().decode().strip() == "42"
    # token errado → 403
    import urllib.error as ue
    try:
        u.urlopen(c.base + "/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=errado&hub.challenge=42", timeout=10)
        assert False
    except ue.HTTPError as e:
        assert e.code == 403


def test_webhook_inerte_sem_config(http_client_factory, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    c = http_client_factory()
    st, _ = _post_raw(c, "/webhooks/whatsapp", b'{"entry":[]}', {"Content-Type": "application/json"})
    assert st == 200   # ack, mas não processa nada (dormiente)


def test_webhook_configurado_roteia_resposta(http_client_factory, seed, app_db, monkeypatch):
    import json as _j, hmac, hashlib
    monkeypatch.setenv("ORIZON_WA_TOKEN", "tok"); monkeypatch.setenv("ORIZON_WA_PHONE_ID", "1")
    monkeypatch.setenv("ORIZON_WA_APP_SECRET", "sekret")
    # prepara um envio de saída p/ o número, para a resposta ter onde cair
    import mod_chat_externo as ext, mod_chat
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1"); db.flush()
    m = mod_chat.enviar_mensagem(db, conv, None, "pergunta", canal="financeiro", _permitir_externo=True)
    e = ext.registrar_envio(db, m, "whatsapp", "financeiro", "cliente", seed["cliente_l1_id"], "5512988887777")
    e.id_externo = "wamid.OUT2"; db.commit(); conv_id = conv.id; db.close()

    payload = {"entry":[{"changes":[{"value":{"messages":[
        {"from":"5512988887777","id":"wamid.IN2","text":{"body":"resposta via webhook"},
         "context":{"id":"wamid.OUT2"}}]}}]}]}
    raw = _j.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"sekret", raw, hashlib.sha256).hexdigest()
    c = http_client_factory()
    st, _ = _post_raw(c, "/webhooks/whatsapp", raw,
                      {"Content-Type":"application/json","X-Hub-Signature-256":sig})
    assert st == 200
    db = app_db.get_session()
    msgs = mod_chat.listar_mensagens(db, conv_id)
    assert any(x["corpo"] == "resposta via webhook" and x["autor_usuario_id"] is None for x in msgs)
    db.close()

    # assinatura inválida → 403, nada persistido
    st, _ = _post_raw(c, "/webhooks/whatsapp", raw,
                      {"Content-Type":"application/json","X-Hub-Signature-256":"sha256=deadbeef"})
    assert st == 403


# ── despachar(): transportes AO VIVO (boundary de rede mockado) ──────────────

class _FakeSMTP:
    enviados = []
    def __init__(self, host, port, timeout=None): _FakeSMTP.host = host
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self): pass
    def login(self, u, p): _FakeSMTP.login_user = u
    def send_message(self, msg): _FakeSMTP.enviados.append(msg)


def _cfg_email(mp):
    mp.setenv("ORIZON_SMTP_HOST","smtp.x"); mp.setenv("ORIZON_SMTP_PORT","587")
    mp.setenv("ORIZON_SMTP_USER","u@x"); mp.setenv("ORIZON_SMTP_PASS","p")
    mp.setenv("ORIZON_SMTP_FROM","sac@loja.com")


def test_despachar_email_smtp(app_db, seed, monkeypatch):
    import mod_chat_externo as ext, smtplib
    _cfg_email(monkeypatch)
    _FakeSMTP.enviados = []
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    env = ext.EnvioExterno(mensagem_id=1, meio="email", direcao="saida", canal="comercial",
                           destino="cliente@ex.com", status="enfileirado")
    ok, idext, erro = ext.despachar(env, "corpo do e-mail")
    assert ok and erro is None and idext                      # Message-ID gerado
    m = _FakeSMTP.enviados[-1]
    assert m["To"] == "cliente@ex.com" and m["From"] == "sac@loja.com"
    assert "corpo do e-mail" in m.get_content()


def test_despachar_email_from_por_canal(app_db, seed, monkeypatch):
    import mod_chat_externo as ext, smtplib
    _cfg_email(monkeypatch)
    monkeypatch.setenv("ORIZON_SMTP_FROM_FINANCEIRO", "financeiro@loja.com")  # override por canal
    _FakeSMTP.enviados = []; monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    env = ext.EnvioExterno(mensagem_id=1, meio="email", canal="financeiro",
                           destino="x@y.z", status="enfileirado")
    ok, _i, _e = ext.despachar(env, "oi")
    assert ok and _FakeSMTP.enviados[-1]["From"] == "financeiro@loja.com"


def test_despachar_whatsapp_meta(app_db, seed, monkeypatch):
    import mod_chat_externo as ext, urllib.request, json, io
    monkeypatch.setenv("ORIZON_WA_TOKEN","tok123"); monkeypatch.setenv("ORIZON_WA_PHONE_ID","999")
    capt = {}
    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def fake_urlopen(req, timeout=None):
        capt["url"]=req.full_url; capt["auth"]=req.get_header("Authorization")
        capt["data"]=json.loads(req.data.decode())
        return _Resp(json.dumps({"messages":[{"id":"wamid.NEW"}]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    env = ext.EnvioExterno(mensagem_id=1, meio="whatsapp", canal="comercial",
                           destino="(12) 90000-1111", status="enfileirado")
    ok, idext, erro = ext.despachar(env, "olá via zap")
    assert ok and idext == "wamid.NEW" and erro is None
    assert "999/messages" in capt["url"] and capt["auth"] == "Bearer tok123"
    assert capt["data"]["to"] == "12900001111" and capt["data"]["text"]["body"] == "olá via zap"


def test_despachar_falha_vira_erro(app_db, seed, monkeypatch):
    import mod_chat_externo as ext, smtplib
    _cfg_email(monkeypatch)
    def boom(*a, **k): raise OSError("conexão recusada")
    monkeypatch.setattr(smtplib, "SMTP", boom)
    env = ext.EnvioExterno(mensagem_id=1, meio="email", canal="comercial",
                           destino="x@y.z", status="enfileirado")
    ok, idext, erro = ext.despachar(env, "oi")
    assert ok is False and idext is None and "recusada" in erro


def test_despachar_sem_config_nao_toca_rede(app_db, seed, monkeypatch):
    import mod_chat_externo as ext
    monkeypatch.delenv("ORIZON_SMTP_HOST", raising=False)
    env = ext.EnvioExterno(mensagem_id=1, meio="email", canal="comercial",
                           destino="x@y.z", status="pendente_config")
    ok, idext, erro = ext.despachar(env, "oi")
    assert ok is False and "não configurado" in erro.lower()
