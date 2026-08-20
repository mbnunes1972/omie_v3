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
        self.envelope_status = "running"
        self.signatarios = {}
        self.cancelados = []
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

    def adicionar_requisito_assinatura(self, envelope_id, documento_id, signer_id, role="sign"):
        return {"ok": True}

    def adicionar_requisito_autenticacao(self, envelope_id, documento_id, signer_id, meio="email"):
        return {"ok": True}

    def ativar_envelope(self, envelope_id):
        return {"ok": True}

    def marcar_assinado(self, signer_id, ip="203.0.113.9"):
        self.signatarios[signer_id]["signed_at"] = "2026-08-11T10:00:00Z"
        self.signatarios[signer_id]["ip"] = ip

    def fechar_envelope(self):
        """Achado do usuário 2026-08-20, confirmado ao vivo contra o sandbox real: a ClickSign
        NUNCA preenche `signed_at` no signer (o campo não existe de fato nessa versão da API) —
        o único sinal de conclusão é o ENVELOPE fechar. Simula esse cenário real sem tocar
        `signed_at` nenhum, pra travar contra regressão de quem só olhava signed_at."""
        self.envelope_status = "closed"

    def consultar_envelope(self, envelope_id):
        included = [{"type": "signers", "id": sid, "attributes": {
                        "email": info["email"], "name": info["nome"],
                        "signed_at": info["signed_at"], "last_seen_ip": info.get("ip", "")}}
                    for sid, info in self.signatarios.items()]
        return {"data": {"id": envelope_id, "attributes": {"status": self.envelope_status}}, "included": included}

    def cancelar_envelope(self, envelope_id):
        self.cancelados.append(envelope_id)
        return {"ok": True}

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
                     cpf_cliente="11144477735", testemunhas=None):
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
            email_cliente=email_cliente, nome_cliente=nome_cliente, cpf_cliente=cpf_cliente,
            testemunhas=testemunhas)
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


def test_enviar_com_testemunhas_registra_signatarios(app_db, seed, monkeypatch, tmp_path):
    """Achado do usuário 2026-08-17: testemunha com e-mail vira signatária digital também."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    testemunhas = [
        {"nome": "Fulano Testemunha", "cpf": "22233344455", "email": "test1@teste.com"},
        {"nome": "Beltrana Testemunha", "cpf": "66677788899", "email": "test2@teste.com"},
    ]
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path, testemunhas=testemunhas)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, cid)
        signatarios = _json.loads(contrato.clicksign_signatarios_json)
        assert "testemunha1" in signatarios and "testemunha2" in signatarios
        assert fake.signatarios[signatarios["testemunha1"]["signer_id"]]["email"] == "test1@teste.com"
        assert fake.signatarios[signatarios["testemunha2"]["signer_id"]]["email"] == "test2@teste.com"
        # 4 signatários no envelope: loja, cliente, testemunha1, testemunha2
        assert len(fake.signatarios) == 4
    finally:
        db.close()


def test_enviar_testemunha_sem_email_nao_e_convocada(app_db, seed, monkeypatch, tmp_path):
    """Testemunha sem e-mail é ignorada silenciosamente — não vira signatária, sem erro."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    testemunhas = [
        {"nome": "Fulano Testemunha", "cpf": "22233344455", "email": ""},
        {"nome": "", "cpf": "", "email": ""},
    ]
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path, testemunhas=testemunhas)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, cid)
        signatarios = _json.loads(contrato.clicksign_signatarios_json)
        assert "testemunha1" not in signatarios and "testemunha2" not in signatarios
        assert len(fake.signatarios) == 2   # só loja + cliente
    finally:
        db.close()


def test_registrar_assinatura_testemunha_nao_mexe_no_status_intermediario(app_db, seed):
    """Achado do usuário 2026-08-17: `parte` deixou de ser só loja/cliente (testemunha também
    pode assinar). Testemunha assinando primeiro não pode fazer o contrato parecer "assinado
    pelo cliente" por engano."""
    import main as _main
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, seed["contrato_l1_id"])
        contrato.status = "para_assinatura"
        db.commit()
        status = _main._registrar_assinatura_contrato(
            db, contrato, "testemunha1", "Fulano Testemunha", "22233344455", "203.0.113.5",
            seed["loja1_id"])
        assert status == "para_assinatura", "testemunha assinando não deve mudar o status intermediário"
        db.refresh(contrato)
        assert contrato.status == "para_assinatura"
        assert any(a.parte == "testemunha1" for a in contrato.assinaturas)
    finally:
        db.close()


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


