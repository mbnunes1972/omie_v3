# -*- coding: utf-8 -*-
"""Painel guiado de Lançamentos (2026-08-09): sugestões de despesa do mês anterior — o objetivo é
facilitar o lançamento pra quem não entende contabilidade. `sugestoes_despesas_mes_anterior`
sugere toda conta de despesa (grupo 5) com movimento líquido POSITIVO no mês passado, com a
contrapartida mais recente e um aviso se já foi lançada de novo no mês corrente."""
import datetime as dt
import mod_contabil as mc


def _contas(db, ot, oid):
    return {c.codigo: c for c in db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}


# ── _intervalo_mes_anterior / _intervalo_mes_atual ──────────────────────────────────────────────
def test_intervalo_mes_anterior_mes_normal():
    ini, fim = mc._intervalo_mes_anterior(dt.datetime(2026, 8, 5, 14, 30))
    assert ini == dt.datetime(2026, 7, 1, 0, 0, 0)
    assert fim.date() == dt.date(2026, 7, 31) and fim.hour == 23 and fim.minute == 59


def test_intervalo_mes_anterior_janeiro_rola_pro_ano_anterior():
    ini, fim = mc._intervalo_mes_anterior(dt.datetime(2026, 1, 15))
    assert ini == dt.datetime(2025, 12, 1, 0, 0, 0)
    assert fim.date() == dt.date(2025, 12, 31)


def test_intervalo_mes_anterior_fevereiro_bissexto_e_nao_bissexto():
    _, fim_bis = mc._intervalo_mes_anterior(dt.datetime(2024, 3, 1))
    assert fim_bis.date() == dt.date(2024, 2, 29)
    _, fim_nao = mc._intervalo_mes_anterior(dt.datetime(2025, 3, 1))
    assert fim_nao.date() == dt.date(2025, 2, 28)


def test_intervalo_mes_atual_fim_e_o_proprio_ref_nao_o_fim_do_mes():
    ref = dt.datetime(2026, 8, 5, 14, 0)
    ini, fim = mc._intervalo_mes_atual(ref)
    assert ini == dt.datetime(2026, 8, 1, 0, 0, 0)
    assert fim == ref


# ── sugestoes_despesas_mes_anterior ──────────────────────────────────────────────────────────────
def test_sugestao_aparece_com_valor_do_mes_passado(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1010
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    ref = dt.datetime(2026, 8, 5)
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas["1.1.01"].id, 1500.0,
              data=dt.datetime(2026, 7, 10), historico="aluguel julho")
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=ref)
    sug = next(s for s in out["sugestoes"] if s["codigo"] == "5.4.01")
    assert sug["valor_sugerido"] == 1500.0
    assert sug["contrapartida_sugerida_id"] == contas["1.1.01"].id
    assert sug["ja_lancado_mes_atual"] is False
    db.close()


def test_sugestao_sem_movimento_nao_aparece(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1011
    mc.seed_plano(db, ot, oid)
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=dt.datetime(2026, 8, 5))
    assert out["sugestoes"] == []
    db.close()


def test_sugestao_liquido_zero_nao_aparece(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1012
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas["1.1.01"].id, 500.0, data=dt.datetime(2026, 7, 5))
    mc.lancar(db, ot, oid, contas["1.1.01"].id, contas["5.4.01"].id, 500.0, data=dt.datetime(2026, 7, 6))
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=dt.datetime(2026, 8, 5))
    assert not any(s["codigo"] == "5.4.01" for s in out["sugestoes"])
    db.close()


def test_sugestao_liquido_negativo_nao_aparece(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1013
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas["1.1.01"].id, 200.0, data=dt.datetime(2026, 7, 5))
    mc.lancar(db, ot, oid, contas["1.1.01"].id, contas["5.4.01"].id, 500.0, data=dt.datetime(2026, 7, 20))
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=dt.datetime(2026, 8, 5))
    assert not any(s["codigo"] == "5.4.01" for s in out["sugestoes"])
    db.close()


def test_contrapartida_sugerida_e_a_mais_recente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1014
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    banco = mc.criar_conta(db, ot, oid, contas["1.1"].id, "Banco Itaú")
    contas = _contas(db, ot, oid)
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas["1.1.01"].id, 100.0, data=dt.datetime(2026, 7, 5))
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas[banco["codigo"]].id, 200.0, data=dt.datetime(2026, 7, 20))
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=dt.datetime(2026, 8, 5))
    sug = next(s for s in out["sugestoes"] if s["codigo"] == "5.4.01")
    assert sug["contrapartida_sugerida_id"] == contas[banco["codigo"]].id   # o lançamento mais tardio venceu
    assert sug["valor_sugerido"] == 300.0
    db.close()


