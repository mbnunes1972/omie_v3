"""Renomeia 5.6.10 e remove o centro de custo Producao Propria.

Revisao 0004 — primeira migration de DADOS do Orizon One.

Decisoes de 27/08/2026:

  5.6.10  "Ajuste de Provisoes" -> "Ajustes de Reconciliacao"
          A variancia de provisao passa a lancar na conta da propria despesa
          que ela corrige, nao numa conta de passagem. Esta conta sobrevive
          apenas para diferenca sem origem identificavel (arredondamento,
          ajuste de fechamento) e nunca deve ser destino padrao.

  1.1     "Producao propria" sai da arvore de centro de custo.
          Zero contas vinculadas; nem toda loja tera producao propria, e
          quando tiver recria pela tela com suas contas de materia-prima.

O que esta migration NAO faz, de proposito: as reclassificacoes de Brindes,
Ajuste de Provisoes e Combustivel ja estao corretas no banco, aplicadas pelo
bootstrap. O que falta ali e CODIGO — corrigir a semente em mod_contabil.py e
remover as tres linhas de correcao pontual (~895-923), no mesmo commit.
Semear e codigo; corrigir e migration.

Sobre o downgrade: recriar um no apagado nunca restaura o id original. Se
alguma conta voltar a apontar para Producao Propria, o vinculo precisara ser
refeito a mao. Como o no esta hoje sem nenhuma conta, isso e teorico.

Revision ID: 0004
Revises: 0003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOME_NOVO = "Ajustes de Reconciliação"
NOME_ANTIGO = "Ajuste de Provisões"
CODIGO_PP = "1.1"
NOME_PP = "Produção própria"


def upgrade() -> None:
    bind = op.get_bind()

    renomeadas = bind.execute(
        sa.text("UPDATE conta SET nome = :novo, atualizado_em = now() "
                "WHERE codigo = '5.6.10'"),
        {"novo": NOME_NOVO},
    ).rowcount
    print(f"  0004: {renomeadas} contas 5.6.10 renomeadas")

    # a FK fk_conta_centro_custo_id ja barraria, mas uma mensagem clara vale
    # mais que um erro de constraint no meio de um deploy
    em_uso = bind.execute(sa.text("""
        SELECT count(*) FROM conta c
        JOIN centro_custo cc ON cc.id = c.centro_custo_id
        WHERE cc.codigo = :cod
    """), {"cod": CODIGO_PP}).scalar()
    if em_uso:
        raise RuntimeError(
            f"{em_uso} conta(s) ainda apontam para o centro de custo {CODIGO_PP}. "
            "Reclassifique-as antes de aplicar a 0004."
        )

    filhos = bind.execute(sa.text("""
        SELECT count(*) FROM centro_custo f
        JOIN centro_custo p ON p.id = f.pai_id
        WHERE p.codigo = :cod
    """), {"cod": CODIGO_PP}).scalar()
    if filhos:
        raise RuntimeError(
            f"O centro de custo {CODIGO_PP} tem {filhos} filho(s). "
            "Remova-os antes de aplicar a 0004."
        )

    removidos = bind.execute(
        sa.text("DELETE FROM centro_custo WHERE codigo = :cod"), {"cod": CODIGO_PP}
    ).rowcount
    print(f"  0004: {removidos} nos '{NOME_PP}' removidos")


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(sa.text("""
        INSERT INTO centro_custo (owner_tipo, owner_id, codigo, nome, pai_id,
                                  ativo, ordem, criado_em, atualizado_em)
        SELECT op.owner_tipo, op.owner_id, :cod, :nome, op.id,
               COALESCE((SELECT irmao.ativo FROM centro_custo irmao
                         WHERE irmao.pai_id = op.id ORDER BY irmao.codigo LIMIT 1), 1),
               1, now(), now()
        FROM centro_custo op
        WHERE op.codigo = '1'
          AND NOT EXISTS (SELECT 1 FROM centro_custo x
                          WHERE x.owner_tipo = op.owner_tipo
                            AND x.owner_id = op.owner_id
                            AND x.codigo = :cod)
    """), {"cod": CODIGO_PP, "nome": NOME_PP})

    bind.execute(
        sa.text("UPDATE conta SET nome = :antigo, atualizado_em = now() "
                "WHERE codigo = '5.6.10'"),
        {"antigo": NOME_ANTIGO},
    )
