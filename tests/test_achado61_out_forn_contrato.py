# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-61 — irmão do ACHADO-59, outra porta.

Medido (06/09, percurso Teste_7, beta2): `orc.out_forn` já tinha campo na negociação
(Parâmetros) e já entrava no Cust_Var do motor (soma, não desconta do CFO — mod_provisoes.py) —
mas o dict `valores` de `_fin_provisoes_venda_seguro` (main.py) não incluía a chave "outros_forn",
então a rubrica nunca nascia no razão no fechamento do contrato. R$2.000,00 digitados nos
Parâmetros não geravam lançamento nenhum em 2.1.04.14.

Regra econômica (decidida): no CONTRATO, Outros Fornecedores é ADITIVO — constitui par próprio
(1.1.06.14 × 2.1.04.14) e NÃO reduz o Custo de Fábrica. Na AF, é SUBSTITUTIVO (migra do CFO pelo
delta — ACHADO-59, já implementado, não tocado aqui)."""
import mod_contabil as mc


def _saldo(db, ot, oid, codigo, nome):
    return round(mc._mov(db, ot, oid, codigo, "credor", None, None, projeto_id=nome), 2)


def _limpar(app_db, ot, owner_id, nome):
    """seed/app_db são module-scoped — sem isto, o teste de idempotência (mesmo projeto_l1)
    herdaria o lançamento do primeiro teste deste arquivo (regra dos irmãos, F2-29 Fatia D)."""
    db = app_db.get_session()
    db.query(mc.Lancamento).filter_by(owner_tipo=ot, owner_id=owner_id, projeto_id=nome).delete()
    db.commit(); db.close()


def test_out_forn_no_fechamento_constitui_par_proprio_sem_mexer_no_cfo(app_db, seed):
    import main

    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.loja_id = seed["loja1_id"]
    orc.valor_total = 5000.0
    orc.cfo = 10000.0
    orc.out_forn = 2000.0
    db.commit()

    ot, owner_id = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    assert _saldo(db, ot, owner_id, "2.1.04.14", nome) == 0.0
    assert _saldo(db, ot, owner_id, "1.1.06.14", nome) == 0.0

    main._fin_provisoes_venda_seguro(orc, nome, "achado61:" + nome)
    db.close()

    db = app_db.get_session()
    saldo_prov_outros_forn = _saldo(db, ot, owner_id, "2.1.04.14", nome)
    saldo_ativo_outros_forn = mc._mov(db, ot, owner_id, "1.1.06.14", "devedor", None, None, projeto_id=nome)
    saldo_cfo = _saldo(db, ot, owner_id, "2.1.04.06", nome)
    db.close()

    assert saldo_prov_outros_forn == 2000.0, (
        "ACHADO-61: out_forn digitado nos Parâmetros tem que provisionar de verdade no fechamento")
    assert round(saldo_ativo_outros_forn, 2) == 2000.0
    # o CFO congelado tem que ficar EXATAMENTE no que foi constituído — o par de Outros
    # Fornecedores é ADITIVO no contrato, nunca migra/reduz o Custo de Fábrica.
    assert saldo_cfo == 10000.0, "Outros Fornecedores no contrato não pode mexer no CFO"
    _limpar(app_db, ot, owner_id, nome)


def test_out_forn_zero_nao_lanca(app_db, seed):
    import main

    oid = seed["orcamento_l2_id"]
    nome = seed["projeto_l2"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.loja_id = seed["loja2_id"]
    orc.valor_total = 3000.0
    orc.cfo = 1000.0
    orc.out_forn = 0.0
    db.commit()

    ot, owner_id = mc.resolver_owner(db, {"loja_id": seed["loja2_id"], "rede_id": None})
    main._fin_provisoes_venda_seguro(orc, nome, "achado61-zero:" + nome)
    db.close()

    db = app_db.get_session()
    saldo = _saldo(db, ot, owner_id, "2.1.04.14", nome)
    db.close()
    assert saldo == 0.0, "out_forn == 0 não pode gerar lançamento nenhum em 2.1.04.14"


def test_out_forn_idempotente_por_ref(app_db, seed):
    import main

    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.loja_id = seed["loja1_id"]
    orc.valor_total = 5000.0
    orc.cfo = 10000.0
    orc.out_forn = 2000.0
    db.commit()

    ot, owner_id = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    ref_base = "achado61-idemp:" + nome
    main._fin_provisoes_venda_seguro(orc, nome, ref_base)
    db.close()
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    main._fin_provisoes_venda_seguro(orc, nome, ref_base)
    db.close()

    db = app_db.get_session()
    saldo = _saldo(db, ot, owner_id, "2.1.04.14", nome)
    db.close()
    assert saldo == 2000.0, "rodar o wiring duas vezes com o mesmo ref_base não pode duplicar"
