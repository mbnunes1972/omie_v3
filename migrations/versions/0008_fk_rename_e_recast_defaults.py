"""Renomeia uma FK orfa e reemite 3 server_default com cast desatualizado —
achados da comparacao constraint-a-constraint entre o localhost e a baseline
gerada do zero (revisao B1/B2 de 27/08/2026).

CAT 2 — FK orfa (segundo caso real que justifica a R1, ver CLAUDE.md)
conversa_mensagens.documento_ref_id tinha a FK nomeada fk_convmsg_documento_ref
no banco, sem o modelo declarar esse nome. Veio do `_migrar_colunas_pg` (DO-block
com ADD CONSTRAINT nomeado, ver database.py) — funcao congelada pela R1, nunca
replicada pro modelo. A baseline gerada do zero produz o nome padrao do Postgres
(conversa_mensagens_documento_ref_id_fkey), porque o modelo nao declara `name=`.
Renomeado aqui pra alinhar o localhost ao que a baseline gera.

CAT 3 — cast do DEFAULT desatualizado apos o ALTER COLUMN TYPE da 0006
`ALTER COLUMN ... TYPE` no Postgres nao recasta o literal de um DEFAULT ja
existente — so' um DEFAULT novo (CREATE TABLE do zero, ou um SET DEFAULT
explicito) usa o cast do tipo atual. As 3 colunas abaixo tiveram o tipo
alterado pela 0006 (varchar -> text) e ficaram com o DEFAULT ainda castado
pro tipo antigo:

  assistencia_caso.forma_pagamento       'direto'::character varying -> 'direto'::text
  ciclo_etapas.transferencia_status      'nenhuma'::character varying -> 'nenhuma'::text
  parcela_ambiente.valor_ambiente        0.0 (sem cast)               -> '0'::double precision

parcela_ambiente.valor_ambiente nao teve o tipo alterado (sempre foi Float) —
o cast dela diverge porque o DEFAULT original veio de uma ALTER TABLE ADD
COLUMN do _migrar_colunas_pg com um literal numerico puro, enquanto o
SET DEFAULT emitido aqui usa a mesma forma (string) que o modelo declara
(server_default="0.0"), igual ao que uma baseline nova produziria.

Revision ID: 0008
Revises: 0007
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE conversa_mensagens "
        "RENAME CONSTRAINT fk_convmsg_documento_ref "
        "TO conversa_mensagens_documento_ref_id_fkey"
    )
    op.alter_column("assistencia_caso", "forma_pagamento",
                     existing_type=sa.Text(), server_default="direto",
                     existing_nullable=False)
    op.alter_column("ciclo_etapas", "transferencia_status",
                     existing_type=sa.Text(), server_default="nenhuma",
                     existing_nullable=False)
    op.alter_column("parcela_ambiente", "valor_ambiente",
                     existing_type=sa.Float(), server_default="0.0",
                     existing_nullable=False)


def downgrade() -> None:
    op.alter_column("parcela_ambiente", "valor_ambiente",
                     existing_type=sa.Float(), server_default=sa.text("0.0"),
                     existing_nullable=False)
    op.alter_column("ciclo_etapas", "transferencia_status",
                     existing_type=sa.Text(), server_default=sa.text("'nenhuma'::character varying"),
                     existing_nullable=False)
    op.alter_column("assistencia_caso", "forma_pagamento",
                     existing_type=sa.Text(), server_default=sa.text("'direto'::character varying"),
                     existing_nullable=False)
    op.execute(
        "ALTER TABLE conversa_mensagens "
        "RENAME CONSTRAINT conversa_mensagens_documento_ref_id_fkey "
        "TO fk_convmsg_documento_ref"
    )
