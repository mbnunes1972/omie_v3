# -*- coding: utf-8 -*-
"""tests/test_documentos_api.py — Task 8: os 5 endpoints HTTP do registro de modelos de
documento por loja (miolo já pronto/testado em mod_documentos.py / mod_marcadores.py /
mod_documentos_import.py).

Sobe o servidor real (fixtures `servidor`/`seed`/`http_client_factory` de conftest.py) e bate
via HTTP — a Task 6 aprendeu que teste unitário não prova a composição (login+escopo+multipart+
resposta), então aqui é E2E de propósito, não chamada direta aos módulos.

`HttpClient` (conftest.py) só fala JSON. Os endpoints desta frente precisam de multipart
(importar) e de resposta binária/PDF (preview) — os dois helpers abaixo (`_post_multipart`,
`_post_json_raw`) resolvem isso com urllib puro, no mesmo estilo de
tests/test_qualidade_upload_e2e.py.

NENHUM teste sobe .docx/.odt de verdade — só .md/.txt (leitura direta, sem LibreOffice) — e o
teste de "falha de conversão" monkeypatcha mod_documentos_import.normalizar em vez de forçar o
LibreOffice a falhar.
"""
import os
import json as _json
import urllib.request as _urllib_req

import pytest


# ── Helpers HTTP (o HttpClient de conftest.py só fala JSON) ────────────────────

def _post_multipart(client, path, campos, arquivo=None):
    """arquivo: (nome_campo, filename, bytes) ou None. Devolve (status, dict|bytes)."""
    boundary = b"----DocApiTestBoundary"
    partes = []
    for k, v in (campos or {}).items():
        partes.append(
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="' + k.encode() + b'"\r\n\r\n'
            + str(v).encode("utf-8") + b"\r\n"
        )
    if arquivo:
        nome_campo, filename, dados = arquivo
        partes.append(
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="' + nome_campo.encode() +
            b'"; filename="' + filename.encode() + b'"\r\n'
            b"Content-Type: application/octet-stream\r\n\r\n"
            + dados + b"\r\n"
        )
    partes.append(b"--" + boundary + b"--\r\n")
    body = b"".join(partes)

    req = _urllib_req.Request(client.base + path, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary.decode())
    if client.cookie:
        req.add_header("Cookie", client.cookie)
    try:
        resp = _urllib_req.urlopen(req, timeout=10)
        status, raw = resp.status, resp.read()
    except _urllib_req.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        data = _json.loads(raw) if raw else None
    except Exception:
        data = raw
    return status, data


