"""aplica decisoes do codigo que nao alcancaram a base existente

`seed_plano()` (mod_contabil.py) so' CRIA os codigos de `PLANO_PADRAO` que ainda faltam num
owner — por desenho, nunca corrige um codigo que ja existe. Toda decisao expressa como edicao
de `PLANO_PADRAO`/`CLASSIFICACAO_GRUPO5_V1` depois que um owner ja foi semeado fica sem efeito
pra ele: o owner novo nasce certo, o owner antigo carrega o valor de quando foi semeado pra
sempre. Foi assim que os 3 casos abaixo divergiram entre o codigo (fonte da verdade) e o banco
(o que `c1ab3f8007c4` reproduziu fielmente do localhost, valor velho incluso):

1) `1.1.09`/`2.1.09`: renomeadas em `PLANO_PADRAO` pelo commit f647b94 (21/07/2026, reforma
   Acordos Financeiros — contraparte generalizada) de "Conta Corrente com Lojas do Grupo (a
   receber/pagar)" pra "Creditos/Debitos com Empresas (conta corrente)". A rede (owner mais
   antigo) ja tinha essas duas contas ANTES do rename e nunca foi atualizada; as lojas foram
   semeadas depois e ja nasceram com o nome novo — por isso a divergencia so aparecia na rede.
   O `CONTA_NOME_OVERRIDE_POR_OWNER_TIPO` da `c1ab3f8007c4` (que aplicava o nome novo so' pra
   loja, preservando o nome velho da rede) vira LETRA MORTA a partir desta revisao: os 3 owners
   passam a ter o mesmo nome (o novo), entao o override nunca mais teria o que fazer. Nao mexe
   em `c1ab3f8007c4` (ja aplicada, downgrade la' e' declaradamente irreversivel) — so' registra
   aqui por que ele deixou de ser necessario.
2) `5.5.05`: `CLASSIFICACAO_GRUPO5_V1` tem `variavel` (decisao Frente 4 #8 — acompanha volume
   de credito concedido) mas nunca teve migracao propria (comentario no proprio dict admite
   isso). O banco (e a `c1ab3f8007c4`) ficou com `fixo`, o valor de antes da decisao.

Idempotente por chave natural (owner_tipo, owner_id, codigo), atualizando SO' onde o valor
gravado ainda for o antigo especifico listado abaixo — nunca "onde diferir do gabarito atual"
(isso reorganizaria por cima de reclassificacao manual legitima feita depois, que nao e' o que
este upgrade se propoe a fazer). Roda em TODO owner que ja tem `conta` na hora do upgrade
(descoberto em runtime, sem id numerico nem lista fixa de owners — um owner futuro que
`seed_plano()`/`migrar_classificacao_grupo5_v1` venham a criar so' teria esses codigos se o
proprio seed ja os semear com o valor ANTIGO, o que nao acontece mais).

CLAUDE.md ganha a regra (junto da de rename, R11): mudanca em `PLANO_PADRAO` ou nas tabelas de
classificacao (`CLASSIFICACAO_GRUPO5_V1` etc.) exige migration de dado no MESMO commit — quem
faz isso valer e' `tests/test_gabarito_migration_x_seed.py`.

Revision ID: ecc77df9ca32
Revises: c1ab3f8007c4
Create Date: 2026-08-28 00:57:08.737418

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ecc77df9ca32'
down_revision: Union[str, Sequence[str], None] = 'c1ab3f8007c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (codigo, campo, valor_antigo, valor_novo)
CORRECOES = [
    ('1.1.09', 'nome', 'Conta Corrente com Lojas do Grupo (a receber)',
     'Créditos com Empresas (conta corrente)'),
    ('2.1.09', 'nome', 'Conta Corrente com Lojas do Grupo (a pagar)',
     'Débitos com Empresas (conta corrente)'),
    ('5.5.05', 'natureza_custo', 'fixo', 'variavel'),
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
    """Nao reversivel de forma util — mesma razao da `c1ab3f8007c4`: reverter significaria
    reintroduzir de proposito um nome/classificacao que o proprio codigo (PLANO_PADRAO /
    CLASSIFICACAO_GRUPO5_V1) ja nao reconhece mais como correto, e a passada e' condicional no
    valor antigo (rodar upgrade nao guarda o que cada linha tinha antes de mudar)."""
