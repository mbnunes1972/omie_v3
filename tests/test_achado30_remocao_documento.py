"""ACHADO-30 / TAREFA_BLOCO_FISCAL item 1 — documento de fase não tinha como ser removido:
as tentativas se acumulavam na tela e não havia como tirar a errada.

DECIDIDO 03/09 (Marcelo): remoção MARCADA (`removido_em`/`removido_por_id`), nunca DELETE — o
registro e o arquivo continuam existindo, a promessa append-only do modelo segue de pé, e o
rastro de que houve tentativa não some. Enquanto a fase está ABERTA remove-se à vontade; com a
fase concluída, o documento é imutável.

O risco real que estes aceites guardam não é a tela: é o PORTÃO. Um documento removido que
continuasse contando faria "existe XML da etapa 12?" responder sim por causa de um arquivo
descartado, e deixaria a emissão da NF-e aceitar um XML da fábrica que alguém já tinha tirado
da fase. Por isso a leitura tem porta única (`main._docs_vivos`) e uma trava anti-órfão.
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.test_ciclo_pe_e2e import _post_multipart, _login

_MAIN = os.path.join(os.path.dirname(__file__), "..", "main.py")


def _sobe_doc(c, proj, etapa="11a", nome="planta.pdf"):
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/{etapa}/documento",
        {"login": "dir_l2", "senha": "senha123"},
        file_field="arquivo", filename=nome, filedata=b"%PDF-fake")
    assert st == 200 and body.get("ok") is True, body
    return body["documento_id"]


def test_aceite1_remover_tira_da_tela_sem_apagar_o_registro(http_client_factory, seed, projetos_dir, app_db):
    """O aceite do achado: a tentativa errada some da listagem — e o registro continua lá, com
    quem removeu e quando. Remoção não é apagar."""
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    doc_id = _sobe_doc(c, proj)
    _sobe_doc(c, proj, nome="planta_v2.pdf")
    st, r = c.post(f"/api/projetos/{proj}/ciclo/11a/documentos/{doc_id}/remover",
                   {"login": "dir_l2", "senha": "senha123"})
    assert st == 200 and r.get("ok") is True, r
    st2, docs = c.get(f"/api/projetos/{proj}/ciclo/pe")
    assert st2 == 200
    ids = [d["id"] for d in docs["documentos"]]
    assert doc_id not in ids, "documento removido não pode continuar na tela"
    assert len(ids) >= 1, "a remoção tira só o removido, não a fase inteira"
    db = app_db.get_session()
    linha = db.get(app_db.CicloDocumento, doc_id)
    assert linha is not None, "remoção é marcada, o registro NÃO some do banco"
    assert linha.removido_em is not None and linha.removido_por_id is not None, "quem e quando"
    assert linha.arquivo_path, "o arquivo continua referenciado — não apagamos do disco"
    db.close()


def test_aceite2_documento_removido_nao_satisfaz_o_portao_da_etapa_12(seed, app_db):
    """O caso que faria a remoção ser cosmética. O XML da etapa 12 é o que libera concluir as
    etapas operacionais (`guarda_conclusao_operacional`). Prova em duas metades, de propósito:
    a consulta CRUA continua enxergando o documento removido — é assim que o defeito voltaria —
    e a porta única (`_docs_vivos`), que é quem o portão usa, não enxerga."""
    import main, mod_ciclo
    proj = seed["projeto_l2"]
    tipo12 = mod_ciclo.tipo_doc_operacional("12")
    db = app_db.get_session()
    doc = app_db.CicloDocumento(projeto_nome=proj, etapa_codigo="12", tipo=tipo12,
                                arquivo_path="ciclo/12/x.xml", nome_original="pedido.xml")
    db.add(doc); db.commit()
    vivo = main._docs_vivos(db, projeto_nome=proj, etapa_codigo="12", tipo=tipo12).first()
    assert vivo is not None, "pré-condição: com o documento vivo, o portão enxerga"
    doc.removido_em = __import__("datetime").datetime.utcnow()
    db.commit()
    cru = db.query(app_db.CicloDocumento).filter_by(
        projeto_nome=proj, etapa_codigo="12", tipo=tipo12).first()
    assert cru is not None, "a consulta crua AINDA vê — é por isso que a porta única existe"
    depois = main._docs_vivos(db, projeto_nome=proj, etapa_codigo="12", tipo=tipo12).first()
    assert depois is None, "o portão não pode enxergar documento removido"
    db.close()


def test_aceite3_fase_concluida_recusa_remocao(http_client_factory, seed, projetos_dir, app_db):
    """A outra metade da regra: depois que a fase fecha, o documento é imutável.

    O `finally` não é zelo decorativo — a primeira versão deste teste concluía a 11a e ia embora
    assim, e os dois aceites seguintes (mesmo projeto semeado, mesma sessão de banco) recebiam
    409 por causa DESTE teste, não do que estavam medindo. É a LP-04 em miniatura: fixture que
    monta estado direto no banco e não devolve prova menos do que promete e ainda derruba o
    vizinho."""
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    doc_id = _sobe_doc(c, proj)
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="11a").first()
    if et is None:
        et = app_db.CicloEtapa(projeto_nome=proj, etapa_codigo="11a")
        db.add(et); db.flush()
    status_antes = et.status
    et.status = "concluido"
    db.commit(); db.close()
    try:
        st, r = c.post(f"/api/projetos/{proj}/ciclo/11a/documentos/{doc_id}/remover",
                       {"login": "dir_l2", "senha": "senha123"})
        assert st == 409, (st, r)
        db = app_db.get_session()
        assert db.get(app_db.CicloDocumento, doc_id).removido_em is None, "recusou, então não marcou"
        db.close()
    finally:
        db = app_db.get_session()
        et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="11a").first()
        et.status = status_antes
        db.commit(); db.close()


def test_aceite4_autoridade_espelha_a_do_upload(http_client_factory, seed, projetos_dir):
    """A autoridade de remover é a MESMA de subir, incluindo o atalho: `_usuario_com_capacidade`
    é sessão-primeiro (2026-07-24, "logado com permissão não redigita senha"), então quem já tem
    `executar_pe` remove sem senha — igual ao upload. O que não passa é credencial de TERCEIRO
    errada, que é o caminho de quem não tem a permissão e pede a de alguém que tem."""
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    doc_id = _sobe_doc(c, proj)
    st, r = c.post(f"/api/projetos/{proj}/ciclo/11a/documentos/{doc_id}/remover",
                   {"login": "dir_l2", "senha": "errada"})
    assert st == 403, ("senha de terceiro errada tem que ser recusada", st, r)
    doc_id2 = _sobe_doc(c, proj, nome="planta_b.pdf")
    st2, r2 = c.post(f"/api/projetos/{proj}/ciclo/11a/documentos/{doc_id2}/remover", {})
    assert st2 == 200, ("sessão com a capacidade dispensa senha, como no upload", st2, r2)


def test_aceite5_remover_duas_vezes_nao_muda_quem_removeu(http_client_factory, seed, projetos_dir, app_db):
    """Idempotência pela própria porta de leitura: a segunda chamada não acha mais o documento
    (ele já não está vivo), então responde 404 em vez de reescrever o rastro."""
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    doc_id = _sobe_doc(c, proj)
    st, _ = c.post(f"/api/projetos/{proj}/ciclo/11a/documentos/{doc_id}/remover",
                   {"login": "dir_l2", "senha": "senha123"})
    assert st == 200
    db = app_db.get_session()
    quando = db.get(app_db.CicloDocumento, doc_id).removido_em
    db.close()
    st2, _ = c.post(f"/api/projetos/{proj}/ciclo/11a/documentos/{doc_id}/remover",
                    {"login": "dir_l2", "senha": "senha123"})
    assert st2 == 404
    db = app_db.get_session()
    assert db.get(app_db.CicloDocumento, doc_id).removido_em == quando, "o rastro original fica"
    db.close()


def test_trava_toda_leitura_de_documento_passa_pela_porta_unica():
    """Trava anti-órfão (mesmo padrão da trava de capacidade em `test_perfis_matriz.py`): uma
    leitura nova de `CicloDocumento` que esqueça o filtro de removido faz a remoção virar
    cosmética — e o modo de falhar é silencioso, que é o pior. Toda leitura crua tem que tratar
    `removido_em` explicitamente na mesma linha ou nas duas seguintes; o normal é usar
    `_docs_vivos`."""
    linhas = open(_MAIN, encoding="utf-8").read().splitlines()
    orfas = []
    for i, ln in enumerate(linhas):
        if re.search(r"db\.(query|get)\(CicloDocumento", ln):
            vizinhanca = " ".join(linhas[i:i + 3])
            if "removido_em" not in vizinhanca:
                orfas.append("%d: %s" % (i + 1, ln.strip()))
    assert not orfas, (
        "leitura de CicloDocumento sem tratar removido_em (use main._docs_vivos):\n"
        + "\n".join(orfas))
