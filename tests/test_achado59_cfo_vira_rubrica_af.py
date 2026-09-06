# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-59, Passo 2 — DECIDIDO pelo Marcelo (05/09): "a diferença
do CFO na aprovação do Projeto Executivo é um evento que visa facilitar os lançamentos para
conciliação, por isso o resíduo da previsão de fábrica deve ir para Outros Fornecedores. Na AF2
pode ocorrer fato semelhante."

Hoje o CFO não era rubrica: era a BASE do cálculo (`cust_var = cfo + soma das rubricas`), por
isso não aparecia como linha editável no painel da AF. Passa a ser, na AF1 e na AF2 — REUSANDO o
motor que já existe (`mod_contabil.conferencia_pedido`, a MESMA função que `POST /ciclo/12/
conferencia`, etapa 12, chama): reduzir o CFO na AF migra o resíduo pra Outros Fornecedores, dois
lançamentos auditáveis (ativo × provisão, nunca DRE). A etapa 12 continua intocada.

MEDIDO antes de codar: `_RUBRICAS_CUST_AD`/`_RUBRICA_CUST_FIN` já documentam o bug ① — uma
rubrica que entra na SOMA de `cust_var_marg_cont` E continua sendo a BASE dobra o custo. CFO
mora em `_RUBRICA_CUST_FAB` (dict novo, mesma família de Cust_Ad/Cust_Fin) — NUNCA em
`_RUBRICAS` (a que `cust_var_marg_cont` soma) — por isso vira linha sem dobrar nada.

F2-28 Passo 2 (05/09, DECIDIDO — substitui o mecanismo do F2-25 Passo 2 acima): Custo de Fábrica
NÃO é mais editável na AF — "não vejo necessidade de ter dois... podemos tornar a provisão de
custo fábrica não editável, de forma que o lançamento em Outros Fornecedores seja
automaticamente lançado em contrapartida ao custo fábrica" (Marcelo). O gerente digita só
`out_forn` (o INCREMENTO, não mais o alvo do CFO); a contrapartida contra a fábrica é automática.
`test_f2_28_af_e_contrato.py` cobre o mecanismo novo em detalhe — este teste é rederivado só pra
provar que os DOIS lançamentos ainda saem (reclassificação, mesmo motor de sempre)."""
from tests.test_provisao_registro import _setup_venda


def test_migracao_af1_produz_os_dois_lancamentos_da_conferencia(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")

    import mod_contabil as mc
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    # _registrar_provisao_venda (chamada por _setup_venda) só SNAPSHOTA — não constitui nada no
    # razão. Constitui aqui o estado real que um projeto pós-fechamento já teria.
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_fabrica", 4000.0,
                        projeto_id=seed["projeto_l1"], ref="test:cfo:constituir")
    db.commit()
    cfo_atual = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None, projeto_id=seed["projeto_l1"])
    db.close()
    assert cfo_atual == 4000.0   # CFO constituído, confirmado antes de editar

    # F2-28: digita-se o INCREMENTO de Outros Fornecedores (1000), não mais o alvo de Custo de
    # Fábrica — a contrapartida (CFO cai 1000, pra 3000) é automática. `custo_fabrica` no painel
    # é read-only agora (mesmo se algo vier no `itens`, é ignorado — ver teste dedicado).
    itens = {"frete_fab": 0.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
             "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0,
             "prov_imp": 0.0, "out_forn": 1000.0}
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "revisa", "itens": itens, "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body

    db = app_db.get_session()
    try:
        saldo_cfo = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None, projeto_id=seed["projeto_l1"])
        saldo_outros = mc._mov(db, ot, oid, "2.1.04.14", "credor", None, None, projeto_id=seed["projeto_l1"])
        assert saldo_cfo == 3000.0, "lançamento 1 — CFO debitado automaticamente (contrapartida)"
        assert saldo_outros == 1000.0, "lançamento 2 — o incremento de Outros Fornecedores"

        # Os DOIS lançamentos têm que ser estruturalmente iguais aos que a Conferência (etapa 12,
        # POST /ciclo/12/conferencia) produziria — mesma origem (reclassificação).
        origens = {l.origem for l in db.query(mc.Lancamento).filter(
            mc.Lancamento.projeto_id == seed["projeto_l1"],
            mc.Lancamento.ref.like("af:%:rev1:%:outros%")).all()}
        assert mc._ORIGEM_RECLASS in origens, origens
    finally:
        db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
        db.commit(); db.close()


def test_cust_var_nao_dobra_com_cfo_virando_linha(app_db, seed):
    """Aceite explícito do Passo 2: o total de custo (Cust_Var) NÃO muda por o CFO ter virado
    linha no painel. `custo_fabrica` incluído em `itens` (como o painel agora manda) não pode
    somar de novo sobre o `cfo` que já é a base."""
    import mod_provisoes as mp
    cfo = 4000.0
    val_liq = 9000.0
    itens_sem_cfo = {"frete_fab": 100.0, "out_forn": 50.0}
    itens_com_cfo = {"frete_fab": 100.0, "out_forn": 50.0, "custo_fabrica": cfo}   # painel novo manda isto também
    cust_var_sem, marg_sem = mp.cust_var_marg_cont(cfo, val_liq, itens_sem_cfo)
    cust_var_com, marg_com = mp.cust_var_marg_cont(cfo, val_liq, itens_com_cfo)
    assert cust_var_sem == cust_var_com == round(cfo + 100.0 + 50.0, 2), (
        "custo_fabrica em itens não pode ser somado de novo — CFO já é a base")
    assert marg_sem == marg_com


def test_custo_fabrica_aparece_no_breakdown_do_painel():
    """itens_provisao (o que popula o painel) agora inclui custo_fabrica como linha."""
    import mod_provisoes as mp
    siglas = {"CFO": 4000.0, "Cust_Fin": 200.0}
    itens = mp.itens_provisao(siglas)
    assert itens["custo_fabrica"] == 4000.0
