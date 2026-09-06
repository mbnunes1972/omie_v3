# -*- coding: utf-8 -*-
"""F2-29 Fatia A — o F2-28 mediu que "Atual" (painel de Provisões) lia `_negociacao_breakdown`
(recomputa da negociação salva, nunca o razão) e consertou só `custo_fabrica`/`out_forn` — as
duas rubricas que o percurso do Marcelo exercitou. Medido aqui: as outras 17 rubricas de
`mod_provisoes.itens_provisao` continuavam com o MESMO defeito (regra dos irmãos, ACHADO-26) —
um gerente olhando a Provisão de Montagem depois de uma efetivação veria o valor da venda, não
o razão. Corrigido: toda rubrica com par ativo×provisão (`mod_contabil._PAINEL_ITEM_RUBRICA_
TODAS`) passa a ler o SALDO VIVO da provisão. `custo_financeiro` fica de fora, de propósito —
rota do ramo financeiro, sem conta de provisão própria nesta família."""
from tests.test_provisao_registro import _setup_venda


def test_atual_montagem_reflete_razao_apos_efetivacao(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    import mod_contabil as mc
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        mc.constituir_provisoes_fechamento(db, ot, oid, seed["projeto_l1"],
                                           {"montagem": 1000.0}, ref_base="pf:direto")
        db.commit()
    finally:
        db.close()

    _, prov0 = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert prov0["provisoes"]["atual"]["itens"]["prov_mont"] == 1000.0

    # efetivação parcial (a mesma classe de evento que o F2-28 mediu no print do Teste_6:
    # o razão se move, "Atual" tinha ficado congelado no valor da venda)
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        mc.efetivar_provisao(db, ot, oid, seed["projeto_l1"], "2.1.04.02", 400.0, ref="ef:direto")
        db.commit()
    finally:
        db.close()

    _, prov1 = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    # F2-27: efetivar_provisao só move a perna de caixa (D provisão × C caixa) — o saldo CREDOR
    # da provisão (o que "Atual" mostra) cai pro que ainda falta pagar, 600.
    assert prov1["provisoes"]["atual"]["itens"]["prov_mont"] == 600.0
    assert prov1["provisoes"]["desatualizado"] is False   # efetivação não é "negociação mudou"


def test_atual_cust_esp_tambem_le_razao(http_client_factory, app_db, seed, projetos_dir):
    """cust_esp nunca foi AF-editável, mas tem provisão de verdade — também precisa ler o vivo."""
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    import mod_contabil as mc
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        mc.constituir_provisoes_fechamento(db, ot, oid, seed["projeto_l1"],
                                           {"cust_esp": 300.0}, ref_base="pf:direto")
        db.commit()
    finally:
        db.close()
    _, prov = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert prov["provisoes"]["atual"]["itens"]["cust_esp"] == 300.0


def test_atual_custo_financeiro_continua_do_motor(http_client_factory, app_db, seed, projetos_dir):
    """Controle negativo: custo_financeiro NÃO tem conta de provisão nesta família (rota do ramo
    financeiro) — continua vindo de `_negociacao_breakdown`, deliberadamente fora do alcance."""
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, prov = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert "custo_financeiro" in prov["provisoes"]["atual"]["itens"]
