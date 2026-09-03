# -*- coding: utf-8 -*-
"""docs/db/TAREFA_BLOCO_FISCAL.md, item 3 — o erro do Focus chega sem detalhe.

`FocusError` guarda a lista da SEFAZ em `.erros` (integracoes/focus_client.py) — as três rotas
que emitem (emitir-teste, ciclo/15/emitir-nfe, ciclo/15/emitir-nfse) faziam só
`except Exception as e: str(e)`, que mostra a mensagem e descarta a lista. Aceite: as três
devolvem `erros` no JSON quando o Focus rejeita com detalhe."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import uuid as _uuid, json as _json
import urllib.request, urllib.error
from fiscal import nfe_emissao
from integracoes.focus_client import FocusError

_ERROS_SEFAZ = [{"codigo": "228", "mensagem": "Rejeicao: Falha no Schema XML"},
                {"codigo": "999", "mensagem": "Rejeicao: CFOP invalido"}]


class FakeClient:
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        raise AssertionError("não deveria chegar aqui — emitir_nfe_produto já lançou FocusError")
    def aguardar_processamento_nfse(self, ref, timeout=60, intervalo=3):
        raise AssertionError("não deveria chegar aqui — emitir_nfse_servico já lançou FocusError")
    def baixar(self, caminho): return b"BYTES"


class FakeEmissorFocusError:
    def __init__(self): self.client = FakeClient()
    def emitir_nfe_produto(self, nota):
        raise FocusError("Rejeicao SEFAZ", status_code=422, erros=_ERROS_SEFAZ)
    def emitir_nfse_servico(self, nota):
        raise FocusError("Rejeicao prefeitura", status_code=422, erros=_ERROS_SEFAZ)


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _fixture_xml():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "nfe", "nfe_basica.xml"), "rb") as f:
        return f.read()


def _perfil(app_db, loja_id, ambiente="homologacao"):
    from fiscal import fiscal_cripto
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    em = db.get(app_db.Emitente, loja.emitente_id) if loja.emitente_id else None
    if em is None:
        em = app_db.Emitente(cnpj="90000000000%02d" % loja_id, razao_social="LOJA X",
                             regime_tributario="simples", csosn_padrao="102",
                             cfop_dentro_uf="5102", cfop_fora_uf="6102", uf="SP",
                             cidade="Sao Paulo", logradouro="Rua A", numero="1",
                             bairro="Centro", cep="01000-000")
        db.add(em); db.flush()
        loja.emitente_id = em.id
    em.ambiente_ativo = ambiente
    em.inscricao_municipal = "322176"
    em.municipio_ibge = "3549904"
    em.cod_servico_municipio = "14.13.03"
    em.aliquota_iss = 5.0
    em.focus_token_homolog_enc = fiscal_cripto.encrypt("tok-homolog")
    em.focus_token_prod_enc = fiscal_cripto.encrypt("tok-prod")
    db.commit(); db.close()


def _reset15(app_db, proj):
    db = app_db.get_session()
    db.query(app_db.DocumentoFiscal).filter_by(projeto_nome=proj).delete()
    ids = [d.id for d in db.query(app_db.CicloDocumento)
           .filter_by(projeto_nome=proj, etapa_codigo="15").all()]
    if ids:
        (db.query(app_db.ConversaMensagem)
           .filter(app_db.ConversaMensagem.documento_ref_id.in_(ids))
           .update({"documento_ref_id": None}, synchronize_session=False))
    db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").delete()
    contrato = db.query(app_db.Contrato).filter_by(projeto_nome=proj).order_by(app_db.Contrato.id.desc()).first()
    if contrato is not None:
        orc = db.get(app_db.Orcamento, contrato.orcamento_id)
        if orc is not None and not (orc.valor_total or 0) > 0:
            orc.valor_total = 100000.0
            orc.vavo = 100000.0
    db.commit(); db.close()


def _upload_xml(c, proj, data):
    boundary = "----t" + _uuid.uuid4().hex
    parts = [("--"+boundary+"\r\n").encode(),
             ('Content-Disposition: form-data; name="arquivo"; filename="fabrica.xml"\r\n').encode(),
             b"Content-Type: application/octet-stream\r\n\r\n", data, b"\r\n",
             ("--"+boundary+"--\r\n").encode()]
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/15/nfe-fabrica",
                                 data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary="+boundary)
    req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def _post(c, path, body):
    req = urllib.request.Request(c.base + path, data=_json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if c.cookie: req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def _post_multipart(base, cookie, path, fields, filename, filedata):
    boundary = "----t" + _uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(("--"+boundary+"\r\n").encode())
        parts.append((f'Content-Disposition: form-data; name="{k}"\r\n\r\n').encode())
        parts.append((str(v)+"\r\n").encode())
    parts.append(("--"+boundary+"\r\n").encode())
    parts.append((f'Content-Disposition: form-data; name="arquivo"; filename="{filename}"\r\n').encode())
    parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
    parts.append(filedata); parts.append(b"\r\n")
    parts.append(("--"+boundary+"--\r\n").encode())
    req = urllib.request.Request(base+path, data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary="+boundary)
    if cookie: req.add_header("Cookie", cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def test_emitir_teste_focus_error_devolve_lista_de_erros(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissorFocusError())
    _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, b = _post_multipart(c.base, c.cookie, f"/api/admin/lojas/{seed['loja2_id']}/nfe/emitir-teste",
                            {"projeto_nome": proj, "markup_pct": "30"}, "fabrica.xml", _fixture_xml())
    assert st == 500, b
    assert b["ok"] is False
    assert b["erros"] == _ERROS_SEFAZ, b
    assert "Rejeicao SEFAZ" in b["erro"]


def test_emitir_nfe_focus_error_devolve_lista_de_erros(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissorFocusError())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 500, b
    assert b["ok"] is False
    assert b["erros"] == _ERROS_SEFAZ, b
    assert "Rejeicao SEFAZ" in b["erro"]


def test_emitir_nfse_focus_error_devolve_lista_de_erros(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissorFocusError())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 500, b
    assert b["ok"] is False
    assert b["erros"] == _ERROS_SEFAZ, b
    assert "Rejeicao prefeitura" in b["erro"]