def _post_json_raw(client, path, payload):
    """POST JSON devolvendo a resposta CRUA (status, bytes, headers) — usado no preview,
    que devolve application/pdf, não JSON."""
    data = _json.dumps(payload).encode("utf-8")
    req = _urllib_req.Request(client.base + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if client.cookie:
        req.add_header("Cookie", client.cookie)
    try:
        resp = _urllib_req.urlopen(req, timeout=15)
        return resp.status, resp.read(), dict(resp.headers)
    except _urllib_req.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def _login(factory, who):
    c = factory()
    status, body = c.login(who, "senha123")
    assert status == 200, body
    return c


CORPO_OK = "CLAUSULA PRIMEIRA\n1.1. [NOME_CLIENTE], CPF [CPF_CLIENTE], texto de teste.\n"
CORPO_DESCONHECIDO = "CLAUSULA PRIMEIRA\n1.1. [MARCADOR_QUE_NAO_EXISTE] no meio do texto.\n"


# ── GET /api/documentos/marcadores ──────────────────────────────────────────────

def test_marcadores_sem_sessao_401(http_client_factory):
    c = http_client_factory()
    status, body = c.get("/api/documentos/marcadores")
    assert status == 401, body


def test_marcadores_com_sessao_devolve_catalogo(http_client_factory):
    c = _login(http_client_factory, "dir_l1")
    status, body = c.get("/api/documentos/marcadores")
    assert status == 200, body
    assert body["ok"] is True
    assert "NOME_CLIENTE" in body["catalogo"]
    assert body["catalogo"]["NOME_CLIENTE"]["escopo"] == "cliente"


# ── GET /api/documentos/modelos — escopo por loja + pode_gerir ─────────────────

def test_modelos_get_escopado_e_pode_gerir_reflete_perfil(http_client_factory):
    master = _login(http_client_factory, "dir_l1")
    status, body = master.get("/api/documentos/modelos")
    assert status == 200, body
    assert body["ok"] is True
    assert body["pode_gerir"] is True   # master: gerir_documentos = True

    operador = _login(http_client_factory, "cons_l1")
    status, body = operador.get("/api/documentos/modelos")
    assert status == 200, body
    assert body["pode_gerir"] is False  # operador: gerir_documentos = False


def test_tenancy_loja_a_nao_ve_modelo_da_loja_b(app_db, seed, http_client_factory):
    import mod_documentos
    db = app_db.get_session()
    try:
        v = mod_documentos.criar_versao(
            db, seed["loja2_id"], "contrato",
            "CLAUSULA PRIMEIRA\n1.1. Modelo exclusivo da Loja 2.\n", "l2.md", 1)
        mod_documentos.ativar(db, v.id)
        v_id = v.id
    finally:
        db.close()

    c1 = _login(http_client_factory, "dir_l1")
    status, body = c1.get("/api/documentos/modelos")
    assert status == 200, body
    ids_l1 = {m["id"] for m in body["modelos"]}
    assert v_id not in ids_l1, "loja A não pode enxergar modelo da loja B"

    c2 = _login(http_client_factory, "dir_l2")
    status, body = c2.get("/api/documentos/modelos")
    assert status == 200, body
    ids_l2 = {m["id"] for m in body["modelos"]}
    assert v_id in ids_l2


# ── POST /api/documentos/modelos/importar ───────────────────────────────────────

def test_importar_sem_capacidade_403(app_db, seed, http_client_factory, monkeypatch, tmp_path):
    """403 não basta: tem que provar que NADA aconteceu antes do gate.

    Hoje a ordem do código já checa a capacidade antes de qualquer I/O, mas sem estas
    asserções nada trava isso — bastaria alguém mover o guardar_staging para cima do gate
    para um operador sem permissão passar a escrever no disco da loja, e o teste seguiria verde.
    """
    import mod_documentos
    docs_dir = str(tmp_path / "docs_403")
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", docs_dir)
    db = app_db.get_session()
    antes = db.query(app_db.DocumentoModelo).count()
    db.close()

    c = _login(http_client_factory, "cons_l1")   # operador: sem gerir_documentos
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "modelo.md", CORPO_OK.encode("utf-8")))
    assert status == 403, body

    assert not os.path.exists(docs_dir), (
        "403 deixou rastro em disco — o gate de capacidade está DEPOIS do guardar_staging")
    db = app_db.get_session()
    assert db.query(app_db.DocumentoModelo).count() == antes, "403 mexeu no banco"
    db.close()


def test_importar_pdf_400_com_mensagem_acionavel(http_client_factory):
    c = _login(http_client_factory, "dir_l1")
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "modelo.pdf", b"%PDF-1.4 conteudo qualquer"))
    assert status == 400, body
    assert "PDF" in body["erro"] and "Word" in body["erro"]


def test_importar_md_valido_devolve_corpo_e_nao_cria_versao(app_db, seed, http_client_factory):
    db = app_db.get_session()
    antes = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "modelo_valido.md", CORPO_OK.encode("utf-8")))
    assert status == 200, body
    assert body["ok"] is True
    assert body["corpo_md"].strip()
    assert body["origem_nome"] == "modelo_valido.md"
    assert body["tipo"] == "contrato"
    assert body["staging"] == os.path.basename(body["staging"]), "staging deve ser só o basename"
    assert "/" not in body["staging"] and "\\" not in body["staging"]
    assert body["analise"]["bloqueia_ativacao"] is False
    assert "NOME_CLIENTE" in body["analise"]["conhecidos_usados"]

    db = app_db.get_session()
    depois = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()
    assert depois == antes, "importar NUNCA cria versão — só converte e analisa"


