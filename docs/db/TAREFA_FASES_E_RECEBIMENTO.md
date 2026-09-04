# Fases independentes, recebimento e entrada fiscal

Frente aberta em 04/09/2026, no percurso do `v2026.09.04-beta1` em
Homologação. **Fila: LP-18** (`LISTA_PARALELA.md`) — adiada de propósito para
depois do ciclo de achados. Este arquivo é o desenho, não a ordem de fazer.

**Nada aqui é defeito.** É ausência: o que o sistema não tem. O único defeito
que saiu do mesmo percurso é o ACHADO-49 (o Remover da etapa 12), que foi para
a fila ativa como F2-20 e não tem relação com o resto deste documento.

**Estado deste documento: DESENHO, sem decisão tomada.** O que está escrito é
o que o Marcelo descreveu, na ordem em que descreveu, mais as perguntas que a
descrição deixou abertas. Nenhuma linha aqui é decisão fechada, e nenhuma
medição de código foi feita para os itens 2 e 3 — quando a frente for
executada, medir antes, como sempre.

## O que motivou

O projeto foi desmembrado em duas fases (Fase 1: Banheiro Social, Suite
Master; Fase 2: Cozinha, Sala Íntima). O sistema trata a etapa como uma coisa
só: carregado um arquivo, a etapa inteira se deu por concluída. Na operação
real as fases andam em ritmos diferentes — houve o caso de a obra exigir que a
Fase 2 seguisse enquanto a Fase 1 ficava sem finalizar.

## Item 1 — implantação do pedido por fase

- carregar pedidos e implantar **dentro de cada fase**, com botões próprios,
  em vez de um par de botões para a etapa inteira
- cada fase conclui sozinha, e o registro é "Fase X concluída", não "etapa
  concluída"
- as fases seguem **independentes**: uma pode avançar com a outra parada
- indicador no painel geral do ciclo quando uma fase seguiu e a outra não —
  o Marcelo sugeriu um selo na aba superior

*Medido em 04/09 (só o que estava à mão, ao investigar o ACHADO-49):* o card
da implantação é `_renderCardImplantacao` em `static/index.html`, etapa de
código `12`, e hoje ele é único para a etapa — a lista de XML, o botão
"Carregar Pedidos" e o "Encaminhar Pedidos à Fábrica" não conhecem fase. A
"Entrega por fase" que aparece acima deles é exibição, não estrutura de ação.

**Em aberto:** onde a fase vive hoje no modelo (a tabela de entrega por fase
já existe — a implantação passa a referenciá-la, ou nasce outra coisa?); o que
"Fase X concluída" faz com a conclusão da ETAPA, que é o que o ciclo usa para
liberar a seguinte.

## Item 2 — Logística e Expedição: o recebimento

Três subfases; o recebimento **não tem ação de concluir o passo**.

Cada fase precisa de:
- **carga de NF-e e de pedidos recebidos**, em campos separados, com relação
  **N:N** — pode haver mais de um pedido para a mesma NF-e e mais de uma NF-e
  para o mesmo pedido (o Marcelo sugeriu um modal próprio)
- **conferência**, numa tela que registra o número de volumes **da nota**
  (pode ser automático, lido da própria nota) e o número de volumes
  **efetivamente recebidos**
- **campo de observações**
- tudo isso **persistido em banco**, não só exibido

E a **Visão Geral de Logística e Expedição** deixa de listar os números de
pedido: passa a ser o resumo do conjunto da fase.

**Não medido.** Nenhuma linha de código foi lida para este item.

## Item 3 — entrada fiscal no recebimento, emissão por fase

Neste formato, **a NF-e de entrada ocorre no recebimento**. Com isso o evento
de emissão fica isolado do resto, e:

- o botão de **emitir passa a ser por fase**
- ao acionar, o sistema pergunta se existe uma **NF-e de Origem** — mostrando
  a lista das NF-e carregadas na fase anterior (o recebimento) — ou se é
  **"Estoque"**
- **Estoque** = itens que não puxam valor de nenhuma NF-e de origem. O usuário
  **digita o preço de venda**. Não há multiplicador: o Markup de Ajuste é um
  multiplicador sobre valores DE FÁBRICA, e no Estoque não há valor de fábrica
  para multiplicar (fronteira registrada na LP-15 em 04/09)

**Em aberto — e é a pergunta que este item deixou sem resposta:** o item de
Estoque entra na nota com preço de venda e **sem custo de fábrica**. De onde
sai o custo dele para a margem e para a DRE — do custo de compra do estoque,
reconhecido em outro momento? Sem isso, um item vendido por esse caminho tem
receita e não tem CMV.

## Por que isto suspendeu o item 5 do bloco fiscal

O item 5 (NF-e H e NF-e P, `TAREFA_BLOCO_FISCAL.md`) foi desenhado supondo que
a emissão é **um evento do projeto**: o projeto não conclui com a P pendente,
marcador "N" enquanto pendura. Este documento move o chão: a entrada é no
recebimento e a emissão é por fase, com origem escolhida. Escrever o item 5
antes de decidir isto é construir sobre chão que se move.

Provavelmente explica também o achado do Bloco B de 03/09 — *"a etapa 15 já é
destravada de propósito hoje, nada na cadeia de conclusão olha pra ela"*: se a
emissão nunca foi um evento único do projeto, destravar era coerente com a
operação, e o gate do item 5 brigaria com ela.

## Ordem sugerida, quando a frente for executada

1. Item 1 (fase como unidade de ação) — é a fundação; os outros dois assumem
   que "fase" existe como coisa que conclui sozinha.
2. Item 2 (recebimento) — cria o dado que o item 3 consome.
3. Item 3 (emissão por fase) — só depois, porque a lista de NF-e de origem que
   ele oferece é exatamente o que o item 2 grava.

Medir antes de cada um. Nenhum destes três foi medido além do que está
anotado no item 1.
