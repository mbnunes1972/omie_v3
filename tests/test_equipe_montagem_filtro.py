# -*- coding: utf-8 -*-
"""Equipe — seletor de Montagem filtrado por função (feedback do teste, 2026-07-26).

A "Equipe de Montagem" deve ofertar só funcionários MONTADOR ou AJUDANTE DE MONTAGEM (o
Supervisor já é papel próprio); antes listava TODOS os funcionários da loja. Terceiros
(mão de obra terceirizada) seguem candidatos. A função "Ajudante de Montagem" passa a existir
no catálogo padrão e é semeada em todas as lojas por backfill idempotente."""
import mod_equipe


def _mk_func(db, app_db, loja_id, pessoa, funcao_nome):
    fn = db.query(app_db.Funcao).filter_by(loja_id=loja_id, nome=funcao_nome).first()
    if fn is None:
        fn = app_db.Funcao(loja_id=loja_id, nome=funcao_nome, status="ativo")
        db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja_id, nome=pessoa, funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    return f


def test_ajudante_de_montagem_no_catalogo():
    import database
    assert "Ajudante de Montagem" in database.FUNCOES_PADRAO


def test_candidatos_montagem_so_montador_e_ajudante(app_db, seed):
    db = app_db.get_session()
    L = seed["loja1_id"]
    _mk_func(db, app_db, L, "Montador Um", "Montador")
    _mk_func(db, app_db, L, "Ajudante Um", "Ajudante de Montagem")
    _mk_func(db, app_db, L, "Consultor NaoEntra", "Consultor de Vendas")
    _mk_func(db, app_db, L, "Supervisor NaoEntra", "Supervisor de Montagem")
    db.commit()

    out = mod_equipe.candidatos_montagem(db, L)
    nomes = {p["nome"] for p in out["funcionarios"]}
    assert "Montador Um" in nomes and "Ajudante Um" in nomes
    assert "Consultor NaoEntra" not in nomes           # função fora do escopo de montagem
    assert "Supervisor NaoEntra" not in nomes          # supervisor é papel próprio
    db.close()


def test_candidatos_geral_continua_com_todos(app_db, seed):
    """O candidatos() dos OUTROS seletores (medidor/finalizador) não muda — só o de montagem
    é restrito."""
    db = app_db.get_session()
    L = seed["loja1_id"]
    _mk_func(db, app_db, L, "Alguem Qualquer", "Assistente Administrativo")
    db.commit()
    geral = {p["nome"] for p in mod_equipe.candidatos(db, L)["funcionarios"]}
    assert "Alguem Qualquer" in geral                  # geral inclui todos
    montagem = {p["nome"] for p in mod_equipe.candidatos_montagem(db, L)["funcionarios"]}
    assert "Alguem Qualquer" not in montagem           # montagem, não
    db.close()


def test_backfill_semeia_ajudante_em_loja_existente(app_db, seed):
    """Loja 2 (sem funcionários de montagem criados por outros testes) — simula base anterior
    ao catálogo novo removendo a função e provando que o backfill a recria."""
    import database
    db = app_db.get_session()
    L = seed["loja2_id"]
    aj = db.query(database.Funcao).filter_by(loja_id=L, nome="Ajudante de Montagem").first()
    if aj:
        db.delete(aj); db.commit()
    assert db.query(database.Funcao).filter_by(loja_id=L, nome="Ajudante de Montagem").first() is None
    n = database.backfill_funcoes_todas_lojas(db)
    assert n >= 1
    assert db.query(database.Funcao).filter_by(loja_id=L, nome="Ajudante de Montagem").first() is not None
    # idempotente: após semear tudo que faltava, nada novo
    assert database.backfill_funcoes_todas_lojas(db) == 0
    db.close()