def test_importar_falha_de_conversao_remove_o_staging(seed, http_client_factory, monkeypatch, tmp_path):
    """normalizar() falhando (não FormatoNaoSuportado) tem que limpar o staging."""
    import mod_documentos, mod_documentos_import
    docs_dir = str(tmp_path / "docs_falha")
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", docs_dir)
    monkeypatch.setattr(mod_documentos_import, "normalizar",
                        lambda path: (_ for _ in ()).throw(RuntimeError("conversão simulada falhou")))

    c = _login(http_client_factory, "dir_l1")
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "modelo.docx", b"binario irrelevante, normalizar esta mockado"))
    assert status == 400, body
    assert "Falha ao converter" in body["erro"]

    staging_dir = os.path.join(docs_dir, str(seed["loja1_id"]), "contrato", "_staging")
    restantes = os.listdir(staging_dir) if os.path.exists(staging_dir) else []
    assert restantes == [], "staging não foi limpo após falha de conversão: %r" % restantes


def test_importar_corpo_vazio_remove_o_staging(seed, http_client_factory, monkeypatch, tmp_path):
    import mod_documentos
    docs_dir = str(tmp_path / "docs_vazio")
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", docs_dir)

    c = _login(http_client_factory, "dir_l1")
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "vazio.txt", b"   \n\n   \n"))
    assert status == 400, body
    assert "conte" in body["erro"].lower() or "vazio" in body["erro"].lower()

    staging_dir = os.path.join(docs_dir, str(seed["loja1_id"]), "contrato", "_staging")
    restantes = os.listdir(staging_dir) if os.path.exists(staging_dir) else []
    assert restantes == [], "staging não foi limpo após corpo vazio: %r" % restantes


# ── POST /api/documentos/modelos/preview ────────────────────────────────────────

def test_preview_sem_capacidade_403(http_client_factory):
    c = _login(http_client_factory, "cons_l1")
    status, body, _headers = _post_json_raw(
        c, "/api/documentos/modelos/preview", {"corpo_md": CORPO_OK})
    assert status == 403
    assert _json.loads(body)["ok"] is False


def test_preview_com_corpo_malicioso_nao_faz_requisicao_externa(http_client_factory):
    """SSRF pelo endpoint REAL — a composição, não só o mod_contrato isolado.

    Era o vetor mais barato da frente: bastava um POST no /preview, sem ativar nada, para
    o servidor buscar uma URL escolhida pelo atacante (alcance a serviço interno). Depois
    de ativado, dispararia em todo contrato gerado. tests/test_documentos_seguranca.py
    cobre as duas camadas na unidade; aqui prova-se que estão plugadas na rota.
    """
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    hits = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"hi")

        def log_message(self, *a):
            pass

    sonda = HTTPServer(("127.0.0.1", 0), H)
    porta = sonda.server_address[1]
    threading.Thread(target=sonda.serve_forever, daemon=True).start()
    try:
        corpo = ('<img src="http://127.0.0.1:%d/vazou-img">\n\n'
                 '<style>@import url("http://127.0.0.1:%d/vazou-css");</style>\n\n'
                 '# CLAUSULA PRIMEIRA\n1.1. Texto.\n' % (porta, porta))
        c = _login(http_client_factory, "dir_l1")
        status, dados, _h = _post_json_raw(c, "/api/documentos/modelos/preview",
                                           {"corpo_md": corpo})
        assert status == 200, dados[:300]
        assert dados[:4] == b"%PDF"
        assert hits == [], "o /preview buscou URL externa a partir do corpo_md: %r" % hits
    finally:
        sonda.shutdown()


def test_preview_gera_pdf_e_nao_salva_nada(app_db, seed, http_client_factory):
    db = app_db.get_session()
    antes = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    status, dados, headers = _post_json_raw(
        c, "/api/documentos/modelos/preview", {"corpo_md": CORPO_OK})
    assert status == 200, dados[:300]
    assert headers.get("Content-Type") == "application/pdf"
    assert dados[:4] == b"%PDF"

    db = app_db.get_session()
    depois = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()
    assert depois == antes, "preview não pode persistir nada"


# ── POST /api/documentos/modelos — cria + ativa ─────────────────────────────────

def test_modelos_post_sem_capacidade_403(app_db, http_client_factory):
    db = app_db.get_session()
    antes = db.query(app_db.DocumentoModelo).count()
    db.close()

    c = _login(http_client_factory, "cons_l1")
    status, body = c.post("/api/documentos/modelos", {
        "tipo": "contrato", "corpo_md": CORPO_OK, "origem_nome": "m.md",
        "cravados_aprovados": [],
    })
    assert status == 403, body

    db = app_db.get_session()
    assert db.query(app_db.DocumentoModelo).count() == antes, "403 criou versão"
    db.close()


