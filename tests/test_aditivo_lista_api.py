# -*- coding: utf-8 -*-
"""GET /api/projetos/<nome>/aditivos (plural) — histórico COMPLETO de renegociações (achado do
usuário 2026-08-25, Visão Geral do Projeto): o endpoint singular /aditivo só devolve o mais
recente. Prova principal: a 2ª renegociação (novo aditivo) não corrompe o snapshot de condição de
pagamento da 1ª — o risco real que existia antes do forma_pagamento_snapshot em dados_json.

Atualizado pelo ACHADO-21 (docs/db/TAREFA_ACHADO21.md, 6-b, 30/08): "Negociar Complemento" NÃO
reaproveita mais o orçamento que já tem aditivo assinado — a rodada 2 cria um Orcamento NOVO, e o
da rodada 1 fica imutável (nunca mais zerado). A prova do docstring acima fica ainda mais direta:
não é mais "o snapshot sobrevive a um zeramento do MESMO orçamento", é "o orçamento da rodada 1
nem é tocado de novo"."""
import json
import os

from tests.test_aditivo_wizard_e2e import _setup, _upsert_compl, _login


def test_lista_aditivos_preserva_forma_pagamento_de_cada_renegociacao(http_client_factory, seed, app_db):
    nome, pid, pid2 = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    _upsert_compl(app_db, nome, pid2, venda=9000.0, cfo=3000.0)

    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    orc_id = body["orcamento"]["id"]

    # Rodada 1: parcelamento à vista R$ 14.444,44 — grava direto no Orcamento (mesmo formato de
    # window._planoPagamento, salvo via Negociação normal).
    plano_1 = {"nome_forma": "À Vista", "tipo": "avista", "entrada_forma": "pix",
               "entrada_data": "2026-09-01", "entrada_valor": 14444.44,
               "parcelas": [{"valor": 14444.44}]}
    db = app_db.get_session()
    db.get(app_db.Orcamento, orc_id).forma_pagamento = json.dumps(plano_1)
    db.commit(); db.close()

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    primeiro_id = body["aditivo"]["id"]
    assert body["aditivo"]["dados"]["forma_pagamento_snapshot"]["entrada_valor"] == 14444.44

    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        corpo = {"parte": parte, "nome": quem, "cpf": "111.444.777-35"}
        if parte == "cliente":
            corpo["forma_pagamento"] = json.dumps(plano_1)
        st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar", corpo)
        assert st == 200, body

    # Rodada 2: "Negociar Complemento" de novo — ACHADO-21/6-b: já tem aditivo assinado, então
    # NÃO reaproveita mais — cria um Orcamento NOVO, e o da rodada 1 fica intocado.
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    orc_id2 = body["orcamento"]["id"]
    assert orc_id2 != orc_id, "6-b: rodada 2 pós-assinatura tem que criar Orcamento novo"
    db = app_db.get_session()
    assert db.get(app_db.Orcamento, orc_id).forma_pagamento == json.dumps(plano_1), (
        "o orçamento da rodada 1 (já assinado) não pode ser tocado pela rodada 2")
    db.close()

    # Novo plano, BEM diferente do primeiro — parcelado, sem entrada. Grava no orçamento NOVO.
    plano_2 = {"nome_forma": "Cartão", "tipo": "cartao", "entrada_forma": "", "entrada_data": "",
               "entrada_valor": 0.0, "parcelas": [{"valor": 4814.81}] * 3}
    db = app_db.get_session()
    db.get(app_db.Orcamento, orc_id2).forma_pagamento = json.dumps(plano_2)
    db.commit(); db.close()

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"novo": True})
    assert st == 200 and body["ok"], body
    segundo_id = body["aditivo"]["id"]
    assert segundo_id != primeiro_id
    assert body["aditivo"]["dados"]["forma_pagamento_snapshot"]["entrada_valor"] == 0.0
    assert len(body["aditivo"]["dados"]["forma_pagamento_snapshot"]["parcelas"]) == 3

    # O histórico completo mostra as DUAS renegociações, cada uma com sua condição intacta —
    # a prova de que "guardar histórico, não sobrescrever" funciona ponta a ponta.
    st, body = c.get(f"/api/projetos/{nome}/aditivos")
    assert st == 200 and body["ok"], body
    itens = body["aditivos"]
    assert [i["id"] for i in itens] == [primeiro_id, segundo_id]   # ordem cronológica
    assert itens[0]["dados"]["forma_pagamento_snapshot"]["entrada_valor"] == 14444.44
    assert itens[0]["status"] == "assinado"
    assert itens[1]["dados"]["forma_pagamento_snapshot"]["entrada_valor"] == 0.0
    assert itens[1]["status"] == "para_assinatura"
    assert all("parcela_id" in i for i in itens)


def test_lista_aditivos_vazia_quando_nenhum_gerado(http_client_factory, seed):
    # Proj_L2 (loja 2) — nenhum teste deste arquivo gera aditivo nele; _setup() sempre reaproveita
    # o mesmo projeto seedado (Proj_L1), então testar "vazio" ali seria order-dependent.
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, body = c.get(f"/api/projetos/{seed['projeto_l2']}/aditivos")
    assert st == 200 and body["ok"] is True
    assert body["aditivos"] == []


def test_lista_aditivos_404_fora_do_escopo_da_loja(http_client_factory, seed, app_db):
    nome, _pid, _pid2 = _setup(app_db, seed)
    # usuário de outra loja (seed cross-tenancy padrão do projeto) não enxerga o projeto
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, body = c.get(f"/api/projetos/{nome}/aditivos")
    assert st == 404, body
