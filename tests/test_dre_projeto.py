import mod_contabil as mc


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_margem_projeto(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 20); c = _q(db, 20)
    # Projeto A: receita 1000, custo produto 400, comissão 100, provisão 30
    mc.registrar_evento(db, "loja", 20, "faturamento", 1000.0, projeto_id="A")
    mc.lancar(db, "loja", 20, conta_debito_id=c("5.1.01"), conta_credito_id=c("2.1.01"), valor=400.0, projeto_id="A")
    mc.lancar(db, "loja", 20, conta_debito_id=c("5.3.01"), conta_credito_id=c("1.1.01"), valor=100.0, projeto_id="A")
    # FASE D2: a garantia vira DESPESA (5.2.12, formalismo S109) só na NF-e (matching pleno, baixa do ativo diferido 1.1.06.03);
    # a margem lê o custo REALIZADO — simulando aqui o custo já reconhecido na emissão.
    mc.lancar(db, "loja", 20, conta_debito_id=c("5.2.12"), conta_credito_id=c("1.1.06.03"), valor=30.0, projeto_id="A")
    r = mc.margem_projeto(db, "loja", 20, "A")
    db.close()
    assert r["receita"] == 1000.0 and r["custo_produto"] == 400.0
    assert r["comissao"] == 100.0 and r["prov_garantia"] == 30.0
    assert r["margem_contribuicao"] == 470.0     # 1000-400-30(garantia)-100(comissao)


def test_margem_projeto_expoe_saldo_aberto_e_margem_projetada(app_db):
    """2026-08-07 (achado do usuário): margem_contribuicao só reflete o que já foi RECONHECIDO — um
    projeto recém-faturado com o custo ainda todo por reconhecer aparece com margem quase cheia.
    saldo_provisao_aberto + margem_projetada dão o quadro completo (realizado × pior caso).

    ACHADO-60 (F2-27, 05/09/2026): o que muda o estágio agora é a EMISSÃO
    (`reconhecer_provisoes_segmento`), não mais a efetivação — `efetivar_provisao` (pagamento)
    sozinho não move mais margem_contribuicao nem margem_projetada (ver
    test_efetivar_sozinho_nao_move_margem_nem_projetada, abaixo)."""
    db = app_db.get_session(); mc.seed_plano(db, "loja", 22)
    mc.registrar_evento(db, "loja", 22, "registro_venda_contrato", 10000.0, projeto_id="P", ref="v:P")
    mc.constituir_provisoes_fechamento(db, "loja", 22, "P", {"montagem": 1000.0}, ref_base="pf:P")
    mc.registrar_evento(db, "loja", 22, "faturamento", 10000.0, projeto_id="P", ref="fat:P")
    # nada reconhecido ainda: margem_contribuicao "cheia", mas saldo_provisao_aberto expõe o risco
    r0 = mc.margem_projeto(db, "loja", 22, "P")
    assert r0["margem_contribuicao"] == 10000.0
    assert r0["saldo_provisao_aberto"] == 1000.0
    assert r0["margem_projetada"] == 9000.0     # pior caso: se reconhecer toda a provisão pendente
    # emite a NF-e (reconhece o provisionado INTEGRAL, F2-27): margem_contribuicao cai o valor cheio
    mc.reconhecer_provisoes_segmento(db, "loja", 22, "P", "mercadoria", 100.0, ref_base="rec:P")
    r1 = mc.margem_projeto(db, "loja", 22, "P")
    assert r1["margem_contribuicao"] == 9000.0    # 10000 - 1000 (montagem, provisionado integral)
    assert r1["saldo_provisao_aberto"] == 1000.0  # ainda NÃO paga — o eixo do passivo não se move
    assert r1["margem_projetada"] == 9000.0       # == margem_contribuicao — já reconhecida, nada a projetar
    db.close()


def test_margem_projetada_nao_soma_excedente_ja_refletido(app_db):
    """Se o custo já superou o provisionado, o ativo (1.1.06.02) zera antes do reconhecimento
    inteiro consumir o saldo — margem_contribuicao só reconhece o que HAVIA no ativo (o
    provisionado, não o excesso); margem_projetada não deve descontar de novo (senão contaria
    o que já está zerado como se ainda faltasse reconhecer)."""
    db = app_db.get_session(); mc.seed_plano(db, "loja", 23)
    mc.registrar_evento(db, "loja", 23, "registro_venda_contrato", 10000.0, projeto_id="P", ref="v:P")
    mc.constituir_provisoes_fechamento(db, "loja", 23, "P", {"montagem": 1000.0}, ref_base="pf:P")
    mc.registrar_evento(db, "loja", 23, "faturamento", 10000.0, projeto_id="P", ref="fat:P")
    mc.reconhecer_provisoes_segmento(db, "loja", 23, "P", "mercadoria", 100.0, ref_base="rec:P")
    r = mc.margem_projeto(db, "loja", 23, "P")
    assert r["saldo_provisao_aberto"] == 1000.0   # ainda não paga (eixo do passivo, à parte)
    assert r["margem_contribuicao"] == 9000.0     # 10000 - 1000 (o provisionado, tudo que o ativo tinha)
    assert r["margem_projetada"] == 9000.0        # == margem_contribuicao (ativo zerado, nada mais a reconhecer)
    db.close()


