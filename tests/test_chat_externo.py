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
