"""Amplia varchar(n) para text, aperta NOT NULL onde o modelo ja exigia, e
alinha o server_default de assinatura_canal nas 3 classes.

Revisao 0006 — terceira migration de schema do Orizon One.

Origem: TAREFA_ALINHAR_MODELOS.md, C2/C3 e a revisao de 27/08/2026 (itens 2 e
3 do relatorio de alinhamento de modelos).

C2 — tipo (banco atrasado, modelo ja certo)
_migrar_colunas_pg so faz ADD COLUMN, nunca ALTER COLUMN TYPE — o modelo
avancou pra Text nestas 3 colunas em algum commit passado e o banco ficou
para tras em varchar:

  assistencia_caso.forma_pagamento       varchar     -> text
  assistencia_caso.classificacao_avulsa  varchar     -> text
  ciclo_etapas.transferencia_status      varchar(10) -> text

varchar(n) e text guardam o mesmo dado no PostgreSQL — a unica diferenca e
o limite de comprimento, que nenhuma das 3 usa como regra de negocio
(valores gravados sao slugs curtos como "direto"/"pendente"). Ampliar e
sempre seguro; estreitar exigiria checar o maior valor gravado antes.

NOT NULL (mesma causa-raiz: modelo sempre exigiu, banco nunca aplicou)
De passagem, as 2 colunas acima que TAMBEM estao na lista de 14 do item 2
do relatorio (nullable=False no modelo, nullable no banco, zero linhas NULL
hoje) ganham SET NOT NULL no mesmo alter_column — sem migration separada
pra elas. As outras 12 da lista de 14 vao pra 0007 (nao tem type a mudar,
entao nao ha motivo pra estarem aqui).

C3 — server_default da 3a classe (item 3 do relatorio)
solicitacoes_medicao.assinatura_canal nao tinha o server_default='interno'
que contratos.assinatura_canal e aprovacoes_pe.assinatura_canal ja tem
(esses dois vieram de um ALTER COLUMN direto no banco, fora de migration,
sem rastro em codigo — ver a nota em CLAUDE.md, R1). Aplicado aqui pra
igualar as tres classes: campo igual, comportamento igual.

Revision ID: 0006
Revises: 0005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("assistencia_caso", "forma_pagamento",
                     existing_type=sa.VARCHAR(), type_=sa.Text(),
                     nullable=False, existing_nullable=True,
                     existing_server_default="direto")
    op.alter_column("assistencia_caso", "classificacao_avulsa",
                     existing_type=sa.VARCHAR(), type_=sa.Text(),
                     existing_nullable=True)
    op.alter_column("ciclo_etapas", "transferencia_status",
                     existing_type=sa.VARCHAR(length=10), type_=sa.Text(),
                     nullable=False, existing_nullable=True,
                     existing_server_default="nenhuma")
    op.alter_column("solicitacoes_medicao", "assinatura_canal",
                     existing_type=sa.VARCHAR(length=16),
                     server_default="interno", existing_nullable=True)


def downgrade() -> None:
    op.alter_column("solicitacoes_medicao", "assinatura_canal",
                     existing_type=sa.VARCHAR(length=16),
                     server_default=None, existing_nullable=True)
    # Estreitar de volta pra varchar so e seguro se nenhum valor gravado passar do limite
    # antigo — nao verificado aqui de proposito (downgrade e caminho de emergencia, nao uso
    # normal); rode a checagem manualmente antes de descer esta revisao em producao. NOT NULL
    # tambem volta pra nullable (o dado existente continua sem NULL, so a trava sai).
    op.alter_column("ciclo_etapas", "transferencia_status",
                     existing_type=sa.Text(), type_=sa.VARCHAR(length=10),
                     nullable=True, existing_server_default="nenhuma")
    op.alter_column("assistencia_caso", "classificacao_avulsa",
                     existing_type=sa.Text(), type_=sa.VARCHAR(),
                     existing_nullable=True)
    op.alter_column("assistencia_caso", "forma_pagamento",
                     existing_type=sa.Text(), type_=sa.VARCHAR(),
                     nullable=True, existing_server_default="direto")
