# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-44 — trava NO UPLOAD (pool e PE), HTTP fim a fim.

Estende o ACHADO-31: validar não é só conseguir parsear, é fechar a conta. A trava é
PROSPECTIVA — só afeta uploads novos; os arquivos já em base (12/12 dos ArquivoPE de teste do
Marcelo, medido antes de travar) continuam intocados."""
import json as _json
import urllib.request as _urllib_req
from datetime import datetime as _dt


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _criar_briefing(app_db, seed, projeto_nome):
    db = app_db.get_session()
    bf = app_db.Briefing(
        cliente_id=seed["cliente_l1_id"],
        projeto_nome=projeto_nome,
        data_atendimento=_dt(2026, 1, 1),
        tipo_imovel="apartamento",
        budget_declarado=50000.0,
        categoria_proposta="completo",
        data_entrega_desejada="2026-12-01",
        flexibilidade_prazo="sim",
    )
    db.add(bf); db.commit()
    db.close()


def _upload_pool(c, projeto_nome, filename, xml_str):
    boundary = b"----TestBoundaryAchado44"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="xmls"; filename="' + filename.encode() + b'"\r\n'
        b"Content-Type: text/xml\r\n\r\n" + xml_str.encode("utf-8") + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )
    req = _urllib_req.Request(c.base + "/projetos/" + projeto_nome + "/pool", data=body, method="POST")
    req.add_header("Content-Type", (b"multipart/form-data; boundary=" + boundary).decode())
    if c.cookie:
        req.add_header("Cookie", c.cookie)
    try:
        raw = _urllib_req.urlopen(req, timeout=5).read()
    except _urllib_req.URLError as e:
        raw = e.read() if hasattr(e, "code") else (_ for _ in ()).throw(e)
    return _json.loads(raw) if raw else {}


def _xml(order_item, budget_item, order_declarado, budget_declarado):
    return '''<PROJECT DESCRIPTION="Teste" DATE="01/01/2026">
<TOTALPRICES TABLE="0"><MARGINS>
  <ORDER VALUE="%s"/>
  <BUDGET VALUE="%s"/>
</MARGINS></TOTALPRICES>
<CATEGORY DESCRIPTION="X"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="a" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="100" TOTAL="100"><MARGINS><ORDER TOTAL="%s"/><BUDGET TOTAL="%s"/></MARGINS></PRICE>
</ITEM></ITEMS></CATEGORY></PROJECT>''' % (order_declarado, budget_declarado, order_item, budget_item)


XML_CONSISTENTE = _xml(order_item="100", budget_item="150", order_declarado="100", budget_declarado="150")
# TOTAL do item editado à mão (mesma assinatura do C1) — TOTALPRICES não foi recalculado
XML_ADULTERADO = _xml(order_item="500", budget_item="150", order_declarado="100", budget_declarado="150")


def test_pool_upload_recusa_xml_que_nao_fecha_a_conta(http_client_factory, seed, app_db):
    _criar_briefing(app_db, seed, "Proj_L1")
    db = app_db.get_session()
    antes = db.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    data = _upload_pool(c, "Proj_L1", "Adulterado.xml", XML_ADULTERADO)

    assert data.get("ok") is False
    assert "fecha a conta" in data.get("erro", "").lower()

    db2 = app_db.get_session()
    depois = db2.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").count()
    db2.close()
    assert depois == antes, "PoolAmbiente foi criado mesmo com XML que não fecha a conta"


def test_pool_upload_aceita_xml_que_fecha_a_conta(http_client_factory, seed, app_db):
    _criar_briefing(app_db, seed, "Proj_L1")
    c = _login(http_client_factory, "dir_l1")
    data = _upload_pool(c, "Proj_L1", "Integro.xml", XML_CONSISTENTE)
    assert data.get("ok") is True, data
    assert data.get("acao") == "criado"


def _proj_com_ambiente(app_db, seed, nome):
    db = app_db.get_session()
    db.add(app_db.Projeto(nome_safe=nome, loja_id=seed["loja1_id"], status="fechado"))
    pa = app_db.PoolAmbiente(projeto_id=nome, nome="A0", nome_exibicao="Amb 0",
                             xml_path="x", ambientes_json="[]")
    db.add(pa); db.flush()
    pid = pa.id
    db.commit()
    db.close()
    return pid


def test_pe_upload_recusa_xml_que_nao_fecha_a_conta(http_client_factory, seed, app_db):
    pid = _proj_com_ambiente(app_db, seed, "PE44_a")
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post_multipart("/api/projetos/PE44_a/pe/upload",
                             files={"arquivo": ("pe.xml", XML_ADULTERADO.encode("utf-8"))},
                             fields={"pool_ambiente_id": pid})
    assert b.get("ok") is False
    assert "fecha a conta" in b.get("erro", "").lower()

    db = app_db.get_session()
    reg = db.query(app_db.ArquivoPE).filter_by(projeto_nome="PE44_a", pool_ambiente_id=pid).first()
    db.close()
    assert reg is None, "ArquivoPE foi gravado mesmo com XML que não fecha a conta"


def test_pe_upload_aceita_xml_que_fecha_a_conta(http_client_factory, seed, app_db):
    pid = _proj_com_ambiente(app_db, seed, "PE44_b")
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post_multipart("/api/projetos/PE44_b/pe/upload",
                             files={"arquivo": ("pe.xml", XML_CONSISTENTE.encode("utf-8"))},
                             fields={"pool_ambiente_id": pid})
    assert b.get("ok") is True, b

    db = app_db.get_session()
    reg = db.query(app_db.ArquivoPE).filter_by(projeto_nome="PE44_b", pool_ambiente_id=pid).first()
    db.close()
    assert reg is not None and reg.valor_atualizado == 100.0
