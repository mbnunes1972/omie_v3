"""backfill conta 4.4.05 ajuste retencao financeira

ACHADO-01/02/03 (docs/db/TAREFA_ACHADO02_03.md, passo 10 do ROTEIRO): `PLANO_PADRAO`
(mod_contabil.py) ganhou a conta 4.4.05 "Ajuste de Retenção Financeira" — a variância entre a
retenção esperada (2.1.04.19, ramo financeira) e a real, MESMA conta nos dois sentidos, mesma
regra dos impostos (4.3.01). `seed_plano()` só CRIA os códigos que ainda faltam num owner já
existente — owners semeados antes desta revisão nunca ganhariam a conta nova sozinhos.

Dois passos, mesmo padrão de `46a93cfd591b`/`ecc77df9ca32`:
1) `aplicar_gabarito_completo` (idempotente, só preenche o que falta) para CADA rede e loja
   descobertas do próprio banco — cobre ambientes reais (Integração/Homologação/Produção).
2) INSERT literal de 4.4.05 para os 3 owners fixos históricos (rede,1/loja,1/loja,3) — o
   `orizon_baseline_teste` de `tests/test_gabarito_migration_x_seed.py` não tem dado de
   instância (`redes`/`lojas` nascem vazias), então o passo 1 não os alcança ali; esses 3
   owners vêm inteiramente do histórico congelado em `c1ab3f8007c4`/`ecc77df9ca32`, que este
   passo estende com a conta nova, sem mexer nas duas migrations anteriores.

Revision ID: f47f22de46a7
Revises: e031f6ad9c80
Create Date: 2026-08-31 00:14:06.020962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f47f22de46a7'
down_revision: Union[str, Sequence[str], None] = 'e031f6ad9c80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OWNERS_FIXOS = [("rede", 1), ("loja", 1), ("loja", 3)]


def upgrade() -> None:
    from sqlalchemy.orm import Session as _Session
    import database as db
    import mod_contabil as mc

    conn = op.get_bind()

    # passo 1: ambientes reais — owners descobertos do proprio banco, sem lista fixa.
    # Session presa na MESMA conexao/transacao do Alembic (op.get_bind()) -- mesma razao de
    # 46a93cfd591b (DDL/DML nao commitado e' invisivel fora da transacao que o fez).
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

    # passo 2: os 3 owners fixos historicos (c1ab3f8007c4/ecc77df9ca32) — literal, idempotente
    # por chave natural. So' roda se o owner ja tiver plano de contas (senao o passo 1, ou um
    # seed-on-first-access futuro, ja cobre).
    for owner_tipo, owner_id in _OWNERS_FIXOS:
        ja = conn.execute(sa.text(
            "SELECT 1 FROM conta WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
        ), {"ot": owner_tipo, "oid": owner_id, "codigo": "4.4.05"}).scalar_one_or_none()
        if ja is not None:
            continue
        pai = conn.execute(sa.text(
            "SELECT id FROM conta WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
        ), {"ot": owner_tipo, "oid": owner_id, "codigo": "4.4"}).scalar_one_or_none()
        if pai is None:
            continue   # owner sem plano de contas nenhum — nada a estender
        conn.execute(sa.text(
            "INSERT INTO conta (owner_tipo, owner_id, codigo, nome, grupo, tipo, natureza, "
            "pai_id, ativa, ordem) VALUES "
            "(:ot, :oid, '4.4.05', 'Ajuste de Retenção Financeira', 4, 'analitica', 'credora', "
            ":pai_id, 1, 999)"
        ), {"ot": owner_tipo, "oid": owner_id, "pai_id": pai})


def downgrade() -> None:
    """Nao reversivel de forma util — mesma razao de 46a93cfd591b: a conta pode ja ter
    Lancamento apontando pra ela, e o gabarito e' condicional ("so' preenche o que falta"), entao
    upgrade() nao guarda o que cada owner tinha antes pra restaurar."""
    pass
