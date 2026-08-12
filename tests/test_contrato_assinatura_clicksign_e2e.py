import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
import hmac as _hmac
import hashlib as _hashlib
import urllib.request
import urllib.error
import pytest
from cryptography.fernet import Fernet
os.environ["ORIZON_FISCAL_KEY"] = Fernet.generate_key().decode()


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def _post_raw(client, path, body_bytes, headers=None):
    req = urllib.request.Request(client.base + path, data=body_bytes, method="POST")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status
    except urllib.error.HTTPError as e:
        return e.code


class _FakeClickSignClient:
    """Fake do transporte — nunca bate na rede. `envelope_id` único por instância (evita
    colisão entre Contratos de testes diferentes que reusam o mesmo projeto seed)."""
    def __init__(self):
        self._seq = 0
        self.envelope_id = None
        self.signatarios = {}

    def criar_envelope(self, nome):
        self._seq += 1
        self.envelope_id = "env-%d" % self._seq
        return self.envelope_id

    def adicionar_documento(self, envelope_id, pdf_bytes, nome_arquivo):
        self._seq += 1
        return "doc-%d" % self._seq

    def adicionar_signatario(self, envelope_id, email, nome, cpf=None):
        self._seq += 1
        signer_id = "signer-%d-%d" % (self._seq, len(self.signatarios) + 1)
        self.signatarios[signer_id] = {"email": email, "nome": nome, "signed_at": None}
        return signer_id

    def adicionar_requisito_assinatura(self, envelope_id, documento_id, signer_id, role="sign"):
        return {"ok": True}

    def adicionar_requisito_autenticacao(self, envelope_id, documento_id, signer_id, meio="email"):
        return {"ok": True}

    def ativar_envelope(self, envelope_id):
        return {"ok": True}

    def marcar_assinado(self, signer_id, ip="203.0.113.9"):
        self.signatarios[signer_id]["signed_at"] = "2026-08-11T10:00:00Z"
        self.signatarios[signer_id]["ip"] = ip

    def consultar_envelope(self, envelope_id):
        included = [{"type": "signers", "id": sid, "attributes": {
                        "email": info["email"], "name": info["nome"],
                        "signed_at": info["signed_at"], "last_seen_ip": info.get("ip", "")}}
                    for sid, info in self.signatarios.items()]
        return {"data": {"id": envelope_id, "attributes": {"status": "running"}}, "included": included}


def _instalar_config_clicksign(app_db, loja_id, webhook_secret="whs-teste"):
    from integracoes import cripto_segredos
    db = app_db.get_session()
    try:
        cfg = db.query(app_db.IntegracaoClickSign).filter_by(loja_id=loja_id).first()
        if cfg is None:
            cfg = app_db.IntegracaoClickSign(loja_id=loja_id, ambiente_ativo="sandbox")
            db.add(cfg)
        cfg.token_sandbox_enc = cripto_segredos.encrypt("tok-sandbox")
        cfg.webhook_secret_enc = cripto_segredos.encrypt(webhook_secret)
        cfg.ambiente_ativo = "sandbox"
        db.commit()
    finally:
        db.close()


def _limpar_contrato_anterior(app_db, projeto_nome):
    db = app_db.get_session()
    try:
        contrato = db.query(app_db.Contrato).filter_by(projeto_nome=projeto_nome)\
                     .order_by(app_db.Contrato.id.desc()).first()
        if contrato:
            for a in list(contrato.assinaturas):
                db.delete(a)
            contrato.status = "para_assinatura"
            contrato.assinatura_canal = "interno"
            contrato.clicksign_envelope_id = None
            contrato.clicksign_enviado_em = None
            contrato.clicksign_signatarios_json = None
            db.commit()
    finally:
        db.close()


def _garantir_email_do_consultor(app_db, login):
    db = app_db.get_session()
    try:
        u = db.query(app_db.Usuario).filter_by(login=login).first()
        u.email = "loja@teste.com"
        db.commit()
    finally:
        db.close()


def _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path,
                     email_loja="loja@teste.com", nome_loja="Loja 1",
                     email_cliente="cliente@teste.com", nome_cliente="Cliente L1",
                     cpf_cliente="11144477735"):
    import mod_clicksign, main
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, seed["contrato_l1_id"])
        pdf = tmp_path / "contrato.pdf"
        pdf.write_bytes(b"%PDF-fake")
        contrato.pdf_path = str(pdf)
        db.commit()
        main._enviar_contrato_para_clicksign(
            db, contrato, None, email_loja=email_loja, nome_loja=nome_loja,
            email_cliente=email_cliente, nome_cliente=nome_cliente, cpf_cliente=cpf_cliente)
        db.commit()
        return contrato.id
    finally:
        db.close()


