"""Guarda contra 'constraint sumiu em silencio' — achado real do baseline Alembic
(revisao 27/08/2026): use_alter=True dentro de um op.create_table() gerado por
autogenerate faz a FK desaparecer do CREATE TABLE, mas o autogenerate NAO gera
nenhum op.create_foreign_key() complementar pra recria-la depois. `alembic upgrade`
roda sem erro; a constraint simplesmente nao existe no banco resultante — nada
quebra ate alguem depender dela em producao.

Este teste roda contra o schema criado por init_db() (create_all, que resolve
use_alter corretamente ao contrario do autogenerate) — o valor dele nao e' pegar
ESTE bug especifico de novo, e' fechar a classe inteira: qualquer FK ou UNIQUE
declarado no modelo que nao vire constraint de verdade no banco, seja qual for a
causa (migration gerada errada, ALTER manual esquecido, o que for), aparece aqui
como falha de teste em vez de surpresa em producao.
"""

from sqlalchemy import inspect, UniqueConstraint


def _fks_do_modelo(table):
    fks = set()
    for fkc in table.foreign_key_constraints:
        cols = tuple(sorted(c.name for c in fkc.columns))
        ref_table = fkc.elements[0].column.table.name
        ref_cols = tuple(sorted(e.column.name for e in fkc.elements))
        fks.add((cols, ref_table, ref_cols))
    return fks


def _fks_do_banco(insp, table_name):
    fks = set()
    for fk in insp.get_foreign_keys(table_name):
        cols = tuple(sorted(fk["constrained_columns"]))
        ref_cols = tuple(sorted(fk["referred_columns"]))
        fks.add((cols, fk["referred_table"], ref_cols))
    return fks


def _unicos_do_modelo(table):
    unicos = set()
    for c in table.constraints:
        if isinstance(c, UniqueConstraint):
            unicos.add(tuple(sorted(col.name for col in c.columns)))
    for idx in table.indexes:
        if idx.unique:
            unicos.add(tuple(sorted(col.name for col in idx.columns)))
    return unicos


def _unicos_do_banco(insp, table_name):
    unicos = set()
    for uc in insp.get_unique_constraints(table_name):
        unicos.add(tuple(sorted(uc["column_names"])))
    for idx in insp.get_indexes(table_name):
        if idx.get("unique"):
            unicos.add(tuple(sorted(idx["column_names"])))
    return unicos


def test_todas_fks_do_modelo_existem_no_banco(app_db):
    insp = inspect(app_db.ENGINE)
    metadata = app_db.Base.metadata

    faltando = []
    for table_name, table in metadata.tables.items():
        ausentes = _fks_do_modelo(table) - _fks_do_banco(insp, table_name)
        for cols, ref_table, ref_cols in ausentes:
            faltando.append(f"{table_name}{cols} -> {ref_table}{ref_cols}")

    assert not faltando, (
        "FK declarada no modelo mas ausente no banco (constraint sumiu em silencio):\n"
        + "\n".join(sorted(faltando))
    )


def test_todos_unicos_do_modelo_existem_no_banco(app_db):
    insp = inspect(app_db.ENGINE)
    metadata = app_db.Base.metadata

    faltando = []
    for table_name, table in metadata.tables.items():
        ausentes = _unicos_do_modelo(table) - _unicos_do_banco(insp, table_name)
        for cols in ausentes:
            faltando.append(f"{table_name}{cols}")

    assert not faltando, (
        "UNIQUE (constraint ou indice) declarado no modelo mas ausente no banco:\n"
        + "\n".join(sorted(faltando))
    )
