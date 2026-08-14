"""Conciliação de PE/AF2 — Crédito a Clientes (Estorno), ledger puro sobre `app_db`.
Spec: docs/superpowers/specs/financeiro/2026-08-14-conciliacao-pe-af2-complemento-credito-design.md
"""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_eventos_credito_cliente_pares_de_contas():
    E = mc.EVENTOS
    assert E["estorno_credito_cliente"][:2] == ("4.3.02", "2.1.11")
    assert E["baixa_credito_cliente_receber"][:2] == ("2.1.11", "1.1.02")
    assert E["baixa_credito_cliente_caixa"][:2] == ("2.1.11", "1.1.01")


def test_registrar_credito_cliente_debita_devolucao_credita_credito_cliente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 971; mc.seed_plano(db, ot, oid)
    mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjX", valor=1500.0, ref="est:ProjX:1")
    # 4.3.02 é grupo 4 (Receitas) → natureza CREDORA no plano; débito nela reduz o saldo credor
    # (efeito de dedução de receita), por isso aparece negativo em saldo_conta (C−D).
    assert _s(db, ot, oid, "4.3.02") == -1500.0   # Devolução de Vendas — dedução de receita
    assert _s(db, ot, oid, "2.1.11") == 1500.0    # Créditos a Clientes (passivo, credora)
    db.close()


def test_registrar_credito_cliente_idempotente_por_ref(app_db):
    db = app_db.get_session(); ot, oid = "loja", 972; mc.seed_plano(db, ot, oid)
    l1 = mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjY", valor=800.0, ref="est:ProjY:1")
    l2 = mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjY", valor=800.0, ref="est:ProjY:1")
    assert l1["id"] == l2["id"]
    assert _s(db, ot, oid, "2.1.11") == 800.0   # não duplicou
    db.close()


def test_registrar_credito_cliente_valor_invalido_levanta_erro(app_db):
    db = app_db.get_session(); ot, oid = "loja", 973; mc.seed_plano(db, ot, oid)
    import pytest
    with pytest.raises(ValueError):
        mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjZ", valor=0.0, ref="est:ProjZ:1")
    with pytest.raises(ValueError):
        mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjZ", valor=-10.0, ref="est:ProjZ:2")
    db.close()


def test_saldo_credito_cliente_zero_sem_lancamento(app_db):
    db = app_db.get_session(); ot, oid = "loja", 974; mc.seed_plano(db, ot, oid)
    assert mc.saldo_credito_cliente(db, ot, oid, "ProjNenhum") == 0.0
    db.close()


def test_baixar_credito_cliente_receber_abate_o_credito(app_db):
    db = app_db.get_session(); ot, oid = "loja", 975; mc.seed_plano(db, ot, oid)
    mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjA", valor=1000.0, ref="est:ProjA:1")
    assert mc.saldo_credito_cliente(db, ot, oid, "ProjA") == 1000.0

    mc.baixar_credito_cliente(db, ot, oid, "ProjA", valor=1000.0, destino="receber", ref="baixa:ProjA:1")
    assert mc.saldo_credito_cliente(db, ot, oid, "ProjA") == 0.0
    assert _s(db, ot, oid, "1.1.02") == -1000.0   # Contas a Receber reduzido (crédito líquido nela)
    db.close()


def test_baixar_credito_cliente_caixa_devolve_em_dinheiro(app_db):
    db = app_db.get_session(); ot, oid = "loja", 976; mc.seed_plano(db, ot, oid)
    mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjB", valor=500.0, ref="est:ProjB:1")
    mc.baixar_credito_cliente(db, ot, oid, "ProjB", valor=500.0, destino="caixa", ref="baixa:ProjB:1")
    assert mc.saldo_credito_cliente(db, ot, oid, "ProjB") == 0.0
    assert _s(db, ot, oid, "1.1.01") == -500.0    # saiu dinheiro do caixa
    db.close()


def test_baixar_credito_cliente_capado_ao_saldo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 977; mc.seed_plano(db, ot, oid)
    mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjC", valor=300.0, ref="est:ProjC:1")
    # tenta baixar mais do que existe — capa no saldo disponível
    mc.baixar_credito_cliente(db, ot, oid, "ProjC", valor=999999.0, destino="caixa", ref="baixa:ProjC:1")
    assert mc.saldo_credito_cliente(db, ot, oid, "ProjC") == 0.0
    assert _s(db, ot, oid, "1.1.01") == -300.0
    db.close()


def test_baixar_credito_cliente_sem_saldo_retorna_none(app_db):
    db = app_db.get_session(); ot, oid = "loja", 978; mc.seed_plano(db, ot, oid)
    assert mc.baixar_credito_cliente(db, ot, oid, "ProjSemNada", valor=100.0,
                                     destino="caixa", ref="baixa:ProjSemNada:1") is None
    db.close()


def test_baixar_credito_cliente_idempotente_por_ref(app_db):
    db = app_db.get_session(); ot, oid = "loja", 979; mc.seed_plano(db, ot, oid)
    mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjD", valor=200.0, ref="est:ProjD:1")
    b1 = mc.baixar_credito_cliente(db, ot, oid, "ProjD", valor=200.0, destino="receber", ref="baixa:ProjD:1")
    b2 = mc.baixar_credito_cliente(db, ot, oid, "ProjD", valor=200.0, destino="receber", ref="baixa:ProjD:1")
    assert b1["id"] == b2["id"]
    db.close()


def test_baixar_credito_cliente_destino_invalido_levanta_erro(app_db):
    db = app_db.get_session(); ot, oid = "loja", 980; mc.seed_plano(db, ot, oid)
    import pytest
    with pytest.raises(ValueError):
        mc.baixar_credito_cliente(db, ot, oid, "ProjE", valor=100.0, destino="banco", ref="baixa:ProjE:1")
    db.close()


def test_conciliacao_final_nao_varre_credito_a_clientes(app_db):
    # 2.1.11 fica FORA do prefixo "2.1.04." (GRUPO_PROVISOES) — conciliar_final não a enxerga,
    # o projeto pode ser dado como concluído com o crédito ainda em aberto.
    db = app_db.get_session(); ot, oid = "loja", 981; mc.seed_plano(db, ot, oid)
    mc.registrar_credito_cliente(db, ot, oid, projeto_id="ProjF", valor=777.0, ref="est:ProjF:1")
    assert mc.saldo_credito_cliente(db, ot, oid, "ProjF") == 777.0

    resolvido = mc.conciliar_final(db, ot, oid, "ProjF", ref_base="cf:ProjF")

    assert "2.1.11" not in resolvido                      # não foi tocada pela varredura
    assert mc.saldo_credito_cliente(db, ot, oid, "ProjF") == 777.0   # saldo sobrevive intacto
    db.close()