def test_reconciliar_via_envelope_fechado_sem_signed_at(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Achado do usuário 2026-08-20, confirmado ao vivo contra o sandbox real: a ClickSign nunca
    preenche `signed_at` no signer — mesmo depois de ambas as partes assinarem de verdade (e-mail
    de confirmação recebido), o contrato ficava PARA SEMPRE em "para_assinatura". O único sinal
    confiável é o envelope fechar (auto_close=true só fecha quando todos os requisitos de todos
    os signatários são cumpridos) — reproduz exatamente esse cenário: nenhum signed_at, só o
    envelope fechado."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path)
    fake.fechar_envelope()
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/contrato/clicksign/verificar")
    assert st == 200
    assert b["status"] == "assinado"
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, cid)
        assert {a.parte for a in contrato.assinaturas} == {"loja", "cliente"}
    finally:
        db.close()


def test_reenviar_convite_via_endpoint(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Achado do usuário 2026-08-19: precisa dar pra reenviar o convite (cliente não recebeu/
    não achou o e-mail)."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path)
    envelope_id = fake.envelope_id
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/contrato/clicksign/reenviar")
    assert st == 200 and b.get("ok"), b
    assert fake.reenvios == [envelope_id]


def test_reenviar_convite_recusa_fora_do_canal_clicksign(app_db, seed, http_client_factory):
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/contrato/clicksign/reenviar")
    assert st == 400 and not b.get("ok")
    assert "ClickSign" in b["erro"]


class _FakeClickSignClientRejeitaNome(_FakeClickSignClient):
    """Simula a ClickSign rejeitando o nome do signatário (achado da Vera: nome de cliente com
    dígito, ex. 'Cliente P1', volta 'name não está em um formato válido')."""
    def adicionar_signatario(self, envelope_id, email, nome, cpf=None):
        from integracoes.clicksign_client import ClickSignError
        raise ClickSignError("name não está em um formato válido", status_code=422,
                             erros=[{"detail": "name não está em um formato válido"}])


def test_enviar_via_endpoint_erro_da_clicksign_vira_400_nao_500(
        app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Achado da Vera (2026-08-12/13): erro de validação de negócio OU erro remoto da própria
    ClickSign chegava ao cliente HTTP como 500 (código quebrado) em vez de 400 (a mensagem já vem
    limpa do JSON:API da ClickSign, não é um crash do servidor)."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    _garantir_email_do_consultor(app_db, "dir_l1")
    import mod_clicksign
    fake = _FakeClickSignClientRejeitaNome()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, seed["contrato_l1_id"])
        pdf = tmp_path / "contrato2.pdf"
        pdf.write_bytes(b"%PDF-fake")
        contrato.pdf_path = str(pdf)
        proj = db.query(app_db.Projeto).filter_by(nome_safe=seed["projeto_l1"]).first()
        cli = db.get(app_db.Cliente, proj.cliente_id)
        cli.email = "cliente@teste.com"
        db.commit()
    finally:
        db.close()

    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/contrato/clicksign/enviar", {})
    assert st == 400, b   # antes do fix: 500
    assert b["ok"] is False
    assert "não está em um formato válido" in b["erro"]


def test_enviar_via_endpoint_aceita_emails_editados_no_body(
        app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Achado do usuário 2026-08-17: o modal de confirmação deixa o gerente editar os e-mails
    antes de enviar — o endpoint precisa usar o que veio no body em vez do cadastro automático."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    _garantir_email_do_consultor(app_db, "dir_l1")
    import mod_clicksign
    fake = _FakeClickSignClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, seed["contrato_l1_id"])
        pdf = tmp_path / "contrato3.pdf"
        pdf.write_bytes(b"%PDF-fake")
        contrato.pdf_path = str(pdf)
        proj = db.query(app_db.Projeto).filter_by(nome_safe=seed["projeto_l1"]).first()
        cli = db.get(app_db.Cliente, proj.cliente_id)
        cli.email = "email-cadastrado@teste.com"   # deve ser IGNORADO — o body prevalece
        db.commit()
    finally:
        db.close()

    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/contrato/clicksign/enviar", {
        "email_loja": "loja-editado@teste.com",
        "email_cliente": "cliente-editado@teste.com",
        "testemunhas": [{"nome": "Test 1", "cpf": "22233344455", "email": "t1-editado@teste.com"}],
    })
    assert st == 200, b
    db2 = app_db.get_session()
    try:
        contrato2 = db2.get(app_db.Contrato, seed["contrato_l1_id"])
        signatarios = _json.loads(contrato2.clicksign_signatarios_json)
        assert fake.signatarios[signatarios["loja"]["signer_id"]]["email"] == "loja-editado@teste.com"
        assert fake.signatarios[signatarios["cliente"]["signer_id"]]["email"] == "cliente-editado@teste.com"
        assert fake.signatarios[signatarios["testemunha1"]["signer_id"]]["email"] == "t1-editado@teste.com"
        assert "testemunha2" not in signatarios
    finally:
        db2.close()


