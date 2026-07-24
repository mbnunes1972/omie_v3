import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database
from auth import perfil_store


from conftest import _test_database_url, _reset_schema_pg


def _eng_pg():
    """Engine no Postgres de teste com schema recém-criado (herdeiro do sqlite :memory:)."""
    eng = create_engine(_test_database_url())
    _reset_schema_pg(eng)
    database.Base.metadata.create_all(eng)
    return eng

def _sess():
    S = sessionmaker(bind=_eng_pg())
    db = S()
    db.add(database.Loja(id=1, nome="L1"))
    db.add(database.Loja(id=2, nome="L2"))
    db.commit()
    return db


def test_seed_cria_3_perfis_por_loja():
    db = _sess()
    perfil_store.seed_perfis_loja(db, 1)
    perfil_store.seed_perfis_loja(db, 2)
    p1 = db.query(database.PerfilAcesso).filter_by(loja_id=1).all()
    assert {p.slug for p in p1} == {"master", "gerencial", "operador"}
    assert all(p.sistema == 1 for p in p1)
    master = next(p for p in p1 if p.slug == "master")
    mods = set(json.loads(master.modulos_json))
    assert {"admin", "config", "financeiro", "fiscal"} <= mods
    operador = next(p for p in p1 if p.slug == "operador")
    omods = set(json.loads(operador.modulos_json))
    assert "fiscal" not in omods and "financeiro" not in omods and "admin" not in omods   # 2026-07-24


def test_seed_idempotente():
    db = _sess()
    perfil_store.seed_perfis_loja(db, 1)
    perfil_store.seed_perfis_loja(db, 1)
    assert db.query(database.PerfilAcesso).filter_by(loja_id=1).count() == 3


def test_titulos_padronizados_e_backfill_gerente():
    """Padronização 2026-07-22: seed nasce com 'Gerente' (slug 'gerencial' NÃO muda) e o
    backfill renomeia bases antigas — sem sobrescrever nome customizado no painel."""
    db = _sess()
    perfil_store.seed_perfis_loja(db, 1)
    g = db.query(database.PerfilAcesso).filter_by(loja_id=1, slug="gerencial").first()
    assert g.nome == "Gerente"
    # base antiga: volta o nome velho e cria loja 2 sem seed nenhum
    g.nome = "Gerencial"
    db.commit()
    out = perfil_store.backfill_perfis_todas_lojas(db)
    assert out["renomeados"] == 1 and out["criados"] == 3     # loja 2 ganhou o seed
    assert db.query(database.PerfilAcesso).filter_by(loja_id=1, slug="gerencial").first().nome == "Gerente"
    # nome customizado é preservado
    g2 = db.query(database.PerfilAcesso).filter_by(loja_id=2, slug="gerencial").first()
    g2.nome = "Gestor da Casa"
    db.commit()
    perfil_store.backfill_perfis_todas_lojas(db)
    assert db.query(database.PerfilAcesso).filter_by(loja_id=2, slug="gerencial").first().nome == "Gestor da Casa"
