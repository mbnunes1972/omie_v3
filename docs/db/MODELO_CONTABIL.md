# O modelo contábil — o fato, o reconhecimento e as duas visões

Escrito em 05/09/2026, a partir de uma conversa entre o Marcelo e o Claude que
levou cinco rodadas para descobrir que a divergência **não era de número, era
de modelo** — porque o modelo nunca esteve escrito em lugar nenhum. Este
arquivo existe para que essa descoberta não precise ser refeita.

**Como ler as marcações:** `[MEDIDO]` = lido no código, com linha citada.
`[DECIDIDO]` = decisão do Marcelo, com data. `[ABERTO]` = ainda não resolvido —
não implemente sem fechar.

---

## O princípio, em uma frase

**O fato é lançado quando ocorre. O resultado é reconhecido na emissão da NF-e.**

As duas coisas não competem porque moram em contas diferentes:

- **o caixa se move contra o PASSIVO** (Provisões, 2.1.04.x)
- **o resultado se move contra o ATIVO** (Provisões a Apropriar, 1.1.06.xx)

Nenhum lançamento é "guardado para depois". O que é adiado é o
**reconhecimento**, não o **registro**.

## O que está errado hoje

`[MEDIDO]` `mod_contabil.efetivar_provisao` (linha 2137) lança as **duas pernas
soldadas, no mesmo ato**:

1. `reconhecer_despesa_efetivacao` (ref `X:d`) — `D 5.x Despesa × C 1.1.06.xx a Apropriar`
2. (ref `X`) — `D 2.1.04.x Provisão × C 1.1.01 Caixa` (`direto`) ou `× 2.1.01 Fornecedores a Pagar` (`a_prazo`)

Consequência: o custo cai na competência do **pagamento**, e a receita cai na
competência da **NF-e**. Numa operação em que o contrato antecede a entrega em
meses, isso é descasamento **estrutural**, não eventual. Nenhuma DRE conserta
isso depois — a competência já foi carimbada no lançamento.

**A correção é separar as duas pernas.** A perna de caixa fica na data real do
pagamento; a perna de competência dispara no reconhecimento.

## O exemplo, com seis contas

Venda de **R$ 100.000** em **janeiro**. Provisão única de **R$ 60.000**.
Fornecedor pago em **fevereiro** por **R$ 55.000** (gastou menos). Cliente paga
em **março**. NF-e em **maio**.

| quando | lançamento | DRE |
|---|---|---|
| jan · contrato | `D 1.1.02 Contas a Receber 100.000 × C 2.1.06 Receita a Realizar 100.000` | — |
| jan · contrato | `D 1.1.06 Provisões a Apropriar 60.000 × C 2.1.04 Provisões 60.000` | — |
| fev · paga fornecedor | `D 2.1.04 Provisões 55.000 × C 1.1.01 Caixa 55.000` | — |
| mar · cliente paga | `D 1.1.01 Caixa 100.000 × C 1.1.02 Contas a Receber 100.000` | — |
| **mai · NF-e** | `D 2.1.06 Receita a Realizar 100.000 × C Receita 100.000` | **+100.000** |
| **mai · NF-e** | `D Custo 60.000 × C 1.1.06 Provisões a Apropriar 60.000` | **−60.000** |
| conciliação | `D 2.1.04 Provisões 5.000 × C Receita de Conciliação 5.000` | **+5.000** |

Resultado: **45.000**. Caixa: −55.000 +100.000 = **45.000**. Fecha.

**E só fecha porque o resíduo foi ao resultado.** Se ele fosse cancelado contra
o ativo, não haveria contra o quê — o ativo já foi integralmente consumido pelos
60.000 do reconhecimento. Esta é a prova de que, neste modelo, o resíduo
**tem** que virar resultado.

## O que se reconhece na emissão: o provisionado INTEGRAL

`[DECIDIDO 05/09]` Na emissão reconhece-se o **custo provisionado inteiro**, não
só o já incorrido. Se fosse só o incorrido, a parte restante cairia em outra
competência — exatamente o descasamento que o modelo existe para evitar. A
provisão é a melhor estimativa do custo daquela venda; é ela que casa com a
receita.

