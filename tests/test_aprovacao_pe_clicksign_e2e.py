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
    def __init__(self):
        self._seq = 0
        self.envelope_id = None
        self.signatarios = {}
        self.reenvios = []

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

    def marcar_assinado(self, signer_id, ip="203.0.113.9"):
        self.signatarios[signer_id]["signed_at"] = "2026-08-11T10:00:00Z"
        self.signatarios[signer_id]["ip"] = ip

    def consultar_envelope(self, envelope_id):
        included = [{"type": "signers", "id": sid, "attributes": {
                        "email": info["email"], "name": info["nome"],
                        "signed_at": info["signed_at"], "last_seen_ip": info.get("ip", "")}}
                    for sid, info in self.signatarios.items()]
        return {"data": {"id": envelope_id, "attributes": {}}, "included": included}

    def reenviar_notificacao(self, envelope_id, mensagem=None):
        self.reenvios.append(envelope_id)
        return {"ok": True}


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


def _limpar_aprovacao_anterior(app_db, projeto_nome):
    """Limpa AprovacaoPE ANTES de reconstruir — precisa deletar as assinaturas/aprovações
    antes de qualquer coisa que toque Contrato (FK aprovacoes_pe.contrato_id)."""
    db = app_db.get_session()
    try:
        for aprov in db.query(app_db.AprovacaoPE).filter_by(projeto_nome=projeto_nome).all():
            for a in list(aprov.assinaturas):
                db.delete(a)
            db.delete(aprov)
        db.commit()
    finally:
        db.close()


def _instalar_modelo_aprovacao_pe(app_db, loja_id):
    db = app_db.get_session()
    try:
        db.query(app_db.DocumentoModelo).filter_by(
            loja_id=loja_id, tipo="aprovacao_pe").delete()
        m = app_db.DocumentoModelo(loja_id=loja_id, tipo="aprovacao_pe", versao=1,
                                   corpo_md="Aprovação do projeto executivo.", ativo=1)
        db.add(m); db.commit()
    finally:
        db.close()


def _criar_aprovacao(app_db, seed, tmp_path):
    db = app_db.get_session()
    try:
        pdf = tmp_path / "aprovacao_pe.pdf"
        pdf.write_bytes(b"%PDF-fake")
        aprov = app_db.AprovacaoPE(projeto_nome=seed["projeto_l1"], contrato_id=seed["contrato_l1_id"],
                                   loja_id=seed["loja1_id"], status="para_assinatura", pdf_path=str(pdf))
        db.add(aprov); db.commit()
        return aprov.id
    finally:
        db.close()


def _enviar_via_fake(app_db, aprov_id, fake, monkeypatch,
                     email_loja="loja@teste.com", nome_loja="Loja 1",
                     email_cliente="cliente@teste.com", nome_cliente="Cliente L1",
                     cpf_cliente="11144477735"):
    import mod_clicksign, main
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    db = app_db.get_session()
    try:
        aprov = db.get(app_db.AprovacaoPE, aprov_id)
        main._enviar_aprovacao_pe_para_clicksign(
            db, aprov, None, email_loja=email_loja, nome_loja=nome_loja,
            email_cliente=email_cliente, nome_cliente=nome_cliente, cpf_cliente=cpf_cliente)
        db.commit()
    finally:
        db.close()


def test_enviar_grava_envelope_e_signatarios(app_db, seed, monkeypatch, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    aid = _criar_aprovacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, aid, fake, monkeypatch)
    db = app_db.get_session()
    try:
        aprov = db.get(app_db.AprovacaoPE, aid)
        assert aprov.assinatura_canal == "clicksign"
        assert aprov.clicksign_envelope_id == fake.envelope_id
        signatarios = _json.loads(aprov.clicksign_signatarios_json)
        assert fake.signatarios[signatarios["cliente"]["signer_id"]]["email"] == "cliente@teste.com"
    finally:
        db.close()


