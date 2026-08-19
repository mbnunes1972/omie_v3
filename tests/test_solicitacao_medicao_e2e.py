import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
import hmac as _hmac
import hashlib as _hashlib
import urllib.request
import urllib.error
from datetime import datetime
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


def _preparar_contrato_assinado(app_db, seed):
    """Contrato totalmente assinado (loja+cliente) — gate exigido pra gerar a solicitação
    (achado do usuário 2026-08-17: liberada só depois do contrato assinado, Frente 1)."""
    db = app_db.get_session()
    try:
        ct = db.get(app_db.Contrato, seed["contrato_l1_id"])
        ct.status = "assinado"
        db.commit()
    finally:
        db.close()


def _limpar_solicitacao_anterior(app_db, projeto_nome):
    db = app_db.get_session()
    try:
        for sol in db.query(app_db.SolicitacaoMedicao).filter_by(projeto_nome=projeto_nome).all():
            for a in list(sol.assinaturas):
                db.delete(a)
            db.delete(sol)
        db.commit()
    finally:
        db.close()


def _instalar_modelo_solicitacao(app_db, loja_id):
    db = app_db.get_session()
    try:
        db.query(app_db.DocumentoModelo).filter_by(
            loja_id=loja_id, tipo="solicitacao_medicao").delete()
        m = app_db.DocumentoModelo(loja_id=loja_id, tipo="solicitacao_medicao", versao=1,
                                   corpo_md="Solicito a medição dos ambientes: [AMBIENTES_MEDICAO]",
                                   ativo=1)
        db.add(m); db.commit()
    finally:
        db.close()


def _criar_solicitacao(app_db, seed, tmp_path):
    db = app_db.get_session()
    try:
        pdf = tmp_path / "solicitacao_medicao.pdf"
        pdf.write_bytes(b"%PDF-fake")
        sol = app_db.SolicitacaoMedicao(projeto_nome=seed["projeto_l1"], loja_id=seed["loja1_id"],
                                        status="para_assinatura", pdf_path=str(pdf))
        db.add(sol); db.commit()
        return sol.id
    finally:
        db.close()


def _enviar_via_fake(app_db, sol_id, fake, monkeypatch,
                     email_loja="loja@teste.com", nome_loja="Loja 1",
                     email_cliente="cliente@teste.com", nome_cliente="Cliente L1",
                     cpf_cliente="11144477735"):
    import mod_clicksign, main
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    db = app_db.get_session()
    try:
        sol = db.get(app_db.SolicitacaoMedicao, sol_id)
        main._enviar_solicitacao_medicao_para_clicksign(
            db, sol, None, email_loja=email_loja, nome_loja=nome_loja,
            email_cliente=email_cliente, nome_cliente=nome_cliente, cpf_cliente=cpf_cliente)
        db.commit()
    finally:
        db.close()


def test_gerar_exige_contrato_totalmente_assinado(app_db, seed, http_client_factory):
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    db = app_db.get_session()
    ct = db.get(app_db.Contrato, seed["contrato_l1_id"])
    ct.status = "para_assinatura"
    db.query(app_db.ContratoAssinatura).filter_by(contrato_id=seed["contrato_l1_id"]).delete()
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/gerar", {})
    assert st == 400 and not d.get("ok")
    assert "assinado" in d.get("erro", "").lower()


def test_gerar_exige_modelo_ativo(app_db, seed, http_client_factory):
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    _preparar_contrato_assinado(app_db, seed)
    db = app_db.get_session()
    db.query(app_db.DocumentoModelo).filter_by(
        loja_id=seed["loja1_id"], tipo="solicitacao_medicao").delete()
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/gerar", {})
    assert st == 400 and not d.get("ok")
    assert "modelo" in d.get("erro", "").lower()


def test_gerar_cria_pdf_e_grava_status(app_db, seed, http_client_factory):
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    _preparar_contrato_assinado(app_db, seed)
    _instalar_modelo_solicitacao(app_db, seed["loja1_id"])
    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/gerar", {})
    assert st == 200 and d.get("ok"), d
    assert d["solicitacao"]["status"] == "para_assinatura"
    assert d["solicitacao"]["tem_pdf"] is True

    db = app_db.get_session()
    sol = db.query(app_db.SolicitacaoMedicao).filter_by(projeto_nome=seed["projeto_l1"]).first()
    assert sol is not None and sol.pdf_path and os.path.exists(sol.pdf_path)
    assert sol.modelo_versao_id is not None
    db.close()


def test_gerar_regerar_bloqueado_apos_assinado(app_db, seed, http_client_factory):
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    _preparar_contrato_assinado(app_db, seed)
    _instalar_modelo_solicitacao(app_db, seed["loja1_id"])
    db = app_db.get_session()
    sol = app_db.SolicitacaoMedicao(projeto_nome=seed["projeto_l1"], loja_id=seed["loja1_id"],
                                    status="assinado", pdf_path="/tmp/x.pdf")
    db.add(sol); db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/gerar", {})
    assert st == 403 and not d.get("ok")