**Consequência estrutural: depois da NF-e o par se desfaz de propósito.**

- o **ativo** "a Apropriar" é integralmente consumido — vai a zero
- o **passivo** Provisão continua aberto pelo que ainda não foi desembolsado

Esse passivo remanescente passa a se comportar como provisão comum: consumido
pelo pagamento quando ele ocorrer (`D Provisão × C Caixa`, sem tocar a DRE — o
custo já foi reconhecido), e o que sobrar ou faltar vai às contas de
Conciliação, na competência da conciliação.

## O indicador de desbalanceamento

O par ativo × passivo mede a distância entre o **resultado** e o **dinheiro**,
por projeto, e serve nas duas fases com o sinal trocado pela emissão:

| fase | quadro | leitura |
|---|---|---|
| antes da NF-e | Provisão zerada, "a Apropriar" aberta | pagou e ainda não reconheceu → **caixa vazio** |
| depois da NF-e | "a Apropriar" zerada, Provisão aberta | reconheceu e ainda não pagou → **caixa a desembolsar** |

`[ABERTO]` Nenhuma tela mostra isso hoje. A Fila de Provisões olha só o passivo
(`provisoes_em_aberto`, grupo 2.1.04.x) — e **o ativo é que prova que a DRE
recebeu a despesa**. Um projeto com todas as provisões zeradas e o "a Apropriar"
cheio é um projeto com custo faltando no resultado, e hoje ele passaria por
resolvido. É irmão do `relatorio_projetos_encerrados_por_reversao` (ACHADO-16).

## O que difere e o que não

`[DECIDIDO 05/09]` O critério não é "custo do produto × despesa do período" — é
o do **CPC 47 / IFRS 15**:

- **custos incrementais de obtenção do contrato** (comissão de venda, comissão
  de arquiteto vinculada àquela venda) → ativa e reconhece **com a receita**
- **custos para cumprir o contrato** (fábrica, frete, medição, projeto
  executivo, montagem, insumos) → ativa e reconhece com a receita
- **despesa de período** (prospecção geral, viagem não vinculada, administrativo)
  → reconhece quando incorre

`[MEDIDO 05/09, F2-26]` A classificação **rubrica a rubrica** sob esse critério,
preenchida até a leitura preliminar — **a decisão final é do Marcelo** (ver tabela
completa na próxima seção). O agrupamento hoje no código (`mod_provisoes._RUBRICAS`
× `_RUBRICAS_CUST_AD` × `_RUBRICA_CUST_FIN` × `_RUBRICA_CUST_FAB`) foi criado por
OUTRO motivo (evitar dobrar o Cust_Var) e não corresponde 1:1 à classificação do
CPC 47 — as duas grades são independentes; a coluna "grupo hoje" na tabela existe
só pra rastrear a rubrica até o código, não porque o agrupamento atual seja o
critério certo.

## A classificação CPC 47, rubrica a rubrica (medido 05/09, F2-26)

As 21 contas do grupo `2.1.04.x`, com a leitura preliminar sob o critério da seção
anterior. `[MEDIDO]` até a penúltima coluna (código lido, grupo hoje, entra no
Cust_Var, timing típico no ciclo); a última coluna é leitura, não decisão —
`[ABERTO]`, aguarda o Marcelo.

