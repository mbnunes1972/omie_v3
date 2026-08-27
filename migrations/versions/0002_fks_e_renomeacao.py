"""FKs faltantes e indices das colunas filhas.

Revisao 0002 — primeira migration de schema do Orizon One.

Origem: auditoria de 27/08/2026. Das 43 colunas *_id sem FK, 23 eram divida
real; 19 tinham zero orfaos e entram aqui. As 4 restantes ficaram de fora:
  - orcamentos.projeto_id            1 orfao real a resolver antes
  - conversa_participantes.lido_ate_mensagem_id   sentinela 0, precisa de
                                     mudanca de codigo antes
  - lancamento.projeto_id            chave natural (nome_safe), vai virar
  - pool_ambientes.projeto_id        projetos_meta_id inteiro na Onda 2

Regras de exclusao escolhidas, nao herdadas: as 171 FKs pre-existentes estao
todas em NO ACTION por default do PostgreSQL. Estas nao repetem isso.
  RESTRICT  relacao de negocio — impede apagar o pai que ainda tem filhos
  SET NULL  autoria/atribuicao — apagar o usuario desamarra o nome, nao
            apaga o historico

Sem NOT VALID e sem CONCURRENTLY de proposito: a maior tabela do banco tem
667 linhas. Essas tecnicas protegem tabelas grandes em producao com carga;
aqui so adicionariam complexidade sem beneficio.

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (filho, coluna, pai, coluna_pai, ondelete)
FKS = [
    # --- relacao de negocio -------------------------------------------------
    ("acordo_fabrica",     "contraparte_id",   "contraparte_financeira", "id", "RESTRICT"),
    ("assistencia_caso",   "pool_ambiente_id", "pool_ambientes",         "id", "RESTRICT"),
    ("conta",              "centro_custo_id",  "centro_custo",           "id", "RESTRICT"),
    ("conversas",          "assunto_id",       "assuntos",               "id", "RESTRICT"),
    ("conversas",          "rede_id",          "redes",                  "id", "RESTRICT"),
    ("envios_externos",    "template_id",      "template_mensagem",      "id", "RESTRICT"),
    ("envios_externos",    "triagem_id",       "triagem_entradas",       "id", "RESTRICT"),
    ("lojas",              "loja_mae_id",      "lojas",                  "id", "RESTRICT"),
    ("orcamentos",         "parcela_id",       "parcela_projeto",        "id", "RESTRICT"),
    # --- autoria e atribuicao -----------------------------------------------
    ("ciclo_etapas",       "responsavel_terceiro_id",                 "terceiros",    "id", "SET NULL"),
    ("ciclo_etapas",       "transferencia_destino_funcionario_id",    "funcionarios", "id", "SET NULL"),
    ("ciclo_etapas",       "transferencia_destino_terceiro_id",       "terceiros",    "id", "SET NULL"),
    ("ciclo_etapas",       "transferencia_solicitada_por_usuario_id", "usuarios",     "id", "SET NULL"),
    ("conversa_mensagens", "destinatario_usuario_id",                 "usuarios",     "id", "SET NULL"),
    ("conversa_mensagens", "transferido_para_funcionario_id",         "funcionarios", "id", "SET NULL"),
    ("conversas",          "concluido_por_id",                        "usuarios",     "id", "SET NULL"),
    ("conversas",          "criado_por_id",                           "usuarios",     "id", "SET NULL"),
    ("conversas",          "responsavel_usuario_id",                  "usuarios",     "id", "SET NULL"),
    ("segmento_config",    "responsavel_funcionario_id",              "funcionarios", "id", "SET NULL"),
]

# Indices polimorficos (owner_tipo, owner_id). So as tabelas que NAO tem
# constraint unica cobrindo essas colunas — conta, centro_custo e
# perfil_emissao ja sao cobertas pelas suas uq_*_owner_*, e criar aqui
# geraria indice duplicado.
IX_OWNER = [
    ("lancamento",       ["owner_tipo", "owner_id"],               "ix_lancamento_owner"),
    ("periodo_contabil", ["owner_tipo", "owner_id"],               "ix_periodo_contabil_owner"),
    ("envios_externos",  ["destinatario_tipo", "destinatario_id"], "ix_envios_externos_destinatario"),
]


def _fk(filho: str, coluna: str) -> str:
    return f"fk_{filho}_{coluna}"


def _ix(tabela: str, coluna: str) -> str:
    return f"ix_{tabela}_{coluna}"


def upgrade() -> None:
    # 1. renomeia a coluna de comportamento de custo, que hoje colide de nome
    #    com conta.natureza (credora/devedora) e confunde quem le o codigo

    # 2. as 19 constraints
    for filho, coluna, pai, pai_col, ondelete in FKS:
        op.create_foreign_key(
            _fk(filho, coluna), filho, pai, [coluna], [pai_col],
            ondelete=ondelete, onupdate="CASCADE",
        )

    # 3. indice na coluna filha de cada FK nova — o PostgreSQL indexa o lado
    #    do pai automaticamente e nunca o do filho
    for filho, coluna, *_ in FKS:
        op.create_index(_ix(filho, coluna), filho, [coluna])

    # 4. indices dos pares polimorficos
    for tabela, colunas, nome in IX_OWNER:
        op.create_index(nome, tabela, colunas)


def downgrade() -> None:
    for tabela, _colunas, nome in IX_OWNER:
        op.drop_index(nome, table_name=tabela)

    for filho, coluna, *_ in FKS:
        op.drop_index(_ix(filho, coluna), table_name=filho)

    for filho, coluna, *_ in FKS:
        op.drop_constraint(_fk(filho, coluna), filho, type_="foreignkey")

