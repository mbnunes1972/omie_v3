# Medição — `negociacao-preview`, `valor_total` e `margens`

Escrito em 29/08/2026. Fecha a pergunta aberta no teste de ciclo das DREs e
no ACHADO-18, agora sabendo o que o ACHADO-19 mostrou.

**Não conserte nada nesta tarefa.** É medição. Todo conserto sai daqui com
número na mão.

## Situação em 29/08/2026

**Medições 1, 2 e 3: feitas.** Resultado completo no ACHADO-19. Em resumo: o
motor levanta por dois caminhos apenas (`parametros_json` malformado e
complemento auto-referente — ACHADO-20), nenhum alcançável por usuário; as
seis rotas deixam todas a mesma assinatura (insumo novo commitado, número
velho); e o "erro invisível" da tela existe em **uma** rota só, `/parametros`,
não nas duas que a prosa original apontava. Pela regra desta tarefa, o
ACHADO-19 desceu para o Grupo 5, com três consertos de causa baratos no lugar
da reescrita das seis transações.

**Medições 4, 5 e 6: não iniciadas, e agora sem urgência.** A 6 continua
valendo por si — é a pergunta do ACHADO-18 pelo outro lado. A 5 vale como
ferramenta permanente de conferência, não como diagnóstico deste achado.

---

## O que já está medido (não refaça)

`_recalcular_orcamento` (main.py:17337) é a única função que persiste
`orc.valor_total`, `orc.valor_liquido` e as 14 colunas-sombra do motor. Ela
é chamada de nove lugares. Três falham alto; **seis engolem a exceção e
respondem `ok: True`**, com a entrada do usuário commitada assim mesmo. O
mapa completo, linha por linha, está no ACHADO-19.

`POST /api/orcamentos/<id>/negociacao-preview` (main.py:10981) é só
leitura: chama `_negociacao_breakdown` e devolve. Não grava nada, nunca.
Quem grava é `/margens` (10904), `/descontos` (15591), `/parametros`
(10839), `/valor` (15825), os dois de complemento de PE (7838, 7901) e os
três de ambiente/XML (11875, 12184, 12278).

Isto já basta para saber que os nomes não descrevem o comportamento — um
endpoint chamado `margens` é o que consolida o valor da venda. Mas
**renomear vem depois de medir**, não antes.

---

## As seis medições

### 1. `_negociacao_breakdown` levanta exceção com que entrada?

A fail-soft só importa na medida em que a falha acontece. Hoje ninguém sabe
se ela acontece.

Percorra `_negociacao_breakdown` (main.py:17239) e o motor que ela chama
(`mod_negociacao`, `mod_provisoes`, `mod_orcamento_params`) e liste os
pontos que podem levantar. Os candidatos visíveis a olho nu:
`json.loads(proj.parametros_json)` sem try/except; `_complemento_diferencas`
e `_complemento_diferencas_fase`; ambiente sem `budget_total`; divisão por
markup ou carga tributária zerada; `forma_pagamento` gravada com uma
estrutura que o motor não espera.

Para cada candidato, escreva um teste que **constrói a entrada** e afirma se
levanta ou não. Não presuma pela leitura.

**Reportar:** a lista de entradas que fazem o motor levantar, e quais delas
um usuário consegue produzir sem tocar no banco.

### 2. O que fica no banco depois de cada fail-soft

Para cada uma das seis rotas do ACHADO-19: force a falha do recálculo
(monkeypatch em `_recalcular_orcamento`, ou a entrada real da medição 1 se
existir uma), chame a rota pelo cliente HTTP de teste, e leia o banco
depois.

Compare **coluna por coluna, não por total**: `valor_total`,
`valor_liquido`, `desconto_pct`, `forma_pagamento`, `negociacao_json`, e as
14 sombras (`vbvo`, `cfo`, `vbno`, `vavo`, `cust_ad`, `val_liq`,
`com_arq_orc`, `pro_fid_orc`, `desc_tot_pct`, `markup`, `prov_imp`,
`cust_fin`, `val_cont`). Dois erros podem se cancelar num total.

