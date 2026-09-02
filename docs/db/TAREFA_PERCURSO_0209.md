# TAREFA — o percurso de 02/09 (v2026.09.02-beta1)

Sete itens do percurso manual do Marcelo. Dois são medição antes de
conserto, um é frente própria, e um deles corrige uma decisão minha.

**Ordem:** C1 (medir) primeiro — ele pode mudar o que os outros significam.

---

## C1 · MEDIR · O custo mudou onde a venda não mudou

**O achado do dia, e nenhuma linha de código deve mudar antes da medição.**

Banheiro Social e Suite Master, mesmo arquivo de PE do contrato (só o nome
do arquivo trocado, palavra do Marcelo):

| ambiente | venda contrato | venda PE | Δ venda | CFO venda | CFO PE | Δ custo |
|---|---|---|---|---|---|---|
| Banheiro Social | 2.120,40 | 2.120,40 | **0,00** | 953,40 | 1.029,67 | **+76,27** |
| Suite Master | 35.321,93 | 35.321,93 | **0,00** | 15.882,09 | 16.675,84 | **+793,75** |

A venda bate **ao centavo**; o custo não. E as duas grandezas saem do
**mesmo parser**: `PoolAmbiente.order_total` (main.py:12152) e
`mod_pe_comparacao.extrair_cfo_pe` somam `order_total` item a item, sobre
`promob_grupos.ler_xml_str`, com a mesma iteração. Sobre o mesmo XML elas
**não podem** discordar.

Verificado e descartado: o nome do arquivo não entra na conta —
`_ler_xml_root` só o usa como fallback de `DESCRIPTION`. Renomear não muda
nada.

E a razão não é um fator uniforme: 1.029,67/953,40 = **1,080** e
16.675,84/15.882,09 = **1,0500**. Percentuais diferentes por ambiente, o que
aponta para **conteúdo**, não para uma multiplicação aplicada de um lado só.

**A medição, três números por ambiente:**

1. `PoolAmbiente.order_total` como está gravado no banco;
2. `extrair_cfo_pe` recomputado a partir de `PoolAmbiente.ambientes_json`
   (o conteúdo já parseado que ficou guardado na importação);
3. `ArquivoPE.valor_atualizado` e o recomputo sobre o arquivo de PE.

**O par que discordar nomeia a causa:**

- (1) ≠ (2) → `order_total` foi alterado depois da importação — procure
  quem escreve nesse campo (substituição de custo, ajuste de fábrica,
  reimportação) e o achado é "o número gravado deixou de corresponder à sua
  fonte".
- (2) ≠ (3) → os arquivos são genuinamente diferentes; então o achado é
  outro, e menor: a tela deixa o usuário acreditar que carregou o mesmo
  arquivo. Nesse caso reporte a diferença item a item entre os dois
  conteúdos — quais refs entraram ou saíram.

**Reporte a medição e pare.** O conserto depende do que ela disser.

---

## C2 · O Δ custo sem Δ a cobrar não é "nada a decidir" — erro meu no B4

O Marcelo, item 7: *"apesar de surgir uma diferença inexplicável no Projeto
Executivo, o sistema não pediu veredito"*. Ele tem razão, e o motivo é o
B4, que eu especifiquei.

O B4 estava certo no que corrigiu: **cobrar e estornar são decisões sobre o
cliente**, e sem Δ a cobrar não há o que cobrar nem estornar. Eu fui além do
necessário ao escrever *"não é pendência"*, tratando Δ custo como pura
referência. **Não é.** O custo subiu 76,27 e 793,75 nesses dois ambientes,
o preço não subiu, e isso significa exatamente uma coisa: **a margem caiu, e
a empresa absorveu.** Esse é um fato do resultado, não uma referência de
conferência.

O que se perdeu ao remover a linha da pendência não foi a decisão — foi o
**registro de que alguém viu**. A rota antiga gravava "Absorver R$ 0,00",
que era uma decisão sobre nada *a cobrar*, mas provava que um par de olhos
passou ali.

**O desenho:** quando Δ a cobrar é zero e Δ custo não é, a linha não oferece
as quatro opções — oferece **uma**: um reconhecimento de que o custo mudou e
fica com a empresa, com o valor do Δ custo à vista. Não é escolha entre
alternativas; é ciência de um fato. E conta como pendência da fase, porque
esse é o ponto.

