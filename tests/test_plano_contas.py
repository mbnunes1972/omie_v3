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
    # Frente 3 (spec 2026-08-25, DECIDIDO): conta nova em grupo 5 nasce classificada — pai é
    # "5.4.01" (grupo 5), então precisa de centro_custo_id/natureza_custo + autorização.
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1); mc.seed_centro_custo(db, "loja", 1)
    aluguel = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5.4.01").first()
    cc = db.query(app_db.CentroCusto).filter_by(owner_tipo="loja", owner_id=1, codigo="1.5").first()
    assert aluguel.tipo == "analitica"
    nova = mc.criar_conta(db, "loja", 1, pai_id=aluguel.id, nome="Aluguel Matriz",
                          centro_custo_id=cc.id, natureza_custo="fixo",
                          reclassificar_autorizado=True)
    db.refresh(aluguel)
    assert aluguel.tipo == "sintetica"                    # virou pai
    assert nova["codigo"].startswith("5.4.01.") and nova["grupo"] == 5
    assert nova["natureza"] == "devedora" and nova["tipo"] == "analitica"
    assert nova["centro_custo_id"] == cc.id and nova["natureza_custo"] == "fixo"
    db.close()


def test_criar_conta_grupo5_sem_classificacao_400(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 2)
    aluguel = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=2, codigo="5.4.01").first()
    import pytest
    with pytest.raises(ValueError):
        mc.criar_conta(db, "loja", 2, pai_id=aluguel.id, nome="Sem classificação",
                       reclassificar_autorizado=True)   # autorizado mas sem cc/natureza
    db.close()


def test_criar_conta_grupo5_sem_autorizacao_403(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 3); mc.seed_centro_custo(db, "loja", 3)
    aluguel = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=3, codigo="5.4.01").first()
    cc = db.query(app_db.CentroCusto).filter_by(owner_tipo="loja", owner_id=3, codigo="1.5").first()
    import pytest
    with pytest.raises(PermissionError):
        mc.criar_conta(db, "loja", 3, pai_id=aluguel.id, nome="Sem autorização",
                       centro_custo_id=cc.id, natureza_custo="fixo")   # reclassificar_autorizado=False (default)
    db.close()


def test_criar_conta_fora_do_grupo5_nao_exige_classificacao(app_db):
    # backward-compat: grupo 1 nunca exigiu (e continua não exigindo) centro de custo/natureza.
    db = app_db.get_session(); mc.seed_plano(db, "loja", 4)
    caixa = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=4, codigo="1.1.01").first()
    nova = mc.criar_conta(db, "loja", 4, pai_id=caixa.id, nome="Sub-caixa")
    assert nova["grupo"] == 1 and nova["centro_custo_id"] is None
    db.close()


def test_editar_renomeia(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    c = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5.4.05").first()
    r = mc.editar_conta(db, "loja", 1, c.id, nome="Contabilidade e Auditoria")
    db.refresh(c); assert c.nome == "Contabilidade e Auditoria" and r["nome"] == c.nome
    db.close()


# ── Frente 3 (spec 2026-08-25, DECIDIDO): botão Editar reclassifica Centro de Custo/Natureza ────
def test_editar_reclassifica_com_autorizacao(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 5); mc.seed_centro_custo(db, "loja", 5)
    c = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=5, codigo="5.4.05").first()
    cc = db.query(app_db.CentroCusto).filter_by(owner_tipo="loja", owner_id=5, codigo="4.3").first()
    r = mc.editar_conta(db, "loja", 5, c.id, centro_custo_id=cc.id, natureza_custo="fixo",
                        reclassificar_autorizado=True)
    assert r["centro_custo_id"] == cc.id and r["natureza_custo"] == "fixo"
    db.close()


def test_editar_reclassifica_sem_autorizacao_levanta_permission_error(app_db):
    import pytest
    db = app_db.get_session(); mc.seed_plano(db, "loja", 6); mc.seed_centro_custo(db, "loja", 6)
    c = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=6, codigo="5.4.05").first()
    cc = db.query(app_db.CentroCusto).filter_by(owner_tipo="loja", owner_id=6, codigo="4.3").first()
    with pytest.raises(PermissionError):
        mc.editar_conta(db, "loja", 6, c.id, centro_custo_id=cc.id, natureza_custo="fixo")
    db.close()


def test_editar_nao_permite_limpar_classificacao_no_grupo5(app_db):
    """Obrigatoriedade (DECIDIDO): botão Editar não limpa centro_custo/natureza numa conta do
    grupo 5, mesmo autorizado — só classificar_contas_lote (ferramenta administrativa) pode."""
    import pytest
    db = app_db.get_session(); mc.seed_plano(db, "loja", 7); mc.seed_centro_custo(db, "loja", 7)
    c = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=7, codigo="5.4.05").first()
    cc = db.query(app_db.CentroCusto).filter_by(owner_tipo="loja", owner_id=7, codigo="4.3").first()
    mc.editar_conta(db, "loja", 7, c.id, centro_custo_id=cc.id, natureza_custo="fixo",
                    reclassificar_autorizado=True)
    with pytest.raises(ValueError):
        mc.editar_conta(db, "loja", 7, c.id, centro_custo_id=None, natureza_custo="fixo",
                        reclassificar_autorizado=True)
    with pytest.raises(ValueError):
        mc.editar_conta(db, "loja", 7, c.id, centro_custo_id=cc.id, natureza_custo=None,
                        reclassificar_autorizado=True)
    db.close()


def test_editar_renomear_sozinho_nao_exige_autorizacao_de_reclassificar(app_db):
    """Renomear (sem tocar centro_custo_id/natureza_custo) continua com o perfil de sempre —
    reclassificar_autorizado default (False) não bloqueia quem só quer renomear."""
    db = app_db.get_session(); mc.seed_plano(db, "loja", 8)
    c = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=8, codigo="5.4.05").first()
    r = mc.editar_conta(db, "loja", 8, c.id, nome="Novo nome")
    assert r["nome"] == "Novo nome"
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
