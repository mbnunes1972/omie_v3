import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import base64
import pytest
from integracoes import clicksign_client as cc


class FakeResp:
    def __init__(self, status_code, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("sem json")
        return self._json


def _client():
    return cc.ClickSignClient(access_token="Tok", base_url="https://sandbox.clicksign.com/api/v3", timeout=5)


def _capture(monkeypatch, seq):
    chamadas = []
    seq = list(seq)

    def fake_request(method, url, headers, json, timeout):
        chamadas.append({"method": method, "url": url, "headers": headers, "json": json})
        return seq.pop(0)

    monkeypatch.setattr(cc.requests, "request", fake_request)
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)
    return chamadas


def test_auth_vai_por_header_nao_query_string(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "env-1"}})])
    cli = cc.ClickSignClient(access_token="tokenAPI", base_url="https://sandbox.clicksign.com/api/v3")
    cli.criar_envelope("Contrato 1")
    assert chamadas[0]["headers"]["Authorization"] == "tokenAPI"
    assert chamadas[0]["headers"]["Content-Type"] == "application/vnd.api+json"
    assert "tokenAPI" not in (chamadas[0]["url"] or "")


def test_criar_envelope(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "env-novo"}})])
    cli = _client()
    envelope_id = cli.criar_envelope("Contrato 42")
    assert chamadas[0]["method"] == "POST"
    assert chamadas[0]["url"].endswith("/envelopes")
    assert chamadas[0]["json"]["data"]["attributes"]["name"] == "Contrato 42"
    assert envelope_id == "env-novo"


def test_adicionar_documento_manda_base64_nao_multipart(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "doc-1"}})])
    cli = _client()
    doc_id = cli.adicionar_documento("env-1", b"pdf-bytes", "contrato.pdf")
    assert chamadas[0]["url"].endswith("/envelopes/env-1/documents")
    attrs = chamadas[0]["json"]["data"]["attributes"]
    assert attrs["filename"] == "contrato.pdf"
    conteudo = attrs["content_base64"]
    assert conteudo.startswith("data:application/pdf;base64,")
    b64 = conteudo.split(",", 1)[1]
    assert base64.b64decode(b64) == b"pdf-bytes"
    assert doc_id == "doc-1"


def test_adicionar_signatario_com_cpf(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "signer-1"}})])
    cli = _client()
    signer_id = cli.adicionar_signatario("env-1", "cliente@teste.com", "Fulano", cpf="11144477735")
    assert chamadas[0]["url"].endswith("/envelopes/env-1/signers")
    attrs = chamadas[0]["json"]["data"]["attributes"]
    assert attrs["email"] == "cliente@teste.com"
    assert attrs["documentation"] == "111.444.777-35"
    assert attrs["has_documentation"] is True
    assert signer_id == "signer-1"


def test_adicionar_signatario_formata_cpf_ja_pontuado(monkeypatch):
    """Achado do usuário 2026-08-20 (VPS B): a API da ClickSign devolvia "documentation não
    está em um formato válido" mesmo com CPF de dígito verificador correto — o achado anterior
    (2026-08-19, "só aceita dígitos") estava invertido. A doc oficial
    (developers.clicksign.com/reference/api-criar-signatario) descreve o campo como "Informe o
    CPF do signatário formatado (ex: 000.000.000-00)". Normaliza a partir dos dígitos (cobre
    CPF salvo com pontuação incompleta) e reformata — nunca manda dígitos crus."""
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "signer-3"}})])
    cli = _client()
    cli.adicionar_signatario("env-1", "cliente@teste.com", "Fulano", cpf="111.444.777-35")
    attrs = chamadas[0]["json"]["data"]["attributes"]
    assert attrs["documentation"] == "111.444.777-35"
    assert attrs["has_documentation"] is True


def test_adicionar_signatario_cnpj_nao_manda_documentation(monkeypatch):
    """A API só documenta CPF (11 dígitos) neste campo — CNPJ (14 dígitos) não tem formato
    confirmado, então não manda `documentation`/vira `has_documentation=False` em vez de
    arriscar outro formato não suportado."""
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "signer-4"}})])
    cli = _client()
    cli.adicionar_signatario("env-1", "cliente@teste.com", "Empresa", cpf="12.345.678/0001-90")
    attrs = chamadas[0]["json"]["data"]["attributes"]
    assert "documentation" not in attrs
    assert attrs["has_documentation"] is False


