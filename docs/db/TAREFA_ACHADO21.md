# Passo 6 do ROTEIRO — o aditivo para de ser cobrado duas vezes, e passa a ser cobrado

Duas coisas que precisam entrar juntas (ACHADO-21 + recebíveis próprios), e
uma extração que vem antes das duas.

## Ajuste no roteiro, com motivo

O passo 6 dizia também "predicado explícito do aditivo" e "segmentação
congelada". **Saem daqui e vão para o passo 7** — os dois são sobre a *soma
para faturar*, não sobre a imutabilidade. Manter no 6 misturava assuntos e
inchava o passo.

Entra no lugar uma **extração**, pelo motivo do item 6-a abaixo.

---

## 6-a · Extrair `valor_contratado_do_projeto` — antes de qualquer conserto

O ACHADO-21 precisa saber **quanto já foi contratado** (contrato + aditivos
assinados) para calcular a diferença da revisão nova. O ACHADO-12, no passo
7, precisa do mesmo número para faturar. **É o mesmo conceito.**

Se cada passo escrever a sua própria soma, criamos duas respostas para "qual
é o valor do projeto" que podem divergir — que é literalmente o ACHADO-03,
a doença de ter a mesma decisão em dois lugares.

Então: extrair primeiro, uma função só, com testes próprios, **sem mudar
comportamento nenhum**. Mesmo padrão que o roteiro já usa para
`garantir_projeto()` antes da FK.

Ela responde: contrato + aditivos **assinados** (não os rascunhos). O
critério de "assinado" tem que estar explícito na função, não inferido pelo
chamador.

## 6-b · ACHADO-21 — o orçamento de complemento vira imutável

Hoje `POST /pe/complemento/orcamento` faz get-or-create por
`projeto_id + complemento_pe=1 + parcela_id` e **sobrescreve o
`valor_total`** de um orçamento que já tem aditivo assinado. Medido: cobrou
R$ 15.555,55 onde o correto era R$ 11.111,11, e o valor pelo qual o cliente
assinou o primeiro aditivo deixou de existir.

Duas metades, e **as duas são obrigatórias**:

1. **Não reaproveitar** orçamento de complemento que já tenha aditivo
   assinado. A revisão seguinte cria um orçamento novo.
2. **A diferença do novo passa a ser calculada contra `valor_contratado_do_projeto`**
   (6-a), não contra o contrato sozinho. Sem esta metade, o orçamento novo
   cobra a diferença cheia de novo e o defeito continua, só que com duas
   linhas em vez de uma.

A linha de desenho, para ficar no código e não só aqui: **antes da
assinatura, revisão de PE é sobrescrita livre — é o modelo de trabalho;
depois da assinatura, a diferença já virou lançamento, e mudança é evento
novo, não sobrescrita.**

## 6-c · Recebíveis próprios do aditivo

Decidido em 29/08: a assinatura do aditivo coleta forma de pagamento e chama
`_materializar_recebiveis_venda_seguro` para o orçamento do complemento. A
guarda de idempotência já é por `orcamento_id`, então nada toca nos
recebíveis do contrato.

**Por que entra junto com o 6-b:** o recálculo do complemento zera
`forma_pagamento` (main.py:7885-7891). Com a forma coletada na assinatura,
um recálculo posterior a apagaria — e é a imutabilidade do 6-b que impede.
Um sem o outro produz recebível que nasce e some.

**Consequência esperada, não surpresa:** com `forma_pagamento` preenchida, o
aditivo passa a ter **custo financeiro próprio** — `_ramo_financeiro_efetivo`
lê esse campo. Hoje, sem forma de pagamento, ele provavelmente cai no
default à vista e não constitui custo financeiro nenhum. **Meça o antes e o
depois** e reporte: é uma provisão que passa a existir, e tem que existir
pela regra do deságio, mas ninguém deve descobrir isso por acidente.

---

## Aceites

O `xfail(strict=True)` da costura 4 (ACHADO-21) sai no mesmo commit do
conserto. Além dele, escreva antes:

1. **Recebível do aditivo existe e não mexe nos do contrato** — soma dos
   recebíveis do contrato inalterada, linhas novas apenas para o orçamento
   do complemento.
2. **Revisão depois da assinatura cria orçamento novo**, e o valor do
   aditivo #1 continua legível no orçamento dele.
3. **A conferência do ACHADO-21 fecha:** soma dos créditos de 2.1.06 do
   projeto == `valor_contratado_do_projeto`. Hoje diverge; é o rastro que
   registramos como diagnóstico.

## O que NÃO fazer

- Não implementar a soma para faturar (ACHADO-12) — passo 7.
- Não mexer no predicado nem na segmentação — passo 7.
- Não inventar forma de pagamento padrão para o aditivo: se a tela não
  coletar, a assinatura recusa com mensagem clara.
- Não alterar comportamento no 6-a. Extração é extração.

## Um alerta vindo do passo 5

A Vera precisou ajustar `test_cancelar_nfe_estorna_faturamento`, que passava
**por causa** do bug do ACHADO-13. Quando um conserto quebra um teste
vizinho, há duas hipóteses e as duas precisam ser consideradas: o conserto
está errado, ou o teste codificava o defeito como correto. No passo 5 era a
segunda. **Não assuma qual é** — diga qual, e por quê.
