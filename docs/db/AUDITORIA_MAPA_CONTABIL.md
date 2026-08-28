# Auditoria contábil — Parte 1 (mapa) e Parte 2 (pontas)

Derivado do código em 2026-08-28 (mod_contabil.py, main.py, mod_assistencias.py,
mod_folha.py, mod_recebiveis.py). Nenhum conserto foi implementado — ver
docs/db/ACHADOS_CONTABEIS.md para o relatório consolidado (Parte 5).

Fonte única de escrita: `lancar()` (mod_contabil.py:1089) constrói o único
`Lancamento(...)` do sistema. Todo evento de `EVENTOS` (89 entradas) e toda
chamada direta a `lancar(` (21 sites: 18 em mod_contabil.py, 3 em main.py, via
o alias `_mcaf`) passam por ali.

## Parte 1 — mapa evento × conta × sentido

Tabela ordenada por conta. Contas de alto tráfego e natureza puramente
"perna de caixa/receita/despesa sem risco de assimetria" (1.1.01, 1.1.02 nos
eventos de rotina, contas 5.x de despesa avulsa) aparecem condensadas no fim
de cada bloco — o volume de eventos que as tocam não muda o risco: cada uma
delas grava as duas pernas no mesmo `lancar()`, sempre.

### Grupo 1 — ATIVO

| conta | evento/função | sentido | contrapartida | condicional |
|---|---|---|---|---|
| 1.1.01 Caixa/Bancos | ~30 eventos de rotina (recebimento*, pagamento_*, folha_*, captacao_emprestimo, liquidacao_conta_corrente_*, efetivar_provisao forma_pagamento="direto", despesa_avulsa forma_pagamento="direto", rateio_ao_pdv perna mãe) | D e C, conforme o evento | sempre explícita, mesmo lançamento | nenhum — cada evento grava as duas pernas juntas |
| 1.1.02 Contas a Receber (Clientes) | faturamento/faturamento_mercadoria_a_receber/faturamento_servico_a_receber (D), recebimento/recebimento_venda (C), registro_venda_contrato (D), venda_assistencia (D), recebivel_duvidoso (C), reclassificar_recebivel_duvidoso (C), devolver_venda perna (1) (C), baixar_credito_cliente dest="receber" (C) | D e C conforme evento | explícita | `registrar_recebimento_venda` capa ao saldo aberto de 1.1.02 (ou 1.1.10 se duvidoso) |
| 1.1.03 Estoques | — nenhum evento/função toca | — | — | **categoria 4**: nunca tocada — ver Parte 2 |
| 1.1.04 Adiantamentos a Fornecedores | — nenhum evento/função toca | — | — | **categoria 4** |
| 1.1.05 Impostos a Apropriar | fechamento_venda_impostos (D), faturamento_impostos_deducao (C), devolver_venda loop genérico (C, proporcional) | D e C | explícita | ativo espelho de 2.1.04.13 via `_ativo_diferido_de` |
| 1.1.06.02..21 (Custos a Apropriar, 15 contas — ver lista completa abaixo) | `fechamento_venda_<rubrica>` constitui (D), `reconhecimento_despesa_<rubrica>` baixa (C) | D no fechamento, C no reconhecimento | a provisão irmã 2.1.04.0X | reconhecimento capado ao saldo aberto do ativo (matching pleno); ver 1.1.06.19 abaixo, único com DUAS despesas possíveis |
| 1.1.06.19 Custo Financeiro a Apropriar | fechamento_venda_custo_financeiro (D, constituição — só ramo "financeira" no código atual, ver ACHADO-03), reconhecimento_antecipacao (C, ramo loja_antecipacao) OU reconhecimento_despesa_custo_financeiro (C, ramo financeira) via `reconhecer_custo_financeiro` | D constitui, C baixa | 2.1.04.19 na constituição; despesa formal (5.5.03/5.5.04) no reconhecimento | **ACHADO-01**: só esta perna existe — nunca há perna de liquidação (D provisão × C recebível/caixa). **ACHADO-03**: `_fin_provisoes_venda_seguro` (main.py:749) só reconhece ramo=="financeira" para constituir a provisão; ramo "loja_antecipacao" cai no else e constitui `constituir_juros_direto` (1.1.07/2.1.07) em vez de `fechamento_venda_custo_financeiro` — diverge de `_RAMO_CFIN_EVENTO` (mod_contabil.py:1618), que trata os dois ramos IGUAL |
| 1.1.07 Recebíveis de Parcelamentos (juros, ramo loja) | constituir_juros_direto (D), receber_parcela_direto (C), reverter_juros_direto (C) | D constitui, C baixa | 2.1.07 | `apropriar_juros_loja` capa ao saldo aberto; só ramo "loja" |
| 1.1.08 Créditos com a Fábrica | implantacao_credito_fabrica (D), recebimento_credito_fabrica (C), baixa_credito_fabrica (C), desconto_excepcional_fabrica (C) | D e C | explícita | acordos de fábrica (`_mcaf`) |
| 1.1.09 Créditos com Empresas (conta corrente) | implantacao_credito_empresa (D), acerto_acordo_intercompany (D), liquidacao_conta_corrente_credora (C), desconto_excepcional_intercompany (C), rateio_ao_pdv perna mãe (D) | D e C | explícita | intercompany/rateio |
| 1.1.10 Recebíveis Duvidosos | recebivel_duvidoso (D), recebimento_venda_duvidoso (C), reclassificar_recebivel_duvidoso (D) | D e C | explícita | — |
| 1.2.1.01-04 (Imobilizado), 1.2.2 (Intangível) | — nenhum evento/função toca | — | — | **categoria 4** — módulo de ativo fixo não existe |