def test_contrapartida_sugerida_empate_no_mesmo_dia_desempata_por_id(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1015
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    banco = mc.criar_conta(db, ot, oid, contas["1.1"].id, "Banco Itaú")
    contas = _contas(db, ot, oid)
    mesmo_dia = dt.datetime(2026, 7, 15)
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas["1.1.01"].id, 100.0, data=mesmo_dia)
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas[banco["codigo"]].id, 100.0, data=mesmo_dia)
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=dt.datetime(2026, 8, 5))
    sug = next(s for s in out["sugestoes"] if s["codigo"] == "5.4.01")
    assert sug["contrapartida_sugerida_id"] == contas[banco["codigo"]].id   # maior id (o 2º lançado) vence
    db.close()


def test_ja_lancado_mes_atual_so_conta_debito(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1016
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    ref = dt.datetime(2026, 8, 20)
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas["1.1.01"].id, 1000.0, data=dt.datetime(2026, 7, 10))
    mc.lancar(db, ot, oid, contas["5.4.02"].id, contas["1.1.01"].id, 800.0, data=dt.datetime(2026, 7, 10))
    # 5.4.01 já foi relançada como débito este mês -> ja_lancado_mes_atual=True
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas["1.1.01"].id, 1000.0, data=dt.datetime(2026, 8, 5))
    # 5.4.02 só aparece como CRÉDITO este mês (estorno) -> não conta como "já lançado"
    mc.lancar(db, ot, oid, contas["1.1.01"].id, contas["5.4.02"].id, 50.0, data=dt.datetime(2026, 8, 6))
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=ref)
    sug1 = next(s for s in out["sugestoes"] if s["codigo"] == "5.4.01")
    sug2 = next(s for s in out["sugestoes"] if s["codigo"] == "5.4.02")
    assert sug1["ja_lancado_mes_atual"] is True
    assert sug2["ja_lancado_mes_atual"] is False
    db.close()


def test_conta_excluida_da_sugestao_pontos_fidelidade_nao_aparece(app_db):
    # achado do usuário 2026-08-15: 5.3.04 (Pontos Programa de Relacionamento/Fidelidade) é
    # lançada automaticamente pelo caminho da venda — sugerir repetição manual arriscaria
    # duplicar. Continua fora da lista mesmo tendo tido movimento líquido positivo mês passado.
    db = app_db.get_session(); ot, oid = "loja", 1019
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    mc.lancar(db, ot, oid, contas["5.3.04"].id, contas["1.1.01"].id, 700.0,
              data=dt.datetime(2026, 7, 10), historico="fidelidade automática")
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=dt.datetime(2026, 8, 5))
    assert not any(s["codigo"] == "5.3.04" for s in out["sugestoes"])
    db.close()


def test_conta_inativa_nao_aparece(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1017
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    mc.lancar(db, ot, oid, contas["5.4.01"].id, contas["1.1.01"].id, 500.0, data=dt.datetime(2026, 7, 10))
    contas["5.4.01"].ativa = 0
    db.commit()
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=dt.datetime(2026, 8, 5))
    assert not any(s["codigo"] == "5.4.01" for s in out["sugestoes"])
    db.close()


def test_contrapartida_inativada_depois_sinaliza_mas_mantem_id(app_db):
    db = app_db.get_session(); ot, oid = "loja", 1018
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    banco = mc.criar_conta(db, ot, oid, contas["1.1"].id, "Banco Itaú")
    contas = _contas(db, ot, oid)
    banco_conta = contas[banco["codigo"]]
    mc.lancar(db, ot, oid, contas["5.4.01"].id, banco_conta.id, 300.0, data=dt.datetime(2026, 7, 10))
    banco_conta.ativa = 0
    db.commit()
    out = mc.sugestoes_despesas_mes_anterior(db, ot, oid, ref=dt.datetime(2026, 8, 5))
    sug = next(s for s in out["sugestoes"] if s["codigo"] == "5.4.01")
    assert sug["contrapartida_sugerida_id"] == banco_conta.id
    assert sug["contrapartida_sugerida_ativa"] is False
    db.close()


# ── endpoint HTTP ────────────────────────────────────────────────────────────────────────────────
def test_endpoint_sugestoes_mes_anterior(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/lancamentos/sugestoes-mes-anterior")
    assert st == 200 and d["ok"]
    assert "sugestoes" in d and "periodo_referencia" in d


def test_endpoint_sugestoes_sem_login_401(http_client_factory):
    c = http_client_factory()
    st, d = c.get("/api/financeiro/lancamentos/sugestoes-mes-anterior")
    assert st == 401
