"""docs/db/TAREFA_ACHADO21.md, 6-c — recebíveis próprios do aditivo + custo financeiro medido.

CONSERTO (não mais medição): a assinatura que COMPLETA o aditivo agora exige `forma_pagamento` no
corpo (recusa com mensagem clara se ausente — nenhum default inventado) e chama
`_materializar_recebiveis_venda_seguro` para o orçamento do COMPLEMENTO, nunca o do contrato
(guarda de idempotência por `orcamento_id`)."""
import json

from tests.test_aditivo_wizard_e2e import _setup, _upsert_compl, _login


def _limpar_estado_aditivo(app_db, seed):
    """`_setup`/`seed`/`app_db` são module-scoped e reusam o MESMO projeto entre os testes deste
    arquivo — sem limpar, um Aditivo/assinatura de um teste vaza pro próximo (achado ao rodar o
    arquivo inteiro: "Esta parte já assinou" num aditivo que o teste seguinte pensava ser novo)."""
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    for adt in db.query(app_db.Aditivo).filter_by(projeto_nome=nome).all():
        for a in list(adt.assinaturas):
            db.delete(a)
    db.query(app_db.Aditivo).filter_by(projeto_nome=nome).delete()
    db.query(app_db.Recebivel).filter_by(projeto_nome=nome).delete()
    for orc in db.query(app_db.Orcamento).filter_by(projeto_id=nome, complemento_pe=1).all():
        db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=orc.id).delete()
        db.delete(orc)
    db.commit(); db.close()


def test_assinatura_sem_forma_pagamento_recusa_com_mensagem_clara(app_db, seed, http_client_factory):
    _limpar_estado_aditivo(app_db, seed)
    nome, pid, pid2 = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body

    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body

    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "loja", "nome": "Rep Loja", "cpf": "111.444.777-35"})
    assert st == 200 and body["status"] == "assinado_loja", body

    # a assinatura que COMPLETA (cliente, 2ª parte) sem forma_pagamento tem que ser recusada —
    # nenhum default inventado (o que não pede é o que fica sem cobrança, ACHADO-12/21).
    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "cliente", "nome": "Cliente L1", "cpf": "222.333.444-05"})
    assert st == 400 and not body["ok"], body
    assert "forma de pagamento" in body["erro"].lower(), body

    db = app_db.get_session()
    aditivo = db.query(app_db.Aditivo).filter_by(projeto_nome=nome).order_by(
        app_db.Aditivo.id.desc()).first()
    status_apos_recusa = aditivo.status
    db.close()
    assert status_apos_recusa == "assinado_loja", (
        "a recusa não pode ter avançado o status do aditivo — %r" % status_apos_recusa)


def test_recebivel_do_aditivo_existe_e_nao_mexe_nos_do_contrato(app_db, seed, http_client_factory):
    import main, mod_contabil as mc
    _limpar_estado_aditivo(app_db, seed)
    nome, pid, pid2 = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")

    # materializa os recebíveis do CONTRATO original — baseline que não pode mudar. "avista" só
    # gera linhas a partir de "parcelas" (mod_recebiveis.materializar) — 1 parcela à vista pelo
    # valor cheio, igual ao plano-padrão do resto da suíte.
    db = app_db.get_session()
    orc_ct_id = seed["orcamento_l1_id"]
    orc_ct = db.get(app_db.Orcamento, orc_ct_id)
    main._recalcular_orcamento(orc_ct, db)
    db.commit()
    val_cont_ct = round(float(orc_ct.valor_total or 0), 2)
    assert val_cont_ct > 0
    main._materializar_recebiveis_venda_seguro(
        orc_ct, nome, seed["loja1_id"], datetime_utcnow_like(), "receb:contrato-teste:" + nome,
        pagamento_json_str=json.dumps({"tipo": "avista", "parcelas": [{"valor": val_cont_ct}]}))
    db.close()

    db = app_db.get_session()
    recebiveis_contrato_antes = [
        (r.orcamento_id, r.valor_previsto) for r in
        db.query(app_db.Recebivel).filter_by(orcamento_id=orc_ct_id).order_by(app_db.Recebivel.id).all()]
    db.close()
    assert recebiveis_contrato_antes, "pré-condição: contrato tem que ter recebível(is) próprios"

    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj_id = body["orcamento"]["id"]

    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body

    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        corpo = {"parte": parte, "nome": quem, "cpf": "111.444.777-35"}
        if parte == "cliente":
            corpo["forma_pagamento"] = json.dumps(
                {"tipo": "avista", "parcelas": [{"valor": 4444.44}]})
        st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar", corpo)
        assert st == 200, body
    assert body["status"] == "assinado"

    db = app_db.get_session()
    recebiveis_aditivo = (db.query(app_db.Recebivel).filter_by(orcamento_id=aj_id).all())
    recebiveis_contrato_depois = [
        (r.orcamento_id, r.valor_previsto) for r in
        db.query(app_db.Recebivel).filter_by(orcamento_id=orc_ct_id).order_by(app_db.Recebivel.id).all()]
    db.close()

    assert recebiveis_aditivo, "assinatura completa do aditivo deveria materializar recebível(is) próprio(s)"
    assert abs(sum(r.valor_previsto for r in recebiveis_aditivo) - 4444.44) < 0.05, (
        [r.valor_previsto for r in recebiveis_aditivo])
    assert recebiveis_contrato_depois == recebiveis_contrato_antes, (
        "os recebíveis do CONTRATO não podem mudar por causa do aditivo — antes=%r depois=%r"
        % (recebiveis_contrato_antes, recebiveis_contrato_depois))


