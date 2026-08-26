import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json, uuid as _uuid
import urllib.request, urllib.error


def _post_multipart(base, cookie, path, fields, file_field=None, filename=None, filedata=b""):
    """POST multipart/form-data compatível com _parse_multipart_arquivos do main.py."""
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
        parts.append(filedata)
        parts.append(b"\r\n")
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


def test_upload_pe_cria_documento(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
        {"login": "dir_l2", "senha": "senha123"},
        file_field="arquivo", filename="planta.pdf", filedata=b"%PDF-fake")
    assert st == 200 and body.get("ok") is True, body
    st2, _ = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
        {"login": "dir_l2", "senha": "senha123"},
        file_field="arquivo", filename="planta_v2.pdf", filedata=b"%PDF-fake2")
    assert st2 == 200
    st3, docs = c.get(f"/api/projetos/{proj}/ciclo/pe")
    assert st3 == 200
    versoes = [d for d in docs["documentos"] if d["tipo"] == "pe_planta_pontos"]
    assert len(versoes) == 2, "append-only deve manter as duas versões"


def test_get_pe_lista_documentos_e_medicao_intocada(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11c/documento",
                    {"login": "dir_l2", "senha": "senha123"},
                    file_field="arquivo", filename="pe.pdf", filedata=b"PE")
    st, body = c.get(f"/api/projetos/{proj}/ciclo/pe")
    assert st == 200 and body["ok"] is True
    assert any(d["tipo"] == "pe_projeto_executivo" for d in body["documentos"])
    assert "11c" in body["subfases"]
    med = os.path.join(projetos_dir, proj, "medicao")
    assert not os.path.exists(med) or os.listdir(med) == []


def test_download_documento_devolve_conteudo(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
        {"login": "dir_l2", "senha": "senha123"},
        file_field="arquivo", filename="planta.pdf", filedata=b"%PDF-conteudo")
    assert st == 200
    doc_id = body["documento_id"]
    import urllib.request
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/documento/{doc_id}")
    req.add_header("Cookie", c.cookie)
    r = urllib.request.urlopen(req, timeout=5)
    assert r.status == 200
    assert r.read() == b"%PDF-conteudo"


def test_download_documento_inexistente_404(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, _ = c.get(f"/api/projetos/{proj}/ciclo/documento/999999")
    assert st == 404


def test_upload_codigo_invalido_400(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    # 11d não é subfase enriquecida → 400
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11d/documento",
        {"login": "dir_l2", "senha": "senha123"},
        file_field="arquivo", filename="x.pdf", filedata=b"x")
    assert st == 400


def test_upload_sem_arquivo_400(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
        {"login": "dir_l2", "senha": "senha123"})   # sem file_field
    assert st == 400


def test_upload_sem_capability_403(http_client_factory, seed, projetos_dir, app_db):
    # Perfil-4 (novo modelo): as 3 bases de loja (master/gerencial/operador) têm executar_pe —
    # não existe mais um perfil de loja "só painéis sem operacional" (o antigo Suporte foi
    # extinto e seu alias hoje resolve para Operador, que TEM executar_pe). Para exercitar o
    # gate de capability sem enfraquecê-lo, usamos admin_rede (plataforma), que não tem
    # executar_pe em nenhum modelo.
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    u = app_db.Usuario(nome="AdmRede2", login="admrede2@loja.com", nivel="admin_rede",
                        loja_id=l1, ativo=1)
    u.set_senha("senha123"); db.add(u); db.commit(); db.close()
    c = _login(http_client_factory, "admrede2@loja.com")
    proj = seed["projeto_l1"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
        {"login": "admrede2@loja.com", "senha": "senha123"},
        file_field="arquivo", filename="x.pdf", filedata=b"x")
    assert st == 403


def test_concluir_11b_barra_sem_documento(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    # 11b nunca recebe upload nos testes anteriores → guarda rejeita por falta de documento
    st, body = c.post(f"/api/projetos/{proj}/ciclo/11b/concluir",
                      {"login": "dir_l2", "senha": "senha123"})
    assert st == 400 and "Carregue" in body["erro"]


def test_concluir_11a_com_documento(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
                    {"login": "dir_l2", "senha": "senha123"},
                    file_field="arquivo", filename="p.pdf", filedata=b"x")
    st, body = c.post(f"/api/projetos/{proj}/ciclo/11a/concluir",
                      {"login": "dir_l2", "senha": "senha123"})
    assert st == 200 and body.get("ok") is True


def test_revisao_reabre_em_cascata(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    # marca 11e concluída direto no banco para provar que a revisão de 11b a reabre
    db = app_db.get_session()
    for cod in ("11b", "11c", "11d", "11e"):
        et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo=cod).first()
        if et:
            et.status = "concluido"
        else:
            db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo=cod, status="concluido"))
    db.commit(); db.close()
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11b/revisao",
        {"login": "dir_l2", "senha": "senha123", "motivo": "ajuste"},
        file_field="arquivo", filename="relatorio.pdf", filedata=b"rel")
    assert st == 200 and "11e" in body["resetadas"], body
    db = app_db.get_session()
    e11e = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="11e").first()
    assert e11e.status == "pendente"
    e11 = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="11").first()
    assert e11 is not None and e11.status == "em_andamento" and e11.concluido_em is None
    db.close()


# Achado da Vera (2026-08-26, E2E, reproduzido ao vivo): sem fronteira nenhuma, a cascata
# resetava etapas operacionais (12+) já em andamento/concluídas — produção encaminhada, NFe
# emitida, montagem feita — sem checar se já havia trabalho FÍSICO real registrado ali.
def test_revisao_bloqueada_com_etapa_operacional_ja_iniciada(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    db = app_db.get_session()
    for cod in ("11b", "11c", "11d", "11e"):
        et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo=cod).first()
        if et:
            et.status = "concluido"
        else:
            db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo=cod, status="concluido"))
    # etapa 12 (Conferência e Implantação do Pedido) já em andamento — ciclo avançou de verdade
    et12 = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="12").first()
    if et12:
        et12.status = "em_andamento"
    else:
        db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo="12", status="em_andamento"))
    db.commit(); db.close()

    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11b/revisao",
        {"login": "dir_l2", "senha": "senha123", "motivo": "ajuste"},
        file_field="arquivo", filename="relatorio.pdf", filedata=b"rel")
    assert st == 400 and "Conferência e Implantação do Pedido" in body["erro"], body

    # nada foi resetado — a 12 continua em_andamento, a 11e continua concluída
    db = app_db.get_session()
    et12 = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="12").first()
    assert et12.status == "em_andamento"
    e11e = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="11e").first()
    assert e11e.status == "concluido"
    db.close()


def test_revisao_exige_gerente(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "cons_l1")   # consultor não pode revisar
    proj = seed["projeto_l1"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11b/revisao",
        {"login": "cons_l1", "senha": "senha123"},
        file_field="arquivo", filename="r.pdf", filedata=b"r")
    assert st == 403


def test_revisao_exige_relatorio(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11b/revisao",
        {"login": "dir_l2", "senha": "senha123"})   # sem arquivo
    assert st == 400 and "relatório" in body["erro"].lower()
