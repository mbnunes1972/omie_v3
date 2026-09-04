# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-52 — a remoção nas subfases do PE era mais FROUXA que a
porta que subiu o documento. As subfases do PE têm DUAS portas de entrada — a de execução
(POST .../documento, exige executar_pe) e a de revisão (POST .../revisao, exige revisar_pe,
tipo="pe_relatorio_complementar") — mas a remoção usava UMA regra só (executar_pe) pra tudo. O
Operador (executar_pe=True, revisar_pe=False, auth/perfis.py) podia remover um relatório de
revisão que ele jamais poderia ter subido. Conserto: a remoção olha o `tipo` do documento e
espelha a porta que o produziu, não a etapa inteira."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
import urllib.request, urllib.error

from tests.test_ciclo_pe_e2e import _post_multipart


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _post(c, path, body):
    req = urllib.request.Request(c.base + path, data=_json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if c.cookie: req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def _upload_revisao(c, proj, app_db):
    # POST .../revisao não devolve documento_id (devolve "resetadas") — o doc.id vem do banco,
    # pelo tipo exclusivo desta porta (pe_relatorio_complementar, nunca produzido por
    # tipo_doc_de()).
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11b/revisao",
        {"login": "dir_l1", "senha": "senha123", "motivo": "ajuste"},
        file_field="arquivo", filename="relatorio.pdf", filedata=b"rel")
    assert st == 200 and body.get("ok") is True, body
    db = app_db.get_session()
    doc = (db.query(app_db.CicloDocumento)
             .filter_by(projeto_nome=proj, etapa_codigo="11b", tipo="pe_relatorio_complementar")
             .order_by(app_db.CicloDocumento.id.desc()).first())
    db.close()
    assert doc is not None
    return doc.id


def test_operador_nao_remove_relatorio_de_revisao(http_client_factory, seed, app_db, projetos_dir):
    """cons_l1 (operador: executar_pe=True, revisar_pe=False) tenta remover com a PRÓPRIA
    credencial (correta) — não basta ter executar_pe, a porta que subiu este documento foi a
    de revisão."""
    c_master = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    doc_id = _upload_revisao(c_master, proj, app_db)

    c_op = _login(http_client_factory, "cons_l1")
    st, r = _post(c_op, f"/api/projetos/{proj}/ciclo/11b/documentos/{doc_id}/remover",
                  {"login": "cons_l1", "senha": "senha123"})
    assert st == 403, ("operador não tem revisar_pe — não pode remover relatório de revisão", st, r)

    db = app_db.get_session()
    doc = db.get(app_db.CicloDocumento, doc_id)
    assert doc.removido_em is None, "não deveria ter removido"
    db.close()


def test_quem_tem_revisar_pe_remove_o_relatorio_de_revisao(http_client_factory, seed, app_db, projetos_dir):
    """dir_l1 (master: tem revisar_pe) remove o mesmo tipo de documento sem problema."""
    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    doc_id = _upload_revisao(c, proj, app_db)

    st, r = _post(c, f"/api/projetos/{proj}/ciclo/11b/documentos/{doc_id}/remover",
                  {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and r.get("ok") is True, r

    db = app_db.get_session()
    doc = db.get(app_db.CicloDocumento, doc_id)
    assert doc.removido_em is not None
    db.close()


def test_irmao_do_achado49_continua_intacto_documento_normal_exige_executar_pe(
        http_client_factory, seed, projetos_dir):
    """Controle: um documento de subfase NORMAL (tipo != pe_relatorio_complementar, subido pela
    porta de execução) continua exigindo executar_pe pra remover — o conserto do ACHADO-52 não
    afrouxou esse caminho, só corrigiu o da revisão. Credencial de TERCEIRO errada é recusada
    (mesmo padrão do ACHADO-49/ACHADO-30 — sessão já com a capacidade dispensaria senha)."""
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st_up, up = _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
                                {"login": "dir_l2", "senha": "senha123"},
                                file_field="arquivo", filename="planta.pdf", filedata=b"%PDF-fake")
    assert st_up == 200 and up.get("ok") is True, up
    doc_id = up["documento_id"]
    st, r = _post(c, f"/api/projetos/{proj}/ciclo/11a/documentos/{doc_id}/remover",
                  {"login": "dir_l2", "senha": "errada"})
    assert st == 403, ("documento normal de subfase continua exigindo executar_pe", st, r)
