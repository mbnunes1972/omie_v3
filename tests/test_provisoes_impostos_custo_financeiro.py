"""docs/db/TAREFA_PROVISOES.md — Impostos (2.1.04.13) e Custo Financeiro (2.1.04.19). Cobre os
itens 1, 3 e 4 (item 2 está BLOQUEADO — ver ACHADO-01, docs/db/ACHADOS_CONTABEIS.md: a
reconciliação de Contas a Receber/Caixa da venda antecipada/financiada não fecha em código
nenhum hoje, e Custo Financeiro entrar no padrão "tempo real" sem resolver isso primeiro
empurraria o ativo diferido pra negativo — achado feito com aritmética, não suposição):

1. Guarda: `resolver_saldo_provisao` recusa conta que não é provisão legítima.
3. Impostos: sobra e falta vão para a MESMA conta (4.3.01), sinais opostos.
4. 5.6.10 nunca é destino implícito — rubrica sem rota definida falha nomeando o código
   (inclusive Custo Financeiro, enquanto o item 2 seguir bloqueado); quando 5.6.10 É o destino
   de propósito, a escrita loga um alerta.
"""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


# ── item 1: guarda ────────────────────────────────────────────────────────────────────────────
def test_guarda_recusa_conta_que_nao_e_provisao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6100; mc.seed_plano(db, ot, oid)
    try:
        mc.resolver_saldo_provisao(db, ot, oid, "P", "5.2.06", ref="x")
        assert False, "deveria ter recusado conta fora do grupo de provisoes"
    except ValueError as e:
        assert "5.2.06" in str(e)
    db.close()


def test_guarda_recusa_provisao_excluida_do_painel(app_db):
    """2.1.04.01 (Comissão) e 2.1.04.04 (Devolução) não são set-aside de custo — não são
    provisão legítima pra este mecanismo (ver _PROV_PAINEL_EXCLUI)."""
    db = app_db.get_session(); ot, oid = "loja", 6101; mc.seed_plano(db, ot, oid)
    for cod in ("2.1.04.01", "2.1.04.04"):
        try:
            mc.resolver_saldo_provisao(db, ot, oid, "P", cod, ref="x:" + cod)
            assert False, "deveria ter recusado %s" % cod
        except ValueError as e:
            assert cod in str(e)
    db.close()


def test_guarda_aceita_provisao_legitima(app_db):
    """Controle positivo: uma provisão de verdade, sem saldo, não é recusada pela guarda —
    só retorna None (nada a resolver)."""
    db = app_db.get_session(); ot, oid = "loja", 6102; mc.seed_plano(db, ot, oid)
    assert mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.07", ref="x") is None
    db.close()


# ── item 2 BLOQUEADO: Custo Financeiro ainda não tem destino — precisa falhar, não rotear ───────
def test_custo_financeiro_sem_destino_falha_em_vez_de_rotear(app_db):
    """Item 2 continua bloqueado (ACHADO-01): sem a perna de liquidação (D provisão × C
    recebível/caixa), tratar 2.1.04.19 como "tempo real" cancelaria a provisão inteira contra um
    ativo que só tem uma fração aberta — ativo diferido ficaria negativo. Até isso ser resolvido,
    resolver_saldo_provisao tem que FALHAR pra esta conta (item 4), nunca inventar uma rota."""
    db = app_db.get_session(); ot, oid = "loja", 6103; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 1000.0}, ref_base="pf:P")
    mc.reconhecer_custo_financeiro(db, ot, oid, "P", "financeira", 700.0, ref="rcf:P")
    assert _s(db, ot, oid, "2.1.04.19") == 1000.0    # provisão intocada por reconhecer_custo_financeiro
    assert _s(db, ot, oid, "1.1.06.19") == 300.0     # só o ativo drena
    try:
        mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.19", ref="rs:P:19")
        assert False, "deveria falhar -- 2.1.04.19 nao tem destino definido (item 2 bloqueado)"
    except ValueError as e:
        assert "2.1.04.19" in str(e)
    assert _s(db, ot, oid, "2.1.04.19") == 1000.0    # nada foi gravado
    assert _s(db, ot, oid, "1.1.06.19") == 300.0
    db.close()


# ── item 3: Impostos → 4.3.01, nos dois sentidos ────────────────────────────────────────────────
def test_impostos_falta_debita_4301(app_db):
    """Efetivado (via faturamento) > provisionado: a diferença é MAIS dedução de receita —
    debita 4.3.01, igual à dedução de rotina na emissão. "Falta" simulada via reclassificação
    pra outra provisão (cenário real: parte do que sobrava de 2.1.04.13 é redirecionada,
    deixando o saldo negativo) — `ajustar_provisao_delta` não serve aqui: sua redução é capada
    ao ativo diferido em aberto (0, já todo baixado pela efetivação), então não criaria a
    falta. `saldo_conta` usa a natureza da conta (4.3.01 é "credora", grupo 4): debitar reduz
    o número (fica mais negativo) — é essa a direção de "mais dedução"."""
    db = app_db.get_session(); ot, oid = "loja", 6105; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"impostos": 1000.0}, ref_base="pf:P")
    mc.efetivar_impostos_segmento(db, ot, oid, "P", 1000.0, ref_base="fat:P")   # zera a provisão via rota normal
    mc.reclassificar_provisao(db, ot, oid, "P", "2.1.04.13", "2.1.04.07", 300.0, ref="reclass:P")
    assert _s(db, ot, oid, "2.1.04.13") == -300.0    # falta
    ded_antes = _s(db, ot, oid, "4.3.01")
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.13", ref="rs:P:13")
    assert _s(db, ot, oid, "2.1.04.13") == 0.0
    assert _s(db, ot, oid, "4.3.01") == ded_antes - 300.0   # mais dedução (débito → mais negativo)
    assert _s(db, ot, oid, "5.6.10") == 0.0          # nunca mais falta->5.6.10 pra impostos
    assert _s(db, ot, oid, "4.4.02") == 0.0
    db.close()


