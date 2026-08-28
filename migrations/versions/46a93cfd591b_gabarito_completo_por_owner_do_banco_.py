"""gabarito completo por owner do banco, nao lista fixa

`c1ab3f8007c4` conhece 3 owners fixos (rede,1 / loja,1 / loja,3) — os do localhost. Medido nos
servidores em 28/08/2026 (nenhum tem Alembic ainda):

    ambiente        owners
    localhost       rede,1 loja,1 loja,3
    integracao      loja,1                       (so' UM owner)
    homologacao     rede,1/15/16 loja,1/29..34    (10 owners, ids bem diferentes)

Owner e' polimorfico (`owner_tipo`+`owner_id`, sem FK) — nada impede a `c1ab3f8007c4` de gravar
`(rede,1)`/`(loja,3)` na Integracao mesmo esses owners NAO existindo la', e de deixar de fora os
8 owners reais da Homologacao que nao sao nenhum dos 3 fixos. `alembic upgrade head` rodaria sem
erro nos dois ambientes e produziria um banco ERRADO em silencio — o oposto do que a baseline se
propos a resolver.

Nao mexe na `c1ab3f8007c4` (ja aplicada no localhost, downgrade la' e' irreversivel de proposito)
— esta e' uma migration NOVA que substitui a enumeracao fixa por derivacao do proprio banco: para
CADA linha de `redes` e CADA linha de `lojas` do ambiente onde ela roda, garante o gabarito
completo (arvore de centro de custo + plano de contas + classificacao do grupo 5). Sem id
numerico de owner no codigo — os ids vem de uma query, nunca de uma constante.

Chama `mod_contabil.aplicar_gabarito_completo`, a MESMA funcao que `POST /api/admin/lojas`/
`.../pdvs` chamam na criacao de uma loja (docs/db/TAREFA_CENTRO_CUSTO_2.md item 2) — uma
implementacao so', dois pontos de entrada (a migration cobre quem ja existe; a criacao de loja
cobre quem nasce depois). A Session e' presa na MESMA conexao do Alembic (`Session(bind=
op.get_bind())`), nunca uma engine propria: `context.begin_transaction()` (`migrations/env.py`)
envolve a cadeia inteira numa unica transacao, entao uma conexao separada nem enxergaria o
schema que a baseline acabou de criar (DDL/DML nao commitado e' invisivel fora da transacao que
o fez — foi exatamente o erro "relation redes does not exist" da 1a versao desta migration,
tentando abrir uma engine propria via `database.get_session()`). A funcao do gabarito chama
`db.commit()` por dentro (idempotente por natural key, mesma regra de `seed_plano`/
`seed_centro_custo`) — na MESMA conexao, isso so' fecha e reabre a transacao do Alembic (SQLAlchemy
2.x autobegin), sem indisponibilizar o restante da cadeia.

No localhost, os 3 owners ja tem o gabarito completo — esta migration nao muda nada la' (mesmo
criterio de sempre: zero diferencas contra o localhost, tests/test_centro_custo_plano_contas_
migration.py). Na Integracao ela semeia so' loja,1. Na Homologacao, os 10 owners reais, cada um
pelo seu proprio id.

Revision ID: 46a93cfd591b
Revises: ecc77df9ca32
Create Date: 2026-08-28 01:20:10.145947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46a93cfd591b'
down_revision: Union[str, Sequence[str], None] = 'ecc77df9ca32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy.orm import Session as _Session
    import database as db
    import mod_contabil as mc

    # Session presa na MESMA conexao/transacao do Alembic (op.get_bind()) -- nao uma engine
    # propria: `context.begin_transaction()` (migrations/env.py) envolve a cadeia inteira numa
    # unica transacao, entao uma conexao separada nao enxergaria nem o schema que a propria
    # baseline acabou de criar (DDL nao commitado e' invisivel fora da transacao que o fez).
    session = _Session(bind=op.get_bind())
    try:
        redes = [r.id for r in session.query(db.Rede).all()]
        lojas = [l.id for l in session.query(db.Loja).all()]
        for rede_id in redes:
            mc.aplicar_gabarito_completo(session, "rede", rede_id)
        for loja_id in lojas:
            mc.aplicar_gabarito_completo(session, "loja", loja_id)
    finally:
        session.close()


def downgrade() -> None:
    """Nao reversivel de forma util — mesma razao da `c1ab3f8007c4`/`ecc77df9ca32`: o gabarito
    aplicado aqui pode ja ter Lancamento apontando pra ele (bloqueando qualquer DELETE por
    ondelete=RESTRICT), e a funcao de gabarito e' condicional ("so' preenche o que faltar"), entao
    upgrade() nao guarda o que cada owner tinha antes pra restaurar."""
