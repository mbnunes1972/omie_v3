# -*- coding: utf-8 -*-
"""Chat do Orizon — Fatia 4 (Modo privado), spec seção 4 e decisão 8.

Contratos: privada=True cifra DE VERDADE no servidor (Fernet, chave ORIZON_CHAT_ENC_KEY do
ambiente) — o `corpo` claro NUNCA persiste; sem chave no ambiente o envio FALHA com erro
claro (nunca chave descartável, que apodreceria as mensagens no restart); metadados
(autor/natureza/etapa/destinatário/bloqueador) seguem visíveis a todos — só o TEXTO é
secreto; capacidade `ver_mensagem_privada` (master/gerencial) decide quem decripta, via
perfis.pode (respeita override de perfil customizado); quem não pode recebe a MÁSCARA fixa,
nunca o cifrado bruto."""
import pytest
from cryptography.fernet import Fernet

CHAVE_TESTE = Fernet.generate_key().decode()


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _mk_func(db, app_db, loja_id, nome_funcao, nome_pessoa):
    fn = db.query(app_db.Funcao).filter_by(loja_id=loja_id, nome=nome_funcao).first()
    if fn is None:
        fn = app_db.Funcao(loja_id=loja_id, nome=nome_funcao)
        db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja_id, nome=nome_pessoa, funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    return f


# ── capacidade ───────────────────────────────────────────────────────────────

def test_capacidade_ver_mensagem_privada():
    from auth import perfis
    assert perfis.pode("master", "ver_mensagem_privada") is True
    assert perfis.pode("gerencial", "ver_mensagem_privada") is True
    assert perfis.pode("operador", "ver_mensagem_privada") is False
    assert "ver_mensagem_privada" in perfis.CAPACIDADES          # aparece na matriz Admin


# ── criptografia (unidade) ───────────────────────────────────────────────────

def test_roundtrip_e_corpo_claro_nunca_persiste(app_db, seed, monkeypatch):
    monkeypatch.setenv("ORIZON_CHAT_ENC_KEY", CHAVE_TESTE)
    import mod_chat
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1")
    db.flush()
    m = mod_chat.enviar_mensagem(db, conv, None, "segredo da diretoria", privada=True)
    db.commit()
    assert m.privada == 1
    assert m.corpo == ""                                          # claro NUNCA persistido
    assert m.corpo_cifrado and "segredo" not in m.corpo_cifrado   # cifrado ilegível
    claro = Fernet(CHAVE_TESTE.encode()).decrypt(m.corpo_cifrado.encode()).decode()
    assert claro == "segredo da diretoria"                        # roundtrip
    db.close()


def test_sem_chave_no_ambiente_falha_com_erro_claro(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_CHAT_ENC_KEY", raising=False)
    import mod_chat
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1")
    db.flush()
    with pytest.raises(ValueError, match="Modo privado indisponível"):
        mod_chat.enviar_mensagem(db, conv, None, "segredo", privada=True)
    db.rollback()
    # mensagem NORMAL segue funcionando sem a chave
    m = mod_chat.enviar_mensagem(db, conv, None, "mensagem comum")
    assert m.corpo == "mensagem comum"
    db.rollback(); db.close()


# ── e2e: quem vê o quê ───────────────────────────────────────────────────────

def test_api_mascara_para_quem_nao_pode_e_decripta_para_gerencia(
        http_client_factory, seed, app_db, monkeypatch):
    monkeypatch.setenv("ORIZON_CHAT_ENC_KEY", CHAVE_TESTE)
    c_master = _login(http_client_factory, "dir_l1")
    st, body = c_master.post("/api/projetos/Proj_L1/conversa/mensagens",
                             {"corpo": "conteúdo confidencial da gerência", "privada": True})
    assert st == 201 and body["ok"], body
    assert body["mensagem"]["privada"] is True

    # master lê o texto claro
    st, body = c_master.get("/api/projetos/Proj_L1/conversa")
    privadas = [m for m in body["mensagens"] if m["privada"]]
    assert any(m["corpo"] == "conteúdo confidencial da gerência" for m in privadas)

    # operador vê a MÁSCARA fixa — nunca o claro, nunca o cifrado bruto
    c_op = _login(http_client_factory, "cons_l1")
    st, body = c_op.get("/api/projetos/Proj_L1/conversa")
    assert st == 200, body
    privadas = [m for m in body["mensagens"] if m["privada"]]
    assert privadas, body
    for m in privadas:
        assert "confidencial" not in m["corpo"]
        assert "gAAAA" not in m["corpo"]                          # prefixo Fernet: cifrado bruto
        assert m["corpo"].startswith("🔒 Mensagem privada")

    # banco: claro vazio, cifrado ilegível
    db = app_db.get_session()
    row = (db.query(app_db.ConversaMensagem)
             .filter(app_db.ConversaMensagem.privada == 1)
             .order_by(app_db.ConversaMensagem.id.desc()).first())
    assert row.corpo == "" and "confidencial" not in (row.corpo_cifrado or "")
    db.close()


def test_transferencia_privada_grava_v12_e_metadados_visiveis(
        http_client_factory, seed, app_db, monkeypatch):
    monkeypatch.setenv("ORIZON_CHAT_ENC_KEY", CHAVE_TESTE)
    db = app_db.get_session()
    e = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1", etapa_codigo="8").first()
    if e is None:
        db.add(app_db.CicloEtapa(projeto_nome="Proj_L1", etapa_codigo="8", status="pendente"))
    f = _mk_func(db, app_db, seed["loja1_id"], "Conferente", "Destino Privado")
    db.commit(); fid = f.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "assunto sensível", "privada": True,
                       "natureza": "transferencia", "etapa_codigo": "8",
                       "transferido_para_funcionario_id": fid})
    assert st == 201, body

    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1", etapa_codigo="8").first()
    assert et.responsavel_funcionario_id == fid       # transferência funciona MESMO privada
    db.close()

    # operador vê os METADADOS (houve transferência, pra quem, em que etapa) — só o texto não
    c_op = _login(http_client_factory, "cons_l1")
    st, body = c_op.get("/api/projetos/Proj_L1/conversa")
    m = next(m for m in body["mensagens"]
             if m["natureza"] == "transferencia" and m["privada"])
    assert m["transferido_para_nome"] == "Destino Privado"
    assert m["etapa_codigo"] == "8"
    assert m["corpo"].startswith("🔒 Mensagem privada")
