"""docs/db/TAREFA_ACHADO12.md, passo 7 do ROTEIRO — o aceite que fecha o ciclo inteiro.

CONSERTO: `_valores_segmentados_do_projeto` passou a usar `valor_contratado_do_projeto`
(contrato + aditivos ASSINADOS) em vez de ler só `Contrato.orcamento_id → Orcamento.valor_total`.
Este aceite prova a invariante que `docs/db/TAREFA_BATERIA_CICLO.md` já declarava e que o
aditivo quebrava: **projeto com aditivo termina com 2.1.06 zerado** — a receita constituída pelo
aditivo, que antes nunca virava receita faturada, agora sai de 2.1.06 pela NF-e como o resto."""
import mod_contabil as mc

from tests.test_aditivo_costuras import (
    _setup, _upsert_compl, _criar_modelo_aditivo, _assinar_aditivo_completo, _login,
)


def test_projeto_com_aditivo_termina_com_2106_zerado(app_db, seed, http_client_factory):
    import main
    nome, pid, oid = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    loja_id = seed["loja1_id"]

    db = app_db.get_session()
    orc_ct = db.get(app_db.Orcamento, oid)
    main._recalcular_orcamento(orc_ct, db)
    db.commit()
    val_cont_original = round(float(orc_ct.valor_total or 0), 2)
    main._fin_provisoes_venda_seguro(orc_ct, nome, "prov:venda:" + nome)
    db.close()
    assert val_cont_original > 0

    ator = {"loja_id": loja_id, "rede_id": None}
    db = app_db.get_session()
    ot, owner_id = mc.resolver_owner(db, ator)
    db.close()

    # aditivo: diferença de R$ 4.444,44 (venda 84.000, VAVA contratado 88.888,89)
    _criar_modelo_aditivo(app_db, seed, loja_id)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    diferenca_aditivo = round(body["orcamento"]["valor_total"], 2)
    assert abs(diferenca_aditivo - 4444.44) < 0.05, diferenca_aditivo

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    _assinar_aditivo_completo(c, nome)

    valor_contratado = round(val_cont_original + diferenca_aditivo, 2)
    db = app_db.get_session()
    v_contratado_medido = main.valor_contratado_do_projeto(db, nome)
    db.close()
    assert abs(v_contratado_medido - valor_contratado) < 0.05, v_contratado_medido

    saldo_2106_antes_nfe = mc.saldo_adiantamento_projeto(app_db.get_session(), ot, owner_id, nome)
    assert abs(saldo_2106_antes_nfe - valor_contratado) < 0.05, (
        "2.1.06 deveria ter contrato + aditivo constituídos antes da NF-e — %r" % saldo_2106_antes_nfe)

    # a NF-e agora fatura valor_contratado_do_projeto (contrato + aditivo), não só o contrato.
    main._fin_faturamento_segmentado_seguro(loja_id, nome, "mercadoria", "NFE-aceite-achado12")

    faturado = mc.total_lancado(app_db.get_session(), ot, owner_id, "4.1.01", "credito",
                                projeto_id=nome)
    assert abs(faturado - valor_contratado) < 0.05, (
        "4.1.01 deveria fechar em %.2f (contrato + aditivo) — %r" % (valor_contratado, faturado))

    saldo_2106_depois = mc.saldo_adiantamento_projeto(app_db.get_session(), ot, owner_id, nome)
    assert abs(saldo_2106_depois) < 0.005, (
        "ACHADO-12: projeto com aditivo tem que terminar com 2.1.06 ZERADO — sobrou %r"
        % saldo_2106_depois)


def test_selecao_do_orcamento_no_post_aditivo_e_explicita(app_db, seed, http_client_factory):
    """docs/db/TAREFA_ACHADO12.md, ponto 2: `POST /aditivo` não pode mais pegar "o complemento_pe=1
    de maior id" — depois do 6-b existem orçamentos HISTÓRICOS (já com aditivo assinado) no
    mesmo projeto, e um complemento de FASE (parcela_id != None) pode ter id maior que o
    complemento legado (parcela_id=None) pendente. A seleção sem `parcela_id` no corpo tem que
    ficar restrita a `parcela_id=None` E preferir o PENDENTE (sem aditivo assinado ainda) —
    nunca o histórico nem o de outra fase, mesmo que tenham id maior.

    Usa o projeto da LOJA 2 (`qual="l2"`) — `seed`/`app_db` são module-scoped e o outro teste
    deste arquivo já assina um aditivo de verdade no projeto da loja 1."""
    import main
    nome, pid, oid = _setup(app_db, seed, qual="l2")
    c = _login(http_client_factory, "dir_l2")
    loja_id = seed["loja2_id"]
    _criar_modelo_aditivo(app_db, seed, loja_id)

    # revisão 1 (legado, parcela_id=None): aj1, assinado — vira histórico.
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj1_id = body["orcamento"]["id"]
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    _assinar_aditivo_completo(c, nome)

    # revisão 2 (legado, parcela_id=None): aj2, PENDENTE — o 6-b cria um Orcamento novo.
    _upsert_compl(app_db, nome, pid, venda=90000.0, cfo=34000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj2_id = body["orcamento"]["id"]
    assert aj2_id != aj1_id

    # complemento de FASE, parcela_id != None, com id MAIOR que aj2 — mecanismo distinto, nunca
    # pode ser confundido com o legado. Construído direto no banco (não preciso do fluxo de AF2
    # completo pra testar SELEÇÃO — só que o registro exista com id maior).
    db = app_db.get_session()
    parcela = app_db.ParcelaProjeto(projeto_nome=nome, ordem=1)
    db.add(parcela); db.flush()
    orc_fase = app_db.Orcamento(projeto_id=nome, nome="Complemento PE — Fase",
                                ordem=99, desconto_pct=0.0, complemento_pe=1,
                                parcela_id=parcela.id, loja_id=loja_id, valor_total=999.99)
    db.add(orc_fase); db.commit()
    orc_fase_id = orc_fase.id
    assert orc_fase_id > aj2_id, "pré-condição: o de fase tem que ter id MAIOR que aj2"
    db.close()

    # POST /aditivo SEM parcela_id no corpo → tem que pegar aj2 (legado, pendente), nunca
    # orc_fase (id maior, fase errada) nem aj1 (legado, já histórico/assinado).
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"novo": True})
    assert st == 200 and body["ok"], body
    aditivo2_id = body["aditivo"]["id"]
    db = app_db.get_session()
    orcamento_selecionado = db.get(app_db.Aditivo, aditivo2_id).orcamento_complemento_id
    db.close()
    assert orcamento_selecionado == aj2_id, (
        "deveria selecionar o complemento legado PENDENTE (%r) — selecionou %r"
        % (aj2_id, orcamento_selecionado))
