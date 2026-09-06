"""conta despesa avulsa de projeto (F2-30 Fatia 2)

`PLANO_PADRAO` (mod_contabil.py) ganhou o código novo "5.3.22 Despesa Avulsa de Projeto"
(analítica, devedora, classificada em `CLASSIFICACAO_GRUPO5_V1` no mesmo centro de custo de
"5.3.17 Custo Especial de Projeto" — "3.2 Projetos/Design", natureza "variavel"): compra
complementar descoberta na entrega, não prevista na venda, que não corresponde a nenhuma rubrica
com provisão (ver docs/db/MODELO_CONTABIL.md, "Os três destinos de um gasto de projeto").
`seed_plano()` só CRIA os códigos que ainda faltam num owner já existente — owners semeados
antes desta revisão nunca ganhariam a conta nova sozinhos.

Mesmo padrão de `a1f2e3c4d5b6`/`f47f22de46a7`:
1) `aplicar_gabarito_completo` (idempotente, só preenche o que falta) para CADA rede e loja
   descobertas do próprio banco — cobre ambientes reais (Integração/Homologação/Produção).
2) INSERT literal da conta nova para os 3 owners fixos históricos (rede,1/loja,1/loja,3) —
   `orizon_baseline_teste` (tests/test_gabarito_migration_x_seed.py) não tem dado de instância,
   então o passo 1 não os alcança ali; esses 3 owners vêm inteiramente do histórico congelado em
   `c1ab3f8007c4`/`ecc77df9ca32`, que este passo estende com a conta nova, sem mexer nas
   migrations anteriores.

Revision ID: 655716ac5fd8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '655716ac5fd8'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OWNERS_FIXOS = [("rede", 1), ("loja", 1), ("loja", 3)]

_CODIGO = "5.3.22"
_NOME = "Despesa Avulsa de Projeto"
_GRUPO = 5
_TIPO = "analitica"
_NATUREZA = "devedora"
_PAI_CODIGO = "5.3"

# CLASSIFICACAO_GRUPO5_V1["5.3.22"] em mod_contabil.py — mesmo centro de custo de "5.3.17 Custo
# Especial de Projeto" ("3.2 Projetos/Design"), natureza "variavel".
_CENTRO_CUSTO_CODIGO = "3.2"
_NATUREZA_CUSTO = "variavel"


def upgrade() -> None:
    from sqlalchemy.orm import Session as _Session
    import database as db
    import mod_contabil as mc

    conn = op.get_bind()

    # passo 1: ambientes reais — owners descobertos do proprio banco, sem lista fixa.
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

    # passo 2: os 3 owners fixos historicos — literal, idempotente por chave natural.
    for owner_tipo, owner_id in _OWNERS_FIXOS:
        ja = conn.execute(sa.text(
            "SELECT 1 FROM conta WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
        ), {"ot": owner_tipo, "oid": owner_id, "codigo": _CODIGO}).scalar_one_or_none()
        if ja is not None:
            continue
        pai = conn.execute(sa.text(
            "SELECT id FROM conta WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
        ), {"ot": owner_tipo, "oid": owner_id, "codigo": _PAI_CODIGO}).scalar_one_or_none()
        if pai is None:
            continue   # owner sem plano de contas nenhum (ou sem o pai) — nada a estender
        cc_id = conn.execute(sa.text(
            "SELECT id FROM centro_custo WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
        ), {"ot": owner_tipo, "oid": owner_id, "codigo": _CENTRO_CUSTO_CODIGO}).scalar_one_or_none()
        conn.execute(sa.text(
            "INSERT INTO conta (owner_tipo, owner_id, codigo, nome, grupo, tipo, natureza, "
            "pai_id, ativa, ordem, centro_custo_id, natureza_custo) VALUES "
            "(:ot, :oid, :codigo, :nome, :grupo, :tipo, :natureza, :pai_id, 1, 999, :cc_id, :nat_custo)"
        ), {"ot": owner_tipo, "oid": owner_id, "codigo": _CODIGO, "nome": _NOME, "grupo": _GRUPO,
            "tipo": _TIPO, "natureza": _NATUREZA, "pai_id": pai, "cc_id": cc_id,
            "nat_custo": _NATUREZA_CUSTO})


def downgrade() -> None:
    """Não reversível de forma útil — mesma razão de `a1f2e3c4d5b6`/`f47f22de46a7`: a conta pode
    já ter Lancamento apontando pra ela, e o gabarito é condicional (só preenche o que falta),
    então upgrade() não guarda o que cada owner tinha antes pra restaurar."""
    pass
