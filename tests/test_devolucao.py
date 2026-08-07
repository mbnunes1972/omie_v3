"""Fatia D — devolução (parcial/total) da venda. Reverte proporcionalmente a constituição DIFERIDA
(receita a realizar + impostos + provisões × ativos); a despesa já reconhecida NA EFETIVAÇÃO
(2026-08-07 — antes era "na NF-e"; custo real de um móvel já entregue) NÃO reverte. Resolve o buraco
do impostos revisável por devolução.
"""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def _montar_venda(db, ot, oid, proj):
    mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 10000.0, projeto_id=proj, ref="v:" + proj)
    mc.constituir_provisoes_fechamento(db, ot, oid, proj, {"custo_fabrica": 4000.0, "impostos": 1000.0}, ref_base="pf:" + proj)


def test_devolucao_total_reverte_receita_impostos_e_provisoes(app_db):
    db = app_db.get_session(); ot, oid = "loja", 990
    _montar_venda(db, ot, oid, "P")
    mc.devolver_venda(db, ot, oid, "P", 1.0, ref_base="dev:P")
    assert _s(db, ot, oid, "2.1.06") == 0.0 and _s(db, ot, oid, "1.1.02") == 0.0        # receita a realizar + recebível
    assert _s(db, ot, oid, "2.1.04.06") == 0.0 and _s(db, ot, oid, "1.1.06.06") == 0.0  # custo de fábrica
    assert _s(db, ot, oid, "2.1.04.13") == 0.0 and _s(db, ot, oid, "1.1.05") == 0.0     # impostos (o ponto do usuário)
    db.close()


def test_devolucao_parcial_reverte_a_fracao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 991
    _montar_venda(db, ot, oid, "P")
    mc.devolver_venda(db, ot, oid, "P", 0.5, ref_base="dev:P")
    assert _s(db, ot, oid, "2.1.06") == 5000.0
    assert _s(db, ot, oid, "2.1.04.06") == 2000.0
    assert _s(db, ot, oid, "2.1.04.13") == 500.0    # impostos revertidos proporcionalmente
    db.close()


def test_devolucao_nao_reverte_custo_ja_reconhecido_na_efetivacao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 992
    _montar_venda(db, ot, oid, "P")
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.06", 4000.0, ref="ef:P")   # baixa o ativo 1.1.06.06 (móvel entregue)
    out = mc.devolver_venda(db, ot, oid, "P", 1.0, ref_base="dev:P")
    assert "2.1.04.06" not in out                    # não reverte (ativo já baixado — custo real incorrido)
    assert _s(db, ot, oid, "2.1.04.06") == 4000.0    # provisão (a pagar à fábrica) segue
    assert _s(db, ot, oid, "5.1.01") == 4000.0       # CMV reconhecido permanece
    assert _s(db, ot, oid, "2.1.04.13") == 0.0       # mas impostos (não reconhecidos) revertem
    db.close()


def test_devolucao_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 993
    _montar_venda(db, ot, oid, "P")
    mc.devolver_venda(db, ot, oid, "P", 1.0, ref_base="dev:P")
    mc.devolver_venda(db, ot, oid, "P", 1.0, ref_base="dev:P")   # 2ª vez
    assert _s(db, ot, oid, "2.1.06") == 0.0 and _s(db, ot, oid, "2.1.04.06") == 0.0  # não duplicou
    db.close()
