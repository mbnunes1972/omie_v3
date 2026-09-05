# -*- coding: utf-8 -*-
"""Centro de Custo/Natureza (decisão do usuário, 2026-08-08), Passo 1: migrar_centro_custo_natureza_v1
faz os ajustes pontuais no Plano de Contas ANTES da classificação — renomeia 5.2.06, unifica
5.3.10 em 5.2.06, remove/inativa 5.2.11+5.3.10+5.3.20, cria 5.4.19/5.4.20. Idempotente.

5.2.11/5.3.10/5.3.20 saíram de PLANO_PADRAO nesta mesma mudança — um owner novo (seed_plano puro)
nunca as tem. Os testes que exercitam remoção/unificação simulam um owner PRÉ-EXISTENTE (base
anterior a esta migração), no mesmo espírito de _base_geracao_s108 em test_plano_formalismo.py."""
import mod_contabil as mc


def _contas(db, ot, oid):
    return {c.codigo: c for c in db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}


def _add_legado(db, ot, oid, codigo, nome, pai_codigo):
    pai = _contas(db, ot, oid)[pai_codigo]
    c = mc.Conta(owner_tipo=ot, owner_id=oid, codigo=codigo, nome=nome, grupo=5,
                 tipo="analitica", natureza="devedora", pai_id=pai.id, ativa=1, ordem=990)
    db.add(c); db.commit()
    return c


def _base_pre_migracao(db, ot, oid):
    """Simula o estado de um owner ANTES desta migração: 5.2.06/5.1.01/etc com nome antigo,
    5.2.11/5.3.10/5.3.20 existentes, 5.4.19/5.4.20 ainda não existem."""
    mc.seed_plano(db, ot, oid)
    contas = _contas(db, ot, oid)
    contas["5.2.06"].nome = "Combustível de Depósito"
    contas["5.1.01"].nome = "CMV Fábrica (Dal Mobile)"
    db.delete(contas["5.4.19"]); db.delete(contas["5.4.20"])
    db.commit()
    _add_legado(db, ot, oid, "5.2.11", "Viagens de Supervisão", "5.2")
    _add_legado(db, ot, oid, "5.3.10", "Combustível de Venda", "5.3")
    _add_legado(db, ot, oid, "5.3.20", "Retenção de Comissão de Vendas", "5.3")


def test_renomeia_combustivel_e_cria_contas_novas(app_db):
    db = app_db.get_session(); ot, oid = "loja", 960
    _base_pre_migracao(db, ot, oid)
    out = mc.migrar_centro_custo_natureza_v1(db)
    assert out["renomeadas"] >= 2 and out["criadas"] == 2
    contas = _contas(db, ot, oid)
    assert contas["5.2.06"].nome == "Combustível"
    assert contas["5.1.01"].nome == "CMV Fábrica"
    assert contas["5.4.19"].nome == "Licenças Promob e Sketchup"
    assert contas["5.4.20"].nome == "Outras Despesas"
    db.close()


def test_unifica_combustivel_movendo_lancamentos(app_db):
    db = app_db.get_session(); ot, oid = "loja", 961
    _base_pre_migracao(db, ot, oid)
    contas = _contas(db, ot, oid)
    caixa = contas["1.1.01"]
    mc.lancar(db, ot, oid, contas["5.3.10"].id, caixa.id, 150.0, historico="combustível venda")
    out = mc.migrar_centro_custo_natureza_v1(db)
    assert out["combustivel_unificado"] == 1
    contas2 = _contas(db, ot, oid)
    assert "5.3.10" not in contas2                        # sem lançamento remanescente -> apagada
    assert abs(mc.saldo_conta(db, ot, oid, contas2["5.2.06"].id) - 150.0) < 0.01
    db.close()


def test_remove_ou_inativa_as_tres_contas(app_db):
    db = app_db.get_session(); ot, oid = "loja", 962
    _base_pre_migracao(db, ot, oid)
    contas = _contas(db, ot, oid)
    caixa = contas["1.1.01"]
    # 5.3.20 recebe um lançamento manual -> não pode ser apagada, só inativada
    mc.lancar(db, ot, oid, contas["5.3.20"].id, caixa.id, 80.0, historico="retenção manual")
    out = mc.migrar_centro_custo_natureza_v1(db)
    assert out["removidas"] >= 1 and out["inativadas"] >= 1
    contas2 = _contas(db, ot, oid)
    assert "5.2.11" not in contas2                          # sem lançamento -> apagada
    assert "5.3.10" not in contas2                          # sem lançamento -> apagada
    assert "5.3.20" in contas2 and contas2["5.3.20"].ativa == 0   # com lançamento -> inativada
    db.close()