| código | nome | grupo hoje | entra no Cust_Var? | quando incorre no ciclo | leitura preliminar CPC 47 |
|---|---|---|---|---|---|
| 2.1.04.01 | Comissão | excluída (`_PROV_PAINEL_EXCLUI`) | não | — | n/a — sem mecanismo ativo (ACHADO-05), fora do painel |
| 2.1.04.02 | Montagem | `_RUBRICAS` (prov_mont) | sim | depois da entrega — serviço de instalação na casa do cliente | para cumprir o contrato (obrigação de entregar montado) |
| 2.1.04.03 | Garantia | `_RUBRICAS` (prov_gar) | sim | depois da entrega, ao longo do tempo — reparos sob garantia | para cumprir o contrato, mas é garantia tipo-assurance (CPC 47/CPC 25) — provisão de custo esperado, não um contrato de serviço à parte |
| 2.1.04.04 | Devolução | excluída (`_PROV_PAINEL_EXCLUI`) | não | — | n/a — sem mecanismo ativo, fora do painel |
| 2.1.04.05 | Assistência Técnica | `_RUBRICAS` (assist) | sim | depois da entrega, ao longo do tempo — chamados de atendimento | para cumprir o contrato — mesma ressalva de assurance-warranty da Garantia |
| 2.1.04.06 | Custo de Fábrica | `_RUBRICA_CUST_FAB` (base do Cust_Var, não soma) | é a BASE, não uma parcela somada | antes da entrega — produção/aquisição na fábrica | para cumprir o contrato — o COGS primário da venda |
| 2.1.04.07 | Frete de Fábrica | `_RUBRICAS` (frete_fab) | sim | antes da entrega — transporte fábrica→loja | para cumprir o contrato |
| 2.1.04.08 | Frete Local | `_RUBRICAS` (frete_loc) | sim | perto da entrega — transporte loja→cliente | para cumprir o contrato |
| 2.1.04.09 | Insumos Locais | `_RUBRICAS` (ins_loc) | sim | perto da entrega — material complementar na instalação | para cumprir o contrato |
| 2.1.04.10 | Comissão de Medidor | `_RUBRICAS` (com_med) | sim | cedo, antes da fábrica produzir — medição do ambiente | para cumprir o contrato (etapa necessária pra entregar certo, não pra fechar a venda) |
| 2.1.04.11 | Comissão de Projeto/Executivo | `_RUBRICAS` (com_proj_exec) | sim | cedo, antes da fábrica produzir — produção do projeto executivo | para cumprir o contrato (mesma razão da Medição) |
| 2.1.04.12 | Retenção de Comissão de Vendas | `_RUBRICAS` (com_venda) | sim | na venda, mas com retenção/liberação num marco do ciclo (nome sugere holdback) | incremental à obtenção do contrato — o exemplo clássico do CPC 47 |
| 2.1.04.13 | Impostos | rota própria (`_PROV_FORA_DO_VEREDITO`, ACHADO-01) | sim (Prov_Imp) | na emissão da NF-e — fato gerador fiscal | não é custo de contrato — é DEDUÇÃO da receita, tratamento à parte (já com rota própria) |
| 2.1.04.14 | Outros Fornecedores | `_RUBRICAS` (out_forn) | sim | perto da entrega — fornecedor não-Dalmóbile | para cumprir o contrato (mesma família de Frete/Insumos) |
| 2.1.04.15 | Comissão de Arquiteto | `_RUBRICAS_CUST_AD` (com_arq) | não (Cust_Ad) | na venda — indicação/referência daquela venda específica | incremental à obtenção do contrato — o outro exemplo que o próprio CPC 47 cita |
| 2.1.04.16 | Programa de Fidelidade | `_RUBRICAS_CUST_AD` (pro_fid) | não (Cust_Ad) | na venda — incentivo ligado a fechar aquela venda | incremental à obtenção do contrato, SE for de fato vinculado a esta venda (a confirmar caso a caso) |
| 2.1.04.17 | Custo de Viagem | `_RUBRICAS_CUST_AD` (cust_via) | não (Cust_Ad) | variável — depende do motivo da viagem | ambíguo: visita ao cliente antes de fechar → obtenção; viagem ligada à execução → cumprimento; a rubrica não distingue a natureza |
| 2.1.04.18 | Brinde | `_RUBRICAS_CUST_AD` (brinde) | não (Cust_Ad) | no fechamento da venda — brinde de negociação | incremental à obtenção do contrato — incentivo de fechamento |
| 2.1.04.19 | Custo Financeiro | rota própria (`_PROV_FORA_DO_VEREDITO`, ACHADO-01) | sim (Cust_Fin, base separada) | ao longo do parcelamento — custo do crédito ao cliente | não é custo de contrato (obtenção/cumprimento) nem despesa de período no sentido do CPC 47 — é componente financeiro da transação (IFRS 15 tem guidance própria pra isso) |
| 2.1.04.20 | Custo Especial | `_RUBRICAS_CUST_AD` (cust_esp) | não (Cust_Ad) | variável — item ad-hoc do orçamento, não rateado | depende do motivo específico do lançamento — mesma família de natureza mista da Viagem |
| 2.1.04.21 | Comissão Administrativa | `_RUBRICAS` (com_adm) | sim | overhead administrativo, % sobre Val_Liq, constituído no fechamento | despesa de período — é o próprio exemplo que o CPC 47 dá ("administrativo"), a rubrica só está no Cust_Var hoje por convenção do motor, não por natureza |