def test_modelos_post_marcador_desconhecido_400_nada_criado(app_db, seed, http_client_factory):
    db = app_db.get_session()
    antes = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    status, body = c.post("/api/documentos/modelos", {
        "tipo": "contrato", "corpo_md": CORPO_DESCONHECIDO, "origem_nome": "m.md",
        "cravados_aprovados": [],
    })
    assert status == 400, body
    assert body["ok"] is False
    assert "MARCADOR_QUE_NAO_EXISTE" in body["erro"]

    db = app_db.get_session()
    depois = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()
    assert depois == antes, "marcador desconhecido não pode criar versão nenhuma"


def test_modelos_post_feliz_cria_ativa_e_aparece_no_get(http_client_factory):
    c = _login(http_client_factory, "dir_l1")
    status, body = c.post("/api/documentos/modelos", {
        "tipo": "proposta", "corpo_md": CORPO_OK, "origem_nome": "proposta_nova.md",
        "cravados_aprovados": [],
    })
    assert status == 200, body
    assert body["ok"] is True
    modelo = body["modelo"]
    assert modelo["tipo"] == "proposta"
    assert modelo["ativo"] is True

    status, body = c.get("/api/documentos/modelos")
    assert status == 200, body
    achados = [m for m in body["modelos"] if m["id"] == modelo["id"]]
    assert len(achados) == 1
    assert achados[0]["ativo"] is True


# ── Path traversal ───────────────────────────────────────────────────────────────
#
# A primeira versão desta suíte testava só o vetor COM BARRA ('../../loja2/...'), que o
# os.path.basename() realmente resolve — passava pelo motivo certo, mas era o vetor fácil.
# A revisão achou o furo: basename('.') == '.' e basename('..') == '..' (não têm barra,
# então basename não remove nada). Com '.', o join devolvia o PRÓPRIO _staging/ da loja,
# exists() dizia True, e o shutil.move levava o DIRETÓRIO INTEIRO — com os uploads
# pendentes de outras importações — para dentro de v<N>/. Com '..', subia shutil.Error
# não tratado e a conexão caía sem resposta. Os dois comprovados contra o servidor real.
# Agora quem confina é mod_documentos.resolver_staging; estes testes travam os vetores.

@pytest.mark.parametrize("vetor", [
    ".",                       # basename('.') == '.' -> era o _staging/ inteiro
    "..",                      # basename('..') == '..' -> shutil.Error, conexão caída
    "../../algo",
    "..\\..\\algo",
    "/etc/passwd",
    "C:\\Windows\\win.ini",
    "",
    "   ",
    "inventado.md",            # forma inválida (não é <sha16><ext>)
    "0123456789abcdef.md/..",
])
def test_staging_vetor_hostil_nao_promove_nada(app_db, seed, http_client_factory,
                                               monkeypatch, tmp_path, vetor):
    """Nenhum vetor pode escapar do _staging/ da loja, virar 500 ou derrubar a conexão.

    O contrato é: não resolveu -> segue SEM trilha de origem (origem_path None), 200.
    A versão vale sem o original; o que não pode é tocar arquivo de fora.
    """
    import mod_documentos
    docs_dir = str(tmp_path / ("docs_" + str(abs(hash(vetor)))))
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", docs_dir)

    # staging legítimo pendente da Loja 1 — é o que o vetor '.' arrastaria junto.
    pendente, _sha = mod_documentos.guardar_staging(
        seed["loja1_id"], "contrato", "pendente.md", b"UPLOAD PENDENTE DE OUTRA IMPORTACAO")
    # e um arquivo da Loja 2, que nenhum vetor pode alcançar
    outro_dir = os.path.join(docs_dir, str(seed["loja2_id"]), "contrato", "_staging")
    os.makedirs(outro_dir, exist_ok=True)
    secreto = os.path.join(outro_dir, "segredo.docx")
    with open(secreto, "wb") as fh:
        fh.write(b"CONTEUDO DA LOJA 2")

    c = _login(http_client_factory, "dir_l1")   # sessão da Loja 1
    status, body = c.post("/api/documentos/modelos", {
        "tipo": "contrato", "corpo_md": CORPO_OK, "origem_nome": "modelo.md",
        "staging": vetor, "cravados_aprovados": [],
    })
    assert status == 200, "vetor %r devia ser recusado em silêncio, não virar %s: %r" % (
        vetor, status, body)
    assert body["ok"] is True

    db = app_db.get_session()
    try:
        m = db.get(app_db.DocumentoModelo, body["modelo"]["id"])
        assert m.loja_id == seed["loja1_id"]
        assert m.origem_path is None, (
            "vetor %r promoveu algo indevido: origem_path=%r" % (vetor, m.origem_path))
    finally:
        db.close()
    assert os.path.isfile(pendente), (
        "vetor %r arrastou o _staging/ da loja (upload pendente sumiu)" % vetor)
    assert os.path.isfile(secreto), "vetor %r tocou arquivo da Loja 2" % vetor


