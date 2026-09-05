# -*- coding: utf-8 -*-
"""docs/db/TAREFA_BLOCO_FISCAL.md, item 4 — selo de "pronto para emitir" (DECIDIDO: BARRAR + AVISAR).

`prontidao_emitente` (ramo produto) e a nova `prontidao_destinatario` (função IRMÃ, fiscal/mod_fiscal.py)
nomeiam campo a campo o que falta — identificação/endereço do emitente, endereço do destinatário
(Cliente). As três rotas de emissão recusam (400) com a lista; `GET .../ciclo/15/nfe` devolve as
duas listas ANTES do usuário chegar no botão de emitir (selo_fiscal)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import uuid as _uuid, json as _json
import urllib.request, urllib.error
from fiscal import nfe_emissao
from integracoes.emissor_fiscal import resultado_de_focus


class FakeClient:
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH-I4",
                "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"}
    def baixar(self, caminho): return b"BYTES"


class FakeEmissor:
    def __init__(self): self.client = FakeClient()
    def emitir_nfe_produto(self, nota):
        return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _fixture_xml():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "nfe", "nfe_basica.xml"), "rb") as f:
        return f.read()


def _perfil_completo(app_db, loja_id, ambiente="homologacao"):
    from fiscal import fiscal_cripto
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    em = db.get(app_db.Emitente, loja.emitente_id) if loja.emitente_id else None
    if em is None:
        em = app_db.Emitente()
        db.add(em); db.flush()
        loja.emitente_id = em.id
    # Tudo unconditional (não só no if em is None): outro teste no mesmo arquivo pode ter
    # zerado um campo de propósito (_zera_campo_emitente) — este helper sempre devolve o
    # emitente ao estado COMPLETO, não importa o que rodou antes.
    em.cnpj = "90000000000%02d" % loja_id; em.razao_social = "LOJA X"
    em.regime_tributario = "simples"; em.csosn_padrao = "102"; em.csosn_contribuinte = "101"
    em.inscricao_estadual = "123456789"; em.cfop_dentro_uf = "5102"; em.cfop_fora_uf = "6102"
    em.municipio_ibge = "3550308"; em.uf = "SP"; em.logradouro = "Rua A"; em.numero = "1"
    em.bairro = "Centro"; em.cidade = "Sao Paulo"; em.cep = "01000-000"
    em.ambiente_ativo = ambiente
    em.focus_token_homolog_enc = fiscal_cripto.encrypt("tok-homolog")
    em.focus_token_prod_enc = fiscal_cripto.encrypt("tok-prod")
    db.commit()
    eid = em.id
    db.close()
    return eid


def _cliente_endereco(app_db, cliente_id, completo=True):
    db = app_db.get_session()
    cli = db.get(app_db.Cliente, cliente_id)
    if completo:
        cli.logradouro, cli.numero, cli.bairro = "Rua B", "2", "Jardim"
        cli.cidade, cli.estado, cli.cep = "Sao Paulo", "SP", "02000-000"
    else:
        cli.logradouro = cli.numero = cli.bairro = None
        cli.cidade = cli.estado = cli.cep = None
    db.commit(); db.close()


def _zera_campo_emitente(app_db, loja_id, campo):
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    em = db.get(app_db.Emitente, loja.emitente_id)
    setattr(em, campo, None)
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


def test_get_ciclo15_nfe_selo_fiscal_completo_e_none(http_client_factory, seed, app_db, projetos_dir):
    loja_id = seed["loja2_id"]; proj = seed["projeto_l2"]
    _perfil_completo(app_db, loja_id)
    _cliente_endereco(app_db, seed["cliente_l2_id"], completo=True)
    c = _login(http_client_factory, "dir_l2")
    st, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st == 200 and g["ok"] is True, g
    assert g["selo_fiscal"]["emitente_produto"] is None
    assert g["selo_fiscal"]["destinatario"] is None


def test_get_ciclo15_nfe_selo_fiscal_nomeia_falta_do_emitente(http_client_factory, seed, app_db, projetos_dir):
    loja_id = seed["loja2_id"]; proj = seed["projeto_l2"]
    _perfil_completo(app_db, loja_id)
    _cliente_endereco(app_db, seed["cliente_l2_id"], completo=True)
    _zera_campo_emitente(app_db, loja_id, "csosn_contribuinte")
    c = _login(http_client_factory, "dir_l2")
    st, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st == 200
    assert g["selo_fiscal"]["emitente_produto"] and "CSOSN contribuinte" in g["selo_fiscal"]["emitente_produto"]
    assert g["selo_fiscal"]["destinatario"] is None   # os dois são independentes


def test_get_ciclo15_nfe_selo_fiscal_nomeia_falta_do_destinatario(http_client_factory, seed, app_db, projetos_dir):
    loja_id = seed["loja2_id"]; proj = seed["projeto_l2"]
    _perfil_completo(app_db, loja_id)
    _cliente_endereco(app_db, seed["cliente_l2_id"], completo=False)
    c = _login(http_client_factory, "dir_l2")
    st, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st == 200
    assert g["selo_fiscal"]["emitente_produto"] is None
    assert g["selo_fiscal"]["destinatario"] and "logradouro" in g["selo_fiscal"]["destinatario"]


def test_emitir_nfe_barra_com_emitente_incompleto(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    loja_id = seed["loja2_id"]; proj = seed["projeto_l2"]
    _perfil_completo(app_db, loja_id)
    _cliente_endereco(app_db, seed["cliente_l2_id"], completo=True)
    _reset15(app_db, proj)
    _zera_campo_emitente(app_db, loja_id, "cnpj")
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 400, b
    assert "CNPJ" in b["erro"] and "identificação" in b["erro"]


def test_emitir_nfe_barra_com_destinatario_incompleto(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    loja_id = seed["loja2_id"]; proj = seed["projeto_l2"]
    _perfil_completo(app_db, loja_id)
    _cliente_endereco(app_db, seed["cliente_l2_id"], completo=False)
    _reset15(app_db, proj)
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 400, b
    # F2-23 (04/09): mensagem reescrita pra se explicar sozinha (ACHADO-51, "recusas precisam se
    # explicar sozinhas") — "endereço do destinatário", não mais "endereço do cliente".
    assert "endereço do destinatário" in b["erro"] and "logradouro" in b["erro"]


def test_emitir_nfe_passa_com_tudo_completo(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    loja_id = seed["loja2_id"]; proj = seed["projeto_l2"]
    _perfil_completo(app_db, loja_id)
    _cliente_endereco(app_db, seed["cliente_l2_id"], completo=True)
    _reset15(app_db, proj)
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["ok"] is True, b