## A classificação, decidida (05/09/2026)

`[DECIDIDO]` Sob o CPC 47, "incremental à obtenção" e "para cumprir o contrato"
têm o **mesmo destino** — os dois ativam e reconhecem com a receita. A distinção
serve para justificar, não para decidir. Logo a coluna final tem três valores:
**difere**, **rota própria**, ou **sem mecanismo**.

**Das 21 contas, 17 diferem até a emissão.** As quatro restantes:

| conta | destino | quando | onde na DRE |
|---|---|---|---|
| `2.1.04.13` Impostos | rota própria | na emissão, com a receita | **dedução da receita bruta** — nunca custo nem despesa. Variância em `4.3.01`, na linha de dedução |
| `2.1.04.19` Custo Financeiro | rota própria, **por ramo** (ver abaixo) | ver abaixo | grupo financeiro, abaixo do resultado operacional |
| `2.1.04.01` Comissão | **sem mecanismo — remover** | — | — |
| `2.1.04.04` Devolução | **sem mecanismo — a construir** | na competência da ocorrência | **redução de receita**, não custo |

**Por que a Comissão Administrativa (`2.1.04.21`) difere**, contra a leitura
preliminar que a tratava como despesa de período: `[DECIDIDO, razão do Marcelo]`
ela é um **percentual da venda atribuído ao staff da loja**, de papel semelhante
ao da comissão do vendedor. É obrigação com terceiro e incremental à obtenção do
contrato — não é rateio de overhead. Difere como as demais.

**Por que a Comissão (`2.1.04.01`) sai:** `[MEDIDO]` ela nasceu no primeiro motor
de eventos (`b00fb63`, "5 regras do .docx §5"), antes de existir o fluxo real de
comissão. Quando ele foi construído virou a `2.1.04.12` (Retenção de Comissão de
Vendas) e a `01` ficou órfã — o ACHADO-05 provou o evento `pagamento_comissao`
morto. E o caso "comissão eventual" já tem endereço: `despesa_avulsa`, criada em
07/08 para despesa direta sem provisão de projeto.

## A regra geral da variância

`[DECIDIDO 05/09]` **A variância nunca reabre a competência anterior.** Ela entra
na competência em que se torna conhecida, **na seção da DRE a que o item original
pertence**:

- variância de **custo de contrato** → bloco de **Conciliação**, isolado
  justamente para não contaminar a margem operacional do mês corrente
- variância de **imposto** → linha de **dedução de receita** (`4.3.01`)
- variância de **retenção financeira** → `4.4.05 Ajuste de Retenção Financeira`,
  no momento da conferência da retenção (= mês da antecipação)

Em todos os casos, o relatório de **margem por projeto** atribui a variância ao
projeto de origem, independentemente do mês em que ela tocou o resultado. A DRE
classifica por natureza; o relatório de projeto agrega por origem.

## O que entra em Contas a Receber no contrato: o VAVO

`[MEDIDO]` Não é o Val_Cont. O ACHADO-02 (30/08) decidiu e escreveu a razão no
código (`main.py`, antes de `registro_venda_contrato`):

> *"registra o VAVO — não o Val_Cont cheio — em Receita a Realizar
> (1.1.02 × 2.1.06); não toca a DRE. **O preço do móvel não muda conforme a forma
> de pagamento** — o custo financeiro (Val_Cont − VAVO) segue rota própria,
> abaixo, por ramo."*

É o tratamento que o CPC 47 pede quando há componente financeiro relevante:
registrar a venda pelo preço à vista e separar o financiamento.

**Os dois ramos do custo financeiro (Val_Cont − VAVO), decididos em 30/08:**

