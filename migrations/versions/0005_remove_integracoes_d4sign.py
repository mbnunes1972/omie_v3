"""Remove a tabela orfa integracoes_d4sign.

Revisao 0005 — segunda migration de schema do Orizon One.

Origem: TAREFA_ALINHAR_MODELOS.md, T-E. Residuo da "Faxina D4Sign
(2026-08-12)", que removeu as colunas d4sign_* de contratos/aprovacoes_pe
(ver as ALTER TABLE ... DROP COLUMN em database.py, _migrar_colunas_pg) mas
deixou a tabela integracoes_d4sign pra tras. Sem model em database.py, sem
nenhuma referencia funcional no codigo (so comentarios historicos em
integracoes/clicksign_config.py e clicksign_client.py mencionando o antigo
d4sign_client.py/d4sign_config.py).

Tinha 1 linha (id=1, loja_id=1, ambiente_ativo='sandbox', criada em
2026-08-11) no momento desta migration — dado real, nao vazio. Removida
porque a tarefa confirmou a tabela orfa e autorizou o drop; ha backup
completo do banco em docs/db/backup/dados_local_2026-08-27.sql se essa
linha precisar ser recuperada.

Revision ID: 0005
Revises: 0004
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_integracoes_d4sign_loja_id"), table_name="integracoes_d4sign")
    op.drop_index(op.f("ix_integracoes_d4sign_rede_id"), table_name="integracoes_d4sign")
    op.drop_table("integracoes_d4sign")


def downgrade() -> None:
    # Recria a estrutura da tabela — o conteudo (a 1 linha que existia) NAO volta;
    # restaurar dado e responsabilidade de quem rodar o downgrade (ver backup no
    # docstring acima).
    op.create_table(
        "integracoes_d4sign",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("loja_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("rede_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("token_sandbox_enc", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("token_producao_enc", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("cryptkey_sandbox_enc", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("cryptkey_producao_enc", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("safe_uuid_sandbox", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("safe_uuid_producao", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("webhook_secret_enc", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("ambiente_ativo", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("criado_em", postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.Column("atualizado_em", postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(["loja_id"], ["lojas.id"], name=op.f("integracoes_d4sign_loja_id_fkey")),
        sa.ForeignKeyConstraint(["rede_id"], ["redes.id"], name=op.f("integracoes_d4sign_rede_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("integracoes_d4sign_pkey")),
    )
    op.create_index(op.f("ix_integracoes_d4sign_rede_id"), "integracoes_d4sign", ["rede_id"], unique=False)
    op.create_index(op.f("ix_integracoes_d4sign_loja_id"), "integracoes_d4sign", ["loja_id"], unique=False)
