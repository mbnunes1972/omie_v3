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

def test_fila_veredito_absorver_so_para_falta(app_db, seed, http_client_factory):
    """F2-27 (renomeado de 'efetivada'): 'absorver' só é válido quando o pago JÁ supera o
    reconhecido (FALTA) — o excedente vira Despesa de Conciliação."""
    import mod_contabil as mc
    nome = "F23_fila_absorver"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    # paga MAIS do que o provisionado — cria a FALTA genuína.
    db = app_db.get_session()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.06", 1200.0, ref="f23:paga-demais")
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06", "veredito": "absorver"})
    assert st == 200 and body.get("ok"), body

    db = app_db.get_session()
    saldo = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None, projeto_id=nome)
    despesa_conciliacao = mc._mov(db, ot, oid, "5.7.01", "devedor", None, None, projeto_id=nome)
    db.close()
    assert abs(saldo) < 0.005, "saldo tem que zerar depois do veredito 'absorver' — %r" % saldo
    assert abs(despesa_conciliacao - 200.0) < 0.005, despesa_conciliacao


def test_fila_veredito_receber_reconhece_provisionado_integral_na_emissao(app_db, seed, http_client_factory):
    """Mesmo cenário do ACHADO-16 original (test_aceite_achado16.py), mas pela FILA, não pela
    Conciliação Final: a emissão já reconheceu o PROVISIONADO INTEGRAL (1000) em 5.1.01; a
    fábrica cobrou só 700; 'receber' reverte só o resíduo genuíno (300) pra Receita de
    Conciliação — o veredito não reconhece nada de novo, só decide o destino do que sobrou."""
    import mod_contabil as mc
    nome = "F23_fila_receber"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)
    db = app_db.get_session()
    mc.reconhecer_provisoes_segmento(db, ot, oid, nome, "mercadoria", 100.0, ref_base="rec:doc1")
    db.commit()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.06", 700.0, ref="f23:paga")
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06", "veredito": "receber"})
    assert st == 200 and body.get("ok"), body
    assert body["veredito"]["valor_revertido"] == 300.0

    db = app_db.get_session()
    saldo = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None, projeto_id=nome)
    despesa_5101 = mc.total_lancado(db, ot, oid, "5.1.01", "debito", nome)
    receita_conciliacao = mc._mov(db, ot, oid, "4.5.01", "credor", None, None, projeto_id=nome)
    db.close()
    assert abs(saldo) < 0.005, saldo
    assert abs(despesa_5101 - 1000.0) < 0.005, despesa_5101
    assert abs(receita_conciliacao - 300.0) < 0.005, receita_conciliacao


def test_fila_veredito_receber_funciona_sem_motivo(app_db, seed, http_client_factory):
    """F2-27: 'receber' (renomeado, colapso de 'encerrada_valor_menor'+'nao_se_aplica') NÃO exige
    motivo — a distinção "custou menos" × "nunca incidiu" perdeu significado contábil."""
    nome = "F23_fila_receber_sem_motivo"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=500.0)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06", "veredito": "receber"})
    assert st == 200 and body.get("ok"), body
    assert body["veredito"]["valor_revertido"] == 500.0


def test_fila_veredito_adiar_mantem_projeto_aberto(app_db, seed, http_client_factory):
    nome = "F23_fila_adiar"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=800.0)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06", "veredito": "adiar"})
    assert st == 200 and body.get("ok"), body

    # o veredito fica registrado, mas NÃO resolve nada no livro — o projeto continua sem poder
    # concluir, exatamente como sem veredito nenhum.
    st2, body2 = c.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {})
    assert not (st2 == 200 and body2.get("ok")), (
        "'adiar' não pode destravar o fechamento do projeto: st=%r body=%r"
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
    e o custo aparecer em 5.1.01. F2-27: a fábrica cobrou menos do que o provisionado — o
    veredito 'receber' resolve, e o custo em 5.1.01 vem da emissão (provisionado integral),
    não do que foi pago."""
    import mod_contabil as mc
    nome = "F23_fluxo_completo"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)
    db = app_db.get_session()
    mc.reconhecer_provisoes_segmento(db, ot, oid, nome, "mercadoria", 100.0, ref_base="rec:doc-fluxo")
    db.commit()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.06", 700.0, ref="f23:fluxo:paga")
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")

    # a fila lista a rubrica em aberto (sobra de 300 — pagou menos do que foi reconhecido).
    st, body = c.get("/api/financeiro/fila-provisoes")
    assert st == 200 and body["ok"], body
    linha = next((r for r in body["fila"] if r["projeto_id"] == nome and r["codigo"] == "2.1.04.06"), None)
    assert linha is not None, body["fila"]
    assert abs(linha["saldo_aberto"] - 300.0) < 0.005, linha

    # dá o veredito pela fila — nunca pela Conciliação Final.
    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06", "veredito": "receber"})
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
