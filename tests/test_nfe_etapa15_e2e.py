import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import uuid as _uuid, json as _json
import urllib.request, urllib.error
from fiscal import nfe_emissao
from integracoes.emissor_fiscal import resultado_de_focus


class FakeClient:
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH-15",
                "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"}
    def aguardar_processamento_nfse(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CHS-15", "numero": "9", "serie": "1",
                "caminho_xml_nota_fiscal": "/nfse/x.xml", "url": "/nfse/nota.pdf"}
    def baixar(self, caminho): return b"BYTES"


class FakeEmissor:
    def __init__(self): self.client = FakeClient(); self.nota_recebida = None; self.nota_nfse = None
    def emitir_nfe_produto(self, nota):
        self.nota_recebida = nota
        return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})
    def emitir_nfse_servico(self, nota):
        self.nota_nfse = nota
        return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})
    def consultar_status(self, ref):
        return resultado_de_focus({"ref": ref, "status": "autorizado", "chave_nfe": "CH-15",
                                   "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})
    def cancelar(self, ref, justificativa):
        return resultado_de_focus({"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _fixture_xml():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "nfe", "nfe_basica.xml"), "rb") as f:
        return f.read()


def _perfil(app_db, loja_id, ambiente="homologacao"):
    """Garante que a loja tem um Emitente próprio (o do seed) com o ambiente pedido e tokens,
    e que loja.emitente_id aponta para ele. A emissão resolve o Emitente (não o PerfilFiscal)."""
    from fiscal import fiscal_cripto
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    em = db.get(app_db.Emitente, loja.emitente_id) if loja.emitente_id else None
    if em is None:
        em = app_db.Emitente(cnpj="90000000000%02d" % loja_id, razao_social="LOJA X",
                             regime_tributario="simples", csosn_padrao="102", csosn_contribuinte="101",
                             inscricao_estadual="123456789", cfop_dentro_uf="5102", cfop_fora_uf="6102",
                             uf="SP", cidade="Sao Paulo", logradouro="Rua A", numero="1",
                             bairro="Centro", cep="01000-000")
        db.add(em); db.flush()
        loja.emitente_id = em.id
    em.ambiente_ativo = ambiente
    # Prontidão fiscal de serviço (US-42): IM + IBGE + cód. serviço + ISS preenchidos.
    em.inscricao_municipal = "322176"
    em.municipio_ibge = "3549904"
    em.cod_servico_municipio = "14.13.03"
    em.aliquota_iss = 5.0
    em.focus_token_homolog_enc = fiscal_cripto.encrypt("tok-homolog")
    em.focus_token_prod_enc = fiscal_cripto.encrypt("tok-prod")
    # Bloco fiscal item 4 (03/09, DECIDIDO: BARRAR) — prontidao_destinatario agora exige o
    # endereço do Cliente; o seed nasce só com nome/cpf, então completa aqui (só se vazio, nunca
    # sobrescreve um teste que setou de propósito).
    for cli in db.query(app_db.Cliente).filter_by(loja_id=loja_id).all():
        if not (cli.logradouro or "").strip():
            cli.logradouro, cli.numero, cli.bairro = "Rua do Cliente", "10", "Centro"
            cli.cidade, cli.estado, cli.cep = "Sao Paulo", "SP", "01000-000"
    db.commit(); db.close()


def _sem_emitente(app_db, loja_id):
    """Remove qualquer emitente resolvível para a loja (self, override de loja, default de rede)
    → resolver_emitente lança ValueError e o endpoint responde 400."""
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    db.query(app_db.PerfilEmissao).filter_by(owner_tipo="loja", owner_id=loja_id).delete()
    if loja.rede_id is not None:
        db.query(app_db.PerfilEmissao).filter_by(owner_tipo="rede", owner_id=loja.rede_id).delete()
    loja.emitente_id = None
    db.commit(); db.close()


def _reset15(app_db, proj):
    db = app_db.get_session()
    # documento_fiscal.xml_doc_id/danfe_doc_id/fabrica_doc_id são FK reais pra ciclo_documentos.id —
    # tem que apagar o FILHO (documento_fiscal) antes do PAI (ciclo_documentos), senão viola FK
    # (Postgres valida; SQLite não, por isso a ordem errada nunca deu erro até agora).
    db.query(app_db.DocumentoFiscal).filter_by(projeto_nome=proj).delete()
    # Faixas de evento da conversa (spec chat 2026-07-31) também seguram o doc por FK
    # (documento_ref_id) — desreferencia antes (delete é limpeza de teste; produção é append-only).
    ids = [d.id for d in db.query(app_db.CicloDocumento)
           .filter_by(projeto_nome=proj, etapa_codigo="15").all()]
    if ids:
        (db.query(app_db.ConversaMensagem)
           .filter(app_db.ConversaMensagem.documento_ref_id.in_(ids))
           .update({"documento_ref_id": None}, synchronize_session=False))
    db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").delete()
    # ACHADO-18 (docs/db/TAREFA_ACHADO18.md, passo 9): emitir-nfe agora recusa projeto sem valor
    # contratado. A maioria dos testes deste arquivo testa OUTRA coisa (emitente, idempotência,
    # IE...) e nunca dá valor ao orçamento — dá aqui, uma vez só, sem sobrescrever o que um teste
    # já tiver fixado explicitamente (ex.: test_face_fiscal_alinhada_a_segmentacao).
    contrato = db.query(app_db.Contrato).filter_by(projeto_nome=proj).order_by(app_db.Contrato.id.desc()).first()
    if contrato is not None:
        orc = db.get(app_db.Orcamento, contrato.orcamento_id)
        if orc is not None and not (orc.valor_total or 0) > 0:
            # ACHADO-02 (docs/db/TAREFA_ACHADO02_03.md, passo 10): a segmentação da NF-e/NFS-e
            # agora fatura o VAVO, não o Val_Cont cheio — sem custo financeiro nenhum modelado
            # aqui, VAVO == valor_total (cust_fin = 0), como um projeto à vista teria.
            orc.valor_total = 100000.0
            orc.vavo = 100000.0
    db.commit(); db.close()


def _upload_xml(c, proj, data):
    boundary = "----t" + _uuid.uuid4().hex
    parts = [("--"+boundary+"\r\n").encode(),
             (f'Content-Disposition: form-data; name="arquivo"; filename="fabrica.xml"\r\n').encode(),
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


def test_upload_nfe_fabrica_e_estado(http_client_factory, seed, app_db, projetos_dir):
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _upload_xml(c, proj, _fixture_xml())
    assert st == 200 and b.get("documento_id"), b
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st2 == 200 and g["ok"] is True
    assert len(g["fabrica_xmls"]) == 1 and g["fabrica_xmls"][0]["emissao"] is None


def test_upload_nfe_fabrica_perm_403(http_client_factory, seed, app_db, projetos_dir):
    c = _login(http_client_factory, "cons_l1")     # sem editar_dados_loja
    st, _ = _upload_xml(c, seed["projeto_l1"], _fixture_xml())
    assert st == 403


def test_get_nfe_nao_autenticado_401(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory()
    st, _ = c.get(f"/api/projetos/{seed['projeto_l2']}/ciclo/15/nfe")
    assert st == 401


def _upload_sem_arquivo(c, proj):
    boundary = "----t" + _uuid.uuid4().hex
    parts = [("--"+boundary+"\r\n").encode(),
             (f'Content-Disposition: form-data; name="dummy"\r\n\r\n').encode(),
             b"x\r\n", ("--"+boundary+"--\r\n").encode()]
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/15/nfe-fabrica",
                                 data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary="+boundary)
    req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def test_upload_sem_arquivo_400(http_client_factory, seed, app_db, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    st, _ = _upload_sem_arquivo(c, seed["projeto_l2"])
    assert st == 400


def test_upload_projeto_de_outra_loja_404(http_client_factory, seed, app_db, projetos_dir):
    # diretor da loja2 (tem editar_dados_loja) tentando a etapa 15 de um projeto da loja1
    c = _login(http_client_factory, "dir_l2")
    st, _ = _upload_xml(c, seed["projeto_l1"], _fixture_xml())
    assert st == 404


def _post(c, path, body):
    import urllib.request, urllib.error, json as J
    req = urllib.request.Request(c.base + path, data=J.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if c.cookie: req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, J.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, J.loads(e.read() or b"{}")


def _set_cliente_dest(app_db, proj, tipo_dest, ie, cnpj="12.345.678/0001-90"):
    """Ajusta o Cliente do projeto para um dado tipo_dest / IE (para os testes de contribuinte)."""
    db = app_db.get_session()
    p = db.query(app_db.Projeto).filter_by(nome_safe=proj).first()
    cli = db.get(app_db.Cliente, p.cliente_id)
    cli.tipo_dest = tipo_dest
    cli.inscricao_estadual = ie
    cli.cnpj = cnpj
    db.commit(); db.close()


def _get_cliente_ie(app_db, proj):
    db = app_db.get_session()
    p = db.query(app_db.Projeto).filter_by(nome_safe=proj).first()
    ie = db.get(app_db.Cliente, p.cliente_id).inscricao_estadual
    db.close()
    return ie


def test_emitir_contribuinte_sem_ie_no_body_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """Cliente contribuinte sem IE cadastrada e sem `ie` no body → 400 citando Inscrição Estadual;
    a emissão não ocorre (emissor mockado captura nada)."""
    FakeEmissorCaptura._ultima.clear()
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissorCaptura())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    _set_cliente_dest(app_db, proj, "contribuinte", None)
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 400, b
    assert "inscrição estadual" in b.get("erro", "").lower()
    assert "nota" not in FakeEmissorCaptura._ultima   # emissão não chegou ao emissor
    # restaura o cliente para não afetar testes seguintes do módulo
    _set_cliente_dest(app_db, proj, "nao_contribuinte", None, cnpj=None)


def test_emitir_contribuinte_com_ie_no_body_persiste(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """Cliente contribuinte sem IE cadastrada + `ie` no body → 200 e a IE é persistida no Cliente."""
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    _set_cliente_dest(app_db, proj, "contribuinte", None)
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30, "ie": "123456"})
    assert st == 200 and b["status"] == "autorizado", b
    assert _get_cliente_ie(app_db, proj) == "123456"
    # restaura o cliente para não afetar testes seguintes do módulo
    _set_cliente_dest(app_db, proj, "nao_contribuinte", None, cnpj=None)


def test_emitir_nao_contribuinte_nao_exige_ie(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """Default (nao_contribuinte): emite normal sem exigir IE (garante que não regrediu)."""
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["status"] == "autorizado", b


def test_emitir_etapa15_autoriza_conclui(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    doc_id = up["documento_id"]
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st == 200 and b["status"] == "autorizado" and b["chave"] == "CH-15", b
    # ACHADO-54 (04/09): ref por TENTATIVA, não mais constante por doc_id — "-1" é a primeira.
    assert b["ref"] == f"NFE-{proj}-{doc_id}-1" and b["xml_doc_id"]
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="15").first()
    assert et.status == "emitida"
    db.close()
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert g["fabrica_xmls"][0]["emissao"]["status"] == "autorizado"
    st3, b3 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st3 == 200 and b3["ref"] == b["ref"]


def test_emitir_etapa15_sem_emitente_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj)
    _sem_emitente(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    dbx = app_db.get_session()
    d = app_db.CicloDocumento(projeto_nome=proj, etapa_codigo="15", tipo="nfe_fabrica_xml",
                              arquivo_path="ciclo/15/x.xml", nome_original="x.xml")
    dbx.add(d); dbx.commit(); did = d.id; dbx.close()
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": did, "markup_pct": 30})
    assert st == 400 and "emitente" in b.get("erro", "").lower()
    # restaura o emitente da loja para não afetar testes seguintes do módulo
    _perfil(app_db, seed["loja2_id"])


def test_consultar_e_cancelar_etapa15(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    _, b_em = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    ref = b_em["ref"]   # ACHADO-54 (04/09): ref por tentativa — lê da resposta, não reconstrói
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/nfe/consultar", {"ref": ref})
    assert st == 200 and b["status"] == "autorizado"
    st2, b2 = _post(c, f"/api/projetos/{proj}/ciclo/15/nfe/cancelar", {"ref": ref, "justificativa": "cancelamento teste homologacao"})
    assert st2 == 200 and b2["status"] == "cancelado"
    # nota cancelada → etapa 15 deixa de ser conclusiva
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="15").first()
    assert et.status != "emitida"
    db.close()


def test_consultar_cancelar_cross_tenant_via_ref_404(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    # dir_l2 opera sobre o SEU projeto na URL, mas envia um ref de uma NF-e da loja1 no body → 404, sem tocar a nota alheia
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    proj2 = seed["projeto_l2"]; proj1 = seed["projeto_l1"]
    _reset15(app_db, proj2); _reset15(app_db, proj1); _perfil(app_db, seed["loja2_id"])
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="NFE-ALHEIA-1", projeto_nome=proj1, loja_id=seed["loja1_id"], status="autorizado"))
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l2")
    st, _ = _post(c, f"/api/projetos/{proj2}/ciclo/15/nfe/consultar", {"ref": "NFE-ALHEIA-1"})
    assert st == 404
    st2, _ = _post(c, f"/api/projetos/{proj2}/ciclo/15/nfe/cancelar", {"ref": "NFE-ALHEIA-1", "justificativa": "tentativa cross tenant xyz"})
    assert st2 == 404
    db = app_db.get_session()
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="NFE-ALHEIA-1").first()
    assert reg.status == "autorizado"   # a NF-e da loja1 permanece intocada
    db.close()


class FakeEmissorRejeita:
    def __init__(self): self.client = FakeClient()
    def emitir_nfe_produto(self, nota):
        return resultado_de_focus({"ref": nota["ref"], "status": "erro_autorizacao",
                                   "erros": [{"codigo": "999", "mensagem": "rejeitado"}]})


def test_emitir_rejeitada_nao_conclui_etapa(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissorRejeita())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["status"] != "autorizado"
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="15").first()
    assert et.status != "emitida"
    db.close()


class FakeEmissorCaptura:
    """Captura a nota emitida (para inspecionar o CNPJ do emitente no payload)."""
    _ultima = {}
    def __init__(self): self.client = FakeClient()
    def emitir_nfe_produto(self, nota):
        FakeEmissorCaptura._ultima["nota"] = nota
        return resultado_de_focus({"ref": nota["ref"], "status": "autorizado", "chave_nfe": "CH-MC",
                                   "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})


def test_emitir_produto_sob_emitente_central_da_rede(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """Multi-CNPJ: loja com Emitente próprio (self) + PerfilEmissao(owner=rede, produto)→central.
    A emissão de produto deve sair sob o CNPJ da CENTRAL (não o self da loja):
    DocumentoFiscal.emitente_id == central e o payload capturado tem o CNPJ da central."""
    from fiscal import fiscal_cripto
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissorCaptura())
    FakeEmissorCaptura._ultima.clear()
    proj = seed["projeto_l2"]
    _reset15(app_db, proj)
    _perfil(app_db, seed["loja2_id"])   # garante o self-emitente da loja + tokens

    # cria o Emitente CENTRAL da rede e o PerfilEmissao(rede, produto)→central
    db = app_db.get_session()
    loja = db.get(app_db.Loja, seed["loja2_id"])
    self_eid = loja.emitente_id
    rede_id = loja.rede_id
    central = app_db.Emitente(cnpj="77777777000177", razao_social="CENTRAL DA REDE LTDA",
                              regime_tributario="simples", csosn_padrao="101", csosn_contribuinte="101",
                              inscricao_estadual="987654321", municipio_ibge="3550308",
                              cfop_dentro_uf="5102", cfop_fora_uf="6102", uf="SP",
                              cidade="Sao Paulo", logradouro="Av Central", numero="1000",
                              bairro="Centro", cep="01000-000", ambiente_ativo="homologacao",
                              focus_token_homolog_enc=fiscal_cripto.encrypt("tok-central"))
    db.add(central); db.flush()
    central_id = central.id
    db.query(app_db.PerfilEmissao).filter_by(owner_tipo="rede", owner_id=rede_id,
                                             tipo_doc="produto").delete()
    db.add(app_db.PerfilEmissao(owner_tipo="rede", owner_id=rede_id, tipo_doc="produto",
                                emitente_id=central_id))
    db.commit(); db.close()
    assert central_id != self_eid

    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["status"] == "autorizado", b

    # DocumentoFiscal gravado sob o emitente CENTRAL (≠ self da loja)
    db = app_db.get_session()
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref=b["ref"]).first()
    assert reg.emitente_id == central_id and reg.emitente_id != self_eid
    db.close()
    # o payload que foi ao emissor tem o CNPJ da central no bloco emitente
    assert FakeEmissorCaptura._ultima["nota"]["emitente"]["doc"] == "77777777000177"

    # GET nfe expõe o emitente da emissão (central)
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    emissao = g["fabrica_xmls"][0]["emissao"]
    assert emissao["emitente_cnpj"] == "77777777000177"
    assert emissao["emitente_razao"] == "CENTRAL DA REDE LTDA"

    # limpa o PerfilEmissao de rede para não afetar testes seguintes do módulo
    db = app_db.get_session()
    db.query(app_db.PerfilEmissao).filter_by(owner_tipo="rede", owner_id=rede_id,
                                             tipo_doc="produto").delete()
    db.commit(); db.close()


# ---------------------------------------------------------------------------
# NFS-e (serviço, valor manual) — POST .../ciclo/15/emitir-nfse + estado no GET
# ---------------------------------------------------------------------------

def test_emitir_nfse_autoriza_e_estado_no_get(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """valor_servico>0 → 200 autorizado; DocumentoFiscal(servico, ref=NFSE-<proj>);
    GET .../ciclo/15/nfe expõe o estado da NFS-e em g["nfse"]."""
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 200 and b["status"] == "autorizado" and b["chave"] == "CHS-15", b
    assert b["ref"] == f"NFSE-{proj}-1", b   # ref por tentativa (US-41)
    # DocumentoFiscal de serviço gravado
    db = app_db.get_session()
    reg = db.query(app_db.DocumentoFiscal).filter_by(projeto_nome=proj, tipo_documento="servico").first()
    assert reg is not None and reg.ref == f"NFSE-{proj}-1"
    db.close()
    # NFS-e autorizada conclui a etapa 15 (A14), como a NF-e de produto
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="15").first()
    assert et.status == "emitida"
    db.close()
    # GET expõe o estado da NFS-e
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st2 == 200 and g["ok"] is True
    assert g["nfse"] is not None
    assert g["nfse"]["status"] == "autorizado" and g["nfse"]["chave"] == "CHS-15"
    assert g["nfse"]["ref"] == f"NFSE-{proj}-1"


def test_emitir_nfse_valor_ausente_ou_zero_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {})
    assert st == 400, b
    st2, b2 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 0})
    assert st2 == 400, b2
    st3, b3 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": -10})
    assert st3 == 400, b3
    # nada foi emitido
    db = app_db.get_session()
    reg = db.query(app_db.DocumentoFiscal).filter_by(projeto_nome=proj, tipo_documento="servico").first()
    assert reg is None
    db.close()


def test_emitir_nfse_sem_emitente_servico_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _sem_emitente(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 400 and "emitente" in b.get("erro", "").lower(), b
    _perfil(app_db, seed["loja2_id"])   # restaura


def test_emitir_nfse_idempotente(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """2ª emissão do mesmo projeto → mesmo ref, sem re-emitir (nfe_emissao.emitir devolve o registro)."""
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 200 and b["status"] == "autorizado", b
    st2, b2 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 999})
    assert st2 == 200 and b2["ref"] == b["ref"], b2
    # continua um único DocumentoFiscal de serviço
    db = app_db.get_session()
    n = db.query(app_db.DocumentoFiscal).filter_by(projeto_nome=proj, tipo_documento="servico").count()
    assert n == 1
    db.close()


def test_emitir_nfse_consultor_403(http_client_factory, seed, app_db, projetos_dir):
    c = _login(http_client_factory, "cons_l1")   # sem editar_dados_loja
    st, _ = _post(c, f"/api/projetos/{seed['projeto_l1']}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 403


def test_emitir_nfse_nao_autenticado_401(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory()
    st, _ = _post(c, f"/api/projetos/{seed['projeto_l2']}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 401


# ---------------------------------------------------------------------------
# US-41 — NFS-e rejeitada NÃO trava a etapa (re-emissão gera RPS novo). Auditoria A4.
# ---------------------------------------------------------------------------

class _FakeClientRejeita(FakeClient):
    def aguardar_processamento_nfse(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "erro_autorizacao",
                "erros": [{"codigo": "E188", "mensagem": "Simples conflita com RET"}]}


class _FakeEmissorRejeita(FakeEmissor):
    def __init__(self):
        super().__init__(); self.client = _FakeClientRejeita()


def test_emitir_nfse_rejeitada_permite_reemitir(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    # 1ª tentativa: rejeitada → registro em 'erro', ref -1
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: _FakeEmissorRejeita())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 200 and b["status"] == "erro", b
    assert b["ref"] == f"NFSE-{proj}-1", b
    # GET mostra a última (rejeitada) — a UI libera nova emissão
    st_g, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert g["nfse"]["status"] == "erro" and g["nfse"]["ref"] == f"NFSE-{proj}-1"
    # 2ª tentativa: agora autoriza → ref NOVO (-2). NÃO fica preso no RPS morto.
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    st2, b2 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st2 == 200 and b2["status"] == "autorizado", b2
    assert b2["ref"] == f"NFSE-{proj}-2", b2
    db = app_db.get_session()
    n = db.query(app_db.DocumentoFiscal).filter_by(projeto_nome=proj, tipo_documento="servico").count()
    db.close()
    assert n == 2
    st_g2, g2 = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert g2["nfse"]["status"] == "autorizado" and g2["nfse"]["ref"] == f"NFSE-{proj}-2"
    # 3ª chamada: última já autorizada → idempotente (mesmo ref, sem novo registro)
    st3, b3 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st3 == 200 and b3["ref"] == f"NFSE-{proj}-2", b3
    db = app_db.get_session()
    n2 = db.query(app_db.DocumentoFiscal).filter_by(projeto_nome=proj, tipo_documento="servico").count()
    db.close()
    assert n2 == 2


# ---------------------------------------------------------------------------
# US-42 — prontidão fiscal do Emitente barra emissão que geraria nota errada/recusa. Auditoria A2/A3/A5.
# ---------------------------------------------------------------------------

def test_emitir_nfse_prontidao_sem_im_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    db = app_db.get_session()
    loja = db.get(app_db.Loja, seed["loja2_id"]); em = db.get(app_db.Emitente, loja.emitente_id)
    em.inscricao_municipal = None; db.commit(); db.close()
    c = _login(http_client_factory, "dir_l2")
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 400 and "Inscrição Municipal" in b.get("erro", ""), b
    _perfil(app_db, seed["loja2_id"])   # restaura IM


def test_emitir_produto_prontidao_regime_nao_simples_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    db = app_db.get_session()
    loja = db.get(app_db.Loja, seed["loja2_id"]); em = db.get(app_db.Emitente, loja.emitente_id)
    em.regime_tributario = "normal"; db.commit(); db.close()
    c = _login(http_client_factory, "dir_l2")
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": 1, "markup_pct": 30})
    assert st == 400 and "Simples" in b.get("erro", ""), b
    # restaura regime (app_db é module-scoped)
    db = app_db.get_session()
    loja = db.get(app_db.Loja, seed["loja2_id"]); em = db.get(app_db.Emitente, loja.emitente_id)
    em.regime_tributario = "simples"; db.commit(); db.close()


class _FakeClientProcessando(FakeClient):
    def aguardar_processamento_nfse(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "processando_autorizacao"}


class _FakeEmissorProcessando(FakeEmissor):
    def __init__(self):
        super().__init__(); self.client = _FakeClientProcessando()


def test_emitir_nfse_processando_idempotente(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """Enquanto a NFS-e está 'processando', um 2º POST NÃO cria nova tentativa (evita nota dupla)."""
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: _FakeEmissorProcessando())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 200 and b["status"] == "processando", b
    assert b["ref"] == f"NFSE-{proj}-1", b
    st2, b2 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st2 == 200 and b2["ref"] == f"NFSE-{proj}-1", b2   # idempotente, mesma tentativa
    db = app_db.get_session()
    n = db.query(app_db.DocumentoFiscal).filter_by(projeto_nome=proj, tipo_documento="servico").count()
    db.close()
    assert n == 1


def test_wiring_faturamento_lancado_apos_nfe_produto(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """Wiring FASE B2: NF-e de produto autorizada lança a receita da MERCADORIA (4.1.01, segmentada do
    Val_Cont), idempotente por ref. Sem adiantamento prévio → a parcela Mercadoria vai como 'a receber'.
    O evento legado `faturamento` NÃO é mais emitido no wiring.

    F2-27 (docs/db/MODELO_CONTABIL.md, ACHADO-22 fechado 05/09): entre 07/08 e 05/09 o CMV = CFO
    (5.1.01×1.1.06.06) ficava diferido até a efetivação real (razão VELHA, aposentada). Desde o
    F2-27 a NF-e VOLTA a reconhecer despesa — só que pelo PROVISIONADO INTEGRAL, SEGMENTADO
    (`mod_contabil.reconhecer_provisoes_segmento`), não mais o valor de face do documento fiscal
    ("matching pleno", esse sim extinto pra sempre). Este documento é só o de MERCADORIA — reconhece
    só a fatia mercadoria (65% default da loja) do CFO; o resto do ativo fica aberto até a NF-e/NFS-e
    de serviço."""
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    # O wiring segmentado lê Val_Cont/CFO do orçamento do contrato (loja default 65/35 sem override).
    # ACHADO-13 (faturar_segmento delta-aware, docs/db/TAREFA_ACHADO13.md): `seed` é module-scoped e
    # o passo 9 (ACHADO-18) passou a exigir valor_total>0 pra emitir — outros testes deste arquivo
    # agora emitem de verdade e já reconhecem parte da mercadoria. Não basta fixar valor_total num
    # absoluto: o Val_Cont precisa ser INCREMENTADO o bastante pra gerar +65.000,00 de mercadoria
    # AINDA NÃO reconhecida, senão esta rodada teria delta zero (mesmo padrão de
    # test_cancelar_nfe_estorna_faturamento, abaixo).
    incremento_merc_alvo = 65000.0
    val_cont_incremento = round(incremento_merc_alvo / 0.65, 2)   # 65/35 default da loja
    dbx = app_db.get_session()
    orc = dbx.get(app_db.Orcamento, seed["orcamento_l2_id"])
    orc.valor_total = round((orc.valor_total or 0) + val_cont_incremento, 2)
    orc.vavo = orc.valor_total   # sem custo financeiro modelado aqui (ACHADO-02, passo 10)
    orc.cfo = 40000.0
    dbx.commit(); dbx.close()
    # FASE D2: simula o contrato assinado — registra a venda cheia e constitui a provisão de fábrica (=CFO).
    # É pré-requisito do matching: o CMV só é reconhecido na NF-e se o ativo diferido 1.1.06.06 existir.
    import mod_contabil as _mc
    ddb = app_db.get_session()
    _ot, _oid = _mc.resolver_owner(ddb, {"loja_id": seed["loja2_id"], "rede_id": None})
    _mc.registrar_evento(ddb, _ot, _oid, "registro_venda_contrato", val_cont_incremento, projeto_id=proj, ref="venda:" + proj)
    _mc.constituir_provisoes_fechamento(ddb, _ot, _oid, proj, {"custo_fabrica": 40000.0}, ref_base="pf:" + proj)
    ddb.commit(); ddb.close()
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["status"] == "autorizado", b
    st2, d = c.get(f"/api/financeiro/lancamentos?projeto={proj}")
    assert st2 == 200, d
    lans = d["lancamentos"]
    # FASE D2: a venda cheia foi registrada em Receita a Realizar (2.1.06) no contrato, então a NF-e baixa
    # desse pool (adiantado) — a parcela Mercadoria (65% × Val_Cont) não gera "a receber".
    # ACHADO-54 (04/09): ref por tentativa — lê da resposta, não reconstrói.
    ref_merc = f"fat:{b['ref']}:adiantado"
    merc = [l for l in lans if l["ref"] == ref_merc]
    assert len(merc) == 1 and merc[0]["origem"] == "faturamento_mercadoria_adiantado"
    assert merc[0]["valor"] == 65000.0
    # F2-27: "reconhecimento_despesa_custo_fabrica" nunca existiu como origem própria (era um nome
    # do antigo "matching pleno") — a origem real é a genérica `_ORIGEM_RECONHECIMENTO_DESPESA`
    # ("efetivacao_provisao_despesa"), reusada por toda rubrica de despesa em tempo real.
    assert not [l for l in lans if l["origem"] == "reconhecimento_despesa_custo_fabrica"]
    st3, dc = c.get("/api/financeiro/contas")
    assert st3 == 200
    import mod_contabil as _mc2
    dbchk = app_db.get_session()
    ot2, oid2 = _mc2.resolver_owner(dbchk, {"loja_id": seed["loja2_id"], "rede_id": None})
    ca = dbchk.query(_mc2.Conta).filter_by(owner_tipo=ot2, owner_id=oid2, codigo="1.1.06.06").first()
    # F2-27: a NF-e de mercadoria reconhece a fatia MERCADORIA (65% default) do CFO constituído
    # (40000) — 26000 recognized, 14000 (a fatia SERVIÇO, 35%) segue aberto até a NFS-e.
    assert _mc2.saldo_conta(dbchk, ot2, oid2, ca.id) == 14000.0
    assert _mc2.total_lancado(dbchk, ot2, oid2, "5.1.01", "debito", proj) == 26000.0
    dbchk.close()
    # o evento legado 'faturamento' foi aposentado do wiring (não há lançamento com o ref antigo)
    assert not [l for l in lans if l["ref"] == f"fat:NFE-{proj}-{up['documento_id']}"]


def test_cancelar_nfe_estorna_faturamento(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """Achado Vera 2026-08-12: cancelar a NF-e não revertia a receita (4.1.01) lançada na emissão —
    a nota juridicamente inexistente continuava contabilizada. Cancelamento agora estorna as pernas
    de faturamento (mesmo padrão de estornar_rateio: lançamento invertido, ref '<original>:estorno',
    idempotente)."""
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    import mod_contabil as _mc
    def _saldo_4101():
        dbc = app_db.get_session()
        ot2, oid2 = _mc.resolver_owner(dbc, {"loja_id": seed["loja2_id"], "rede_id": None})
        conta = dbc.query(_mc.Conta).filter_by(owner_tipo=ot2, owner_id=oid2, codigo="4.1.01").first()
        s = _mc.saldo_conta(dbc, ot2, oid2, conta.id) if conta else 0.0
        dbc.close()
        return s

    # Snapshots RELATIVOS (não absolutos): `seed` é module-scoped e outros testes deste arquivo já
    # emitem NF-e no mesmo projeto/conta — a conta 4.1.01 pode chegar com saldo pré-existente.
    # ACHADO-13 (faturar_segmento agora delta-aware, docs/db/TAREFA_ACHADO13.md): não basta mais
    # fixar orc.valor_total num número absoluto — o Val_Cont desta rodada precisa ser
    # INCREMENTADO o bastante para gerar +65.000,00 de mercadoria AINDA NÃO reconhecida, senão a
    # emissão desta rodada teria delta zero (o que já foi reconhecido por outro teste do mesmo
    # arquivo não é refaturado de novo — é exatamente o comportamento que o ACHADO-13 corrigiu).
    saldo_pre_emissao = _saldo_4101()
    incremento_merc_alvo = 65000.0
    val_cont_incremento = round(incremento_merc_alvo / 0.65, 2)   # 65/35 default da loja
    dbx = app_db.get_session()
    orc = dbx.get(app_db.Orcamento, seed["orcamento_l2_id"])
    orc.valor_total = round((orc.valor_total or 0) + val_cont_incremento, 2)
    orc.vavo = orc.valor_total   # sem custo financeiro modelado aqui (ACHADO-02, passo 10)
    orc.cfo = 40000.0
    dbx.commit(); dbx.close()
    ddb = app_db.get_session()
    _ot, _oid = _mc.resolver_owner(ddb, {"loja_id": seed["loja2_id"], "rede_id": None})
    _mc.registrar_evento(ddb, _ot, _oid, "registro_venda_contrato", val_cont_incremento,
                         projeto_id=proj, ref="venda:" + proj + ":cancel-teste")
    _mc.constituir_provisoes_fechamento(ddb, _ot, _oid, proj, {"custo_fabrica": 40000.0},
                                       ref_base="pf:" + proj + ":cancel-teste")
    ddb.commit(); ddb.close()
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["status"] == "autorizado", b
    ref = b["ref"]   # ACHADO-54 (04/09): ref por tentativa — lê da resposta, não reconstrói

    saldo_antes = _saldo_4101()
    assert saldo_antes - saldo_pre_emissao == 65000.0   # receita (crédito) da parcela Mercadoria

    st3, b3 = _post(c, f"/api/projetos/{proj}/ciclo/15/nfe/cancelar",
                    {"ref": ref, "justificativa": "cancelamento teste homologacao"})
    assert st3 == 200 and b3["status"] == "cancelado", b3

    st4, d4 = c.get(f"/api/financeiro/lancamentos?projeto={proj}")
    lans = d4["lancamentos"]
    estornos = [l for l in lans if (l["ref"] or "").endswith(":estorno")]
    assert estornos, "cancelamento deveria ter gerado lançamento(s) de estorno"
    assert all(l["origem"] == "estorno_cancelamento_nfe" for l in estornos)

    saldo_depois = _saldo_4101()
    assert saldo_depois == saldo_pre_emissao   # receita revertida — nota cancelada não fica contabilizada

    # idempotente: cancelar de novo (FakeEmissor sempre devolve "cancelado") não duplica os estornos
    st5, b5 = _post(c, f"/api/projetos/{proj}/ciclo/15/nfe/cancelar",
                    {"ref": ref, "justificativa": "segunda tentativa"})
    assert st5 == 200 and b5["status"] == "cancelado", b5
    st6, d6 = c.get(f"/api/financeiro/lancamentos?projeto={proj}")
    estornos2 = [l for l in d6["lancamentos"] if (l["ref"] or "").endswith(":estorno")]
    assert len(estornos2) == len(estornos)


def test_face_fiscal_alinhada_a_segmentacao(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """FASE B2.3: a NF-e de produto sai com Σ itens = parcela Mercadoria (pct_merc × Val_Cont) e a
    NFS-e com valor = parcela Serviço — juntas fecham o Val_Cont, sem duplicar. O markup deixa de
    governar o total (é output do rateio); o valor informado na NFS-e é ignorado quando há contrato."""
    emissor = FakeEmissor()   # instância compartilhada p/ capturar as notas emitidas
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: emissor)
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    dbx = app_db.get_session()
    orc = dbx.get(app_db.Orcamento, seed["orcamento_l2_id"])
    orc.valor_total = 100000.0; orc.vavo = 100000.0; orc.cfo = 40000.0
    dbx.commit(); dbx.close()
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["status"] == "autorizado", b
    itens = emissor.nota_recebida["itens"]
    total_nfe = round(sum(round((it["qCom"] or 0) * (it["preco_venda_unit"] or 0), 2) for it in itens), 2)
    assert total_nfe == 65000.0     # parcela Mercadoria (65% × Val_Cont, loja default) — não custo×markup
    # NFS-e: valor = parcela Serviço, ignora o valor informado (35% × Val_Cont)
    st2, b2 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 999.0})
    assert st2 == 200 and b2["status"] == "autorizado", b2
    assert emissor.nota_nfse["servico"]["valor_servicos"] == 35000.0
    assert round(total_nfe + emissor.nota_nfse["servico"]["valor_servicos"], 2) == 100000.0   # = Val_Cont