Lista completa das 15 contas 1.1.06.0X/provisão irmã (constituição via
`fechamento_venda_*`, baixa via `reconhecimento_despesa_*`, sem exceção —
matching pleno):

| ativo | provisão | rubrica |
|---|---|---|
| 1.1.06.02 | 2.1.04.02 | Montagem |
| 1.1.06.03 | 2.1.04.03 | Garantia |
| 1.1.06.05 | 2.1.04.05 | Assistência Técnica |
| 1.1.06.06 | 2.1.04.06 | Custo de Fábrica |
| 1.1.06.07 | 2.1.04.07 | Frete de Fábrica |
| 1.1.06.08 | 2.1.04.08 | Frete Local |
| 1.1.06.09 | 2.1.04.09 | Insumos Locais |
| 1.1.06.10 | 2.1.04.10 | Comissão de Medidor |
| 1.1.06.11 | 2.1.04.11 | Comissão de Projeto/Executivo |
| 1.1.06.12 | 2.1.04.12 | Retenção de Comissão de Vendas |
| 1.1.06.14 | 2.1.04.14 | Outros Fornecedores (só via `reclassificar_provisao` 2.1.04.06→14, espelhando o ativo — ver nota) |
| 1.1.06.15 | 2.1.04.15 | Comissão de Arquiteto |
| 1.1.06.16 | 2.1.04.16 | Programa de Fidelidade |
| 1.1.06.17 | 2.1.04.17 | Custo de Viagem |
| 1.1.06.18 | 2.1.04.18 | Brinde |
| 1.1.06.20 | 2.1.04.20 | Custo Especial |
| 1.1.06.21 | 2.1.04.21 | Comissão Administrativa |

Nota sobre 1.1.06.14/2.1.04.14: não têm `fechamento_venda_outros_fornecedores`
próprio — nascem por `reclassificar_provisao("2.1.04.06","2.1.04.14", v)`
(mod_contabil.py:1731, dentro de `conferencia_pedido`), que espelha o ativo
(1.1.06.06→1.1.06.14) **capado ao saldo em aberto do ativo de origem**
(mod_contabil.py:1893-1907) — se a reclassificação ocorrer depois de parte do
ativo já ter sido baixado na NF-e, a perna da provisão move o valor cheio mas
a do ativo move só a fração ainda aberta. Ver Parte 2, categoria 3.

### Grupo 2 — PASSIVO