Quando Δ a cobrar **e** Δ custo são zero, aí sim não há nada — a linha diz
"sem diferença" e não pendura a fase.

**Teste:** ambiente com Δ custo ≠ 0 e Δ a cobrar = 0 pendura a fase até o
reconhecimento; ambiente com os dois zerados não pendura. Controle
negativo nos dois sentidos.

**Depende do C1:** se a medição mostrar que o Δ custo daqueles dois
ambientes é artefato e não fato, o reconhecimento continua certo — mas o
número que ele reconhece muda.

---

## C3 · Duas portas para o mesmo destino (regra nova no ROTEIRO)

Ler a seção "Duas portas para o mesmo destino — a regra de 02/09" no
`ROTEIRO.md`. Ela é regra de processo, obrigatória daqui em diante.

O caso que a originou: **"Aprovação Financeira" e "Solicitação de Medição"
aparecem dentro do bloco do contrato E ao lado da Visão Geral.** Decisão do
Marcelo: ficam só ao lado da Visão Geral.

E **o botão "Solicitação de Medição" não funciona** — meça antes de apagar:
qual dos dois está morto, e se o que sobrevive faz o que o nome promete.
Um botão órfão que ninguém mantém é o produto natural de abrir a segunda
porta sem perguntar; é o exemplo vivo da regra.

---

## C4 · "Já aprovado" tem que aparecer, não piscar

Depois do B3, reaprovar a AF1 já não pede senha — correto. Mas a tela
**apenas pisca**. O Marcelo esperava um box dizendo "Aprovação Financeira já
realizada".

É o ACHADO-36 na sua forma mais pura: a recusa existe, está certa, e é
invisível. `avisoPopup`, centro da tela, com OK.

Enumere os irmãos: toda ação que agora recusa por estado depois do B3 diz
por que recusou, ou não passou.

---

## C5 · A Solicitação de Medição precisa de data

Pedido do Marcelo, funcionalidade ausente:

- campo de **data de agendamento** da medição;
- com o projeto desmembrado em fases, **uma data por fase**;
- e o registro **alimenta a agenda do projeto**, alterando a programação
  automática que o cronograma padrão montou na assinatura.

O último ponto é o que decide o item: não é um campo de texto, é uma
entrada que **substitui uma previsão** que o sistema já tinha gerado
sozinha. Meça primeiro onde essa programação automática vive e quem mais a
lê, antes de escrever nela.

---

## C6 · O modal de comparação quebra o número

Terceira imagem: no modal de comparação, `R$` fica numa linha e o número na
linha de baixo. Modal um pouco maior, fonte um pouco menor, e o valor com
`white-space: nowrap` — o símbolo e o número são uma coisa só, nunca duas
linhas.

Prova por captura, como no B5.

---

## C7 · FRENTE PRÓPRIA · O desmembramento em fases não chega nas etapas

Levantado pelo Marcelo, e é grande demais para esta rodada.

> "O desmembramento em fase abre dois braços, que devem ser abertos para
> todas as etapas futuras. A aprovação financeira passa a ser por fase, de
> forma que todas as provisões precisam ser desmembradas proporcionalmente
> nas fases."

Com a delimitação que ele já deu, e que poupa o mais caro:

**As contas de provisão NÃO se desmembram.** A contabilidade continua na
conta consolidada por projeto. O que se desmembra é a **camada de
acionamento**: aprovação financeira e liberações passam a ter botão por
fase, e o valor da aprovação financeira é **proporcional à fase**.

Isso mantém o livro como está — nenhuma migration de plano de contas,
nenhum rateio contábil — e move o corte para onde o usuário opera.

**Não implementar nesta rodada.** O que se faz agora é o levantamento: quais
etapas do ciclo depois do desmembramento assumem hoje que o projeto é um só,
e o que "proporcional" quer dizer em cada uma (proporção de quê — valor de
contrato da fase, CFO da fase, número de ambientes?). Reporte o mapa; a
definição de "proporcional" é decisão do Marcelo.

---

## O que reportar

1. **C1 primeiro**, e pare nele até o resultado ser lido.
2. C2 a C6 com aceite e controle negativo cada.
3. C3 traz também a medição de qual botão está morto.
4. C7 é mapa, não código.
