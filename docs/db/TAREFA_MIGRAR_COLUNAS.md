# Tarefa — fechar os quatro UPDATE/DELETE do _migrar_colunas_pg

## Por que agora
Os quatro rodam a cada boot da aplicacao. Enquanto os bancos estao vazios
eles nao fazem nada. No momento em que a fase de testes criar o dado certo,
o proximo restart o altera ou apaga — em silencio, sem log e sem erro. O
`DELETE` de `papel='assistencia'` e' o mais perigoso: apaga registro
legitimo que alguem acabou de criar.

## Os quatro
1. backfill de `assunto_tipo`
2. migracao `publico` -> `forum_loja`
3. backfill de `responsavel_usuario_id`
4. limpeza de `papel='assistencia'`

## Passo 1 — MEDIR, nao supor
Para cada um dos quatro, escreva a consulta que conta **quantas linhas ele
alteraria hoje** — a mesma condicao do WHERE, so que como SELECT count(*).
Rode contra os quatro bancos:

- localhost (orizon)
- integracao (orizon_integracao)      167.88.33.121
- homologacao (orizon_homologacao)    167.88.33.121
- producao (orizon_producao)          179.197.77.9

Me traga a tabela: quatro linhas por bloco, com a contagem em cada ambiente.
Nao mexa em nada antes disso.

Atencao ao bloco 1: `assuntos` sobreviveu a limpeza do localhost com 2
linhas, entao esse e' o candidato real a ainda ter trabalho a fazer.

## Passo 2 — decidir por bloco, com a medicao na mao
- **Zero em todos os quatro ambientes:** o bloco cumpriu o papel dele.
  Remova a entrada do `_migrar_colunas_pg`, com uma linha no CLAUDE.md
  dizendo o que era e por que saiu. Nao precisa de migration: nao ha nada
  para migrar.
- **Alguma contagem maior que zero:** vira migration de dado (R6), com
  condicao de guarda explicita, e so entao a entrada sai do
  `_migrar_colunas_pg`. Os dois no mesmo commit — separados, um desfaz o
  outro, como no caso do indice duplicado.

## Passo 3 — a rede
Depois que os quatro sairem, o `_migrar_colunas_pg` fica so com ADD/DROP
COLUMN e ALTER de tipo — nenhuma escrita de dado. O
`test_schema_boot_estavel` ja cobre o schema. Acrescente a garantia que
falta: um teste que afirma que **nenhum boot altera DADO**, nao so
estrutura. Retrato de contagem de linhas antes e depois do init_db().

Sem esse teste, o proximo bloco de UPDATE que alguem acrescentar volta a
passar despercebido.

## Relatorio
Traga o passo 1 antes de implementar qualquer coisa.
