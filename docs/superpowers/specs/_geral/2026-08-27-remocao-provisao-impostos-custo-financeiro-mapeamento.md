# Mapeamento — remoção de Impostos e Custo Financeiro da máquina de provisões

**Data:** 2026-08-27 · **Repo medido em:** commit corrente (pós T1–T7 da revisão do banco)
**Status:** FASE 1 — mapeamento. **Nada implementado.** Decisão do Marcelo (27/08/2026): Impostos e
Custo Financeiro saem do mecanismo de provisão (constituição no contrato → efetivação depois).

---

## 1. Todos os pontos hoje envolvidos

### 1.1 Contas do plano (`PLANO_PADRAO`, `mod_contabil.py`)

| código | nome | grupo | usada por |
|---|---|---|---|
| `1.1.05` | Impostos a Apropriar | 1 (Ativo) | ativo diferido de Impostos |
| `2.1.04.13` | Provisão de Impostos | 2 (Passivo) | provisão de Impostos |
| `1.1.06.19` | (sufixo do ativo diferido genérico 1.1.06) | 1 (Ativo) | ativo diferido de Custo Financeiro |
| `2.1.04.19` | (sufixo da provisão genérica 2.1.04) | 2 (Passivo) | provisão de Custo Financeiro |
| `2.1.03` | Obrigações Tributárias | 2 (Passivo) | obrigação fiscal REAL (sobrevive — não é provisão) |
| `4.3.01` | Simples Nacional s/ Vendas | 4 (Receita) | **dedução de receita bruta**, não despesa |
| `5.5.03` | Custo de Antecipação de Recebíveis | 5 (Despesa) | despesa do ramo `loja_antecipacao` — sobrevive |
| `5.5.04` | Custo Financeiro sobre Vendas | 5 (Despesa) | despesa do ramo `financeira` — sobrevive |
| `2.1.05` | Financiamento Total Flex a Pagar | 2 (Passivo) | **vestigial** — ver §1.5 |

*(Não achei os nomes literais de `1.1.06.19`/`2.1.04.19` no `PLANO_PADRAO` — são sufixos do padrão
genérico `1.1.06.XX`/`2.1.04.XX`; confirmar nome exato antes da Fase 2, não presumi.)*

### 1.2 `EVENTOS` (mod_contabil.py) — pares débito×crédito

```
fechamento_venda_impostos             1.1.05      × 2.1.04.13   constituição no contrato (sem DRE)
faturamento_impostos_deducao          4.3.01      × 1.1.05      dedução de receita na emissão (SÓ AQUI toca a DRE)
faturamento_impostos_obrigacao        2.1.04.13   × 2.1.03      efetivação da obrigação fiscal real

fechamento_venda_custo_financeiro     1.1.06.19   × 2.1.04.19   constituição no contrato (sem DRE)
reconhecimento_despesa_custo_financeiro  5.5.04   × 1.1.06.19   despesa ramo "financeira" (toca a DRE)
reconhecimento_antecipacao            5.5.03      × 1.1.06.19   despesa ramo "loja_antecipacao" (toca a DRE)
```

### 1.3 Funções envolvidas

- `constituir_provisoes_fechamento` — constitui as 2 junto das outras 14 rubricas, no fechamento
  da venda (`_PROV_FECHAMENTO["impostos"]`, `_PROV_FECHAMENTO["custo_financeiro"]`).
- `ajustar_provisao_delta` — ajuste na AF (Aprovação Financeira). `_AF_ITEM_RUBRICA["prov_imp"] =
  "impostos"` inclui Impostos no painel de ajuste da AF; **`custo_financeiro` já NÃO entra**
  (comentário no código: "é LEITURA no painel (ajuste pelo box do ramo, rota própria)").