def test_migracao_idempotente(app_db):
    """A migração roda em TODOS os owners a cada chamada — outro teste do módulo pode deixar um
    owner com conta permanentemente inativada (sem lançamento pra apagar), então o dict de
    contagem GLOBAL não zera sozinho numa 2ª chamada (residual de outro owner, não regressão
    deste). O que importa pra idempotência é o estado DESTE owner não mudar mais."""
    db = app_db.get_session(); ot, oid = "loja", 963
    _base_pre_migracao(db, ot, oid)
    out1 = mc.migrar_centro_custo_natureza_v1(db)
    assert any(out1.values())
    estado1 = {c.codigo: (c.nome, c.ativa) for c in _contas(db, ot, oid).values()}
    mc.migrar_centro_custo_natureza_v1(db)
    estado2 = {c.codigo: (c.nome, c.ativa) for c in _contas(db, ot, oid).values()}
    assert estado1 == estado2
    db.close()


def test_preserva_nome_customizado(app_db):
    db = app_db.get_session(); ot, oid = "loja", 964
    _base_pre_migracao(db, ot, oid)
    c = _contas(db, ot, oid)["5.2.06"]
    c.nome = "Combustível da Frota"
    db.commit()
    mc.migrar_centro_custo_natureza_v1(db)
    c2 = _contas(db, ot, oid)["5.2.06"]
    assert c2.nome == "Combustível da Frota"          # não sobrescreve nome customizado
    db.close()


# ── migrar_centro_custo_natureza_v2 (Frente 4, spec 2026-08-25: 5.4.18 perde "veículos") ────────
def test_migrar_centro_custo_natureza_v2_renomeia_5418(app_db):
    db = app_db.get_session(); ot, oid = "loja", 970
    mc.seed_plano(db, ot, oid)
    c = _contas(db, ot, oid)["5.4.18"]
    c.nome = "Manutenção (loja, veículos, informática)"   # simula estado pré-Frente 4
    db.commit()
    out = mc.migrar_centro_custo_natureza_v2(db)
    assert out["renomeadas"] >= 1
    assert _contas(db, ot, oid)["5.4.18"].nome == "Manutenção (loja e informática)"
    db.close()


def test_migrar_centro_custo_natureza_v2_preserva_nome_customizado(app_db):
    db = app_db.get_session(); ot, oid = "loja", 971
    mc.seed_plano(db, ot, oid)
    c = _contas(db, ot, oid)["5.4.18"]
    c.nome = "Manutenção Predial e TI"   # já renomeada manualmente pelo lojista
    db.commit()
    mc.migrar_centro_custo_natureza_v2(db)
    assert _contas(db, ot, oid)["5.4.18"].nome == "Manutenção Predial e TI"
    db.close()


def test_migrar_centro_custo_natureza_v2_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 972
    mc.seed_plano(db, ot, oid)
    c = _contas(db, ot, oid)["5.4.18"]
    c.nome = "Manutenção (loja, veículos, informática)"
    db.commit()
    out1 = mc.migrar_centro_custo_natureza_v2(db)
    assert out1["renomeadas"] >= 1
    out2 = mc.migrar_centro_custo_natureza_v2(db)
    assert out2["renomeadas"] == 0
    db.close()


def test_seed_plano_novo_owner_ja_nasce_com_nome_novo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 973
    mc.seed_plano(db, ot, oid)
    assert _contas(db, ot, oid)["5.4.18"].nome == "Manutenção (loja e informática)"
    db.close()


def test_evento_retencao_debita_5301_apos_migracao(app_db):
    """A provisão de Retenção de Comissão de Vendas efetiva sem erro mesmo depois que 5.3.20
    some do plano — o evento foi redirecionado pra 5.3.01 Comissão de Vendedor."""
    db = app_db.get_session(); ot, oid = "loja", 965
    mc.seed_plano(db, ot, oid)
    mc.migrar_centro_custo_natureza_v1(db)
    contas = _contas(db, ot, oid)
    assert "5.3.20" not in contas
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"retencao_com_vendas": 500.0}, ref_base="pf:P")
    lan = mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.12", 500.0, ref="ef:retencao")
    assert lan is not None
    assert mc.saldo_conta(db, ot, oid, contas["5.3.01"].id) == 500.0
    db.close()


