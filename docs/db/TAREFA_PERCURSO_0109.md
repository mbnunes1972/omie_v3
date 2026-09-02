# TAREFA — o que o percurso de 01/09 encontrou

Seis achados (35 a 40) do percurso manual do Marcelo sobre o
`v2026.09.01-beta1`, mais a resposta a uma pergunta dele que reorganiza a
frente inteira.

**Ler antes:** ACHADO-35 a ACHADO-40 em `ACHADOS_CONTABEIS.md`.

---

# Parte A — a pergunta que muda o desenho

O Marcelo perguntou se o modal de provisões do Ciclo não poderia sumir e
levar direto à Fila, *"um lugar único para resolver provisões, desde
efetivar, revisar, resolver, dar veredito"*.

**A resposta é sim, e o motivo é mais forte do que simplificação de tela.**

As três telas que hoje mostram provisão — Financeiro (leitura), modal de
Reconciliação do projeto, Etapa da Conciliação Final — mais a Fila, são
**quatro caminhos para o mesmo estado**. Essa multiplicidade produziu, em
três dias:

- **ACHADO-26** — a Conciliação Final contornava o veredito por outro
  endpoint;
- **ACHADO-32** — a guarda entrou no servidor e duas telas continuaram
  oferecendo a porta fechada;
- **ACHADO-33** — ao fechar as telas, o único caminho vivo do custo de
  fábrica foi junto.

Três achados, uma causa: **a mesma ação existe em lugares diferentes, com
regras que divergem sozinhas.** Unificar não é estética — é remover a
condição que gera essa família de defeitos.

## O desenho alvo

**Uma tela de Provisões por projeto.** Lista de projetos → provisões
daquele projeto → tudo acontece ali: ver, efetivar, revisar, resolver, dar
veredito. Onde hoje há um modal ou uma tabela editável, passa a haver um
**link para essa tela**, com o projeto já selecionado.

O que some: o modal de Reconciliação do projeto e a edição na tabela da
Conciliação Final. O que fica: a **leitura** na Conciliação Final (ela
precisa mostrar os números que está prestes a fechar) e a leitura
consolidada no Financeiro.

**O botão "Resolver" volta** — pedido explícito do Marcelo, e ele está
certo por dois motivos: um botão comunica ação melhor que um link, e o link
azul de navegador que entrou no lugar está fora do design system
(ACHADO-40). Clicar em Resolver **leva à tela de Provisões daquele
projeto, com a rubrica em foco e o pedido de veredito aberto**.

Isto resolve o ACHADO-37 de graça: por projeto, a fila deixa de ser pilha.

## O que decidir antes de executar

Esta parte **não se implementa junto com a Parte B**. É uma frente própria,
maior, e a Parte B conserta coisas que hoje bloqueiam o operador. Sequência
proposta: Parte B agora, candidato novo, percurso; Parte A como frente
seguinte, com brief próprio.

---

# Parte B — os consertos desta rodada

## B1 · Efetivar duas vezes no mesmo dia (ACHADO-35) — o mais grave

O sistema recusa o segundo lançamento legítimo. Antes do conserto de hoje,
recusava **dizendo que tinha lançado**.

Trocar a recusa por confirmação. Quando já houver efetivação da mesma
rubrica, no mesmo projeto, **no mesmo dia** — de valor igual ou diferente:

> "Já foram efetivados R$ X nesta conta hoje. Confirmar a efetivação de
> **mais** R$ Y?"

Confirmado: lança, com `ref` novo — sequencial dentro do dia, porque é outro
fato. Cancelado: nada. A trava de duplo-clique do botão continua sendo a
proteção contra o acidente; a chave por valor+dia deixa de ser.

**Cuidado que decide o item:** o total efetivado do dia tem que vir do
**razão**, não da soma do que a tela lembra. É a regra 3.

**Teste:** efetivar 3.000, efetivar 3.000 de novo → aparece a confirmação;
confirmando, o efetivado vai a 6.000 e há **dois** lançamentos. Controle
negativo: volte a chave por valor+dia e prove que o teste falha com o
efetivado parado em 3.000.

