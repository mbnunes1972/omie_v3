import pytest
import mod_contabil as mc


def _q(db):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo=cod).first().id


def test_evento_faturamento_gera_lancamento_correto(app_db):
    db = app_db.get_session(); c = _q(db)
    lan = mc.registrar_evento(db, "loja", 1, "faturamento", 1000.0, projeto_id="Proj_A")
    assert lan["conta_debito_id"] == c("1.1.02")    # Contas a Receber
    assert lan["conta_credito_id"] == c("4.1.01")   # Receita com Vendas
    assert lan["origem"] == "faturamento" and lan["projeto_id"] == "Proj_A" and lan["valor"] == 1000.0
    db.close()


def test_evento_recebimento(app_db):
    db = app_db.get_session(); c = _q(db)
    lan = mc.registrar_evento(db, "loja", 1, "recebimento", 400.0, projeto_id="Proj_B")
    assert lan["conta_debito_id"] == c("1.1.01") and lan["conta_credito_id"] == c("1.1.02")
    db.close()


def test_fechamento_venda_3_provisoes_independentes(app_db):
    db = app_db.get_session(); c = _q(db)
    # FASE D2: a constituição debita o ATIVO DIFERIDO (1.1.06.0X), não mais 5.6.0X (despesa só na NF-e)
    m = mc.registrar_evento(db, "loja", 1, "fechamento_venda_montagem", 90.0, projeto_id="Proj_C")
    assert m["conta_debito_id"] == c("1.1.06.02") and m["conta_credito_id"] == c("2.1.04.02")
    a = mc.registrar_evento(db, "loja", 1, "fechamento_venda_assistencia", 40.0, projeto_id="Proj_C")
    assert a["conta_debito_id"] == c("1.1.06.05") and a["conta_credito_id"] == c("2.1.04.05")
    g = mc.registrar_evento(db, "loja", 1, "fechamento_venda_garantia", 30.0, projeto_id="Proj_C")
    assert g["conta_debito_id"] == c("1.1.06.03") and g["conta_credito_id"] == c("2.1.04.03")
    db.close()


def test_evento_execucoes(app_db):
    """ACHADO-05 (docs/db/PLANO_AJUSTES.md, 2026-08-29): "pagamento_comissao" foi removido de
    EVENTOS — nunca foi chamado em produção, superado pelo caminho da Folha (2.1.04.12). Este
    teste testava esse evento; segue cobrindo as execuções, que continuam vivas."""
    db = app_db.get_session(); c = _q(db)
    l2 = mc.registrar_evento(db, "loja", 1, "execucao_montagem", 20.0, projeto_id="Proj_D")
    assert l2["conta_debito_id"] == c("2.1.04.02") and l2["conta_credito_id"] == c("1.1.01")
    l3 = mc.registrar_evento(db, "loja", 1, "execucao_reparo_garantia", 10.0, projeto_id="Proj_D")
    assert l3["conta_debito_id"] == c("2.1.04.03") and l3["conta_credito_id"] == c("1.1.01")
    db.close()


def test_eventos_mortos_removidos_por_decisao():
    """ACHADO-04/05 (docs/db/PLANO_AJUSTES.md, 2026-08-29): "custo_financeiro" (5.5.03×2.1.05,
    nunca confirmado pelo contador, modelava o Parcelamento Loja como financiamento de terceiro)
    e "pagamento_comissao" (2.1.04.01×1.1.01, nunca chamado em produção) foram removidos de
    EVENTOS — não é esquecimento, é decisão registrada."""
    assert "custo_financeiro" not in mc.EVENTOS
    assert "pagamento_comissao" not in mc.EVENTOS


def test_evento_desconhecido_rejeitado(app_db):
    db = app_db.get_session()
    with pytest.raises(ValueError):
        mc.registrar_evento(db, "loja", 1, "evento_inexistente", 10.0)
    db.close()
