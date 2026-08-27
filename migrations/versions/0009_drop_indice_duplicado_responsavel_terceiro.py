"""Remove o indice duplicado ix_ciclo_etapas_responsavel_terceiro.

Mesma classe do achado da 0008 (fk_convmsg_documento_ref): `_migrar_colunas_pg`
tinha `CREATE INDEX IF NOT EXISTS ix_ciclo_etapas_responsavel_terceiro ON
ciclo_etapas (responsavel_terceiro_id)` — nome sem o sufixo `_id`, divergente
do nome padrao que o `index=True` do modelo gera (ix_ciclo_etapas_responsavel_
terceiro_id). Confirmado via pg_index (nao por nome): as duas cobrem a MESMA
coluna (responsavel_terceiro_id) — duplicata de fato, achada por
tests/test_schema_boot_estavel.py comparando `alembic upgrade head` contra
`init_db()`.

Estado hoje difere entre ambientes: o localhost nunca chegou a rodar esse
`_migrar_colunas_pg` especifico (so' tem ix_ciclo_etapas_responsavel_terceiro_id),
mas VPS A/B e producao podem ter os dois, dependendo de quantas vezes o app
reiniciou desde que a entrada foi escrita. DROP INDEX IF EXISTS por isso —
idempotente nos dois casos.

A entrada correspondente saiu de `_migrar_colunas_pg` no MESMO commit desta
migration (ver database.py e CLAUDE.md) — a migration converge os bancos que
ja tem a duplicata, a remocao da entrada impede que ela volte no proximo boot.
Separados, um desfaz o outro.

Revision ID: 0009
Revises: 0008
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ciclo_etapas_responsavel_terceiro")


def downgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ciclo_etapas_responsavel_terceiro "
        "ON ciclo_etapas (responsavel_terceiro_id)"
    )
