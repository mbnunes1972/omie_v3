import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from cryptography.fernet import Fernet
os.environ["ORIZON_FISCAL_KEY"] = Fernet.generate_key().decode()


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_get_inexistente_devolve_padrao(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    st, b = c.get(f"/api/admin/lojas/{lid}/integracao-clicksign")
    assert st == 200 and b["existe"] is False
    assert b["ambiente_ativo"] == "sandbox"
    assert b["token_sandbox_definido"] is False and b["token_producao_definido"] is False
    assert b["webhook_secret_definido"] is False


def test_put_segredos_persiste_cifrado(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    st, _ = c.put(f"/api/admin/lojas/{lid}/integracao-clicksign/segredos",
                  {"token_sandbox": "tok-sandbox-123", "webhook_secret": "whs-abc"})
    assert st == 200
    st2, b = c.get(f"/api/admin/lojas/{lid}/integracao-clicksign")
    assert b["existe"] is True
    assert b["token_sandbox_definido"] is True and b["token_producao_definido"] is False
    assert b["webhook_secret_definido"] is True
    db = app_db.get_session()
    try:
        cfg = db.query(app_db.IntegracaoClickSign).filter_by(loja_id=lid).first()
        assert cfg.token_sandbox_enc != "tok-sandbox-123"
        from integracoes import cripto_segredos
        assert cripto_segredos.decrypt(cfg.token_sandbox_enc) == "tok-sandbox-123"
    finally:
        db.close()


def test_put_segredos_none_limpa_string_vazia_mantem(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    c.put(f"/api/admin/lojas/{lid}/integracao-clicksign/segredos", {"token_sandbox": "tok-1"})
    st, b = c.get(f"/api/admin/lojas/{lid}/integracao-clicksign")
    assert b["token_sandbox_definido"] is True
    # "" mantém o valor
    c.put(f"/api/admin/lojas/{lid}/integracao-clicksign/segredos", {"token_sandbox": ""})
    st2, b2 = c.get(f"/api/admin/lojas/{lid}/integracao-clicksign")
    assert b2["token_sandbox_definido"] is True
    # None limpa
    c.put(f"/api/admin/lojas/{lid}/integracao-clicksign/segredos", {"token_sandbox": None})
    st3, b3 = c.get(f"/api/admin/lojas/{lid}/integracao-clicksign")
    assert b3["token_sandbox_definido"] is False


def test_put_ambiente_troca(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    st, b = c.put(f"/api/admin/lojas/{lid}/integracao-clicksign/ambiente", {"ambiente": "producao"})
    assert st == 200 and b["ambiente_ativo"] == "producao"
    st2, b2 = c.get(f"/api/admin/lojas/{lid}/integracao-clicksign")
    assert b2["ambiente_ativo"] == "producao"


def test_put_ambiente_invalido_rejeita(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    st, _ = c.put(f"/api/admin/lojas/{lid}/integracao-clicksign/ambiente", {"ambiente": "producaoo"})
    assert st == 400


def test_resolver_config_cai_pra_rede_sem_config_propria(app_db, seed):
    import mod_clicksign
    db = app_db.get_session()
    try:
        rede_id = seed["rede_id"]
        lid = seed["loja2_id"]
        loja = db.get(app_db.Loja, lid)
        # limpa config residual de testes anteriores no mesmo módulo (seed é module-scoped)
        db.query(app_db.IntegracaoClickSign).filter_by(loja_id=lid).delete()
        db.query(app_db.IntegracaoClickSign).filter_by(rede_id=rede_id, loja_id=None).delete()
        db.commit()
        assert mod_clicksign.resolver_config(db, loja) is None
        db.add(app_db.IntegracaoClickSign(rede_id=rede_id, ambiente_ativo="sandbox"))
        db.commit()
        achado = mod_clicksign.resolver_config(db, loja)
        assert achado is not None
        assert achado.rede_id == rede_id
        assert achado.loja_id is None
        db.add(app_db.IntegracaoClickSign(loja_id=lid, ambiente_ativo="producao"))
        db.commit()
        achado2 = mod_clicksign.resolver_config(db, loja)
        assert achado2.loja_id == lid
        assert achado2.ambiente_ativo == "producao"
    finally:
        db.close()


def test_client_de_levanta_sem_token(app_db):
    import mod_clicksign
    db = app_db.get_session()
    try:
        cfg = app_db.IntegracaoClickSign(ambiente_ativo="sandbox")
        db.add(cfg); db.commit()
        try:
            mod_clicksign.client_de(cfg)
            assert False, "deveria ter levantado ValueError"
        except ValueError as e:
            assert "access_token" in str(e)
    finally:
        db.close()