## B2 · A comunicação sai do canto (ACHADO-36)

Roteamento, não componente novo — `avisoPopup`/`confirmarPopup` já são do
design system. Toda recusa, todo erro e todo pedido de decisão vão para o
box central com OK. Confirmação de ação trivial pode continuar em toast.

**Comece pelo módulo financeiro/provisões**, que é onde a mensagem não vista
vira lançamento errado. O resto do sistema é higiene e pode vir depois — mas
faça o levantamento de quantos `showToast(..., true)` existem e reporte o
número.

## B3 · Senha depois do estado, nunca antes (ACHADO-38)

`peConciliacaoAprovar` pede credencial antes de saber se a AF2 já está
aprovada; `POST /ciclo/11d/aprovar` valida credencial antes de checar
estado. Inverter nas duas pontas: estado primeiro, credencial só quando a
ação vai mesmo acontecer.

**Enumere os irmãos:** todo lugar que chama `pedirCredenciaisGerente` tem a
mesma inversão em potencial. Liste-os e diga quais têm checagem de estado
antes.

## B4 · A decisão do ambiente vem do Δ a cobrar (ACHADO-39)

`_peConcValidasPorSinal(a.diferenca)` usa Δ custo. Passar a usar
`diferenca_valor_contrato`. Ambiente com Δ a cobrar zero **não é pendência**
— não pede decisão e não bloqueia `fase.completa`.

**Antes de mexer, meça:** existe projeto com decisão já gravada por essa
rota (tipo "Absorver R$ 0,00")? Se existir, essas linhas viram o quê? Não
apague nada sem reportar.

## B5 · A coluna Decisão alinhada (ACHADO-40)

Sub-colunas de largura fixa para rótulo, valor e botão. Prova por captura,
não por asserção de DOM — o defeito é visual.

## B6 · A Fila explica os vereditos na hora de escolher

O Marcelo — que **decidiu** a regra do veredito em 31/08 — não lembrava o
que "não se aplica" e "ainda vai chegar" fazem. Se quem desenhou não
lembra, a assistente administrativa que vai usar a tela todo dia não tem
chance. **A dona da tela é ela** (decisão de 31/08).

Cada opção carrega, ao lado, o que faz no livro:

- **Efetivada** — só quando o efetivado já passou do provisionado. A
  despesa real já foi reconhecida ao longo do projeto; cancela só o resíduo
  mecânico, sem tocar o resultado.
- **Encerrada por valor menor** — aconteceu, custou menos que o previsto.
  Reconhece o custo real e depois reverte a sobra genuína.
- **Não se aplica** — a rubrica **nunca incidiu neste projeto**. Toda
  provisão é constituída por regra no fechamento da venda, para todo
  projeto; este veredito diz que aquela despesa nunca existiu aqui. Reverte
  o saldo inteiro, sem reconhecer custo nenhum. **Exige motivo escrito** —
  é o veredito que mais melhora a margem, e por isso o que mais precisa de
  rastro.
- **Ainda vai chegar** — a despesa existe e ainda não chegou. **Não adia
  para depois da Conciliação Final: impede a Conciliação Final.** O projeto
  continua honestamente aberto até o custo real ser lançado.

O último é o que mais confunde e o que mais importa: não é "resolver
depois", é "não dá para fechar".

---

## Medição pedida, sem conserto

**A Provisão de Montagem do projeto Teste 1 não resolveu na Fila.** O
Marcelo não registrou a mensagem. Reproduza: efetivar parcialmente uma
Montagem e tentar cada veredito na Fila. Reporte **a mensagem exata** e qual
veredito foi recusado. Sem isso não há achado, só sintoma.

## O que reportar

1. Cada item de B com aceite e controle negativo.
2. O número de `showToast` de erro no sistema (B2).
3. A lista de chamadores de `pedirCredenciaisGerente` e quais checam estado
   antes (B3).
4. A medição da Montagem do Teste 1.
5. **Nada da Parte A** — ela depende de decisão do Marcelo.
