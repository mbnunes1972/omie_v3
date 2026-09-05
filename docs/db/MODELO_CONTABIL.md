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

`[ABERTO]` A classificação **rubrica a rubrica** sob esse critério ainda não foi
feita. O código já tem uma separação criada por outro motivo e que provavelmente
serve de ponto de partida: `mod_provisoes._RUBRICAS` (as 12 que somam no
`Cust_Var`) × `_RUBRICAS_CUST_AD` (os 5 custos adicionais, que explicitamente
não entram no Cust_Var) × `_RUBRICA_CUST_FIN`. Revisar uma a uma antes de codar.

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

A solda das duas pernas está concentrada numa função só — por isso separá-las é
viável. **O custo real está nos 28 arquivos de teste:** o verde de hoje codifica
a doutrina de 07/08, e mudando a doutrina esses aceites mudam de significado.
Precisam ser rederivados, não remendados.

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

1. `[ABERTO]` `[MEDIDO]` O evento `faturamento` aparece como
   `D 1.1.02 × C 4.1.01` — debitando Contas a Receber **de novo**. Se o contrato
   já debitou 1.1.02 e a NF-e debita outra vez sem consumir o 2.1.06, o
   recebível dobra e a Receita a Realizar nunca se desfaz. Pode ser que
   `faturar_segmento` (delta-aware desde o ACHADO-13) trate por outro caminho.
   **Medir antes de qualquer desenho** — é a peça exata que a Diferida precisa.
2. `[ABERTO]` A classificação rubrica a rubrica sob o CPC 47 (ver acima).
3. `[ABERTO]` O que cada veredito lança no modelo novo. Os quatro nomes que o
   Marcelo definiu — Absorver, Receber, Encerrar, Adiar — **são a interface
   deste modelo**. Não construir os botões antes desta decisão: "Receber"
   prometeria um lançamento que a regra de 07/08 proíbe em 15 das 19 rubricas.
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