def test_enviar_grava_envelope_e_signatarios(app_db, seed, monkeypatch, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, cid)
        assert contrato.assinatura_canal == "clicksign"
        assert contrato.clicksign_envelope_id == fake.envelope_id
        assert contrato.clicksign_enviado_em is not None
        signatarios = _json.loads(contrato.clicksign_signatarios_json)
        assert fake.signatarios[signatarios["loja"]["signer_id"]]["email"] == "loja@teste.com"
        assert fake.signatarios[signatarios["cliente"]["signer_id"]]["email"] == "cliente@teste.com"
    finally:
        db.close()


def test_enviar_exige_emails(app_db, seed, monkeypatch, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    with pytest.raises(ValueError, match="obrigat"):
        _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path, email_loja="")


def test_webhook_hmac_valido_reconcilia(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    webhook_secret = "segredo-webhook"
    _instalar_config_clicksign(app_db, lid, webhook_secret=webhook_secret)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, cid)
        signatarios = _json.loads(contrato.clicksign_signatarios_json)
        loja_signer_id = signatarios["loja"]["signer_id"]
        envelope_id = contrato.clicksign_envelope_id
    finally:
        db.close()
    fake.marcar_assinado(loja_signer_id)
    payload = _json.dumps({"data": {"attributes": {"envelope_id": envelope_id}}, "event": "close"}).encode()
    calc = "sha256=" + _hmac.new(webhook_secret.encode(), payload, _hashlib.sha256).hexdigest()
    c = http_client_factory()
    st = _post_raw(c, "/webhooks/clicksign", payload,
                   {"Content-Type": "application/json", "Content-Hmac": calc})
    assert st == 200
    db2 = app_db.get_session()
    try:
        c2 = db2.get(app_db.Contrato, cid)
        assert any(a.parte == "loja" for a in c2.assinaturas)
        assert c2.status == "assinado_loja"
    finally:
        db2.close()


def test_webhook_hmac_invalido_rejeita(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    webhook_secret = "segredo-webhook"
    _instalar_config_clicksign(app_db, lid, webhook_secret=webhook_secret)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path)
    db = app_db.get_session()
    try:
        envelope_id = db.get(app_db.Contrato, cid).clicksign_envelope_id
    finally:
        db.close()
    payload = _json.dumps({"data": {"attributes": {"envelope_id": envelope_id}}}).encode()
    c = http_client_factory()
    st = _post_raw(c, "/webhooks/clicksign", payload,
                   {"Content-Type": "application/json", "Content-Hmac": "sha256=deadbeef"})
    assert st == 403


def test_webhook_reentrega_idempotente(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    webhook_secret = "segredo-webhook"
    _instalar_config_clicksign(app_db, lid, webhook_secret=webhook_secret)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, cid)
        signatarios = _json.loads(contrato.clicksign_signatarios_json)
        loja_signer_id = signatarios["loja"]["signer_id"]
        envelope_id = contrato.clicksign_envelope_id
    finally:
        db.close()
    fake.marcar_assinado(loja_signer_id)
    payload = _json.dumps({"data": {"attributes": {"envelope_id": envelope_id}}}).encode()
    calc = "sha256=" + _hmac.new(webhook_secret.encode(), payload, _hashlib.sha256).hexdigest()
    c = http_client_factory()
    headers = {"Content-Type": "application/json", "Content-Hmac": calc}
    st1 = _post_raw(c, "/webhooks/clicksign", payload, headers)
    st2 = _post_raw(c, "/webhooks/clicksign", payload, headers)
    assert st1 == 200 and st2 == 200
    db2 = app_db.get_session()
    try:
        c2 = db2.get(app_db.Contrato, cid)
        assert sum(1 for a in c2.assinaturas if a.parte == "loja") == 1
    finally:
        db2.close()


def test_canal_misto_bloqueia_assinatura_interna(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/contrato/assinar",
                   {"parte": "loja", "nome": "Diretor L1", "cpf": "11144477735"})
    assert st == 400
    assert "ClickSign" in b["erro"]


def test_reconciliar_via_endpoint_verificar(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path)
    db = app_db.get_session()
    try:
        signatarios = _json.loads(db.get(app_db.Contrato, cid).clicksign_signatarios_json)
        loja_signer_id = signatarios["loja"]["signer_id"]
    finally:
        db.close()
    fake.marcar_assinado(loja_signer_id)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/contrato/clicksign/verificar")
    assert st == 200
    assert b["status"] == "assinado_loja"
