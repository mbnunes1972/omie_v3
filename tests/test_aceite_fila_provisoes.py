# -*- coding: utf-8 -*-
"""docs/db/TAREFA_FILA_PROVISOES.md, F2-3 — os aceites do ACHADO-26.

Duas coisas que entram juntas, nesta ordem: a Fila de Provisões (porta da frente do veredito,
`/api/financeiro/fila-provisoes` + `/api/financeiro/fila-provisoes/veredito`) e o fechamento do
desvio (`/api/financeiro/resolver-saldo-provisao` passa a recusar qualquer rubrica que exija
veredito — só continua aberto para Impostos/Custo Financeiro, ACHADO-01, `_PROV_FORA_DO_VEREDITO`).

Reusa os helpers de tests/test_aceite_achado16.py (mesmo projeto "raso" pronto pra Etapa 21)."""
import pytest

from tests.test_aceite_achado16 import _projeto_pronto_para_etapa_21, _constituir_custo_fabrica_nunca_efetivado


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _constituir_impostos(app_db, seed, nome, valor=200.0):
    import mod_contabil as mc
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.constituir_provisoes_fechamento(db, ot, oid, nome, {"impostos": valor}, ref_base="pf:" + nome)
    db.commit()
    db.close()
    return ot, oid


# ── Aceite 1 — o desvio recusa, e o projeto continua sem fechar por ele ─────────────────────

def test_desvio_recusado_para_rubrica_que_exige_veredito(app_db, seed, http_client_factory):
    """É o achado inteiro numa asserção: zerar o saldo pelo `/resolver-saldo-provisao` (a porta
    dos fundos) e concluir o projeto pela Conciliação Final tem que ser recusado — não só um dos
    dois, os DOIS."""
    nome = "F23_desvio_recusado"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/resolver-saldo-provisao",
                      {"conta": "2.1.04.06", "projeto": nome})
    assert not (st == 200 and body.get("ok")), (
        "2.1.04.06 (Custo de Fábrica) exige veredito — o desvio genérico não pode mais zerar "
        "essa rubrica: st=%r body=%r" % (st, body))

    st2, body2 = c.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {})
    assert not (st2 == 200 and body2.get("ok")), (
        "mesmo depois da tentativa pelo desvio, o projeto não pode concluir sem veredito de "
        "verdade: st=%r body=%r" % (st2, body2))


# ── Aceite 2 — cada veredito pela fila, isolado ─────────────────────────────────────────────

def test_fila_veredito_efetivada_so_para_falta(app_db, seed, http_client_factory):
    """'efetivada' só é válido quando o efetivado JÁ supera o provisionado (FALTA) — o resíduo
    MECÂNICO entre ativo e provisão é cancelado sem tocar a DRE (a despesa real já foi
    reconhecida a cada efetivação)."""
    import mod_contabil as mc
    nome = "F23_fila_efetivada"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    # efetiva MAIS do que o provisionado — cria a FALTA genuína.
    db = app_db.get_session()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.06", 1200.0, ref="f23:efetiva-demais")
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06", "veredito": "efetivada"})
    assert st == 200 and body.get("ok"), body

    db = app_db.get_session()
    saldo = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None, projeto_id=nome)
    db.close()
    assert abs(saldo) < 0.005, "saldo tem que zerar depois do veredito 'efetivada' — %r" % saldo


def test_fila_veredito_encerrada_valor_menor_reconhece_custo_real(app_db, seed, http_client_factory):
    """Mesmo cenário do ACHADO-16 original (test_aceite_achado16.py), mas pela FILA, não pela
    Conciliação Final: SOBRA de 1000, efetivado real de 700 — reconhece o custo em 5.1.01 E
    reverte só o resíduo genuíno (300)."""
    import mod_contabil as mc
    nome = "F23_fila_encerrada_valor_menor"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06",
                       "veredito": "encerrada_valor_menor", "valor_efetivado": 700.0})
    assert st == 200 and body.get("ok"), body
    assert body["veredito"]["valor_efetivado"] == 700.0
    assert body["veredito"]["valor_revertido"] == 300.0

    db = app_db.get_session()
    saldo = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None, projeto_id=nome)
    despesa_5101 = mc.total_lancado(db, ot, oid, "5.1.01", "debito", nome)
    db.close()
    assert abs(saldo) < 0.005, saldo
    assert abs(despesa_5101 - 700.0) < 0.005, despesa_5101


