# Medição — a NF-e pode ser emitida sem `valor_total` persistido?

## O achado, ainda não confirmado

Ao construir o teste de ciclo das DREs, apareceu isto:

- `POST /api/orcamentos/<id>/negociacao-preview` é **só leitura**.
- Quem persiste `orc.valor_total` é `POST /api/orcamentos/<id>/margens`.
- Sem essa chamada, `Val_Cont` nunca existe — e a emissão de NF-e
  **não escritura nada, sem erro**. Fail-soft no caminho do dinheiro.

A primeira versão do teste passou vazia, sem medir nada, exatamente por
isso. Não se sabe se a tela real permite chegar lá.

## A pergunta a responder

**A UI consegue levar um projeto até a emissão de NF-e sem ter passado por
`margens`?**

- Se **sim**: existe caminho pelo qual se emite nota fiscal e não se
  escritura nada — receita zero, custo zero, silêncio. Gravidade alta, sobe
  para o topo do Grupo 1.
- Se **não**: é detalhe de encadeamento do teste. Registrar e seguir.

## Como medir

**Não conserte nada.** É medição.

### 1. O caminho no frontend
Percorra o `static/index.html`: a sequência de telas entre negociação e
emissão. Existe algum fluxo — botão, atalho, deep link, projeto retomado
depois de sair no meio, importação — que alcance a emissão sem que
`margens` tenha sido chamado?

Atenção aos casos de retomada: projeto salvo em rascunho e reaberto dias
depois, ou aprovado por outro usuário que não passou pela mesma tela.

### 2. O caminho na API
Independentemente da UI: a API **recusa** a emissão quando `valor_total` é
nulo ou zero, ou aceita? Qualquer integração ou chamada direta é um caminho
válido de entrada.

### 3. Reproduzir, se for alcançável
Se encontrar o caminho, escreva um teste que o percorre e afirma o que
acontece hoje — receita, custo e saldos das contas depois da emissão.
`xfail(strict=True)` citando ACHADO-18, para virar verde quando for
consertado.

## O que reportar

1. A resposta direta: a UI alcança? A API aceita?
2. Se alcança, por qual caminho exatamente (arquivo, função, sequência).
3. O que acontece hoje, em números, quando alcança.
4. Se **não** alcança, o que impede — e se esse impedimento é uma validação
   deliberada ou só a ordem das telas. A diferença importa: ordem de tela
   muda com um redesenho; validação não.

## Por que isso vale antes do conserto

Se a emissão pode escriturar nada em silêncio, nenhum dos outros consertos
do Grupo 1 garante número certo — bastaria esse caminho para zerar tudo de
novo, sem erro e sem aviso.