- `efetivar_impostos_segmento` (main.py:1361-1368, chamada de `_fin_faturamento_segmentado_seguro`)
  — na emissão de CADA NF-e (mercadoria/serviço), pega o TOTAL provisionado em `2.1.04.13`
  (`total_lancado(..., credito)`), segmenta proporcionalmente (mesma % merc/serv do Val_Cont) e
  efetiva a fatia. **Não recalcula o imposto a partir da NF-e** — só libera proporcionalmente o que
  já estava provisionado desde o contrato.
- `reconhecer_custo_financeiro` — chamada em UM único lugar (`/api/orcamentos/<id>/antecipacao`,
  main.py:11179), **entrada MANUAL**: um aprovador financeiro loga com senha e digita o valor real
  observado (extrato do banco / acerto da financeira). Vale pros dois ramos (`loja_antecipacao` →
  5.5.03, `financeira` → 5.5.04).
- `trocar_ramo_custo_financeiro` — troca de ramo depois do fechamento (box da tela de negociação).
- `resolver_saldo_provisao` — o branch `despesa_em_tempo_real` (ver §T5 anterior) é `False` só pra
  estas duas (não estão em `_PROV_DESPESA_POR_ATIVO`, que é derivado de `EVENTOS` e exclui
  explicitamente `reconhecimento_despesa_custo_financeiro`; Impostos nunca teve entrada
  `reconhecimento_despesa_impostos` nesse mapa). É a rota "antiga": SOBRA → `4.4.02` (receita),
  FALTA → `5.6.10` (despesa genérica) — **exatamente o problema que a T5 apontou, mas só pra estas
  duas rubricas**.
- `conciliar_final` (etapa 21) — **exclui explicitamente as duas** do fechamento forçado:
  `excluir = _PROV_PAINEL_EXCLUI | {"2.1.04.13", "2.1.04.19"}`. Docstring já registra o motivo:
  Impostos fecha sozinha a cada NF-e; Custo Financeiro tem rota PARCIAL (só o ativo baixa; a
  provisão em si sobrevive até efetivação manual).
- `_PROV_PAINEL_TIPO` — `2.1.04.13` é tipo `"D"` (**Fiscal**, categoria só dela — some do painel
  agrupado se a conta for removida). `2.1.04.19` não está mapeada, cai em `"O"` (Outros).
- `_ativo_diferido_de` — tem o caso especial `if prov_cod == "2.1.04.13": return "1.1.05"`
  (Impostos é a ÚNICA provisão cujo ativo diferido não segue o padrão `1.1.06.<sufixo>`).

### 1.4 Testes que cobrem os dois mecanismos

`test_fase_b2_eventos.py` (`test_impostos_efetivacao_segmentada`,
`test_efetivar_impostos_idempotente`, `test_custo_financeiro`), `test_fase_d2_nfe.py`
(`test_custo_financeiro_e_impostos_sem_perna_de_despesa`), `test_resultado_financeiro.py` (13
testes — constituição, rota própria, ajuste AF, troca de ramo, conciliação final, reconhecimento
5.5.03/5.5.04). Mais **~23 outros arquivos** que referenciam `carga_trib`/`Prov_Imp`/`Cust_Fin`
incidentalmente (cálculo de Val_Cont, negociação, indicadores) — não fazem asserção sobre o
mecanismo de provisão em si, mas quebram se os campos/contas sumirem sem cuidado. Levantamento
completo por arquivo fica pra Fase 2 (rodar a suíte cedo e ver o que quebra é mais confiável que
eu adivinhar aqui).

### 1.5 Achado à parte (fora do pedido, registro): evento `custo_financeiro` vestigial

`EVENTOS["custo_financeiro"] = ("5.5.03", "2.1.05", ...)` — **nunca é chamado** em lugar nenhum do
código (`registrar_evento(..., "custo_financeiro", ...)` não tem nenhum caller). Parece ser o
mecanismo ANTIGO, substituído por `reconhecer_custo_financeiro`/ativo-diferido, nunca removido.
`2.1.05 "Financiamento Total Flex a Pagar"` só existe por causa dele. Não mexi — só registrando,
já que apareceu na varredura.

