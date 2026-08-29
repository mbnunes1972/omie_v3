# ACHADO-12 — o aditivo não é faturado nem cobrado

Grupo 1, item 1. **Medir antes de consertar**, como nas outras.

O achado está fechado e medido (`docs/db/ACHADOS_CONTABEIS.md`, ACHADO-12):
aditivo de R$ 5.000 sobre contrato de R$ 90.000 fica preso em 2.1.06 até a
Conciliação Final inclusive, e nunca entra em cobrança. O lado do custo está
correto — as provisões do aditivo se constituem e se resolvem normalmente. O
defeito é isolado no lado da receita.

O que esta tarefa faz é levantar as costuras antes de mexer, porque o
conserto atravessa mecanismos que hoje não se conhecem.

---

## O que o aditivo é, na regra do negócio (dito pelo usuário, 29/08)

Isto não estava escrito em lugar nenhum do repositório e muda a ordem da
tarefa. Registrar aqui é metade do trabalho.

- **O aditivo cobra diferença de valores do Projeto Executivo** — entre os
  ambientes planejados na venda e os efetivamente encaminhados à produção no
  pedido. Não é venda nova.
- **Aditivo não tem XML novo.** Se existe XML novo, não é aditivo: é
  **contrato novo, projeto novo**.
- **Na maior parte dos casos o aditivo ocorre na aprovação do PE**, antes de
  existir NF-e.

### O que a terceira regra muda, e o que não muda

**Muda o faturamento.** Se o aditivo já existe quando a NF-e é emitida, a
soma da Costura 1 sozinha resolve o caso majoritário: uma emissão, total
certo. A lógica de delta (Costura 2) passa a ser guarda para o caso
minoritário — aditivo assinado depois da emissão —, não o mecanismo
principal.

**Não muda os recebíveis.** Os `Recebivel` são materializados na **geração
do contrato**, que acontece antes da aprovação do PE, sempre. Não existe
momento de aditivo em que eles já não estejam congelados. **A Costura 3
morde em 100% dos casos.** Por isso ela vem primeiro nesta tarefa.

### Revisões de PE — o modelo (usuário, 29/08)

Assim como a negociação tem vários orçamentos, **o Projeto Executivo tem
várias revisões**. Os ciclos de comparação de valores se repetem — inclusive
para ajustar o valor do próprio aditivo — até o cliente aprovar. **Só
interessa a última versão.**

Decisão do usuário: **não existe terceira versão de XML.** A segunda (o XML
de PE) é atualizada quantas vezes for preciso.

O código já faz exatamente isso, e ninguém tinha notado: o upload de PE
(main.py:7589-7599) é get-or-create com sobrescrita em campo — uma linha por
(projeto, ambiente, formato), `arquivo_path`, `valor_atualizado`,
`valor_venda` e `carregado_em` reescritos a cada upload. O
`UniqueConstraint("projeto_nome","pool_ambiente_id","formato")` garante a
unicidade. **O modelo de revisão que o usuário descreve já está
implementado** — o que não existe é histórico: não há número de revisão nem
rastro de qual revisão gerou qual aditivo. Pela regra "só interessa a
última", isso é aceitável; registrar aqui para que seja escolha, não
descuido.

### A divergência a medir antes de decidir

Existem hoje **dois** mecanismos de complemento no código:

| | como obtém a diferença | seleção do ambiente |
|---|---|---|
| **legado** (11c, `renegociar_pe`, `parcela_id` NULL) | exige um **3º upload de XML** por ambiente (`finalidade=complemento` → `formato="xml_compl"`, em `pe/<id>/compl/`, main.py:7560-7575) | flag manual `renegociar_pe` |
| **novo** (spec 2026-08-14, por fase, AF2/11d) | valor **direto do XML de PE** (`formato='xml_pe'`), *"sem exigir o 3º upload `xml_compl` que o mecanismo legado pedia"* (main.py:16800) | decisão "cobrar" em `ConciliacaoPeFase` |

O legado continua vivo e intocado (main.py:17270). Ele não traz ambiente
novo — `ArquivoPE` por desenho *"NÃO cria PoolAmbiente, NÃO vincula a
orçamento"* —, então não viola a regra do usuário no espírito; apenas pede
um arquivo que o mecanismo novo tornou desnecessário.

