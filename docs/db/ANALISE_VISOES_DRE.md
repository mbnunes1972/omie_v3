# Análise — as três visões de DRE

Escrito em 29/08/2026, a pedido do Marcelo, sobre o modelo de três visões
de resultado que ele desenhou. Análise gerencial, não parecer contábil.

## O resumo, antes do argumento

As três visões que você desenhou respondem a **três perguntas diferentes**,
e só uma delas é uma pergunta de DRE. Forçar as três no mesmo instrumento
custa caro e entrega menos do que quatro instrumentos separados.

A sua desconfiança sobre a terceira visão está certa, e pela razão exata que
você intuiu: **ela não é uma DRE, é fluxo de caixa.**

---

## Limite 1 — DRE não responde pergunta de caixa

Uma DRE responde "quanto eu ganhei neste período". A propriedade que a
define é o **casamento**: receita e o custo que a gerou reconhecidos no
mesmo período, independentemente de quando o dinheiro se move.

Se você a força a seguir o caixa, ela vira um fluxo de caixa com nome de
DRE — e perde a única coisa que ela faz bem, que é dizer se a operação é
lucrativa **independentemente do calendário de pagamento**. Duas empresas
com a mesma DRE e prazos diferentes têm caixas completamente diferentes; é
justamente isso que a DRE isola de propósito.

## Limite 2 — as duas primeiras visões não são duas verdades

Reconhecer o CMV na venda ou na entrega não são duas políticas igualmente
válidas entre as quais se escolhe por gosto. São a mesma coisa medida em
dois momentos, e **se a estimativa da venda fosse perfeita as duas
convergiriam**.

Ou seja: a diferença entre elas não é ruído a conciliar — **é a informação
principal**. Ela mede o seu erro de estimativa, por rubrica e por projeto.

Isso muda o desenho. Você não precisa de duas DREs; precisa de **uma DRE
mais um relatório de variância** — provisionado contra realizado, rubrica a
rubrica. E esse relatório é o instrumento que mais melhora decisão no seu
negócio, porque responde "eu sei orçar?" com número em vez de impressão.

O mecanismo de provisões que já existe produz exatamente esse dado. Ele só
não está sendo lido como variância.

## Limite 3 — três visões são três livros, e divergência vira indistinguível de bug

Este é o risco que você levantou, e ele é maior do que parece.

Se cada visão tiver a **própria lógica de lançamento**, você passa a ter
três contabilidades. Quando duas divergirem — e vão divergir — ninguém
consegue dizer se a diferença é intencional (as visões *devem* diferir) ou
se uma delas quebrou. Conciliar vira trabalho permanente, e o pior tipo:
trabalho que não termina e não pode ser automatizado, porque não há
resposta certa contra a qual comparar.

É a mesma doença que apareceu quatro vezes nesta auditoria — duas fontes
descrevendo a mesma realidade — só que aqui seria **intencional**, o que a
torna imune ao tipo de teste que a gente escreveu esta semana.

**A saída: um livro, várias lentes.** Todo evento lança uma vez só, nos
mesmos `lancamento`, com dimensões suficientes para que cada visão seja uma
**consulta**, não uma contabilidade paralela. As dimensões mínimas:

- data do evento (quando aconteceu)
- data de competência estimada (quando se esperava que acontecesse)
- data de realização (quando de fato se completou)
- rubrica, projeto, loja

Com isso, a invariante fica testável: **as visões têm que se reconciliar
entre si por construção**, e a diferença entre quaisquer duas tem que ser
explicável por uma ponte nomeada. Isso é verificável por teste, como tudo
que a gente fez esta semana. Três livros não são.

## Limite 4 — a terceira visão precisa de dado que você ainda não tem

"Resultado real de riscos associados às dívidas assumidas" exige
probabilidade de inadimplência do recebível, probabilidade de estouro de
custo de obra, exposição de assistência e garantia. Nada disso está nos
lançamentos. Sai de **histórico** — e o sistema é novo, as bases acabaram de
ser zeradas.

Construir essa visão agora produz precisão falsa: números com duas casas
decimais em cima de premissas inventadas. O que dá para fazer hoje é
registrar a **exposição** (quanto está em aberto, com que idade, em que
projeto), e deixar o risco entrar quando houver base para estimá-lo.

## Limite 5 — a assimetria do negócio é real, e merece instrumento próprio

Em planejados o dinheiro entra cedo (sinal, parcelas, antecipação) e o custo
sai tarde (fábrica, montagem, assistência), com meses entre um e outro.

Consequência: a empresa pode parecer lucrativa e estar morrendo, ou parecer
quebrada e estar bem. Essa é a razão legítima por trás das suas três visões.

Mas o instrumento certo para essa assimetria não é uma variante de DRE — é
um **relatório de carteira**: vendido e não entregue, com o custo comprometido
contra ele, o caixa já recebido, e a margem esperada. É isso que responde
"até onde posso me alavancar", e responde muito melhor que qualquer DRE.

---

## O que eu proporia no lugar

**Um livro** — todo evento lança uma vez, com as dimensões acima.

**Quatro instrumentos**, cada um respondendo uma pergunta:

1. **DRE por competência** — política de reconhecimento decidida **uma vez**.
   Para planejados, a recomendação é reconhecer receita e custo na entrega:
   a venda é um contrato, não um resultado. O resultado nasce quando a
   obrigação é cumprida.
2. **Variância provisão × realizado** — por rubrica e projeto. Responde
   "eu sei orçar?". É o instrumento de maior retorno e o dado já existe.
3. **Fluxo de caixa realizado e projetado** — a pergunta de caixa, com o
   nome de caixa.
4. **Carteira** — vendido não entregue: valor, custo comprometido, caixa
   recebido, margem esperada, idade. Responde a pergunta da alavancagem.

## Como suas três perguntas se respondem

**"Qual o resultado se eu antecipar o meu problema?"**
DRE por competência somada à variância. Se as provisões forem
sistematicamente otimistas, a variância mostra em quanto — e aí "antecipar o
problema" deixa de ser cenário e vira correção da premissa.

**"Até onde posso usar caixa e crédito para me alavancar?"**
Carteira mais fluxo de caixa projetado. A DRE não tem essa resposta e nunca
vai ter, em nenhuma das suas variantes.

**"Qual é o resultado real de riscos?"**
Ainda não é respondível. O que dá para entregar hoje é a exposição; o risco
entra quando houver histórico. Prometer isso agora é inventar número.

---

## Ressalva

Isto é análise de desenho gerencial, não parecer contábil. O uso de partidas
dobradas para retratar ativos e passivos é a escolha certa e deve continuar
— é ela que torna as invariantes testáveis. Mas antes de qualquer visão
virar base de decisão com dinheiro real, vale um par de olhos de contador
sobre a política de reconhecimento do item 1.
