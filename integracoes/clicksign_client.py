"""clicksign_client.py — cliente HTTP da ClickSign (transporte puro; sem regra de negócio).

Mesmo molde de `focus_client.py`/antigo `d4sign_client.py`: retry/backoff em 429/5xx, erro
tipado, sem saber o que é "contrato" ou "aprovação de PE" — quem decide isso é a camada de
wiring (mod_clicksign.py).

Modelo de dados da ClickSign (API v3, JSON:API): um `envelope` nasce a cada envio (não é um
contêiner persistente como o "cofre" da D4Sign) → um `document` sobe em base64 pro envelope →
`signer`s são criados no envelope → cada signer precisa de DOIS `requirement`s ligando-o ao
documento (um de ação — assinar — e um de autenticação, ex. e-mail) → só então um PATCH no
envelope (`status: "running"`) dispara os convites por e-mail.

Auth: header `Authorization: <access_token>` (não Bearer). Toda requisição usa
`Content-Type`/`Accept: application/vnd.api+json` (JSON:API).

NOTA (achado do desenho, 2026-08-11): os nomes exatos de alguns campos (o campo com o `secret`
na resposta de `registrar_webhook`; a forma exata da lista de signatários/status em
`consultar_envelope`, inclusive se ela expõe o IP de quem assinou; os valores aceitos de
`action`/`auth` nos requirements) vêm de documentação pública, NÃO de teste contra o sandbox
real — o sandbox da ClickSign é autoatendido (cria conta e já usa a API, sem aprovação manual
por e-mail como a D4Sign exigia), então validar isso é rápido; ajustar aqui assim que o usuário
tiver testado contra uma conta sandbox de verdade. Rodar a suíte de testes (mock) não substitui
esse passo manual.
"""
import base64
import re
import time
import requests

_STATUS_RETRIAVEIS = frozenset({429, 500, 502, 503, 504})


class ClickSignError(Exception):
    def __init__(self, mensagem, status_code=None, erros=None):
        super().__init__(mensagem)
        self.status_code = status_code
        self.erros = erros or []