| conta | evento/função | sentido | contrapartida | condicional |
|---|---|---|---|---|
| 2.1.01 Fornecedores a Pagar | pagamento_fornecedor (D), efetivar_provisao forma_pagamento="a_prazo" (C), despesa_avulsa forma_pagamento="a_prazo" (C) | D baixa, C constitui | explícita | — |
| 2.1.02 Obrigações Trabalhistas | — nenhum evento toca; folha_fixa/variavel/beneficios creditam 1.1.01 direto, sem perna de provisionamento trabalhista | — | — | **categoria 4** |
| 2.1.03 Obrigações Tributárias | faturamento_impostos_obrigacao (C) | C | 2.1.04.13 | — |
| 2.1.04.01 Provisão de Comissão | pagamento_comissao (D, EVENTOS) — **nunca creditada por nada** | D só | 1.1.01 | **categoria 1 + achado**: `pagamento_comissao` só é chamado em `tests/test_eventos.py`; nenhum caminho de produção credita OU debita esta conta — evento morto. A comissão de venda real usa 2.1.04.12 (ver mod_folha.py). Excluída do painel (`_PROV_PAINEL_EXCLUI`) com comentário que pressupõe `pagamento_comissao` ativo, o que não é o caso |
| 2.1.04.02/.03/.05/.06/.07/.08/.09/.10/.11/.12/.14/.15/.16/.17/.18/.20/.21 | ver tabela de 17 pares acima; drenagem via `resolver_saldo_provisao` (sobra/falta cancela contra o ativo, sem DRE) ou `efetivar_provisao`/`realizar_caso` (custo real, capado ao saldo do ativo) | C constitui, D drena | ativo 1.1.06.0X irmã | `conciliar_final` (etapa 21) força a resolução de todas estas ao fechar o projeto |
| 2.1.04.04 Provisão de Devolução | — nenhum evento/percentual de constituição hoje (comentário do próprio código, `_PROV_PAINEL_EXCLUI` linha 2352) | — | — | **categoria 4**, autodocumentado — saldo sempre 0 |
| 2.1.04.13 Provisão de Impostos | fechamento_venda_impostos (C), faturamento_impostos_obrigacao (C) — constitui; `efetivar_impostos_segmento` baixa proporcional por segmento na NF-e; `resolver_saldo_provisao` fecha resíduo → 4.3.01, nos dois sentidos (item 3, já implementado) | C constitui, D baixa | 1.1.05 (ativo) / 2.1.03 (obrigação) / 4.3.01 (variância) | também alvo de `devolver_venda` (proporcional) |
| 2.1.04.19 Provisão de Custo Financeiro | fechamento_venda_custo_financeiro (C, só ramo "financeira" — ver ACHADO-03) | C só | 1.1.06.19 | **NUNCA drenada por nenhuma função** — `reconhecer_custo_financeiro` só baixa o ativo (1.1.06.19), nunca a provisão (ACHADO-01). `conciliar_final` exclui explicitamente esta conta da resolução forçada. `resolver_saldo_provisao` falha com erro nomeando a conta (item 2 bloqueado, item 4 aplicado) — comportamento correto dado o bloqueio, mas o saldo fica aberto até decisão |
| 2.1.05 Financiamento Total Flex a Pagar | — nenhum evento/lancar toca | — | — | **categoria 4 + achado**: conta nomeada explicitamente no plano e no docstring de `Recebivel` (o caso "Total Flex" do valor de face) mas nenhum código credita/debita — produto de financiamento nomeado sem contrapartida contábil nenhuma |
| 2.1.06 Receita a Realizar | registro_venda_contrato (C), faturamento_mercadoria_adiantado (D), faturamento_servico_adiantado (D), devolver_venda perna (1) (D, proporcional) | C constitui, D realiza/reverte | 1.1.02 | — |
| 2.1.07 Receita Financeira a Apropriar (juros, ramo loja) | constituir_juros_direto (C), apropriar_receita_financeira (C — via `receber_parcela_direto`), reverter_juros_direto (D) | C constitui, D realiza/reverte | 1.1.07 | só ramo "loja"; ver ACHADO-03 (pode ser tocada por engano no lugar de 2.1.04.19) e ACHADO-02 (a receita financeira realizada aqui, 4.4.03, pode já estar embutida no Val_Cont faturado em 4.1.01) |
| 2.1.08/2.1.09/2.1.10 (Acordos Fábrica/Empresa/Empréstimo) | implantacao_*, atualizacao_divida_*, pagamento_*, baixa_*, captacao_emprestimo, liquidacao_conta_corrente_devedora, acordos `_mcaf` (transferir/acrescer/abater/encerrar, direto via `lancar`) | D e C | 3.5 (implantação) ou 1.1.01/1.1.08/1.1.09 (movimento) | ver main.py:7112-7460 |
| 2.1.11 Créditos a Clientes | registrar_credito_cliente (C), baixar_credito_cliente (D), estorno_credito_cliente (D) | C constitui, D baixa | 4.3.02 / 1.1.01 ou 1.1.02 | fora de 2.1.04 de propósito (spec PE/AF2), não é varrida por `conciliar_final` |
| 2.2.01 Financiamentos de Longo Prazo | — nenhum evento toca | — | — | **categoria 4** |