**DECIDIDO pelo usuário em 29/08: não há terceira versão de XML.** A
direção é o mecanismo novo; o `xml_compl` do legado não deve ser exigido.

**Medir antes de remover** (a decisão é de direção, não ordem de arrancar
código vivo): o legado ainda é alcançável pela UI? Que projetos existentes
dependem dele? O que quebra se `finalidade=complemento` deixar de gravar?
Reporte o custo da remoção — não remova nesta tarefa.

**Medir também a regra de fronteira:** existe alguma guarda que impeça um
XML novo (pool de ambientes novo) de ser anexado a um projeto com contrato
assinado? A hipótese é que a trava `_contrato_assinado` já faça isso — o
`ArquivoPE` foi desenhado justamente para *não* esbarrar nela —, mas é
hipótese, não medição. Se a regra "XML novo ⇒ projeto novo" não estiver
escrita em código nenhum, ela é mais uma proteção por coincidência de
desenho, e já sabemos o que isso vale.

---

## O desenho decidido (não reabrir)

- O `Aditivo` continua entidade própria. Rastreabilidade importa: quem
  vendeu, quando, por quanto.
- **Uma função única responde "qual é o valor do projeto"** = contrato +
  aditivos. Hoje essa função já existe e já se declara única:
  `_valores_segmentados_do_projeto` (main.py:1293), *"Fonte ÚNICA da
  segmentação de um projeto p/ a face fiscal e o wiring contábil"*. Ela é o
  lugar do conserto — não um segundo caminho ao lado dela.
- O acréscimo percorre **o mesmo caminho do contrato**: 2.1.06 →
  faturamento. Nada de rota paralela para aditivo.
- O `Recebivel` passa a contemplar os aditivos.

**Não** criar um `Contrato` novo por aditivo. main.py:13824 é hoje o único
ponto de criação de `Contrato` em todo o código, e essa unicidade é o que
mantém `_valores_segmentados_do_projeto` simples. Um segundo ponto de
criação transforma "o contrato do projeto" em pergunta ambígua.

---

## As costuras a medir

Ordem: **4 → 3 → 1 → 2**. A 4 é hipótese de cobrança em duplicidade e vem
primeiro por isso. A 3 vale sempre; a 1 corrige o caso majoritário; a 2 é
guarda do minoritário e não pode ser escrita antes da 1.

### Costura 4 — revisão DEPOIS da assinatura do aditivo · **começa por aqui**

Hipótese levantada ao registrar o modelo acima, ainda **não medida**:

1. O upload de PE sobrescreve `valor_venda` sem verificar nada além do gate
   de parcela retida (`_mret.gate_operacao_ambiente`). Não há checagem de
   aditivo já assinado no caminho.
2. `_complemento_diferencas` / `_complemento_diferencas_fase` calculam a
   diferença sempre contra o **contrato** (`_pe_fator_contexto` → `orc_ct`),
   nunca contra "contrato + aditivos já assinados".

Se as duas coisas valerem juntas, uma revisão de PE recebida **depois** de um
aditivo assinado permitiria gerar um segundo complemento que cobra de novo a
mesma diferença — a partir da linha de base do contrato original. É a mesma
família do ACHADO-13.

**Medir:** um segundo complemento é alcançável depois de um aditivo assinado?
O que impede — validação, ou a flag `renegociar_pe` / a decisão em
`ConciliacaoPeFase` sendo consumida? (Se for a segunda, é proteção por
consumo de estado, e já sabemos o que isso vale.) Reproduza com números:
contrato, revisão 1, aditivo assinado, revisão 2, segundo complemento.

**A linha que precisa existir**, seja qual for a medição: **antes da
aprovação do cliente, revisão é sobrescrita livre — é o modelo de trabalho.
Depois da assinatura do aditivo, a diferença já virou lançamento, e mudança
é evento contábil, não sobrescrita.** Hoje nada no código desenha essa linha.

### Costura 1 — o que somar, exatamente

`_valores_segmentados_do_projeto` hoje lê **um** orçamento (o do contrato) e
devolve `val_cont`, `mercadoria`, `servico`, `cfo`, `seg`, `orc`. Somar
aditivos quebra três coisas de uma vez:

- **`cfo`**: é o CMV congelado, lido de `orc.cfo`. Somando orçamentos, soma
  também os CFOs? (Deve — o aditivo tem mercadoria própria — mas confirme
  que o CMV do aditivo já não é reconhecido por outro caminho, senão dobra.)
