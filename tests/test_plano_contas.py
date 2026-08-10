import mod_contabil as mc


def test_seed_idempotente_e_grupos(app_db):
    db = app_db.get_session()
    n1 = mc.seed_plano(db, "loja", 1)   # materializa
    n2 = mc.seed_plano(db, "loja", 1)   # 2ª vez não duplica
    contas = mc.listar_contas(db, "loja", 1)   # árvore (raízes)
    db.close()
    assert n1 > 60 and n2 == 0
    raizes = [c["codigo"] for c in contas]
    assert raizes == ["1", "2", "3", "4", "5"]           # 5 grupos, ordenados
    assert contas[0]["nome"].upper().startswith("ATIVO")


def test_natureza_por_grupo_e_tipo(app_db):
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 1)
    plano = {c.codigo: c for c in db.query(app_db.Conta)
             .filter_by(owner_tipo="loja", owner_id=1).all()}
    db.close()
    assert plano["1"].natureza == "devedora" and plano["5"].natureza == "devedora"
    assert plano["2"].natureza == "credora" and plano["4"].natureza == "credora"
    assert plano["5"].tipo == "sintetica"                 # tem filhos
    assert plano["5.4.01"].tipo == "analitica"            # folha (Aluguel)
    assert plano["5.4.01"].nome == "Aluguel"


def test_resolver_owner_avulsa_e_rede_admin(app_db):
    db = app_db.get_session()
    # loja inexistente (avulsa, sem rede) -> owner é a própria loja
    assert mc.resolver_owner(db, {"loja_id": 1, "rede_id": None}) == ("loja", 1)
    # usuário admin de rede (sem loja) -> owner é a rede
    assert mc.resolver_owner(db, {"loja_id": None, "rede_id": 7}) == ("rede", 7)
    db.close()


def test_resolver_owner_loja_com_rede(seed, app_db):
    db = app_db.get_session()
    # Corte S187 (achado do usuário — "cada loja tem vida própria"): loja de rede tem razão
    # PRÓPRIO, nunca mais compartilhado com as lojas-irmãs.
    assert mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None}) == ("loja", seed["loja1_id"])
    assert mc.resolver_owner(db, {"loja_id": seed["loja2_id"], "rede_id": None}) == ("loja", seed["loja2_id"])
    db.close()


def test_criar_filho_torna_pai_sintetica(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    aluguel = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5.4.01").first()
    assert aluguel.tipo == "analitica"
    nova = mc.criar_conta(db, "loja", 1, pai_id=aluguel.id, nome="Aluguel Matriz")
    db.refresh(aluguel)
    assert aluguel.tipo == "sintetica"                    # virou pai
    assert nova["codigo"].startswith("5.4.01.") and nova["grupo"] == 5
    assert nova["natureza"] == "devedora" and nova["tipo"] == "analitica"
    db.close()


def test_editar_renomeia(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    c = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5.4.05").first()
    r = mc.editar_conta(db, "loja", 1, c.id, nome="Contabilidade e Auditoria")
    db.refresh(c); assert c.nome == "Contabilidade e Auditoria" and r["nome"] == c.nome
    db.close()


def test_remover_folha_apaga_pai_inativa(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    folha = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5.4.18").first()
    r1 = mc.remover_conta(db, "loja", 1, folha.id)
    assert r1["acao"] == "apagada"
    assert db.get(app_db.Conta, folha.id) is None
    grupo5 = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5").first()
    r2 = mc.remover_conta(db, "loja", 1, grupo5.id)        # tem filhos -> inativa
    db.refresh(grupo5)
    assert r2["acao"] == "inativada" and grupo5.ativa == 0
    db.close()


def test_remover_ultimo_filho_reverte_pai_a_analitica(app_db):
    """Achado ao apagar contas de teste do Fluxo de Caixa: criar_conta() promove o pai (ex.: "1.1.01"
    Caixa/Bancos) a sintética; se o único filho depois é apagado, o pai tinha ficado preso sintética
    e vazio — sem poder receber lançamento de novo até alguém recriar um filho."""
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    caixa = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="1.1.01").first()
    banco = mc.criar_conta(db, "loja", 1, pai_id=caixa.id, nome="Banco Itaú")
    db.refresh(caixa)
    assert caixa.tipo == "sintetica"
    r = mc.remover_conta(db, "loja", 1, banco["id"])
    assert r["acao"] == "apagada"
    db.refresh(caixa)
    assert caixa.tipo == "analitica"                      # reverteu — volta a aceitar lançamento
    mc.lancar(db, "loja", 1, caixa.id,
              db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="4.1.02").first().id,
              100.0)
    db.close()


def test_cross_owner_barrado(app_db):
    import pytest
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    c = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5").first()
    with pytest.raises(PermissionError):
        mc.editar_conta(db, "loja", 999, c.id, nome="hack")   # owner diferente
    db.close()
