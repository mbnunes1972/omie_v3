# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-51 (extensão 04/09) — DECIDIDO pelo Marcelo: a mesma
NF-e não pode cobrir dois projetos, bloquear também ENTRE projetos. Exceção que muda o desenho:
projeto CANCELADO libera a chave (a nota que ele recebeu pode voltar a ser processada em outro
projeto) — a trava não é "esta chave já existe", é "esta chave está VIVA em projeto ATIVO".
Medido antes de codar: `_projeto_cancelado` (main.py) já lê `Projeto.status == "cancelado"`,
reusado por `_contrato_assinado` — discriminador existente, nenhum estado novo precisou nascer."""
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
    """Mesmo isolamento do arquivo irmão (test_achado51_nfe_fabrica_duplicata.py) — soft-delete,
    não DELETE, por causa da FK de conversa_mensagens."""
    import datetime
    db = app_db.get_session()
    db.query(app_db.CicloDocumento).filter_by(
        projeto_nome=proj, etapa_codigo="15", tipo="nfe_fabrica_xml"
    ).update({"removido_em": datetime.datetime.utcnow()})
    db.commit(); db.close()


def _marcar_cancelado(app_db, proj):
    db = app_db.get_session()
    pm = db.get(app_db.Projeto, proj)
    if pm is None:
        pm = app_db.Projeto(nome_safe=proj)
        db.add(pm)
    pm.status = "cancelado"
    db.commit(); db.close()


def test_mesma_chave_em_projeto_diferente_e_recusada_nomeando_o_projeto(
        http_client_factory, seed, app_db, projetos_dir):
    _limpar_docs_etapa15(app_db, seed["projeto_l1"])
    _limpar_docs_etapa15(app_db, seed["projeto_l2"])
    c1 = _login(http_client_factory, "dir_l1")
    proj1 = seed["projeto_l1"]
    st1, r1 = _upload(c1, proj1, _fixture("nfe_basica.xml"), filename="fabrica.xml")
    assert st1 == 200 and r1.get("ok") is True, r1

    c2 = _login(http_client_factory, "dir_l2")
    proj2 = seed["projeto_l2"]
    st2, r2 = _upload(c2, proj2, _fixture("nfe_basica.xml"), filename="mesma_de_outro_jeito.xml")
    assert st2 == 400, r2
    assert proj1 in r2["erro"], r2


def test_projeto_cancelado_libera_a_chave_para_outro_projeto(
        http_client_factory, seed, app_db, projetos_dir):
    _limpar_docs_etapa15(app_db, seed["projeto_l1"])
    _limpar_docs_etapa15(app_db, seed["projeto_l2"])
    c1 = _login(http_client_factory, "dir_l1")
    proj1 = seed["projeto_l1"]
    st1, r1 = _upload(c1, proj1, _fixture("nfe_basica.xml"), filename="fabrica.xml")
    assert st1 == 200 and r1.get("ok") is True, r1

    c2 = _login(http_client_factory, "dir_l2")
    proj2 = seed["projeto_l2"]
    # antes de cancelar, a trava normal do lado de fora se aplica.
    st_antes, r_antes = _upload(c2, proj2, _fixture("nfe_basica.xml"), filename="outro_nome.xml")
    assert st_antes == 400, r_antes

    _marcar_cancelado(app_db, proj1)
    st_depois, r_depois = _upload(c2, proj2, _fixture("nfe_basica.xml"), filename="outro_nome.xml")
    assert st_depois == 200 and r_depois.get("ok") is True, r_depois


def test_remover_e_recarregar_no_mesmo_projeto_continua_permitido(
        http_client_factory, seed, app_db, projetos_dir):
    """Controle-irmão: a extensão pra ENTRE projetos não pode endurecer o caso já resolvido
    (mesmo projeto, ACHADO-30) — remover e recarregar a mesma nota no MESMO projeto continua
    liso, sem precisar cancelar nada."""
    _limpar_docs_etapa15(app_db, seed["projeto_l1"])
    _limpar_docs_etapa15(app_db, seed["projeto_l2"])
    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    st1, r1 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="original.xml")
    assert st1 == 200 and r1.get("ok") is True, r1
    doc_id = r1["documento_id"]
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/15/documentos/{doc_id}/remover",
                                 data=b"{}", method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", c.cookie)
    r_rm = urllib.request.urlopen(req, timeout=5)
    assert _json.loads(r_rm.read())["ok"] is True

    st2, r2 = _upload(c, proj, _fixture("nfe_basica.xml"), filename="recarregada.xml")
    assert st2 == 200 and r2.get("ok") is True, r2
