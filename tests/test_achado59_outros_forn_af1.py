# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-59 — o Outros Fornecedores da AF1 não era gravado.

Medido (F2-25, Passo 0c): o painel de AF (`_PROV_RUBRICAS`, static/index.html) mostra um campo
editável pra "Outros Fornecedores" (chave `out_forn`) e o envia normalmente pro servidor — a
requisição chega, e `ProvisaoRegistro.itens_json` PERSISTE o valor digitado (confirmado:
`tests/test_provisao_registro.py::test_rev1_revisa_grava_editado` já provava isso). Mas
`mod_contabil.disparar_deltas_af` — quem transforma o `itens` aprovado em lançamento de
verdade — nunca gerava evento pra ela: `_AF_ITEM_RUBRICA` excluía `out_forn` de propósito,
comentário original dizendo que ela "só nasce por reclassificação (conferencia_pedido, etapa
12)". Resultado: a tela aceitava, o usuário acreditava, e nada era provisionado — enquanto
Impostos (mesma rota, mesmo painel) funcionava normalmente.

O par ativo×provisão (1.1.06.14/2.1.04.14, "Outros Fornecedores a Apropriar") já existia pronto
(usado pelo reconhecimento de despesa) — faltava só a entrada em `_PROV_FECHAMENTO` pra
`ajustar_provisao_delta` achá-lo. Convive sem conflito com a reclassificação da conferência
(refs em namespaces diferentes: `af:...:outros_forn` × `conf:...:outros`).

F2-28 Passo 2 (05/09, DECIDIDO): o mecanismo por trás mudou — `out_forn` não passa mais pelo
ajuste independente (`disparar_deltas_af`/`_AF_ITEM_RUBRICA`, que a excluía sempre agora); toda
edição de `out_forn` na AF é RECLASSIFICAÇÃO automática de Custo de Fábrica pra Outros
Fornecedores (Custo de Fábrica virou read-only, contrapartida automática — main.py, POST
.../provisoes/<rev>). O teste abaixo continua passando com o MESMO valor final (500,0) porque
`_setup_venda` constitui CFO=4.000,00 — sobra de sobra pra migrar 500 — mas o lançamento real
agora é diferente: debita 2.1.04.06 (e o ativo 1.1.06.06 espelho), não mais um ajuste isolado
de 2.1.04.14 sozinho."""
import json as _json

from tests.test_provisao_registro import _setup_venda


def test_out_forn_editado_na_af1_gera_evento_real(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    itens = {"frete_fab": 0.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
             "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0,
             "prov_imp": 0.0, "out_forn": 500.0}
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "revisa", "itens": itens, "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body

    _, prov = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert prov["provisoes"]["rev1"]["itens"]["out_forn"] == 500.0   # já persistia antes

    import mod_contabil as mc
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        saldo = mc._mov(db, ot, oid, "2.1.04.14", "credor", None, None, projeto_id=seed["projeto_l1"])
        assert saldo == 500.0, (
            "out_forn digitado na AF1 tem que provisionar de verdade — o defeito era exatamente "
            "'a tela aceita, o usuário acredita, e nada acontece'")
        # F2-28 Passo 2: a contrapartida é AUTOMÁTICA contra o Custo de Fábrica (reclassificação,
        # não mais um ajuste isolado) — `_setup_venda` só grava o snapshot `ProvisaoRegistro`
        # ("venda"), nunca lança no razão, então o CFO real aqui é 0 antes da AF; a perna da
        # PROVISÃO da reclassificação sempre move o valor CHEIO pedido (ACHADO-05 — só a perna do
        # ATIVO espelho é capada ao saldo em aberto), por isso vai a -500,00 (não capada a 0).
        cfo = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None, projeto_id=seed["projeto_l1"])
        assert cfo == -500.0, "a migração tem que debitar o Custo de Fábrica automaticamente"
    finally:
        db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
        db.commit(); db.close()


def test_impostos_continua_funcionando_controle_irmao(http_client_factory, app_db, seed, projetos_dir):
    """Controle-irmão: Impostos (que o Marcelo já viu funcionar, "ajustou para menor") continua
    provisionando — o conserto do out_forn não mexeu no caminho das outras rubricas."""
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    itens = {"frete_fab": 0.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
             "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0,
             "prov_imp": 300.0, "out_forn": 0.0}
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "revisa", "itens": itens, "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body

    import mod_contabil as mc
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        saldo = mc._mov(db, ot, oid, "2.1.04.13", "credor", None, None, projeto_id=seed["projeto_l1"])
        assert saldo == 300.0
    finally:
        db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
        db.commit(); db.close()