- **`seg`**: a segmentação é congelada na assinatura e vem dos parâmetros do
  **projeto**, não do orçamento. Um aditivo assinado depois de uma mudança
  de parâmetro herda qual segmentação? Medir o que o código faz hoje.
- **`orc`**: quem passa a ser o `orc` devolvido, se são vários? Quem usa esse
  campo e para quê? Levantar todos os consumidores antes de mudar a
  assinatura da função.

**Medir:** qual predicado seleciona os orçamentos que entram na soma.
`complemento_pe=1` cobre aditivo E complemento por fase (`parcela_id` não
nulo) — são a mesma coisa para efeito de faturamento? Se não, o predicado
precisa distinguir, e a distinção tem que estar no código, não na cabeça de
quem escreveu.

**Reportar:** a lista de consumidores de `_valores_segmentados_do_projeto`,
o predicado proposto, e o que acontece com `cfo` e `seg` em cada caso.

### Costura 2 — faturar o delta, não o total

Costura perigosa, e é onde o ACHADO-12 encosta no ACHADO-13. **Caso
minoritário** (aditivo assinado depois da emissão), mas a regressão que ela
previne atinge o caso majoritário — ver abaixo.

Se o total do projeto cresce depois de a NF-e original já ter sido emitida,
a emissão seguinte tem que faturar **o que ainda não foi faturado**, não o
total novo. Hoje `faturar_segmento` é chamado com o valor do segmento e
`ref_base="fat:"+ref_doc` (main.py, `_fin_faturamento_segmentado_seguro`).

**Medir:**
1. Como `faturar_segmento` decide o que já foi lançado — pela `ref`, por
   soma na conta, ou não decide?
2. Emitir NF-e, assinar aditivo, emitir de novo: o que acontece hoje, conta
   por conta? (Provavelmente nada, porque o valor nem cresce — mas registre
   o comportamento atual antes de mudar.)
3. Com a soma da Costura 1 implementada, a mesma sequência passa a faturar
   duas vezes o valor original? **É a regressão que esta tarefa pode
   introduzir.** Escreva o teste que a pega ANTES de escrever o conserto.

O critério correto é "faturado = o que já saiu de 2.1.06 para 4.1.01/4.2.01
neste projeto", e o que falta é a diferença. Confirme que dá para calcular
isso do livro, sem coluna nova.

### Costura 3 — como o cliente paga o aditivo · **vale em 100% dos casos**

`_materializar_recebiveis_venda_seguro` (main.py:812) tem **um único
chamador**: main.py:13865, dentro da geração do contrato. A guarda de
idempotência é por orçamento (`filter_by(orcamento_id=orc_id)`), então
chamá-la para o orçamento do aditivo materializaria recebíveis próprios,
sem tocar nos do contrato. Mecanicamente, o caminho existe.

O que falta não é código: é **plano de pagamento**. O orçamento de
complemento nasce com `forma_pagamento = None` (o próprio wiring zera, ver
main.py:7885-7891). Sem forma de pagamento, `mod_recebiveis.materializar`
não tem o que materializar — e o código já prevê esse caso com um warning
"verifique manualmente" (main.py:842-846).

**Medir:** o fluxo de assinatura do aditivo
(`POST /api/projetos/<nome>/aditivo/assinar`, main.py:9106-9165) coleta
alguma informação de pagamento? A tela pede? Se não pede, essa é uma
**decisão de produto** e não de contabilidade — reporte e pare aí, não
invente um default.

---

## O que reportar

0. A divergência dos dois mecanismos de complemento, e se a regra "XML novo
   ⇒ projeto novo" está escrita em código ou só no desenho.
1. As quatro costuras, com o que foi medido em cada uma.
2. O teste de regressão da Costura 2, escrito e passando contra o
   comportamento atual (ele tem que ficar verde hoje e continuar verde
   depois do conserto — é isso que ele serve para provar).
3. A decisão de produto da Costura 3, formulada como pergunta, com as
   opções que o código já suporta.

## O que NÃO fazer

- Não criar `Contrato` por aditivo.
- Não adicionar coluna para "valor já faturado" antes de provar que o livro
  não responde isso sozinho.
- Não implementar a soma da Costura 1 sem o teste da Costura 2 no lugar.
- Não escolher forma de pagamento de aditivo por conta própria.
