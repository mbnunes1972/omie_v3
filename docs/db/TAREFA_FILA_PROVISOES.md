# F2-3 — a fila de provisões, e só então o fechamento do desvio

Duas coisas que entram **juntas e nesta ordem**. A fila é a porta da frente;
o desvio é a porta dos fundos. Fechar os fundos antes de abrir a frente
deixa o sistema sem porta nenhuma.

## Por que os dois juntos

O passo 8 fez a Conciliação Final recusar projeto com provisão em aberto. O
F2-2 mostrou que a tela nunca ganhou campo de veredito, e que os botões
"Efetivar"/"Resolver" zeram o saldo por outro endpoint, sem veredito nenhum
— então o ACHADO-16 continua acontecendo, pela única porta que existe
(ACHADO-26).

## Parte 1 — a fila (a porta da frente)

**Dona: a assistente administrativa da loja.** Decisão do Marcelo em 31/08:
é quem tem o pedido e a nota da fábrica na mão e sabe responder *"ainda há
despesa a realizar?"* — a pergunta que o sistema não consegue responder
sozinho e que é a origem de todo o ACHADO-16.

Lista toda provisão em aberto, por projeto. Cada linha precisa do mínimo
para a pessoa **decidir**, não só para ver: rubrica, valor provisionado,
valor já efetivado, saldo, projeto, e há quanto tempo está aberta.

As ações são os quatro vereditos já decididos, e nada além deles:

| veredito | o que a tela pede | o que o livro faz |
|---|---|---|
| **efetivada** | nada | nada — já lançado |
| **encerrada com valor menor** | o valor real | efetiva pelo valor real **e depois** reverte o resíduo — as duas pernas |
| **não se aplica** | motivo escrito, obrigatório | reverte o saldo integralmente |
| **ainda vai chegar** | nada | não resolve; o projeto continua aberto |

Grava em `VeredictoProvisao`, que já existe desde o passo 8. **Nenhum quinto
veredito, nenhum "outros".**

## Parte 2 — o desvio (só depois da Parte 1 funcionando)

`/api/financeiro/resolver-saldo-provisao` passa a recusar as rubricas que
exigem veredito.

**Meça antes de restringir:** esse endpoint atende hoje a impostos e custo
financeiro, que a `conciliar_final` exclui da regra de veredito de
propósito. Levante todos os usos legítimos antes de mexer — restringir
demais quebra o que funciona, e é o erro simétrico ao que estamos
consertando.

E confira os **irmãos**: existe algum outro endpoint que zere saldo de
provisão? A lição do ACHADO-26 é essa, e ela custa uma varredura.

## Parte 3 — a mensagem da Conciliação Final

Ela **não ganha campos de veredito**. Continua recusando quando há provisão
em aberto, mas a mensagem passa a dizer **onde resolver** — hoje o usuário vê
um toast e não tem o que fazer com ele.

## Aceites

Antes do conserto, `xfail(strict=True)` citando ACHADO-26:

1. **Zerar o saldo pelo desvio e concluir o projeto é recusado.** É o achado
   inteiro numa asserção.
2. Cada veredito pela fila, isolado — inclusive *não se aplica* sem motivo
   sendo recusado e *ainda vai chegar* mantendo o projeto aberto.
3. **Controle positivo:** os usos legítimos de `resolver-saldo-provisao`
   (impostos, custo financeiro) continuam funcionando. Sem ele, uma restrição
   ampla demais passaria nos outros.
4. **Fluxo completo pela tela:** dar vereditos na fila, concluir o projeto, e
   o custo aparecer em `5.1.01`. É o aceite que prova que a porta da frente
   existe de verdade.

## O que NÃO fazer

- Não feche o desvio antes de a fila funcionar.
- Não coloque veredito na tela de Conciliação Final.
- Não invente veredito novo nem campo "observação" que faça as vezes de um.
- Não restrinja `resolver-saldo-provisao` sem levantar os usos legítimos.
