"""renomeia conta 2.1.05 total flex para parcelamento loja

ACHADO-14 (docs/db/ACHADOS_CONTABEIS.md / docs/db/PLANO_AJUSTES.md): o produto mudou de nome —
"Total Flex" virou "Parcelamento Loja" (mod_fin/__init__.py:98 já mostra o nome novo pro
usuário) — mas o rename nunca alcançou o nome da conta 2.1.05 no `PLANO_PADRAO`
(mod_contabil.py), nem, por consequência, o banco (`seed_plano()` só cria o que falta — R13/R14,
CLAUDE.md). Mesmo padrão de 1.1.09/2.1.09 (`ecc77df9ca32`).

Idêntico em mecanismo à `ecc77df9ca32`: idempotente por chave natural (owner_tipo, owner_id,
codigo), atualiza SÓ onde o valor gravado ainda for o nome antigo específico — nunca "onde
diferir do gabarito atual" (preserva reclassificação manual legítima feita depois). Roda em
TODO owner que já tem `conta`, descoberto em runtime (R15) — sem lista fixa de owners.

Revision ID: 95c7e64afc6a
Revises: 46a93cfd591b
Create Date: 2026-08-29 07:26:43.505764

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95c7e64afc6a'
down_revision: Union[str, Sequence[str], None] = '46a93cfd591b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (codigo, campo, valor_antigo, valor_novo)
CORRECOES = [
    ('2.1.05', 'nome', 'Financiamento Total Flex a Pagar',
     'Financiamento Parcelamento Loja a Pagar'),
]


def upgrade() -> None:
    conn = op.get_bind()

    owners = conn.execute(sa.text(
        "SELECT DISTINCT owner_tipo, owner_id FROM conta"
    )).all()

    for owner_tipo, owner_id in owners:
        for codigo, campo, valor_antigo, valor_novo in CORRECOES:
            atual = conn.execute(sa.text(
                f"SELECT {campo} FROM conta WHERE owner_tipo = :ot AND owner_id = :oid "
                "AND codigo = :codigo"
            ), {"ot": owner_tipo, "oid": owner_id, "codigo": codigo}).scalar_one_or_none()
            if atual == valor_antigo:
                conn.execute(sa.text(
                    f"UPDATE conta SET {campo} = :novo WHERE owner_tipo = :ot AND owner_id = :oid "
                    "AND codigo = :codigo"
                ), {"novo": valor_novo, "ot": owner_tipo, "oid": owner_id, "codigo": codigo})


def downgrade() -> None:
    """Não reversível de forma útil — mesma razão da `ecc77df9ca32`: reverter significaria
    reintroduzir de propósito um nome que o próprio código (`PLANO_PADRAO`) já não reconhece
    mais como correto, e a passada é condicional no valor antigo (rodar upgrade não guarda o
    que cada linha tinha antes de mudar)."""