---

## 2. Destino contábil proposto

### 2.1 IMPOSTO — é dedução de receita, confirmado

Sua suspeita bate: **`faturamento_impostos_deducao` já debita `4.3.01 Simples Nacional s/
Vendas`**, que é conta do **grupo 4 (Receita)** — mesmo grupo de `4.3.02 Devolução de Vendas`, ou
seja, já é tratada como dedução da receita bruta, não como despesa. Confirmei contra:

- **Plano de contas:** `4.3.01`/`4.3.02` estão sob o grupo 4, natureza credora (`_natureza(4) =
  "credora"`) — o débito nessas contas reduz receita, não é lançamento de despesa.
- **Módulo fiscal** (`fiscal/mod_fiscal.py`, `fiscal/nfe_emissao.py`): **não tem NENHUM vínculo com
  `mod_contabil.py`** (`grep` não achou import nem chamada em nenhum sentido). O módulo fiscal
  cuida só de emitir o documento (Focus API) e mostrar a discriminação de impostos NO PDF da NF-e
  (`discrimina_impostos`, `aliquota_iss` do emitente) — **é informação pra COMPLIANCE/transparência
  ao cliente, não alimenta a contabilidade gerencial**. A "Provisão de Impostos" sempre foi um
  cálculo GERENCIAL paralelo, nunca ligado ao valor fiscal real calculado pelo Focus.

**De onde vem o valor hoje:** `Prov_Imp = carga_trib% × Val_Cont` (`mod_negociacao.py:94`),
`carga_trib` é o campo "Carga Tributária" do Painel de Parâmetros (congelado no
`Projeto.parametros_json` na negociação, default 8% vindo da config da loja). Na emissão de cada
NF-e, `efetivar_impostos_segmento` pega o TOTAL provisionado e libera a fatia proporcional
merc/serv — **não recalcula nada novo**, só distribui o valor já fixado no fechamento do contrato.

**Proposta (lançamento único, na emissão, sem constituição prévia):**

```
Na emissão de cada NF-e/NFS-e (mercadoria ou serviço), direto:
  DÉBITO  4.3.01 Simples Nacional s/ Vendas     (dedução de receita)
  CRÉDITO 2.1.03 Obrigações Tributárias         (obrigação fiscal real)
  valor = carga_trib% × valor_do_segmento_desta_NFe
```

Isso é o **mesmo cálculo matemático** que roda hoje (`carga_trib × valor_segmento`) — só sem passar
por `1.1.05`/`2.1.04.13` no meio. `2.1.03` (Obrigações Tributárias) **sobrevive** — não é conta de
provisão, é o passivo fiscal real, já existente e usado por `faturamento_impostos_obrigacao` hoje.

### 2.2 CUSTO FINANCEIRO — confirmado, com uma ressalva sobre a origem do valor

Confirmado: **ramo `financeira` → `5.5.04` Custo Financeiro sobre Vendas**; **ramo
`loja_antecipacao` → `5.5.03` Custo de Antecipação de Recebíveis**. Ambas já `variavel` no plano
(bate com T2). Ramo `loja` (capital próprio) não gera despesa nenhuma — só receita financeira por
competência (`2.1.07 × 4.4.03`), fora do escopo desta mudança.

**De onde vem o valor — aqui a resposta é diferente do que você esperava:** o motor Total Flex
(`mod_fin/total_flex.py`) **não chama `mod_contabil.py` em nenhum ponto** e não dispara nenhum
reconhecimento automático. O reconhecimento da despesa financeira **é sempre manual** hoje, nos
dois ramos: um único endpoint, `POST /api/orcamentos/<id>/antecipacao`, exige senha de aprovador
financeiro e o VALOR é **digitado por uma pessoa** (extrato do banco / acerto da financeira). O que
o Total Flex/negociação calculam é `Cust_Fin = Val_Cont − VAVO` (`_cust_fin_orc`), um valor
ESTIMADO na negociação — que hoje só serve de referência para constituir a provisão no fechamento,
não é ele que vira o lançamento de despesa final (esse é o valor real, digitado depois).

