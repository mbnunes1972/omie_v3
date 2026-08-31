# -*- coding: utf-8 -*-
"""GET /api/projetos/<nome>/aditivo/<id>/pdf — PDF de uma renegociação HISTÓRICA específica
(achado do usuário 2026-08-25, Visão Geral do Projeto). O endpoint singular existente
(.../aditivo/pdf) só serve o mais recente; a Visão Geral precisa baixar o PDF de QUALQUER
renegociação do histórico, não só a última."""
import json

from tests.test_aditivo_wizard_e2e import _setup, _upsert_compl, _login


def test_pdf_por_id_de_cada_renegociacao(http_client_factory, seed, app_db):
    nome, pid, pid2 = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    _upsert_compl(app_db, nome, pid2, venda=9000.0, cfo=3000.0)
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    primeiro_id = body["aditivo"]["id"]
    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        corpo = {"parte": parte, "nome": quem, "cpf": "111.444.777-35"}
        if parte == "cliente":
            corpo["forma_pagamento"] = json.dumps({"tipo": "avista", "entrada_valor": 1.0})
        st_ass, body_ass = c.post(f"/api/projetos/{nome}/aditivo/assinar", corpo)
        assert st_ass == 200 and body_ass["status"] in ("assinado_loja", "assinado"), body_ass

    # ACHADO-21/6-b: aditivo #1 já assinado — "Negociar Complemento" de novo cria Orcamento NOVO.
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"novo": True})
    assert st == 200 and body["ok"], body
    segundo_id = body["aditivo"]["id"]
    assert segundo_id != primeiro_id

    st1, raw1 = c.get(f"/api/projetos/{nome}/aditivo/{primeiro_id}/pdf")
    st2, raw2 = c.get(f"/api/projetos/{nome}/aditivo/{segundo_id}/pdf")
    assert st1 == 200 and raw1[:4] == b"%PDF"
    assert st2 == 200 and raw2[:4] == b"%PDF"

    # id inexistente / de outro projeto → 404 (nunca vaza PDF fora do escopo)
    st3, _ = c.get(f"/api/projetos/{nome}/aditivo/999999/pdf")
    assert st3 == 404


def test_pdf_por_id_404_fora_do_escopo_da_loja(http_client_factory, seed, app_db):
    nome, pid, pid2 = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    _upsert_compl(app_db, nome, pid2, venda=9000.0, cfo=3000.0)
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    aditivo_id = body["aditivo"]["id"]

    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    st, _ = c2.get(f"/api/projetos/{nome}/aditivo/{aditivo_id}/pdf")
    assert st in (403, 404)