def test_impostos_sobra_credita_4301_mesma_conta_sinal_oposto(app_db):
    """Provisionado > efetivado: a sobra volta pra 4.3.01 (mesma conta da falta), reduzindo a
    dedução em vez de virar receita em 4.4.02 (achado do Marcelo — os dois lados da mesma
    variância não podem cair em contas diferentes). Crédito em conta "credora" AUMENTA
    `saldo_conta` — sinal oposto do débito da falta, mesma conta."""
    db = app_db.get_session(); ot, oid = "loja", 6106; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"impostos": 1000.0}, ref_base="pf:P")
    mc.efetivar_impostos_segmento(db, ot, oid, "P", 700.0, ref_base="fat:P")   # só parte efetivada
    assert _s(db, ot, oid, "2.1.04.13") == 300.0     # sobra
    ded_antes = _s(db, ot, oid, "4.3.01")
    mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.13", ref="rs:P:13")
    assert _s(db, ot, oid, "2.1.04.13") == 0.0
    assert _s(db, ot, oid, "4.3.01") == ded_antes + 300.0   # menos dedução (crédito → sinal oposto da falta)
    assert _s(db, ot, oid, "4.4.02") == 0.0          # nunca mais sobra->receita pra impostos
    db.close()


# ── item 4: 5.6.10 nunca é destino implícito ────────────────────────────────────────────────────
def test_rubrica_sem_destino_falha_nomeando_o_codigo(app_db, monkeypatch):
    """Provisão legítima (grupo 2.1.04, não excluída do painel), mas sem rota tempo-real nem
    destino explícito definido — simula uma rubrica futura acrescentada sem configurar o
    destino. Tem que falhar, não sumir em 5.6.10."""
    db = app_db.get_session(); ot, oid = "loja", 6107; mc.seed_plano(db, ot, oid)
    pai = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="2.1.04").first()
    nova = mc.Conta(owner_tipo=ot, owner_id=oid, codigo="2.1.04.98", nome="Provisão Sintética de Teste",
                    grupo=2, tipo="analitica", natureza="credora", pai_id=pai.id, ativa=1, ordem=999)
    db.add(nova); db.commit()
    caixa = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="1.1.01").first()
    mc.lancar(db, ot, oid, caixa.id, nova.id, 500.0, projeto_id="P", historico="constituição sintética",
              ref="sint:P:98")
    assert "2.1.04.98" not in mc._PROV_DESPESA_POR_ATIVO.values()
    assert "2.1.04.98" not in mc._PROV_TEMPO_REAL_ROTA_PROPRIA
    assert "2.1.04.98" not in mc._PROV_DESTINO_VARIANCIA
    try:
        mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.98", ref="rs:P:98")
        assert False, "deveria ter falhado — rubrica sem destino definido"
    except ValueError as e:
        assert "2.1.04.98" in str(e)
    db.close()


def test_5610_usada_de_proposito_grava_e_alerta(app_db, monkeypatch, caplog):
    """Quando 5.6.10 É o destino explícito de propósito (simulado aqui via monkeypatch — hoje
    nenhuma rubrica real usa), a escrita acontece normalmente E loga um alerta na própria função."""
    db = app_db.get_session(); ot, oid = "loja", 6108; mc.seed_plano(db, ot, oid)
    pai = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="2.1.04").first()
    nova = mc.Conta(owner_tipo=ot, owner_id=oid, codigo="2.1.04.97", nome="Provisão Sintética 5.6.10",
                    grupo=2, tipo="analitica", natureza="credora", pai_id=pai.id, ativa=1, ordem=999)
    db.add(nova); db.commit()
    caixa = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="1.1.01").first()
    mc.lancar(db, ot, oid, caixa.id, nova.id, 500.0, projeto_id="P", historico="constituição sintética",
              ref="sint:P:97")

    monkeypatch.setitem(mc._PROV_DESTINO_VARIANCIA, "2.1.04.97", "5.6.10")
    import logging
    with caplog.at_level(logging.WARNING, logger="mod_contabil"):
        mc.resolver_saldo_provisao(db, ot, oid, "P", "2.1.04.97", ref="rs:P:97")
    # sobra (saldo>0) credita o destino — 5.6.10 é "devedora" (grupo 5): crédito baixa
    # `saldo_conta` (D−C), por isso -500 (nada mais tocou 5.6.10 neste teste sintético).
    assert _s(db, ot, oid, "5.6.10") == -500.0
    assert any("5.6.10" in rec.message and "2.1.04.97" in rec.message for rec in caplog.records)
    db.close()
