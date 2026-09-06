# -*- coding: utf-8 -*-
"""F2-30 Fatia 1 — rescaldo do F2-28. Observado pelo Marcelo no beta5, projeto Teste_6, print:
duas revisões sucessivas da AF1 (migração de 3.000, depois alterada pra 4.000) deixavam Rev1
gravado com Custo de Fábrica = 98.446,51 (a contrapartida da migração ANTERIOR, de 3.000) nas
DUAS submissões, enquanto "Atual" (que lê o razão) corretamente mostrava 97.446,51 depois da
2ª. O snapshot da revisão parava de bater consigo mesmo — Outros Fornecedores dizia "migrei
4.000" e Custo de Fábrica dizia "a fábrica ficou em 98.446,51" (que só fecha pra 3.000).

Causa: Custo de Fábrica é DERIVADO desde o F2-28 Passo 2 (read-only) — mas o valor que a tela
envia em `itens.custo_fabrica` é só o prefill de quando o box abriu, não o resultado da migração
DESTA submissão. Corrigido: o backend calcula a migração ANTES de montar o registro e sobrescreve
`itens["custo_fabrica"]` pelo valor que o razão vai ter depois desta submissão."""
from tests.test_provisao_registro import _setup_venda


def _itens_base(**over):
    base = {"frete_fab": 0.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
            "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0, "prov_imp": 0.0}
    base.update(over)
    return base


def test_duas_revisoes_sucessivas_fecham_consigo_mesmas(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    import mod_contabil as mc
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        mc.constituir_provisoes_fechamento(db, ot, oid, seed["projeto_l1"],
                                           {"custo_fabrica": 101446.51}, ref_base="pf:direto")
        db.commit()
    finally:
        db.close()

    # 1ª revisão: migra 3.000
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "revisa", "itens": _itens_base(out_forn=3000.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body
    _, prov1 = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    rev1_1 = prov1["provisoes"]["rev1"]["itens"]
    # coerência INTERNA da própria revisão: 101446.51 - out_forn migrado = custo_fabrica gravado
    assert rev1_1["out_forn"] == 3000.0
    assert rev1_1["custo_fabrica"] == 98446.51
    assert prov1["provisoes"]["atual"]["itens"]["custo_fabrica"] == 98446.51

    # 2ª revisão (mesma rev1, reeditada): migra mais 1.000 (total 4.000)
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "revisa", "itens": _itens_base(out_forn=4000.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body
    _, prov2 = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    rev1_2 = prov2["provisoes"]["rev1"]["itens"]
    atual2 = prov2["provisoes"]["atual"]["itens"]
    assert rev1_2["out_forn"] == 4000.0
    # O ACHADO: antes do conserto, isto vinha 98446.51 (a contrapartida da migração ANTERIOR).
    assert rev1_2["custo_fabrica"] == 97446.51, (
        "Rev1 tem que fechar consigo mesma: migrou 4.000 de 101.446,51, "
        "custo_fabrica gravado tem que ser 97.446,51")
    assert atual2["custo_fabrica"] == 97446.51
    # razão de verdade — confirma que "Atual" e o registro da revisão contam a MESMA história
    db = app_db.get_session()
    try:
        saldo_razao = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None,
                              projeto_id=seed["projeto_l1"])
        saldo_out_forn = mc._mov(db, ot, oid, "2.1.04.14", "credor", None, None,
                                 projeto_id=seed["projeto_l1"])
    finally:
        db.close()
    assert round(saldo_razao, 2) == 97446.51
    assert round(saldo_out_forn, 2) == 4000.0
    _limpar(app_db, seed)


def _limpar(app_db, seed):
    """seed/app_db são module-scoped (mesmo orçamento em todo teste deste arquivo) — sem isto,
    o próximo teste herdaria os lançamentos e o ProvisaoRegistro daqui (regra dos irmãos,
    F2-29 Fatia D)."""
    import mod_contabil as mc
    db = app_db.get_session()
    db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    db.query(mc.Lancamento).filter_by(owner_tipo=ot, owner_id=oid,
                                      projeto_id=seed["projeto_l1"]).delete()
    db.commit(); db.close()


def test_revisao_sem_migracao_controle_negativo(http_client_factory, app_db, seed, projetos_dir):
    """Controle: sem editar out_forn (migração=0), custo_fabrica gravado é só o saldo atual —
    nunca muda por conta de uma revisão que não mexeu na fábrica."""
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    import mod_contabil as mc
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        mc.constituir_provisoes_fechamento(db, ot, oid, seed["projeto_l1"],
                                           {"custo_fabrica": 50000.0}, ref_base="pf:direto")
        db.commit()
    finally:
        db.close()
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "revisa", "itens": _itens_base(out_forn=0.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body
    _, prov = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert prov["provisoes"]["rev1"]["itens"]["custo_fabrica"] == 50000.0
    assert prov["provisoes"]["atual"]["itens"]["custo_fabrica"] == 50000.0
    _limpar(app_db, seed)
