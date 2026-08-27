# Tarefa — alinhar os modelos ao banco (bloqueia a baseline do Alembic)

## Diagnóstico

`alembic revision --autogenerate` propõe **dropar os 94 índices criados pela
migration 0003**, porque os modelos SQLAlchemy não os declaram. Enquanto isso
não for corrigido, qualquer autogenerate futuro sugere destruir o trabalho do
Dia 3.

## T-A · Anotar os índices simples nos modelos

Em `migrations/versions/0003_indices_fk.py` existem as listas `NIVEL_1` e
`NIVEL_2` com pares (tabela, coluna) — 94 no total. Para cada par, adicione
`index=True` na coluna correspondente do modelo em `database.py`.

Detalhe que evita retrabalho: o nome padrão que o SQLAlchemy gera para
`index=True` é `ix_<tabela>_<coluna>`, idêntico ao que a 0003 criou. Não
invente nome nem use `Index()` explícito nesses — `index=True` basta e casa.

Faça o mesmo para os 19 pares da lista `FKS` em `0002_fks_e_renomeacao.py`.

## T-B · Índices compostos

A 0002 criou três índices de duas colunas, que precisam de declaração
explícita em `__table_args__`:

    Index('ix_lancamento_owner', 'owner_tipo', 'owner_id')
    Index('ix_periodo_contabil_owner', 'owner_tipo', 'owner_id')
    Index('ix_envios_externos_destinatario', 'destinatario_tipo', 'destinatario_id')

## T-C · As FKs da 0002 nos modelos

Confirme que os 19 `ForeignKey` da 0002 estão declarados nos modelos **com as
mesmas regras de exclusão** (`ondelete` RESTRICT ou SET NULL, `onupdate`
CASCADE). Se algum modelo declarar a FK sem `ondelete`, o autogenerate diverge.
A lista canônica está em `FKS` no arquivo da 0002.

## T-D · server_default em usuarios

O autogenerate propõe alterar duas colunas, removendo o `server_default`:

    usuarios.senha_provisoria    (INTEGER)
    usuarios.notificar_whatsapp  (VARCHAR(16))

Investigue: o banco tem default que o modelo não declara, ou o contrário?
Decida qual lado está certo e alinhe o outro. Relate o que encontrou antes de
mudar, se a decisão não for óbvia.

## T-E · integracoes_d4sign

Confirmada órfã: existe no banco, sem modelo, sem nenhuma referência no código.
É resíduo da "Faxina D4Sign (2026-08-12)", que removeu as colunas `d4sign_*` de
`contratos`/`aprovacoes_pe` mas deixou a tabela. Mantenha a proposta de drop —
ela vira a migration 0005.

## Critério de aceite

Rodar `alembic revision --autogenerate -m "verificacao"` e o `upgrade()` conter
APENAS o drop da `integracoes_d4sign` e dos dois índices dela. Nenhum outro
`drop_index`, nenhum `alter_column`. Apague o arquivo de verificação depois.

## Regra a acrescentar no CLAUDE.md

    R10  Toda migration que cria indice ou constraint tem declaracao
         equivalente no modelo, no mesmo commit. Migration e modelo
         divergentes fazem o autogenerate propor desfazer o que a
         migration fez.