def test_staging_legitimo_continua_sendo_promovido(app_db, seed, http_client_factory,
                                                   monkeypatch, tmp_path):
    """Contraponto do teste acima: endurecer não pode matar o caminho feliz.

    O nome que o importar devolve TEM que continuar promovendo o original para v<N>/ —
    senão a trilha de auditoria (origem_path/origem_sha256) morreria em silêncio.
    """
    import mod_documentos
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", str(tmp_path / "docs_feliz"))

    c = _login(http_client_factory, "dir_l1")
    status, imp = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "modelo_real.md", CORPO_OK.encode("utf-8")))
    assert status == 200, imp

    status, body = c.post("/api/documentos/modelos", {
        "tipo": "contrato", "corpo_md": imp["corpo_md"], "origem_nome": imp["origem_nome"],
        "staging": imp["staging"], "origem_sha256": imp["origem_sha256"],
        "cravados_aprovados": [],
    })
    assert status == 200, body

    db = app_db.get_session()
    try:
        m = db.get(app_db.DocumentoModelo, body["modelo"]["id"])
        assert m.origem_path and os.path.isfile(m.origem_path), (
            "o staging legítimo devia ter sido promovido: origem_path=%r" % m.origem_path)
        assert "v%d" % m.versao in m.origem_path
        assert m.origem_sha256 == imp["origem_sha256"]
    finally:
        db.close()


def test_falha_de_io_ao_promover_nao_derruba_conexao_nem_duplica_versao(
        app_db, seed, http_client_factory, monkeypatch, tmp_path):
    """criar_versao commita a linha e SÓ DEPOIS move o original, deixando a exceção do
    move subir (contrato travado por test_documentos_registro). Antes, o handler só
    pegava ValueError -> OSError derrubava a conexão sem resposta.

    Responder erro também seria errado: a versão JÁ existe, o lojista tentaria de novo e
    criaria uma DUPLICADA — a armadilha que o próprio criar_versao documenta. O certo é
    recuperar a linha, ativar e avisar.
    """
    import mod_documentos
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", str(tmp_path / "docs_io"))

    # app_db/seed são module-scoped: as versões acumulam entre os testes deste arquivo.
    # Contar o delta é o que prova "não duplicou" — um assert de total absoluto estaria
    # testando a ordem das fixtures, não o comportamento.
    def _n_propostas():
        db = app_db.get_session()
        try:
            return [m.id for m in mod_documentos.listar(db, seed["loja1_id"])
                    if m.tipo == "proposta"]
        finally:
            db.close()
    antes = _n_propostas()

    c = _login(http_client_factory, "dir_l1")
    status, imp = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "proposta"},
        arquivo=("arquivo", "io.md", CORPO_OK.encode("utf-8")))
    assert status == 200, imp

    def explode(*a, **k):
        raise OSError("disco cheio (simulado)")
    monkeypatch.setattr(mod_documentos, "_promover_original", explode)

    status, body = c.post("/api/documentos/modelos", {
        "tipo": "proposta", "corpo_md": imp["corpo_md"], "origem_nome": imp["origem_nome"],
        "staging": imp["staging"], "origem_sha256": imp["origem_sha256"],
        "cravados_aprovados": [],
    })
    assert status == 200, "falha de I/O virou %s (antes: conexão caída): %r" % (status, body)
    assert body["ok"] is True
    assert "aviso" in body, "o lojista tem que saber que a trilha de origem se perdeu"

    depois = _n_propostas()
    assert len(depois) == len(antes) + 1, (
        "a falha de I/O tinha que gerar UMA versão, não %d" % (len(depois) - len(antes)))

    db = app_db.get_session()
    try:
        m = db.get(app_db.DocumentoModelo, body["modelo"]["id"])
        assert m.ativo == 1, "a versão existe e é válida — tem que ficar ativa"
        assert m.origem_path is None
    finally:
        db.close()


