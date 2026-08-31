# Marco da Fase 1 — implantar nos três servidores

Não é passo do roteiro: é o marco entre a Fase 1 e a Fase 2. Primeira vez
desde a baseline que os ambientes saem de sincronia, e a primeira vez que o
roteiro produz migration.

## O que vai

Duas migrations, encadeadas:

| revisão | o que faz |
|---|---|
| `e031f6ad9c80` | tabela `veredictos_provisao` (ACHADO-16) |
| `f47f22de46a7` | conta 4.4.05, Ajuste de Retenção Financeira (passo 10) |

A segunda já faz o backfill por owner descoberto do próprio banco, no mesmo
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

**Reporte os números e pare.** A decisão do que fazer com dado de teste
anterior à Fase 1 é do Marcelo, não sua. Se vier zero nos três ambientes, o
assunto morre aqui.

## Aplicar

`docs/db/IMPLANTAR.md` é o procedimento. As quatro armadilhas reais já estão
documentadas lá e todas já morderam uma vez:

1. `pip install --break-system-packages --no-deps`
2. o `.env` usa `export` — carregar com `set -a; . ./.env; set +a`
3. postgres não lê `/root` — passar o SQL por stdin
4. dump de PG18 para PG16 precisa de `grep -v '^SET transaction_timeout'`

Ordem: **Integração → Homologação → Produção.** Se algo falhar na
Integração, pare — não é para descobrir o problema em produção.

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
- **Não** rodar `limpar_base.sql` sem decisão explícita. Ele preserva 20
  tabelas de configuração, mas apaga movimento.
- **Não** aplicar em Produção antes de Integração e Homologação passarem.

## O que reportar

1. As três contagens por ambiente, **antes** de aplicar.
2. A saída do `confirmar.sh` de cada ambiente.
3. `alembic current` de cada um, mostrando `f47f22de46a7` como head.