def test_fila_veredito_nao_se_aplica_exige_motivo(app_db, seed, http_client_factory):
    nome = "F23_fila_nao_se_aplica"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=500.0)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06", "veredito": "nao_se_aplica"})
    assert not (st == 200 and body.get("ok")), (
        "'nao_se_aplica' sem motivo tem que ser recusado: st=%r body=%r" % (st, body))

    st2, body2 = c.post("/api/financeiro/fila-provisoes/veredito",
                        {"projeto": nome, "conta": "2.1.04.06", "veredito": "nao_se_aplica",
                         "motivo": "Ambiente cancelado antes da fábrica produzir."})
    assert st2 == 200 and body2.get("ok"), body2
    assert body2["veredito"]["valor_revertido"] == 500.0


def test_fila_veredito_ainda_vai_chegar_mantem_projeto_aberto(app_db, seed, http_client_factory):
    nome = "F23_fila_ainda_vai_chegar"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=800.0)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06", "veredito": "ainda_vai_chegar"})
    assert st == 200 and body.get("ok"), body

    # o veredito fica registrado, mas NÃO resolve nada no livro — o projeto continua sem poder
    # concluir, exatamente como sem veredito nenhum.
    st2, body2 = c.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {})
    assert not (st2 == 200 and body2.get("ok")), (
        "'ainda_vai_chegar' não pode destravar o fechamento do projeto: st=%r body=%r"
        % (st2, body2))


# ── Aceite 3 — controle positivo: Impostos continua funcionando pelo desvio ─────────────────

def test_resolver_saldo_provisao_continua_funcionando_para_impostos(app_db, seed, http_client_factory):
    """Sem este controle, uma restrição ampla demais (bloquear TODA rubrica) passaria nos dois
    testes acima do mesmo jeito — Impostos é o uso legítimo que o F2-3 tinha que preservar."""
    import mod_contabil as mc
    nome = "F23_impostos_continua"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_impostos(app_db, seed, nome, valor=200.0)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/resolver-saldo-provisao",
                      {"conta": "2.1.04.13", "projeto": nome})
    assert st == 200 and body.get("ok"), body

    db = app_db.get_session()
    saldo = mc._mov(db, ot, oid, "2.1.04.13", "credor", None, None, projeto_id=nome)
    db.close()
    assert abs(saldo) < 0.005, saldo


# ── Aceite 4 — o fluxo completo pela tela: fila → conclusão → custo em 5.1.01 ───────────────

def test_fluxo_completo_fila_ate_conclusao_com_custo_em_5101(app_db, seed, http_client_factory):
    """É o aceite que prova que a porta da frente existe de verdade: dar veredito na fila,
    concluir o projeto pela Conciliação Final normal ({} — a tela não ganha campo de veredito),
    e o custo aparecer em 5.1.01."""
    import mod_contabil as mc
    nome = "F23_fluxo_completo"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    c = _login(http_client_factory, "dir_l1")

    # a fila lista a rubrica em aberto.
    st, body = c.get("/api/financeiro/fila-provisoes")
    assert st == 200 and body["ok"], body
    linha = next((r for r in body["fila"] if r["projeto_id"] == nome and r["codigo"] == "2.1.04.06"), None)
    assert linha is not None, body["fila"]
    assert abs(linha["saldo_aberto"] - 1000.0) < 0.005, linha

    # dá o veredito pela fila — nunca pela Conciliação Final.
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06",
                       "veredito": "encerrada_valor_menor", "valor_efetivado": 1000.0})
    assert st == 200 and body.get("ok"), body

    # F2-25 Passo 3 (05/09, DECIDIDO): a rubrica resolvida NÃO some da fila — migra pro grupo
    # "fechada_zerada" (visível, sem ação), pra distinguir de uma que nunca abriu.
    st, body = c.get("/api/financeiro/fila-provisoes")
    assert st == 200 and body["ok"], body
    linha = next((r for r in body["fila"] if r["projeto_id"] == nome and r["codigo"] == "2.1.04.06"), None)
    assert linha is not None, body["fila"]
    assert linha["grupo"] == "fechada_zerada", linha
    assert abs(linha["saldo_aberto"]) < 0.005, linha

    # a Conciliação Final conclui com o corpo vazio de sempre — nada mudou na tela.
    st, body = c.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {})
    assert st == 200 and body.get("ok"), body
    assert body["status"] == "concluido"

    db = app_db.get_session()
    despesa_5101 = mc.total_lancado(db, ot, oid, "5.1.01", "debito", nome)
    db.close()
    assert abs(despesa_5101 - 1000.0) < 0.005, (
        "o custo real da fábrica tem que aparecer em 5.1.01 — %r" % despesa_5101)