### Grupo 3 — PATRIMÔNIO LÍQUIDO

| conta | evento/função | sentido | contrapartida | condicional |
|---|---|---|---|---|
| 3.5 Ajustes de Exercícios Anteriores | implantacao_divida_*/credito_* (contrapartida de implantação), acordos `_mcaf` acrescer/abater com `contrapartida="pl"` (direto via `lancar`, main.py:7396) | D e C | 1.1.08/1.1.09/2.1.08/2.1.09/2.1.10 | nunca toca DRE (CPC 23), só `_mcaf` |
| 3.1/3.2/3.3/3.4 | — nenhum evento toca | — | — | esperado — sem lançamento automático de PL corrente |

### Grupo 4 — RECEITAS

| conta | evento/função | sentido | contrapartida | condicional |
|---|---|---|---|---|
| 4.1.01/4.1.02/4.2.01 | faturamento*, venda_assistencia | C | 1.1.02 | ver ACHADO-02: 4.1.01 fatura o Val_Cont CHEIO (que já inclui o custo financeiro do ramo "loja"), e 4.4.03 reconhece esse mesmo custo financeiro de novo — achado do teste de ciclo completo, Parte 4 |
| 4.2.02 | — nenhum evento toca | — | — | **categoria 4** |
| 4.3.01 Simples Nacional s/ Vendas (dedução) | faturamento_impostos_deducao (D, rotina), `resolver_saldo_provisao` sobra/falta de 2.1.04.13 (C sobra / D falta, item 3) | D reduz receita (rotina + falta), C reduz dedução (sobra) | 1.1.05 (rotina) / 2.1.04.13 (variância) | conta "credora" de grupo mas usada como contra-receita — `saldo_conta` fica negativo no uso normal (ver CLAUDE.md) |
| 4.3.02 Devolução de Vendas | estorno_credito_cliente (D) | D | 2.1.11 | — |
| 4.4.01 Receita de Aluguéis | — nenhum evento toca | — | — | **categoria 4** — manual/despesa_avulsa presumido |
| 4.4.02 Reversão de Provisões | rota antiga de `resolver_saldo_provisao` pré-item-3/4 — **hoje só alcançável se uma rubrica nova tiver `_PROV_DESTINO_VARIANCIA` apontando pra cá** (nenhuma tem) | C | — | ver ACHADO (item 3/4 já fechou o caminho direto; mas nada IMPEDE um destino futuro apontar pra 4.4.02 por engano — não há guarda de "4.4.02 é proibido como destino", só 5.6.10 tem o alerta) |
| 4.4.03 Receita Financeira | apropriar_receita_financeira (C) | C | 2.1.07 | ramo "loja" |
| 4.4.04 Ganhos com Acordos Financeiros | `_mcaf` acrescer/abater com `contrapartida="resultado"` e `ganho=True` (direto via `lancar`, main.py:7399) | C/D conforme direção | 3.5-equivalente do acordo (conta_saldo) | escolha manual do operador (pl vs resultado) — ver Parte 2, categoria 6 |

### Grupo 5 — DESPESAS/CUSTOS

