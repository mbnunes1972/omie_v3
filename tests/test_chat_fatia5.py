# -*- coding: utf-8 -*-
"""Chat do Orizon — Fatia 5 (Documento compartilhável).

Contratos: `documento_ref_id` vira FK real de `ciclo_documentos` e SÓ vale em
natureza=transferencia (regra da Fatia 2, inalterada); o documento anexado precisa ser do
MESMO projeto da conversa (400 se não for — não vaza referência entre projetos); a mensagem
devolve nome/tipo do documento RESOLVIDOS (não só o id cru)."""


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _mk_func(db, app_db, loja_id, nome_pessoa):
    fn = db.query(app_db.Funcao).filter_by(loja_id=loja_id, nome="Conferente").first()
    if fn is None:
        fn = app_db.Funcao(loja_id=loja_id, nome="Conferente")
        db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja_id, nome=nome_pessoa, funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    return f


def _mk_doc(db, app_db, projeto, tipo="pe_projeto_executivo", nome="planta.pdf"):
    d = app_db.CicloDocumento(projeto_nome=projeto, etapa_codigo="11a", tipo=tipo,
                              arquivo_path="docs/" + nome, nome_original=nome)
    db.add(d); db.flush()
    return d


def test_anexa_documento_do_projeto_e_resolve_nome(http_client_factory, seed, app_db):
    db = app_db.get_session()
    f = _mk_func(db, app_db, seed["loja1_id"], "Recebe Doc")
    doc = _mk_doc(db, app_db, "Proj_L1", nome="PE_cozinha.pdf")
    db.commit(); fid, did = f.id, doc.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "segue o PE", "natureza": "transferencia",
                       "transferido_para_funcionario_id": fid, "documento_ref_id": did})
    assert st == 201 and body["ok"], body
    m = body["mensagem"]
    assert m["documento_ref_id"] == did
    assert m["documento_nome"] == "PE_cozinha.pdf"          # resolvido, não só o id
    assert m["documento_tipo"] == "pe_projeto_executivo"

    # e a listagem também resolve
    st, body = c.get("/api/projetos/Proj_L1/conversa")
    m = next(x for x in body["mensagens"] if x["documento_ref_id"] == did)
    assert m["documento_nome"] == "PE_cozinha.pdf"


def test_documento_de_outro_projeto_recusado(http_client_factory, seed, app_db):
    db = app_db.get_session()
    f = _mk_func(db, app_db, seed["loja1_id"], "Recebe Doc 2")
    doc_l2 = _mk_doc(db, app_db, "Proj_L2", nome="doc_da_l2.pdf")
    db.commit(); fid, did = f.id, doc_l2.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "x", "natureza": "transferencia",
                       "transferido_para_funcionario_id": fid, "documento_ref_id": did})
    assert st == 400, body
    # id inexistente também é 400 (não 500 de FK)
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "x", "natureza": "transferencia",
                       "transferido_para_funcionario_id": fid, "documento_ref_id": 999999})
    assert st == 400, body


def test_documento_em_interacao_continua_recusado(http_client_factory, seed, app_db):
    """Regra da Fatia 2, inalterada: campos de transferência não valem em interação."""
    db = app_db.get_session()
    doc = _mk_doc(db, app_db, "Proj_L1", nome="avulso.pdf")
    db.commit(); did = doc.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "x", "natureza": "interacao", "documento_ref_id": did})
    assert st == 400, body