class ClickSignClient:

    def __init__(self, access_token, base_url, timeout=25, max_tentativas=3):
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_tentativas = max_tentativas

    def _headers(self):
        return {
            "Authorization": self.access_token,
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }

    def _backoff(self, tentativa, resp):
        if resp is not None:
            ra = resp.headers.get("Retry-After")
            if ra and str(ra).isdigit():
                return min(int(ra), 30)
        return min(2 ** tentativa, 8)

    def _request(self, method, path, json_body=None):
        url = self.base_url + path
        for tentativa in range(self.max_tentativas):
            ultima = tentativa == self.max_tentativas - 1
            try:
                resp = requests.request(method, url, headers=self._headers(),
                                         json=json_body, timeout=self.timeout)
            except requests.RequestException as e:
                if ultima:
                    raise ClickSignError("Falha de conexão com a ClickSign: %s" % e)
                time.sleep(self._backoff(tentativa, None))
                continue
            if resp.status_code in _STATUS_RETRIAVEIS and not ultima:
                time.sleep(self._backoff(tentativa, resp))
                continue
            try:
                dados = resp.json()
            except ValueError:
                dados = {}
            if not isinstance(dados, dict):
                dados = {"_raw": dados}
            if resp.status_code >= 400:
                erros = dados.get("errors")
                if erros:
                    msg = "; ".join(
                        e.get("detail") or e.get("title") or str(e)
                        for e in erros if isinstance(e, dict)
                    ) or str(erros)
                else:
                    msg = (resp.text or "")[:300] or "HTTP %d" % resp.status_code
                raise ClickSignError(msg, status_code=resp.status_code, erros=erros)
            dados["_http_status"] = resp.status_code
            return dados
        return None

    @staticmethod
    def _id(dados):
        """Extrai o id do recurso principal de uma resposta JSON:API (`data.id`)."""
        return (dados.get("data") or {}).get("id")

    def criar_envelope(self, nome):
        """POST /envelopes — cria o contêiner do processo de assinatura. Retorna o envelope_id."""
        body = {"data": {"type": "envelopes", "attributes": {
            "name": nome, "locale": "pt-BR", "auto_close": True}}}
        return self._id(self._request("POST", "/envelopes", json_body=body))

    def adicionar_documento(self, envelope_id, pdf_bytes, nome_arquivo):
        """POST /envelopes/{id}/documents — upload em base64 (não multipart, diferente da
        D4Sign). Retorna o documento_id."""
        conteudo = "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii")
        body = {"data": {"type": "documents", "attributes": {
            "filename": nome_arquivo, "content_base64": conteudo}}}
        return self._id(self._request("POST", "/envelopes/%s/documents" % envelope_id, json_body=body))

    def adicionar_signatario(self, envelope_id, email, nome, cpf=None):
        """POST /envelopes/{id}/signers — cadastra 1 signatário no envelope. Retorna o signer_id.
        `documentation` só aceita DÍGITOS (achado do usuário 2026-08-19: a API devolvia
        "documentation inválido" quando vinha formatado, ex. "111.444.777-35" ou CNPJ com
        pontuação — o CPF/CNPJ é gravado formatado no cadastro, então limpa aqui antes de
        enviar, não no chamador)."""
        doc_digitos = re.sub(r"\D", "", cpf or "")
        attrs = {"name": nome, "email": email, "has_documentation": bool(doc_digitos)}
        if doc_digitos:
            attrs["documentation"] = doc_digitos
        body = {"data": {"type": "signers", "attributes": attrs}}
        return self._id(self._request("POST", "/envelopes/%s/signers" % envelope_id, json_body=body))

    def adicionar_requisito_assinatura(self, envelope_id, documento_id, signer_id, role="sign"):
        """POST /envelopes/{id}/requirements — liga o signatário ao documento como parte que
        assina (`action: 'agree'`, `role: 'sign'`)."""
        body = {"data": {"type": "requirements", "attributes": {
                    "action": "agree", "role": role},
                "relationships": {
                    "document": {"data": {"type": "documents", "id": documento_id}},
                    "signer":   {"data": {"type": "signers",   "id": signer_id}},
                }}}
        return self._request("POST", "/envelopes/%s/requirements" % envelope_id, json_body=body)

    def adicionar_requisito_autenticacao(self, envelope_id, documento_id, signer_id, meio="email"):
        """POST /envelopes/{id}/requirements — exige um meio de autenticação do signatário
        antes de assinar (`action: 'provide_evidence'`, `auth: meio`)."""
        body = {"data": {"type": "requirements", "attributes": {
                    "action": "provide_evidence", "auth": meio},
                "relationships": {
                    "document": {"data": {"type": "documents", "id": documento_id}},
                    "signer":   {"data": {"type": "signers",   "id": signer_id}},
                }}}
        return self._request("POST", "/envelopes/%s/requirements" % envelope_id, json_body=body)

    def ativar_envelope(self, envelope_id):
        """PATCH /envelopes/{id} — status='running' dispara os convites por e-mail (equivalente
        ao `enviar_para_assinatura` da D4Sign)."""
        body = {"data": {"id": envelope_id, "type": "envelopes",
                          "attributes": {"status": "running"}}}
        return self._request("PATCH", "/envelopes/%s" % envelope_id, json_body=body)

    def cancelar_envelope(self, envelope_id):
        """PATCH /envelopes/{id} — status='canceled' invalida o envelope (achado do usuário
        2026-08-17: cancelar/revisar um contrato já enviado pra assinatura não pode deixar o
        convite pendente no ar). MESMO CAVEAT do resto deste cliente (ver docstring do módulo):
        o valor exato do status pra cancelar não foi confirmado contra o sandbox real — ajustar
        assim que testado. Chamador trata fail-soft (best-effort)."""
        body = {"data": {"id": envelope_id, "type": "envelopes",
                          "attributes": {"status": "canceled"}}}
        return self._request("PATCH", "/envelopes/%s" % envelope_id, json_body=body)

    def consultar_envelope(self, envelope_id):
        """GET /envelopes/{id}?include=signers,documents — status do envelope + signatários.
        Retorna o dict bruto da resposta JSON:API (`data` + `included`)."""
        return self._request("GET", "/envelopes/%s?include=signers,documents" % envelope_id)

    def registrar_webhook(self, url, eventos=None):
        """POST /webhooks — registro é por CONTA (não por envelope/documento como na D4Sign),
        chamado uma vez no setup. Retorna o dict bruto — o `secret` do HMAC vem embutido na
        resposta (nome exato do campo a confirmar contra o sandbox real)."""
        body = {"data": {"type": "webhooks", "attributes": {
            "endpoint": url,
            "events": eventos or ["upload", "close", "document_closed"],
            "status": "active",
        }}}
        return self._request("POST", "/webhooks", json_body=body)
