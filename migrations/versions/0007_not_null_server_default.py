"""Aperta NOT NULL nas 12 colunas restantes da lista de 14 (item 2 do
relatorio de alinhamento de modelos, 27/08/2026) — as outras 2
(assistencia_caso.forma_pagamento, ciclo_etapas.transferencia_status) ja
foram fechadas na 0006 porque tambem mudavam de tipo.

Mesma causa-raiz de sempre: o modelo sempre declarou `nullable=False`,
`_migrar_colunas_pg` so faz ADD COLUMN e nunca aplicou a trava no banco.
Todas as 12 tem server_default no banco e zero linhas NULL hoje (checado
por query direta antes de escrever esta migration) — seguro fechar.

  acordo_fabrica.contraparte_tipo       VARCHAR(10)
  conversa_mensagens.natureza           VARCHAR(20)
  conversa_mensagens.bloqueador         INTEGER
  conversa_mensagens.privada            INTEGER
  conversa_participantes.origem         VARCHAR(8)
  conversa_participantes.removido       INTEGER
  conversas.tipo                        VARCHAR(20)
  conversas.assunto_tipo                VARCHAR(12)
  conversas.urgente                     INTEGER
  conversas.status                      VARCHAR(12)
  lojas.tipo                            VARCHAR(12)
  parcela_ambiente.valor_ambiente       FLOAT

parcela_ambiente.valor_ambiente merece nota a parte: e coluna de valor, nao
de estado — o server_default 0.0 nao e um "estado inicial neutro" como os
outros 11, e um preenchimento silencioso. main.py (linhas ~6957 e ~7034,
caminho de desmembramento de parcela) cria ParcelaAmbiente sem nunca passar
valor_ambiente, contando inteiramente no default. mod_retido.py e o unico
lugar que define o valor explicitamente, e ainda tem leituras defensivas
`m.valor_ambiente or 0.0` (linhas ~224-225, ~366) pra esse mesmo motivo.
Isso ja e o comportamento hoje, sem NOT NULL — travar so torna explicito
o que o banco ja fazia por default; nao muda nenhum caminho de insercao
existente. Reportado como achado, nao corrigido aqui.

Revision ID: 0007
Revises: 0006
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUNAS = [
    ("acordo_fabrica",         "contraparte_tipo", sa.VARCHAR(length=10), "fabrica"),
    ("conversa_mensagens",     "natureza",          sa.VARCHAR(length=20), "interacao"),
    ("conversa_mensagens",     "bloqueador",        sa.Integer(),          "0"),
    ("conversa_mensagens",     "privada",           sa.Integer(),          "0"),
    ("conversa_participantes", "origem",            sa.VARCHAR(length=8),  "manual"),
    ("conversa_participantes", "removido",          sa.Integer(),          "0"),
    ("conversas",              "tipo",              sa.VARCHAR(length=20), "projeto"),
    ("conversas",              "assunto_tipo",      sa.VARCHAR(length=12), "livre"),
    ("conversas",              "urgente",           sa.Integer(),          "0"),
    ("conversas",              "status",            sa.VARCHAR(length=12), "aberta"),
    ("lojas",                  "tipo",              sa.VARCHAR(length=12), "loja"),
    ("parcela_ambiente",       "valor_ambiente",    sa.Float(),            "0.0"),
]


def upgrade() -> None:
    for table, column, tipo, default in _COLUNAS:
        op.alter_column(table, column, existing_type=tipo,
                         nullable=False, existing_server_default=default)


def downgrade() -> None:
    for table, column, tipo, default in reversed(_COLUNAS):
        op.alter_column(table, column, existing_type=tipo,
                         nullable=True, existing_server_default=default)