**Proposta:** manter o reconhecimento manual exatamente como é (mesma tela, mesmo endpoint, mesma
exigência de senha) — só remover o passo intermediário do ativo diferido:

```
Reconhecimento manual (endpoint /antecipacao, quando o valor real é apurado):
  ramo "financeira":        DÉBITO 5.5.04 × CRÉDITO ??? valor_real
  ramo "loja_antecipacao":  DÉBITO 5.5.03 × CRÉDITO ??? valor_real
```

**Pergunta em aberto — o CRÉDITO.** Hoje é `1.1.06.19` (o ativo diferido, que só existe por causa
da provisão). Sem a provisão, o lançamento perde o par natural. Acho que a resposta certa depende
de COMO o dinheiro chegou fisicamente:

- Se o banco/financeira já descontou a taxa ANTES de repassar (o caso mais comum de antecipação/
  cartão — a loja recebe líquido), o crédito natural é **`1.1.02 Contas a Receber`** (reduzindo o
  valor a receber pela diferença) ou até `1.1.01 Caixa` direto, dependendo de QUANDO no fluxo essa
  tela é usada (antes ou depois do recebimento já ter sido registrado).
- Existe também `2.1.05 "Financiamento Total Flex a Pagar"` (vestigial, §1.5) — mas não tenho
  evidência de que seja o destino certo; parece só ter sobrado de um desenho anterior.

**Não decidi isso sozinho** — preciso que você confirme contra o fluxo de caixa real: quando o
aprovador financeiro registra "custo real da antecipação", o valor que ele digita já foi
DESCONTADO de algum recebimento já lançado (nesse caso o crédito é ajuste de `1.1.02`/`1.1.01`), ou
é um lançamento isolado sem contrapartida de caixa ainda registrada?

---

## 3. Contas órfãs (1.1.05, 2.1.04.13, 1.1.06.19, 2.1.04.19)