# ── GET /api/documentos/modelos/padroes-disponiveis ─────────────────────────────

def test_padroes_disponiveis_sem_sessao_401(http_client_factory):
    c = http_client_factory()
    status, body = c.get("/api/documentos/modelos/padroes-disponiveis")
    assert status == 401, body


def test_padroes_disponiveis_lista_so_tipos_com_arquivo(http_client_factory):
    """Bate contra os arquivos REAIS de modelos_documentos_padrao/ — trava a promessa de
    que a tela nunca hardcoda essa lista (achado real: 'contrato'/'proposta' ainda não
    foram replicados pra lá, só têm o fallback contrato_template/)."""
    c = _login(http_client_factory, "dir_l1")
    status, body = c.get("/api/documentos/modelos/padroes-disponiveis")
    assert status == 200, body
    assert body["ok"] is True
    assert "termo_vistoria" in body["tipos"]
    assert "termo_responsabilidade" in body["tipos"]
    assert "contrato" not in body["tipos"]
    assert "proposta" not in body["tipos"]


# ── POST /api/documentos/modelos/usar-padrao ─────────────────────────────────────

def test_usar_padrao_sem_capacidade_403(http_client_factory):
    c = _login(http_client_factory, "cons_l1")   # operador: sem gerir_documentos
    status, body = c.post("/api/documentos/modelos/usar-padrao", {"tipo": "termo_vistoria"})
    assert status == 403, body


def test_usar_padrao_tipo_sem_modelo_400(http_client_factory):
    c = _login(http_client_factory, "dir_l1")
    status, body = c.post("/api/documentos/modelos/usar-padrao", {"tipo": "contrato"})
    assert status == 400, body
    assert "não há modelo padrão" in body["erro"]


def test_usar_padrao_devolve_analise_com_marcadores_conhecidos(http_client_factory):
    """O modelo padrão nunca pode usar marcador fora do CATALOGO — se usasse, sairia
    literal ('[MARCADOR]') no PDF de toda loja que o ativasse sem perceber."""
    c = _login(http_client_factory, "dir_l1")
    status, body = c.post("/api/documentos/modelos/usar-padrao", {"tipo": "termo_vistoria"})
    assert status == 200, body
    assert body["ok"] is True
    assert body["tipo"] == "termo_vistoria"
    assert body["staging"] is None
    assert body["origem_sha256"] is None
    assert body["corpo_md"].strip()
    assert body["analise"]["desconhecidos"] == []
    assert body["analise"]["bloqueia_ativacao"] is False


def test_usar_padrao_seguido_de_ativar_cria_versao_sem_origem(app_db, seed, http_client_factory):
    c = _login(http_client_factory, "dir_l1")
    status, padrao = c.post("/api/documentos/modelos/usar-padrao", {"tipo": "termo_responsabilidade"})
    assert status == 200, padrao

    status, body = c.post("/api/documentos/modelos", {
        "tipo": "termo_responsabilidade", "corpo_md": padrao["corpo_md"],
        "origem_nome": padrao["origem_nome"], "staging": padrao["staging"],
        "origem_sha256": padrao["origem_sha256"], "cravados_aprovados": [],
    })
    assert status == 200, body
    assert body["ok"] is True

    db = app_db.get_session()
    try:
        m = db.get(app_db.DocumentoModelo, body["modelo"]["id"])
        assert m.ativo == 1
        assert m.origem_path is None
        assert m.origem_nome == "Modelo padrão Orizon"
    finally:
        db.close()


def test_modelos_padrao_arquivos_tem_forma_de_tipo_valida():
    """Todo .md em modelos_documentos_padrao/ (exceto README) precisa nomear um tipo que
    o backend reconheça — senão o arquivo existe mas nunca aparece em nenhuma tela."""
    import mod_documentos
    for nome in os.listdir(mod_documentos.MODELOS_PADRAO_DIR):
        if not nome.endswith(".md") or nome == "README.md":
            continue
        tipo = nome[:-3]
        assert mod_documentos.tipo_forma_valida(tipo), (
            "%s não corresponde a um tipo válido de mod_documentos.TIPOS" % nome)
