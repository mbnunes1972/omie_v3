import pytest
from datetime import datetime

import mod_arvore


@pytest.fixture
def ator_super():
    return {"nivel": "super_admin", "loja_id": None, "rede_id": None}


@pytest.fixture(scope="module")
def rede_id(app_db, seed):
    db = app_db.get_session()
    try:
        return db.get(app_db.Loja, seed["loja1_id"]).rede_id
    finally:
        db.close()


@pytest.fixture(scope="module")
def com_etapas(app_db, seed):
    """Proj_L1 ganha etapas 1,2,3 concluídas e 4 pendente (etapa atual = 4)."""
    from database import CicloEtapa
    db = app_db.get_session()
    try:
        db.add_all([
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="1",
                       status="concluido", concluido_em=datetime(2026, 1, 1)),
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="2",
                       status="concluido", concluido_em=datetime(2026, 1, 2)),
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="3",
                       status="concluido", concluido_em=datetime(2026, 1, 3)),
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="4",
                       status="pendente"),
        ])
        db.commit()
    finally:
        db.close()
    return seed


def test_super_ve_projetos_com_agregacao(app_db, seed, com_etapas, ator_super):
    db = app_db.get_session()
    try:
        out = mod_arvore.projetos_estruturais(db, ator_super, seed["loja1_id"])
    finally:
        db.close()
    p = next(x for x in out if x["nome_safe"] == "Proj_L1")
    assert p["etapas_concluidas"] == 3
    assert p["etapa_atual_codigo"] == "4"
    assert p["etapa_atual_nome"] == "Orçamento"
    # 20 − etapas 5/6 eliminadas + 21 (Conciliação Final, FASE D2) − 8/9 (achado do usuário
    # 2026-08-17: AF1 e Solicitação de Medição saíram dos principais, viraram gatilhos da 7)
    # − 14/15/16 (achado 2026-08-18: grupo "Logística e Expedição", representado por "13").
    assert p["total_etapas"] == 14


def test_super_agrega_grupo_logistica_parcialmente_concluido(app_db, seed, ator_super):
    """Achado do usuário 2026-08-18: "13" (Produção, representante de "Logística e
    Expedição") não pode contar como concluída nem deixar `atual` pular pra "17" enquanto
    14/15/16 ainda estiverem pendentes. Projeto próprio (isolado dos outros testes do
    módulo, que reaproveitam Proj_L1 via a fixture `com_etapas`)."""
    from database import CicloEtapa, Projeto
    nome = "Proj_Grupo_Logistica"
    db = app_db.get_session()
    try:
        if db.get(Projeto, nome) is None:
            db.add(Projeto(nome_safe=nome, loja_id=seed["loja1_id"]))
        db.query(CicloEtapa).filter_by(projeto_nome=nome).delete()
        for cod in ("1", "2", "3", "4", "7", "10", "11", "12", "13"):
            db.add(CicloEtapa(projeto_nome=nome, etapa_codigo=cod, status="concluido"))
        db.add(CicloEtapa(projeto_nome=nome, etapa_codigo="14", status="pendente"))
        db.commit()
    finally:
        db.close()

    db2 = app_db.get_session()
    try:
        out = mod_arvore.projetos_estruturais(db2, ator_super, seed["loja1_id"])
    finally:
        db2.close()
    p = next(x for x in out if x["nome_safe"] == nome)
    # "13" concluída sozinha NÃO conta — 14 ainda pendente, então "atual" continua em "13"
    # (o grupo "Logística e Expedição"), não pula pra "17" (Montagem).
    assert p["etapa_atual_codigo"] == "13"
    assert p["etapa_atual_nome"] == "Produção"
    # concluídas: 1,2,3,4,7,10,11,12 = 8 (NÃO inclui "13", que ainda não fechou o grupo)
    assert p["etapas_concluidas"] == 8


def test_projetos_sem_pii(app_db, seed, com_etapas, ator_super):
    db = app_db.get_session()
    try:
        out = mod_arvore.projetos_estruturais(db, ator_super, seed["loja1_id"])
    finally:
        db.close()
    assert out, "esperava ao menos um projeto"
    assert set(out[0].keys()) == {
        "nome_safe", "status", "etapa_atual_codigo",
        "etapa_atual_nome", "total_etapas", "etapas_concluidas"}


def test_admin_rede_ve_loja_da_propria_rede(app_db, seed, rede_id):
    ator = {"nivel": "admin_rede", "loja_id": None, "rede_id": rede_id}
    db = app_db.get_session()
    try:
        out = mod_arvore.projetos_estruturais(db, ator, seed["loja1_id"])
    finally:
        db.close()
    assert any(x["nome_safe"] == "Proj_L1" for x in out)


def test_loja_inexistente_levanta_lookuperror(app_db, ator_super):
    db = app_db.get_session()
    try:
        with pytest.raises(LookupError):
            mod_arvore.projetos_estruturais(db, ator_super, 999999)
    finally:
        db.close()


def test_fora_de_escopo_levanta_permissionerror(app_db, seed, rede_id):
    ator = {"nivel": "admin_rede", "loja_id": None, "rede_id": rede_id + 999}
    db = app_db.get_session()
    try:
        with pytest.raises(PermissionError):
            mod_arvore.projetos_estruturais(db, ator, seed["loja1_id"])
    finally:
        db.close()


def test_etapas_super_ordenadas_com_nome(app_db, seed, com_etapas, ator_super):
    db = app_db.get_session()
    try:
        out = mod_arvore.etapas_do_projeto(db, ator_super, "Proj_L1")
    finally:
        db.close()
    assert [e["etapa_codigo"] for e in out] == ["1", "2", "3", "4"]
    assert out[0]["etapa_nome"] == "Cadastro do Cliente"
    assert out[3]["status"] == "pendente"
    assert out[0]["concluido_em"].startswith("2026-01-01")


def test_etapas_sem_pii(app_db, seed, com_etapas, ator_super):
    db = app_db.get_session()
    try:
        out = mod_arvore.etapas_do_projeto(db, ator_super, "Proj_L1")
    finally:
        db.close()
    assert out, "esperava etapas"
    assert set(out[0].keys()) == {"etapa_codigo", "etapa_nome", "status", "concluido_em"}


def test_etapas_projeto_inexistente(app_db, ator_super):
    db = app_db.get_session()
    try:
        with pytest.raises(LookupError):
            mod_arvore.etapas_do_projeto(db, ator_super, "NaoExiste")
    finally:
        db.close()


def test_etapas_fora_de_escopo(app_db, seed, rede_id):
    ator = {"nivel": "admin_rede", "loja_id": None, "rede_id": rede_id + 999}
    db = app_db.get_session()
    try:
        with pytest.raises(PermissionError):
            mod_arvore.etapas_do_projeto(db, ator, "Proj_L1")
    finally:
        db.close()
