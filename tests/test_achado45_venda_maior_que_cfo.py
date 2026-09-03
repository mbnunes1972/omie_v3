# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-45 — venda nunca pode ser igual ou menor que o custo de
fábrica (CFO). `budget_total` e `order_total` vêm do MESMO XML e ninguém os comparava.

DECIDIDO 02/09 (2ª rodada, corrigindo a 1ª): a regra é uma só e é POR ITEM — `budget_total >
order_total` (markup > 1) em TODO item do XML. Item com valor zero cai nesta mesma regra, não é
caso separado. Recusa dura: "Arquivo XML com erro, verifique o Promob." A quarentena existente
(`qa_selo='bloqueado'`, mod_qualidade_xml.py) NÃO é substituída — usa tolerância/limiar agregado
diferentes e continua cobrindo o que já cobria (`test_qualidade_upload_e2e.py`, fixture ajustado
pra ficar acima do novo hard-reject e ainda testar só a quarentena).

Medido antes de travar (02/09, Homologação — único ambiente com dados reais hoje): 0/795 itens
(12 ambientes) violavam a regra por item; checado também o caso de item zerado sem o ambiente
perder margem — nenhum encontrado na base real. Integração e Produção estão zeradas (feature
ainda não usada nelas). O upload de PE (`.../pe/upload`, `ArquivoPE`) recebeu a versão agregada
(`venda_maior_que_cfo`, por ambiente) — não tinha NENHUMA trava antes desta rodada."""
import json as _json
import urllib.request as _urllib_req
from datetime import datetime as _dt

import integracoes.promob_grupos as pg


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
    boundary = b"----TestBoundaryAchado45"
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


# venda (150) > CFO (100) — passa nos dois achados (44 e 45)
XML_OK = _xml(order_item="100", budget_item="150", order_declarado="100", budget_declarado="150")
# fecha a conta consigo mesmo (ACHADO-44 passa), mas venda (150) < CFO (200) — ACHADO-45 recusa
# (PE) ou quarentena (pool, ver docstring do módulo)
XML_VENDA_MENOR_QUE_CFO = _xml(order_item="200", budget_item="150", order_declarado="200", budget_declarado="150")


def test_pure_venda_maior_que_cfo():
    assert pg.venda_maior_que_cfo(150.0, 100.0) is True
    assert pg.venda_maior_que_cfo(100.0, 150.0) is False
    assert pg.venda_maior_que_cfo(100.0, 100.0) is False, "empate não passa — é 'maior', não 'maior ou igual'"
    assert pg.venda_maior_que_cfo(100.003, 100.0) is False, "diferença de fração de centavo não conta como margem real"


def test_pure_itens_com_markup_invalido():
    amb_ok = {"grupos": [{"itens": [{"order_total": 100.0, "budget_total": 150.0}]}]}
    amb_ruim = {"grupos": [{"itens": [
        {"order_total": 100.0, "budget_total": 150.0},   # este item passa
        {"order_total": 200.0, "budget_total": 150.0},   # este não — venda < CFO
    ]}]}
    amb_empate = {"grupos": [{"itens": [{"order_total": 100.0, "budget_total": 100.0}]}]}
    amb_zero = {"grupos": [{"itens": [{"order_total": 50.0, "budget_total": 0.0}]}]}
    assert pg.itens_com_markup_invalido(amb_ok) == []
    assert len(pg.itens_com_markup_invalido(amb_ruim)) == 1
    assert len(pg.itens_com_markup_invalido(amb_empate)) == 1, "empate (markup==1) também viola"
    assert len(pg.itens_com_markup_invalido(amb_zero)) == 1, "item zerado cai na mesma regra, sem cláusula própria"


def test_pool_upload_recusa_item_com_markup_invalido(http_client_factory, seed, app_db):
    """DECIDIDO 02/09: a regra é por item — recusa dura, não quarentena."""
    _criar_briefing(app_db, seed, "Proj_L1")
    db = app_db.get_session()
    antes = db.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    data = _upload_pool(c, "Proj_L1", "VendaMenor.xml", XML_VENDA_MENOR_QUE_CFO)
    assert data.get("ok") is False
    assert data.get("erro") == "Arquivo XML com erro, verifique o Promob."

    db2 = app_db.get_session()
    depois = db2.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").count()
    db2.close()
    assert depois == antes, "PoolAmbiente foi criado mesmo com item de markup <= 1"


def test_pool_upload_quarentena_antiga_continua_valendo_pro_que_ja_cobria(http_client_factory, seed, app_db):
    """A quarentena (`qa_selo='bloqueado'`) não foi substituída — continua cobrindo o caso que já
    cobria (margem quase nula, agregada, ACIMA do novo hard-reject por item). Mesmo fixture de
    `test_qualidade_upload_e2e.py::XML_RUIM`, agora via o endpoint de pool."""
    from tests.test_qualidade_upload_e2e import XML_RUIM
    _criar_briefing(app_db, seed, "Proj_L1")
    c = _login(http_client_factory, "dir_l1")
    data = _upload_pool(c, "Proj_L1", "QuaseSemMargem.xml", XML_RUIM)
    assert data.get("ok") is True, data

    db = app_db.get_session()
    pa = db.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").order_by(
        app_db.PoolAmbiente.id.desc()).first()
    db.close()
    assert pa is not None and pa.qa_selo == "bloqueado"


def test_pool_upload_aceita_venda_maior_que_cfo(http_client_factory, seed, app_db):
    _criar_briefing(app_db, seed, "Proj_L1")
    c = _login(http_client_factory, "dir_l1")
    data = _upload_pool(c, "Proj_L1", "Ok.xml", XML_OK)
    assert data.get("ok") is True, data


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


def test_pe_upload_recusa_venda_menor_que_cfo(http_client_factory, seed, app_db):
    pid = _proj_com_ambiente(app_db, seed, "PE45_a")
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post_multipart("/api/projetos/PE45_a/pe/upload",
                             files={"arquivo": ("pe.xml", XML_VENDA_MENOR_QUE_CFO.encode("utf-8"))},
                             fields={"pool_ambiente_id": pid})
    assert b.get("ok") is False
    assert "custo de fábrica" in b.get("erro", "").lower()

    db = app_db.get_session()
    reg = db.query(app_db.ArquivoPE).filter_by(projeto_nome="PE45_a", pool_ambiente_id=pid).first()
    db.close()
    assert reg is None, "ArquivoPE foi gravado mesmo com venda <= CFO"


def test_pe_upload_aceita_venda_maior_que_cfo(http_client_factory, seed, app_db):
    pid = _proj_com_ambiente(app_db, seed, "PE45_b")
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post_multipart("/api/projetos/PE45_b/pe/upload",
                             files={"arquivo": ("pe.xml", XML_OK.encode("utf-8"))},
                             fields={"pool_ambiente_id": pid})
    assert b.get("ok") is True, b


def test_complemento_nao_e_travado_pela_regra_absoluta():
    """xml_compl é um DELTA sobre um ambiente já aprovado, não venda/custo absolutos — o guard
    em main.py só aplica venda_maior_que_cfo quando formato != 'xml_compl'. Tripwire de código:
    se alguém remover a condição, este teste falha antes que o complemento comece a ser recusado
    incorretamente."""
    import inspect
    src = inspect.getsource(__import__("main"))
    assert 'formato != "xml_compl" and not venda_maior_que_cfo(venda, valor)' in src
