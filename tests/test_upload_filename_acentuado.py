# -*- coding: utf-8 -*-
"""Filename com acento no multipart (caso real: 'ASuíte Master.xml', Sessão 104/105).

O browser manda o filename em UTF-8 cru no Content-Disposition; o parser compat32 do
email devolve então um email.header.Header (não str) e o `.split(";")` dos parsers
estourava AttributeError — conexão morria SEM resposta e o fetch reportava
"Failed to fetch" (mesmo sintoma do teto do nginx, causa diferente). Era por isso que
'Cozinha.xml' subia e 'ASuíte Master.xml' não."""
import json as _json
import urllib.request as _urllib_req


XML_MINIMO = ('<PROJECT DESCRIPTION="Orçamento" DATE="01/01/2026"><CATEGORY DESCRIPTION="X"><ITEMS>'
              '<ITEM REFERENCE="A" DESCRIPTION="a" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">'
              # ACHADO-45 (docs/db/TAREFA_PERCURSO_0209.md): venda > CFO — o teste é sobre
              # filename acentuado, não sobre margem; valores só precisam passar no upload.
              '<PRICE TABLE="100" TOTAL="100"><MARGINS><ORDER TOTAL="80"/><BUDGET TOTAL="100"/></MARGINS></PRICE>'
              '</ITEM></ITEMS></CATEGORY></PROJECT>')


def _multipart_xmls(filename_utf8, conteudo):
    boundary = b"----AcentoBoundary"
    body = (b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="xmls"; filename="'
            + filename_utf8.encode("utf-8") + b'"\r\n'
            b"Content-Type: text/xml\r\n\r\n"
            + conteudo.encode("utf-8") + b"\r\n"
            b"--" + boundary + b"--\r\n")
    return body, "multipart/form-data; boundary=" + boundary.decode()


def test_parse_multipart_filename_acentuado(servidor):
    import main
    body, ct = _multipart_xmls("ASuíte Master.xml", XML_MINIMO)
    arquivos, campos = main._parse_multipart(body, ct)
    assert arquivos, "parser descartou o arquivo de nome acentuado"
    assert arquivos[0][0] == "ASuíte Master.xml"


def test_parse_multipart_arquivos_filename_acentuado(servidor):
    import main
    body, ct = _multipart_xmls("ASuíte Master.xml", XML_MINIMO)
    # o binário usa name= diferente; monta na mão com name="arquivo"
    body = body.replace(b'name="xmls"', b'name="arquivo"')
    arquivos, campos = main._parse_multipart_arquivos(body, ct)
    assert "arquivo" in arquivos
    assert arquivos["arquivo"][0] == "ASuíte Master.xml"


def test_pool_upload_filename_acentuado_e2e(http_client_factory, seed, app_db):
    """POST real no /pool com filename acentuado tem que responder JSON ok (não derrubar
    a conexão). Usa Proj_L2, que já tem briefing no seed."""
    c = http_client_factory()
    c.login("dir_l2", "senha123")
    assert c.cookie
    body, ct = _multipart_xmls("Suíte Acentuada É.xml", XML_MINIMO)
    req = _urllib_req.Request(c.base + "/projetos/Proj_L2/pool", data=body, method="POST")
    req.add_header("Content-Type", ct)
    req.add_header("Cookie", c.cookie)
    try:
        resp = _urllib_req.urlopen(req, timeout=10)
        status, raw = resp.status, resp.read()
    except _urllib_req.HTTPError as e:
        status, raw = e.code, e.read()
    data = _json.loads(raw)
    assert data.get("ok") is True, f"upload falhou: {data}"
    assert data.get("acao") == "criado"
    assert data["ambiente"]["nome_exibicao"].startswith("Suíte Acentuada")
