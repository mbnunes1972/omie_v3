# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-51 — terceira condição (04/09, DECIDIDO pelo Marcelo):
"assim como um projeto cancelado, uma NF-e cancelada deve liberar a NF-e de fábrica de origem —
pode haver erro na emissão e a NF-e da fábrica será a mesma." A trava passa de "chave viva em
projeto ativo" para "chave viva, em projeto ativo, com emissão não cancelada" — mesmo desenho das
duas primeiras condições (documento removido / projeto cancelado)."""
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


def _limpar_docs_etapa15(app_db, proj):
    import datetime
    db = app_db.get_session()
    db.query(app_db.CicloDocumento).filter_by(
        projeto_nome=proj, etapa_codigo="15", tipo="nfe_fabrica_xml"
    ).update({"removido_em": datetime.datetime.utcnow()})
    db.commit(); db.close()


def _marcar_emissao(app_db, fabrica_doc_id, status, ref=None):
    """Cria (ou atualiza) o DocumentoFiscal ligado a este documento da fábrica, no status pedido —
    dispensa emitir de verdade (o que interessa aqui é só o estado que a trava consulta)."""
    db = app_db.get_session()
    reg = db.query(app_db.DocumentoFiscal).filter_by(fabrica_doc_id=fabrica_doc_id).first()
    if reg is None:
        reg = app_db.DocumentoFiscal(ref=ref or ("REF-%d" % fabrica_doc_id),
                                     tipo_documento="produto", fabrica_doc_id=fabrica_doc_id)
        db.add(reg)
    reg.status = status
    db.commit(); db.close()


def test_nfe_cancelada_libera_a_mesma_nf_e_da_fabrica(http_client_factory, seed, app_db, projetos_dir):
    _limpar_docs_etapa15(app_db, seed["projeto_l1"])
    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    st1, r1 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="original.xml")
    assert st1 == 200 and r1.get("ok") is True, r1
    doc_id = r1["documento_id"]

    # antes de cancelar a emissão, a trava normal se aplica (mesmo projeto).
    st_antes, r_antes = _upload(c, proj, _fixture("nfe_basica.xml"), filename="tentativa2.xml")
    assert st_antes == 400, r_antes

    _marcar_emissao(app_db, doc_id, "cancelado")
    st_depois, r_depois = _upload(c, proj, _fixture("nfe_basica.xml"), filename="tentativa3.xml")
    assert st_depois == 200 and r_depois.get("ok") is True, r_depois


def test_nfe_em_erro_nao_cancelada_continua_bloqueando(http_client_factory, seed, app_db, projetos_dir):
    """Controle: só CANCELADA libera — `erro` (rejeição) não é a mesma coisa, a trava continua
    valendo (a nota da fábrica pode não ter chegado a ser processada de verdade ainda)."""
    _limpar_docs_etapa15(app_db, seed["projeto_l1"])
    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    st1, r1 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="original.xml")
    assert st1 == 200 and r1.get("ok") is True, r1
    doc_id = r1["documento_id"]

    _marcar_emissao(app_db, doc_id, "erro")
    st2, r2 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="tentativa2.xml")
    assert st2 == 400, r2