# ── Centro de Custo: seed + CRUD ──────────────────────────────────────────────────────────────
def _ccs(db, ot, oid):
    return {c.codigo: c for c in db.query(mc.CentroCusto).filter_by(owner_tipo=ot, owner_id=oid).all()}


def test_seed_centro_custo_cria_arvore_padrao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 970
    criados = mc.seed_centro_custo(db, ot, oid)
    assert criados == len(mc.CENTRO_CUSTO_PADRAO)
    ccs = _ccs(db, ot, oid)
    assert ccs["1"].nome == "Operacional" and ccs["1.3"].nome == "Montagem"
    assert ccs["1.3"].pai_id == ccs["1"].id
    # idempotente: 2ª chamada não cria nada
    assert mc.seed_centro_custo(db, ot, oid) == 0
    db.close()


def test_listar_centros_custo_monta_arvore(app_db):
    db = app_db.get_session(); ot, oid = "loja", 971
    raizes = mc.listar_centros_custo(db, ot, oid)
    operacional = next(r for r in raizes if r["codigo"] == "1")
    # T3 (27/08/2026): "Produção própria" (1.1) saiu da semente — a 0004 já a removeu do banco.
    assert {f["nome"] for f in operacional["filhos"]} == {
        "Fábricas e Fornecedores", "Montagem", "Logística/Expedição",
        "Instalações/Infraestrutura"}
    db.close()


# ── migrar_centro_custo_v2 (ajuste do usuário, 2026-08-08: Produtivo->Operacional, Instalações ──
# entra em Operacional, Projetos/Design entra em Pós-venda) — simula owner na árvore ANTERIOR.
def _base_pre_v2(db, ot, oid):
    """Simula o estado ANTERIOR a esta migração: 'Produtivo' (não 'Operacional'), Instalações/
    Infraestrutura ainda em 4.1 (Suporte), Projetos/Design ainda em 2.2 (Comercial) — "1.5"/"3.2"
    (posições NOVAS) ainda não existem nessa base."""
    mc.seed_centro_custo(db, ot, oid)
    ccs = _ccs(db, ot, oid)
    ccs["1"].nome = "Produtivo"
    db.delete(ccs["1.5"]); db.delete(ccs["3.2"])
    db.commit()
    ccs = _ccs(db, ot, oid)
    inst = mc.CentroCusto(owner_tipo=ot, owner_id=oid, codigo="4.1", nome="Instalações/Infraestrutura",
                          pai_id=ccs["4"].id, ativo=1, ordem=990)
    proj = mc.CentroCusto(owner_tipo=ot, owner_id=oid, codigo="2.2", nome="Projetos/Design",
                          pai_id=ccs["2"].id, ativo=1, ordem=991)
    db.add(inst); db.add(proj); db.commit()
    return inst.id, proj.id


def test_migrar_centro_custo_v2_renomeia_e_move(app_db):
    db = app_db.get_session(); ot, oid = "loja", 975
    inst_id, proj_id = _base_pre_v2(db, ot, oid)
    out = mc.migrar_centro_custo_v2(db)
    assert out["renomeados"] == 1 and out["movidos"] == 2
    ccs = _ccs(db, ot, oid)
    assert ccs["1"].nome == "Operacional"
    assert "4.1" not in ccs and "2.2" not in ccs
    assert ccs["1.5"].id == inst_id and ccs["1.5"].pai_id == ccs["1"].id
    assert ccs["3.2"].id == proj_id and ccs["3.2"].pai_id == ccs["3"].id
    db.close()


def test_migrar_centro_custo_v2_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 976
    _base_pre_v2(db, ot, oid)
    mc.migrar_centro_custo_v2(db)
    out2 = mc.migrar_centro_custo_v2(db)
    assert out2 == {"renomeados": 0, "movidos": 0}
    db.close()