| conta | evento/função | sentido | contrapartida | condicional |
|---|---|---|---|---|
| 5.1.01/5.1.02 | reconhecimento_despesa_custo_fabrica, reconhecimento_despesa_outros_fornecedores (ambas em 5.1.01!), reconhecimento_despesa_frete_fabrica | D | 1.1.06.06/1.1.06.14/1.1.06.07 | — |
| 5.2.01/5.2.08/5.2.09/5.2.12/5.2.13 | reconhecimento_despesa_montagem/frete_local/insumos/garantia/assistencia | D | 1.1.06.0X | — |
| 5.2.02-07/10 | — nenhum evento toca | — | — | manual/despesa_avulsa presumido, não é bug |
| 5.3.01 Comissão de Vendedor | reconhecimento_despesa_retencao_com_vendas (D) **e** folha_variavel (D, rotina) — mesma conta usada por dois mecanismos distintos | D | 1.1.06.12 (retenção) / 1.1.01 (folha) | **observação categoria 3**: não existe "Retenção de Comissão de Vendas" dedicado em 5.3.x (suprimida na família 5.6, Sessão 109) — pode ser intencional (retenção é comissão de venda como outra qualquer) ou resíduo do formalismo; vale confirmar intenção |
| 5.3.03/.04/.12/.14/.15/.16/.17/.18/.19 | reconhecimento_despesa_com_adm/pro_fid/brinde/cust_via/com_arq/(folha_beneficios)/cust_esp/com_medidor/com_proj_exec | D | 1.1.06.0X ou 1.1.01 (folha) | — |
| 5.3.02/.05/.07-09/.11/.13/.21 | — nenhum evento toca, exceto 5.3.21 via `despesa_avulsa` (concessão a cliente, mod_assistencias.py:155) | — | — | manual/despesa_avulsa; 5.3.21 confirmado no código |
| 5.4.* (Despesas Administrativas, todas) | — nenhum evento toca | — | — | manual/despesa_avulsa presumido — nenhuma delas é destino de evento nem de site direto de `lancar` |
| 5.5.01 Tarifas Bancárias | — nenhum evento toca | — | — | manual/despesa_avulsa presumido |
| 5.5.02 Juros de Empréstimos | atualizacao_divida_empresa/fabrica, atualizacao_emprestimo, pagamento_juros_acordo | D | 2.1.09/2.1.08/2.1.10/1.1.01 | — |
| 5.5.03 Custo de Antecipação de Recebíveis | reconhecimento_antecipacao (D) — via `reconhecer_custo_financeiro`, ramo loja_antecipacao | D | 1.1.06.19 | ver ACHADO-01/03 |
| 5.5.04 Custo Financeiro sobre Vendas | reconhecimento_despesa_custo_financeiro (D) — via `reconhecer_custo_financeiro`, ramo financeira | D | 1.1.06.19 | ver ACHADO-01/03 |
| 5.5.05 Perdas com Acordos Financeiros | `_mcaf` acrescer/abater `contrapartida="resultado"`, `ganho=False` (direto, main.py:7399) | D | conta_saldo do acordo | idem 4.4.04 |
| 5.6.10 Ajustes de Reconciliação | `resolver_saldo_provisao` — só quando `_PROV_DESTINO_VARIANCIA[cod]=="5.6.10"` explicitamente (hoje nenhuma rubrica real; só simulado em teste) | C sobra / D falta | a provisão resolvida | item 4: nunca destino implícito, sempre alerta em log quando usada — já implementado |

## Parte 2 — as pontas, por categoria

**1. Conta com um sentido só**
- 2.1.04.01 (Provisão de Comissão): `pagamento_comissao` só debita; nada credita. Evento não é chamado por nenhum caminho de produção (só teste). Achado, não risco ativo — mas o comentário em `_PROV_PAINEL_EXCLUI` (mod_contabil.py:2351) descreve um mecanismo que não roda.
- 2.1.04.19 (Provisão de Custo Financeiro): só é constituída (`fechamento_venda_custo_financeiro`), nunca drenada por função nenhuma — é o ACHADO-01, já sob decisão pendente.
- 2.1.05 (Financiamento Total Flex a Pagar): conta nomeada no plano e no docstring de `Recebivel`, mas nem debitada nem creditada em lugar nenhum.

**2. Par constituído junto com drenagem assimétrica**
- 1.1.06.14/2.1.04.14 (Outros Fornecedores): nascem juntos via `reclassificar_provisao`, mas a perna do ativo é CAPADA ao saldo aberto de 1.1.06.06 no momento da reclassificação (mod_contabil.py:1893-1907) enquanto a perna da provisão sempre move o valor cheio — se a conferência do pedido ocorrer depois de parte do ativo já ter sido reconhecido na NF-e, a provisão e o ativo saem de 1.1.06.14/2.1.04.14 com saldos DIFERENTES por construção (documentado no próprio código como intencional, mas nunca testado).

