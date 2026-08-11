"""Ambiente "fantasma" no upload de XML do Promob (PoolAmbiente nunca é deletado,
só desvinculado de orçamento — um registro travado no nome fica preso pra sempre):

1. XML estruturalmente válido mas sem nenhum item com preço visível não pode
   criar um PoolAmbiente vazio.
2. Falha ao salvar o arquivo em disco não pode deixar um PoolAmbiente órfão no
   banco (storage_salvar_texto roda ANTES do commit, não depois).
"""
import json as _json
import urllib.request as _urllib_req
from datetime import datetime as _dt


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _criar_briefing(app_db, seed, projeto_nome="Proj_L1"):
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


def _upload_xml(c, projeto_nome, filename, xml_str):
    boundary = b"----TestBoundaryPool"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="xmls"; filename="' + filename.encode() + b'"\r\n'
        b"Content-Type: text/xml\r\n"
        b"\r\n"
        + xml_str.encode("utf-8") + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )
    ct = b"multipart/form-data; boundary=" + boundary
    req = _urllib_req.Request(c.base + "/projetos/" + projeto_nome + "/pool", data=body, method="POST")
    req.add_header("Content-Type", ct.decode())
    if c.cookie:
        req.add_header("Cookie", c.cookie)
    try:
        resp = _urllib_req.urlopen(req, timeout=5)
        raw = resp.read()
    except _urllib_req.URLError as e:
        if hasattr(e, "code"):
            raw = e.read()
        else:
            raise
    return _json.loads(raw) if raw else {}


# Item existe mas SHOWPRICE="N" — não entra no parse (integracoes/promob_grupos.py:173)
XML_VAZIO = '''<PROJECT DESCRIPTION="Teste" DATE="01/01/2026"><CATEGORY DESCRIPTION="X"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="a" UNIT="UN" QUANTITY="1" SHOWPRICE="N">
<PRICE TABLE="100" TOTAL="100"><MARGINS><ORDER TOTAL="100"/><BUDGET TOTAL="100"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''

# Item normal, com preço visível e quantidade válida
XML_VALIDO = '''<PROJECT DESCRIPTION="Teste" DATE="01/01/2026"><CATEGORY DESCRIPTION="X"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="a" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="100" TOTAL="100"><MARGINS><ORDER TOTAL="100"/><BUDGET TOTAL="150"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


def test_ler_xml_str_vazio_devolve_grupos_vazio():
    from integracoes.promob_grupos import ler_xml_str
    amb = ler_xml_str("vazio.xml", XML_VAZIO)
    assert amb.get("grupos") == []   # sanidade do dado de teste
    assert amb.get("total", 0.0) == 0.0


def test_upload_xml_vazio_recusa_e_nao_cria_ambiente(http_client_factory, seed, app_db):
    _criar_briefing(app_db, seed)
    db = app_db.get_session()
    antes = db.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    data = _upload_xml(c, "Proj_L1", "VazioE2E.xml", XML_VAZIO)

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


def test_falha_ao_salvar_disco_nao_cria_ambiente_orfao(http_client_factory, seed, app_db, monkeypatch):
    """storage_salvar_texto roda ANTES do db.commit() — se a escrita em disco falhar
    (disco cheio, permissão), nenhum PoolAmbiente deve ficar gravado no banco."""
    import main as _main

    def _explode(*a, **k):
        raise OSError("disco cheio (simulado)")
    monkeypatch.setattr(_main, "storage_salvar_texto", _explode)

    _criar_briefing(app_db, seed)
    db = app_db.get_session()
    antes = db.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    data = _upload_xml(c, "Proj_L1", "DiscoFalhou.xml", XML_VALIDO)

    assert data.get("ok") is False
    assert "disco cheio" in data.get("erro", "").lower()

    db2 = app_db.get_session()
    depois = db2.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").count()
    orfao = db2.query(app_db.PoolAmbiente).filter_by(
        projeto_id="Proj_L1", nome="DiscoFalhou"
    ).first()
    db2.close()
    assert depois == antes, "PoolAmbiente foi commitado mesmo com falha ao salvar o XML em disco"
    assert orfao is None
