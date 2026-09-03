"""adicional (fixo + comissao) no cadastro do funcionario — ACHADO-47

docs/db/ACHADOS_CONTABEIS.md, ACHADO-47 (DECIDIDO 02/09): sem papel avulso no funcionário — o
acúmulo de papéis se paga por um bloco Adicional no cadastro, não por uma segunda função.
Quatro colunas novas em `funcionarios`:
  - adicional_fixo (valor mensal)
  - adicional_comissao_pct (percentual — só válido quando a função primária já é comissionada,
    guarda no servidor, não só na tela)
  - adicional_comissao_base (base declarada; única suportada por ora: 'val_liq_venda')
  - adicional_obs (um só campo de observações, serve aos dois adicionais)

Revision ID: 82275b998a4a
Revises: f47f22de46a7
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82275b998a4a'
down_revision: Union[str, Sequence[str], None] = 'f47f22de46a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('funcionarios', sa.Column('adicional_fixo', sa.Float(), nullable=True))
    op.add_column('funcionarios', sa.Column('adicional_comissao_pct', sa.Float(), nullable=True))
    op.add_column('funcionarios', sa.Column('adicional_comissao_base', sa.String(length=20), nullable=True))
    op.add_column('funcionarios', sa.Column('adicional_obs', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('funcionarios', 'adicional_obs')
    op.drop_column('funcionarios', 'adicional_comissao_base')
    op.drop_column('funcionarios', 'adicional_comissao_pct')
    op.drop_column('funcionarios', 'adicional_fixo')