- **financeira** (Aymoré/Cartão): a retenção esperada é **posição de balanço —
  nada no resultado**. Só a **diferença** entre a retenção esperada e a real toca
  o resultado, em `4.4.05`, na conferência. Não é despesa financeira corrente.
- **loja / loja_antecipação**: **receita financeira a apropriar** (capital
  próprio, sem despesa), *pro rata temporis* ao longo das parcelas. O deságio do
  banco na antecipação é custo **separado**, só no evento da antecipação.
  `[MEDIDO]` A estrutura já existe: `1.1.07 Recebíveis de Parcelamentos` carrega
  **só os juros**, com o VAVO permanecendo em `1.1.02`.

Consequência a manter escrita: no ramo **loja**, como os juros correm ao longo
das parcelas, **o resultado daquela safra só fecha quando a última parcela
correr**. É a natureza da conta, não defeito — mas sem esta nota alguém olha uma
safra entregue e conclui que falta receita.

## As contas de Conciliação

`[DECIDIDO 05/09]` Duas contas novas — **Receita de Conciliação** e **Despesa de
Conciliação** — recebem os resíduos apurados na conciliação final, na
competência em que a conciliação ocorre.

Conceitualmente isso é **mudança de estimativa**: a norma manda tratá-la
prospectivamente, no período em que a diferença se torna conhecida, sem reabrir
a competência anterior. É o que o modelo faz.

**Onde ficam na DRE:** depois do resultado operacional do período, em bloco
próprio e em destaque, rotulado como ajuste de safras anteriores — nunca no topo
junto da receita de venda, que costuma ser base de comissão, meta e indicador.
Se possível, o bloco **abre por safra**: isso transforma o que seria ruído em
medida da qualidade do provisionamento.

## Os três destinos de um gasto de projeto

`[DECIDIDO 06/09, F2-30 Fatia 3]` Uma compra complementar do fornecedor,
descoberta na entrega — algo que faltou, que o cliente pediu a mais, que a
fábrica cobrou além do previsto — tem **três destinos possíveis, e só três**:

1. **Consome a provisão da rubrica**, quando ela existe e tem saldo — é
   efetivação normal, a margem **não muda** (era previsto, o gasto real ficou
   dentro do que já se esperava para aquela rubrica).
2. **Excede a provisão da rubrica** — é falta: antes da emissão, aumenta a
   própria provisão (a estimativa estava baixa, corrige-se prospectivamente);
   depois da emissão, é o veredito **Absorver** → **Despesa de Conciliação**
   (`5.7.01`, ver seção acima — resíduo de uma provisão que existiu).
3. **Não corresponde a nenhuma rubrica** — a compra não é Montagem, não é
   Garantia, não é nenhuma das ~17 famílias de despesa em tempo real; é
   **despesa avulsa**, na competência em que ocorre, na conta própria
   `5.3.22 Despesa Avulsa de Projeto` (`mod_contabil.despesa_avulsa`, com
   `projeto_id` — F2-30 Fatia 2).

**A porta é DERIVADA, nunca digitada.** O operador escolhe **o que foi
comprado** — nunca **onde lançar**. Se a rubrica escolhida tem provisão com
saldo, o sistema oferece consumir; se não tem (ou não existe rubrica
correspondente), oferece avulsa. O mesmo princípio de
`vereditos_validos_para_saldo`/ACHADO-41: a tela nunca oferece o que o modelo
não aceitaria — quem decide QUAL dos três destinos é o estado da provisão, não
o dedo de quem está lançando.

**NÃO CONFUNDIR avulsa com variância.** Despesa avulsa nunca teve provisão —
por definição, ninguém estimou aquele gasto antes. Conciliação (`4.5.01`/
`5.7.01`) é o resíduo de uma provisão que **existiu e fechou** com sobra ou
falta. Misturar as duas contaminaria o bloco de Conciliação, que existe
especificamente para medir a **qualidade do provisionamento** — um gasto que
nunca foi provisionado não é ruído de estimativa, é outra categoria de evento
inteira. `despesa_avulsa` recusa em código as duas contas de Conciliação como
`codigo_despesa` (ValueError), pelo mesmo motivo que a porta é derivada: não
dar a opção errada é melhor que confiar em ninguém escolher errado.

