# -*- coding: utf-8 -*-
"""docs/db/TAREFA_PERCURSO_0109.md, item B4 — o aceite do ACHADO-39, e a correção do C2
(docs/db/TAREFA_PERCURSO_0209.md).

`_peConcValidasPorSinal(a.diferenca)` (frontend) escolhia os botões pelo sinal de Δ CUSTO DE
FÁBRICA — referência de conferência interna que o cliente nunca vê. A decisão (Manter/Absorver/
Cobrar/Estornar) é sobre Δ A COBRAR/ESTORNAR (`diferenca_valor_contrato`), a grandeza que
efetivamente vira Complemento/Estorno. Passa a usar essa.

**Medição antes do conserto** (regra do Marcelo para este item): consultada a `orizon_homologacao`
(servidor 167.88.33.121) via SSH — 4 linhas de `conciliacao_pe_fase` já registradas como
"Absorver R$ 0,00" (`diferenca_valor_contrato = 0`), nos projetos Teste_1 e Teste_2 (o próprio
percurso de Marcelo, 31/08 e 02/09), com `diferenca_cfo` de 793.75 e 76.27 — exatamente o padrão
do achado: custo de fábrica mudou, mas nada a cobrar do cliente.

**C2 (02/09) corrige a primeira versão deste aceite:** "Δ a cobrar zero não é pendência" estava
ERRADO quando Δ custo não é zero — o custo mudou e a empresa absorveu a margem, e isso é fato do
resultado, não referência. Só quando os DOIS são zero é que não há nada. O teste original
('nao_e_pendencia') foi reescrito para provar o OPOSTO do que provava antes — o nome mudou de
propósito, pra não ficar um teste com nome mentindo sobre o que prova."""
import mod_conciliacao_pe as mc_pe

from tests.test_conciliacao_pe_e2e import (
    _setup, _carrega_pe, _registra_venda_baseline, _aprova_af1_af2, _login,
)


def test_delta_custo_sem_delta_a_cobrar_continua_pendencia(http_client_factory, seed, app_db):
    """C2: Δ custo ≠ 0 e Δ a cobrar = 0 — a fase NÃO fecha até o reconhecimento. É a correção do
    erro do B4 (a versão anterior deste teste dizia o oposto: 'nao_e_pendencia')."""
    # venda_pe == budget_total (VBVA contratado) → diferenca_valor_contrato_estimada dá ZERO,
    # não importa o vava_contratado — mas diferenca_cfo continua não-zero (custo subiu de verdade).
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=80000.0)
    c = _login(http_client_factory)

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    assert st == 200 and body["ok"], body
    fase = body["fases"][0]
    amb = fase["ambientes"][0]
    assert amb["diferenca"] == 3000.0
    assert amb["diferenca_valor_contrato"] == 0.0
    assert amb["decisao"] is None
    assert amb["precisa_reconhecimento"] is True
    assert fase["completa"] is False, "Δ custo ≠ 0 sem Δ a cobrar CONTINUA pendência (C2)"
    assert fase["faltam"] == [pid]

    _registra_venda_baseline(app_db, oid)
    _aprova_af1_af2(c, oid)
    st2, body2 = c.post(f"/api/projetos/{nome}/ciclo/11d/aprovar",
                        {"login": "dir_l1", "senha": "senha123"})
    assert st2 == 400 and body2["ok"] is False and body2["faltam"] == [pid], (
        "a AF2 não pode aprovar com um Δ custo não reconhecido pendente", body2)


def test_reconhecimento_resolve_a_pendencia_com_o_valor_do_delta_custo(http_client_factory, seed, app_db):
    """C2: registrar o reconhecimento (tipo_decisao='absorver', valor_aprovado=|Δ custo|) resolve
    a pendência — e o valor gravado é o Δ CUSTO, não zero (o que a rota antiga gravava)."""
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=80000.0)
    c = _login(http_client_factory)

    st, body = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                      {"login": "dir_l1", "senha": "senha123",
                       "tipo_decisao": "absorver", "valor_aprovado": 3000.0})
    assert st == 200 and body["ok"], body
    assert body["decisao"]["valor_aprovado"] == 3000.0, (
        "o reconhecimento grava o Δ CUSTO à vista, nunca 0 — é isso que prova que alguém viu")

    st2, body2 = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    fase = body2["fases"][0]
    assert fase["completa"] is True, "reconhecido, a fase fecha"
    assert fase["faltam"] == []


def test_ambos_zero_nao_e_pendencia(http_client_factory, seed, app_db):
    """Único caso em que 'sem diferença' de fato vale: Δ a cobrar E Δ custo zerados."""
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=30000.0)   # Δ custo = 0 também
    c = _login(http_client_factory)

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    assert st == 200 and body["ok"], body
    fase = body["fases"][0]
    amb = fase["ambientes"][0]
    assert amb["diferenca"] == 0.0
    assert amb["diferenca_valor_contrato"] == 0.0
    assert amb["precisa_reconhecimento"] is False
    assert fase["completa"] is True
    assert fase["faltam"] == []


def test_ambiente_com_delta_a_cobrar_nao_zero_continua_pendencia(http_client_factory, seed, app_db):
    """Controle positivo: quando Δ a cobrar É diferente de zero, continua pendência normal —
    o conserto não pode ter afrouxado o caso comum."""
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)   # sem venda_pe: cai no fallback CFO×markup
    c = _login(http_client_factory)

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    assert st == 200 and body["ok"], body
    fase = body["fases"][0]
    assert fase["ambientes"][0]["diferenca_valor_contrato"] == 6000.0
    assert fase["ambientes"][0]["precisa_reconhecimento"] is False
    assert fase["completa"] is False
    assert fase["faltam"] == [pid]


def test_precisa_reconhecimento_pure_function():
    assert mc_pe.precisa_reconhecimento(diferenca_valor_contrato=0.0, diferenca_cfo=793.75) is True
    assert mc_pe.precisa_reconhecimento(diferenca_valor_contrato=0.0, diferenca_cfo=0.0) is False
    assert mc_pe.precisa_reconhecimento(diferenca_valor_contrato=1000.0, diferenca_cfo=793.75) is False
    assert mc_pe.decisao_e_necessaria(0.0, 793.75) is True
    assert mc_pe.decisao_e_necessaria(0.0, 0.0) is False
