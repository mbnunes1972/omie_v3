"""Indices nas colunas filhas das FKs — niveis 1 e 2.

Revisao 0003.

Diagnostico do Dia 0: 147 das 171 FKs pre-existentes nao tinham indice na
coluna filha, em 75 das 83 tabelas. O PostgreSQL indexa o lado do pai
automaticamente e nunca o do filho.

Escopo: niveis 1 e 2 (43 + 51 = 94). O nivel 3 — colunas de autoria
(*_por_id, criado_por_id) — fica adiado ate haver evidencia de uso: varias
delas estao vazias em 100% das linhas hoje.

Motivo, com honestidade: a maior tabela do banco tem 667 linhas, entao isto
NAO corrige lentidao medida. E investimento — criar indice agora custa
milissegundos; com dados de cliente e carga real, a mesma operacao vira
janela de manutencao.

Guarda contra duplicata: o codigo antigo criou indices com nomes abreviados
(ex.: ix_ciclo_etapas_responsavel_terceiro). Cada criacao verifica o catalogo
antes e pula se ja houver indice NAO-PARCIAL comecando por aquela coluna.
Indice parcial nao conta: ele nao satisfaz a checagem de FK.

Revision ID: 0003
Revises: 0002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Duplicata exata confirmada em 27/08/2026: mesmo indice que a 0002 criou
# como ix_ciclo_etapas_responsavel_terceiro_id, com nome antigo abreviado.
DUPLICATAS = [
    ("ciclo_etapas", "ix_ciclo_etapas_responsavel_terceiro"),
]

# NIVEL 1 — multi-tenant e hierarquia contabil (43)
NIVEL_1 = [
    ("acordo_fabrica", "loja_titular_id"),
    ("adiantamento_funcionario", "loja_id"),
    ("aditivos", "loja_id"),
    ("ajuste_fabrica", "loja_id"),
    ("aprovacoes_pe", "loja_id"),
    ("assistencia_caso", "loja_id"),
    ("atribuicoes_ambiente", "loja_id"),
    ("centro_custo", "pai_id"),
    ("ciclo_logistico", "loja_id"),
    ("clientes", "loja_id"),
    ("comissao_folha", "loja_id"),
    ("conta", "pai_id"),
    ("contratos", "loja_id"),
    ("documento_fiscal", "emitente_id"),
    ("documento_fiscal", "loja_id"),
    ("emitente", "rede_id"),
    ("folha_pagamento", "loja_id"),
    ("fornecedores", "loja_id"),
    ("funcionarios", "loja_id"),
    ("funcoes", "loja_id"),
    ("integracoes_clicksign", "loja_id"),
    ("integracoes_clicksign", "rede_id"),
    ("integracoes_d4sign", "loja_id"),
    ("integracoes_d4sign", "rede_id"),
    ("lancamento", "conta_credito_id"),
    ("lancamento", "conta_debito_id"),
    ("lojas", "emitente_id"),
    ("lojas", "rede_id"),
    ("orcamentos", "loja_id"),
    ("parceiro_lojas", "loja_id"),
    ("parceiros", "rede_id"),
    ("perfil_emissao", "emitente_id"),
    ("projetos_meta", "loja_id"),
    ("provisao_data_prevista", "loja_id"),
    ("recebivel", "loja_id"),
    ("redes", "emitente_central_id"),
    ("simulador_autorizacoes", "loja_id"),
    ("simulador_log_acessos", "loja_id"),
    ("solicitacoes_medicao", "loja_id"),
    ("terceiros", "loja_id"),
    ("usuario_lojas", "loja_id"),
    ("usuarios", "loja_id"),
    ("usuarios", "rede_id"),
]

# NIVEL 2 — relacionais de negocio (51)
NIVEL_2 = [
    ("adiantamento_funcionario", "funcionario_id"),
    ("aditivos", "contrato_id"),
    ("aditivos", "modelo_versao_id"),
    ("aditivos", "orcamento_complemento_id"),
    ("aditivos_assinaturas", "aditivo_id"),
    ("ajuste_fabrica", "acordo_id"),
    ("ajuste_fabrica_aplicacao", "ajuste_id"),
    ("aprovacoes_pe", "contrato_id"),
    ("aprovacoes_pe", "modelo_versao_id"),
    ("aprovacoes_pe_assinaturas", "aprovacao_id"),
    ("arquivo_pe", "pool_ambiente_id"),
    ("assistencia_anexos", "caso_id"),
    ("assistencia_executores", "caso_id"),
    ("assistencia_executores", "funcionario_id"),
    ("assistencia_executores", "terceiro_id"),
    ("atribuicoes_ambiente", "funcionario_id"),
    ("atribuicoes_ambiente", "pool_ambiente_id"),
    ("atribuicoes_ambiente", "terceiro_id"),
    ("briefings", "cliente_id"),
    ("ciclo_logistico", "nfe_id"),
    ("ciclo_logistico", "parcela_id"),
    ("ciclo_logistico_transicao", "ciclo_logistico_id"),
    ("ciclo_revisoes", "relatorio_doc_id"),
    ("comissao_folha", "funcionario_id"),
    ("conciliacao_pe_fase", "parcela_id"),
    ("conciliacao_pe_fase", "pool_ambiente_id"),
    ("contratos", "modelo_versao_id"),
    ("contratos", "orcamento_id"),
    ("contratos_assinaturas", "contrato_id"),
    ("conversa_mensagens", "documento_ref_id"),
    ("conversas", "cliente_id"),
    ("documento_fiscal", "danfe_doc_id"),
    ("documento_fiscal", "fabrica_doc_id"),
    ("documento_fiscal", "xml_doc_id"),
    ("folha_pagamento", "funcionario_id"),
    ("funcionarios", "funcao_id"),
    ("orcamento_ambientes", "pool_ambiente_id"),
    ("parceiro_lojas", "parceiro_id"),
    ("parcela_ambiente", "pool_ambiente_id"),
    ("parcela_projeto", "orcamento_id"),
    ("projetos_meta", "cliente_id"),
    ("provisao_registro", "por_id"),
    ("recebivel", "orcamento_id"),
    ("segmento_config", "template_padrao_id"),
    ("sinal_retido", "pool_ambiente_id"),
    ("solicitacoes_medicao", "modelo_versao_id"),
    ("solicitacoes_medicao_assinaturas", "solicitacao_id"),
    ("terceiros", "funcao_id"),
    ("triagem_entradas", "conversa_id"),
    ("usuarios", "funcao_id"),
    ("usuarios", "funcionario_id"),
]

ALVOS = NIVEL_1 + NIVEL_2


def _ix(tabela: str, coluna: str) -> str:
    return f"ix_{tabela}_{coluna}"


def _ja_indexada(bind, tabela: str, coluna: str) -> bool:
    """True se ja existe indice NAO-PARCIAL cuja primeira coluna e esta."""
    return bool(bind.execute(sa.text("""
        SELECT 1
        FROM pg_index i
        JOIN pg_class     t ON t.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = i.indkey[0]
        WHERE n.nspname = 'public'
          AND t.relname = :tabela
          AND a.attname = :coluna
          AND i.indpred IS NULL
        LIMIT 1
    """), {"tabela": tabela, "coluna": coluna}).scalar())


def upgrade() -> None:
    bind = op.get_bind()

    for tabela, indice in DUPLICATAS:
        op.execute(f"DROP INDEX IF EXISTS {indice}")

    criados = pulados = 0
    for tabela, coluna in ALVOS:
        if _ja_indexada(bind, tabela, coluna):
            pulados += 1
            continue
        op.create_index(_ix(tabela, coluna), tabela, [coluna])
        criados += 1

    print(f"  0003: {criados} indices criados, {pulados} pulados (ja existiam)")


def downgrade() -> None:
    # DROP IF EXISTS porque o upgrade pula os que ja existiam — estes nunca
    # foram criados por esta revisao e nao devem ser removidos por ela.
    for tabela, coluna in ALVOS:
        op.execute(f"DROP INDEX IF EXISTS {_ix(tabela, coluna)}")

    # a duplicata removida no upgrade e recriada, para o downgrade ser fiel
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ciclo_etapas_responsavel_terceiro "
        "ON ciclo_etapas (responsavel_terceiro_id)"
    )
