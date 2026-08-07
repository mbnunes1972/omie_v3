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
    """2026-08-07 (achado do usuário): margem_contribuicao só reflete o que já foi EFETIVADO — um
    projeto recém-faturado com provisão ainda toda em aberto aparece com margem quase cheia.
    saldo_provisao_aberto + margem_projetada dão o quadro completo (realizado × pior caso)."""
    db = app_db.get_session(); mc.seed_plano(db, "loja", 22)
    mc.registrar_evento(db, "loja", 22, "registro_venda_contrato", 10000.0, projeto_id="P", ref="v:P")
    mc.constituir_provisoes_fechamento(db, "loja", 22, "P", {"montagem": 1000.0}, ref_base="pf:P")
    mc.registrar_evento(db, "loja", 22, "faturamento", 10000.0, projeto_id="P", ref="fat:P")
    # nada efetivado ainda: margem_contribuicao "cheia", mas saldo_provisao_aberto expõe o risco
    r0 = mc.margem_projeto(db, "loja", 22, "P")
    assert r0["margem_contribuicao"] == 10000.0
    assert r0["saldo_provisao_aberto"] == 1000.0
    assert r0["margem_projetada"] == 9000.0     # pior caso: se gastar toda a provisão pendente
    # efetiva parte (400 de 1000): margem_contribuicao cai (despesa real reconhecida), saldo_aberto reduz
    mc.efetivar_provisao(db, "loja", 22, "P", "2.1.04.02", 400.0, ref="ef:P")
    r1 = mc.margem_projeto(db, "loja", 22, "P")
    assert r1["margem_contribuicao"] == 9600.0    # 10000 - 400 (montagem, já vira despesa real)
    assert r1["saldo_provisao_aberto"] == 600.0
    assert r1["margem_projetada"] == 9000.0       # realizado + o que falta = sempre o mesmo pior caso
    db.close()


def test_margem_projetada_nao_soma_excedente_ja_refletido(app_db):
    """Se o custo real já superou o provisionado, saldo_provisao_aberto fica NEGATIVO — o excesso já
    está em margem_contribuicao (despesa real, reconhecida na efetivação); margem_projetada não deve
    descontar de novo (senão contaria o excesso duas vezes)."""
    db = app_db.get_session(); mc.seed_plano(db, "loja", 23)
    mc.registrar_evento(db, "loja", 23, "registro_venda_contrato", 10000.0, projeto_id="P", ref="v:P")
    mc.constituir_provisoes_fechamento(db, "loja", 23, "P", {"montagem": 1000.0}, ref_base="pf:P")
    mc.registrar_evento(db, "loja", 23, "faturamento", 10000.0, projeto_id="P", ref="fat:P")
    mc.efetivar_provisao(db, "loja", 23, "P", "2.1.04.02", 1200.0, ref="ef:P")   # custo real > provisão
    r = mc.margem_projeto(db, "loja", 23, "P")
    assert r["saldo_provisao_aberto"] == -200.0
    assert r["margem_contribuicao"] == 8800.0     # 10000 - 1200 (despesa real, já reflete o excesso)
    assert r["margem_projetada"] == 8800.0        # == margem_contribuicao (nada mais a descontar)
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
