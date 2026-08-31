# F2-2 — auditoria de contrato de API × frontend

**Não estava no roteiro. Entra na frente do passo 12** porque o ACHADO-25
mostrou que estamos consertando código que a tela talvez não alcance mais.

## O que aconteceu

O passo 6-c passou a exigir `forma_pagamento` na assinatura do aditivo. O
frontend nunca foi atualizado: `peAditivoAssinar` manda só
`{parte, nome, cpf}`. Hoje **toda** 2ª assinatura de aditivo é recusada com
400 em produção. Ninguém percebeu porque **a suíte chama a API direto** — os
testes mandam o campo novo e passam.

Essa é a lacuna: **mudança de contrato de API é invisível para os 2466
testes.** Cada passo da Fase 1 que mexeu em campo obrigatório pode ter
quebrado uma tela, e nada acusaria.

## O que medir

Para **cada** conserto que tocou um endpoint, confira o chamador real em
`static/index.html`:

| passo | endpoint | o que mudou | a tela manda? |
|---|---|---|---|
| 6-c | `POST /projetos/<n>/aditivo/assinar` | exige `forma_pagamento` | **NÃO — ACHADO-25** |
| 8 | `POST /projetos/<n>/ciclo/21/conciliar` | exige veredito por rubrica aberta | ? |
| 9 | `POST /projetos/<n>/contrato` | recusa `valor_total <= 0` | ? |
| 9 | `POST /projetos/<n>/ciclo/15/emitir-nfe` | recusa total contratado <= 0 | ? |
| F2-1 | `POST /contrato` e assinatura do aditivo | exige plano que gere recebível | ? |
| 10 | rotas de ramo financeiro | mudou evento, não contrato | provavelmente n/a |

**O passo 8 é o suspeito grave.** Se a tela da Conciliação Final não manda
vereditos, nenhum projeto se conclui pela interface — quebra maior que a do
aditivo, no fluxo mais importante do sistema.

Para cada linha: a tela alcança o endpoint com os campos exigidos hoje? Se
não, qual a mensagem que o usuário vê?

## O que NÃO fazer nesta tarefa

**Não conserte as telas.** Cada uma é trabalho de frontend com decisão de
produto embutida — que campos, onde, com que rótulo. Vira tarefa própria,
com o Marcelo decidindo o desenho.

O produto aqui é o **mapa**: quais fluxos estão quebrados hoje, por qual
campo, e com que mensagem o usuário esbarra.

## O que fica depois, e é o mais importante

A suíte prova o servidor e não prova o sistema. Proponha — **sem
implementar** — como fechar isso. Direções possíveis:

- um teste que varre `static/index.html` e confere que todo `fetch` para uma
  rota conhecida manda os campos que ela exige;
- um contrato declarado por endpoint, lido pelos dois lados;
- e2e de navegador nos fluxos críticos.

Diga qual você faria e por quê, com o custo de cada uma. **A recomendação é
o entregável, não o código.**

## Reportar

1. A tabela acima preenchida, com evidência por linha.
2. Para cada fluxo quebrado: o campo que falta e a mensagem que o usuário vê.
3. A recomendação de como impedir que isto se repita.
