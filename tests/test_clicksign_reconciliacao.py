import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
import pytest
from cryptography.fernet import Fernet
os.environ["ORIZON_FISCAL_KEY"] = Fernet.generate_key().decode()
os.environ["ORIZON_INTERNAL_JOB_TOKEN"] = "job-secret-teste"


def _instalar_config_clicksign(app_db, loja_id):
    from integracoes import cripto_segredos
    db = app_db.get_session()
    try:
        cfg = db.query(app_db.IntegracaoClickSign).filter_by(loja_id=loja_id).first()
        if cfg is None:
            cfg = app_db.IntegracaoClickSign(loja_id=loja_id, ambiente_ativo="sandbox")
            db.add(cfg)
        cfg.token_sandbox_enc = cripto_segredos.encrypt("tok-sandbox")
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


class _FakeClickSignClient:
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

    def adicionar_requisito_assinatura(self, *a, **k):
        return {"ok": True}

    def adicionar_requisito_autenticacao(self, *a, **k):
        return {"ok": True}

    def ativar_envelope(self, envelope_id):
        return {"ok": True}

    def marcar_assinado(self, signer_id):
        self.signatarios[signer_id]["signed_at"] = "2026-08-11T10:00:00Z"

    def consultar_envelope(self, envelope_id):
        included = [{"type": "signers", "id": sid, "attributes": {
                        "email": info["email"], "name": info["nome"],
                        "signed_at": info["signed_at"], "last_seen_ip": "203.0.113.9"}}
                    for sid, info in self.signatarios.items()]
        return {"data": {"id": envelope_id, "attributes": {}}, "included": included}


def _post_job(client, path):
    req = urllib.request.Request(client.base + path, data=b"", method="POST")
    req.add_header("X-Internal-Job-Token", "job-secret-teste")
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status, _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, _json.loads(e.read())
        except Exception:
            return e.code, None


def _enviar(app_db, seed, fake, monkeypatch, tmp_path):
    import mod_clicksign
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, seed["contrato_l1_id"])
        pdf = tmp_path / "contrato.pdf"
        pdf.write_bytes(b"%PDF-fake")
        contrato.pdf_path = str(pdf)
        db.commit()
        import main
        main._enviar_contrato_para_clicksign(
            db, contrato, None,
            email_loja="loja@teste.com", nome_loja="Loja 1",
            email_cliente="cliente@teste.com", nome_cliente="Cliente L1",
            cpf_cliente="11144477735")
        db.commit()
    finally:
        db.close()


def test_job_ignora_enviado_recentemente(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    _enviar(app_db, seed, fake, monkeypatch, tmp_path)
    c = http_client_factory()
    st, b = _post_job(c, "/internal/clicksign/reconciliar")
    assert st == 200
    assert b["contratos_verificados"] == 0


def test_job_reconcilia_pendente_antigo(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    _enviar(app_db, seed, fake, monkeypatch, tmp_path)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, seed["contrato_l1_id"])
        contrato.clicksign_enviado_em = datetime.utcnow() - timedelta(minutes=30)
        db.commit()
        signatarios = _json.loads(contrato.clicksign_signatarios_json)
        loja_signer_id = signatarios["loja"]["signer_id"]
    finally:
        db.close()
    fake.marcar_assinado(loja_signer_id)
    c = http_client_factory()
    st, b = _post_job(c, "/internal/clicksign/reconciliar")
    assert st == 200
    assert b["contratos_verificados"] == 1
    assert b["contratos_atualizados"] == 1
    db2 = app_db.get_session()
    try:
        c2 = db2.get(app_db.Contrato, seed["contrato_l1_id"])
        assert c2.status == "assinado_loja"
    finally:
        db2.close()


def test_job_sem_token_desabilitado(app_db, seed, monkeypatch, http_client_factory):
    monkeypatch.delenv("ORIZON_INTERNAL_JOB_TOKEN", raising=False)
    c = http_client_factory()
    st, _ = _post_job(c, "/internal/clicksign/reconciliar")
    assert st == 503


def test_job_token_invalido_rejeita(app_db, seed, http_client_factory):
    c = http_client_factory()
    req = urllib.request.Request(c.base + "/internal/clicksign/reconciliar", data=b"", method="POST")
    req.add_header("X-Internal-Job-Token", "token-errado")
    try:
        urllib.request.urlopen(req, timeout=5)
        status = 200
    except urllib.error.HTTPError as e:
        status = e.code
    assert status == 403
