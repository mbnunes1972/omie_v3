# Marco da Fase 1 — implantar nos três servidores

Não é passo do roteiro: é o marco entre a Fase 1 e a Fase 2. Primeira vez
desde a baseline que os ambientes saem de sincronia, e a primeira vez que o
roteiro produz migration.

## O que vai

**Três migrations, não duas** — corrigido ao rodar `alembic current` nos três
ambientes antes de aplicar qualquer coisa: os três partiam de `46a93cfd591b`,
e `95c7e64afc6a` nunca tinha entrado nesta lista.

| revisão | o que faz |
|---|---|
| `95c7e64afc6a` | renomeia 2.1.05 Total Flex → Parcelamento Loja (ACHADO-14) |
| `e031f6ad9c80` | tabela `veredictos_provisao` (ACHADO-16) |
| `f47f22de46a7` | conta 4.4.05, Ajuste de Retenção Financeira (passo 10) |

A terceira já faz o backfill por owner descoberto do próprio banco, no mesmo
padrão de `46a93cfd591b` — não precisa de passo manual para as contas.

## Antes de aplicar: medir o que já existe

**Os lançamentos anteriores seguem as regras antigas.** Depois da Fase 1,
`4.1.01` recebe o VAVO; antes, recebia o Val_Cont cheio. Um livro com as
duas convenções misturadas não é meio certo — é errado de um jeito que
nenhum relatório consegue separar.

Então, em cada ambiente, antes de qualquer coisa:

```sql
SELECT count(*) FROM lancamentos;
SELECT count(*) FROM contratos;
SELECT count(*) FROM orcamentos;
```

**AUTORIZADO pelo Marcelo em 31/08: pode apagar.** Onde houver movimento,
rode `limpar_base.sql` — ele preserva as 20 tabelas de configuração,
`usuarios` entre elas (o script tem comentário próprio explicando que
`funcionarios` não é dropado justamente porque o CASCADE levaria `usuarios`
junto). O acesso à produção sobrevive.

Reporte as contagens de antes e de depois assim mesmo — é o registro de que
o livro recomeçou sob uma regra só.

## Aplicar

`docs/db/IMPLANTAR.md` é o procedimento. As quatro armadilhas reais já estão
documentadas lá e todas já morderam uma vez:

1. `pip install --break-system-packages --no-deps`
2. o `.env` usa `export` — carregar com `set -a; . ./.env; set +a`
3. postgres não lê `/root` — passar o SQL por stdin
4. dump de PG18 para PG16 precisa de `grep -v '^SET transaction_timeout'`

Ordem entre ambientes: **Integração → Homologação → Produção.** Se algo
falhar na Integração, pare — não é para descobrir o problema em produção.

Ordem **dentro** de cada ambiente:

1. backup;
2. aplicar as duas migrations;
3. `confirmar.sh` — zero FALHA;
4. **só então** `limpar_base.sql`;
5. contagens de novo, para registrar o zero.

A limpeza vem por último de propósito: se a migration falhar, o dado ainda
está lá e as opções continuam abertas. Apagar primeiro fecha portas sem
necessidade.

## Conferir

`bash docs/db/confirmar.sh` **em cada ambiente**, e a saída inteira no
relatório. É o script que compara modelos × banco em quatro dimensões e
reconstrói o schema do zero pelas migrations. Zero FALHA em todos os três,
ou não seguimos.

Confira também que `veredictos_provisao` está no manifesto de `modulos.py` —
o passo 8 descobriu isso por acidente e não deve ser redescoberto em
produção.

## Não confundir

- **Não** tocar em `docs/db/config_*.sql` — contêm credenciais de integração
  e são gitignored de propósito.
- **Não** rodar `limpar_base.sql` antes do `confirmar.sh` passar.
- **Não** aplicar em Produção antes de Integração e Homologação passarem.

## O que reportar

1. As três contagens por ambiente, **antes** de aplicar.
2. A saída do `confirmar.sh` de cada ambiente.
3. `alembic current` de cada um, mostrando `f47f22de46a7` como head.

## Feito — 31/08/2026

Contagens ZERO nos três antes de aplicar (assunto morreu ali, como previsto).
Upgrade incremental, Integração → Homologação → Produção, `confirmar.sh` 15
OK / 0 FALHA nos três, `alembic current` = `f47f22de46a7` nos três,
`veredictos_provisao` no manifesto de `modulos.py` confirmado nos três.
Registro completo (comandos, armadilhas novas encontradas) em
`docs/db/IMPLANTAR.md`, seção "Executado".