def test_migrar_centro_custo_v2_preserva_id_pra_conta_ja_classificada(app_db):
    """O vínculo Conta.centro_custo_id sobrevive à migração — o nó MOVE, não é recriado."""
    db = app_db.get_session(); ot, oid = "loja", 977
    mc.seed_plano(db, ot, oid)
    inst_id, _ = _base_pre_v2(db, ot, oid)
    conta = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="5.4.01").first()
    conta.centro_custo_id = inst_id
    db.commit()
    mc.migrar_centro_custo_v2(db)
    conta2 = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="5.4.01").first()
    assert conta2.centro_custo_id == inst_id
    novo = db.get(mc.CentroCusto, inst_id)
    assert novo.codigo == "1.5"
    db.close()


def test_crud_centro_custo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 972
    mc.seed_centro_custo(db, ot, oid)
    pai = _ccs(db, ot, oid)["2.1"]
    novo = mc.criar_centro_custo(db, ot, oid, pai.id, "Loja Centro")
    assert novo["codigo"] == "2.1.1" and novo["nome"] == "Loja Centro"
    editado = mc.editar_centro_custo(db, ot, oid, novo["id"], nome="Loja Centro Renomeada")
    assert editado["nome"] == "Loja Centro Renomeada"
    out = mc.remover_centro_custo(db, ot, oid, novo["id"])
    assert out["acao"] == "apagado"                    # folha sem uso -> apaga de fato
    assert novo["id"] not in {c.id for c in db.query(mc.CentroCusto).filter_by(owner_tipo=ot, owner_id=oid).all()}
    db.close()


def test_remover_centro_custo_com_conta_apontando_so_inativa(app_db):
    db = app_db.get_session(); ot, oid = "loja", 973
    mc.seed_plano(db, ot, oid)
    mc.seed_centro_custo(db, ot, oid)
    cc = _ccs(db, ot, oid)["1.3"]                        # Montagem
    conta = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="5.2.01").first()
    conta.centro_custo_id = cc.id
    db.commit()
    out = mc.remover_centro_custo(db, ot, oid, cc.id)
    assert out["acao"] == "inativado"
    cc2 = db.get(mc.CentroCusto, cc.id)
    assert cc2 is not None and cc2.ativo == 0
    db.close()


def test_remover_centro_custo_com_filho_so_inativa(app_db):
    db = app_db.get_session(); ot, oid = "loja", 974
    mc.seed_centro_custo(db, ot, oid)
    ccs = _ccs(db, ot, oid)
    out = mc.remover_centro_custo(db, ot, oid, ccs["1"].id)   # tem filhos (1.2..1.5)
    assert out["acao"] == "inativado"
    db.close()


# ── T4 (27/08/2026, revisão do banco): código protegido nunca apaga de verdade ──────────────────
def test_remover_centro_custo_protegido_so_inativa_mesmo_childless_e_sem_uso(app_db):
    """"1.3" (Montagem) é resolvido por CÓDIGO por migrar_classificacao_grupo5_v1 — mesmo um owner
    NOVO, sem conta nenhuma classificada nele ainda (childless, sem uso — o caso que normalmente
    apagaria de verdade), não pode perder o nó, senão a automação futura fica sem destino."""
    db = app_db.get_session(); ot, oid = "loja", 975
    mc.seed_centro_custo(db, ot, oid)   # sem seed_plano/v1 — "1.3" garantidamente childless e sem uso
    cc = _ccs(db, ot, oid)["1.3"]
    out = mc.remover_centro_custo(db, ot, oid, cc.id)
    assert out["acao"] == "inativado" and out["protegido"] is True
    cc2 = db.get(mc.CentroCusto, cc.id)
    assert cc2 is not None and cc2.ativo == 0   # nó sobrevive, só inativado
    db.close()


def test_serial_centro_custo_marca_protegido(app_db):
    db = app_db.get_session(); ot, oid = "loja", 976
    mc.seed_centro_custo(db, ot, oid)
    ccs = _ccs(db, ot, oid)
    assert mc._serial_cc(ccs["1.3"])["protegido"] is True    # usado por CLASSIFICACAO_GRUPO5_V1
    # "1" é grupo (nó-pai "Operacional"), não é código-folha — CLASSIFICACAO_GRUPO5_V1 só mapeia
    # pra folhas, então nenhum grupo de topo é protegido.
    assert mc._serial_cc(ccs["1"])["protegido"] is False
    db.close()