def test_assinatura_interna_conclui_etapa9_so_com_as_duas_partes(app_db, seed, http_client_factory, tmp_path):
    """Achado do usuário 2026-08-17: a etapa 9 não conclui mais no simples upload — só depois
    das DUAS assinaturas (loja+cliente) do documento gerado, mesmo padrão da etapa 7."""
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    from database import CicloEtapa
    sol_id = _criar_solicitacao(app_db, seed, tmp_path)
    db = app_db.get_session()
    db.query(CicloEtapa).filter_by(projeto_nome=seed["projeto_l1"], etapa_codigo="9").delete()
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/assinar",
                   {"parte": "loja", "nome": "Loja Teste", "cpf": "00000000000"})
    assert st == 200 and d.get("ok") and d["status"] == "assinado_loja", d

    db = app_db.get_session()
    e9 = db.query(CicloEtapa).filter_by(projeto_nome=seed["projeto_l1"], etapa_codigo="9").first()
    assert e9 is None or e9.status != "concluido", "não pode concluir com só 1 assinatura"
    db.close()

    st2, d2 = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/assinar",
                     {"parte": "cliente", "nome": "Cliente Teste", "cpf": "11111111111"})
    assert st2 == 200 and d2.get("ok") and d2["status"] == "assinado", d2

    db = app_db.get_session()
    e9 = db.query(CicloEtapa).filter_by(projeto_nome=seed["projeto_l1"], etapa_codigo="9").first()
    assert e9 is not None and e9.status == "concluido"
    db.close()


def test_assinatura_interna_recusa_com_canal_clicksign(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    sid = _criar_solicitacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, sid, fake, monkeypatch)
    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/assinar",
                   {"parte": "loja", "nome": "Diretor L1", "cpf": "11144477735"})
    assert st == 400
    assert "ClickSign" in d["erro"]


def test_enviar_grava_envelope_e_signatarios(app_db, seed, monkeypatch, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    sid = _criar_solicitacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, sid, fake, monkeypatch)
    db = app_db.get_session()
    try:
        sol = db.get(app_db.SolicitacaoMedicao, sid)
        assert sol.assinatura_canal == "clicksign"
        assert sol.clicksign_envelope_id == fake.envelope_id
        signatarios = _json.loads(sol.clicksign_signatarios_json)
        assert fake.signatarios[signatarios["cliente"]["signer_id"]]["email"] == "cliente@teste.com"
        assert fake.signatarios[signatarios["loja"]["signer_id"]]["email"] == "loja@teste.com"
    finally:
        db.close()


def test_webhook_reconcilia_solicitacao_medicao(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    webhook_secret = "segredo-sm"
    _instalar_config_clicksign(app_db, lid, webhook_secret=webhook_secret)
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    sid = _criar_solicitacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, sid, fake, monkeypatch)
    db = app_db.get_session()
    try:
        signatarios = _json.loads(db.get(app_db.SolicitacaoMedicao, sid).clicksign_signatarios_json)
        cliente_signer_id = signatarios["cliente"]["signer_id"]
        envelope_id = db.get(app_db.SolicitacaoMedicao, sid).clicksign_envelope_id
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
        s2 = db2.get(app_db.SolicitacaoMedicao, sid)
        assert any(a.parte == "cliente" for a in s2.assinaturas)
        assert s2.status == "assinado_cliente"
    finally:
        db2.close()


def test_reconciliar_via_endpoint_verificar(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    sid = _criar_solicitacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, sid, fake, monkeypatch)
    db = app_db.get_session()
    try:
        signatarios = _json.loads(db.get(app_db.SolicitacaoMedicao, sid).clicksign_signatarios_json)
        cliente_signer_id = signatarios["cliente"]["signer_id"]
    finally:
        db.close()
    fake.marcar_assinado(cliente_signer_id)
    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/clicksign/verificar")
    assert st == 200
    assert d["status"] == "assinado_cliente"


def test_reenviar_convite_via_endpoint(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Achado do usuário 2026-08-19: precisa dar pra reenviar o convite."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    sid = _criar_solicitacao(app_db, seed, tmp_path)
    fake = _FakeClickSignClient()
    _enviar_via_fake(app_db, sid, fake, monkeypatch)
    envelope_id = fake.envelope_id
    c = _login(http_client_factory, "dir_l1")
    st, d = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/clicksign/reenviar")
    assert st == 200 and d.get("ok"), d
    assert fake.reenvios == [envelope_id]


def test_get_expoe_estado_e_clicksign_defaults(app_db, seed, tmp_path, http_client_factory):
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    _criar_solicitacao(app_db, seed, tmp_path)
    c = _login(http_client_factory, "dir_l1")
    st, d = c.get(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao")
    assert st == 200 and d.get("ok"), d
    assert d["solicitacao"]["status"] == "para_assinatura"
    assert "clicksign_defaults" in d
