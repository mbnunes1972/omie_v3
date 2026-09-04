# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-49 — o Remover da etapa 12 herdou a autoridade do PE, e
a tela cala quando a credencial não vem.

Causa 1: a etapa 12 não é subfase do PE (caiu no `else` da rota de remoção, pensado só pras
subfases), e por isso exigia login+senha de `executar_pe` pra remover, embora o próprio upload
(POST /ciclo/12/pedido-xml) não peça credencial nenhuma. A autoridade agora espelha o upload: a
12 usa o mesmo gate de execução (`_bloqueio_execucao_etapa`), sem credencial.

Causa 2: `removerDocCiclo` fazia `return` silencioso quando `pedirCredenciaisGerente` devolvia
vazio (cancelado, ou sem a capacidade) — padrão "estado antes da credencial" do ACHADO-38/B3,
pela quinta vez. Agora avisa."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
import urllib.request, urllib.error


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


def _upload_pedido_xml(c, proj, codigo="12"):
    import uuid as _uuid
    boundary = "----t" + _uuid.uuid4().hex
    parts = [("--"+boundary+"\r\n").encode(),
             ('Content-Disposition: form-data; name="arquivo"; filename="pedido.xml"\r\n').encode(),
             b"Content-Type: application/octet-stream\r\n\r\n", b"<xml>fake</xml>", b"\r\n",
             ("--"+boundary+"--\r\n").encode()]
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/{codigo}/pedido-xml",
                                 data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary="+boundary)
    req.add_header("Cookie", c.cookie)
    r = urllib.request.urlopen(req, timeout=5)
    return _json.loads(r.read())


def test_causa1_remover_etapa12_nao_exige_credencial_do_pe(http_client_factory, seed, app_db, projetos_dir):
    """A autoridade de remover a 12 espelha o upload: nenhuma credencial, só o gate de execução."""
    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    up = _upload_pedido_xml(c, proj)
    assert up.get("ok") is True, up
    doc_id = up["documento_id"]
    # Sem login/senha no corpo — se a causa 1 não estivesse corrigida, isto voltaria 403
    # ("Ação exige login+senha de Projetista Executivo...").
    st, r = _post(c, f"/api/projetos/{proj}/ciclo/12/documentos/{doc_id}/remover", {})
    assert st == 200 and r.get("ok") is True, r
    db = app_db.get_session()
    doc = db.get(app_db.CicloDocumento, doc_id)
    assert doc.removido_em is not None, "removeu de verdade, sem pedir executar_pe"
    db.close()


def test_causa1_irmaos_do_else_continuam_exigindo_executar_pe(http_client_factory, seed, app_db, projetos_dir):
    """Controle: a correção é só pra 12. Subfase de PE de verdade (11a) continua na porta do
    `else` — credencial de TERCEIRO errada é recusada (o mesmo caso que
    test_aceite4_autoridade_espelha_a_do_upload usa pra provar a exigência; sessão já com a
    capacidade dispensaria senha, então não prova a exigência sozinho)."""
    from tests.test_ciclo_pe_e2e import _post_multipart
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st_up, up = _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
                                {"login": "dir_l2", "senha": "senha123"},
                                file_field="arquivo", filename="planta.pdf", filedata=b"%PDF-fake")
    assert st_up == 200 and up.get("ok") is True, up
    doc_id = up["documento_id"]
    st, r = _post(c, f"/api/projetos/{proj}/ciclo/11a/documentos/{doc_id}/remover",
                  {"login": "dir_l2", "senha": "errada"})
    assert st == 403, ("subfase de PE de verdade continua exigindo executar_pe", st, r)
