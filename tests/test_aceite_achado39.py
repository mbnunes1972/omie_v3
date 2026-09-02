# -*- coding: utf-8 -*-
"""docs/db/TAREFA_PERCURSO_0109.md, item B4 — o aceite do ACHADO-39.

`_peConcValidasPorSinal(a.diferenca)` (frontend) escolhia os botões pelo sinal de Δ CUSTO DE
FÁBRICA — referência de conferência interna que o cliente nunca vê. A decisão (Manter/Absorver/
Cobrar/Estornar) é sobre Δ A COBRAR/ESTORNAR (`diferenca_valor_contrato`), a grandeza que
efetivamente vira Complemento/Estorno. Passa a usar essa.

**Medição antes do conserto** (regra do Marcelo para este item): consultada a `orizon_homologacao`
(servidor 167.88.33.121) via SSH — 4 linhas de `conciliacao_pe_fase` já registradas como
"Absorver R$ 0,00" (`diferenca_valor_contrato = 0`), nos projetos Teste_1 e Teste_2 (o próprio
percurso de Marcelo, 31/08 e 02/09), com `diferenca_cfo` de 793.75 e 76.27 — exatamente o padrão
do achado: custo de fábrica mudou, mas nada a cobrar do cliente. Nenhuma linha apagada ou alterada
— o teste abaixo prova só que NENHUMA NOVA fica exigindo decisão quando Δ a cobrar é zero."""
from tests.test_conciliacao_pe_e2e import (
    _setup, _carrega_pe, _registra_venda_baseline, _aprova_af1_af2, _login,
)


def test_ambiente_com_delta_a_cobrar_zero_nao_e_pendencia(http_client_factory, seed, app_db):
    # venda_pe == budget_total (VBVA contratado) → diferenca_valor_contrato_estimada dá ZERO,
    # não importa o vava_contratado — mas diferenca_cfo continua não-zero (custo subiu de verdade).
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=80000.0)
    c = _login(http_client_factory)

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    assert st == 200 and body["ok"], body
    fase = body["fases"][0]
    amb = fase["ambientes"][0]
    assert amb["diferenca"] == 3000.0, "Δ custo tem que continuar não-zero — é referência, não pendência"
    assert amb["diferenca_valor_contrato"] == 0.0, "Δ a cobrar zero é a condição deste aceite"
    assert amb["decisao"] is None, "nenhuma decisão foi registrada — e não deve ser exigida"
    assert fase["completa"] is True, "Δ a cobrar zero não é pendência — a fase já está completa"
    assert fase["faltam"] == []

    _registra_venda_baseline(app_db, oid)
    _aprova_af1_af2(c, oid)
    st2, body2 = c.post(f"/api/projetos/{nome}/ciclo/11d/aprovar",
                        {"login": "dir_l1", "senha": "senha123"})
    assert st2 == 200 and body2["ok"], (
        "a aprovação da AF2 não pode exigir decisão de um ambiente com Δ a cobrar zero", body2)


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
    assert fase["completa"] is False
    assert fase["faltam"] == [pid]