def test_webhook_reconcilia_aprovacao_pe(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    webhook_secret = "segredo-ap"
    _instalar_config_clicksign(app_db, lid, webhook_secret=webhook_secret)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    aid = _criar_aprovacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, aid, fake, monkeypatch)
    db = app_db.get_session()
    try:
        aprov = db.get(app_db.AprovacaoPE, aid)
        signatarios = _json.loads(aprov.clicksign_signatarios_json)
        cliente_signer_id = signatarios["cliente"]["signer_id"]
        envelope_id = aprov.clicksign_envelope_id
    finally:
        db.close()
    fake.marcar_assinado(cliente_signer_id)
    payload = _json.dumps({"data": {"attributes": {"envelope_id": envelope_id}}}).encode()
    calc = "sha256=" + _hmac.new(webhook_secret.encode(), payload, _hashlib.sha256).hexdigest()
    c = http_client_factory()
    st = _post_raw(c, "/webhooks/clicksign", payload,
                   {"Content-Type": "application/json", "Content-Hmac": calc})
    assert st == 200
    db2 = app_db.get_session()
    try:
        a2 = db2.get(app_db.AprovacaoPE, aid)
        assert any(a.parte == "cliente" for a in a2.assinaturas)
        assert a2.status == "assinado_cliente"
    finally:
        db2.close()


def test_canal_misto_bloqueia_assinatura_interna(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    aid = _criar_aprovacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, aid, fake, monkeypatch)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/aprovacao-pe/assinar",
                   {"parte": "loja", "nome": "Diretor L1", "cpf": "11144477735"})
    assert st == 400
    assert "ClickSign" in b["erro"]


def test_reconciliar_via_endpoint_verificar(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    aid = _criar_aprovacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, aid, fake, monkeypatch)
    db = app_db.get_session()
    try:
        signatarios = _json.loads(db.get(app_db.AprovacaoPE, aid).clicksign_signatarios_json)
        cliente_signer_id = signatarios["cliente"]["signer_id"]
    finally:
        db.close()
    fake.marcar_assinado(cliente_signer_id)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/aprovacao-pe/clicksign/verificar")
    assert st == 200
    assert b["status"] == "assinado_cliente"


def test_reenviar_convite_via_endpoint(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Achado do usuário 2026-08-19: precisa dar pra reenviar o convite, mesma regra do
    Contrato/Solicitação de Medição."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    aid = _criar_aprovacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, aid, fake, monkeypatch)
    envelope_id = fake.envelope_id
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/aprovacao-pe/clicksign/reenviar")
    assert st == 200 and b.get("ok"), b
    assert fake.reenvios == [envelope_id]


def test_reenviar_convite_recusa_fora_do_canal_clicksign(app_db, seed, http_client_factory, tmp_path):
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    _criar_aprovacao(app_db, seed, tmp_path)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/aprovacao-pe/clicksign/reenviar")
    assert st == 400 and not b.get("ok")
    assert "ClickSign" in b["erro"]


def test_geracao_nao_envia_mais_automaticamente_ao_clicksign(app_db, seed, http_client_factory):
    """Achado do usuário 2026-08-19: a escolha do canal (Imprimir × Assinatura ClickSign) passa a
    ser explícita — a geração não deve mais disparar o envio sozinha, mesmo com credencial
    configurada."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _instalar_modelo_aprovacao_pe(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/aprovacao-pe", {})
    assert st == 200 and b.get("ok"), b
    assert b["aprovacao"]["status"] == "para_assinatura"
    assert b["aprovacao"]["assinatura_canal"] == "interno"
    assert "clicksign_erro" not in b


def test_enviar_via_endpoint_explicito(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    _criar_aprovacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    import mod_clicksign
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/aprovacao-pe/clicksign/enviar",
                   {"email_loja": "loja@teste.com", "email_cliente": "cliente@teste.com"})
    assert st == 200 and b.get("ok"), b
    assert b["assinatura_canal"] == "clicksign"


def test_get_aprovacao_pe_expoe_defaults(app_db, seed, http_client_factory, tmp_path):
    """Achado do usuário 2026-08-19: mesmos defaults do Contrato/Solicitação de Medição — o GET
    precisa expor clicksign_defaults/assinatura_defaults pro frontend pré-preencher."""
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    _criar_aprovacao(app_db, seed, tmp_path)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.get(f"/api/projetos/{seed['projeto_l1']}/aprovacao-pe")
    assert st == 200 and b.get("ok"), b
    assert "clicksign_defaults" in b
    assert "assinatura_defaults" in b
    assert b["aprovacao"]["assinatura_canal"] == "interno"
