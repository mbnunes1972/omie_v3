import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json, uuid as _uuid
import urllib.request, urllib.error


def _post_multipart(base, cookie, path, fields, file_field=None, filename=None, filedata=b""):
    boundary = "----orizonTEST" + _uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(("--" + boundary + "\r\n").encode())
        parts.append((f'Content-Disposition: form-data; name="{k}"\r\n\r\n').encode())
        parts.append((str(v) + "\r\n").encode())
    if file_field:
        parts.append(("--" + boundary + "\r\n").encode())
        parts.append((f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n').encode())
        parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
        parts.append(filedata); parts.append(b"\r\n")
    parts.append(("--" + boundary + "--\r\n").encode())
    body = b"".join(parts)
    req = urllib.request.Request(base + path, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def _reset_etapas(app_db, proj, codigos):
    """Zera CicloDocumento + CicloEtapa das etapas dadas. Necessário porque `seed`/
    `app_db` são module-scoped → o estado vaza entre testes do mesmo arquivo."""
    db = app_db.get_session()
    for cod in codigos:
        # As faixas de evento da conversa (spec chat 2026-07-31) referenciam o documento por FK
        # (documento_ref_id) — desreferencia antes do delete (produção é append-only; o delete
        # é só desta limpeza de teste).
        ids = [d.id for d in db.query(app_db.CicloDocumento)
               .filter_by(projeto_nome=proj, etapa_codigo=cod).all()]
        if ids:
            (db.query(app_db.ConversaMensagem)
               .filter(app_db.ConversaMensagem.documento_ref_id.in_(ids))
               .update({"documento_ref_id": None}, synchronize_session=False))
        db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo=cod).delete()
        db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo=cod).delete()
    db.commit(); db.close()


def _marcar_concluida(app_db, proj, codigo):
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo=codigo).first()
    if et:
        et.status = "concluido"
    else:
        db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo=codigo, status="concluido"))
    db.commit(); db.close()


def test_upload_xml_append_only_e_listagem(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["12"])
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
        file_field="arquivo", filename="pedido1.xml", filedata=b"<xml>1</xml>")
    assert st == 200 and body.get("ok") is True, body
    st2, _ = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
        file_field="arquivo", filename="pedido2.xml", filedata=b"<xml>2</xml>")
    assert st2 == 200
    st3, lst = c.get(f"/api/projetos/{proj}/ciclo/12/pedido-xml")
    assert st3 == 200 and lst["ok"] is True
    assert len(lst["documentos"]) == 2, "append-only deve manter os dois XMLs"


def test_upload_xml_sem_arquivo_400(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, _ = _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {})
    assert st == 400


def test_upload_xml_etapa_sem_upload_400(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, _ = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/13/pedido-xml", {},
        file_field="arquivo", filename="x.xml", filedata=b"x")
    assert st == 400


def test_upload_xml_nao_autenticado_401(http_client_factory, seed, projetos_dir):
    c = http_client_factory()   # sem login
    proj = seed["projeto_l2"]
    st, _ = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
        file_field="arquivo", filename="x.xml", filedata=b"x")
    assert st == 401


def test_upload_xml_cycle_gated_consultor_ok(http_client_factory, seed, projetos_dir):
    # consultor NÃO tem executar_pe, mas AQUI é cycle-gated → deve conseguir (200)
    c = _login(http_client_factory, "cons_l1")
    proj = seed["projeto_l1"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
        file_field="arquivo", filename="p.xml", filedata=b"<xml/>")
    assert st == 200 and body.get("ok") is True, body


def test_12_nao_conclui_sem_xml_e_conclui_com_xml(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["11", "12"])
    _marcar_concluida(app_db, proj, "11")   # libera o gating sequencial da 12
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/12", {"status": "concluido"})
    assert st == 400 and "XML" in body["erro"], body
    _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
                    file_field="arquivo", filename="p.xml", filedata=b"<xml/>")
    st2, body2 = c.patch(f"/api/projetos/{proj}/ciclo/12", {"status": "concluido"})
    assert st2 == 200 and body2.get("ok") is True, body2


def test_13_nao_conclui_sem_numeros_e_conclui_com_numeros(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["12", "13"])
    _marcar_concluida(app_db, proj, "12")   # libera a 13
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/13", {"status": "concluido"})
    assert st == 400 and "número" in body["erro"].lower(), body
    st_s, _ = c.patch(f"/api/projetos/{proj}/ciclo/13", {"observacoes": "P-1001\nP-1002"})
    assert st_s == 200
    st2, body2 = c.patch(f"/api/projetos/{proj}/ciclo/13", {"status": "concluido"})
    assert st2 == 200 and body2.get("ok") is True, body2


def test_13_conclui_com_numeros_no_mesmo_patch(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["12", "13"])
    _marcar_concluida(app_db, proj, "12")
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/13",
                       {"status": "concluido", "observacoes": "P-9"})
    assert st == 200 and body.get("ok") is True, body


def test_14_nao_conclui_sem_relatorio_e_conclui_com_relatorio(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["13", "14"])
    _marcar_concluida(app_db, proj, "13")   # libera a 14
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/14", {"status": "concluido", "observacoes": "   "})
    assert st == 400 and "Relatório" in body["erro"], body
    st2, body2 = c.patch(f"/api/projetos/{proj}/ciclo/14",
                         {"status": "concluido", "observacoes": "1 gaveta avariada"})
    assert st2 == 200 and body2.get("ok") is True, body2


def test_gating_sequencial_preservado_13_sem_12(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["12", "13"])   # garante 12 NÃO concluída
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/13",
                       {"status": "concluido", "observacoes": "P-1"})
    assert st == 400 and "anterior" in body["erro"].lower(), body


def test_pe_intocado_smoke(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["11a"])
    _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
                    {"login": "dir_l2", "senha": "senha123"},
                    file_field="arquivo", filename="p.pdf", filedata=b"x")
    st, body = c.post(f"/api/projetos/{proj}/ciclo/11a/concluir",
                      {"login": "dir_l2", "senha": "senha123"})
    assert st == 200 and body.get("ok") is True, body