**Consequência esperada, a registrar:** como a despesa avulsa é por definição
**imprevista**, ela nunca aparece em `_PROV_DESPESA_POR_ATIVO` (a família de
17 rubricas que `margem_projetada` lê no ativo para estimar o "pior caso" —
ver "O indicador de desbalanceamento", acima). Isso significa que
`margem_projetada`, calculada ANTES da compra complementar ser descoberta,
nunca a antecipava — não havia como. Depois que a despesa avulsa é lançada,
`margem_realizada` (`margem_contribuicao`) cai imediatamente (ela entra pelo
grupo `5.3`, dentro de `comissao`), e como `margem_projetada` é derivada dela
(`margem_contribuicao − não_reconhecido`), a queda se propaga junto — sem
duplicar e sem sumir. A divergência real está no **histórico do projeto**: a
projeção que existia ANTES da descoberta e a realizada de DEPOIS diferem
exatamente por esse valor. É o retrato correto de uma surpresa genuína — não
um defeito do cálculo.

## As duas visões

`[DECIDIDO 05/09]`

**A DRE é a Diferida** — competência na emissão/entrega. É ela que fecha com o
balanço e é ela que o contador assina. Reconhecer resultado na assinatura do
contrato seria reconhecer receita antes de entregar; não é aceitável e não será
feito.

**A Antecipada não é uma DRE — é um recorte gerencial por safra de contratos.**
E, o mais importante: **ela não precisa de lançamento nenhum**. São os MESMOS
lançamentos, reagrupados pela data do contrato em vez da data da emissão.
Nenhuma conta nova, nenhum evento novo, nenhuma segunda verdade no razão.

Isso muda o custo da Fase 4: **um razão, uma DRE, dois recortes.**

`[ABERTO]` O nome. "DRE Antecipada" convida alguém a apresentá-la como
demonstração contábil. Sugerido: "Resultado por Safra" ou "Resultado da Venda".

Por que ela vale a pena: com contrato em janeiro e entrega em maio, a DRE de
janeiro não diz nada sobre a qualidade da venda de janeiro, e a de maio mistura
safras. Sem a visão por safra não se avalia desconto, comissão nem margem por
consultor. É gestão, não contabilidade — por isso convivem sem competir.

## O que isso implica no que já está construído

**Superfície de código, medida em 05/09:**

| o quê | tamanho |
|---|---|
| `efetivar_provisao` | **5 chamadores**, em `main.py`, `mod_assistencias.py`, `mod_contabil.py`, `mod_folha.py` |
| `resolver_saldo_provisao` | **5 chamadores** |
| eventos `reconhecimento_despesa_*` | **15 rubricas** |
| arquivos de teste que tocam as três funções | **28** |
| — dos quais asseguram especificamente a doutrina de 07/08 | **7** `[MEDIDO 05/09, F2-26]` |

A solda das duas pernas está concentrada numa função só — por isso separá-las é
viável. **O custo real não está nos 28 arquivos — está nos 7** que de fato
travam "sobra/falta cancela contra o ativo SEM tocar a DRE" (checagem direta de
uma conta 4.4.02/5.6.10/5.x ficando em zero, não só do saldo da provisão
zerando — isso os outros 21 também verificam, e continua verdadeiro no modelo
novo). Só estes 7 mudam de SIGNIFICADO, não só de asserção — precisam ser
rederivados, não remendados. Os outros 21 tocam `efetivar_provisao`/
`reconhecer_despesa_efetivacao`/`resolver_saldo_provisao` por outros motivos
(idempotência, DRE por projeto, devolução, centro de custo, partida dobrada,
ciclo completo, guardas/exclusões de Impostos e Custo Financeiro — que têm
rota própria e não fazem parte desta doutrina) e continuam válidos:

- `tests/test_fase_d_reconciliacao.py` — `test_resolver_saldo_sobra_cancela_sem_receita`
  / `test_resolver_saldo_falta_cancela_sem_despesa_extra` (4.4.02/5.6.10 == 0)
- `tests/test_fase_d2_reclass.py` — `test_sobra_custo_fabrica_cancela_sem_dre`
  (4.4.02 == 0 pro Custo de Fábrica especificamente)