def test_custo_financeiro_do_aditivo_antes_e_depois_da_forma_de_pagamento(app_db, seed, http_client_factory):
    """MEDIÇÃO explícita pedida pelo 6-c: com forma_pagamento financiada (total_cliente > VAVA da
    diferença), o aditivo passa a ter Cust_Fin PRÓPRIO — reporta o antes (zero, sem forma de
    pagamento) e o depois (financiado)."""
    import main, mod_contabil as mc
    _limpar_estado_aditivo(app_db, seed)
    nome, pid, pid2 = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj_id = body["orcamento"]["id"]
    diferenca = round(body["orcamento"]["valor_total"], 2)   # 4.444,44 — VAVA da diferença

    db = app_db.get_session()
    antes_cust_fin = db.get(app_db.Orcamento, aj_id).cust_fin or 0.0
    db.close()

    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body

    # forma de pagamento FINANCIADA: o cliente paga mais do que a diferença à vista (juros).
    total_financiado = round(diferenca * 1.10, 2)
    ator = {"loja_id": seed["loja1_id"], "rede_id": None}
    db = app_db.get_session()
    ot, owner_id = mc.resolver_owner(db, ator)
    db.close()

    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        corpo = {"parte": parte, "nome": quem, "cpf": "111.444.777-35"}
        if parte == "cliente":
            corpo["forma_pagamento"] = json.dumps(
                {"tipo": "cartao", "total_cliente": total_financiado})
        st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar", corpo)
        assert st == 200, body
    assert body["status"] == "assinado"

    db = app_db.get_session()
    depois_cust_fin = db.get(app_db.Orcamento, aj_id).cust_fin or 0.0
    depois_valor_total = db.get(app_db.Orcamento, aj_id).valor_total
    db.close()

    print("ACHADO-21/6-c — Cust_Fin do aditivo: antes=%.2f depois=%.2f (diferença negociada "
          "continua %.2f; valor_total pós-financiamento=%.2f)"
          % (antes_cust_fin, depois_cust_fin, diferenca, depois_valor_total))

    assert antes_cust_fin == 0.0, (
        "antes de coletar forma de pagamento, o aditivo não tem custo financeiro nenhum — %r"
        % antes_cust_fin)
    assert abs(depois_cust_fin - (total_financiado - diferenca)) < 0.05, (
        "depois de uma forma de pagamento financiada, Cust_Fin passa a existir (a regra do "
        "deságio) — esperado %.2f, obtido %.2f" % (total_financiado - diferenca, depois_cust_fin))

    # a provisão de custo financeiro/juros do ADITIVO passou a existir no razão — mesma decisão
    # de ramo do contrato principal (ACHADO-03/_ramo_financeiro_efetivo lê orc.forma_pagamento).
    db = app_db.get_session()
    ramo = main._ramo_financeiro_efetivo(db.get(app_db.Orcamento, aj_id))
    db.close()
    evento_esperado = mc._RAMO_CFIN_EVENTO.get(ramo)
    assert evento_esperado is not None, ramo
    cod_debito, cod_credito, _hist = mc.EVENTOS[evento_esperado]
    db = app_db.get_session()
    saldo_cfin = mc._mov(db, ot, owner_id, cod_credito, "credor", None, None, projeto_id=nome)
    db.close()
    assert abs(saldo_cfin - (total_financiado - diferenca)) < 0.05, (
        "a provisão/receita financeira do aditivo (%s) deveria refletir o Cust_Fin — %r"
        % (cod_credito, saldo_cfin))


def datetime_utcnow_like():
    import datetime as _dt
    return _dt.datetime.utcnow()
