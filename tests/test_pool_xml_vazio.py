"""XML do Promob estruturalmente válido mas sem nenhum item com preço visível
(SHOWPRICE != "Y") ou quantidade > 0 não pode criar um PoolAmbiente vazio —
esse ambiente ficava preso pra sempre (PoolAmbiente nunca é deletado, só
desvinculado de orçamento) sem forma de limpar o nome.
"""
import json as _json
import urllib.request as _urllib_req


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


# Item existe mas SHOWPRICE="N" — não entra no parse (integracoes/promob_grupos.py:173)
XML_VAZIO = '''<PROJECT DESCRIPTION="Teste" DATE="01/01/2026"><CATEGORY DESCRIPTION="X"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="a" UNIT="UN" QUANTITY="1" SHOWPRICE="N">
<PRICE TABLE="100" TOTAL="100"><MARGINS><ORDER TOTAL="100"/><BUDGET TOTAL="100"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


def test_ler_xml_str_vazio_devolve_grupos_vazio():
    from integracoes.promob_grupos import ler_xml_str
    amb = ler_xml_str("vazio.xml", XML_VAZIO)
    assert amb.get("grupos") == []   # sanidade do dado de teste
    assert amb.get("total", 0.0) == 0.0


def test_upload_xml_vazio_recusa_e_nao_cria_ambiente(http_client_factory, seed, app_db):
    from datetime import datetime as _dt

    db = app_db.get_session()
    bf = app_db.Briefing(
        cliente_id=seed["cliente_l1_id"],
        projeto_nome="Proj_L1",
        data_atendimento=_dt(2026, 1, 1),
        tipo_imovel="apartamento",
        budget_declarado=50000.0,
        categoria_proposta="completo",
        data_entrega_desejada="2026-12-01",
        flexibilidade_prazo="sim",
    )
    db.add(bf); db.commit()
    antes = db.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    base = c.base
    cookie = c.cookie

    boundary = b"----TestBoundaryVazio"
    xml_bytes = XML_VAZIO.encode("utf-8")
    filename = b"VazioE2E.xml"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="xmls"; filename="' + filename + b'"\r\n'
        b"Content-Type: text/xml\r\n"
        b"\r\n"
        + xml_bytes + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )
    ct = b"multipart/form-data; boundary=" + boundary

    req = _urllib_req.Request(base + "/projetos/Proj_L1/pool", data=body, method="POST")
    req.add_header("Content-Type", ct.decode())
    if cookie:
        req.add_header("Cookie", cookie)

    try:
        resp = _urllib_req.urlopen(req, timeout=5)
        status, raw = resp.status, resp.read()
    except _urllib_req.URLError as e:
        if hasattr(e, "code"):
            status, raw = e.code, e.read()
        else:
            raise

    data = _json.loads(raw) if raw else {}
    assert data.get("ok") is False
    assert "preço" in data.get("erro", "").lower() or "item" in data.get("erro", "").lower()

    db2 = app_db.get_session()
    depois = db2.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").count()
    orfao = db2.query(app_db.PoolAmbiente).filter_by(
        projeto_id="Proj_L1", nome="VazioE2E"
    ).first()
    db2.close()
    assert depois == antes, "PoolAmbiente vazio foi criado mesmo com XML sem itens"
    assert orfao is None