- `tests/test_fase_d2_conciliacao_final.py` — `test_conciliar_final_resolve_sobra_e_falta_com_veredito`
  (4.4.02/5.6.10 == 0 via `conciliar_final`, duas rubricas ao mesmo tempo)
- `tests/test_aceite_achado16.py` — `test_veredito_encerrada_valor_menor_reconhece_custo_real_antes_de_reverter`
  (5.1.01 == só o efetivado; o resíduo não soma na despesa)
- `tests/test_aceite_fila_provisoes.py` — mesma asserção, pela rota da Fila
- `tests/test_custos_adicionais_provisao.py` — `test_cust_esp_nunca_efetivado_exige_veredito_e_nao_se_aplica_cancela_sem_dre`
  (5.3.17/4.4.02 == 0)
- `tests/test_achado34_veredito_da_folha.py` — `test_aceite3_o_livro_nao_muda_na_sobra`
  (4.4.02/5.6.10 == 0 via a porta da folha)

**O que muda de sentido sem quebrar:** o veredito deixa de *cancelar resíduo* e
passa a *levar resíduo ao resultado*. Toda a maquinaria continua valendo — a
Fila (F2-3), o veredito nomeado (ACHADO-34), os vereditos válidos por sinal
(ACHADO-41), o contra-controle de reversão (ACHADO-16), o rastro auditável.
**Nada do que foi feito é desperdiçado**: muda o que o botão lança, não como ele
funciona.

**O que NÃO é afetado:** o bloco fiscal inteiro (emissão, XML, selo, Focus), o
ciclo, permissões e documentos (ACHADOS 30, 49, 52, 58), a LP-18. E o lado da
receita **já está certo**: `[MEDIDO]` o evento `registro_venda_contrato` faz
`D 1.1.02 × C 2.1.06 Receita a Realizar` — passivo, não receita. Metade do
modelo já está construída.

**E não há dado a migrar.** `[MEDIDO 04/09]` Produção tem 1 usuário cadastrado,
0 sessões, 0 upload desde 28/08; Integração e Homologação são base de teste. O
custo desta mudança é código e teste, **não migração de razão**. A mesma mudança
com lojas reais lançando seria reconciliação de competências já carimbadas. Esta
é a janela mais barata que a decisão vai ter.

## Pendências que bloqueiam a implementação

1. `[MEDIDO 05/09, F2-26]` **Não é isso — o recebível não dobra. Mas há um problema
   real, diferente, confirmado ao vivo.** `faturar_segmento` (mod_contabil.py:1559)
   é delta-aware e SPLITA o delta em duas pernas, cada uma seu próprio evento:
   - **perna "adiantado"** (`D 2.1.06 × C 4.1.01/4.2.01`, mod_contabil.py:1461-1464):
     consome o pool de 2.1.06 (`saldo_adiantamento_projeto`, linha 1553) até o limite
     do que ele tem disponível. Esta é a perna que roda em TODO caso real medido.
   - **perna "a_receber"** (`D 1.1.02 × C 4.1.01/4.2.01`): só dispara para o RESTO,
     quando o valor faturado excede o que sobrou em 2.1.06 — cenário que exigiria a
     venda ter side crescido (aditivo) sem 2.1.06 correspondente, ou algum erro de
     segmentação. Medido em Homologação (3 projetos faturados: Projeto_3, Teste_1,
     Teste_4) — **nenhum** dos três jamais acionou essa perna. `1.1.02` fica
     intocado por faturamento em todos os casos reais; ele só zera quando o CLIENTE
     paga (`D 1.1.01 × C 1.1.02`), como o exemplo de seis contas já descreve.
   - **O problema real, medido ao vivo:** `Teste_1` e `Teste_4` estão **status
     "fechado"** (projeto concluído) com **2.1.06 aberto** — R$ 63.330,58 e
     R$ 68.870,01 respectivamente, nunca consumidos. Causa: cada um teve só UM
     documento fiscal (`nfe_loja_xml`, segmento "mercadoria") — nenhum NFS-e de
     serviço. `valor_seg` vem de `_valores_segmentados_do_projeto` (Val_Cont ×
     segmentação, `main.py:1544`) — a parte "serviço" da segmentação nunca teve
     evento fiscal que a faturasse, e `faturar_segmento` só roda quando ALGUÉM
     chama (não há verificação de completude no fechamento do ciclo). `Projeto_3`
     tem 2.1.06 = 1.1.02 (parecendo "nunca faturado") porque a única NF-e que
     emitiu foi CANCELADA (`estorno_cancelamento_nfe`, reverte a perna adiantado
     por inteiro) — isso é correto, não é o defeito.
   - **Consequência pro modelo:** confirma exatamente o que "O indicador de
     desbalanceamento" (acima) já previa — um projeto "fechado" com "a Apropriar"
     zerado e Provisão aberta é esperado (fase pós-NF-e); mas um projeto "fechado"
     com **Receita a Realizar (2.1.06) aberta** é outro sinal, ainda pior: nem toda
     a receita contratada foi reconhecida. Hoje NENHUMA tela mostra isso — ninguém
     saberia que Teste_1/Teste_4 têm R$63k/R$69k de receita nunca faturada sem essa
     query direta no banco. Isso PRECISA de um indicador antes (ou junto) da
     Diferida — sem ele, fechar o ciclo com faturamento incompleto fica invisível
     pra sempre, do mesmo jeito que o ACHADO-16 era invisível antes do
     contra-controle.
   - **`devolver_venda`** (mod_contabil.py:2793) é o TERCEIRO consumidor de 2.1.06
     (`D 2.1.06 × C 1.1.02`, reversão proporcional por devolução) — não achado
     nenhum quarto consumidor no código.
