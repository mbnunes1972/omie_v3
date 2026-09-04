# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-51 — nada impedia carregar a mesma NF-e da fábrica duas
vezes (DECIDIDO: bloquear). Dedup pela CHAVE lida do XML (Id de <infNFe>), nunca pelo nome do
arquivo; respeita o ACHADO-30 — documento REMOVIDO não bloqueia um novo upload da mesma nota."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import uuid as _uuid, json as _json
import urllib.request, urllib.error


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _fixture(nome):
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "nfe", nome), "rb") as f:
        return f.read()


def _upload(c, proj, data, filename="nfe.xml"):
    boundary = "----t" + _uuid.uuid4().hex
    parts = [("--"+boundary+"\r\n").encode(),
             (f'Content-Disposition: form-data; name="arquivo"; filename="{filename}"\r\n').encode(),
             b"Content-Type: application/octet-stream\r\n\r\n", data, b"\r\n",
             ("--"+boundary+"--\r\n").encode()]
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/15/nfe-fabrica",
                                 data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary="+boundary)
    req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def _post(c, path, body):
    req = urllib.request.Request(c.base + path, data=_json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if c.cookie: req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def _limpar_docs_etapa15(app_db, proj):
    """O seed é compartilhado entre testes do arquivo — sem limpar, o upload de um teste
    fica vivo pro próximo, e a própria trava do achado (que é o que estamos testando)
    rejeitaria o 1º upload de um teste seguinte como se fosse duplicata do anterior.
    Soft-delete (removido_em), não DELETE: linhas antigas têm mensagem de conversa
    apontando pro documento (FK), e o próprio _docs_vivos já ignora removido_em."""
    import datetime
    db = app_db.get_session()
    db.query(app_db.CicloDocumento).filter_by(
        projeto_nome=proj, etapa_codigo="15", tipo="nfe_fabrica_xml"
    ).update({"removido_em": datetime.datetime.utcnow()})
    db.commit(); db.close()


def test_segundo_upload_da_mesma_chave_e_recusado(http_client_factory, seed, app_db, projetos_dir):
    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    _limpar_docs_etapa15(app_db, proj)
    st1, r1 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="fabrica_v1.xml")
    assert st1 == 200 and r1.get("ok") is True, r1
    # mesmo conteúdo (mesma chave), nome de arquivo DIFERENTE de propósito — o achado é
    # explícito: nome diferente não faz nota diferente.
    st2, r2 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="fabrica_v2_recebida_de_novo.xml")
    assert st2 == 400, r2
    assert "fabrica_v1.xml" in r2["erro"], r2


def test_chave_diferente_nao_e_bloqueada(http_client_factory, seed, app_db, projetos_dir):
    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    _limpar_docs_etapa15(app_db, proj)
    st1, r1 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="a.xml")
    assert st1 == 200 and r1.get("ok") is True, r1
    st2, r2 = _upload(c, proj, _fixture("nfe_sem_ipi.xml"), filename="b.xml")
    assert st2 == 200 and r2.get("ok") is True, r2   # chave diferente — não é duplicata


def test_remover_e_recarregar_a_mesma_nota_continua_permitido(http_client_factory, seed, app_db, projetos_dir):
    """ACHADO-30: documento removido não pode virar uma porta sem volta. Sobe, remove, sobe de
    novo a MESMA chave — tem que passar, porque o vivo (_docs_vivos) não vê mais o removido."""
    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    _limpar_docs_etapa15(app_db, proj)
    st1, r1 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="original.xml")
    assert st1 == 200 and r1.get("ok") is True, r1
    doc_id = r1["documento_id"]
    st_rm, r_rm = _post(c, f"/api/projetos/{proj}/ciclo/15/documentos/{doc_id}/remover", {})
    assert st_rm == 200 and r_rm.get("ok") is True, r_rm
    st2, r2 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="recarregada.xml")
    assert st2 == 200 and r2.get("ok") is True, r2
