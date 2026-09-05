"""contas de conciliação (F2-27, MODELO_CONTABIL.md)

`PLANO_PADRAO` (mod_contabil.py) ganhou quatro códigos novos: "4.5 Conciliação" (sintética) /
"4.5.01 Receita de Conciliação" (analítica, credora) e "5.7 Conciliação" (sintética) /
"5.7.01 Despesa de Conciliação" (analítica, devedora, classificada em
`CLASSIFICACAO_GRUPO5_V1` no mesmo centro de custo de "5.6.10 Ajustes de Reconciliação" —
"4.5 Custos Distribuídos", natureza "variavel"). `seed_plano()` só CRIA os códigos que ainda
faltam num owner já existente — owners semeados antes desta revisão nunca ganhariam as contas
novas sozinhos.

Mesmo padrão de `f47f22de46a7` (backfill da 4.4.05):
1) `aplicar_gabarito_completo` (idempotente, só preenche o que falta) para CADA rede e loja
   descobertas do próprio banco — cobre ambientes reais (Integração/Homologação/Produção).
2) INSERT literal das 4 contas (2 sintéticas + 2 analíticas) para os 3 owners fixos históricos
   (rede,1/loja,1/loja,3) — `orizon_baseline_teste` (tests/test_gabarito_migration_x_seed.py)
   não tem dado de instância, então o passo 1 não os alcança ali; esses 3 owners vêm
   inteiramente do histórico congelado em `c1ab3f8007c4`/`ecc77df9ca32`, que este passo
   estende com as contas novas, sem mexer nas migrations anteriores.

Revision ID: a1f2e3c4d5b6
Revises: b0ecb9ce82d2
Create Date: 2026-09-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f2e3c4d5b6'
down_revision: Union[str, Sequence[str], None] = 'b0ecb9ce82d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OWNERS_FIXOS = [("rede", 1), ("loja", 1), ("loja", 3)]

# (codigo, nome, grupo, tipo, natureza, pai_codigo, precisa_classificacao_grupo5)
_CONTAS_NOVAS = [
    ("4.5",    "Conciliação",              4, "sintetica", "credora", "4",   False),
    ("4.5.01", "Receita de Conciliação",   4, "analitica", "credora", "4.5", False),
    ("5.7",    "Conciliação",              5, "sintetica", "devedora", "5",  False),
    ("5.7.01", "Despesa de Conciliação",   5, "analitica", "devedora", "5.7", True),
]

# CLASSIFICACAO_GRUPO5_V1["5.7.01"] em mod_contabil.py — centro de custo "4.5" (Custos
# Distribuídos, mesmo bucket de "5.6.10 Ajustes de Reconciliação"), natureza "variavel".
_CENTRO_CUSTO_CODIGO_5_7_01 = "4.5"
_NATUREZA_CUSTO_5_7_01 = "variavel"


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

    # passo 2: os 3 owners fixos historicos — literal, idempotente por chave natural, na ORDEM
    # da lista (sinteticas antes das analiticas, senao o pai nao existe ainda pro lookup).
    for owner_tipo, owner_id in _OWNERS_FIXOS:
        for codigo, nome, grupo, tipo, natureza, pai_codigo, precisa_g5 in _CONTAS_NOVAS:
            ja = conn.execute(sa.text(
                "SELECT 1 FROM conta WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
            ), {"ot": owner_tipo, "oid": owner_id, "codigo": codigo}).scalar_one_or_none()
            if ja is not None:
                continue
            pai = conn.execute(sa.text(
                "SELECT id FROM conta WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
            ), {"ot": owner_tipo, "oid": owner_id, "codigo": pai_codigo}).scalar_one_or_none()
            if pai is None:
                continue   # owner sem plano de contas nenhum (ou sem o pai recem-inserido) — nada a estender
            cc_id = None
            nat_custo = None
            if precisa_g5:
                cc_id = conn.execute(sa.text(
                    "SELECT id FROM centro_custo WHERE owner_tipo = :ot AND owner_id = :oid AND codigo = :codigo"
                ), {"ot": owner_tipo, "oid": owner_id, "codigo": _CENTRO_CUSTO_CODIGO_5_7_01}).scalar_one_or_none()
                nat_custo = _NATUREZA_CUSTO_5_7_01
            conn.execute(sa.text(
                "INSERT INTO conta (owner_tipo, owner_id, codigo, nome, grupo, tipo, natureza, "
                "pai_id, ativa, ordem, centro_custo_id, natureza_custo) VALUES "
                "(:ot, :oid, :codigo, :nome, :grupo, :tipo, :natureza, :pai_id, 1, 999, :cc_id, :nat_custo)"
            ), {"ot": owner_tipo, "oid": owner_id, "codigo": codigo, "nome": nome, "grupo": grupo,
                "tipo": tipo, "natureza": natureza, "pai_id": pai, "cc_id": cc_id, "nat_custo": nat_custo})


def downgrade() -> None:
    """Não reversível de forma útil — mesma razão de `f47f22de46a7`: as contas podem já ter
    Lancamento apontando pra elas, e o gabarito é condicional (só preenche o que falta), então
    upgrade() não guarda o que cada owner tinha antes pra restaurar."""
    pass