# ── Centro de Custo: endpoints HTTP ───────────────────────────────────────────────────────────
def _find(nodes, codigo):
    for n in nodes:
        if n["codigo"] == codigo:
            return n
        f = _find(n["filhos"], codigo)
        if f:
            return f
    return None


def test_endpoints_centro_custo_crud(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/centro-custo")
    assert st == 200 and d["ok"]
    montagem = _find(d["centros_custo"], "1.3")
    assert montagem["nome"] == "Montagem"

    st2, d2 = c.post("/api/financeiro/centro-custo", {"pai_id": montagem["id"], "nome": "Terceirizada"})
    assert st2 == 201 and d2["centro_custo"]["nome"] == "Terceirizada"
    novo_id = d2["centro_custo"]["id"]

    st3, d3 = c.put(f"/api/financeiro/centro-custo/{novo_id}", {"nome": "Montagem Terceirizada"})
    assert st3 == 200 and d3["centro_custo"]["nome"] == "Montagem Terceirizada"

    st4, d4 = c.post(f"/api/financeiro/centro-custo/{novo_id}/remover", {})
    assert st4 == 200 and d4["acao"] == "apagado"


# ── classificar_contas_lote (endpoint pronto, ainda não chamado por nenhum fluxo automático) ───
def test_classificar_lote_aplica_centro_custo_e_natureza(app_db):
    db = app_db.get_session(); ot, oid = "loja", 980
    mc.seed_plano(db, ot, oid)
    mc.seed_centro_custo(db, ot, oid)
    out = mc.classificar_contas_lote(db, ot, oid, [
        {"codigo": "5.2.01", "centro_custo_codigo": "1.3", "natureza_custo": "variavel"},
        {"codigo": "5.4.01", "centro_custo_codigo": "1.5", "natureza_custo": "fixo"},
    ])
    assert out["classificadas"] == 2
    contas = _contas(db, ot, oid)
    cc_montagem = _ccs(db, ot, oid)["1.3"]
    assert contas["5.2.01"].centro_custo_id == cc_montagem.id
    assert contas["5.2.01"].natureza_custo == "variavel"
    assert contas["5.4.01"].natureza_custo == "fixo"
    db.close()


def test_classificar_lote_limpa_com_valor_vazio(app_db):
    db = app_db.get_session(); ot, oid = "loja", 981
    mc.seed_plano(db, ot, oid)
    mc.seed_centro_custo(db, ot, oid)
    mc.classificar_contas_lote(db, ot, oid, [
        {"codigo": "5.2.01", "centro_custo_codigo": "1.3", "natureza_custo": "variavel"}])
    mc.classificar_contas_lote(db, ot, oid, [
        {"codigo": "5.2.01", "centro_custo_codigo": "", "natureza_custo": ""}])
    conta = _contas(db, ot, oid)["5.2.01"]
    assert conta.centro_custo_id is None and conta.natureza_custo is None
    db.close()


def test_classificar_lote_valida_tudo_antes_de_gravar(app_db):
    """Uma linha ruim no meio do lote não deixa a classificação pela metade (tudo ou nada)."""
    db = app_db.get_session(); ot, oid = "loja", 982
    mc.seed_plano(db, ot, oid)
    mc.seed_centro_custo(db, ot, oid)
    import pytest
    with pytest.raises(ValueError):
        mc.classificar_contas_lote(db, ot, oid, [
            {"codigo": "5.2.01", "centro_custo_codigo": "1.3", "natureza_custo": "variavel"},
            {"codigo": "5.4.01", "centro_custo_codigo": "9.9", "natureza_custo": "fixo"},  # cc inexistente
        ])
    conta = _contas(db, ot, oid)["5.2.01"]
    assert conta.centro_custo_id is None                  # 1º item NÃO ficou meio-aplicado
    with pytest.raises(ValueError):
        mc.classificar_contas_lote(db, ot, oid, [{"codigo": "9.9.9", "centro_custo_codigo": "1.3"}])
    with pytest.raises(ValueError):
        mc.classificar_contas_lote(db, ot, oid, [
            {"codigo": "5.2.01", "natureza_custo": "invalida"}])
    db.close()


# ── migrar_classificacao_grupo5_v1 (aprovada por Marcelo e Juliana, 2026-08-08) ─────────────────
def test_migracao_classificacao_grupo5_preenche_conforme_a_tabela(app_db):
    db = app_db.get_session(); ot, oid = "loja", 990
    mc.seed_plano(db, ot, oid); mc.seed_centro_custo(db, ot, oid)
    # a migração roda em TODOS os owners — outros testes do módulo já deixaram owners com
    # contas grupo 5 pendentes de classificar, então o contador GLOBAL não é 60 (mesma pegadinha
    # já resolvida em test_migracao_idempotente pra migrar_centro_custo_natureza_v1). O que
    # importa é o estado DESTE owner (990), checado direto abaixo.
    out = mc.migrar_classificacao_grupo5_v1(db)
    assert out["centro_custo_setado"] >= 60 and out["natureza_setado"] >= 60
    contas = _contas(db, ot, oid); ccs = _ccs(db, ot, oid)
    todas_g5 = [c for cod, c in contas.items() if cod in mc.CLASSIFICACAO_GRUPO5_V1]
    assert len(todas_g5) == 60   # 59 + "5.7.01 Despesa de Conciliação" (F2-27)
    assert all(c.centro_custo_id is not None and c.natureza_custo is not None for c in todas_g5)
    montagem = contas["5.2.01"]
    assert montagem.centro_custo_id == ccs["1.3"].id and montagem.natureza_custo == "variavel"
    aluguel = contas["5.4.01"]
    assert aluguel.centro_custo_id == ccs["1.5"].id and aluguel.natureza_custo == "fixo"
    db.close()


def test_migracao_classificacao_grupo5_nao_sobrescreve_classificacao_manual(app_db):
    db = app_db.get_session(); ot, oid = "loja", 991
    mc.seed_plano(db, ot, oid); mc.seed_centro_custo(db, ot, oid)
    contas = _contas(db, ot, oid); ccs = _ccs(db, ot, oid)
    # classifica manualmente 5.2.01 num centro DIFERENTE do que a tabela padrão diria (1.3)
    contas["5.2.01"].centro_custo_id = ccs["4.4"].id
    contas["5.2.01"].natureza_custo = "fixo"
    db.commit()
    mc.migrar_classificacao_grupo5_v1(db)
    conta = _contas(db, ot, oid)["5.2.01"]
    assert conta.centro_custo_id == ccs["4.4"].id and conta.natureza_custo == "fixo"   # intocado
    db.close()


def test_migracao_classificacao_grupo5_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 992
    mc.seed_plano(db, ot, oid); mc.seed_centro_custo(db, ot, oid)
    mc.migrar_classificacao_grupo5_v1(db)
    out2 = mc.migrar_classificacao_grupo5_v1(db)
    assert out2 == {"centro_custo_setado": 0, "natureza_setado": 0}
    db.close()


# ── migrar_classificacao_grupo5_v2/v3 (correções pontuais de 2026-08-08 e 2026-08-15) ──────────
# Saíram do boot em 2026-08-25 (Frente 1) e foram apagadas em 27/08/2026 (T2 do briefing de
# revisão do banco): já tinham cumprido o papel em todos os ambientes, e a semente
# (CLASSIFICACAO_GRUPO5_V1/PLANO_PADRAO) nasce direto com os valores finais que elas corrigiam.
# Os testes que só exercitavam essas duas funções foram removidos junto.


# ── Frente 1 (spec 2026-08-25): v2/v3 saíram do BOOT — teste obrigatório da spec ────────────────
def test_boot_pos_frente1_nao_reverte_reclassificacao_manual_pro_default_antigo(app_db):
    """Reproduz o cenário de risco descrito na spec: v2/v3 detectavam "ainda no default antigo"
    PELO VALOR, não pela origem — reclassificar Combustível de volta pra "variavel" (o que v3
    corrigia) seria revertido em silêncio no próximo boot. Com v2/v3 fora do boot (só
    migrar_classificacao_grupo5_v1 roda mais — ver main.py), a escolha manual sobrevive."""
    db = app_db.get_session(); ot, oid = "loja", 999
    mc.seed_plano(db, ot, oid); mc.seed_centro_custo(db, ot, oid)
    mc.migrar_classificacao_grupo5_v1(db)   # 1º "boot": Combustível nasce Fixo (mapa já corrigido)
    assert _contas(db, ot, oid)["5.2.06"].natureza_custo == "fixo"

    # decisão manual legítima: reclassifica de volta pro valor que v3 costumava "corrigir"
    contas = _contas(db, ot, oid)
    contas["5.2.06"].natureza_custo = "variavel"
    db.commit()

    # "reinicia o servidor" — só a v1 roda mais (v2/v3 aposentadas do boot em main.py)
    mc.migrar_classificacao_grupo5_v1(db)
    assert _contas(db, ot, oid)["5.2.06"].natureza_custo == "variavel"   # sobreviveu
    db.close()


def test_endpoint_classificar_lote(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/contas")
    conta = _find(d["contas"], "5.2.01")
    st2, d2 = c.get("/api/financeiro/centro-custo")
    cc = _find(d2["centros_custo"], "1.3")
    st3, d3 = c.post("/api/financeiro/plano-contas/classificar-lote", {"itens": [
        {"codigo": "5.2.01", "centro_custo_codigo": "1.3", "natureza_custo": "variavel"}]})
    assert st3 == 200 and d3["ok"] and d3["classificadas"] == 1
    st4, d4 = c.get("/api/financeiro/contas")
    conta2 = _find(d4["contas"], "5.2.01")
    assert conta2["id"] == conta["id"]


# ── Frente 3 (spec 2026-08-25, DECIDIDO): botão Editar (PUT) reclassifica ────────────────────────
def test_put_conta_reclassifica_com_autorizacao_e_grava_rastro(http_client_factory, seed, app_db):
    import json
    from database import LogAcaoGerencial
    c = http_client_factory(); c.login("dir_l1", "senha123")   # master: tem aprovar_financeiro
    _, d = c.get("/api/financeiro/contas")
    conta = _find(d["contas"], "5.2.02")
    _, d2 = c.get("/api/financeiro/centro-custo")
    cc = _find(d2["centros_custo"], "3.1")

    st, dr = c.put(f"/api/financeiro/contas/{conta['id']}",
                   {"nome": "Comissão de Vendas", "centro_custo_id": cc["id"], "natureza_custo": "variavel"})
    assert st == 200 and dr["ok"]
    assert dr["conta"]["nome"] == "Comissão de Vendas"
    assert dr["conta"]["centro_custo_id"] == cc["id"] and dr["conta"]["natureza_custo"] == "variavel"

    db = app_db.get_session()
    log = (db.query(LogAcaoGerencial).filter_by(acao="reclassificar_conta")
             .order_by(LogAcaoGerencial.id.desc()).first())
    assert log is not None and json.loads(log.contexto)["codigo"] == conta["codigo"]
    db.close()


def test_put_conta_reclassifica_sem_permissao_403(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("cons_l1", "senha123")   # operador: nem passa exige_edicao
    st, d = c.get("/api/financeiro/contas")   # cons_l1 sem acesso financeiro -> 403 já aqui é aceitável
    # tenta direto a reclassificação
    st2, d2 = c.put("/api/financeiro/contas/1", {"centro_custo_id": 1, "natureza_custo": "fixo"})
    assert st2 == 403


def test_put_conta_nao_limpa_classificacao_grupo5_400(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.get("/api/financeiro/contas")
    conta = _find(d["contas"], "5.2.03")
    _, d2 = c.get("/api/financeiro/centro-custo")
    cc = _find(d2["centros_custo"], "1.3")
    c.put(f"/api/financeiro/contas/{conta['id']}", {"centro_custo_id": cc["id"], "natureza_custo": "fixo"})

    st, dr = c.put(f"/api/financeiro/contas/{conta['id']}", {"centro_custo_id": None, "natureza_custo": "fixo"})
    assert st == 400


def test_post_conta_grupo5_exige_classificacao(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.get("/api/financeiro/contas")
    despesas_adm = _find(d["contas"], "5.4")
    _, d2 = c.get("/api/financeiro/centro-custo")
    cc = _find(d2["centros_custo"], "4.3")

    st, dr = c.post("/api/financeiro/contas", {"pai_id": despesas_adm["id"], "nome": "Conta Nova Sem Classe"})
    assert st == 400   # sem centro_custo_id/natureza_custo

    st2, dr2 = c.post("/api/financeiro/contas", {"pai_id": despesas_adm["id"], "nome": "Conta Nova Classificada",
                                                 "centro_custo_id": cc["id"], "natureza_custo": "fixo"})
    assert st2 == 201 and dr2["conta"]["centro_custo_id"] == cc["id"]