**3. Estimativa sem reconciliação**
- `Recebivel.valor_previsto` (mod_contabil.py:1064): valor de face, só reconciliado para ramo "loja" via `apropriar_juros_loja`. Ramos "financeira"/"loja_antecipacao" não têm reconciliação do valor de face nenhuma — é a raiz do ACHADO-01.
- `_materializar_recebiveis_venda_seguro` (main.py:834): materializa `Recebivel` sem lançamento nenhum — puro dado, sem contrapartida contábil no momento da criação (esperado; a reconciliação é o problema, não a criação).

**4. Conta do PLANO_PADRAO que nenhum evento toca**
1.1.03, 1.1.04, 1.2.1.01-04, 1.2.2, 2.1.02, 2.1.04.04, 2.1.05, 2.2.01, 4.2.02,
4.4.01, e a maior parte de 5.2.*/5.3.*/5.4.*/5.5.01 (manual/despesa_avulsa
presumido, não é bug — mas nunca confirmado contra o gabarito de contas
usadas na prática).

**5. Evento que grava em conta fora do PLANO_PADRAO**
Nenhum encontrado. Todo código de D/C em `EVENTOS` e todo `_conta_por_codigo`
resolve contra o plano semeado — não há string de código hardcoded fora da
lista de `PLANO_PADRAO` nos 89 eventos nem nos 21 sites diretos de `lancar`.

**6. Lançamento sem contrapartida explícita no mesmo escopo transacional**
Nenhuma encontrada como BUG — `lancar()` é a única função que cria
`Lancamento` e sempre recebe conta_débito + conta_crédito no mesmo argumento.
Duas rotas merecem atenção como CONTROLE (não como ausência de contrapartida):
- `POST /api/financeiro/lancamentos` (main.py:9923): conta_débito/crédito
  vêm direto do corpo da requisição — qualquer par de contas analíticas
  ativas do owner, sem regra de negócio nenhuma além da permissão.
- `POST /api/financeiro/eventos` (main.py:10195): o nome do evento vem do
  corpo da requisição — permite disparar qualquer um dos 89 eventos
  (inclusive `custo_financeiro`, `reconhecimento_despesa_*`) fora dos
  fluxos guardados (sem os caps/ramos/idempotência que os endpoints
  dedicados aplicam).
- `_mcaf` acrescer/abater (main.py:7375-7414): contrapartida (PL 3.5 vs
  resultado 4.4.04/5.5.05) é escolha manual do operador no ato — não há
  regra que valide se a escolha corresponde à natureza real do fato.

## Achados que saem deste levantamento (ver docs/db/ACHADOS_CONTABEIS.md)
- ACHADO-01 (já investigado): reconciliação líquida de venda antecipada/financiada não fecha em código nenhum.
- ACHADO-02 (novo, achado no teste de ciclo completo, Parte 4): ramo "loja" pode reconhecer o
  custo financeiro duas vezes — uma dentro de 4.1.01 (Val_Cont cheio), outra em 4.4.03.
- ACHADO-03 (novo, achado nesta auditoria): `_fin_provisoes_venda_seguro` (main.py:749) diverge de `_RAMO_CFIN_EVENTO` (mod_contabil.py:1618) para o ramo "loja_antecipacao".
- Achado-candidato menor: 2.1.04.01/`pagamento_comissao` é mecanismo morto.
- Achado-candidato menor: 2.1.05 (Total Flex a Pagar) nomeado no plano sem nenhuma contrapartida contábil.
- Achado-candidato menor: `_fin_evento_seguro` (main.py:667) é código morto (definido, nunca chamado).

## Parte 4 — o que os testes de ciclo completo mostraram
Ver tests/test_ciclo_completo_por_ramo.py. Ramo "loja": fecha — todas as contas transitórias do
projeto zeram e o balancete bate (mas ver ACHADO-02 sobre o NÚMERO de receita, que fechar não
garante estar certo). Ramos "financeira" e "loja_antecipacao": marcados `xfail` — a Provisão de
Custo Financeiro (2.1.04.19) fica aberta ao final do ciclo em ambos, exatamente como o ACHADO-01
descreve; se algum conserto futuro fizer esses testes passarem inesperadamente, o `xfail(strict=True)`
vira falha (XPASS) — o sinal para remover o marcador.