def test_get_contrato_expoe_clicksign_defaults_com_testemunhas_da_loja(
        app_db, seed, http_client_factory):
    """GET /contrato precisa devolver os defaults pro modal de confirmação — inclui as
    testemunhas cadastradas na loja (nome/CPF/e-mail)."""
    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, seed["loja1_id"])
        loja.testemunha1_nome = "Testemunha Um"
        loja.testemunha1_cpf = "22233344455"
        loja.testemunha1_email = "t1@loja.com"
        loja.testemunha2_nome = "Testemunha Dois"
        loja.testemunha2_cpf = "66677788899"
        loja.testemunha2_email = "t2@loja.com"
        db.commit()
    finally:
        db.close()

    c = _login(http_client_factory, "dir_l1")
    st, b = c.get(f"/api/projetos/{seed['projeto_l1']}/contrato")
    assert st == 200 and b["ok"], b
    defs = b["contrato"]["clicksign_defaults"]
    assert defs["testemunha1"]["email"] == "t1@loja.com"
    assert defs["testemunha1"]["nome"] == "Testemunha Um"
    assert defs["testemunha2"]["email"] == "t2@loja.com"


def test_cancelamento_leve_revisao_libera_canal_clicksign_e_notifica(
        app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Achado do usuário 2026-08-17: enviou pro ClickSign, cancelou ANTES de alguém assinar,
    escolheu "retornar para orçamento" — tentar assinar de novo ficava bloqueado com "já enviado
    pra assinatura eletrônica" (o canal ficava preso em 'clicksign' pra sempre). Também precisa
    notificar por e-mail quem já tinha recebido o convite, e tentar cancelar o envelope."""
    import main, mod_clicksign
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    emails_enviados = []
    import mod_chat_externo
    monkeypatch.setattr(mod_chat_externo, "enviar_email_simples",
                        lambda dest, assunto, corpo: emails_enviados.append((dest, assunto, corpo)))
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path,
                           testemunhas=[{"nome": "Test 1", "cpf": "22233344455",
                                        "email": "test1@teste.com"}])
    envelope_id = fake.envelope_id

    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/orcamentos/{seed['orcamento_l1_id']}/cancelamento",
                   {"login": "dir_l1", "senha": "senha123", "desfecho": "revisao"})
    assert st == 200 and d.get("ok") and d.get("status") == "em_revisao", d

    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, cid)
        assert contrato.assinatura_canal == "interno", "canal deveria liberar pra escolher de novo"
        assert contrato.clicksign_envelope_id is None
        assert contrato.clicksign_signatarios_json is None
    finally:
        db.close()

    # notificou os 3 signatários (loja/cliente/testemunha1) que tinham recebido o convite
    assert len(emails_enviados) == 3
    destinatarios = {e[0] for e in emails_enviados}
    assert destinatarios == {"loja@teste.com", "cliente@teste.com", "test1@teste.com"}
    assert all("revisão" in e[1].lower() or "revis" in e[2].lower() for e in emails_enviados)

    # tentou cancelar o envelope na ClickSign também
    assert envelope_id in fake.cancelados


def test_cancelamento_leve_cancelar_notifica_mas_nao_libera_canal(
        app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Desfecho "cancelar" (projeto travado pra sempre): também notifica quem recebeu o convite,
    mas não precisa liberar o canal — não haverá nova tentativa de assinar."""
    import main, mod_clicksign
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_contrato_anterior(app_db, seed["projeto_l1"])
    fake = _FakeClickSignClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    emails_enviados = []
    import mod_chat_externo
    monkeypatch.setattr(mod_chat_externo, "enviar_email_simples",
                        lambda dest, assunto, corpo: emails_enviados.append((dest, assunto, corpo)))
    cid = _enviar_via_fake(app_db, seed, fake, monkeypatch, tmp_path)

    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/orcamentos/{seed['orcamento_l1_id']}/cancelamento",
                   {"login": "dir_l1", "senha": "senha123", "desfecho": "cancelar"})
    assert st == 200 and d.get("ok") and d.get("status") == "cancelado", d

    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, cid)
        assert contrato.assinatura_canal == "clicksign", "registro histórico — não precisa liberar"
    finally:
        db.close()

    assert len(emails_enviados) == 2   # loja + cliente
    assert all("cancelado" in e[1].lower() for e in emails_enviados)