2. `[DECIDIDO 05/09]` A classificação rubrica a rubrica sob o CPC 47 — fechada
   com o Marcelo. Ver a seção "A classificação, decidida" logo abaixo da tabela.
3. `[DECIDIDO 05/09, F2-26]` O que cada veredito lança no modelo novo — fechado
   com o modelo, sem precisar de decisão nova (a interface se DERIVA do
   princípio da seção "As contas de Conciliação"):
   - **Absorver** (gastou mais que o provisionado — FALTA) → Despesa de
     Conciliação, na competência da conciliação.
   - **Receber** (gastou menos — SOBRA) → Receita de Conciliação, mesma
     competência.
   - **Encerrar** (bateu exato — sem sobra nem falta) → fecha sem tocar o
     resultado (não há resíduo a levar a lugar nenhum).
   - **Adiar** → não resolve nada; mantém a rubrica aberta, com data prevista
     (já é o comportamento de `ainda_vai_chegar` — só o nome muda).

   Por que "Receber" **não é receita de venda**: as contas de Conciliação ficam
   **depois** do resultado operacional do período, em bloco próprio — a receita
   de venda é base de comissão, meta e indicador, e misturar um resíduo de
   provisionamento ali de dentro contaminaria os três. Ver "As contas de
   Conciliação" acima para o detalhe (inclusive a leitura por safra).

   Registrado em `docs/db/LISTA_PARALELA.md`, LP-20 (Fechados). **Ainda não
   implementado** — isto é desenho fechado, a implementação entra na frente
   própria (ver "Onde isto entra no plano").
4. `[ABERTO]` Os 15 rótulos `reconhecimento_despesa_*` dizem "Reconhecimento de
   despesa **NA NF-E**" — resíduo do matching pleno extinto em 07/08. Hoje é
   mentira; no modelo novo volta a ser verdade. Ajustar junto, não antes.

## Onde isto entra no plano

Não é Fase 4. É **pré-requisito** dela, e irmã do item 18 da Fase 3
(competência referida) — os dois tratam da mesma coisa: um lançamento que sabe a
que competência pertence. Provavelmente frente própria, entre a Fase 2 e a
Fase 4.

## Risco a monitorar

Se o custo reconhecido é o provisionado, a qualidade da DRE passa a depender da
qualidade do provisionamento. Provisionar com folga infla o custo na competência
da entrega e devolve o excesso como Receita de Conciliação meses depois —
embelezando o mês errado. O controle já existe e nasceu para outra finalidade:
`relatorio_projetos_encerrados_por_reversao` (ACHADO-16), que olha justamente
projetos que fecham com reversão grande.