def test_adicionar_signatario_sem_cpf(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "signer-2"}})])
    cli = _client()
    cli.adicionar_signatario("env-1", "loja@teste.com", "Loja")
    attrs = chamadas[0]["json"]["data"]["attributes"]
    assert "documentation" not in attrs
    assert attrs["has_documentation"] is False


def test_adicionar_requisito_assinatura(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "req-1"}})])
    cli = _client()
    cli.adicionar_requisito_assinatura("env-1", "doc-1", "signer-1")
    assert chamadas[0]["url"].endswith("/envelopes/env-1/requirements")
    body = chamadas[0]["json"]["data"]
    assert body["attributes"]["action"] == "agree"
    assert body["attributes"]["role"] == "sign"
    assert body["relationships"]["document"]["data"]["id"] == "doc-1"
    assert body["relationships"]["signer"]["data"]["id"] == "signer-1"


def test_adicionar_requisito_autenticacao(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "req-2"}})])
    cli = _client()
    cli.adicionar_requisito_autenticacao("env-1", "doc-1", "signer-1")
    body = chamadas[0]["json"]["data"]
    assert body["attributes"]["action"] == "provide_evidence"
    assert body["attributes"]["auth"] == "email"


def test_ativar_envelope_manda_patch_status_running(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "env-1", "attributes": {"status": "running"}}})])
    cli = _client()
    cli.ativar_envelope("env-1")
    assert chamadas[0]["method"] == "PATCH"
    assert chamadas[0]["url"].endswith("/envelopes/env-1")
    assert chamadas[0]["json"]["data"]["attributes"]["status"] == "running"


def test_consultar_envelope(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "env-1", "attributes": {"status": "running"}}, "included": []})])
    cli = _client()
    dados = cli.consultar_envelope("env-1")
    assert chamadas[0]["method"] == "GET"
    assert "/envelopes/env-1" in chamadas[0]["url"]
    assert "include=" in chamadas[0]["url"]
    assert dados["data"]["id"] == "env-1"


def test_reenviar_notificacao(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"summary": [
        {"signer_id": "s1", "notified": True}]}})])
    cli = _client()
    cli.reenviar_notificacao("env-1")
    assert chamadas[0]["method"] == "POST"
    assert chamadas[0]["url"].endswith("/envelopes/env-1/notifications")
    assert chamadas[0]["json"]["data"]["type"] == "notifications"
    assert chamadas[0]["json"]["data"]["attributes"] == {}


def test_reenviar_notificacao_com_mensagem(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {}})])
    cli = _client()
    cli.reenviar_notificacao("env-1", mensagem="Por favor, assine o quanto antes.")
    assert chamadas[0]["json"]["data"]["attributes"]["message"] == "Por favor, assine o quanto antes."


def test_registrar_webhook(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"attributes": {"secret_hmac_sha256": "abc123"}}})])
    cli = _client()
    cli.registrar_webhook("https://minhaloja.com/webhooks/clicksign")
    assert chamadas[0]["url"].endswith("/webhooks")
    assert chamadas[0]["json"]["data"]["attributes"]["endpoint"] == "https://minhaloja.com/webhooks/clicksign"


def test_erro_4xx_vira_clicksignerror(monkeypatch):
    _capture(monkeypatch, [FakeResp(422, {"errors": [{"title": "invalido", "detail": "documento inválido"}]})])
    cli = _client()
    with pytest.raises(cc.ClickSignError) as e:
        cli.criar_envelope("env-1")
    assert e.value.status_code == 422
    assert "documento inválido" in str(e.value)


def test_retry_5xx_depois_sucesso(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(500, {}), FakeResp(200, {"data": {"id": "env-1"}})])
    cli = _client()
    envelope_id = cli.criar_envelope("env-1")
    assert envelope_id == "env-1"
    assert len(chamadas) == 2


def test_retry_esgota_5xx(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(500, {}), FakeResp(500, {}), FakeResp(500, {})])
    cli = _client()
    with pytest.raises(cc.ClickSignError):
        cli.criar_envelope("env-1")
    assert len(chamadas) == 3


def test_erro_conexao_recupera(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"data": {"id": "env-1"}})])
    cli = _client()
    original = cc.requests.request
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise cc.requests.RequestException("reset")
        return original(*a, **k)

    monkeypatch.setattr(cc.requests, "request", flaky)
    envelope_id = cli.criar_envelope("env-1")
    assert envelope_id == "env-1"
    assert len(chamadas) == 1