def test_efetivar_sozinho_nao_move_margem_nem_projetada(app_db):
    """ACHADO-60 (F2-27, 05/09/2026): pagar (`efetivar_provisao`) sem antes ter emitido a NF-e não
    move mais margem_contribuicao (a despesa só nasce na emissão) nem margem_projetada (que agora
    lê o ativo, não o passivo) — só reduz saldo_provisao_aberto (o passivo, o que falta pagar).
    Controle-irmão dos dois testes acima: prova que o eixo do pagamento ficou mesmo isolado do
    eixo do reconhecimento."""
    db = app_db.get_session(); mc.seed_plano(db, "loja", 27)
    mc.registrar_evento(db, "loja", 27, "registro_venda_contrato", 10000.0, projeto_id="P", ref="v:P")
    mc.constituir_provisoes_fechamento(db, "loja", 27, "P", {"montagem": 1000.0}, ref_base="pf:P")
    mc.registrar_evento(db, "loja", 27, "faturamento", 10000.0, projeto_id="P", ref="fat:P")
    mc.efetivar_provisao(db, "loja", 27, "P", "2.1.04.02", 400.0, ref="ef:P")
    r = mc.margem_projeto(db, "loja", 27, "P")
    assert r["margem_contribuicao"] == 10000.0    # nada reconhecido — pagamento sozinho não move
    assert r["saldo_provisao_aberto"] == 600.0     # o passivo SIM reduziu — pagou 400 de 1000
    assert r["margem_projetada"] == 9000.0         # ainda o pior caso pleno (ativo intacto, nada reconhecido)
    db.close()


def test_margem_projetada_janela_pos_emissao_pre_pagamento(app_db):
    """ACHADO-60 (F2-27, 05/09/2026) — o caso que NÃO EXISTIA antes do F2-27: emitida a NF-e (custo
    já reconhecido, ativo zerado) mas a provisão ainda não paga (passivo aberto). Antes do F2-27
    isto era impossível (reconhecimento e pagamento aconteciam na MESMA chamada); agora é a janela
    mais comum do ciclo. margem_projetada tem que ler o ATIVO (zerado → nada a projetar), nunca
    o saldo de provisão aberto (que seguiria de pé, e duplicaria o custo se fosse descontado)."""
    db = app_db.get_session(); mc.seed_plano(db, "loja", 28)
    mc.registrar_evento(db, "loja", 28, "registro_venda_contrato", 10000.0, projeto_id="P", ref="v:P")
    mc.constituir_provisoes_fechamento(db, "loja", 28, "P", {"montagem": 1000.0}, ref_base="pf:P")
    mc.registrar_evento(db, "loja", 28, "faturamento", 10000.0, projeto_id="P", ref="fat:P")
    mc.reconhecer_provisoes_segmento(db, "loja", 28, "P", "mercadoria", 100.0, ref_base="rec:P")
    r = mc.margem_projeto(db, "loja", 28, "P")
    ativo_id = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=28, codigo="1.1.06.02").first().id
    assert mc.saldo_conta(db, "loja", 28, ativo_id) == 0.0        # ativo zerado — tudo reconhecido
    assert r["saldo_provisao_aberto"] == 1000.0                   # passivo intacto — nada pago ainda
    assert r["margem_contribuicao"] == 9000.0
    assert r["margem_projetada"] == 9000.0                        # sem duplo-conto — a bug que o ACHADO-60 fechou
    db.close()


def test_margem_projeto_simulada_competencia_estimada(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 24)
    mc.registrar_evento(db, "loja", 24, "registro_venda_contrato", 10000.0, projeto_id="P", ref="v:P")
    mc.constituir_provisoes_fechamento(db, "loja", 24, "P", {"montagem": 1000.0, "com_medidor": 200.0},
                                       ref_base="pf:P")
    mc.registrar_evento(db, "loja", 24, "faturamento", 10000.0, projeto_id="P", ref="fat:P")
    real = mc.margem_projeto(db, "loja", 24, "P")
    assert real["margem_contribuicao"] == 10000.0   # nada efetivado ainda
    sim = mc.margem_projeto_simulada(db, "loja", 24, "P", "competencia_estimada")
    assert sim["modo"] == "competencia_estimada"
    assert sim["receita"] == 10000.0
    assert sim["prov_montagem"] == 1000.0
    assert sim["comissao"] == 200.0
    assert sim["margem_contribuicao"] == 8800.0   # 10000 - 1000 - 200
    db.close()


def test_margem_projeto_simulada_antecipacao_contrato(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 25)
    mc.registrar_evento(db, "loja", 25, "registro_venda_contrato", 10000.0, projeto_id="P", ref="v:P")
    mc.constituir_provisoes_fechamento(db, "loja", 25, "P", {"garantia": 300.0}, ref_base="pf:P")
    sim = mc.margem_projeto_simulada(db, "loja", 25, "P", "antecipacao_contrato")
    assert sim["receita"] == 10000.0   # Val_Cont, mesmo sem NF-e ainda
    assert sim["prov_garantia"] == 300.0
    assert sim["margem_contribuicao"] == 9700.0
    db.close()


def test_margem_projeto_simulada_modo_invalido(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 26)
    try:
        mc.margem_projeto_simulada(db, "loja", 26, "P", "xpto")
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass
    db.close()


def test_margem_isola_por_projeto(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 21)
    mc.registrar_evento(db, "loja", 21, "faturamento", 500.0, projeto_id="X")
    mc.registrar_evento(db, "loja", 21, "faturamento", 200.0, projeto_id="Y")
    rx = mc.margem_projeto(db, "loja", 21, "X")
    ry = mc.margem_projeto(db, "loja", 21, "Y")
    todos = mc.margem_todos_projetos(db, "loja", 21)
    db.close()
    assert rx["receita"] == 500.0 and ry["receita"] == 200.0
    assert [t["projeto_id"] for t in todos] == ["X", "Y"]   # ordenado por margem desc
    assert mc.projetos_com_lancamento.__name__            # existe