**Reportar:** uma tabela por rota — o que mudou, o que ficou velho, e qual é
o código de resposta. A pergunta que a tabela responde: existe alguma rota
onde insumo e resultado ficam consistentes? Se existe, ela é o modelo do
conserto.

### 3. A tela mostra o número que o banco não tem?

Em `/parametros` (10893) e `/margens` (10966) a resposta devolve `sombra`,
recalculada na hora. Se a persistência falhou e a leitura funciona, a tela
mostra o novo e o banco guarda o velho.

Reproduza: force a falha só na persistência e verifique se a `sombra`
devolvida traz o valor novo. Se trouxer, isso é pior que o erro — é o erro
invisível.

**Reportar:** sim ou não, com o JSON da resposta ao lado da linha do banco.

### 4. O contrato bate consigo mesmo?

`_ambientes_valor_para_contrato` (17357) e `_valores_contrato_por_ambiente`
(17399) recalculam o breakdown **ao vivo** para ratear ambientes. O total do
contrato vem de `orc.valor_total` **persistido**.

Com um `valor_total` defasado, a soma dos ambientes do contrato bate com o
total do contrato? E as parcelas, que saem do rateio?

**Reportar:** os dois números lado a lado num contrato com `valor_total`
defasado. Se divergirem, é um contrato internamente inconsistente entregue
ao cliente — sobe direto para o Grupo 1.

### 5. Quantos orçamentos já estão defasados hoje?

A medição que decide a gravidade. Escreva um script **somente leitura**
(`scripts/conferir_valor_total.py`) que, para cada orçamento de cada
ambiente, recalcula `_negociacao_breakdown` e compara com as colunas
persistidas, com tolerância de centavo.

Rode nos quatro ambientes. **Não grave nada, não conserte nada** — a saída é
uma lista: orçamento, loja, projeto, coluna, valor persistido, valor
recalculado, diferença.

**Reportar:** a contagem por ambiente e as dez maiores diferenças. Zero
divergências é um resultado válido e importante: significa que o fail-soft
nunca disparou em produção até aqui, e o conserto é preventivo.

Este script fica no repositório depois da medição — vira a conferência
padrão, do mesmo jeito que `confirmar.sh` virou.

### 6. Existe caminho até o contrato sem nunca ter persistido?

A pergunta original do ACHADO-18, agora com o alvo certo. `index.html:22975`
chama `negociacao-preview` a partir de outra tela — descubra qual, e se
dela se alcança a geração de contrato sem passar por nenhuma das rotas que
gravam.

Atenção ao caso de retomada: orçamento criado, negociado na tela de preview,
salvo, reaberto por outro usuário e aprovado.

**Reportar:** o caminho exato, ou a confirmação de que não existe — e, se não
existe, o que impede: validação deliberada ou ordem de tela. Essa distinção
já se mostrou decisiva uma vez.

---

## Ordem

1, 2 e 3 primeiro: são de laboratório e respondem se o problema é real.
5 em seguida: dá o tamanho. 4 e 6 depois, porque dependem de saber que 1-3
deram positivo.

Se a medição 1 mostrar que `_negociacao_breakdown` **não tem** caminho de
exceção alcançável por usuário, o ACHADO-19 continua valendo (a resposta
`ok` a uma falha continua errada) mas desce de prioridade, e o conserto vira
higiene do Grupo 5 em vez de urgência do Grupo 1.

## O que não fazer

- Não renomeie endpoint nenhum nesta tarefa.
- Não transforme `except` em `raise` "de passagem" — o conserto tem que
  incluir a transação, e transação mal fechada é pior que fail-soft.
- Não use o total como critério de comparação em lugar nenhum.
- Não escreva no banco de nenhum ambiente. A medição 5 é `SELECT` e
  cálculo em memória.