**Recomendo INATIVAR, não remover.** Motivo: `Conta.ativa=0` já é o padrão deste módulo pra contas
com histórico (mesma regra de `remover_conta`/`remover_centro_custo` — nunca apaga o que tem
lançamento). Todo projeto já fechado ANTES da mudança tem lançamentos reais nessas 4 contas
(`1.1.05`/`2.1.04.13` de todo projeto faturado; `1.1.06.19`/`2.1.04.19` de todo projeto com
custo financeiro provisionado) — apagar quebraria o razão histórico e o Balanço de qualquer período
fechado anterior à mudança. Inativa: some das telas de criação/seleção, mas o extrato/DRE histórico
continua íntegro. Isso é migration de SCHEMA (`ativa=0` é dado, mas a ação em si — não pode ser dado
em produção sem constraint —, então entendo como parte da 0005: `UPDATE conta SET ativa=0 WHERE
codigo IN (...)`, mas ver a regra R6: **migração de schema e de dados nunca na mesma revisão** —
isso é migração de DADO, precisa ser revisão separada da que mexe em `_PROV_FECHAMENTO`/`EVENTOS`
(que não é DDL, é código Python — não é revisão Alembic nenhuma). Confirmar esse desenho de duas
revisões (uma de dado pras 4 contas, uma de schema se algo mais mudar) antes da Fase 2.

---

## 4. Simplificação de `resolver_saldo_provisao`/`conciliar_final`

**Sim, nos dois.**

- `conciliar_final`: a linha `excluir = _PROV_PAINEL_EXCLUI | {"2.1.04.13", "2.1.04.19"}` vira só
  `_PROV_PAINEL_EXCLUI` — sem `2.1.04.13`/`2.1.04.19` no plano, elas nem aparecem na query de
  `contas` (`WHERE codigo LIKE '2.1.04.%'`), a exclusão explícita fica morta.
- `resolver_saldo_provisao`: o branch `else` inteiro (linhas ~1883-1889, "rota antiga" SOBRA→4.4.02/
  FALTA→5.6.10) **fica sem nenhum chamador possível** — `despesa_em_tempo_real` seria sempre
  `True` pra qualquer provisão que sobrar no plano (as 14 restantes já estão todas em
  `_PROV_DESPESA_POR_ATIVO`). Dá pra apagar o branch inteiro (a função vira só o caminho
  "tempo real"), ou deixá-lo como código morto defensivo — recomendo apagar (mesma lógica do T2:
  código sem chamador é dívida, não segurança).
- `_ativo_diferido_de`: o caso especial `if prov_cod == "2.1.04.13": return "1.1.05"` também some.
- `5.6.10 Ajustes de Reconciliação` deixa de ter QUALQUER rota automática que a alimente — sobra
  exatamente como a T5 pedia: só ajuste manual de diferença sem origem identificável (arredondamento,
  fechamento). Ou seja, **essa mudança fecha o que a T5 tinha deixado pendente**, sem precisar
  tocar `resolver_saldo_provisao` de novo por causa da T5 — a remoção das duas rubricas JÁ resolve.

---

## 5. Momento de reconhecimento no DRE — antes × depois

### Imposto

| | ANTES | DEPOIS |
|---|---|---|
| Contrato assinado | `1.1.05 × 2.1.04.13` — **não toca a DRE** | nada lançado |
| Emissão de cada NF-e | `4.3.01 × 1.1.05` (dedução) — **É AQUI que toca a DRE hoje** | `4.3.01 × 2.1.03` (dedução) — **mesmo momento** |

**Não muda o momento de reconhecimento no DRE.** A dedução de receita já acontece na emissão da
NF-e hoje (o contrato só reserva um ativo diferido, sem efeito de resultado) — a proposta só
elimina o passo intermediário sem DRE. Onde MUDA de verdade: hoje, se um projeto nunca chegar a
faturar 100% do Val_Cont (cancelamento parcial, etc.), o resíduo da provisão de impostos vai pra
`5.6.10`/`4.4.02` na reconciliação — depois da mudança, **esse resíduo simplesmente não existe
mais**, porque não há mais nada provisionado adiantado pra sobrar ou faltar.

### Custo Financeiro

| | ANTES | DEPOIS |
|---|---|---|
| Contrato assinado | `1.1.06.19 × 2.1.04.19` — não toca a DRE | nada lançado |
| Reconhecimento manual (endpoint /antecipacao) | `5.5.03`/`5.5.04` × `1.1.06.19` — **É AQUI que toca a DRE hoje** | `5.5.03`/`5.5.04` × ??? (§2.2) — **mesmo momento, mesmo trigger manual** |

**Também não muda o momento** — o reconhecimento sempre foi no ato manual (endpoint /antecipacao),
nunca no contrato. A diferença real: hoje, se ninguém NUNCA registrar o "custo real" daquele
projeto, a provisão fica pendurada até a Conciliação Final resolver o resíduo (`5.6.10` ou `4.4.02`
— a única das duas rubricas que HOJE passa pelo fluxo antigo E é tocada por `conciliar_final`,
já que Impostos está excluída de lá). Depois da mudança, **sem provisão nenhuma, não existe mais
esse fechamento automático de resíduo** — se ninguém reconhecer o custo financeiro manualmente, ele
simplesmente nunca entra na DRE (nem como despesa, nem como resíduo genérico). Vale confirmar se
isso é aceitável — hoje a Conciliação Final pelo menos GARANTE que todo Custo Financeiro pendente
vira lançamento (mesmo que genérico em `5.6.10`); depois, a garantia desaparece.

---

## 6. UI — três telas encontradas, não duas

Você mencionou "Painel de Parâmetros" e "tela de negociação". Achei uma **terceira**: o painel de
Aprovação Financeira (AF).

1. **Painel de Parâmetros** (`static/index.html`, campo `mp-carga-trib`, rótulo "Carga Tributaria")
   — confirmado, é onde Imposto aparece. **Atenção:** o CAMPO em si (`carga_trib`, o percentual)
   continua sendo necessário — é o input do cálculo em §2.1. O que sai é o efeito de "isso vira uma
   provisão" — o campo do percentual pode continuar exatamente onde está, só muda o que ele
   alimenta por trás. Confirmar se isso é "remover" no seu sentido, ou só desvincular da provisão.
2. **Tela de negociação** — achei DOIS elementos distintos aqui, que merecem sua confirmação
   separadamente:
   - Uma linha "Impostos" com **cadeado por senha** (`_atualizarImpostos`/`_renderImpostosLock`,
     `static/index.html:9829+`), duplicada em CADA uma das 4 modalidades de pagamento (Aymoré,
     Cartão, À Vista, Total Flex — linhas ~1576/1603/1627/1655). Essa é claramente removível — é
     só o valor provisionado, exibido com controle de acesso.
   - O box `#ramo-fin-container` ("Custo financeiro R$ X — como está sendo financiado?",
     `static/index.html:22270+`) — **isto NÃO é só uma exibição de provisão**: é o seletor do RAMO
     (loja/antecipação/financeira) E o formulário de reconhecimento manual (`Reconhecer despesa`,
     que chama exatamente o endpoint `/antecipacao` do §2.2). Remover esse box removeria a
     FUNCIONALIDADE, não só um número — a escolha de ramo e o reconhecimento manual do custo real
     continuam necessários mesmo sem provisão. Confirmo que "REMOVER as duas" na tela de negociação
     é sobre a linha/valor de PROVISÃO exibido (analógico ao cadeado de Impostos), não sobre este
     box funcional?
3. **Painel de Aprovação Financeira (AF1/AF2)** — `_AF_ITEM_RUBRICA["prov_imp"] = "impostos"`
   (mod_contabil.py) tem espelho no frontend (`{ key: 'prov_imp', label: 'Provisão Impostos' }`,
   `static/index.html:20765`): a AF hoje deixa AJUSTAR o valor provisionado de Impostos como
   qualquer outra rubrica. Sem provisão, essa linha do painel de AF também precisa sair — você não
   mencionou essa tela; incluindo aqui pra fechar o mapa. Custo Financeiro **já não está** nessa
   tela (comentário no código confirma: "é LEITURA no painel, ajuste pelo box do ramo").

---

## Resumo do que preciso que você confirme antes da Fase 2

1. **Custo Financeiro, o crédito do lançamento manual** (§2.2) — contra qual conta, dado que o
   ativo diferido some. Minha melhor hipótese é `1.1.02 Contas a Receber` ou `1.1.01 Caixa`,
   dependendo do momento do fluxo de caixa — preciso que você diga qual.
2. **Órfãs — inativar em revisão de DADO separada da de schema** (§3) — confirma o desenho de duas
   revisões (R6)?
3. **Custo Financeiro sem reconhecimento nunca virar DRE** (§5) — aceitável perder a garantia que a
   Conciliação Final dava hoje (fechar o resíduo em `5.6.10`), ou precisa de algum mecanismo novo
   de "sobrou custo financeiro sem reconhecer" (alerta? bloqueio de fechamento de projeto?)?
4. **UI — as 3 confirmações do §6**: Painel de Parâmetros (campo `carga_trib` fica, só desvincula
   da provisão?), tela de negociação (o cadeado de Impostos sim, o box `#ramo-fin-container` NÃO?),
   e a linha "Provisão Impostos" no painel de AF (não mencionada por você — incluo na remoção?).
5. Achado à parte (§1.5): evento `custo_financeiro` vestigial (`5.5.03 × 2.1.05`, nunca chamado) —
   quer que eu aproveite esta mesma frente pra apagar, ou trato como fora de escopo?
