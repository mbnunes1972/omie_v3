# Achados contábeis — auditoria das pontas abertas do plano de contas

Consolidado da auditoria (docs/db/TAREFA_AUDITORIA_CONTABIL.md), a partir do
mapa em docs/db/AUDITORIA_MAPA_CONTABIL.md. Numeração estável — um achado
novo entra com o próximo número, nunca reordena os existentes. Ordenado por
consequência no número final, não por facilidade de conserto.

---

## ACHADO-01 — Custo Financeiro nunca reconcilia com o recebimento líquido · PARCIALMENTE RESOLVIDO 31/08 no passo 10 (ramo financeira); loja_antecipacao segue passo 12

**A pergunta mais antiga desta auditoria tem resposta, e para o ramo
`financeira` já tem código.** `mod_contabil.conferir_retencao_financeira`
(docs/db/TAREFA_ACHADO02_03.md, passo 10) é a perna de liquidação: cancela o
par ativo×provisão (2.1.04.19/1.1.06.19) constituído no fechamento e manda a
diferença entre a retenção esperada e a real para 4.4.05 ("Ajuste de Retenção
Financeira"), mesma conta nos dois sentidos — a mesma regra já decidida para
os impostos. **Nada disparado automaticamente ainda** — falta o endpoint/
gatilho que chama essa função quando o assistente financeiro confere o
extrato; isso é o que resta do passo 12 para este ramo.

Para `loja_antecipacao`, o passo 10 mudou o desenho: no fechamento ela passou
a ser receita financeira a apropriar, **igual a `loja`** — não constitui mais
a Provisão de Custo Financeiro. O deságio do banco na antecipação (quando ela
de fato acontece) segue reconhecido por `reconhecer_custo_financeiro`, que
agora se auto-constitui e resolve no mesmo evento (não precisa mais de uma
estimativa prévia para capar) — **esse pedaço do ACHADO-01 está fechado por
completo** para este ramo: não sobra provisão nenhuma para liquidar depois.

Isso saiu da decisão da tabela por ramo (30/08, ver `PLANO_AJUSTES.md`) e do
que o usuário explicou sobre a operação: a financeira retém o valor, o
dinheiro não passa pelo caixa da loja. O passo 12 do roteiro encolhe: falta
só o gatilho de conferência para `financeira` (a função já existe e está
testada) — `loja_antecipacao` não precisa de nada a mais.

O texto original do achado, que segue abaixo, continua descrevendo o defeito
corretamente — só a pergunta final estava sem resposta.


**O que acontece:** a Provisão de Custo Financeiro (2.1.04.19) é constituída
no fechamento da venda e nunca é drenada por nenhuma função — só o ativo
diferido irmão (1.1.06.19) baixa, quando `reconhecer_custo_financeiro`
reconhece a despesa formal (5.5.03/5.5.04).

**Evidência:** `reconhecer_custo_financeiro` (mod_contabil.py:1669-1687) só
lança despesa × ativo; nunca toca 2.1.04.19. `registrar_recebimento_venda`
(mod_contabil.py:1972), o único lugar que credita Contas a Receber/Caixa com
dinheiro real, é estruturalmente independente do fluxo de antecipação/custo
financeiro — nenhum código liga os dois. `Recebivel.valor_previsto`
(mod_contabil.py:1064) é reconciliado com o valor real só para ramo "loja"
(via `apropriar_juros_loja`); ramos "financeira"/"loja_antecipacao" não têm
reconciliação de valor de face nenhuma.

**Consequências no número final:**
- A provisão 2.1.04.19 cresce sem parar em todo contrato "financeira"/
  "loja_antecipacao" e nunca fecha sozinha — `conciliar_final` exclui essa
  conta explicitamente da resolução forçada, então o saldo fica aberto até
  decisão manual, projeto após projeto.
- Não há como saber, hoje, se o deságio realmente descontado pelo banco/
  financeira bate com o que foi provisionado — a única reconciliação
  possível é manual, e nada no código valida ou alerta a diferença.
- Bloqueia especificamente o item 2 de TAREFA_PROVISOES.md (rotear a
  variância de Custo Financeiro pelo padrão "tempo real" das outras 15
  rubricas) — tentar isso hoje empurraria o ativo diferido para saldo
  negativo (ver comentário em `_PROV_TEMPO_REAL_ROTA_PROPRIA`).

**O que bloqueia:** item 2 de docs/db/TAREFA_PROVISOES.md.

**Decisão necessária:** o fluxo de confirmação de recebimento (ou o de
antecipação bancária) deve passar a registrar a perna de liquidação da
provisão (D provisão × C recebível/caixa) no mesmo lançamento que já existe
hoje, ou essa perna precisa de um evento novo, criado especificamente pra
fechar esse ciclo?

---

## ACHADO-02 — Ramo "loja": a Receita Financeira pode ser reconhecida duas vezes (achado do teste de ciclo completo, Parte 4) · RESOLVIDO 31/08/2026, junto do ACHADO-03

**RESOLVIDO (docs/db/TAREFA_ACHADO02_03.md, passo 10 do ROTEIRO — fundido com o
ACHADO-03: o 02 é a consequência, o 03 o roteador que a produzia).**
`registro_venda_contrato`/`faturar_segmento` passam a usar o **VAVO** — não o
Val_Cont cheio — em `1.1.02×2.1.06` e em `4.1.01`/`4.2.01`. `cust_fin =
Val_Cont − VAVO` tem rota própria por ramo (`_RAMO_CFIN_EVENTO`, também
corrigida — ver ACHADO-03 abaixo): receita financeira a apropriar (loja/
loja_antecipacao) ou retenção esperada, posição de balanço (financeira). A
receita de vendas nunca mais inclui o custo financeiro, e o ramo que
reconhece esse custo faz isso uma vez só, na conta certa.

`valor_contratado_do_projeto`/`_valores_segmentados_do_projeto` ganharam o
espelho `vavo_contratado_do_projeto` (mesma soma contrato+aditivos assinados,
campo `vavo` em vez de `valor_total`) — sem essa segunda soma, a segmentação
mercadoria/serviço continuaria proporcional ao Val_Cont, arrastando o
cust_fin junto.

Aceite nº 1 (`tests/test_aceite_achado02_03.py::test_aceite1_...`): mesma
venda, quatro ramos (à vista/loja/loja_antecipacao/financeira), mesma receita
em 4.1.01 — é o teste que prova a decisão inteira.
`test_ramo_loja_receita_total_deveria_contar_o_custo_financeiro_uma_vez_so`
(o teste de medição do achado, sem `xfail` — nunca teve um, era só medição)
foi reescrito para `test_ramo_loja_receita_total_conta_o_custo_financeiro_
uma_vez_so`, com os mesmos números (R$ 46.300,00), agora fechando certo.

**Histórico da medição (antes do conserto):**

**O que acontece:** no fechamento da venda (`_fin_provisoes_venda_seguro`, main.py:739),
`registro_venda_contrato` registra o Val_Cont CHEIO (D:1.1.02 × C:2.1.06) — e Val_Cont, por
definição do próprio motor de precificação, INCLUI o custo financeiro (`cust_fin = Val_Cont −
VAVO`, main.py:746). A NF-e (`_fin_faturamento_segmentado_seguro`, main.py:1358-1360) fatura
esse mesmo Val_Cont cheio contra 4.1.01/4.2.01 (Receitas com Vendas). Separadamente,
`constituir_juros_direto`/`apropriar_juros_loja` reconhecem o `cust_fin` (a MESMA fatia que já
está dentro do Val_Cont) de novo, como Receita Financeira (4.4.03).

**Evidência:** main.py:739-751 (Val_Cont cheio para `registro_venda_contrato` e para o cálculo
de `cust_fin`); main.py:1340-1341,1358-1360 (`_fin_faturamento_segmentado_seguro`: "o valor do
segmento vem do ORÇAMENTO DO CONTRATO (Val_Cont × segmentação efetiva)"); comentário em
tests/test_resultado_financeiro.py:67 ("recebível dos juros (só juros; VAVO fica no 1.1.02)") —
que descreve um desenho onde 1.1.02 deveria carregar SÓ o VAVO, não o Val_Cont cheio;
mod_provisoes.py:234 ("margem_contrato: base Val_Cont (inclui o custo financeiro — que se
cancela no numerador)") — confirma, no próprio código, que Val_Cont inclui o custo financeiro, e
que o "cancelamento" existe hoje só na MARGEM gerencial (mod_provisoes.py), não na
contabilização em partida dobrada (mod_contabil.py). Reproduzido em
tests/test_ciclo_completo_por_ramo.py::test_ciclo_completo_ramo_loja: com Val_Cont=10000,
VAVO=9000, cust_fin=1000, o teste fecha (todas as contas transitórias zeram, balancete bate) MAS
4.1.01 fecha em 10000 E 4.4.03 fecha em 1000 — receita total reconhecida de 11000 para um
contrato de 10000. Isolado em números concretos, com a afirmação explícita de quanto a receita
DEVERIA ser, em
tests/test_ciclo_completo_por_ramo.py::test_ramo_loja_receita_total_deveria_contar_o_custo_financeiro_uma_vez_so
(`xfail(strict=True)`, vira verde sozinho no dia da correção): venda de R$ 46.300,00 (VAVO R$
42.500,00 + cust_fin R$ 3.800,00) — receita apurada hoje = R$ 50.100,00 (4.1.01 R$ 46.300,00 +
4.4.03 R$ 3.800,00) contra R$ 46.300,00 esperado. **Distorção de R$ 3.800,00 — exatamente o
custo financeiro, contado duas vezes.**

**Consequências no número final:**
- A Receita (DRE) de todo contrato ramo "loja" com financiamento direto (cust_fin > 0) fica
  inflada exatamente pelo valor do custo financeiro — não é um erro de centavos, é proporcional
  ao volume financiado nesse ramo.
- O efeito não aparece em nenhum saldo de balanço aberto (por isso o ciclo "fecha" no sentido de
  balancete e contas transitórias zeradas) — só aparece comparando a soma de 4.1.01+4.4.03 contra
  o Val_Cont do contrato, o que nenhum teste fazia antes deste.
- Se a margem gerencial (mod_provisoes.py) já "cancela" esse efeito pra relatório de margem, a
  DRE contábil oficial e o relatório de margem podem estar reportando receita de vendas
  diferente pro mesmo contrato, sem nenhuma reconciliação entre os dois hoje.

**O que bloqueia:** nada diretamente, mas se for confirmado como bug, precisa de correção antes
de qualquer fechamento de DRE oficial que dependa de 4.1.01/4.4.03 para contratos ramo "loja"
financiados.

**Decisão necessária:** `registro_venda_contrato`/`faturar_segmento` deveriam usar VAVO (não
Val_Cont) para a receita de vendas no ramo "loja", com o custo financeiro reconhecido só via
4.4.03 (como o comentário de 1.1.07 already describes) — ou Val_Cont cheio em 4.1.01 é
intencional, e a Receita Financeira de 4.4.03 deveria ser cancelada por uma dedução em vez de
somada, algo que não existe hoje no razão?

---

## ACHADO-03 — Constituição do Custo Financeiro diverge por ramo entre dois pontos do código · RESOLVIDO 31/08/2026, junto do ACHADO-02

**RESOLVIDO (docs/db/TAREFA_ACHADO02_03.md, passo 10 do ROTEIRO).** A medição
original apontava a divergência certa, mas a resposta óbvia ("faça main.py
chamar `_RAMO_CFIN_EVENTO`") estava errada: a medição da decisão (30/08)
mostrou que **nenhuma das duas versões estava certa** — a tabela também
mudou. `_RAMO_CFIN_EVENTO` agora é:

| ramo | evento |
|---|---|
| `financeira` | `fechamento_venda_custo_financeiro` (retenção esperada, posição de balanço) |
| `loja` / `loja_antecipacao` | `constituir_juros_direto` (receita financeira a apropriar) |

`main.py` passou a ler a tabela (`mod_contabil.evento_custo_financeiro`) em
vez de uma comparação binária própria — as duas fontes de verdade viraram
uma. `trocar_ramo_custo_financeiro` (troca de ramo na AF) foi ajustada
junto: só `financeira` é "provisão" agora — loja↔loja_antecipacao virou
no-op contábil (eram os dois "provisão" que eram no-op entre si antes).

`tests/test_aceite_achado03.py` (antes `xfail(strict=True)`, controle
negativo confirmado) foi reescrito: hoje prova que main.py e o dicionário
canônico **concordam** para `loja_antecipacao` — não mais uma divergência a
corrigir.

**Histórico da medição (antes do conserto):**

**O que acontece:** `_fin_provisoes_venda_seguro` (main.py:749) decide qual
evento constituir com uma comparação binária `_ramo == "financeira"` — só
esse ramo constitui a Provisão de Custo Financeiro
(`fechamento_venda_custo_financeiro`, 1.1.06.19×2.1.04.19); qualquer outro
ramo, incluindo "loja_antecipacao", cai no `else` e constitui
`constituir_juros_direto` (1.1.07×2.1.07 — o mecanismo de juros próprios do
ramo "loja"). Isso diverge de `_RAMO_CFIN_EVENTO` (mod_contabil.py:1618-1623),
o dicionário que já existe no código pra essa mesma decisão e que trata
"financeira" e "loja_antecipacao" da MESMA forma.

**Evidência:** main.py:749 (`_ev = "fechamento_venda_custo_financeiro" if
_ramo == "financeira" else "constituir_juros_direto"`) vs.
mod_contabil.py:1618-1623 (`_RAMO_CFIN_EVENTO = {"financeira": ...,
"loja_antecipacao": ..., "loja": "constituir_juros_direto"}`).
`orc.ramo_financeiro` só é escrito em main.py:11147, dentro do endpoint
`POST /api/orcamentos/<id>/ramo-financeiro`, que **não valida se o contrato
já fechou** antes de aceitar a troca (main.py:11115-11152: a única guarda é
`cust_fin > 0`).

**Consequências no número final:**
- Se o ramo for trocado para "loja_antecipacao" (via aprovação financeira)
  ANTES do fechamento do contrato (2ª assinatura), `_fin_provisoes_venda_seguro`
  lê `orc.ramo_financeiro` já setado e constitui `constituir_juros_direto`
  em vez da provisão de Custo Financeiro — a venda financiada por
  antecipação bancária acaba registrada como se fosse financiamento com
  capital próprio da loja (ramo "loja"), nas contas erradas (1.1.07/2.1.07
  em vez de 1.1.06.19/2.1.04.19).
- Como `trocar_ramo_custo_financeiro` (chamado pelo mesmo endpoint) já
  constitui a provisão corretamente ao trocar de "loja" para
  "loja_antecipacao"/"financeira", a sequência acima pode resultar em
  AMBOS os mecanismos lançados para o mesmo valor de custo financeiro — a
  aritmética exata do resíduo depende da ordem e não foi testada em nenhum
  teste hoje.
- Deixa duas fontes de verdade divergentes no código para a mesma decisão
  (qual evento por ramo) — quem mexer numa sem saber da outra reintroduz o
  problema mesmo depois de corrigido aqui.

**O que bloqueia:** nada diretamente, mas contamina a mesma área do
ACHADO-01 (2.1.04.19/1.1.06.19) — resolver os dois juntos evita retrabalho.

**Decisão necessária:** o operador pode legitimamente trocar o ramo
financeiro de um orçamento ANTES do fechamento do contrato, ou essa troca
só deveria ser possível depois? Se só depois, falta uma guarda explícita no
endpoint; se pode ser antes, `_fin_provisoes_venda_seguro` precisa usar
`_RAMO_CFIN_EVENTO`/`evento_custo_financeiro()` em vez da comparação binária
própria.

---

## ACHADO-04 — 2.1.05 "Financiamento Total Flex a Pagar" nunca é tocada

**O que acontece:** a conta existe no PLANO_PADRAO com esse nome, mas
nenhum evento e nenhum site direto de `lancar` credita ou debita ela.

**Evidência:** mod_contabil.py:75 (definição no plano); grep confirma zero
outras ocorrências fora da definição. O produto "Total Flex" (`tipo="tf"`)
na verdade mapeia para ramo "loja" (mod_recebiveis.py:29, `_RAMO = {...,
"tf": "loja", ...}`), que usa 1.1.07/2.1.07 (Recebíveis de Parcelamentos/
Receita Financeira a Apropriar) — uma perna de ATIVO, não de passivo "a
pagar".

**Consequências no número final:** provavelmente nenhuma hoje — o
mecanismo real do Total Flex parece ter migrado para o padrão do ramo
"loja" (1.1.07/2.1.07) em algum momento, deixando 2.1.05 como resíduo de um
desenho anterior. Mas enquanto a conta existir sem uso e sem nota, qualquer
lançamento manual (`/api/financeiro/lancamentos`) ou relatório que a
encontre vazia não tem como saber se é "conta morta" ou "produto não
lançado ainda".

**O que bloqueia:** nada.

**Decisão necessária:** 2.1.05 pode ser removida do plano (resíduo do
desenho anterior do Total Flex, hoje coberto por 1.1.07/2.1.07), ou existe
um caso de financiamento de terceiro real que ainda precisa dela?

---

## ACHADO-05 — 2.1.04.01 "Provisão de Comissão" e o evento `pagamento_comissao` são mecanismo morto

**O que acontece:** `EVENTOS["pagamento_comissao"]` debita 2.1.04.01 e
credita 1.1.01, mas nenhum caminho de produção chama esse evento — só
`tests/test_eventos.py`. Nada credita 2.1.04.01 em lugar nenhum.

**Evidência:** grep por `"pagamento_comissao"` em todo o repositório: só
mod_contabil.py:1326 (definição) e tests/test_eventos.py:39 (o teste). A
comissão de venda real hoje passa por 2.1.04.12 (Retenção de Comissão de
Vendas), via `mod_folha.pagar` (mod_folha.py:150,306-312,
`_PROV_COMISSAO_VENDA = "2.1.04.12"`).

**Consequências no número final:** nenhuma hoje — a conta nunca é usada, o
saldo é sempre zero. É achado de higiene, não de risco ativo. Já está
excluída do painel (`_PROV_PAINEL_EXCLUI`), mas o comentário ali
("Comissão — despesa de venda; baixa via pagamento_comissao") descreve um
mecanismo que não roda mais.

**O que bloqueia:** nada.

**Decisão necessária:** 2.1.04.01 e o evento `pagamento_comissao` podem ser
removidos (substituídos por 2.1.04.12), ou há um caso de uso futuro
planejado que ainda os reserva?

---

## ACHADO-06 — Reclassificação de Outros Fornecedores pode deixar ativo e provisão com saldos diferentes

**O que acontece:** `reclassificar_provisao("2.1.04.06", "2.1.04.14", v)`
(chamada por `conferencia_pedido`, mod_contabil.py:1731) sempre move o valor
cheio na perna da provisão, mas espelha o ativo diferido (1.1.06.06→1.1.06.14)
capado ao saldo aberto do ativo de origem no momento da chamada
(mod_contabil.py:1893-1907).

**Evidência:** mod_contabil.py:1896-1907 — comentário do próprio código já
admite o comportamento ("reclass ANTES da NF-e espelha tudo; DEPOIS da NF-e
não move").

**Consequências no número final:** se a conferência do pedido (que dispara
essa reclassificação) ocorrer depois de parte do Custo de Fábrica já ter
sido reconhecido na NF-e, a Provisão de Outros Fornecedores (2.1.04.14) e o
Ativo a Apropriar de Outros Fornecedores (1.1.06.14) nascem com saldos
diferentes por construção — o excedente da provisão sem ativo equivalente
só se resolve manualmente via `resolver_saldo_provisao`, sem alerta
automático hoje. Nenhum teste cobre esse cenário.

**O que bloqueia:** nada diretamente.

**Decisão necessária:** esse descasamento merece um alerta automático (como
o de 5.6.10) quando a reclassificação ocorre pós-NF-e parcial, ou o
comportamento atual (resolver manualmente depois) já é suficiente?

---

## ACHADO-07 — Dois "escape hatches" manuais sem validação de regra de negócio

**O que acontece:** `POST /api/financeiro/lancamentos` (main.py:9923-9947)
aceita conta_débito/conta_crédito/valor diretos do corpo da requisição, sem
regra de negócio além da permissão. `POST /api/financeiro/eventos`
(main.py:10195-10213) aceita o NOME do evento (qualquer um dos 89) e o
valor diretos do corpo, contornando os caps/ramos/idempotência que os
endpoints dedicados aplicam para os mesmos eventos.

**Evidência:** main.py:9923-9947, main.py:10195-10213.

**Consequências no número final:** nenhuma automática — são superfícies de
controle, não bugs. Mas permitem, por permissão apenas, disparar
`custo_financeiro`/`reconhecimento_despesa_*`/qualquer evento com qualquer
valor, fora dos fluxos guardados — inclusive contornando o bloqueio do item
2 (Custo Financeiro) descrito no ACHADO-01, se alguém chamar o evento
`custo_financeiro` (não confundir com `reconhecimento_despesa_custo_financeiro`)
manualmente.

**O que bloqueia:** nada.

**Decisão necessária:** esses dois endpoints deveriam ficar restritos a um
perfil administrativo mais estrito que o resto do módulo financeiro, dado
que contornam toda a lógica de negócio das rotas dedicadas?

---

## ACHADO-08 — Contas do PLANO_PADRAO nunca tocadas por nenhum evento (refinado em 2026-08-29)

**Origem comum:** todas as contas abaixo nasceram juntas no seed inicial
(commit `0b86514`, 09/07/2026, "Plano de Contas — modelo Conta + seed
padrão (99 contas)"), derivado de `Especificacao_Financeiro_Orizon_v2.docx`
§2/§2.1 — a spec (`docs/superpowers/specs/financeiro/2026-07-09-plano-de-
contas-design.md`) descreve o seed como "as ~70 analíticas do Pontta" e o
enquadra explicitamente como "ponto de partida, ajustável com o contador".
Um plano de contas completo foi importado de uma vez — nenhuma dessas
contas nasceu de uma funcionalidade sendo construída conta-por-conta. A
investigação de origem (2026-08-29) não encontrou nenhuma tabela de banco
(`Veiculo`, `Imobilizado`, `Estoque`, `ContratoAluguel`, etc.), tela ou
endpoint correspondente a nenhuma delas.

O primeiro relatório (2026-08-28) tratava a lista como uma coisa só. Ela
não é — **"nunca tocada por evento" significa coisas diferentes conforme
o tipo de conta**, e a categoria decide se isso é sintoma ou é esperado.

### Contas de evento (módulo declarado, ainda não construído)
1.1.03 (Estoques), 1.1.04 (Adiantamentos a Fornecedores), 1.2.1.01-04
(Imobilizado — Informática/Veículos/Obras/Show Room), 1.2.2 (Intangível),
2.1.02 (Obrigações Trabalhistas formal), 2.2.01 (Financiamentos de Longo
Prazo), 4.2.02 (Prestação de Serviços a Terceiros), 4.4.01 (Receita de
Aluguéis).

Estas são contas que, num módulo automático de verdade (controle de
estoque, ativo fixo, folha trabalhista formal, financiamento de longo
prazo), SERIAM movidas por evento — hoje não são porque o módulo em si não
existe, não porque o evento foi esquecido. É o plano de contas funcionando
como **mapa do que a empresa pretende ser**, não sobra de código. Ficam no
catálogo como futuro declarado; "nunca tocada" volta a ser sinal relevante
no dia em que o módulo correspondente for desenhado — vale conferir contra
esta lista antes de desenhar qualquer um deles.

### Contas de lançamento manual (usadas — por lançamento manual, não por evento)
A maior parte das famílias 5.2.*/5.3.*/5.4.*/5.5.01 (Aluguel, Água,
Energia, Salários Administrativos, Combustível, Manutenção etc.) fazem
parte do mesmo template importado, mas são o tipo de conta que uma
operação real usa via `despesa_avulsa`/`/api/financeiro/lancamentos` — o
funcionário lança a despesa manualmente quando ela acontece, não existe
nem deveria existir um evento automático que a debite sozinho. "Nunca
tocada por evento" aqui não é sintoma nenhum — é o desenho correto para
despesa de escritório. Excluí-las da lista de vigilância.

**Consequências no número final:** nenhuma nos dois grupos.

**O que bloqueia:** nada.

**Decisão necessária:** nenhuma para o grupo de lançamento manual (fora da
lista de vigilância a partir de agora). Para o grupo de módulo declarado:
nenhuma decisão pendente — permanecem no catálogo como futuro declarado;
a decisão relevante (implementar o módulo) é de roadmap, não de auditoria.

---

## ACHADO-09 — `5.3.01` usada por dois mecanismos com nomes conceitualmente diferentes

**O que acontece:** `reconhecimento_despesa_retencao_com_vendas` debita
5.3.01 ("Comissão de Vendedor") para reconhecer a retenção de comissão de
vendas — não existe uma conta "Retenção de Comissão de Vendas" dedicada em
5.3.x (a família 5.6 que a teria foi suprimida na Sessão 109, formalismo
pleno).

**Evidência:** mod_contabil.py, entrada EVENTOS
`reconhecimento_despesa_retencao_com_vendas` (D:5.3.01); `folha_variavel`
também debita 5.3.01 para comissão de venda de rotina.

**Consequências no número final:** provavelmente nenhuma — retenção de
comissão de vendas sendo despesa de comissão de vendedor é uma leitura
razoável. Mas as duas origens (folha de rotina e reconhecimento de
retenção provisionada) ficam misturadas na mesma conta sem distinção de
origem além do campo `origem` do lançamento.

**O que bloqueia:** nada.

**Decisão necessária:** é intencional que retenção de comissão e comissão
de venda de rotina compartilhem 5.3.01, ou a supressão da família 5.6
deveria ter criado uma conta própria para a retenção?

---

## ACHADO-10 — `_fin_evento_seguro` é código morto

**O que acontece:** função definida em main.py:667-686 (wrapper fail-soft
em torno de `registrar_evento`), sem nenhum chamador em todo o main.py.

**Evidência:** grep por `_fin_evento_seguro(` retorna só a própria
definição.

**Consequências no número final:** nenhuma — não executa.

**O que bloqueia:** nada.

**Decisão necessária:** remover, ou havia uma integração planejada que
nunca foi ligada?

---

## ACHADO-11 — Docstring de `conciliar_final` desatualizada

**O que acontece:** o docstring de `conciliar_final` (mod_contabil.py:2143-2153)
ainda descreve "sobra → 4.4.02, falta → 5.6.10" como o comportamento das 17
rubricas de custo — mas a função delega para `resolver_saldo_provisao`
(mod_contabil.py:2165), que hoje cancela sobra/falta contra o ativo diferido
sem tocar a DRE (comportamento correto pós item-1/3/4 de
TAREFA_PROVISOES.md). O comportamento em produção já está certo; só o
texto ficou para trás.

**Evidência:** mod_contabil.py:2143-2153 (docstring) vs. 2165 (delegação
real).

**Consequências no número final:** nenhuma — é só documentação
desatualizada, não afeta o lançamento gravado.

**O que bloqueia:** nada.

**Decisão necessária:** nenhuma — ajustar o docstring é conserto trivial,
não requer decisão.

---

## ACHADO-12 — Aditivo contratual: a receita constituída nunca é faturada · RESOLVIDO 30/08/2026

**RESOLVIDO (docs/db/TAREFA_ACHADO12.md, passo 7 do ROTEIRO).** Último dos
três defeitos do aditivo — o 13 (passo 5) e o 21 (passo 6) já tinham saído,
nessa ordem, por desenho (somar antes deles transformaria defeito raro em
defeito de todo projeto com aditivo, ou somaria um valor já duplicado).

`_valores_segmentados_do_projeto` passou a usar `valor_contratado_do_projeto`
(extraída no passo 6: contrato + aditivos **assinados**) em vez de ler só
`Contrato.orcamento_id → Orcamento.valor_total`. Não escreveu um segundo
predicado de "quais orçamentos contam" — herdou a definição que o ACHADO-21
já fixou. Aceite: `tests/test_aceite_achado12.py::
test_projeto_com_aditivo_termina_com_2106_zerado` — contrato R$ 88.888,89 +
aditivo R$ 4.444,44, 2.1.06 chega a R$ 93.333,33 antes da NF-e e fecha em
**R$ 0,00** depois dela; 4.1.01 fecha em R$ 93.333,33 (contrato + aditivo,
uma vez só).

**Três pontos resolvidos junto:**
- `cfo` **removido** do retorno de `_valores_segmentados_do_projeto` —
  nenhum dos três consumidores o lia (o custo de fábrica do aditivo já é
  constituído por `_fin_provisoes_venda_seguro` na assinatura, achado do
  passo 6); mantê-lo seria a mesma promessa sem consumidor do ACHADO-22.
- Seleção do orçamento em `POST /aditivo` ficou **explícita**: entre os
  candidatos do mesmo `parcela_id` (default `None` — nunca mais pega um
  complemento de FASE por engano), prefere o **pendente** (sem aditivo
  assinado ainda), nunca "o de maior id" — que ficou perigoso depois do
  passo 6 criar orçamentos históricos. Aceite: `tests/test_aceite_achado12.py::
  test_selecao_do_orcamento_no_post_aditivo_e_explicita`.
- **Segmentação congelada — medido, não implementado** (`tests/
  test_medicao_segmentacao_congelada.py`):
  1. **Não é alcançável em operação normal.** `/api/projetos/<n>/parametros`
     (que inclui `pct_mercadoria`/`pct_servico`) é bloqueado por
     `_contrato_assinado` assim que o contrato tem qualquer assinatura.
     `_congelar_segmentacao_no_projeto` (main.py:961, disparado na mesma
     hora que as provisões) grava a segmentação efetiva DENTRO do
     `Projeto.parametros_json`, e `segmentacao_efetiva` faz o override do
     projeto vencer sempre o default da loja — uma mudança em `Loja.
     pct_mercadoria`/`pct_servico` (edição de dados da loja, que não checa
     projeto nenhum) depois disso **não afeta** o projeto: medido —
     congelado em 100% mercadoria, loja mudou para 30/70 depois, o projeto
     faturou os mesmos R$ 88.888,89 em mercadoria.
  2. **Mas o congelamento é fail-soft** (main.py:956-963, `except Exception
     as _eseg: ... print(...)`) — se falhar por qualquer motivo (ou num
     projeto legado anterior ao mecanismo), o projeto vive do default da
     loja AO VIVO, para sempre, e o caminho abre: medido sem o
     congelamento — mercadoria a 65% = R$ 57.777,78; loja muda para 20%
     depois da assinatura; mercadoria vira R$ 17.777,78 — R$ 40.000,00 de
     diferença na face fiscal do MESMO contrato de R$ 88.888,89, sem
     nenhuma ação no próprio projeto.
  3. `Aditivo.dados_json` **não carrega segmentação nenhuma** hoje (só
     `ambientes`, `valor_original/novo`, `diferenca`, `forma_pagamento_
     snapshot`) — precisaria ganhar o campo se o congelamento por aditivo
     for decidido.
  **Decisão pendente do Marcelo:** o aditivo deveria congelar a própria
  segmentação no `dados_json` (protegendo mesmo no caminho fail-soft), ou
  o conserto é tornar o congelamento do CONTRATO menos fail-soft (falhar
  alto em vez de silenciar)? As duas endereçam achados diferentes — a
  primeira é sobre o aditivo, a segunda sobre o próprio ACHADO-19.

---

## ACHADO-12 · histórico da medição original

**O que acontece:** um aditivo assinado (`POST /api/projetos/<nome>/aditivo/assinar`,
main.py:9106-9165) cria um `Orcamento` separado (`complemento_pe=1`, valor da
diferença) e, na 2ª assinatura, chama `_fin_provisoes_venda_seguro` (o mesmo
wiring do fechamento original) — isso corretamente constitui a Receita a
Realizar (2.1.06) e as provisões (as 17 rubricas) pela diferença. Mas a NF-e
(`_fin_faturamento_segmentado_seguro` → `_valores_segmentados_do_projeto`,
main.py:1315-1336) resolve o Val_Cont a faturar sempre a partir do único
`Contrato` do projeto (main.py:13824 é o ÚNICO ponto de criação de
`Contrato` em todo o código) — nenhum aditivo cria ou atualiza esse
registro. A segmentação de NF-e nem sabe que o aditivo existe.

**Evidência:** main.py:9159-9161 (aditivo só cria `Orcamento`, nunca
`Contrato`); main.py:1315-1336 (`_valores_segmentados_do_projeto` lê
`Contrato.orcamento_id` → `Orcamento.valor_total`, sempre o original);
main.py:13824 (confirmado por grep: único `Contrato(` do código).
tests/test_complemento_pe_e2e.py:222-234 valida que o aditivo grava
lançamentos (idempotência do wiring), mas nenhum teste hoje verifica
`faturar_segmento`/4.1.01 contra o valor do aditivo. **Confirmado de novo,
com números concretos, em `tests/test_dre_ciclo_completo_e2e.py`**
(docs/db/TESTE_DRE_CICLO.md): aditivo de R$ 5.000,00 sobre contrato de
R$ 90.000,00 — 2.1.06 fica em R$ 5.000,00 (nunca zera) do marco da emissão
da NF-e de serviço até a Conciliação Final (etapa 21) inclusive; 1.1.02
fecha o ciclo em R$ 5.000,00 também (o recebimento só cobre os
`Recebivel` do contrato original — materializados na geração do
contrato, antes do aditivo existir — nunca há `Recebivel` para o valor do
aditivo, então nem o caminho de recebimento tem como cobrar esse
resíduo). Ver docs/db/RELATORIO_DRE_CICLO.md, marcos `6b` a `8`.

**Consequências no número final:**
- Para um aditivo de R$ X, o R$ X inteiro fica constituído em Receita a
  Realizar (2.1.06) e NUNCA vira receita faturada (4.1.01/4.2.01) — 100% do
  valor do aditivo, não uma fração ou um arredondamento.
- Qualquer projeto com aditivo fecha com 2.1.06 aberto para sempre — contraria
  diretamente a invariante "contas transitórias zeradas no fechamento"
  (docs/db/TAREFA_BATERIA_CICLO.md, invariante 2) e é o motivo dos cenários
  `tem_aditivo=True` da bateria de ciclo completo terem que ficar `xfail`.
- As provisões de custo do aditivo (constituídas corretamente) seguem seu
  próprio caminho de resolução normalmente — o problema é ISOLADO ao lado da
  receita, não contamina o lado do custo.

**O que bloqueia:** a matriz de docs/db/TAREFA_BATERIA_CICLO.md — todo
cenário com `tem_aditivo=True` fica `xfail(strict=True)` citando este achado.

**Decisão necessária:** a NF-e do aditivo deveria ser emitida vinculando-se a
um novo `Contrato` próprio, ou `_valores_segmentados_do_projeto` deveria somar
o Val_Cont de TODOS os orçamentos `complemento_pe=1` do projeto (original +
aditivos) ao resolver o que falta faturar? Alguma dessas é o desenho
pretendido, ou existe um terceiro mecanismo (fora deste código) que fatura o
aditivo por caminho manual?

---

**Escalada em 29/08/2026, medido no teste de ciclo:** o aditivo não é só
não-faturado — ele **não é cobrado do cliente**. O `Recebivel` nasce da
geração do contrato original, antes de o aditivo existir. Aditivo de
R$ 5.000,00 ficou preso em 2.1.06 até a Conciliação Final inclusive, e nunca
entrou em cobrança. Deixou de ser erro de relatório: é caixa que não entra.

**Regra do negócio registrada em 29/08 (dita pelo usuário, não estava escrita
em lugar nenhum):** o aditivo cobra **diferença de valores do Projeto
Executivo** — entre os ambientes planejados na venda e os efetivamente
encaminhados à produção no pedido. **Não tem XML novo**; se há XML novo, é
contrato novo e projeto novo. E ele ocorre, na maioria dos casos, **na
aprovação do PE, antes de existir NF-e**.

A terceira parte muda o conserto: com o aditivo já existente na emissão, a
soma resolve o faturamento numa única NF-e. Mas **não** muda o lado da
cobrança — os `Recebivel` nascem na geração do contrato, antes do PE, sempre.
Ordem do conserto e as medições em `docs/db/TAREFA_ADITIVO.md`.

---

### Medições de docs/db/TAREFA_ADITIVO.md (29/08) — Costuras 4, 3, 1, 2 + item 0

**Costura 4 — reproduzida com números (`tests/test_aditivo_costuras.py::
test_costura4_revisao_apos_aditivo_assinado_duplica_cobranca`, `xfail(strict=True)`):
CONFIRMADA.** Contrato de R$ 88.888,89 (VAVA, 1 ambiente, comissão de arquiteto 10%
repassada). Revisão 1 do PE (venda R$ 84.000): complemento = R$ 4.444,44 → aditivo #1
assinado → 2.1.06 creditado em R$ 4.444,44 (exato). Revisão 2 do MESMO ambiente,
DEPOIS do aditivo #1 assinado (venda R$ 90.000): `POST /pe/complemento/orcamento`
**reaproveita o MESMO `Orcamento`** que o aditivo #1 já referencia (get-or-create por
`projeto_id + complemento_pe=1 + parcela_id=None` — main.py:7863-7867) e sobrescreve
`valor_total` para R$ 11.111,11 — a diferença cheia contra a MESMA linha de base do
contrato original, não incremental sobre o que o aditivo #1 já cobriu.
`POST /api/projetos/<nome>/aditivo` com `{"novo": true}` cria o aditivo #2, com um
`aditivo.id` novo (portanto um `ref` novo em `registrar_evento`) apontando para esse
MESMO orçamento. Assinar o aditivo #2 credita 2.1.06 de novo pelo `valor_total`
ATUAL (R$ 11.111,11) — **total creditado pelos dois aditivos = R$ 15.555,55, quando a
diferença final real (revisão 2 já supera e substitui a revisão 1) é R$ 11.111,11**.
Os R$ 4.444,44 da revisão 1 foram cobrados duas vezes. Confirma as duas hipóteses da
tarefa juntas: (1) o upload de PE sobrescreve `valor_venda` sem checar aditivo já
assinado, e (2) `_complemento_diferencas`/`_pe_fator_contexto` sempre comparam contra
o `Contrato.orcamento_id`, nunca contra "contrato + aditivos já assinados". **Nada
impede — nem `renegociar_pe` nem a criação do aditivo #2 são bloqueados pelo aditivo
#1 já assinado.** A linha que a tarefa pede ("depois da assinatura do aditivo, a
diferença já virou lançamento — mudança é evento contábil, não sobrescrita") não
existe hoje em código nenhum.

**Costura 3 — vale em 100% dos casos. Medido: a tela NÃO coleta forma de pagamento do
aditivo. Decisão de produto formulada abaixo — não escolhida por conta própria (regra
da tarefa).** `POST /api/projetos/<nome>/aditivo/assinar` (main.py:9083-9138) só
recebe `parte`, `nome`, `cpf` — nenhum campo de pagamento, nem no corpo da
requisição nem em nenhum lugar antes dele no fluxo de assinatura. `_materializar_
recebiveis_venda_seguro` (main.py:812) tem um único chamador (main.py:13865, na
geração do CONTRATO), antes de o aditivo existir — mecanicamente alcançável para o
orçamento do aditivo (guarda de idempotência é por `orcamento_id`), mas **ninguém a
chama para `orcamento_complemento_id`**. Pergunta para decisão, com as opções que o
código já suporta:
- (a) A assinatura do aditivo passa a coletar forma de pagamento (novo campo na tela
  de assinatura) e chama `_materializar_recebiveis_venda_seguro` com o
  `orc_aj`/`pagamento_json` recebido — cria `Recebivel`s próprios do aditivo, com a
  MESMA mecânica do contrato.
- (b) O valor do aditivo é somado ao PRÓXIMO recebível em aberto do contrato original
  (ajusta um `Recebivel.valor_previsto` existente) — não cria linha nova, mas exige
  decidir qual parcela recebe o acréscimo.
- (c) Terceiro mecanismo fora deste código (cobrança manual, boleto avulso) — o
  aditivo nunca vira `Recebivel`, só o registro contábil (2.1.06/provisões) que já
  existe hoje.
Nenhuma das três está implementada; sem escolha do usuário, nenhuma foi presumida.

**Costura 1 — consumidores e predicado, medidos.** `_valores_segmentados_do_projeto`
tem **3 chamadores**: `_fin_faturamento_segmentado_seguro` (main.py:1331, credita o
razão), NF-e produto (main.py:14816, rescala os itens da fábrica para o total
Mercadoria) e NFS-e (main.py:14927, valor do serviço). Nenhum dos três usa o campo
`cfo` que a função já devolve — o docstring de `_fin_faturamento_segmentado_seguro`
promete reconhecer "CMV = CFO congelado... ref `cmv:<projeto>`", mas não existe
nenhum `registrar_evento`/lançamento com esse ref em código nenhum — **a promessa do
docstring não tem implementação**; achado isolado, à parte de qualquer soma futura.
Predicado: `complemento_pe=1` **não distingue** aditivo (legado, `parcela_id=None`)
de complemento por fase (`parcela_id=<id>`) — só `parcela_id` distingue. Risco
concreto: `POST /api/projetos/<nome>/aditivo` (main.py:8945-8947) filtra por
`parcela_id` **só se a requisição enviar essa chave**; sem ela, a query pega **o
`complemento_pe=1` de MAIOR id do projeto**, seja ele o legado ou de qualquer fase —
se as duas rotas de complemento coexistirem no mesmo projeto (nada as impede), o
aditivo pode amarrar no orçamento errado por ordem de criação, não por regra de
negócio. Se a soma da Costura 1 for implementada, o predicado precisa ser explícito
(ex.: enumerar exatamente quais `orcamento_id`s entram, não inferir por `parcela_id`
sozinho) — hoje a distinção está só na cabeça de quem escreveu o endpoint de aditivo,
como a tarefa antecipou. `cfo`: cada orçamento de complemento já tem seu próprio
`.cfo` recém-calculado, e `_fin_provisoes_venda_seguro` (chamado na assinatura do
aditivo) JÁ reconhece esse `cfo` como provisão `custo_fabrica` própria — somar `cfo`
de contrato+aditivos em `_valores_segmentados_do_projeto` não duplicaria nada, desde
que a soma leia o mesmo conjunto de orçamentos usado para a soma do `val_cont`. `seg`:
não medido além do código-fonte — a segmentação vem de `Projeto.parametros_json`
(live, não de um snapshot por orçamento); um aditivo assinado depois de uma mudança
de parâmetro herdaria a segmentação ATUAL do projeto no momento da NF-e, não a que
valia quando o aditivo foi negociado — mesma classe de risco que o ACHADO-19 already
descreve para `parametros_json`, não uma novidade desta tarefa. `orc`: nenhum
consumidor externo de `_valores_segmentados_do_projeto` usa a chave `orc` do retorno
além da própria função (`round(float(getattr(orc, "cfo", 0)...`); pode virar uma
lista sem quebrar consumidor nenhum hoje.

**Costura 2 — teste de regressão escrito e ANTES de qualquer conserto
(`tests/test_aditivo_costuras.py::test_costura2_reemissao_nao_duplica_o_ja_faturado`,
`xfail(strict=True)`): a regressão que a tarefa temia É REAL, e pior do que a
suspeita original. `faturar_segmento` decide o split usa/resto (quanto sai de 2.1.06
"adiantado" vs. quanto vira `1.1.02` "a receber") pelo saldo ATUAL da conta — mas
**usa+resto sempre soma o `valor` recebido por inteiro, creditado em 4.1.01/4.2.01**.
O split não tem nenhuma noção de "quanto desta receita já foi reconhecido antes" —
só decide QUAL conta de contrapartida absorve o débito. Reproduzido: contrato
R$ 88.888,89 (100% mercadoria), fechamento credita 2.1.06, 1ª NF-e fatura R$ 88.888,89
(drena 2.1.06 a zero). Aditivo assinado (+R$ 4.444,44 em 2.1.06). Simulada a soma da
Costura 1 (monkeypatch em `_valores_segmentados_do_projeto`, SEM implementá-la de
verdade) devolvendo R$ 93.333,33 (88.888,89+4.444,44). 2ª NF-e: **4.1.01 fecha em
R$ 182.222,22** (R$ 88.888,89 da 1ª + R$ 93.333,33 da 2ª) — não em R$ 93.333,33, que
seria o correto. **Isto não é exclusivo da soma da Costura 1**: já é verdade HOJE,
sem nenhuma soma, para qualquer segundo documento fiscal emitido pro mesmo segmento
do mesmo projeto — é o MESMO mecanismo do ACHADO-13, agora confirmado com números no
contexto do aditivo. **Conclusão prática: não dá pra somar a Costura 1 sem antes (ou
junto) consertar `faturar_segmento` para ser delta-aware na conta de RECEITA, não só
no split do débito** — exatamente a ordem que a tarefa pediu para não inverter.

**Item 0 — divergência dos dois mecanismos, medida.** Os dois estão **simultaneamente
vivos na UI hoje** (static/index.html): o legado (checkbox "Renegociar" + upload de
XML `finalidade=complemento`, linhas 21489/21637/21689 — tela 11c/comparação de
venda) e o novo por fase (`peConciliacaoDecidir`/`peConciliacaoGerarComplemento`,
linhas 22045-22088 — tela AF2/`ConciliacaoPeFase`) — não são um substituindo o outro
na tela, coexistem. A regra "XML novo ⇒ projeto novo" **está escrita em código, não
só no desenho**: toda rota que cria/sobrescreve/renomeia um `PoolAmbiente` (a criação
via XML "do pool", i.e. um AMBIENTE NOVO — main.py:11875, 11960, 12042, 12084) checa
`_contrato_assinado(nome_safe, db)` e recusa com 403 "Contrato assinado — alterações
não permitidas" — a mesma trava, msm texto, em toda rota de pool. O `ArquivoPE`
(upload de PE/complemento, `xml_pe`/`xml_compl`) foi desenhado para não esbarrar
nessa trava (correto — ele não cria `PoolAmbiente`), então a fronteira é real, não
coincidência de ordem de tela. **Não medido** (fora do escopo — exigiria consultar
dado real dos 4 ambientes, não pedido nesta tarefa): quantos projetos em produção
ainda têm `ArquivoPE.formato='xml_compl'` gravado (dependência real do legado). **O
que quebra se `finalidade=complemento` parar de gravar:** nada crasha —
`_complemento_diferencas` já trata `compl_carregado=False` como estado normal
("PE não carregado" na tela); o legado ficaria mostrando zero para todo ambiente
marcado, sem erro. Nenhum outro código lê `formato="xml_compl"` além dessa função.

## ACHADO-13 — `faturar_segmento` duplica receita se chamado 2x para o mesmo segmento · RESOLVIDO 30/08/2026

**RESOLVIDO (docs/db/TAREFA_ACHADO13.md, passo 5 do ROTEIRO).**
`faturar_segmento` (mod_contabil.py) passou a ler o já-reconhecido do
próprio livro (`_mov(..., "4.1.01"/"4.2.01", "credor", ...)` — medido como
LÍQUIDO de estornos em `tests/test_mov_credor_liquido_estorno.py`, não
bruto) e a faturar só o **delta** contra o `valor` recebido, que passou a
significar "o total que deve estar reconhecido", não um incremento. Delta
negativo é recusado com erro nomeado (citando os dois números); delta ~0 é
no-op; o split usa/resto não mudou — passou a repartir o delta em vez do
total. Único chamador em produção (`main.py:1338`, dentro de
`_fin_faturamento_segmentado_seguro`) já passava o total do segmento a
cada chamada — não precisou de ajuste. `tests/test_aditivo_costuras.py::
test_costura2_reemissao_nao_duplica_o_ja_faturado` perdeu o `xfail` no
mesmo commit do conserto.

**Escalado em 29/08** (histórico, antes do conserto): deixou de ser "não
confirmado". A Costura 2 da
`TAREFA_ADITIVO` reproduziu: o split usa/resto decide apenas **qual conta
absorve o débito** — a receita em 4.1.01/4.2.01 é creditada pelo **valor
cheio a cada chamada**, sem nenhuma noção de quanto já foi reconhecido.
Segunda emissão para o mesmo segmento do mesmo projeto: 4.1.01 fechou em
R$ 182.222,22 onde o correto era R$ 93.333,33. O que continua não medido é a
frequência em produção, não o mecanismo.

**Consequência de ordem:** a soma do ACHADO-12 (contrato + aditivos) **não
pode** ser implementada antes disto. Somar sem tornar `faturar_segmento`
delta-aware na conta de receita transforma um defeito raro em defeito de
todo projeto com aditivo.


**O que acontece:** `faturar_segmento` sempre recalcula `usa`/`resto` a
partir do saldo ATUAL de 2.1.06 do projeto (não de um valor incremental
próprio do documento) a cada chamada. Se dois documentos fiscais forem
emitidos para o MESMO segmento do MESMO projeto (duas NF-e's de
"mercadoria", por exemplo), a segunda chamada, com 2.1.06 já drenado a zero
pela primeira, lançaria o valor segmentado inteiro de novo como "a
receber"/receita — um duplo-reconhecimento independente do caso do
aditivo (ACHADO-12).

**Evidência:** mod_contabil.py:1449-1479 (`faturar_segmento`) — `usa =
min(saldo_adiantamento_projeto(...), valor)`; sem esse saldo, todo o
`valor` cai no `resto` (`faturamento_%s_a_receber`), incondicionalmente.

**Consequências no número final:** não medidas — não confirmei se o fluxo
de negócio permite duas NF-e's do mesmo segmento por projeto na prática
(pode ser que cada segmento só receba UM documento fiscal por design, o que
tornaria isto inatingível). Achado de baixa confiança, registrado para
constar.

**O que bloqueia:** nada, até confirmação.

**Decisão necessária:** o fluxo permite emitir mais de uma NF-e de
mercadoria (ou de serviço) para o mesmo projeto? Se sim, `faturar_segmento`
precisa de um controle por documento (não só por segmento) antes de ser
chamado de novo nesse cenário.

---

## ACHADO-15 — `real` e `competencia_estimada` divergem quando o projeto fecha sem efetivação · APOSENTADO 31/08/2026

**O que acontece:** se um projeto chega à Conciliação Final (etapa 21) sem
que as rubricas de custo "matching pleno" (montagem, custo de fábrica,
frete etc.) tenham sido efetivadas (`efetivar_provisao`), a DRE `real()`
nunca reconhece esse custo — `conciliar_final`/`resolver_saldo_provisao`
cancela a provisão contra o ativo diferido sem tocar a DRE (por desenho,
FASE D2). `dre_simulada('competencia_estimada')`, por outro lado, sempre
mostra o valor CONSTITUÍDO (a estimativa da venda) como custo,
independente de ter sido efetivado ou resolvido depois — as duas visões
nunca reconciliam nesse cenário. Isso responde à pergunta central de
docs/db/TESTE_DRE_CICLO.md: **elas não batem, e a diferença é medida e
estrutural, não um bug pontual.**

**Evidência:** `tests/test_dre_ciclo_completo_e2e.py::test_ciclo_completo_tres_visoes_dre`
— no marco `6a_nfe_produto_emitida` (repete em todos os marcos seguintes
até a conclusão do projeto): `real["cmv_csp"] == 0.00` vs
`dre_simulada('competencia_estimada')["cmv_csp"] == 42000.00` (CFO =
R$ 40.000,00 + demais rubricas de custo padrão da provisão), com receita
IDÊNTICA nas duas visões (R$ 58.500,00) no mesmo período — ver
docs/db/RELATORIO_DRE_CICLO.md para a tabela completa, marco a marco.
mod_contabil.py:2940-2945 (`constituido = total_lancado(...,"credito",...,
excluir_origens={_ORIGEM_RESOL_FALTA}) - total_lancado(...,"debito",...,
origens={_ORIGEM_RECLASS})`) nunca subtrai a baixa de
`_ORIGEM_RESOL_SOBRA` (o cancelamento que `resolver_saldo_provisao` grava
quando a provisão nunca foi efetivada) — por isso o "constituído"
permanece com o valor cheio mesmo depois do projeto fechar com a provisão
cancelada.

**Consequências no número final:**
- Toda vez que um projeto FECHA (etapa 21) sem que TODAS as rubricas
  operacionais tenham passado por `efetivar_provisao`, a DRE `real` relata
  lucro bruto/EBITDA/lucro líquido INFLADOS pelo custo nunca reconhecido
  (no cenário medido: R$ 42.000,00 de diferença sobre R$ 58.500,00 de
  receita — quase 72% de sobrestimativa de lucro bruto).
- `competencia_estimada`, que deveria ser uma aproximação de `real`, na
  prática é a única visão que reflete o custo estimado da venda — mas
  também nunca é corrigida quando a provisão é formalmente cancelada (o
  "constituído" ignora a baixa de sobra), então nem ela reflete com
  precisão o que aconteceu de fato depois do fechamento.
- Nenhuma das duas visões avisa o usuário que o ciclo fechou com custo
  pendurado — silencioso, no mesmo padrão dos ACHADO-01/12.

**O que bloqueia:** decidir o rename/consolidação de `real`/
`competencia_estimada` (o objetivo original de docs/db/TESTE_DRE_CICLO.md)
— elas não são a mesma coisa hoje, e a causa é estrutural (timing de
efetivação), não um bug pontual fácil de corrigir sem decisão de negócio.

**Decisão necessária:** a Conciliação Final deveria FORÇAR (ou pelo menos
avisar) que as rubricas operacionais sejam efetivadas antes de fechar o
projeto — hoje ela só trata Impostos/Custo Financeiro com cuidado (item 5
de TAREFA_PROVISOES.md, já decidido: avisar+listar), mas resolve as outras
rubricas em silêncio, sem nunca reconhecer a despesa real? Ou a DRE `real`
deveria reconhecer, no momento da Conciliação Final, o custo cancelado
como despesa (mesmo sem execução física confirmada), pra não subestimar
custo?

**Remedição pós-Fase 1, 31/08/2026 (docs/db/TAREFA_REMEDICAO_DRE.md):** a
"decisão necessária" acima foi tomada — o passo 8 (ACHADO-16) passou a
exigir um veredito nomeado por rubrica em aberto na Conciliação Final.
Medido: `real` e `competencia_estimada` continuam divergindo entre
`6a_nfe_produto_emitida` e `7_recebimento` — mesmos números de antes da
Fase 1 (`cmv_csp`: 0,00 vs 42.000,00, receita idêntica) — mas, quando o
veredito escolhido reconhece o custo cheio (`encerrada_valor_menor` @
42.000,00, o cenário testado), as duas visões **reconciliam no marco
final**: o projeto deixou de fechar com margem de 100% (era
`lucro_liquido = 95.000,00`; agora `53.000,00`, igual a
`competencia_estimada`).

**Decisão de Marcelo, 31/08/2026: aposentar o achado.** Divergir durante
o ciclo — entre a NF-e e a Conciliação Final — é o MODELO, não o defeito:
decisão de 07/08 (mod_contabil.py:1826-1832) já estabelecia que a despesa
entra em `real()` só na competência REAL da efetivação; `competencia_estimada`
é projeção por desenho e sai inteira na Fase 4. Verificado antes de
aposentar: toda divergência de meio de ciclo, em todo marco, se resume a
uma única causa (`cmv_csp` e sua cascata aritmética em
`lucro_bruto`/`ebitda`/`lucro_liquido`) — nenhuma outra linha diverge em
nenhum marco, então não há remanescente sem explicação pelo desenho.

`xfail(strict=True)` removido de `test_ciclo_completo_tres_visoes_dre`; a
asserção mudou de "bate em todo marco" para "bate no fechamento
(`8_conclusao_projeto`)" — divergências de meio de ciclo continuam
capturadas e reportadas, só deixaram de ser tratadas como falha. Teste
roda PASSED. Relatório completo, marco a marco, em
docs/db/RELATORIO_DRE_CICLO_POS_FASE1.md.

---

## ACHADO-14 — "Total Flex" virou "Parcelamento Loja" e o rename não chegou · RESOLVIDO 29/08/2026

Produto renomeado; código e nome da conta 2.1.05 no banco não acompanharam.
Mesmo padrão de 1.1.09/2.1.09: rename em código não alcança base existente.

Resolvido: arquivos renomeados, migration 95c7e64afc6a para o nome da conta.
Dívida aceita: o identificador `total_flex` continua no wire do frontend, com
alias. Sai quando alguém tocar naquela tela.

---

## ACHADO-16 — Provisão cancelada em silêncio na Conciliação Final torna a margem fictícia · RESOLVIDO 30/08/2026

**RESOLVIDO (docs/db/TAREFA_ACHADO16.md, passo 8 do ROTEIRO).** O maior
conserto da auditoria — muda fluxo, não só número. `conciliar_final` não
resolve mais saldo de provisão sozinha: toda rubrica aberta (grupo `2.1.04.x`,
exceto Impostos e Custo Financeiro) exige um **veredito nomeado**
(`resolver_veredito_provisao`, nova tabela `VeredictoProvisao` — quem
decidiu, quando, com qual motivo), e a chamada é recusada, tudo ou nada, se
faltar veredito para qualquer rubrica em aberto ou se alguma vier
`ainda_vai_chegar`.

- **A regra das duas pernas** (`encerrada_valor_menor`): efetiva pelo valor
  real via `efetivar_provisao` (é isto que reconhece o custo em 5.1.01 — a
  única porta pela qual custo entra na DRE) e **só então** reverte o resíduo
  via `resolver_saldo_provisao`. Reverter sem efetivar reproduziria o
  ACHADO-16 com outro nome. `valor_efetivado=0` é válido e comum: cobre a
  rubrica já efetivada mais cedo no projeto, chegando aqui só com o resíduo
  a reverter.
- **`não se aplica`** reverte o saldo integralmente, mas exige `motivo`
  escrito — recusado sem ele.
- **`ainda vai chegar`** não resolve nada; o projeto continua aberto.
- **Custo financeiro (2.1.04.19) não segue a regra de reversão** — guarda do
  ACHADO-01, tanto em `conciliar_final` (nunca pede veredito para ele) quanto
  em `resolver_veredito_provisao` (recusa explícita se chamado com ele).
- **O relatório** `relatorio_projetos_encerrados_por_reversao` (+ endpoint
  `GET /api/financeiro/projetos-encerrados-por-reversao`) veio no mesmo
  commit, não depois: projetos encerrados por `encerrada_valor_menor`/`nao_
  se_aplica`, ordenados pelo valor revertido (maior primeiro), motivo ao
  lado — o contra-controle para a reversão não virar formalidade.
- A resposta de `POST /api/projetos/<nome>/ciclo/21/conciliar` trocou a
  chave `"resolvido"` por `"vereditos"` (veredito + valor_efetivado +
  valor_revertido por rubrica) — a palavra "resolvido" não cabia mais para
  uma decisão nomeada.

`tests/test_aceite_achado16.py::test_conciliacao_final_recusa_com_provisao_
nunca_efetivada` perdeu o `xfail(strict=True)` do passo 1 neste commit — a
recusa é agora o comportamento correto, não mais um bug pendente. O teste de
medição do mecanismo antigo (`test_mecanismo_hoje_cancela_saldo_sem_tocar_
5101`) foi **reescrito**, não consertado para continuar verde: o mecanismo
que ele documentava (cancelar sem tocar 5.1.01 incondicionalmente) não existe
mais — o novo teste prova, no mesmo cenário motivador do achado, que
`encerrada_valor_menor` reconhece o custo real (5.1.01) antes de reverter o
resíduo genuíno, as duas pernas verificadas separadamente.

**Histórico da medição (antes do conserto):**

**GRAVE. Medido em 29/08/2026 pelo teste de ciclo completo das DREs.**

### O que acontece
Uma provisão constituída na venda e **nunca efetivada** é cancelada na
Conciliação Final contra o ativo diferido — sem tocar a DRE, sem alerta, sem
registro de que a estimativa foi descartada.

### O número medido
Projeto entregue com receita de R$ 90.000,00 e `cmv_csp` = **zero**. Lucro
bruto de 100%. Na venda o sistema estimava R$ 42.000,00 de custo; no
fechamento jogou a estimativa fora.

O livro não está mentindo — está sendo fiel. Ninguém lançou o custo. O
problema é que **o sistema decide sozinho que o custo não existiu.**

### Por que isso importa
Provisão que chega à conclusão sem efetivação é uma de duas coisas:
- um custo que realmente não aconteceu — raríssimo, não se entrega móvel
  sem comprar;
- **um custo que aconteceu e ninguém lançou** — o caso comum.

O sistema assume a primeira, em silêncio. Basta um assistente esquecer a
nota da fábrica e o projeto fecha com margem inventada, sem nenhum sinal.

### Consequências
- Margem por projeto pode ser fictícia, sempre para cima.
- Comparação entre lojas fica distorcida a favor de quem lança pior.
- A variância provisão × realizado, que seria o instrumento para detectar
  isso, é justamente o que o cancelamento apaga.

### DECIDIDO 29/08/2026 — recusar o fechamento; toda provisão é resolvida antes

**A Conciliação Final não fecha o projeto enquanto houver provisão em
aberto.** Não existe cancelamento silencioso, e não existe cancelamento
confirmado com um clique: cada rubrica aberta precisa de um **veredito
nomeado** de uma pessoa, e o veredito é uma resposta a uma pergunta
específica, não um "OK".

Os quatro vereditos possíveis, e o que cada um faz no livro:

| veredito | quando | efeito |
|---|---|---|
| **efetivada** | o documento real chegou pelo valor previsto | nada a fazer; já lançado |
| **encerrada com valor menor** | o documento real chegou por menos | o realizado vira custo; **o resíduo reverte o custo** (a margem melhora, e isso é honesto — foi superprovisionado) |
| **não se aplica** | a rubrica não incide neste projeto | o saldo reverte o custo integralmente; exige motivo escrito |
| **ainda vai chegar** | a despesa existe e o documento não chegou | **não resolve — o projeto não fecha** |

O quarto veredito é o que faz esta decisão funcionar sem virar pressão para
chutar. Ninguém é obrigado a inventar um valor para encerrar: a pessoa pode
dizer "ainda vai chegar", e o projeto fica honestamente aberto.

**A pergunta que a disciplina exige** (formulada pelo usuário ao decidir):
*ainda há despesa a realizar?* O sistema não consegue distinguir
"superprovisionado" de "a nota ainda não chegou" — os dois têm a mesma
aparência no banco. Só uma pessoa que olhou o pedido sabe. É por isso que a
resolução é obrigatória e é humana.

**Não confundir com o ACHADO-01.** Aqui o resíduo reverte custo porque a
despesa é futura e não veio, ou veio menor — é correção de estimativa. No
custo financeiro o deságio já foi retido na origem, não há pagamento futuro,
e o acerto da provisão é puro balanço. Mecânicas diferentes; aplicar a regra
de um no outro reintroduz o erro que o ACHADO-01 registra.

**O risco que esta decisão aceita, e o contra-controle.** Projetos vão ficar
abertos, e a pressão será para marcar "não se aplica" só para encerrar. A
reversão de resíduo **melhora** a margem — então um projeto que fecha com
reversão grande é exatamente o que se quer olhar. Relatório de controle:
projetos encerrados por reversão, ordenados pelo valor revertido, com o
motivo escrito ao lado. Sem esse relatório, a decisão vira uma formalidade.

Isso amplia o item 5 da TAREFA_PROVISOES: a fila não é só de Impostos e
Custo Financeiro — é de **toda provisão que fecha sem efetivação**.

---

## ACHADO-17 — `2.1.04.12 "Retenção de Comissão de Vendas"`: o nome descreve o que o código não faz

O conceito pretendido: a comissão **nasce retida**, é liberada quando paga,
pode ficar retida parcialmente até a entrega ou por erro de projeto do
consultor, e o **resíduo revertido em favor da empresa vira receita** que
compensa outras despesas.

O mecanismo atual é uma provisão simples: nasce na 2ª assinatura, a Folha
resolve. Não há retenção parcial, condição de liberação nem reversão para
receita.

Não há duplicidade de saldo (medido, ACHADO-05 fechou). O problema é que
quem lê o plano de contas acredita que a funcionalidade existe.

**Consequência:** nenhuma hoje no número. A funcionalidade de retenção
simplesmente não existe — o que é uma decisão de produto pendente, não um
defeito contábil.

**A decidir:** implementar a retenção como concebida, ou renomear a conta
para o que ela de fato é (provisão de comissão)?

---

## ACHADO-18 — NF-e sem `valor_total` não lança nada, em silêncio · RESOLVIDO 30/08/2026

**RESOLVIDO (docs/db/TAREFA_ACHADO18.md, passo 9 do ROTEIRO).** Guarda
explícita de `valor_total > 0`, recusa com mensagem, em `POST /api/projetos/
<nome>/contrato` e `POST /api/projetos/<nome>/ciclo/15/emitir-nfe` (main.py).
A guarda **lê, não recalcula** — a mesma disciplina de "presença de
ambiente" que já existia para contrato, agora acompanhada da checagem de
valor (as duas perguntas são diferentes e as duas importam, como o DECIDIDO
abaixo já previa).

Detalhe que mudou desde a medição (ACHADO-12/passo 7 somou contrato +
aditivos assinados na receita): a guarda de NF-e lê o **total contratado**
(`valor_contratado_do_projeto`), não só o `valor_total` do orçamento do
contrato — um contrato zerado com aditivo assinado positivo não é recusado.
A guarda de contrato, ao contrário, olha só o `valor_total` do orçamento
sendo contratado (aditivos ainda não existem nesse momento — nascem depois
do primeiro contrato). NFS-e não ganhou a guarda: seu valor é manual
(`valor_servico`, informado pelo operador na emissão), já guardado por
`valor <= 0` — aplicar a regra do Val_Cont ali quebraria o desenho.

Os dois `xfail(strict=True)` do passo 4
(`test_gerar_contrato_recusa_valor_total_zero`,
`test_emitir_nfe_recusa_valor_total_zero`) saíram neste commit.
`test_emitir_nfe_passa_com_aditivo_assinado_positivo_mesmo_com_contrato_zerado`
prova o caso novo do detalhe acima. Vários testes pré-existentes
construíam orçamento com ambiente vinculado direto no banco (sem passar pelo
recálculo real) e por isso tinham `valor_total` nulo/zero — deram esse valor
a si mesmos (`_setup_cenario`, `_reset15`, e alguns testes individuais),
matching o que um projeto real teria.

---

**Histórico da medição (antes do conserto):**

**Resposta direta:** a UI/API real **não alcança** o cenário do fail-soft
silencioso. Mas o motivo importa mais que a resposta — ver abaixo.

### O que impede, hoje
Não é uma validação explícita de `valor_total > 0`. É um fato mecânico: o
único caminho real pelo qual um ambiente com valor passa a integrar um
orçamento — `POST /orcamentos/<oid>/ambientes/<pid>` (main.py:12229-12285),
e as variações de sobrescrita/nova-versão de XML do mesmo pool
(main.py:11875, 11957) — já chama `_recalcular_orcamento` (que persiste
`valor_total`) **na mesma requisição, sem try/except ao redor**
(main.py:12278): se o recálculo falhar, a requisição inteira falha
(`db.rollback()`) e nada é anexado. Não existe caminho de duplicar/clonar
orçamento que copie o vínculo de ambiente sem recalcular (grep confirma:
nenhuma ocorrência de "duplicar"/"clonar" em main.py). A geração de
contrato também exige "ao menos um ambiente" (main.py:13729-13736) — mas
essa checagem é de PRESENÇA de ambiente, não de `valor_total`.

**Medido e confirmado com testes** (`tests/test_failsoft_nfe_medicao.py`):
anexar um ambiente ao orçamento pelo endpoint real persiste `valor_total`
na mesma chamada; gerar contrato de um orçamento sem nenhum ambiente é
recusado (400, "ambiente").

### Por que isso não fecha o caso
A pergunta do próprio ACHADO era "é ordem de tela ou é validação
deliberada?" — e a resposta é **ordem de tela, não validação**. Nenhum
código verifica `valor_total > 0` em lugar nenhum do caminho
contrato→assinatura→NF-e; o que impede hoje é a COINCIDÊNCIA de que o
único jeito de dar valor a um orçamento já recalcula no mesmo golpe. Um
redesenho futuro que anexe ambiente por outro caminho (importação em lote,
API de integração, correção manual de banco por suporte) reabriria o
fail-soft silencioso sem que nenhum teste ou validação acuse — porque não
há guarda, só sorte de desenho.

**Consequências no número final:** nenhuma hoje — não é alcançável por
nenhum caminho conhecido.

**O que bloqueia:** nada.

**Decisão necessária:** vale adicionar uma validação EXPLÍCITA de
`valor_total > 0` antes de gerar contrato e antes de emitir NF-e — não
porque o caminho atual falhe, mas porque hoje a proteção é acidental
(nenhum teste passaria a falhar com essa validação a mais; ela só se torna
visível se algum caminho futuro tentar contornar a coincidência atual)?

### DECIDIDO 29/08/2026 — sim, e por um motivo diferente do que a pergunta supunha

A validação entra. Não como cinto de segurança para um cenário improvável:
o ACHADO-19, escrito logo abaixo, mostra que o fail-soft **é alcançável**,
por seis rotas reais, e que a medição desta seção examinou o único ponto de
entrada que não tem o problema.

O que fica decidido, na ordem:

1. **`valor_total > 0` vira guarda explícita** na geração de contrato e na
   emissão de NF-e. Recusa com mensagem, `ok: False`. Hoje nenhum teste
   muda de cor com isso — é exatamente o sinal de que a guarda é barata.
2. **A guarda é a segunda linha, não a primeira.** A primeira é o
   ACHADO-19: enquanto seis rotas responderem `ok` a um recálculo que
   falhou, a guarda só transforma "escritura errado" em "recusa no fim do
   caminho", depois de o vendedor ter fechado a venda.
3. **A checagem de presença de ambiente (main.py:13729) fica**, e passa a
   ser acompanhada da checagem de valor. Presença e valor são perguntas
   diferentes e as duas importam.

O princípio, para não reabrir a discussão: **proteção acidental não é
proteção — é uma coincidência que ninguém documentou e que o próximo
redesenho desfaz sem avisar.** O custo de escrever a guarda é uma linha; o
custo de descobrir que ela faltava é uma nota fiscal emitida sobre valor
zero.

---

## ACHADO-19 — seis dos nove caminhos que gravam `valor_total` engolem a falha e respondem "ok" · MEDIDO 29/08/2026: REBAIXADO PARA GRUPO 5, COM UMA EXCEÇÃO

**Este achado reabre o ACHADO-18.** A medição de 29/08 concluiu "não
alcançável hoje" olhando UM ponto de entrada (`POST
/orcamentos/<oid>/ambientes/<pid>`, que de fato não tem try/except). Mas
`_recalcular_orcamento` — a única função que persiste `orc.valor_total` e as
14 colunas-sombra do motor (main.py:17337) — é chamada de **nove** lugares.
Em **seis** deles a exceção é engolida e a resposta ao cliente é `ok: True`.

### Os nove chamadores

**Falham alto (corretos) — respondem `ok: False`:**

| linha | rota |
|---|---|
| 11932 | sobrescrita de XML do pool |
| 12184 | `POST /orcamentos/<id>/ambientes/<pid>` — remover ambiente |
| 12278 | `POST /orcamentos/<id>/ambientes/<pid>` — adicionar ambiente |

**Falham baixo (fail-soft) — respondem `ok: True`:**

| linha | rota | o que fica commitado mesmo assim |
|---|---|---|
| 7891  | `/api/projetos/<n>/pe/complemento/orcamento` | `forma_pagamento = None`, `negociacao_json = None` |
| 7956  | `/api/projetos/<n>/pe/complemento/fase/<f>`  | inclusão/exclusão de ambientes do orçamento |
| 10893 | `/api/projetos/<n>/parametros`               | o `parametros_json` novo, por orçamento |
| 10966 | `/api/orcamentos/<id>/margens`               | `desconto_pct` novo |
| 15655 | `/api/orcamentos/<id>/descontos`             | `desconto_individual_pct` de cada ambiente |
| 15871 | `/orcamentos/<id>/valor` (PATCH)             | `forma_pagamento`, `negociacao_json` |

### Por que é pior que o ACHADO-18

O ACHADO-18 descrevia um `valor_total` **ausente** — a NF-e não escritura
nada, e o vazio é pelo menos detectável. Aqui o `valor_total` fica
**presente e plausível**: é o número da negociação anterior, sobrevivendo a
uma mudança de insumo que foi gravada. O banco guarda um desconto novo e um
valor calculado sobre o desconto velho, e nada na tela diz isso.

Em cinco dos seis casos a entrada do usuário é commitada **antes** ou
**depois** do recálculo falho, nunca junto: em 10966 e 15655 o `db.commit()`
do desconto já aconteceu e o `db.rollback()` seguinte só desfaz o recálculo;
em 7891, 7956, 10893 e 15871 o `db.commit()` vem depois do `except` e leva a
alteração junto. Não existe um caso em que insumo e resultado andem na mesma
transação.

### Medição 1 (29/08) — `_negociacao_breakdown` levanta com que entrada?

`docs/db/TESTE_NEGOCIACAO_VALOR_TOTAL.md`, `tests/test_negociacao_breakdown_excecoes.py`
(11 testes). Cada candidato listado na tarefa foi **construído em banco**, não presumido:

| candidato | levanta? | produzível por usuário via endpoint real? |
|---|---|---|
| `parametros_json` malformado (`json.loads`, main.py:17258, sem try/except) | **SIM** — `JSONDecodeError` | NÃO — os 3 pontos de escrita reais (main.py:1289, 10889, 17677) sempre gravam `json.dumps(dict)` |
| `complemento_pe=1` no MESMO orçamento que já é `Contrato.orcamento_id` do projeto (auto-referência) | **SIM** — `RecursionError` (achado novo, fora da lista original) | NÃO confirmado — o endpoint real de criação de complemento sempre cria um Orçamento novo e separado |
| `forma_pagamento` malformado / `total_cliente` não numérico | não | guardado por try/except (main.py:17296-17301) |
| ambiente sem `budget_total`/`order_total` | não | guardado (`or 0.0`) |
| `complemento_pe` sem contrato do projeto | não | guardado (`for l in (linhas_c or [])`) |
| complemento por fase sem `ConciliacaoPeFase` | não | guardado, resumo com totais zerados |
| `desconto_pct` fora de 0-100 (ex.: 150) | não levanta (resultado sem sentido, mas não crasha) | — |
| `config_financeira_json` malformado | não | guardado por try/except (main.py:17250-17254) |
| `carga_trib` zerado como divisor | **hipótese da tarefa não se confirma** — `mod_negociacao.py:30` usa `carga_trib` só como multiplicador (`prov_imp = pct_trib * val_cont`), nunca como divisor | — |
| `projeto_id` órfão | não | guardado |

**Resposta à pergunta da tarefa:** a única exceção real é `JSONDecodeError` em `parametros_json`
malformado, mais o `RecursionError` (achado novo). **Nenhuma das duas é alcançável por um
usuário através dos 3 endpoints reais que escrevem `parametros_json`, nem do endpoint real de
criação de complemento.** Pela regra que a própria tarefa definiu: o ACHADO-19 continua valendo
(a resposta `ok` a uma falha continua errada) mas **desce de prioridade — o conserto é higiene do
Grupo 5, não urgência do Grupo 1.** O `RecursionError` fica registrado como risco de robustez
(uma correção manual de suporte ou migração futura poderia produzir o estado auto-referente),
não como caminho de exploração hoje.

### Medição 2 (29/08) — o que fica no banco depois de cada fail-soft

`tests/test_fail_soft_medicao2.py`. Recálculo forçado a falhar via monkeypatch (Medição 1 não
achou entrada real produzível pelo usuário para forçar a falha organicamente). Comparação
coluna por coluna, nunca por total:

| rota | o que persiste mesmo com recálculo falho | `valor_total`/sombras mudam? | resposta HTTP |
|---|---|---|---|
| 10966 `/margens` | `desconto_pct` novo (0→25) | não — ficam no valor anterior | `200 {"ok": true, "sombra": null, "erro_sombra": "..."}` |
| 15655 `/descontos` | `desconto_individual_pct` novo do ambiente (0→20) | não | `200 {"ok": true, "sombra": null, "erro_sombra": "..."}` |
| 10893 `/parametros` | `parametros_json` novo (`comissao_arq_ativa`, `comissao_arq_pct`) | não | `200 {"ok": true, "sombra": {...recalculado ao vivo...}}` — ver Medição 3 |
| 15871 `/valor` (PATCH) | `forma_pagamento` novo | não | `200 {"ok": true}` |
| 7891 `/pe/complemento/orcamento` | `forma_pagamento`/`negociacao_json` zerados (parte do wiring da rota) | não | `200 {"ok": true, "orcamento": {...}}` |

**Não existe rota, das seis, onde insumo e resultado ficam consistentes.** Em nenhuma delas o
`valor_total`/sombras persistidos acompanham o novo insumo quando o recálculo falha — todas
deixam a mesma assinatura: insumo novo commitado, resultado numérico velho. Não há "modelo do
conserto" pronto entre as seis; o conserto (transação única) precisa ser desenhado do zero.

### Medição 3 (29/08) — a tela mostra o número que o banco não tem?

Reproduzido: falha forçada só no recálculo, comparando o `sombra` da resposta HTTP com a linha
persistida no banco.

- **`/parametros` (10893): SIM — erro invisível confirmado.** `main.py:10893`,
  `brk = _negociacao_breakdown(proj_orcs[0], db) if proj_orcs else None`, roda **fora e
  incondicionalmente** do laço `try/except` que envolve `_recalcular_orcamento` — é uma segunda
  chamada, de leitura pura, sobre o `parametros_json` **já commitado** (linha 10889, antes do
  laço). Reproduzido com `comissao_arq_pct` mudando de 8%→15%: o banco ficou com `Cust_Ad`/`Val_Cont`
  **inalterados** (diff vazio nas 14 colunas-sombra) enquanto a resposta trouxe
  `"sombra": {"Com_Arq": 8100.0, "Val_Cont": 54000.0, ...}` — o número novo, calculado ao vivo, que
  o banco não tem.
- **`/margens` (10966): NÃO.** `main.py:10966-10970`, a chamada a `_negociacao_breakdown` está
  **dentro** do mesmo `try` que embrulha `_recalcular_orcamento` — só é alcançada se o recálculo
  teve sucesso. No `except`, a resposta é explicitamente `"sombra": None, "erro_sombra": str(_e)}`
  (main.py:10973). Reproduzido: `erro_sombra` presente, `sombra` nulo. A prosa original deste
  achado generalizava demais ao citar 10966 junto de 10893 — **medido: o agravante da tela só
  existe em 10893.**
- **`/descontos` (15655): NÃO**, pelo mesmo motivo e mesmo padrão de código que `/margens`
  (confirmado no mesmo teste da Medição 2: `sombra: None, erro_sombra` presente).

**Conclusão da Medição 3:** o "erro invisível" (tela mostra o novo, banco guarda o velho) é
real, mas **restrito a uma única rota — `/parametros` (10893)** — não às duas que o achado
original apontava. É a rota que **mais precisa** do conserto de transação única, porque hoje é a
única onde o próprio sistema mostra ao usuário um número que nunca chegou a existir no banco.

### Pode mesmo falhar?

Sim, mas por um caminho mais estreito do que a lista original de candidatos sugeria — ver
Medição 1 acima. A hipótese "divisão por carga tributária zerada" não se confirma no código
atual; `mod_negociacao.py:30` usa `carga_trib` só como multiplicador.

**Consequências no número final:** `valor_total` defasado alimentaria
contrato, parcelas, provisões, `Val_Cont` da NF-e e as três visões de DRE —
seria a raiz da árvore **se a falha acontecesse**. A Medição 1 mostrou que
hoje ela não acontece por caminho de usuário. O que sobra de real é o caso
`/parametros`, onde a tela mostra um número que o banco não tem.

**O que bloqueia:** confiar em qualquer margem calculada depois de uma
alteração de desconto, parâmetro ou forma de pagamento — em especial em
`/parametros`, onde a tela pode mostrar um número que o banco nunca gravou.

**Conserto:** insumo e recálculo na mesma transação; falha vira `ok: False`
com rollback do conjunto. Os dois `print` viram log de erro de verdade.
Prioridade: **Grupo 5** (higiene) para as seis rotas em geral — nenhuma exceção real e
alcançável por usuário foi confirmada nelas — mas o caso `/parametros` (erro invisível na tela)
justifica tratamento isolado antes das demais, dado o risco de decisão tomada sobre um número
fantasma.

### DECIDIDO 29/08/2026 — rebaixa, mas fecha as duas coincidências

O rebaixamento é aceito, e a prosa original deste achado estava errada em um
ponto medido: generalizava o "agravante da tela" para `/margens`, que não
tem o problema. Corrigido acima pela Medição 3.

Fica, porém, uma tensão que não deve ser varrida para debaixo do tapete. O
argumento que rebaixa o ACHADO-19 — "nenhum caminho de usuário produz a
exceção hoje" — é o **mesmo** argumento que o ACHADO-18 rejeitou seis
parágrafos acima, com o princípio de que proteção acidental não é proteção.
A diferença não é de princípio, é de **preço**:

- No ACHADO-18 a guarda custava uma linha. Barata: entra.
- No ACHADO-19 o conserto é reescrever a transação de seis rotas. Caro: sem
  falha alcançável, espera.

Mas há um terceiro caminho, que é o que fica decidido: **em vez de blindar
as seis rotas contra uma exceção, eliminar as duas exceções.** São três
consertos baratos, todos no Grupo 5, todos fechando causa em vez de sintoma:

1. **`json.loads(proj.parametros_json)` ganha try/except** (main.py:17258).
   Seis linhas acima, `config_financeira_json` já tem o dele
   (main.py:17250-17254): a mesma função trata os dois JSONs de forma
   diferente, e ninguém decidiu isso — é resíduo. Falhar com nome e cair no
   default, como o vizinho já faz.
2. **Guarda de auto-referência no complemento** — ver ACHADO-20.
3. **`/parametros` (10893) deixa de exibir o que não gravou.** Uma linha: a
   segunda chamada a `_negociacao_breakdown` passa para dentro do `try`, ou
   a resposta devolve `sombra: None` quando algum recálculo do laço falhou,
   igual ao que `/margens` já faz. É o único dos seis casos onde o sistema
   mostra ao usuário um número que nunca existiu no banco.

Feitos esses três, o fail-soft das seis rotas continua sendo desenho errado
— mas sem nada para engolir. A reescrita da transação fica registrada como
dívida do Grupo 5, para quando alguma rota precisar mudar por outro motivo.

---

## ACHADO-20 — complemento de PE auto-referente entra em recursão infinita

Achado pela Vera na Medição 1 do ACHADO-19, fora da lista de candidatos da
tarefa.

Um `Orcamento` com `complemento_pe = 1` que seja, ele próprio, o
`Contrato.orcamento_id` do projeto faz `_negociacao_breakdown` chamar
`_complemento_diferencas` que volta a pedir o breakdown do mesmo orçamento:
`RecursionError`. Não há guarda de ciclo.

**Alcançável hoje?** Não pelo endpoint real de criação de complemento, que
sempre cria um `Orcamento` novo e separado. Ou seja: mais uma proteção que
vem do desenho, não de uma verificação.

**Por que registrar mesmo assim:** os caminhos que produziriam o estado
auto-referente não são exóticos — correção manual de suporte no banco,
migração futura, importação. E o modo de falha é pior que uma exceção comum:
estouro de pilha atravessa `except Exception` em algumas versões, derruba a
requisição inteira e não deixa mensagem útil.

**Conserto:** guarda explícita de ciclo em `_complemento_diferencas` /
`_complemento_diferencas_fase` — se o orçamento do complemento for o
orçamento do contrato, recusa com erro nomeado em vez de recorrer.

**Consequências no número final:** nenhuma hoje.

**Grupo:** 5, junto com os outros dois consertos de causa do ACHADO-19.

---

## ACHADO-21 — revisão de PE depois do aditivo assinado cobra a mesma diferença duas vezes · RESOLVIDO 30/08/2026

**RESOLVIDO (docs/db/TAREFA_ACHADO21.md, passo 6 do ROTEIRO).** Três partes:

- **6-a** — extraída `valor_contratado_do_projeto(db, nome_safe)` (main.py):
  contrato + Val_Cont de cada Aditivo com `status == "assinado"` (as duas
  partes; rascunho/parcial não conta). Fonte única, testada isoladamente em
  `tests/test_valor_contratado_do_projeto.py`, sem mudar comportamento de
  quem ainda não a chamava.
- **6-b** — as duas metades obrigatórias: (1) `POST /pe/complemento/
  orcamento` não reaproveita mais um orçamento de complemento que já tem
  Aditivo assinado — a revisão seguinte cria um `Orcamento` NOVO; (2) a
  diferença do orçamento novo passa a ser calculada contra
  `_pe_fator_contexto`'s `ja_contratado_por_ambiente` (contrato + aditivos
  já assinados, lido do snapshot `Aditivo.dados_json`, não recomputado ao
  vivo — recomputar ao vivo criaria recursão infinita, um aditivo se
  subtraindo de si mesmo — achado ao medir o 6-c). Reproduzido com os
  mesmos números do achado original: revisão 2 agora cobra R$ 6.666,67 (o
  incremento real), não R$ 11.111,11 de novo — total pelos dois aditivos
  fecha em R$ 11.111,11, batendo com `valor_contratado_do_projeto`.
- **6-c** — a assinatura que completa o aditivo (2ª parte) agora exige
  `forma_pagamento` no corpo — recusa com mensagem clara se ausente, nenhum
  default inventado — e chama `_materializar_recebiveis_venda_seguro` para
  o orçamento do COMPLEMENTO (guarda de idempotência por `orcamento_id`;
  recebíveis do contrato nunca tocados). **Consequência medida, não
  surpresa:** com forma de pagamento financiada, o aditivo passa a ter
  Cust_Fin próprio — medido em `tests/test_aditivo_recebiveis_e_custo_
  financeiro.py`: diferença negociada R$ 4.444,44, total financiado
  R$ 4.888,88 → Cust_Fin R$ 444,44, reconhecido na mesma provisão/conta do
  ramo financeiro do contrato principal (`_ramo_financeiro_efetivo`).

`tests/test_aditivo_costuras.py::test_costura4_...` perdeu o `xfail` no
mesmo commit do conserto.

**Histórico da medição (antes do conserto):** Medido pela Vera na Costura 4 de `docs/db/TAREFA_ADITIVO.md`, reproduzido com
números em `tests/test_aditivo_costuras.py`. Os detalhes da medição estão na
seção do ACHADO-12; esta entrada existe porque o defeito **não é** o do
ACHADO-12 e não deve ser resolvido junto com ele.

- **ACHADO-12:** o aditivo não é faturado nem cobrado. Dinheiro que não entra.
- **ACHADO-21:** o aditivo é cobrado **duas vezes**. Dinheiro cobrado a mais
  do cliente.

São defeitos opostos, no mesmo lugar do código, e o conserto de um pode
mascarar o outro.

**O número:** contrato R$ 88.888,89. Revisão 1 → aditivo #1 de R$ 4.444,44,
assinado, 2.1.06 creditado. Revisão 2 → o endpoint **reaproveita o mesmo
`Orcamento`** (get-or-create por `projeto_id + complemento_pe=1 +
parcela_id=None`, main.py:7863-7867) e sobrescreve `valor_total` para
R$ 11.111,11 — a diferença cheia contra a linha de base do **contrato**,
não o incremento. Aditivo #2 assinado credita os R$ 11.111,11 inteiros.
Total cobrado R$ 15.555,55; correto R$ 11.111,11. Nada bloqueia a sequência.

### O agravante que os números não mostram

A cobrança em dobro é a metade visível. A outra metade é que **o registro do
que foi assinado é destruído**: aditivo #1 e aditivo #2 apontam para o mesmo
`Orcamento`, cujo `valor_total` agora vale R$ 11.111,11. Não existe mais, em
lugar nenhum da entidade, o valor pelo qual o aditivo #1 foi assinado. O
cliente assinou um documento cujo valor o sistema já não sabe reproduzir.

Sobra um rastro só no livro — e ele é o diagnóstico: **a soma dos créditos de
2.1.06 do projeto não bate com o `valor_total` do orçamento de complemento.**
R$ 15.555,55 lançados contra R$ 11.111,11 registrados. Serve como conferência
enquanto o conserto não vem.

### Por que aconteceu

Um `Orcamento` que já foi base de evento contábil continuou mutável. É a
mesma doença do ACHADO-16 (o sistema reescreve em silêncio um número já
escriturado) e do ACHADO-19 (insumo commitado sem o resultado que dele
depende). Aqui ela é mais cara porque atravessa a assinatura do cliente.

**Conserto — a linha que falta:** antes da aprovação do cliente, revisão de
PE é sobrescrita livre; **depois da assinatura do aditivo, o orçamento de
complemento é imutável** e a revisão seguinte gera um novo orçamento, cuja
diferença é calculada contra **contrato + aditivos já assinados**, nunca
contra o contrato sozinho.

**O que bloqueia:** cobrar aditivo de cliente real. Este é o único achado da
auditoria que tira dinheiro a mais de quem comprou.

---

## ACHADO-22 — docstring promete um mecanismo que VOCÊ MESMO mandou extinguir · GRUPO 5

**Esta entrada foi reescrita em 29/08.** A primeira versão afirmava que o
reconhecimento do CMV na emissão "nunca foi implementado" e levantava a
hipótese de que esse seria o primeiro buraco da divergência medida no
ACHADO-15/16. **A hipótese está errada.** O registro do erro fica aqui de
propósito.

### O que a medição da Vera achou, e que continua verdade

O docstring de `_fin_faturamento_segmentado_seguro` (main.py:1318-1321)
promete: *"No segmento 'mercadoria' também reconhece o CMV = CFO congelado
(1× por projeto, ref `cmv:<projeto>`)"*. Não existe nenhum lançamento com
esse `ref` em código nenhum.

### O que eu não tinha verificado

O mecanismo existiu e **foi extinto por decisão sua**, registrada no próprio
código (mod_contabil.py:1826-1832):

> *"2026-08-07 (achado do usuário): despesa na COMPETÊNCIA REAL da
> efetivação, não mais estimada de uma vez na NF-e (extinto o antigo
> 'matching pleno', `reconhecer_despesas_nfe`/`_MATCHING_NFE` — as despesas
> de projeto de móveis planejados ocorrem espalhadas ao longo do ciclo,
> muitas depois da própria NF-e, que só sai no fim, na entrega)."*

O reconhecimento hoje acontece em `reconhecer_despesa_efetivacao`
(mod_contabil.py:1862), chamado por `efetivar_provisao`: débito na despesa
formal da rubrica × crédito no ativo diferido espelho. Para o CMV de fábrica,
`5.1.01 × 1.1.06.06` — o evento existe e está ligado.

**Portanto:** o `cmv_csp` valer 0 na emissão da NF-e **é o comportamento
correto e desejado**. Na emissão a provisão ainda não foi efetivada, então
não há custo a reconhecer. A divergência naquele marco é de desenho, não
defeito.

### O que sobra de achado

Um docstring que descreve um mecanismo extinto há três semanas, no ponto do
código onde alguém vai procurar como o CMV é reconhecido. É a quinta
ocorrência da regra 3 do plano — nome/documentação que não descreve
comportamento — e a mais perigosa delas, porque induziu exatamente o erro que
esta entrada registra. **Conserto: apagar a promessa do docstring e apontar
para `reconhecer_despesa_efetivacao`.** Grupo 5.

### O que isto reforça no ACHADO-16

Se a **única** porta pela qual o custo entra no resultado é a efetivação da
provisão, então uma provisão que nunca é efetivada é custo que nunca existe
na DRE — não por falha de rota, mas por ausência do evento que a dispara.
A decisão do ACHADO-16 (o projeto não fecha com provisão em aberto) deixa de
ser prudência e passa a ser a única coisa que garante que o custo chegue ao
resultado.

Com uma precisão a mais para quem implementar: o veredito *"encerrada com
valor menor"* tem **duas** pernas — efetivar a provisão pelo valor real (é
isso que reconhece o custo, via `reconhecer_despesa_efetivacao`) e só então
reverter o resíduo. Reverter sem efetivar reproduz o ACHADO-16 com outro
nome.

---

## ACHADO-23 — o congelamento da segmentação é fail-soft, e a assinatura completa mesmo assim · RESOLVIDO 31/08/2026

**RESOLVIDO (docs/db/TAREFA_ACHADO23.md, passo 11 do ROTEIRO — último da
Fase 1).** A assinatura continua completando normalmente; a AF1 (etapa "8")
ganhou o gate: sem `parametros_json["segmentacao_congelada"]` (o marcador
que `_congelar_segmentacao_no_projeto` grava — não basta `pct_mercadoria`/
`pct_servico` existirem, que também é o override editável de antes da
assinatura), a AF1 tenta congelar ali mesmo (reparo); só recusa, nomeando o
projeto, se o reparo também falhar. O `print` virou
`logging.getLogger(__name__).error(...)`, nos dois pontos (assinatura e
reparo da AF1).

`tests/test_aceite_achado23.py` (4 aceites): as falhas foram FORÇADAS POR
INJEÇÃO (monkeypatch de `_congelar_segmentacao_no_projeto`, não uma
condição natural) — e os dois testes que dependem do gate (recusa por
injeção; reparo na AF1) foram confirmados falhando **contra o código
pré-conserto**, pelo motivo certo (recusa esperada e não aconteceu — não um
erro de setup de data/contrato/senha). O controle positivo (segmentação já
congelada → AF1 aprova sem tentar recongelar) e os dois testes de assinatura
(completa com e sem falha de congelamento) passam nos dois códigos, como
esperado de um controle.

Este foi o achado que quase escapou do fechamento da Fase 1: nunca teve
`xfail`, então o contador de xfails (o `grep` do ROTEIRO) não o via — só
apareceu porque `ACEITE.md` não tinha linha nenhuma pra ele. A partir daqui
o aceite de cada fase exige as duas travas: suíte sem xfail da fase **e**
`ACEITE.md` sem linha da fase em "SEM PROVA".

**Histórico da medição (antes do conserto):**

Medido pela Vera no passo 7 (`docs/db/TAREFA_ACHADO12.md`, ponto 3), que
pedia só a medição da segmentação. Achado novo — entra na fila pela regra do
roteiro, não é consertado dentro do passo.

### O mecanismo existe e funciona

`_congelar_segmentacao_no_projeto` (main.py) grava a segmentação efetiva no
`parametros_json` do projeto na assinatura, e o override do projeto sempre
vence o default da loja. **Medido:** congelado em 100% mercadoria, loja
alterada depois para 30/70, o projeto continuou faturando os mesmos
R$ 88.888,89 em mercadoria. Em operação normal não há problema.

### Mas o chamador engole as duas falhas

```python
try:
    if _congelar_segmentacao_no_projeto(db, loja_id, nome_safe) is not None:
        db.commit()
except Exception as _eseg:
    db.rollback()
    print("[SEGMENTACAO] congelar na assinatura falhou:", _eseg)
```

Dois caminhos silenciosos, e nos dois **a assinatura completa**:

1. retorno `None` (loja ou projeto ausente) — não commita, não reclama;
2. exceção — rollback, um `print`, e segue.

O projeto passa a viver do default da loja **ao vivo, para sempre**.

### O número

Medido sem o congelamento: mercadoria a 65% = R$ 57.777,78; loja alterada
para 20% depois de "assinado"; virou R$ 17.777,78. **R$ 40.000,00 de
diferença na face fiscal do mesmo contrato, sem ninguém tocar no projeto.**

### O que isto é

A mesma doença do ACHADO-19: um `print` onde deveria haver erro, e a
operação seguindo como se nada tivesse acontecido. Só que aqui o valor
afetado é o que vai na nota fiscal do cliente.

Projeto legado não é preocupação — a base está limpa, não existe projeto
anterior ao mecanismo. **O risco é inteiramente o caminho de falha.**

### DECIDIDO 30/08/2026 — a trava vai para a AF1

**A assinatura completa normalmente.** A conferência da segmentação passa a
ser condição da **Aprovação Financeira (AF1)**: sem segmentação congelada, a
AF1 não aprova.

Três opções foram oferecidas (recusar a assinatura / bloquear a NF-e / deixar
como está) e o usuário propôs uma quarta, melhor que as três:

- **Não trava a venda** com o cliente na frente, no ato da assinatura.
- **Não espera a NF-e**, que é perto da entrega — onde o atraso custa mais.
- Cai numa etapa que **já existe e já é obrigatória**
  (`mod_ciclo.exige_aprovacao_financeira`), criada na mesma assinatura que
  congela.
- Quem senta nela é o perfil que **consegue resolver** — e a segmentação
  Mercadoria × Serviço é um dos números que ele revisa de qualquer jeito. Ela
  estava sendo congelada num lugar onde ninguém olhava.
- **O caminho de reparo não precisa ser inventado:** é a própria AF1.

Fica no conserto, além disso:
1. A pendência diz **o que** falhou, com o projeto identificado — quem lê é
   quem vai resolver.
2. A AF1 consegue **disparar o congelamento** ali mesmo, não só recusar.
3. O `print` vira log de erro de verdade. Hoje ninguém fica sabendo, nem
   depois.

**Consequências no número final:** nenhuma em operação normal; até
R$ 40.000 num contrato de R$ 88.888,89 se a falha ocorrer.

---

## ACHADO-24 — aditivo assinado com plano de pagamento vazio não gera cobrança nenhuma · RESOLVIDO 31/08/2026

Encontrado em 31/08 ao ler o relatório da remedição do ciclo. A Vera
identificou corretamente que o resíduo de R$ 5.000 em 1.1.02 era artefato do
fixture; o mecanismo que o produziu, porém, é um achado.

**O que acontece:** a assinatura do aditivo (passo 6-c) passou a exigir
`forma_pagamento` e a chamar `_materializar_recebiveis_venda_seguro`. Mas
nada valida que a forma de pagamento **produz** recebíveis. Um payload
`{"tipo": "avista", "total_cliente": 0}` sem `parcelas` nem `entrada_valor`
é aceito; `mod_recebiveis.materializar` nunca lê `total_cliente` e devolve
zero linhas. O aditivo fica assinado, com receita constituída em 2.1.06, e
**sem nenhum `Recebivel`** — não entra em cobrança em lugar nenhum.

**Alguém já previu o caso e escolheu fail-soft:** main.py:842-846 tem um
`logging.warning` — *"orçamento tem valor_total>0 mas nenhum plano de
pagamento ... 0 recebíveis materializados. Verifique manualmente"*. Aviso em
log não é controle: ninguém lê log de produção procurando venda não cobrada.

**Por que importa:** é o ACHADO-12 por outra porta. Aquele era "o wiring de
recebíveis nunca é chamado para o aditivo"; este é "o wiring é chamado e não
produz nada". O efeito no caixa é idêntico — aditivo vendido, executado, não
cobrado.

**Mesma forma do ACHADO-18:** coisa com valor aceita sem cobrança atrelada,
em silêncio. E a guarda é igualmente barata.

**Medição F2-1 (docs/db/TAREFA_ACHADO24.md), 31/08/2026 — os dois caminhos,
não só o aditivo:** `_materializar_recebiveis_venda_seguro` é compartilhada
com a geração de contrato (`POST /projetos/<nome>/contrato`, main.py). Medido
por HTTP com `tests/test_aceite_achado24.py` (2 `xfail(strict=True)` +
controle positivo, antes do conserto):

- **Aditivo:** a tela real (`static/index.html`, `peAditivoAssinar`) **não
  envia `forma_pagamento` nenhum** — nem vazio, nem cheio. É pior do que o
  achado original supunha: hoje, em produção, TODA tentativa de completar a
  2ª assinatura do aditivo é recusada com "Informe a forma de pagamento do
  aditivo antes de concluir a assinatura." (o guard de presença do passo
  6-c). Ninguém consegue fechar um aditivo pela tela desde que aquele passo
  entrou — ver ACHADO-25.
- **Contrato:** medido e confirmado — `POST /contrato` aceitava
  `pagamento_json` vazio **sem nenhuma validação**, nem de presença. Achado
  maior do que registrado: um contrato inteiro podia fechar sem cobrança,
  não só um aditivo.

**Conserto aplicado:** valor > 0 exige que o plano produza ao menos um
`Recebivel`, ou a operação é recusada com mensagem — nos dois chamadores
(main.py, assinatura do aditivo e geração de contrato). O `logging.warning`
antigo vira recusa de verdade. `xfail(strict=True)` dos dois aceites
removido no commit do conserto; controle positivo (plano normal,
`test_aditivo_com_plano_real_...`/`test_contrato_com_plano_real_...`)
confirma que a guarda não barra o caso legítimo.

**Fixture do ciclo corrigido:** `test_dre_ciclo_completo_e2e.py` (marco 5c)
passou a enviar um plano real (parcela cobrindo o valor cheio do
complemento) — o resíduo de R$ 5.000 em `1.1.02` desapareceu (vai a `0.00`
no marco 7), confirmando que era artefato do fixture, não um remanescente
da aplicação. Ver docs/db/RELATORIO_DRE_CICLO_POS_FASE1.md.

**Consequências no número final:** nenhuma medida (não há cliente real). Em
uso real, antes do conserto: 100% do valor do aditivo ou do contrato sem
cobrança, quando o plano de pagamento chegasse vazio.

**Grupo:** 1 por natureza — é caixa que não entra. Resolvido como primeiro
item da Fase 2 (F2-1), antes do passo 12.

---

## ACHADO-25 — a tela de assinatura do aditivo nunca envia forma de pagamento — ninguém completa um aditivo hoje · RESOLVIDO 31/08/2026 (F2-4)

Encontrado ao medir o ACHADO-24 (F2-1, docs/db/TAREFA_ACHADO24.md): a
pergunta era "a tela exige parcelas, ou aceita um plano vazio como o
fixture?" — nenhuma das duas. `peAditivoAssinar(parte)` em
`static/index.html` (linha ~21849, chamada pelo botão "Assinar (parte)")
manda só `{parte, nome, cpf}`. Não existe campo de forma de pagamento em
lugar nenhum perto da UI do Termo Aditivo — só `#pe-ad-nome` e `#pe-ad-cpf`.

**O que impede:** **campo obrigatório de formulário ausente**, não
validação. O backend (passo 6-c, ACHADO-21, 30/08/2026) passou a EXIGIR
`forma_pagamento` na assinatura que completa o aditivo (`completa_agora`) —
mas o frontend nunca foi atualizado para coletá-la. Resultado: hoje, em
produção, clicar em "Assinar" na parte que completa o par (loja+cliente)
**sempre** recebe `400` — "Informe a forma de pagamento do aditivo antes de
concluir a assinatura." — com plano vazio, cheio, ou qualquer coisa, porque
o campo simplesmente não existe para preencher.

**Por que é mais grave que o ACHADO-24:** aquele era "a tela pode aceitar
plano vazio". Este é "a tela não tem como completar o aditivo de jeito
nenhum" — uma regressão funcional bloqueando um fluxo inteiro (2ª
assinatura do Termo Aditivo) desde que o passo 6-c entrou, sem que nenhum
teste de UI tivesse pego (os testes E2E chamam a rota HTTP diretamente,
com `forma_pagamento` no corpo — nunca passaram pela tela real).

**Não bloqueou o F2-1** (a guarda do ACHADO-24 se prova por HTTP,
independente do formulário) — registrado e enfileirado, não consertado
neste passo, por regra do roteiro.

**Conserto provável:** um campo (ou modal) de forma de pagamento na UI do
Termo Aditivo, no mesmo padrão do modal de Aprovar Orçamento
(`_capturarPagamento`/`window._planoPagamento`) — coletado antes de permitir
o clique em "Assinar" na parte que completa o par.

**Consequências no número final:** nenhuma medida (é uso de tela, não
número contábil) — mas em produção, hoje, é bloqueio total: nenhum aditivo
completa a 2ª assinatura pela tela.

**Grupo:** 1 — bloqueia um fluxo de negócio inteiro, não é só higiene.

**Conserto aplicado (31/08/2026):** modal novo,
`_abrirModalPagamentoAditivo(valorComplemento)` (`static/index.html`) —
mesma modalidade à vista/cartão/Aymore do pagamento do contrato, mas NÃO
reaproveita `_capturarPagamento`/`window._planoPagamento` diretamente (o
modal do contrato assume um fluxo de página inteira, com o resto da UI de
negociação ao redor; o do aditivo precisa caber dentro do fluxo de
assinatura de duas partes, num popup próprio) — reaproveita, sim, a lista
de formas de entrada (`_FORMAS_ENTRADA`) e a mesma lógica de saldo/parcela
única pro caso à vista. `peAditivoAssinar(parte)` agora sabe, no momento do
clique, se ESTA assinatura completa o par — dois globais
(`_peAditivoPartesAssinadas`, `_peAditivoValorComplemento`) setados em
`peComplementoRender()`, onde a resposta de `/aditivo` já foi lida — e só
abre o modal quando `completaAgora` for verdadeiro; a primeira assinatura
(a que não completa) continua mandando só `{parte, nome, cpf}`, como antes.

**Prova:** `tests/test_e2e_browser_conciliacao_final.py` — o mesmo E2E de
navegador do ACHADO-24/ACHADO-26, estendido: gera o Termo Aditivo, assina a
loja, assina o cliente (a assinatura que completa o par), preenche o modal
de pagamento novo e confirma — clicado na tela, não chamado por HTTP. Roda
em banco próprio (`orizon_e2e`) e voltou pra `pytest -q` padrão (docs/db/ESTEIRA.md).

---

## ACHADO-26 — a Conciliação Final não manda veredito nenhum: ou o projeto trava, ou o veredito é contornado em silêncio · RESOLVIDO 31/08/2026 (F2-3)

Encontrado no levantamento F2-2 (docs/db/TAREFA_CONTRATOS_UI.md), que a
tarefa já apontava como suspeito grave: se a tela não manda vereditos,
nenhum projeto se conclui pela interface. **Confirmado — e pior do que
"não conclui": há um segundo caminho que conclui, mas sem o veredito
nunca existir.**

**O que a tela manda:** `conciliarFinal()` (static/index.html:20045) chama
`POST /ciclo/21/conciliar` com `body: '{}'` — sempre, sem exceção. Nenhuma
string do vocabulário de veredito (`encerrada_valor_menor`,
`nao_se_aplica`, `ainda_vai_chegar`) aparece em `static/index.html` — zero
ocorrências, confirmado por busca. Não existe formulário, campo ou modal
para dar um veredito nomeado.

**Caminho 1 — bloqueio direto:** se alguma rubrica de provisão (grupo
2.1.04.x, exceto Impostos/Custo Financeiro) está em aberto quando o
usuário clica "Concluir Conciliação Final", `mod_contabil.conciliar_final`
recusa com `ValueError` — HTTP 400, mostrado via `showToast`:
*"Conciliação Final recusada: falta veredito para `<código>` — toda
provisão em aberto precisa de um veredito nomeado antes do projeto
fechar."* Não há nenhuma ação na tela que o usuário possa tomar A PARTIR
desta mensagem — o campo que falta não existe em lugar nenhum da UI.

**Caminho 2 — contorno silencioso (o achado mais sério):** a mesma tela da
Conciliação Final mostra uma tabela editável de provisões
(`_reconProvTabelaHtml(..., {editavel:true, prefixo:'efc-'})`) com botões
"Efetivar" e **"Resolver"**, que chamam `/api/financeiro/efetivar-provisao`
e `/api/financeiro/resolver-saldo-provisao` diretamente —
`mod_contabil.resolver_saldo_provisao` **zera o saldo da provisão sem
exigir veredito nenhum e sem gravar nada em `VeredictoProvisao`**. Se o
usuário clicar "Resolver" em cada rubrica aberta ANTES de clicar
"Concluir", `abertas` fica vazia, `conciliar_final({})` passa limpo, e o
projeto fecha — **mas o mecanismo inteiro do ACHADO-16 (veredito nomeado,
motivo, tabela de auditoria, `relatorio_projetos_encerrados_por_reversao`)
nunca é acionado.** `resolver_saldo_provisao` é uma função legítima
(usada internamente por `resolver_veredito_provisao`), mas seu endpoint
próprio permite pular o veredito por inteiro — é o único caminho que a
tela oferece pra zerar uma rubrica, então é o caminho que todo usuário
real necessariamente usa.

**Por que é mais grave que o ACHADO-25:** aquele bloqueia um fluxo
(aditivo). Este tem DOIS problemas simultâneos no fluxo mais importante do
sistema (o fechamento que a auditoria inteira girou em torno de medir):
ou o projeto não fecha (Caminho 1), ou fecha exatamente como fechava
ANTES do ACHADO-16 ser corrigido no backend — sem nenhum registro de por
quê uma provisão foi zerada sem efetivação. O conserto do ACHADO-16 no
código nunca chega a proteger um usuário real, porque a tela nunca oferece
o mecanismo que o protegeria.

**A quarta ocorrência do mesmo erro.** ACHADO-19 (seis rotas, uma guardada),
ACHADO-03 (dois roteadores divergentes), ACHADO-24 (função compartilhada,
dois chamadores), e agora este. A disciplina que faltava não é medir o livro
nem checar quem chama: é **enumerar os irmãos** — antes de guardar uma
operação, listar todo endpoint capaz de produzir a mesma mudança de estado.

**Decisão de Marcelo, 31/08: a fila é a porta da frente, não a tela de
Conciliação Final.** Quem dá os vereditos é a assistente administrativa da
loja — quem tem o pedido e a nota da fábrica na mão e sabe responder "ainda
há despesa a realizar?". A Conciliação Final **não ganha campos de
veredito**: continua conferindo que nada ficou em aberto e, quando ficar,
aponta para a fila. Ordem obrigatória: a fila entra **antes** do desvio
fechar — fechá-lo primeiro deixaria o sistema sem porta nenhuma pra
concluir projeto.

**Conserto aplicado (F2-3, docs/db/TAREFA_FILA_PROVISOES.md), 31/08/2026:**

1. **A fila** — `GET /api/financeiro/fila-provisoes` (`mod_contabil.
   provisoes_em_aberto`, todo projeto, toda rubrica em aberto que exige
   veredito) e `POST /api/financeiro/fila-provisoes/veredito` (um veredito
   por vez, por projeto+rubrica, via `resolver_veredito_provisao` — o
   mesmo mecanismo do passo 8, `ref="fila:<projeto>:<conta>"`).
2. **O desvio fechado** — `/api/financeiro/resolver-saldo-provisao` passa a
   recusar (409) qualquer `conta` fora de `_PROV_FORA_DO_VEREDITO`
   (Impostos/Custo Financeiro, ACHADO-01 — os únicos usos legítimos
   levantados antes de restringir; nenhum outro endpoint zera saldo de
   provisão além deste e do já conhecido ACHADO-07, Grupo 5, não tocado).
   Achado colateral do levantamento: Custo Financeiro (2.1.04.19) já
   falhava sozinho nesta rota genérica ANTES do F2-3 — não tem entrada em
   `_PROV_DESTINO_VARIANCIA` nem em `_PROV_TEMPO_REAL_ROTA_PROPRIA`, de
   propósito (rota própria é `conferir_retencao_financeira`) — listado em
   `_PROV_FORA_DO_VEREDITO` só por simetria com `conciliar_final`, não
   porque a rota funcionasse pra ele.
3. **A mensagem** — o texto de `conciliar_final` ao recusar por falta de
   veredito passou a dizer onde resolver ("Resolva na Fila de Provisões").
   A Conciliação Final continua sem campo de veredito nenhum.

Provado por `tests/test_aceite_fila_provisoes.py` (7 aceites): o desvio
recusado para rubrica que exige veredito (e o projeto continua sem
concluir); os quatro vereditos pela fila, isolados (`efetivada` só para
FALTA, `encerrada_valor_menor` reconhece o custo real em 5.1.01 antes de
reverter o resíduo, `nao_se_aplica` exige motivo, `ainda_vai_chegar` não
destrava o fechamento); controle positivo — Impostos continua funcionando
pelo desvio; e o fluxo completo — veredito pela fila, fila deixa de listar
a rubrica, Conciliação Final conclui com `{}` de sempre, custo aparece em
5.1.01.

**Consequências no número final:** as mesmas do ACHADO-16 — margem
fictícia, custo que some — mas só até este conserto: agora todo projeto
concluído pela tela passa pelo veredito de verdade (fila) ou continua
travado até passar.

**Grupo:** 1 — é o fluxo de fechamento do sistema inteiro.

---

## ACHADO-27 — plano de pagamento longo colapsa o card de ambientes na tela de Negociação · RESOLVIDO 31/08/2026

Achado do Marcelo, clicando em Homologação, 31/08/2026 — **não é regressão
desta rodada** (a esteira e o F2-4 não tocaram `#page-02`/CSS de layout;
já existia antes, só nunca tinha sido clicado com um plano longo o
suficiente para expor).

**O que acontecia:** na tela de Negociação, com um plano de pagamento
longo (medido com Cartão de Crédito, 15x), o card que contém a tabela de
ambientes E a linha de ações (Salvar/Aprovar/Imprimir) colapsava para
~1-2px de altura e sumia da tela. Os três botões continuavam **existindo**
no DOM — `getComputedStyle` reportava `display:flex; visibility:visible`,
e um `is_visible()` ingênuo (Playwright) reportava `true` — mas nenhum
clique real os alcançava, recortados pelo pai.

**Causa (medida, não suposta):** `#page-02.active` é `display:flex;
flex-direction:column`, com altura ditada pelo espaço disponível na
viewport (819px medidos no navegador real do Marcelo; ~604px no
headless deste teste — o número muda com a janela, o mecanismo não).
Pela regra do flexbox, o **mínimo automático** de um item flex no eixo
principal (o valor que `min-height:auto` resolve) usa o tamanho do
CONTEÚDO do item — **exceto** quando o item tem `overflow` diferente de
`visible`, caso em que o mínimo automático vira **0**, e só então o item
pode encolher além do próprio conteúdo. O card de ambientes
(`#neg-tbl-ambientes-card`, antes só `.card` sem id) tem
`overflow:hidden` inline — ali só para cortar os cantos arredondados da
tabela no `border-radius` do card, sem relação nenhuma com altura.

**Medido antes de mexer (a instrução era explícita: não tapar o buraco
sem entender o resto do prédio) — os outros filhos diretos de `#page-02`
não compartilham a mesma exposição:** `.neg-top` (grid do cabeçalho) e os
cinco `.mod-panel` `#plano-*` (um por modalidade, só um visível por vez)
não têm `overflow` declarado — o padrão é `visible`, então o mínimo
automático deles já é o tamanho do conteúdo, e eles **já recusavam**
encolher abaixo dele antes de qualquer conserto. Medido:
`#plano-cartao` sozinho, com 15 parcelas, mede ~847px e não se move — é
exatamente ele quem sobra além dos ~604-819px disponíveis, e o card de
ambientes (o único com a saída de emergência do `overflow:hidden`) que
absorve 100% do encolhimento. `#ciclo-panel` (o outro filho notável de
`#page-02`, ver N4/2026-08-26 na CSS) é `position:absolute;inset:0` — fora
do fluxo, não entra nesta conta.

**Conserto:** `flex-shrink:0` só em `#neg-tbl-ambientes-card`
(`static/index.html`) — tira o item do cálculo de encolhimento por
completo, sem tocar no `overflow:hidden` que ele usa pra outra coisa
(cortar cantos). `#page-02` volta a crescer além da viewport quando o
plano é longo, e `.content` (ancestral, já com `overflow-y:auto` desde o
N4) rola normalmente pra mostrar o resto — nenhuma mudança na altura do
próprio `#page-02` nem no `#ciclo-panel` absolutamente posicionado dentro
dele. Tentativa descartada: `min-height:auto` explícito no card — não
muda nada, porque `auto` já É o valor padrão; o mecanismo do flexbox que
zera o mínimo automático olha o `overflow`, não se o autor escreveu
`min-height` ou deixou implícito.

**Por que tem que ser um teste de NAVEGADOR:** nenhuma chamada de API vê
isto — é um bug puramente de CSS/layout, que só existe depois que o motor
do navegador renderiza a árvore inteira. Exatamente a classe de achado
que o F2-2 já mostrou (ACHADO-25/26): milhares de testes de API verdes, e
a tela travada.

**Prova:** `tests/test_e2e_browser_negociacao_layout.py` — projeto real
criado pela tela, ambiente via XML, modalidade Cartão de Crédito + 15
parcelas selecionados na tela; mede `getBoundingClientRect().height` do
card (> 100px, não recortado) e clica de verdade nos três botões
(Salvar/Imprimir/Aprovar) — não só `is_visible()`, que o achado provou
não bastar. Confirmado que o teste falha (`getBoundingClientRect` de um
elemento sem a id nova, ou altura ~2px com o seletor antigo) contra o
código de antes do conserto, e passa depois.

**Consequências no número final:** nenhuma — é layout puro, nenhum valor
contábil passa por aqui. Mas em produção, com plano de pagamento longo,
ninguém consegue aprovar orçamento nem assinar contrato pela tela.

**Grupo:** 1 — bloqueia um fluxo de negócio inteiro (aprovar/assinar) sob
uma condição específica (plano longo), não é só higiene.

---

## ACHADO-28 — CPF de assinatura não é validado, e é ele que identifica quem assinou · RESOLVIDO 31/08/2026

Encontrado pelo Marcelo em 31/08, clicando em Homologação: a assinatura do
gerente aceitou um número aleatório como CPF.

**O validador existe.** `validacao_doc.valida_cpf` confere os dígitos
verificadores, e `validacao_doc.erro_doc` é chamado nos caminhos de cadastro
— cliente, parceiro, loja (main.py:9965, 9974, 10716, 10940, 10984).

**Os caminhos de assinatura não o chamam.** Nenhum dos três:

- `_registrar_assinatura_contrato` (main.py:891)
- `_registrar_assinatura_aprovacao_pe` (main.py:1125)
- `_registrar_assinatura_solicitacao_medicao` (main.py:1198)

**Por que aqui é pior que no cadastro.** No cadastro, CPF errado é dado ruim
— corrige-se depois. Na assinatura, o CPF entra em
`calcular_hash_assinatura(nome, cpf, contrato_id, timestamp)`
(mod_contrato.py:68): ele é **parte da evidência de quem assinou**. Uma
assinatura com CPF inválido é evidência de nada, e o hash lhe dá aparência
de prova.

**Sexta ocorrência do mesmo padrão.** ACHADO-19, 03, 24, 26, e o CMV do 22:
o mecanismo existe, e o caminho real não passa por ele. Aqui a distância é
de uma linha.

**Conserto aplicado:** os três caminhos de assinatura chamam
`validacao_doc.erro_doc` antes de gravar, recusando com `ValueError` — por
estar DENTRO das três funções compartilhadas (não em cada chamador), cobre
os dois gatilhos de cada uma de graça: o endpoint síncrono de assinatura
interna (recusa vira HTTP 400) e o webhook/reconciliação ClickSign, onde o
CPF vem de fora — ali a recusa não pode derrubar a reconciliação inteira
(um CPF ruim de UM signatário não pode travar os outros), então
`_reconciliar_contrato_clicksign`/`_reconciliar_aprovacao_pe_clicksign`/
`_reconciliar_solicitacao_medicao_clicksign` capturam o `ValueError`, logam
e seguem para o próximo signatário.

**A decidir junto:** CPF do signatário deve **bater com o cadastro** da
parte que assina (o cliente do projeto, o gerente da loja), ou basta ser um
CPF válido? Validar o dígito impede o número inventado; conferir contra o
cadastro impede o CPF de outra pessoa. São guardas diferentes e a segunda é
decisão do dono do negócio — adiada pra próxima, ver LP-02 em
`docs/db/LISTA_PARALELA.md`.

**Prova:** `tests/test_aceite_achado28.py` — seis aceites (dois por
caminho): CPF estruturalmente inválido recusado com 400 e mensagem nomeando
a parte, sem avançar o status do documento; CPF válido passa — controle
positivo, sem o qual uma guarda que recusasse sempre passaria no primeiro
aceite de cada par. `pytest -q` completo confirmado verde depois do
conserto (2482 passed, 4 xfailed) — a guarda nova expôs CPFs de teste
estruturalmente inválidos (dígitos repetidos, sequenciais) usados como
placeholder em seis arquivos de teste pré-existentes, todos trocados pelo
CPF de teste válido já padrão na suíte (111.444.777-35).

**Consequências no número final:** nenhuma. É evidência, não contabilidade —
e é por isso que precisa ser boa.

---

## ACHADO-29 — o plano de pagamento do aditivo mostra o contrato inteiro financiado

Encontrado pelo Marcelo em 31/08, na tela de Negociar Complemento (beta3,
Homologação).

**O número medido:** entrada R$ 20.000 + 10 × R$ 17.429,56 =
**R$ 194.295,56**. O contrato à vista é R$ 180.944,52; a diferença de
R$ 13.351,04 é o custo financeiro da forma de pagamento. **É o contrato
inteiro, financiado** — não o aditivo. O Δ de venda do PE, que é o valor do
aditivo, é R$ 12.683,94.

**Onde não está a causa:** o orçamento do complemento nasce com
`forma_pagamento = None` (main.py:8055). O número não vem do banco.
Hipótese a medir: **vazamento de estado do frontend** — o plano do orçamento
anterior não é zerado ao abrir o complemento.

### O desenho, especificado pelo usuário em 31/08

**A base é o valor à vista.** Forma de pagamento não foi discutida na
renegociação, então a referência é o à vista, não o financiado.

**Carrega o desconto original do contrato** — a renegociação parte das
mesmas condições da venda.

**Apresenta a diferença definida na aprovação financeira**, não a diferença
bruta: nem todo ambiente compõe o aditivo, porque o gerente financeiro pode
**absorver** a diferença de alguns.

**Valores editáveis.** O **limite de desconto continua valendo** no aditivo
— o usuário considerou e reverteu, em 31/08, a ideia de removê-lo.

### Os dois planos — a distinção que o usuário pediu atenção

**Não confundir.** A decisão *cobrar / manter / absorver / estornar* é
tomada olhando os **valores de fábrica** (plano de custo). O **valor do
aditivo** vive no **plano de venda** — com o markup e os descontos da venda
original. A decisão de custo determina **se** cobra; o quanto sai do plano
de venda. **A armadilha a evitar:** pegar a diferença de custo e aplicar
markup nela. Não é isso — é a diferença entre **dois valores de venda** já
calculados pelo motor com os parâmetros da venda original. Na tela medida:
Cozinha, à vista contrato R$ 103.462,72 × à vista PE R$ 124.154,20,
Δ +R$ 20.691,48 = exatos +20%.

**Onde nasce, confirmado:** o botão "Gerar Termo Aditivo" fica na **etapa 7,
Projeto Executivo**, na seção de aprovação do PE (static/index.html:21731) —
onde o usuário espera que esteja. Quando há valor a cobrar, há termo de
aditivação.

**Grupo:** 1 — é o valor que o cliente paga.

---

## ACHADO-30 — documentos de fase não têm como ser trocados, nem ficam imutáveis depois · RESOLVIDO 03/09/2026 (F2-15, item 1 do bloco fiscal)

Encontrado pelo Marcelo em 31/08. Vale para os arquivos de **medição** e
para o **XML da NF-e da fábrica**, e provavelmente para os demais
`CicloDocumento`.

**Duas faltas, e a primeira é pré-requisito da segunda:**

1. **Não existe o acionamento.** Não há lixeira para apagar nem botão para
   sobrescrever o arquivo anterior. A regra de imutabilidade não significa
   nada enquanto não for possível trocar antes.
2. **Não existe a trava.** Depois de a fase fechar, o arquivo deveria ficar
   inalterável — e não fica.

**A regra:** **mutável enquanto a fase está aberta, imutável depois.**
Múltiplos arquivos permitidos enquanto aberta. É a regra 3 do plano — *o que
já virou fato se lê de onde foi congelado* — estendida de lançamento
contábil para documento.

**Grupo:** 2 — não muda número, mas o documento é a prova do que foi feito.

### DECIDIDO 03/09 — remover é MARCAR, não apagar

O item pedia "apagar e substituir". Medido antes de escrever: **não existe rota
de remoção nenhuma hoje** (zero), e o `CicloDocumento` promete no próprio
docstring *"Append-only: nunca sobrescreve"*. Ou seja, não era consertar uma
porta — era abrir a que nunca existiu, num modelo que promete o contrário. Por
isso a pergunta foi feita antes (regra das duas portas), e a decisão do Marcelo
foi a marcação: `removido_em`/`removido_por_id`, **registro e arquivo em disco
preservados**.

O que isso compra: a promessa append-only continua de pé; o rastro de que houve
tentativa não some — mesma razão que fez o cancelamento silencioso virar veredito
nomeado no ACHADO-16; e o arquivo não é destruído numa pasta (`PROJETOS/`) que
**ainda não tem cópia fora do host** — um engano no apagar não teria de onde
voltar hoje. O que isso não cobre, e fica dito: um arquivo subido por engano
continua no disco; se algum dia for preciso destruí-lo, é decisão separada.

### Conserto (03/09)

Migration `b0ecb9ce82d2` (id gerado, nunca digitado — a lição do ACHADO-47),
duas colunas nullable: todo documento existente nasce vivo.

**A parte que importa mais que a tela: os portões.** `main._docs_vivos` virou a
porta ÚNICA de leitura e **oito** leitores passaram por ela — três deles não são
listagem, são portão: o `tem_xml` que libera concluir as etapas operacionais
(12/13/14), o `tipos_presentes` das subfases do PE, e a escolha do
`fabrica_doc_id` na emissão da NF-e. Um portão que contasse documento removido
tornaria a remoção cosmética, e falharia em silêncio — que é o pior modo. Uma
trava anti-órfão (`tests/test_achado30_remocao_documento.py`) varre o `main.py` e
recusa qualquer leitura crua de `CicloDocumento` que não trate `removido_em`.

**A rota** é POST (o servidor não tem `do_DELETE`), recusa 409 em fase concluída
(a segunda metade da regra), e a **autoridade espelha a do upload daquela etapa**
— capacidade fiscal da sessão na 15, `executar_pe` nas subfases do PE, com o mesmo
atalho sessão-primeiro do upload — em vez de inventar uma terceira regra de quem
manda no documento.

**Na tela**, "Remover" aparece nas subfases do PE, na lista de XML da etapa 12 e
no XML da fábrica da 15 — mas **não** num XML que já virou emissão: remover o
documento de origem de uma NF-e autorizada seria buraco, não conserto.
`removido_em` fica em `utcnow()` por ser timestamp de auditoria e não competência
(a classificação do ACHADO-48), igual ao `enviado_em` irmão.

**Prova:** 6 aceites — remoção some da tela com o registro intacto no banco (quem
e quando); o portão da etapa 12 deixa de enxergar; fase concluída recusa (409);
autoridade espelhada; segunda remoção devolve 404 sem reescrever o rastro; e a
trava anti-órfão. O aceite do portão carrega **o próprio controle negativo
dentro dele**: afirma que a consulta CRUA ainda vê o documento removido e que a
porta única não vê — se alguém trocar `_docs_vivos` por `db.query` ali, o teste
cai. Suíte completa: **2576 passed, 4 xfailed, 0 failed**.

**Achado de processo, no meio do caminho:** a primeira versão do aceite da fase
concluída concluía a etapa 11a e ia embora assim — os dois aceites seguintes, no
mesmo projeto semeado, passaram a receber 409 por causa dele e não do que mediam.
É a **LP-04** ("fixtures que montam estado direto no banco") se provando sozinha,
no mesmo dia em que está adiada. Corrigido com `finally` que devolve o status.

**Grupo:** 2.

---

## ACHADO-31 — o XML da fábrica só é validado na emissão, dois passos depois do upload · PARCIALMENTE RESOLVIDO 03/09/2026 (F2-16, item 2 do bloco fiscal) — falta o markup de ajuste

Encontrado pelo Marcelo em 31/08, ao não conseguir concluir a etapa 15.

**O upload aceita qualquer arquivo.** `POST /ciclo/15/nfe-fabrica`
(main.py:14680) só verifica que veio um arquivo — a mensagem
*"Anexe o XML da NF-e da fábrica"* dispara com campo vazio, não com conteúdo
errado.

**Quem rejeita é a emissão**, quando `mod_nfe.preview(xml_bytes, markup)`
não acha o `infNFe`. O erro aparece dois passos depois da causa, e não diz
que o problema é o arquivo.

**Conserto:** validar no upload. O arquivo entra ou não entra ali.

### RESOLVIDO 03/09 — a metade da validação

`fiscal/mod_nfe.problemas_de_upload(xml)` devolve `(ok, problemas)` no mesmo formato do
`consistencia_interna` do ACHADO-44, e `POST /ciclo/15/nfe-fabrica` recusa com 400 **antes de
gravar documento nenhum**. O parser sempre esteve bom — `parse_nfe` já sabia recusar XML mal
formado e XML sem `<infNFe>` com mensagem clara; ninguém escutava no momento certo.

Recusa quatro coisas: XML mal formado; XML sem `<infNFe>`; nota que parseia mas **não tem item
nenhum** (não há o que emitir); e item sem NCM, CFOP, unidade ou com quantidade não positiva —
nomeando quais itens estão furados. Esse último grupo é a regra do item 4 do mesmo bloco
aplicada ao ITEM: *erro de schema da SEFAZ é falha nossa de validação*, e a nota não deve chegar
lá para descobrir que o campo estava vazio.

**Medido antes de travar**, nos 5 XML conhecidos (os 3 reais da fábrica — 195, 89 e 13 linhas —
e as 2 fixtures sintéticas): **zero** itens sem NCM, sem CFOP, sem unidade ou com quantidade
zerada. A trava não rejeitaria nenhum arquivo real conhecido. Ela é **prospectiva, só na porta
de entrada** (mesmo desenho do ACHADO-44): documento carregado antes dela continua sendo
conferido na emissão, que segue parseando por conta própria — defesa em profundidade, não porta
substituída.

**Correção de uma medição minha, para o registro:** ao medir eu li as chaves em maiúsculas
(`NCM`/`CFOP`) e o parser as grava em minúsculas, o que me fez relatar que os itens reais não
tinham NCM nem CFOP. Errado — o texto original desta seção estava certo em tudo, inclusive no
"12 itens", que são os consolidados do `NFe-163298` (13 linhas → 12).

**Prova:** `tests/test_achado31_xml_no_upload.py` (9 — a medição dos 5 arquivos travada como
teste, as quatro recusas nomeadas, e os dois aceites de ponta a ponta: o upload ruim para na
porta sem deixar documento, o upload bom continua entrando). Rodados junto os três arquivos que
sobem XML pela mesma porta (`test_nfe_etapa15_e2e`, `test_aceite_achado18`,
`test_dre_ciclo_completo_e2e`) — é neles que apareceria se a trava tivesse fechado a porta do
arquivo legítimo. Suíte completa: **2585 passed, 4 xfailed, 0 failed**.

**O que NÃO foi feito, e por isso o achado fica PARCIAL:** o *markup de ajuste* decidido em
31/08 (a seção abaixo) continua sem uma linha de código — medido em 03/09: não existe
`markup_ajuste` em lugar nenhum, e o rateio segue sobrescrevendo o valor digitado via
`rescalar_itens_para_total` quando há contrato. Decisão tomada e não implementada, sem dono em
nenhum item do bloco fiscal — registrada agora como LP-15 para não sumir.

### O campo "30" ao lado de cada arquivo — corrigido em 31/08

**Primeira versão desta seção dizia que o campo era inútil. Estava errada.**
É o `markup_pct`, e ele tem propósito, explicado pelo usuário: a NF-e de
**saída** extrai os produtos da NF-e de **entrada** (a da fábrica), e o
markup leva o valor do produto de uma para a outra. Nome proposto pelo
usuário: **"markup de ajuste"**.

**O defeito real é maior do que a falta de rótulo:** quando existe contrato,
o código reescalona os itens para a parcela Mercadoria do `Val_Cont`, e o
próprio comentário diz *"o markup vira output do rateio"* — com o fallback
*"sem contrato/Val_Cont (venda avulsa/teste) → mantém o markup"*. **O valor
digitado é descartado justamente no caso normal.**

### DECIDIDO 31/08 — o rateio sugere, o markup manda

**O rateio pelo `Val_Cont` deixa de sobrescrever e passa a preencher.** Ele
calcula o markup implícito e **pré-preenche o campo**; o usuário ajusta se a
realidade do projeto exigir; a emissão usa o que está no campo. Um número só
manda, e a sugestão vira valor inicial em vez de segundo dono.

**Por que o markup precisa ser editável** (razão do usuário): quando parte
do projeto é **produzida localmente**, a NF-e da fábrica não cobre tudo —
forçar a face da saída a ser a parcela Mercadoria rateada dos itens da
fábrica produz um número que não corresponde ao que saiu.

O campo ganha o nome **"markup de ajuste"**.

**Consequência aceita, registrada para não virar susto:** o rateio existe
hoje para *"alinhar a FACE da NF-e à parcela Mercadoria"* (comentário do
próprio código). Com o markup podendo sobrepor, **a face da nota deixa de
bater com a receita de mercadoria escriturada**. Gerencialmente é
irrelevante — a contabilidade vem de `_valores_segmentados_do_projeto`, não
da nota. Fiscalmente é divergência que alguém vai perguntar sobre um dia.

**Grupo:** 2.

---

## ACHADO-32 — a guarda entrou no servidor e a tela continuou oferecendo a porta fechada · RESOLVIDO 01/09/2026

Encontrado pelo Marcelo em 01/09, na Conciliação Final do ciclo de
homologação. Relato dele: *"na hora de dar o veredito nas provisões que
restaram a tela não parece processar o veredito"*.

**Não é a tela que não processa. É o servidor que recusa, e a tela que
continua pedindo.**

O F2-3 (ACHADO-26, ontem) fechou a porta dos fundos:
`POST /api/financeiro/resolver-saldo-provisao` (main.py:10264) agora
responde **409** para qualquer rubrica fora de
`_PROV_FORA_DO_VEREDITO = {"2.1.04.13", "2.1.04.19"}` — Impostos e Custo
Financeiro. Todas as demais têm que passar pela Fila de Provisões.

A tabela da Etapa 21 é montada por `_reconProvTabelaHtml(..., {editavel:true})`
e desenha **Efetivar/Resolver em toda linha**, sem saber dessa regra. Na tela
do Marcelo, das seis provisões abertas, **nenhuma** podia ser resolvida ali:
Comissão de Vendedor, Comissão de Gerente, Retenção, Comissão Adicional,
Montagem e Garantia são todas rubricas de veredito nomeado.

E o texto do próprio card, escrito em 07/08, ainda instrui a fazer o que o
servidor passou a recusar em 31/08:

> *"o botão abaixo NÃO força essas duas; use Efetivar/Resolver na tabela se
> precisar agir nelas"*

**É o padrão "enumere os irmãos" ao contrário.** Nas ocorrências anteriores a
guarda existia num endpoint e faltava no irmão. Aqui a guarda entrou nos dois
endpoints e faltou no **chamador**: a UI oferece um botão cuja resposta é
409 em 100% das linhas que ela mostra.

**Irmãos a enumerar:** `_reconProvTabelaHtml` é compartilhado por três telas
(Financeiro em leitura, modal de Reconciliação do projeto, Etapa 21). As duas
editáveis — modal e Etapa 21 — têm o mesmo botão e o mesmo 409. Reconferido no
conserto (grep pelas chamadas de `_reconProvTabelaHtml`): continuam sendo só
essas três — nenhuma quarta tela apareceu.

**Conserto (docs/db/TAREFA_CONCILIACAO_UI.md, item 1):** `mod_contabil.
reconciliacao()` passa a expor `exige_veredito` por linha — derivado da MESMA
`_PROV_FORA_DO_VEREDITO` que o endpoint usa pra recusar, nunca uma cópia no
JavaScript (isso recriaria o defeito na próxima mudança de regra). A linha
"veredito nomeado" perde Efetivar/Resolver genéricos e ganha um link "Dar
veredito na Fila de Provisões"; a rota genérica (Impostos/Custo Financeiro)
mantém os botões, agora com tooltip dizendo o EFEITO no livro (item 3), não o
nome do botão. Texto do card reescrito (a frase de 07/08 que o F2-3 invalidou).

Junto (mesmo ciclo, TAREFA_CONCILIACAO_UI.md itens 2 e 4 — pedidos do Marcelo
no mesmo percurso manual): selo de estado por linha (Em Aberto/Efetivada/
Resolvida/Na Fila — texto, não só cor) com realce de um segundo na linha que
acabou de mudar, e toast dizendo o valor ("Efetivado R$X"/"Resolvido R$X"/
"Nada a resolver"); `#ciclo-panel` deixa de ser um overlay curto demais —
`#page-02.ciclo-on` esconde o resto da tela (a negociação não aparece mais
por baixo ao rolar com o Plano de Pagamento aberto).

**Prova:** `tests/test_aceite_conciliacao_ui_item1.py` (flag derivada da
constante + controle negativo movendo um código pra `_PROV_FORA_DO_VEREDITO`),
`tests/test_e2e_browser_conciliacao_ui.py` (navegador — os três estados
batidos contra o JSON real do endpoint, tooltips, selo, toast) e
`tests/test_e2e_browser_ciclo_overlay.py` (navegador — Ciclo aberto esconde a
negociação, `.modal-overlay` continua visível).

**Correção sobre `446216b` (01/09):** o selo do commit original misturava dois
eixos — "Na Fila" (uma ROTA, onde se age) entrava na mesma cadeia de decisão
do estado do dinheiro, e vinha ANTES de "Efetivada", tornando "Efetivada"/
"Parcialmente Efetivada" inalcançáveis pra qualquer código fora de Impostos/
Custo Financeiro (mesmo `efetivar-provisao` não tendo guarda de veredito —
qualquer rubrica pode acumular `efetivado` de verdade). Corrigido: o selo
(EM ABERTO/PARCIALMENTE EFETIVADA/EFETIVADA/RESOLVIDA/"—") só reflete o fato
do dinheiro; "onde se agir" continua só na célula de Ação, via
`p.exige_veredito`, já correta desde `446216b`. Também corrigido:
`|saldo_aberto|<0.005` sozinho marcava "Resolvida" uma rubrica NUNCA
constituída (o teste original gravava isso como certo — trocado pela
asserção que exige movimento real: provisionado, efetivado ou resolvido
≠ 0); e o toast de Efetivar mostrava o valor DIGITADO, não o do razão
(`d.lancamento.valor`, como o Resolver já fazia), e não distinguia um clique
novo de um repetido no mesmo dia — `efetivar_provisao` é idempotente por ref
e o segundo clique não lança nada, então o endpoint passa a devolver `novo`
(checando `lancamento_por_ref` ANTES de chamar) e o toast diz "Já efetivado
hoje." em vez de fingir um lançamento que não aconteceu. Controle negativo
de cada uma das três, revertendo e confirmando que o teste correspondente
falha, documentado na conversa.

**Grupo:** 1.

---

## ACHADO-33 — o conserto do ACHADO-32 tirou a única porta por onde o custo de fábrica e de montagem entrava · RESOLVIDO 01/09/2026 (item 6)

**Achado meu, 01/09, conferindo o c6fdf38. A causa é minha: o
`TAREFA_CONCILIACAO_UI.md` item 1 escreveu "veredito nomeado → link pra
Fila, sem Efetivar/Resolver genéricos" — e Efetivar não tinha nada a ver com
o 409.**

O F2-3 fechou **`resolver-saldo-provisao`**. `efetivar-provisao` nunca teve
guarda de veredito, e não devia ter: são ações diferentes.

- **Efetivar** registra um fato que ACONTECEU — o custo real, na competência
  real. É a coisa que a auditoria inteira defendeu contra o custo estimado
  de uma vez na NF-e.
- **Veredito** decide o destino do que SOBROU no fim. É decisão, precisa de
  nome, data e pessoa.

A tela agora não oferece Efetivar em nenhuma rubrica de veredito nomeado —
ou seja, em todas menos Impostos e Custo Financeiro.

**Quem alimenta cada provisão, medido:**

| rubrica | alimentador real |
|---|---|
| Comissões (2.1.04.10/11/12/21) | `mod_folha` |
| Garantia (.03) e Assistência (.05) | `mod_assistencias` |
| **Montagem (2.1.04.02)** | **nenhum** |
| **Fábrica e fornecedores (.06 .07 .08 .09 .14)** | **nenhum** |

Para essas seis, o botão genérico era a **única** rota viva. Sem ele, o
custo da fábrica — o maior número de qualquer projeto — só entra no
fechamento, pelo veredito `encerrada_valor_menor`, capado ao saldo aberto e
datado no dia do encerramento. **A competência real morre.**

### E os eventos que existiam para isso nunca foram ligados

`EVENTOS` tem `"execucao_montagem"` (2.1.04.02 × 1.1.01) e
`"pagamento_fabrica"` (2.1.04.06 × 1.1.01). Procurados no código inteiro:
aparecem na tabela de eventos e **em testes**. Nenhum caminho da aplicação
dispara os dois.

É a **sétima ocorrência** do padrão (a) — "o mecanismo existe e o caminho
real não usa" — e a mais cara delas, porque os testes exercitam
`registrar_evento` direto e o mecanismo parece vivo.

### A regra que fica

**A restrição da Fila é sobre RESOLVER, nunca sobre EFETIVAR.** O link da
Fila substitui o Resolver; o Efetivar continua em toda rubrica (menos as
duas que o módulo Assistências já alimenta, guarda de 07/08 que continua
valendo).

**Conserto aplicado (item 6):** o estado "veredito nomeado" da tabela volta
a mostrar Efetivar + input (com o tooltip do item 3); só o Resolver
genérico sai, trocado pelo link da Fila. Assistência/Garantia mantêm o
Efetivar travado do módulo Assistências, agora dentro deste mesmo ramo (elas
também são veredito nomeado).

**Prova:** `tests/test_e2e_browser_conciliacao_ui.py` — aceite que importa:
a linha de Montagem (2.1.04.02, veredito nomeado, **sem alimentador**) com
Efetivar habilitado e Resolver ausente. Controle negativo: Efetivar
removido de toda rubrica de veredito nomeado — o teste falha na linha de
Comissão (2.1.04.10), antes mesmo de chegar em Montagem.

**A asserção do item 1 mudou de forma — a segunda vez nesta tarefa que isso
acontece** (a primeira foi "RESOLVIDA" na rubrica nunca constituída, item
2). **Saiu:** `assert linha_comissao.locator('button:has-text("Efetivar")').count() == 0`
(gravava o erro de redação do item 1 como correto — "veredito nomeado →
nenhum botão, só link"). **Entrou:** o Efetivar tem que estar presente e
HABILITADO em rubrica de veredito nomeado; só o Resolver genérico continua
ausente, substituído pelo link da Fila.

**O que fica aberto — decisão do Marcelo (item 7, medido sem mexer):**
`execucao_montagem`/`pagamento_fabrica` (`EVENTOS`, só disparados por
teste) — ligar (a versão de hoje faz só o lançamento provisão×caixa, SEM a
perna de despesa que `efetivar_provisao` já faz — ligar assim perderia a
competência real) ou remover da tabela. Ver LP-11 em
`docs/db/LISTA_PARALELA.md`.

**Grupo:** 1.

---

## ACHADO-34 — `conciliar_final` exige veredito pelo SALDO, não pela decisão — quem zera antes do fechamento nunca passa pela exigência · RESOLVIDO 03/09/2026 (F2-8)

**Generalização (01/09, ao mover pra fila ativa da Fase 2 — antes registrado
como LP-12):** `conciliar_final` monta a lista de rubricas que exigem
veredito olhando quem **ainda tem saldo aberto** no momento da Conciliação
Final — não quem foi de fato **decidido** por um veredito nomeado. Qualquer
mecanismo capaz de zerar o saldo de uma provisão ANTES desse momento
atravessa a exigência inteira sem nunca precisar dela. `mod_folha` é o
**caso real** disso, medido — não o único possível.

Encontrado no mesmo levantamento do ACHADO-33. `mod_folha.py:306` chama
`efetivar_provisao` e, na linha seguinte, `resolver_saldo_provisao` direto
em Python — sem passar pelo endpoint, portanto sem o 409 do F2-3 e sem
gravar `VeredictoProvisao`.

**Não está claro que seja defeito**, e por isso é achado e não conserto: a
folha É o ato nomeado — funcionário, competência, valor, aprovação. Talvez
seja um registro melhor que um veredito digitado à mão.

O que não pode continuar é **implícito**. Ou a folha é reconhecida por
escrito como uma segunda forma legítima de veredito, ou ela grava um
`VeredictoProvisao` com origem `folha`. É o quinto irmão de
`resolver_saldo_provisao`, e ninguém o tinha enumerado.

**Medido em 01/09 (item 8, sem mexer):** só `2.1.04.12` (Retenção de
Comissão de Vendas) passa por esse caminho — as outras comissões não são
tocadas por `mod_folha`. Depois de uma folha paga, o projeto chega na
Conciliação Final **sem** `VeredictoProvisao` pra essa rubrica, e **não
trava**: `conciliar_final` só exige veredito pra provisão com saldo aberto,
e a folha já zerou o saldo antes de o projeto chegar lá. Consequência:
`relatorio_projetos_encerrados_por_reversao` (que lista por veredito
revertido) nunca enxerga esses casos — não existe veredito nenhum pra
listar.

**Grupo:** 1.

---

### DECIDIDO 03/09 — a folha GRAVA um veredito, não é reconhecida como um

Das duas saídas que o achado deixava abertas, o Marcelo escolheu a segunda: a
folha passa a gravar um `VeredictoProvisao`. A primeira — reconhecer por escrito
que a folha já É o ato nomeado — foi recusada porque deixaria o
`relatorio_projetos_encerrados_por_reversao` permanentemente cego a esses
projetos, e o relatório é o contra-controle do ACHADO-16: sem ele, "encerrado
por reversão" volta a ser uma categoria que ninguém consegue auditar.

**Sem migration.** `VeredictoProvisao` não tem coluna `origem`, mas tem `motivo`,
`ref` e `decidido_por_id` — o ato que decidiu cabe no campo escrito, e criar uma
coluna pra guardar o que o campo já guarda custaria uma migration por nada.

### Conserto (03/09)

`mod_contabil.resolver_por_ato_nomeado` é a porta única para resolver o saldo de
uma provisão por um ato nomeado que acontece FORA da Conciliação Final. Genérica
de propósito: hoje o único chamador é `mod_folha.pagar`, mas o achado registra
que a folha é o caso real medido e não o único possível — o próximo mecanismo
que zerar uma provisão antes do fechamento tem uma porta certa pra usar, em vez
de chamar `resolver_saldo_provisao` direto e sumir do rastro (a regra das "duas
portas" do ROTEIRO, aplicada antes de a segunda porta existir).

**O veredito sai do SINAL do saldo, derivado de `vereditos_validos_para_saldo`** —
a mesma função que `resolver_veredito_provisao` usa pra recusar, nunca uma
segunda cópia dos limites (é literalmente a doença que o ACHADO-41 nomeia).
FALTA ou zero → `efetivada`; SOBRA → `encerrada_valor_menor` com
`valor_efetivado=0`, o caso que o próprio `resolver_veredito_provisao` já
documentava: a rubrica foi efetivada mais cedo no projeto, fora daquela chamada,
e chega só com o resíduo a reverter.

**O livro não muda.** Nos dois sinais o caminho termina no mesmo
`resolver_saldo_provisao` que a folha chamava sozinha — o que entra é o rastro,
não a contabilidade. Só o `ref` do lançamento ganha sufixo (`:ajuste` →
`:ajuste:residual`/`:reverte`); conferido que nada no repositório dependia dessa
string. `mod_folha.pagar` ganhou `decidido_por_id=None` e `main.py` passa
`usuario.get("id")` — o único chamador real, enumerado antes de mudar a
assinatura.

**Prova:** `tests/test_achado34_veredito_da_folha.py` (5 aceites) — veredito
nomeado existe depois da folha paga, com motivo citando a folha e a competência
e `decidido_por_id` de quem pagou; SOBRA vira `encerrada_valor_menor` e o
projeto **passa a aparecer** no relatório de encerrados por reversão (a
consequência exata que o achado registrava como perdida); o livro conferido
conta a conta contra os mesmos números que `test_comissao.py` já travava
(despesa, saldo da provisão, rota "sem DRE" com 4.4.02/5.6.10 intocadas); FALTA
vira `efetivada` com a despesa formal pelo valor ajustado; idempotência por
`ref`. Suíte completa: **2570 passed, 4 xfailed, 0 failed** (era 2565 — os 5
aceites novos, nada mais mexeu).

**Controle negativo:** revertida só a chamada em `mod_folha` para
`resolver_saldo_provisao` (assinatura mantida, pra não falhar por `TypeError`),
os aceites 1, 2 e 4 falham em `len(vs) == 1` com **zero vereditos** — o achado
em si, na linha que o descreve. Os aceites 3 e 5 passam nos dois lados **por
desenho**, e é assim que devem se comportar: o 3 afirma que o livro NÃO muda
(controle de regressão, não detector do achado) e o 5 chama
`resolver_por_ato_nomeado` direto, provando a idempotência da função e não o
caminho da folha. Três detectores, dois controles de propriedade — a distinção
fica escrita pra ninguém ler "5 aceites" como "5 provas do achado".

**Grupo:** 1.


## ACHADO-35 — a idempotência recusa o lançamento legítimo, e antes de hoje recusava em silêncio · RESOLVIDO 02/09/2026 (B1)

Encontrado pelo Marcelo em 01/09, no percurso do `v2026.09.01-beta1`.
Lançou R$ 3.000,00 em Provisão de Montagem, precisou lançar **mais** R$
3.000,00 no mesmo dia, e o sistema recusou.

`efetivar_provisao` é idempotente por
`ref = "ef:<projeto>:<conta>:<valor>:<hoje>"` — chave desenhada em 07/08
**contra o duplo-clique**. Ela não distingue *repetição acidental* de
*segunda efetivação real de mesmo valor no mesmo dia*, e a segunda é um
evento normal: duas entregas de montagem, dois pagamentos parciais iguais.

**A parte grave é o que acontecia antes do conserto de hoje (item 3 do
ACHADO-32):** a chamada era no-op, o backend devolvia o lançamento antigo, e
a tela dizia **"Efetivado R$ 3.000,00"**. O operador via a confirmação de
um lançamento que não aconteceu. O item 3 tornou a recusa visível; **não
tornou o lançamento possível.**

Prova de que a guarda protege pouco: o Marcelo lançou R$ 2.000,00 em
seguida e **passou** — o valor entra na chave. Ela só barra o par idêntico.

### O desenho certo: confirmar, não recusar

A idempotência serve à requisição repetida (duplo-clique, retry de rede),
não ao operador que quer lançar de novo. Então:

> "Já foram efetivados R$ 3.000,00 nesta conta hoje. Confirmar a efetivação
> de **mais** R$ 3.000,00?"

Confirmado, o lançamento acontece — com `ref` novo (sequencial dentro do
dia), porque é outro fato. Cancelado, nada acontece. **Vale para qualquer
segundo lançamento no mesmo dia, de valor igual ou diferente** (pedido do
Marcelo: "poderia haver erro também" no de R$ 2.000,00) — a tela mostra o
que já foi efetivado hoje e pergunta.

A trava de duplo-clique do botão continua sendo o que protege o acidente.

**Conserto (docs/db/TAREFA_PERCURSO_0109.md, item B1):** `/api/financeiro/
efetivar-provisao` (main.py) ganhou a checagem por `mod_contabil.
efetivado_no_dia(db, owner_tipo, owner_id, projeto_id, codigo, dia)` — soma
do **razão** (débito na própria conta de provisão, no dia), nunca uma soma
lembrada pela tela (regra 3). Já havendo lançamento no dia — valor igual ou
diferente — o endpoint devolve `{"ok": false, "duplicado": true,
"total_hoje": X}` em vez de lançar; a tela (`reconProvEfetivar`, static/
index.html) pergunta via `confirmarPopup` ("Já foram efetivados R$ X nesta
conta hoje. Confirmar a efetivação de mais R$ Y?"); confirmado, reenvia com
`confirmado:true` e o backend lança com `ref` sequencial
(`ref_base + ":" + (qtd_hoje+1)`), nunca colidindo com o `ref` do dia
anterior de lançamentos. Cancelado, nada é enviado. A trava de duplo-clique
do botão (`btn.disabled`) continua intocada.

**Prova:** `tests/test_aceite_achado35.py` (dois aceites HTTP diretos: mesmo
valor e valor diferente, ambos pedem confirmação, ambos lançam DOIS
lançamentos com `ref` distintos ao confirmar, `total_hoje` sempre do
razão) e `tests/test_e2e_browser_conciliacao_ui.py` (navegador — Custo
Financeiro parcialmente efetivado, segunda efetivação pede confirmação,
cancelar não lança nada, confirmar lança e soma 800,00). Controle negativo:
`main.py`+`mod_contabil.py` revertidos (stash) — os dois aceites HTTP E o
teste de navegador falham (o navegador trava esperando um texto que nunca
aparece); restaurados, os três voltam a passar.

**Grupo:** 1.

---

## ACHADO-36 — o sistema comunica pelo canto da tela · RESOLVIDO 02/09/2026 (B2, módulo financeiro/provisões)

Decisão do Marcelo, 01/09: *"Precisa comunicar algo, coloque no centro da
tela. Se precisa de confirmação coloque um botão de ok, mas não coloque no
cantinho escondido."*

`showToast` no canto inferior direito é hoje o canal de **tudo** —
inclusive de recusas ("Informe o valor real efetivado", "Já efetivado
hoje") e de confirmações de lançamento contábil. Foi assim que o "não
processa o veredito" nasceu: a informação existia e não era vista.

**A regra que passa a valer:**

| o que | onde |
|---|---|
| recusa, erro, ou qualquer coisa que o usuário precise **entender** | box central, no design do Orizon, com OK |
| pedido de decisão | box central, com as opções |
| confirmação de ação trivial já visível na tela | toast pode ficar |

`avisoPopup` / `confirmarPopup` já existem e já são do design system — o
trabalho é de roteamento, não de componente novo.

**Correção sobre a redação original:** `showToast(msg, true)` já não caía no
canto — redirecionava para `mostrarErroModal` (`erro-modal-overlay`), um
overlay manuscrito próprio, de 2026-08-17, **fora do design system**
(z-index/cores hard-coded, sem foco automático, sem Esc/Enter). O problema
não era posição na tela; era ser um componente PARALELO a `avisoPopup`/
`confirmarPopup`, com comportamento levemente diferente — a mesma família
de defeito do ACHADO-32/33 (a mesma ação existindo em dois lugares que
divergem sozinhos), aqui entre dois avisos em vez de duas rotas.

**Conserto (docs/db/TAREFA_PERCURSO_0109.md, item B2):** levantamento no
sistema inteiro: **200** chamadas de `showToast(..., true)` no candidato
`v2026.09.01-beta1` (contagem correta atravessa quebra de linha — uma
delas se parte em duas linhas e escapa de um grep simples). Convertidas
nesta rodada, escopadas ao módulo financeiro/provisões (recon\*/filaProv\*/
efetivar\*/resolver\*/folha\*/contasPagar\*/pagarFornecedor\*/provisao\*/
lancamento\*/rateio\*/periodo\*, static/index.html): **36** chamadas — todas
recusa/erro simples (nenhuma era pedido de decisão), viraram
`avisoPopup(msg, {titulo:'Financeiro'})`. Ficam **164** no resto do
sistema — higiene, fora de escopo desta rodada.

**Prova:** `tests/test_aceite_achado36.py` — checagem estrutural (zero
`showToast(..., true)` restando na faixa do módulo; contagem total do
sistema = 164) e um aceite de navegador (sem projeto ativo,
`abrirReconciliacaoProjeto()` mostra o `avisoPopup` do design system —
`<h4>Financeiro</h4>` com botão `[data-act="ok"]` — nunca o
`#erro-modal-overlay`). Controle negativo: revertida a conversão de
`abrirReconciliacaoProjeto`, os três testes falham (o de navegador trava
esperando um popup que não aparece); restaurada, os três voltam a passar.

**Grupo:** 5 (higiene), com exceção: as recusas de lançamento contábil sobem
para o grupo 1, porque a mensagem não vista é o que produz o lançamento
errado.

---

## ACHADO-37 — a Fila de Provisões empilha todos os projetos para sempre

`provisoes_em_aberto` devolve uma lista plana de toda provisão aberta de
**todos** os projetos. Com o sistema em uso, é uma pilha que só cresce.

Observação do Marcelo: a unidade de trabalho é o **projeto** — quem resolve
tem o pedido e a nota daquele projeto na mão. A tela lista **projetos**, e
abre as provisões de um projeto por vez.

**Grupo:** 2.

---

## ACHADO-38 — a AF2 pede senha antes de conferir se já foi aprovada · RESOLVIDO 02/09/2026 (B3)

Reaprovar a AF2 abre o pedido de login e senha do gerente, em vez de dizer
"Aprovação Financeira já realizada".

Não é só a tela: `POST /ciclo/11d/aprovar` (main.py:7877) chama
`_aprovador_financeiro(...)` — que valida credencial — **antes** de
qualquer checagem de estado. A ordem está invertida nas duas pontas.

**A regra:** conferir o estado antes de pedir credencial. Pedir senha para
uma ação que não vai acontecer treina o operador a digitar senha sem ler.

**Correção sobre a redação original:** não havia, na verdade, um "já
aprovada" nem antes nem depois da credencial — `_set_etapa_status`
sobrescreve o status sem olhar o anterior. A checagem que faltava teve
que ser **criada**, não só reordenada.

**Conserto (docs/db/TAREFA_PERCURSO_0109.md, item B3):**

- **Backend** (main.py, `/ciclo/11d/aprovar`): todas as checagens de estado
  (escopo/tenancy — via `usuario` da sessão, não depende da credencial do
  aprovador —, existência, contrato, data de entrega, assinatura dupla,
  **11d já concluído** [checagem nova], subfases pendentes, rev2, fase
  completa) passam a rodar ANTES de `_aprovador_financeiro`. A credencial só
  é validada quando a aprovação vai mesmo acontecer.
- **Frontend** (`peConciliacaoAprovar`, static/index.html): reconfere
  `GET .../pe/conciliacao` (a MESMA fonte que desenha o botão — nunca uma
  cópia da regra) antes de `pedirCredenciaisGerente`; se `etapa_status ===
  'concluido'`, avisa "A AF2 já foi aprovada." e nunca chega a pedir senha.

**Irmãos enumerados — todo chamador de `pedirCredenciaisGerente`
(static/index.html), e se já checava estado antes da credencial:**

| função | checava estado antes? |
|---|---|
| `reconRecebConfirmar` | não — só trava de duplo-clique |
| `reconRecebReprogramar` | não — só validação de formulário (data preenchida) |
| `reconRecebDuvidoso` | parcial — `confirmarPopup` (confirmação de ação, não estado do servidor) antes |
| `fluxoRecebivelConfirmar` | não |
| `convDestravar` | não — só formulário (motivo) |
| `concluirAprovacaoFinanceira` | não — só `projetoAtivo` (precondição, não estado da ação) |
| `_provAprovar` | não |
| `_provAcao` | não |
| `enviarSolicitacaoMedicao` | não — só formulário (arquivo anexado) |
| `enviarParecerMedicao` | não — só formulário |
| `enviarDecisaoReprovado` | não — só formulário |
| `peConciliacaoDecidir` | não |
| **`peConciliacaoAprovar`** | **era não — RESOLVIDO nesta rodada** |
| `peConciliacaoReprovar` | não — fora de escopo (achado não nomeia; sem `fase_completa`-like gate, reordenar teria pouco efeito) |
| `ramoJurosLojaRegistrar` | não — só formulário |
| `devolucaoRegistrar` | não — só formulário |
| `cancelarContrato` | parcial — `_escolherDesfechoCancelamento()` olha `_contratoTotalmenteAssinado` antes, mas escolhe variante, não checa "já cancelado" |
| `ramoAntecipacaoRegistrar` | não — só formulário |
| `ramoFinanceiroTrocar` | não |
| `peUpload` | não — só formulário |
| `conferenciaRegistrar` | não — só formulário |
| `peConcluir` | não — só `projetoAtivo` |
| `peRevisao` | parcial — `confirmarPopup` (aviso de consequência) antes, não checagem de estado |
| `abrirModalReabrir` | parcial — `confirmarPopup` (aviso de consequência) antes, não checagem de estado |
| `revisarContrato` | parcial — `confirmarPopup` (aviso de consequência) antes, não checagem de estado |

Nenhum outro caso tem o mesmo formato do ACHADO-38 (checagem de "estado
JÁ CONCLUÍDO" que o servidor tem e a tela ignora) — os demais checam
formulário (obrigatório preencher algo) ou pedem confirmação de
consequência, categorias diferentes. Fora de escopo desta rodada; ficam
candidatos a auditoria de higiene futura.

**Prova:** `tests/test_aceite_achado38.py` — HTTP (aprova, aprova de novo
com senha ERRADA de propósito: a recusa tem que ser "AF2 já aprovada"
[400], nunca "Senha/perfil inválido" [403] — prova a ORDEM, não só a
existência; só um `LogAcaoGerencial` mesmo com duas chamadas) e navegador
(estado mockado como `concluido`, `peConciliacaoAprovar()` nunca abre o
modal de credenciais, mostra "A AF2 já foi aprovada." direto). Controle
negativo: backend revertido (stash) — teste HTTP falha (403 em vez de
400); frontend revertido — teste de navegador falha (modal de credenciais
abre). Ambos restaurados, voltam a passar.

**Grupo:** 1.

---

## ACHADO-39 — a decisão do ambiente é oferecida pela coluna errada · RESOLVIDO 02/09/2026 (B4)

Na AF2, `_peConcValidasPorSinal(a.diferenca)` escolhe os botões pelo sinal
de **Δ custo** — e a decisão é sobre **Δ a cobrar/estornar**.

O cabeçalho da própria tabela diz a diferença: *"Δ custo — só referência,
não é o valor cobrado"* e *"Δ a cobrar/estornar — valor que será
efetivamente cobrado/estornado do cliente"*.

Consequência medida na tela do Marcelo: ambiente com Δ custo +R$ 76,27 e Δ
a cobrar R$ 0,00 exige decisão, e o resultado registrado é **"Absorver R$
0,00"** — uma decisão sobre nada, que ainda assim bloqueia o
`fase.completa` e portanto a aprovação da AF2.

**Regra, a mesma do deságio:** decide quem move dinheiro. Sem Δ a cobrar não
há decisão a tomar — a linha entra como "sem diferença a decidir" e não
conta como pendência.

**Medição antes do conserto (regra da rodada — não apagar nada):** consulta
read-only na `orizon_homologacao` (167.88.33.121, via SSH) —

    total | zero_valor_contrato | absorver_zero
    ------+---------------------+---------------
        8 |                   4 |             4

Quatro linhas de `conciliacao_pe_fase` já eram exatamente esse padrão:
projetos **Teste_1** (`diferenca_cfo` 793.75 e 76.27) e **Teste_2** (mesmos
dois valores, mesmos ambientes — o percurso do Marcelo repetido), todas
`tipo_decisao='absorver'`, `diferenca_valor_contrato=0`,
`valor_aprovado=0`. `orizon_integracao` e `orizon_producao` — zero linhas
(tabela existe, vazia desse padrão). **Nenhuma linha foi apagada ou
alterada.** O que acontece com elas: continuam no banco, inertes —
`agregar_complemento` só soma decisões `'cobrar'`, então uma `'absorver'`
R$0,00 nunca contribuiu pra nada; daqui pra frente essas quatro linhas
simplesmente deixam de ser **exigidas** (o ambiente não entra mais em
`ambientes_com_pe` de `fase_completa`) — se o gerente abrir a tela de novo,
a linha mostra "Sem diferença a cobrar — nada a decidir." em vez do botão
"alterar", mas o registro histórico de 31/08-02/09 permanece intacto.

**Conserto (docs/db/TAREFA_PERCURSO_0109.md, item B4):**

- **Frontend**: `_peConcValidasPorSinal` passa a receber
  `a.diferenca_valor_contrato` (Δ a cobrar), não `a.diferenca` (Δ custo).
  Ambiente com `abs(diferenca_valor_contrato) <= 0.005` nunca mostra
  botões — mostra "Sem diferença a cobrar — nada a decidir.", mesmo se já
  tiver uma decisão antiga registrada (as quatro linhas de homologação
  incluídas).
- **Backend**: `mod_conciliacao_pe.decisao_e_necessaria(diferenca_valor_
  contrato)` (nova, `abs(round(dvc,2)) > 0.005`) filtra o conjunto
  `ambientes_com_pe` de `fase_completa` nos **três** lugares que o
  calculavam — `GET /pe/conciliacao` (já tinha o Δ a cobrar por ambiente
  calculado, só faltava filtrar), `POST /ciclo/11d/aprovar` e o **irmão
  encontrado ao revisar**: o PATCH genérico `/ciclo/<codigo>` tinha a
  MESMA conta ingênua ("todo PE carregado é pendência") duplicada. Os dois
  últimos agora chamam `main._pe_ambientes_pendentes_decisao(db, nome)`
  (nova, extrai a MESMA fórmula do GET) — nenhuma cópia da regra.
- **Não tocado, deliberadamente:** `mod_conciliacao_pe.decisao_valida`/
  `_VALIDOS_POR_SINAL` continuam validando pelo sinal de Δ CUSTO — regra
  dura, decisão do usuário de 2026-08-14, que o achado não pede pra mudar.
  **Risco residual MEDIDO, não mais hipotético — virou ACHADO-42:** o
  markup pode ser negativo (`comissao_arq_pct`/`fidelidade_pct` sem limite
  nenhum, ao contrário do desconto do orçamento), e nesse caso a rota
  fallback de `diferenca_valor_contrato_estimada` inverte o sinal de Δ a
  cobrar contra Δ custo — a tela oferece um botão que o backend recusa com
  400. Prova computada (markup = −1,0 com uma comissão de 150%) em
  ACHADO-42, mais abaixo. Sem conserto ainda — decisão de conserto em
  aberto lá.

**Prova:** `tests/test_aceite_achado39.py` — aceite principal (venda_pe ==
VBVA contratado → Δ a cobrar = 0 com Δ custo = 3000; `fase.completa` já
True sem decisão nenhuma; `/ciclo/11d/aprovar` aprova sem exigir a decisão
deste ambiente) e controle positivo (Δ a cobrar ≠ 0 continua pendência
normal, sem regressão). Controle negativo: `main.py`+`mod_conciliacao_pe.
py`+`static/index.html` revertidos (stash) — o aceite principal falha
(`fase.completa` volta a False); o controle positivo continua passando
(prova que o teste pega o achado certo, não qualquer coisa). Restaurado,
os dois voltam a passar.

**Grupo:** 1.

---

## ACHADO-40 — a coluna Decisão desalinha depois de decidida · PARCIALMENTE RESOLVIDO 02/09/2026 (B5)

Cosmético, medido na imagem do Marcelo. A célula decidida é um flex livre
(`<span>rótulo</span> valor <button>alterar</button>`), então rótulo, valor
e botão caem em posições diferentes a cada linha, conforme o comprimento do
texto. Precisa de sub-colunas de largura fixa.

E, no mesmo lote: o link **"Dar veredito na Fila de Provisões"** saiu como
`<a>` sem classe — azul de navegador, fora do design system. O verificador
de tokens não pega, porque não há cor literal no CSS: a cor é o default do
agente. O Marcelo pediu outra coisa, que resolve os dois problemas — ver o
item correspondente na tarefa.

**Conserto (docs/db/TAREFA_PERCURSO_0109.md, item B5) — só o desalinhamento:**
a célula decidida (`peConciliacaoRender`, static/index.html) ganhou
sub-colunas de largura fixa (rótulo 64px, valor 90px alinhado à direita em
fonte monoespaçada, botão `flex:0 0 auto`) — rótulo/valor/botão caem no
mesmo lugar horizontal em toda linha, qualquer que seja o texto
("Manter"/"Absorver"/"Cobrar"/"Estornar", R$ 100,00/R$ 123.456,78).

**O link azul NÃO foi tocado nesta rodada** — a própria Parte A do
TAREFA_PERCURSO_0109.md nomeia esse conserto como parte do redesenho da
tela de Provisões (botão "Resolver" volta, substituindo o link), e a Parte
A está explicitamente fora desta rodada (decisão do Marcelo, frente
própria). Achado permanece aberto só nessa metade.

**Prova (por captura, não por asserção de DOM — o defeito é visual):**
`tests/test_aceite_achado40.py` — duas linhas mockadas com rótulo e valor
de comprimentos bem diferentes ("Manter"/R$100,00 vs "Estornar"/
R$123.456,78); screenshot real salvo em disco (path impresso no teste) +
medição de bounding box da sub-coluna de valor nas duas linhas (mesmo `x`
= alinhado). Controle negativo: revertido, a mesma consulta de DOM não
encontra as sub-colunas (markup antigo não as tem) — o teste falha.
Restaurado, volta a passar.

**Grupo:** 5.

---

## ACHADO-41 — a Fila oferece os quatro vereditos, e o servidor recusa dois por sinal

Achado meu em 01/09, conferindo a Parte B. **É a causa direta do "não
consegui resolver a Montagem do Teste 1"** que o Marcelo reportou, e a
medição da Vera já continha a resposta sem que ninguém a lesse assim.

`static/index.html:15012-15015` desenha os quatro botões de veredito **em
toda linha**, sem olhar o sinal de `saldo_aberto`.
`resolver_veredito_provisao` recusa por sinal:

| estado da linha | vereditos que o servidor aceita | oferecidos na tela |
|---|---|---|
| SOBRA (saldo > 0) | encerrada_valor_menor, nao_se_aplica, ainda_vai_chegar | os quatro |
| FALTA (saldo < 0) | efetivada, ainda_vai_chegar | os quatro |

**Em toda linha da Fila há pelo menos um botão que é recusa garantida** — e
na sobra, que é o caso comum, o botão inútil é o primeiro da fileira,
"Efetivada", justamente o que soa natural para quem acabou de pagar uma
parcela. Foi exatamente o que aconteceu.

### É a quarta ocorrência do mesmo padrão em um dia

- **ACHADO-32** — a Conciliação Final oferecia "Resolver" com 409 garantido.
- **ACHADO-33** — ao fechar aquilo, fechamos também o que funcionava.
- **ACHADO-39** — a AF2 oferecia decisão escolhida pela grandeza errada.
- **ACHADO-41** — a Fila oferece veredito que o sinal já exclui.

**A regra, agora explícita:** *nenhuma tela oferece ação que o servidor
recusará por regra conhecida no momento de desenhar a tela.* Quando a regra
mora no backend, é o backend que diz quais ações valem para aquela linha —
a tela não recalcula e não adivinha.

O B6 (tooltips) foi o complemento certo e insuficiente: explicar bem um
botão que nunca vai funcionar não é ajuda.

**Conserto:** a linha da fila traz do backend a lista de vereditos válidos
(derivada do mesmo lugar que `resolver_veredito_provisao` usa para recusar,
nunca uma cópia da regra no JavaScript), e a tela desenha só esses. Os
tooltips do B6 ficam.

**Implementação:** `mod_contabil.vereditos_validos_para_saldo(saldo)` (nova)
— `resolver_veredito_provisao` passa a CHAMAR essa função nas suas duas
checagens de sinal (em vez de reimplementar o limiar inline), e
`provisoes_em_aberto` expõe `vereditos_validos` por linha, chamando a
MESMA função. `filaProvisoesCarregar` (static/index.html) filtra
`_FILAPROV_BOTOES` por `r.vereditos_validos.includes(...)` antes de
desenhar — nunca lista os quatro incondicionalmente.

**Prova:** `test_aceite_achado41.py` (HTTP — linha em SOBRA não tem
`efetivada` em `vereditos_validos`; linha em FALTA não tem
`encerrada_valor_menor`/`nao_se_aplica`; conferido também que o backend
continua recusando por trás, não é o campo ficando redundante por acaso)
+ `test_aceite_b6_fila_tooltips.py::test_linha_em_sobra_nao_desenha_botao_efetivada`
(navegador — linha em SOBRA nunca desenha o botão "Efetivada"). Controle
negativo: `mod_contabil.py`+`static/index.html` revertidos (stash) — os 2
aceites HTTP e o de navegador falham; restaurados, os 3 voltam a passar.

**Grupo:** 1.

---

## ACHADO-42 — o markup pode ser negativo, e aí o Δ a cobrar troca de sinal contra o Δ custo · RESOLVIDO 02/09/2026

Medido a pedido do Marcelo, verificando o risco residual anotado no
ACHADO-39 ("se o sinal de Δ a cobrar divergir do de Δ custo, a tela oferece
um botão que o backend recusa"). A pergunta era se `markup` podia ser
`<= 0`. **Pode — negativo, não só zero.**

`markup = (val_liq / CFO) if CFO > 0 else 0.0` (`mod_negociacao.
calcular_orcamento`). `val_liq = VAVO − cust_ad`, e `cust_ad` inclui
`comissao_arq_pct`/`fidelidade_pct` **sem nenhum limite** — ao contrário do
desconto do orçamento (`desconto_pct`), que passa por `limite_desconto` e
autorização de gerente quando excede o teto, comissão/fidelidade não têm
teto, nem autorização, nem clamp em `mod_orcamento_params.merge_parametros`
(`float(dn["comissao_arq_pct"] or 0)`, aceita qualquer valor).

**Prova (computada, não hipotética):**

```python
>>> import mod_negociacao as mn
>>> mn.calcular_orcamento(
...     [{"VBVA": 10000.0, "CFA": 5000.0, "desc_amb_pct": 0.0}],
...     {"incluir_custos": False, "comissao_arq_ativa": True, "comissao_arq_pct": 150.0},
...     desc_orc_pct=0.0)
{..., 'Val_Liq': -5000.0, 'Markup': -1.0, ...}
```

Uma comissão de 150% sobre a VAVA (erro de digitação plausível — 150 em vez
de 15) e nada mais especial já derruba o markup pra **-1,0**.

**Consequência para o ACHADO-39/B4:** com `markup = -1.0` e um ambiente com
Δ custo = +1000 (subiu), a rota fallback de `diferenca_valor_contrato_
estimada` (sem `valor_venda_pe`) calcula Δ a cobrar = 1000 × (−1.0) =
**−1000** — sinal invertido. A tela (B4, correta em usar Δ a cobrar) oferece
`manter`/`estornar` (sinal negativo); o backend (`decisao_valida`, que usa
Δ CUSTO, sinal "alta") só aceita `absorver`/`cobrar` para este ambiente —
**qualquer clique é recusado com 400** ("decisão incompatível com diferença
de CFO"). O residual deixa de ser hipotético: **é alcançável com um erro de
digitação num campo sem validação nenhuma.**

**O que isto NÃO é:** não é um defeito do B4 — o B4 fez a coisa certa
(mostrar o botão pela grandeza que o cliente vê). É um achado sobre a
AUSÊNCIA de limite em `comissao_arq_pct`/`fidelidade_pct`, e sobre
`decisao_valida` continuar ancorada em Δ custo (decisão de 2026-08-14) numa
situação em que essa grandeza já não é mais a que a tela usa para decidir
qual botão oferecer.

**Sem conserto nesta rodada** — é medição. Candidatos de conserto (não
decididos): (a) validar `comissao_arq_pct`/`fidelidade_pct` num teto
plausível, mesmo padrão de `limite_desconto`; (b) `decisao_valida` passar a
usar Δ a cobrar também, alinhando com o B4; ou (c) as duas.

**Grupo:** 2 (medição — decisão de conserto em aberto).

### DECIDIDO 02/09 — o mesmo portão do desconto

Decisão do Marcelo: **comissão de arquiteto e fidelidade passam pelo mesmo
portão do desconto** — teto do perfil, e autorização de quem tem limite
maior para estourar.

A razão é a que o próprio achado expõe: os três campos tiram dinheiro da
**mesma margem**. Um deles exigir gerente e os outros dois não é uma
assimetria sem defesa — quem quisesse contornar o teto do desconto já podia
fazê-lo digitando a diferença como comissão de arquiteto.

**Três coisas que decidem o conserto:**

**1 · O portão é o do perfil, não da loja.** O padrão real é
`Usuario.limite_desconto` → `perfis.desconto_max(nivel)`, verificado no
servidor por `_usuario_autoriza_desconto` (main.py:403). O achado de UAT de
10/08 vale aqui inteiro: *a autorização da tela sem trava no servidor é
decoração*.

**2 · Compor, nunca checar campo a campo.** Este é o achado da Vera de
12/08, e ele se repete aqui com três campos em vez de dois: naquela vez,
45% global + 45% individual davam 69,75% efetivo, e cada um passava
sozinho no limite de 50%. Comissão e fidelidade têm que ser medidas
**pelo efeito conjunto sobre a margem**, junto com o desconto que já
estiver aplicado — não cada percentual contra o teto.

**3 · Margem negativa não se autoriza.** O teto com autorização cobre a
venda agressiva; não cobre vender abaixo de zero. `Val_Liq < 0` é recusa
dura, sem credencial que a levante. Se algum dia houver caso real de venda
deliberadamente negativa, ele volta como decisão própria — não entra pela
porta de um campo sem validação.

**E a segunda metade do ACHADO-42 continua valendo:** com o portão, o
markup deixa de ir a negativo pela porta da digitação, mas `decisao_valida`
segue ancorado em Δ custo enquanto a tela decide por Δ a cobrar. Alinhar as
duas pontas é o que torna a divergência impossível **por construção**, e não
apenas improvável. Vale a regra que a auditoria já usou no deságio e no
markup de ajuste: **um número só manda.**

### Implementado 02/09 — os quatro itens do DECIDIDO

**1 · Portão no servidor.** `POST /api/projetos/<nome>/parametros` passa a
checar `comissao_arq_pct`/`fidelidade_pct`/`comissao_arq_ativa`/
`fidelidade_ativa` pelo MESMO mecanismo de `/margens` — `_usuario_autoriza_
desconto` (main.py:403), `LogAutorizacao` gravado inclusive na tentativa
recusada (`origem: "parametros_comissao_fidelidade"`).

**2 · Composto, nunca campo a campo.** `_maior_composto_com_parametros_pct`
(nova) roda o motor de verdade (`_negociacao_breakdown` →
`mod_negociacao.calcular_orcamento`) com a alavanca PROPOSTA sobreposta às
já salvas — nunca uma fórmula paralela. Por **AMBIENTE**, nunca a média do
orçamento (uma média diluiria o pior caso exatamente como o achado de
12/08 escondia o composto quando checado campo a campo): `Desc_Tot_
ambiente = (VBVA − Val_Liq_ambiente) / VBVA`, o maior entre todos os
ambientes de todos os orçamentos do projeto (exceto complemento,
neutralizado por design, mesma exceção de `_maior_desconto_efetivo_pct`).
`_negociacao_breakdown` ganhou `params_override`/`desconto_pct_override`/
`desconto_individual_override` pra pré-visualizar sem gravar. Os
chamadores existentes (`/margens`, `/descontos`) somam o resultado com
`max()` ao cálculo antigo (`_maior_desconto_efetivo_pct`) — a garantia de
12/08 continua exatamente como era, esta é adicional, nunca substitui.

**3 · Margem negativa é recusa dura.** `menor_val_liq < -0,005` (a menor
margem líquida entre os orçamentos do projeto) recusa com 400 ANTES de
qualquer tentativa de `_usuario_autoriza_desconto` — nenhuma credencial,
nem a do próprio Master (limite 50%, o maior do sistema), resolve.

**4 · `decisao_valida` alinhado a Δ a cobrar.** `mod_conciliacao_pe.
decisao_valida`/`sinal_diferenca` passam a receber `diferenca_valor_
contrato`, não `diferenca_cfo` — `montar_decisao` (única chamadora) troca
qual argumento repassa. A divergência do ACHADO-39 fica impossível **por
construção**, não só protegida pelo portão do item 1.

**Prova:** `tests/test_aceite_achado42_portao.py` (itens 1-3: comissão
sozinha recusada/aceita/autorizada/senha errada; COMPOSIÇÃO nas duas
ordens — desconto-depois-comissão e comissão-depois-desconto, cada um
sozinho dentro do limite mas recusado junto; controle positivo — composto
pequeno não bloqueia; margem negativa recusa mesmo com a própria
credencial de Master) + `tests/test_conciliacao_pe.py`/`tests/test_
medicao_achado42_markup_negativo.py` (item 4, via `montar_decisao` — testar
`decisao_valida` isolada com um valor literal não pegaria uma regressão de
qual argumento o chamador passa). Controle negativo: `main.py` revertido —
7 dos 9 aceites do portão falham (os 2 que sobram são os controles
positivos, que não dependem do gate); `mod_conciliacao_pe.py` revertido —
os 2 aceites do item 4 falham. Restaurados, tudo volta a passar (43
testes relacionados, mais a suíte completa).

---

## ACHADO-43 — o portão da comissão tem porta dos fundos: o cadastro do parceiro · RESOLVIDO 02/09/2026

Achado meu em 02/09, conferindo o portão do ACHADO-42 **no mesmo dia em que
ele foi construído**.

O portão cobre `comissao_arq_pct` quando o número é **digitado** — o `POST
/api/projetos/<nome>/parametros` agora passa por `_usuario_autoriza_desconto`.
Mas o campo tem uma segunda origem, que não passa por lugar nenhum:

```
main.py:17805   pct_parc = float(getattr(parc, "comissao_padrao_pct", 0) or 0)
main.py:17808   par["comissao_arq_pct"] = pct_parc
```

`Parceiro.comissao_padrao_pct` entra no orçamento **por default**, sem
autorização, e é gravado em três lugares sem validação nenhuma:

| onde | linha | validação |
|---|---|---|
| criar parceiro | main.py:11130 | `float(req.get(...) or 0)` |
| editar parceiro | main.py:11182 | `float(req[...] or 0)` |
| importação em lote | main.py:18427 | `float(item.get(...) or 0)` |

`Loja.comissao_padrao_pct` (database.py:568) é o irmão seguinte, ainda não
medido.

**Consequência:** um parceiro cadastrado com 150% aplica 150% em **todo
projeto dele**, sem passar pelo portão — e o portão recusaria o mesmo 150%
se alguém o digitasse na tela do orçamento. A trava vale para quem digita e
não vale para quem cadastra.

**A lição, e é sobre nós:** o portão foi construído hoje seguindo a decisão
do Marcelo, com aceite e controle negativo — e nasceu com o irmão não
enumerado. **A regra "enumere os irmãos" vale também para as guardas que a
gente acabou de escrever**, não só para as que encontramos prontas. A
pergunta que faltou é de uma linha: *de onde mais este campo pode vir?*

**Conserto:** o teto se aplica ao **valor efetivo que chega ao orçamento**,
qualquer que seja a origem. Ou o cadastro do parceiro valida contra o mesmo
limite, ou o portão passa a medir depois da fusão dos defaults — a segunda
é mais robusta, porque não depende de enumerar origens futuras.

**Grupo:** 1.

### Medição antes de escolher

A citação original ("`Loja.comissao_padrao_pct` (database.py:568)") estava
imprecisa: aquela linha é de `ParceiroLoja` (override por loja, tabela de
junção parceiro↔loja), não de `Loja` — `Loja` não tem essa coluna. Medido
também: `ParceiroLoja.comissao_padrao_pct` é **write-only** — gravado em
três lugares, lido em nenhum caminho de negócio (só aparece no array de
exibição do `_parceiro_dict`).

Nos três reais (Homologação/Integração/Produção): **zero parceiros
cadastrados**. Não há legado dos dois lados da escolha.

### Conserto (02/09)

Escolhida a **segunda opção** (medir depois da fusão): `_params_iniciais_projeto`
só *sugere* o default do parceiro em duas rotas GET/preview — nunca grava
sozinho. A única gravação real do campo composto é `POST
/api/projetos/<nome>/parametros`, já gated pelo ACHADO-42 desde o mesmo dia.
A porta dos fundos já estava estruturalmente fechada — exceto por uma
lacuna de UX nova: o auto-save do formulário (`salvarParametrosAuto`)
engolia `d.ok===false` em silêncio (ACHADO-36 de novo), inclusive quando a
recusa vinha de um valor de parceiro. Corrigido: `salvarParametrosAuto`
reabre `pedirCredenciaisGerente` quando `d.requer_autorizacao`.

**Prova:** `tests/test_achado43_porta_dos_fundos.py` (3 — inclui a medição
como teste, valor do parceiro passa pelo mesmo portão com e sem
autorizador válido) + `tests/test_achado43_autosave_e2e.py` (navegador —
recusa do servidor abre o modal, não falha em silêncio). Controle negativo
confirmado nos dois arquivos.

---

## ACHADO-44 — nada verifica se o XML fecha consigo mesmo · RESOLVIDO 02/09/2026

Medido em 02/09 (C1 do `TAREFA_PERCURSO_0209.md`), a partir do percurso do
Marcelo: dois ambientes com venda idêntica ao centavo e CFO diferente.

### A primeira versão desta entrada estava errada na causa

Ela concluía que `ORDER/TOTAL` variava com "um estado do projeto no Promob
que não viaja no arquivo", e levantava agregação de pedido ou frete por
volume. **Errado.** O Marcelo respondeu: *"essa diferença é culpa minha, no
passado eu pedi para alterar os arquivos para testar as comparações, e daí a
alteração foi forçada sobre o valor total do pedido."*

Fica registrado como estava, corrigido e não apagado — o percurso da
investigação vale mais que o acerto final, e a lição está justamente aqui.

### O que a medição provou, e continua valendo

O código do Orizon está certo dos dois lados:

| ambiente | (1) `order_total` no banco | (2) do `ambientes_json` | (3a) `ArquivoPE.valor_atualizado` | (3b) do arquivo |
|---|---|---|---|---|
| Banheiro Social | 953,40 | 953,40 | 1.029,67 | 1.029,67 |
| Suite Master | 15.882,09 | 15.882,09 | 16.675,84 | 16.675,84 |

Mesmos itens, mesmos `ref`, mesmas quantidades, `price_table` com razão
**1,000000 nos 94 itens**, receita de `<MARGINS>` idêntica atributo por
atributo — e a diferença inteira em `<ORDER UNIT TOTAL>`, com **`UNIT`
batendo e `TOTAL` não**, uniforme por ambiente (~8,0% e ~5,0%).

### O achado de verdade

**Um arquivo alterado à mão entrou, foi aceito, virou custo de fábrica, e
atravessou o ciclo inteiro até a AF2 — onde apareceu como Δ custo de
+76,27 e +793,75 que o sistema apresentou como fato.**

A edição era do próprio dono do sistema, para teste. O ponto é que **nada no
caminho notou**, e nada notaria se viesse de fora.

E o arquivo se denuncia sozinho: `TOTAL` deixou de ser coerente com `UNIT`,
com a quantidade e com a receita de margem que o **próprio arquivo** carrega.
Não era preciso comparar com nada externo — bastava conferir o arquivo
contra ele mesmo.

**A regra, decisão do Marcelo em 02/09:** *a soma dos valores dos itens, com
os devidos impostos conforme o próprio arquivo, tem que bater.* Consistência
interna, verificada **no upload** — o que estende o ACHADO-31 ("o XML só é
validado na emissão"): validar não é só conseguir parsear, é fechar a conta.

**Grupo:** 1.

### Medição antes de travar

Dos arquivos já em base: `pool_ambientes` reais (Homologação) — **0/12 não
fechavam**; `arquivo_pe` reais — **12/12 não fechavam** (os arquivos de
teste do próprio Marcelo, editados de propósito — a causa já conhecida
deste achado). Nenhuma linha existente foi tocada — a trava é só no
**upload de arquivo novo**, nunca retroativa.

### Conserto (02/09)

`consistencia_interna(amb)` (`integracoes/promob_grupos.py`) soma
`order_total`/`total` de todos os itens e compara contra o
`declarado_order`/`declarado_budget` que o próprio `TOTALPRICES` do arquivo
carrega. Recusa **dura** — decisão coberta pelo próprio texto do pedido
("um arquivo com TOTAL forçado é recusado") e sustentada pela medição (o
único jeito de furar hoje é editar o arquivo à mão, o mesmo gesto que
causou o C1). Dois pontos de entrada: `POST /projetos/<nome>/pool`
(contrato) e `POST /api/projetos/<nome>/pe/upload` (PE).

**Prova:** `tests/test_achado44_consistencia_xml.py` (4 — função pura,
fixture real de 16MB) + `tests/test_achado44_upload_e2e.py` (4 — HTTP, os
dois endpoints, aceita/recusa). Controle negativo confirmado.

---

## ACHADO-45 — nada impede que a venda seja igual ou menor que o custo de fábrica · RESOLVIDO 02/09/2026

Decisão do Marcelo em 02/09, saída do ACHADO-44: **valor de venda nunca pode
ser igual ou menor que o CFO.**

Hoje as duas grandezas entram juntas do mesmo XML — `budget_total` (venda) e
`order_total` (custo) — e ninguém as compara. Um ambiente pode ser importado,
orçado e contratado com margem zero ou negativa sem que nada avise.

É o mesmo princípio do portão do ACHADO-42, um andar abaixo: lá, a margem ia
a negativo por um percentual sem teto; aqui, ela já nasce negativa no
arquivo. As duas portas dão no mesmo lugar.

**Medido em 02/09:** zero violações em toda a base real — Homologação,
Integração e Produção. A trava pode ser dura sem travar trabalho existente.

### DECIDIDO 02/09 — a regra é uma só: markup > 1 dentro do XML

**A primeira redação desta decisão estava errada, e o erro era meu.** Eu
tinha escrito três condições, misturando duas coisas que não se misturam:
o valor de venda do **contrato** e os valores do **XML**. O Marcelo
corrigiu:

> *"O valor de venda que comparo no arquivo XML é o valor do próprio XML com
> markup, não é o valor de venda do contrato ser zero."*

**O XML traz dois valores por item:**

- `BUDGET/TOTAL` (`budget_total`) — o valor **com markup**, preço de venda;
- `ORDER/TOTAL` (`order_total`) — o **custo de fábrica**, já com IPI e com a
  receita de margem aplicada.

**A regra, inteira:** para cada item, `budget_total > order_total` — ou seja,
**o markup precisa ser > 1**. Arquivo em que isso não vale está errado, e a
recusa é dura, com **"arquivo XML com erro, verifique o promob"** e botão OK.

**Item com valor zero deixa de ser condição separada** — ele viola essa
mesma regra e é recusado por ela. Não precisa de cláusula própria.

**E o brinde não é caso disto.** Zerar um item é decisão comercial e
acontece **no contrato**, não no XML — e lá ela já tem guarda: o portão do
desconto composto (ACHADO-42). Se coube no limite de margem, foi uma decisão
autorizada; se não coube, o portão recusa. As duas coisas vivem em camadas
diferentes e nenhuma cobre a outra.

**A quarentena existente (`qa_selo='bloqueado'`) não é substituída** —
continua valendo para o que já cobria. O que entra é a recusa para markup ≤
1, que não é "qualidade duvidosa", é arquivo errado.

**Um ponto a confirmar na implementação:** a regra é **por item**, que é
como os dois valores existem no XML. Reportar também o agregado por
ambiente, para o caso de um item vir zerado da fábrica sem que o ambiente
perca margem — se isso acontecer na base real, o caso precisa de nome antes
de a recusa por item ficar de pé.

**Medido em 02/09:** zero violações de venda ≤ CFO em toda a base real —
Homologação, Integração e Produção. A trava pode ser dura sem travar
trabalho existente.

**Grupo:** 1.

### Conserto (02/09, DECIDIDO — regra corrigida): implementado no pool

Medição por ITEM antes de travar (Homologação, único ambiente com dados
reais): **0/795 itens em 12 ambientes violavam** `budget_total >
order_total`. Checado especificamente o caso que o Marcelo pediu pra
verificar antes de travar — item vindo zerado da fábrica sem o ambiente
perder margem — e **nenhum caso assim foi encontrado**; não havia motivo
para parar antes de travar.

`itens_com_markup_invalido(amb)` (`integracoes/promob_grupos.py`) percorre
todo item de todo grupo e recusa quando `budget_total ≤ order_total +
tolerância` (markup ≤ 1, empate incluído — a regra é "maior", nunca "maior
ou igual"). Recusa dura no `POST /projetos/<nome>/pool`: **"Arquivo XML com
erro, verifique o Promob."**, com botão OK.

A quarentena existente (`avaliar_qualidade_xml`/`qa_selo='bloqueado'`,
`mod_qualidade_xml.py`) não foi tocada — ela usa tolerância relativa
(0,01%) e limiar agregado (5% do valor) diferentes desta regra (tolerância
absoluta de centavos, por item), e continua cobrindo o que já cobria
(margem "quase zero" espalhada por muitos itens, sem nenhum item
isoladamente no prejuízo).

O upload de PE (`.../pe/upload`) já tinha a versão **agregada** por
ambiente (`venda_maior_que_cfo`, ver acima) — as duas travas convivem: PE
compara o ambiente inteiro; pool compara item por item, que é como os dois
valores realmente existem no arquivo.

**Prova:** `tests/test_achado45_venda_maior_que_cfo.py` — pura
(`itens_com_markup_invalido`, incl. empate e item zerado) + HTTP (recusa
com item ruim; a quarentena antiga continua funcionando com o MESMO
fixture de `test_qualidade_upload_e2e.py`, ajustado pra ficar acima do
novo hard-reject). Controle negativo confirmado.

**Grupo:** 1.

---

## ACHADO-46 — a transferência de responsabilidade procura por NOME de função, e o mecanismo certo já existe sem uso · RESOLVIDO 02/09/2026

Encontrado pelo Marcelo em 02/09: tentou transferir a responsabilidade do
projeto dentro do Ciclo e *"não encontrou ninguém de projeto executivo"*.

**A busca é por nome literal.** `mod_escopo.PAPEL_FUNCOES` (mod_escopo.py:21)
mapeia papel → uma tupla de **nomes** de função:

```python
PAPEL_FUNCOES = {
    "projeto_executivo": ("Projetista Executivo",),
    "medicao":           ("Medidor",),
    "montagem":          ("Montador", "Supervisor de Montagem"),
}
```

Quem não tiver uma função chamada exatamente "Projetista Executivo" não
existe para a transferência. Uma loja que chame o cargo de "Projetista",
"Detalhista" ou "Projetista Técnico" fica sem ninguém — **em silêncio**, que
é a parte ruim: não diz "nenhum funcionário tem essa função", diz que não
achou.

**E o mecanismo certo já está construído e sem uso.** `Funcao.
atribuicoes_json` guarda os papéis (`mod_escopo.PAPEIS`), e a própria
`funcao_operacional` a chama de **"fonte PREFERIDA quando preenchida —
elimina o acoplamento por nome"**. O comentário do código admite a dívida em
mod_escopo.py:18: *"Follow-up: campo `papel` na Tabela de Funções elimina o
acoplamento por nome."*

É o padrão (a) mais uma vez — **o mecanismo existe e o caminho real não
usa** — e desta vez está escrito no próprio arquivo.

**Quinto irmão da mesma lista:** `mod_assistencias.py:21` carrega uma cópia
de `PAPEL_FUNCOES["montagem"]`, **copiada e não importada**, com comentário
explicando a decisão. Duas listas com a mesma regra divergem no dia em que
alguém edita uma.

**Conserto:** a busca vai por papel, lendo `atribuicoes_json`; o nome vira
fallback declarado, não a fonte. E a tela de Funções passa a permitir marcar
os papéis — hoje o campo existe no banco e não é preenchido pela Config, que
é a razão de ele nunca ter substituído o nome.

**Grupo:** 1.

### Conserto (02/09)

`mod_escopo.funcao_compativel(papel, funcao_nome, papeis=None)` ganhou o
parâmetro `papeis` (mesmo padrão de `funcao_operacional`, já existente):
quando a função declara papéis (`Funcao.atribuicoes_json`), decide por
eles — o nome vira fallback só para função ainda não migrada. Único
chamador real (`_resolve_alvo`, `POST /projetos/<nome>/atribuicoes`)
atualizado para passar os papéis.

**Quinto irmão (`mod_assistencias.FUNCOES_ELEGIVEIS`):** medido — o
catálogo de nomes era **idêntico** a `PAPEL_FUNCOES["montagem"]` nos três
reais (nenhum funcionário com função customizada para montagem). **Decisão:
unificar por IMPORT**, não copiar — `FUNCOES_ELEGIVEIS =
mod_escopo.PAPEL_FUNCOES["montagem"]`, e a checagem de elegibilidade
(`mod_assistencias.funcao_elegivel_assistencia`) reaproveita
`funcao_compativel("montagem", ...)`, papel-primeiro-nome-fallback igual ao
resto. Duas listas nunca mais divergem por estarem fisicamente separadas.

**Tela de Funções:** ganhou os três checkboxes de papel (Config → Funções →
Editar). `Funcao.atribuicoes_json` deixa de ser campo morto —
`funcao_serialize`/`funcao_aplicar` (mod_cadastro.py) leem/gravam,
validando contra `mod_escopo.PAPEIS` (nunca um valor arbitrário do
request).

**Backfill:** `FUNCOES_PADRAO_PAPEIS` (database.py) mapeia as 4 funções
padrão que já correspondiam a um papel por nome (Projetista Executivo,
Medidor, Montador, Supervisor de Montagem) — `backfill_funcoes_todas_lojas`
já semeia as NOVAS com o papel; `backfill_papeis_funcoes_padrao` (novo,
roda no start) preenche as JÁ EXISTENTES, só quando `atribuicoes_json`
estiver vazio (nunca sobrescreve o que o cadastro já editou).

**Medição que ficou faltando no commit `ed761b6` — feita em 03/09, a
pedido do Marcelo, antes de ele começar o percurso:** quantos funcionários
ficariam sem papel nenhum. Só `FUNCOES_PADRAO_PAPEIS` tem 4 das 13
`FUNCOES_PADRAO` — as outras 9 (Consultor de Vendas, Gerente de Vendas,
Gerente Administrativo/Financeiro, Diretor, Assistente Logístico,
Conferente, Assistente Administrativo, Ajudante de Montagem, SAC) nascem
sem papel, por desenho ("é o cadastro que decide", não um gap do
backfill). Medido nas bases reais: Homologação, 2 de 5 funcionários (o
Consultor de Vendas e a Assistente Administrativo) — exatamente as duas
funções fora do mapa; Integração e Produção sem funcionário nenhum ainda.
Nenhuma surpresa — confirma que a lista de 4 está certa e não faltou
nenhuma correspondência óbvia.

**Aceite do achado:** funcionário cuja função se chama "Projetista" (não
"Projetista Executivo") mas declara o papel `projeto_executivo` aparece na
transferência — `tests/test_achado46_papel_por_atribuicoes_json.py`.

**Prova:** também `tests/test_achado47_papeis_funcao.py` (serialize/aplicar
de papéis, backfill seletivo, reaproveitamento do mod_assistencias).
Controle negativo confirmado nos dois arquivos.

---

## ACHADO-47 — uma pessoa só pode ter uma função, e a função é quem paga · RESOLVIDO 02/09/2026

Pedido do Marcelo em 02/09: *"uma mesma pessoa deve poder acumular mais de
uma função (por exemplo o Projeto Executivo e a Medição frequentemente são
feitos pela mesma pessoa)"*.

`Funcionario.funcao_id` é uma FK única (database.py). Uma função por
pessoa, e é por isso que a busca do ACHADO-46 não acha quem faz os dois.

### Acumular FUNÇÃO é a forma errada, e o próprio esquema diz por quê

`Funcao` carrega `salario_fixo`, `beneficios_json`, `comissao_json`,
`usa_comissao_vendas`, `comissao_fixa`, `remuneracao_padrao`. **Ela é o
registro de quanto a pessoa ganha.** Duas funções na mesma pessoa criam uma
pergunta sem resposta: qual salário vale? Qual comissão? A folha lê o quê?

A separação certa está a um passo de existir:

- **Função — o que a pessoa É e quanto ganha.** Uma só. Continua como está.
- **Papéis — o que a pessoa FAZ.** Vários. Já existem em
  `Funcao.atribuicoes_json`, já são a fonte preferida do código, e não são
  preenchidos por tela nenhuma.

Quem faz Projeto Executivo **e** Medição tem **uma** função, cujos papéis
declaram os dois. Nada de migration, nada de tabela de ligação, nenhuma
ambiguidade de folha. E se a remuneração for genuinamente diferente, então
são duas pessoas-função diferentes de verdade — e aí a resposta é outra
função, não uma segunda.

### DECIDIDO 02/09 — sem papel avulso; o acúmulo se paga por adicional

Decisão do Marcelo: **não há papel avulso no funcionário.** Os papéis vêm da
função, e pronto — a mudança do ACHADO-46/47 acontece sem tocar no banco
nessa parte.

O que o acúmulo gera é **remuneração**, e ela vai no cadastro do
funcionário, num bloco **Adicional**:

- **adicional fixo** — valor mensal;
- **adicional de comissão** — percentual, com **base declarada**. Padrão:
  **Valor Líquido de Venda**. Outras bases ficam para depois, mas o campo
  nasce dizendo qual base usa, em vez de assumir.

O desenho fecha a ambiguidade que o acúmulo de funções criava: **a função
paga a base, o adicional paga o acúmulo**, e a folha nunca precisa escolher
entre dois salários.

**Dois pontos que este desenho deixa em aberto, e que precisam de resposta
antes de virar código:**

**1 · O adicional não diz por quê — RESOLVIDO em 02/09.** O Marcelo
acrescentou um **campo de observações** ao bloco Adicional, para o motivo.
Um só campo, servindo aos dois adicionais. O valor deixa de ser órfão.

**2 · O adicional de comissão é custo novo — RESPONDIDO em 02/09.**

Decisão do Marcelo, e ela dispensa rubrica nova:

> O adicional de comissão **só pode existir para funcionário cuja função
> primária já seja comissionada**. Ele **soma sobre a comissão anterior** e
> **provisiona junto** — o ciclo contábil fica preservado.

É a resposta mais limpa possível para a pergunta que o ACHADO-33 nos ensinou
a fazer: em vez de criar uma rota, o adicional **pega carona numa rota que
já funciona**. Sem rubrica nova, sem alimentador novo, sem veredito novo, e
a Conciliação Final o enxerga porque ele já está dentro do que ela olha.

**A consequência é uma guarda, e ela vale no servidor:** função primária não
comissionada ⇒ o campo de adicional de comissão não existe para aquele
funcionário. Guarda só na tela é decoração — foi o achado de UAT de 10/08.

**E o campo de observação é UM só** para os dois adicionais, fixo e
comissão (decisão do Marcelo no mesmo momento) — o que responde o ponto 1
acima.

**E uma nota de aritmética:** a base padrão é o `Val_Liq`, a mesma grandeza
que o portão do ACHADO-42 protege. Com o portão, ela não vai mais a
negativo — o que é bom, porque comissão sobre base negativa seria comissão
negativa. Vale registrar a dependência: **o adicional de comissão só é
seguro porque o portão existe.**

**E a base de funções que ele pediu já existe:** `FUNCOES_PADRAO`
(database.py:2186) semeia treze — Consultor de Vendas, Gerente de Vendas,
Gerente Administrativo/Financeiro, Diretor, Assistente Logístico,
Conferente, Supervisor de Montagem, Assistente Administrativo, Projetista
Executivo, Medidor, Montador, Ajudante de Montagem, SAC. O que falta não é a
base: é **cada uma declarar seus papéis**.

### Conserto (02/09) — bloco Adicional no cadastro do funcionário

Quatro colunas novas em `Funcionario` (migration Alembic
`82275b998a4a`, `revises f47f22de46a7`): `adicional_fixo`,
`adicional_comissao_pct`, `adicional_comissao_base` (só
`'val_liq_venda'` suportada — "outras bases ficam para depois"),
`adicional_obs` (um só campo, os dois adicionais).

**Guarda no servidor** (`mod_cadastro.func_aplicar`, não só na tela):
`adicional_comissao_pct` só é aceito quando `mod_folha.funcao_e_comissionada`
(alias de `mod_cadastro.funcao_e_comissionada`, ver nota de arquitetura
abaixo) é `True` para a função primária do funcionário — senão, `ValueError`
→ 400. `adicional_fixo` é livre (não depende de a função ser comissionada).

**Provisiona junto, sem alimentador novo:**
- Fixo: soma dentro de `parte_fixa` em `mod_folha.calcular_folha` — mesmo
  campo que já vira lançamento em 5.3.0X, sem tocar nada além do valor.
- Comissão: soma **no MESMO item** de `ComissaoFolha` que o alimentador
  de comissão por papel já cria (`mod_comissao.preparar_comissao_etapa`) —
  `pct_efetivo = pct_da_função + adicional_comissao_pct`, um item só, uma
  base só (Val_Liq do ambiente, a mesma da função). A guarda "função já
  comissionada" é a própria condição `pct <= 0` que já existia ali — quem
  chega a somar o adicional já passou por ela.
- O caminho de VENDA do Consultor (`mod_folha._upsert_itens_venda`, fonte
  única desde 2026-08-12, provisão constituída na assinatura do contrato)
  **não foi tocado** — fora de escopo desta rodada (acumular Vendas com
  outro papel não é o caso do achado, que é Projeto Executivo + Medição;
  mexer na provisão de venda é risco desproporcional ao pedido).

**Achado de arquitetura ao implementar:** `funcao_e_comissionada` não podia
morar em `mod_folha.py` — "folha" DEPENDE de "cadastro" (`modulos.py`), não
o contrário, e a função só olha campos de `Funcao` (domínio cadastro). Mora
em `mod_cadastro.py`; `mod_folha.py` reexporta pra não quebrar quem já
chamava `mod_folha.funcao_e_comissionada`. Pego por
`test_arquitetura_modulos.py::test_dominios_so_importam_o_que_declaram` —
o teste fez exatamente o que devia.

**Tela:** Config → Funcionários → Editar ganhou a seção "Adicional (acúmulo
de papéis)" — fixo, comissão (rótulo já avisa a condição), observações. A
base declarada não tem seletor ainda (só um valor existe).

**Prova:** `tests/test_achado47_adicional_funcionario.py` (9 — pura,
`func_aplicar`/`func_serialize`, HTTP fim a fim nos dois sentidos, e o
aceite central: `preparar_comissao_etapa` soma o adicional no MESMO item,
nunca cria um segundo). Controle negativo confirmado.

**Grupo:** 1.

---

## ACHADO-48 — o livro é datado em UTC e a empresa vive em UTC−3 · RESOLVIDO 03/09/2026 (F2-14)

Encontrado pela Vera em 02/09, investigando três testes que falhavam antes
de cortar a tag. **O diagnóstico dela está certo e é maior do que o sintoma
que o revelou.**

### O sintoma

Três aceites do ACHADO-35 falhavam. `efetivado_no_dia` monta a janela do dia
com `date.today()` — **hora local** —, e `lancar()` carimba o lançamento com
`datetime.utcnow()` quando `data` não é passada (mod_contabil.py:1113). Em
UTC−3, das ~21h em diante, o lançamento nasce "amanhã" em UTC, cai fora da
janela de "hoje" local, e **a guarda contra efetivação duplicada fica
inerte**. Bisect até `cba0159` (onde a guarda nasceu): falha lá também. Não
é regressão; é o defeito desde o primeiro dia, visível só em certa hora.

### O achado

`lancar()` é a porta única do razão, e **11 dos 27 chamadores não passam
`data`** — esses lançamentos ficam com `utcnow()`. `registrar_evento`, que é
por onde a maior parte dos eventos de negócio entra, tem `data=None` por
padrão e repassa.

Ou seja: **a data de competência de boa parte do razão é a data UTC.** Uma
venda fechada às 21h30 de 30 de setembro em Brasília é escriturada em **1º de
outubro**. Ela cai no mês seguinte, na DRE seguinte, no `PeriodoContabil`
seguinte. Loja de móveis planejados fecha às 20h, 21h, 22h — a janela errada
é justamente o fim do expediente.

### E o comportamento depende da máquina, o que é pior

O sistema **não declara fuso nenhum**. `date.today()` é do relógio do
processo; `utcnow()` é UTC. Então:

- Em servidor com TZ local (a bancada da Vera), os dois discordam e a
  **guarda quebra** — foi assim que apareceu.
- Em servidor com TZ = UTC (o padrão de VPS), os dois concordam e a guarda
  funciona — mas **a data continua errada em relação a Brasília**, e ninguém
  percebe.

A bancada é mais honesta que a produção. O defeito se esconde exatamente
onde importa.

**Medição que falta:** `timedatectl` nos três servidores. Ela diz qual das
duas faces está de pé em cada um.

### O conserto, e por que agora

Um número só manda — a mesma regra do deságio e do markup de ajuste. **O
fuso é declarado em um lugar**, e tanto o carimbo de `lancar()` quanto todo
`date.today()` de regra de negócio saem dessa fonte única. O relógio da
máquina deixa de decidir competência.

### DECIDIDO 02/09 — o fuso é configuração, com Brasília por padrão

Decisão do Marcelo: **campo de fuso horário no painel de configuração**,
com **America/Sao_Paulo como padrão**. Quando não estiver ajustado, vale
Brasília. Ajusta-se no futuro se algum dia houver loja em outro fuso — o
Brasil tem quatro.

**Onde mora, sem migration:** `Loja.config_financeira_json` já existe e já é
lida por `_cfg_financeira_loja`. Uma chave `fuso_horario` ali resolve, sem
coluna nova.

**A cadeia de resolução, e o ponto que decide o achado:**

```
config da loja → config da rede → America/Sao_Paulo
```

**Nunca o relógio da máquina.** Configuração ausente cai em Brasília, não no
`TZ` do processo. Se o fallback for a máquina, o defeito volta inteiro pela
porta do default — que é exatamente como ele nasceu.

O livro tem dono (`owner_tipo`/`owner_id`), então o fuso é resolvido pelo
dono do livro: loja quando é loja, rede quando é rede.

**O momento é este e não outro:** produção está sem dado real de cliente.
Consertar o relógio depois significa migrar um razão com datas de significado
misturado — algumas UTC, algumas locais, sem marca que as distinga. Hoje
custa uma função; depois custa uma migração de livro.

**Grupo:** 1.

### Medição (02/09, antes do conserto)

`timedatectl` inverteu a suposição do próprio achado:
- Integração + Homologação (mesma máquina, 167.88.33.121): `Etc/UTC` — aqui a
  guarda "funciona" (os dois relógios concordam), mas a competência grava
  errada em relação a Brasília, sem ninguém ver.
- Produção (179.197.77.9): `America/Sao_Paulo` (-03) — aqui é onde o sintoma
  apareceria visível, como na bancada.

Lançamentos na janela 00h-03h UTC (candidatos a ter nascido "amanhã" para
Brasília): Homologação, 71 lançamentos no total (31/08 a 02/09), todos entre
12h-21h UTC (9h-18h Brasília, expediente comercial) — **zero** na janela.
Integração e Produção: bancos vazios (sem dado real de cliente). Nenhum
lançamento com data deslocada em nenhuma base real — o defeito é
estrutural/latente, ainda sem vítima nos dados. Confirma que este é o
momento certo.

### Conserto (02/09)

Fonte única em `mod_contabil.py`: `resolver_fuso_owner(db, owner_tipo,
owner_id)` lê `Loja.config_financeira_json['fuso_horario']` (cadeia loja →
rede da loja → `America/Sao_Paulo`; owner "rede" pula direto pro degrau da
rede); `Rede` não tem `config_financeira_json` hoje, então o degrau existe
na cadeia mas não tem o que ler ainda — cai no default, documentado no
código, não é bug. `agora_no_fuso`/`hoje_no_fuso` usam `zoneinfo` (stdlib,
sem dependência nova) para dar a hora de parede do fuso, **sempre
independente do relógio/TZ do processo** — é essa independência que fecha o
achado. `data_emissao_iso_no_fuso` substitui o hack de NF-e/NFS-e
(`utcnow() - timedelta(hours=3)`, "-03:00" fixo).

`lancar()` agora carimba com `agora_no_fuso`, nunca `utcnow()`. Sem coluna
nova, sem migration — `fuso_horario` é só mais uma chave no JSON que já
existia. Campo novo em Config → Agenda e Capacidade (`static/index.html`,
select com os quatro fusos do Brasil, default America/Sao_Paulo).

**Os irmãos** (todo `date.today()`/`datetime.utcnow()` em caminho de regra
de negócio, revisados um a um):

Mudam (~32 sites, todos passaram a usar `agora_no_fuso`/`hoje_no_fuso`/
`data_emissao_iso_no_fuso`, porque alimentam uma decisão de competência —
mês da DRE, guarda de duplicidade, vencido/atraso, âncora de cronograma,
emissão fiscal): o carimbo de `lancar()`; `alertas_contas_escape`;
`sugestoes_despesas_mes_anterior` (e os dois `_intervalo_mes_*` que ela
alimenta); a guarda `efetivado_no_dia`/`efetivar-provisao` (ACHADO-35, o
alvo central); `reclassificar_recebivel_duvidoso`; confirmação de
recebível; três comparações de "vencido" (fluxo de caixa, reconciliação de
provisões, financeiro/recebíveis); `/financeiro/indicadores` e
`/estrategico/indicadores`; todo carimbo de `CicloEtapa.iniciado_em`/
`concluido_em` (etapas "4","7","9","10","11d","15","21", PATCH genérico de
ciclo, `_set_etapa_status`) — cascade porque `concluido_em` alimenta
`mod_comissao.preparar_comissao_etapa`'s `competencia`; `_registrar_
assinatura_contrato` (etapa7 + âncora do cronograma); auto-complete de
ETAPAS_PRE e etapas 1/2 na criação do projeto; briefing (conclusão +
`data_atendimento` ×2); `_marcar_etapa_cliente`; `_enriquecer_projetos_
com_atraso` (com cache por loja, porque uma listagem de rede cruza lojas de
fusos potencialmente diferentes); validação de "não agendar no passado";
`materializar(...,"check")` (×2) e `_materializar_recebiveis_venda_seguro`;
`proj.data_inicio`; três `data_emissao` de NF-e/NFS-e; `mod_folha.pagar`
(`pago_em`); `mod_assistencias.criar_caso`/`realizar_caso`.

Ficam em `utcnow()` (~40 sites — timestamp de auditoria/log, "quando isso
aconteceu", não competência): `assinado_em`, `clicksign_enviado_em` (×3),
`ts=...isoformat()` de hash (×3), `gerado_em` (×4: contrato, aditivo,
aprovação, solicitação), `atualizado_em` (×4), `resolvido_em` (chat),
`carregado_em` (upload PE), `medicao_em`/`excecao_em`,
`transferencia_solicitada_em`, `travada_em`, `unico = ...strftime(...)` (×6,
nome de arquivo), janela de carência do ClickSign, ref "TESTE-...".

**Prova:** `tests/test_achado48_fuso_horario.py` (5) — cadeia loja → rede →
default; `agora_no_fuso` independe do TZ do processo (verificado); `lancar`
carimba com `agora_no_fuso`, não `utcnow()` (fuso deliberadamente extremo,
`Pacific/Kiritimati` UTC+14, pra tornar o desvio sempre detectável); os três
aceites do ACHADO-35 passam com o processo em UTC e em America/Sao_Paulo.

**Controle negativo:** reapontar `lancar()` para `utcnow()` faz o teste
determinístico (`Pacific/Kiritimati`) falhar — confirmado. O controle via
subprocess dos aceites do ACHADO-35 sob reversão é dependente da janela
real de relógio (só falha durante o descompasso local/UTC de meia-noite,
que se move com a hora real) — não é um controle negativo confiável por si
só; o determinístico é a evidência primária.

**Grupo:** 1.


## ACHADO-49 — o Remover da etapa 12 herdou a autoridade do PE, e a tela cala quando a credencial não vem · ABERTO 04/09/2026

Achado pelo Marcelo no percurso do `v2026.09.04-beta1` em Homologação
(04/09) — a primeira coisa que ele clicou: *"o botão remover não
funcionou"*. É defeito do que o F2-15 entregou 24 horas antes.

**Onde.** O card que a tela mostra como etapa 8 ("Conferência e Implantação
do Pedido") é, por dentro, o código `12` — `_renderCardImplantacao` em
`static/index.html`. O botão existe, está renderizado e chama
`removerDocCiclo('12', ...)`. Não é botão solto.

**Causa 1 — a autoridade não espelha o upload.** O ACHADO-30 fixou a regra
no próprio comentário da rota: *"a autoridade ESPELHA a de subir naquela
etapa, em vez de inventar uma terceira regra de quem manda no documento"* —
etapa 15 pela capacidade fiscal da sessão, subfases do PE por login+senha de
`executar_pe`. Mas a rota tem só DOIS ramos (`if codigo == "15"` / `else`), e
a etapa 12 **não é subfase do PE**: caiu no `else` e herdou a exigência do PE.
Medido nas duas pontas:

| ação na etapa 12 | credencial exigida |
|---|---|
| subir o pedido (`POST /ciclo/12/pedido-xml`) | nenhuma — a tela manda só o arquivo |
| remover (`POST /ciclo/12/documentos/<id>/remover`) | login+senha de `executar_pe` |

Na etapa 12 a remoção é ESTRITAMENTE mais dura que o upload: a terceira regra
que a regra proibia. O `else` foi escrito pensando nas subfases e não
enumerou quem mais cairia nele.

**Causa 2 — falha silenciosa.** Em `removerDocCiclo`, quando
`pedirCredenciaisGerente` devolve vazio (cancelado, ou quem está logado não
tem a capacidade), a função faz `return` **sem nenhuma mensagem**. É o padrão
"estado antes da credencial" do ACHADO-38/B3, que o projeto já consertou
quatro vezes em telas diferentes — e que voltou pela porta nova. Do lado do
usuário: o botão não faz nada, sem explicação.

**Medido em 04/09 (F2-20), antes de consertar — os irmãos do `else`.** Os únicos quatro pontos
que criam `CicloDocumento` são: `/ciclo/<codigo>/documento` (subfases do PE — 11a/11b/11c/11e,
`SUBFASES_PE`, autoridade `executar_pe`, mesma do `else`), `/ciclo/<codigo>/pedido-xml` (só
aceita `codigo="12"` — `mod_ciclo.ETAPAS_OPERACIONAIS["13"]`/`["14"]` não têm `tipo_doc`, então
`tipo_doc_operacional` devolve `None` pra eles e a rota recusa antes de chegar a criar
documento), `/ciclo/15/nfe-fabrica` (etapa 15, tem ramo próprio no `remover`) e `/ciclo/<codigo>
/revisao` (só 11b/11c, as únicas com `revisavel: True`). **Conclusão: nenhuma OUTRA etapa além
da 12 cai no `else` sem ser subfase do PE** — 13 e 14 nunca geram documento, então nunca chegam
no `remover` de verdade (404 antes).

**Achado adjacente, mesma família, NÃO a mesma causa — registrado aqui, não vira item próprio
do conserto:** o upload de `/ciclo/<codigo>/revisao` (documento `pe_relatorio_complementar`,
11b/11c) exige `revisar_pe` (Gerente de Vendas, Gerente Adm/Financeiro, Diretor) — uma
capacidade DIFERENTE de `executar_pe` (Projetista Executivo, Conferente, Gerente, Diretor), que
é o que o `remover` sempre exige pra qualquer código fora da 15. Quem tem só `executar_pe` e
não `revisar_pe` consegue remover um relatório complementar que não teria permissão de subir. Não
é a mesma causa do ACHADO-49 (aqui a etapa É subfase do PE de verdade) — é uma segunda
dissonância upload×remoção, dentro da mesma etapa. Fica registrado; não decidido se conserta
nesta rodada.

---

## ACHADO-50 — nota em processamento é reportada como FALHA · ABERTO 04/09/2026

Achado pelo Marcelo no mesmo percurso do `v2026.09.04-beta1` em Homologação:
emitiu a NF-e da loja e a tela devolveu *"Falha na emissão: A nota fiscal
ainda está em processamento"*.

**A cadeia, com linha citada:**
- `integracoes/emissor_fiscal.py:50` mapeia o status `"processando_
  autorizacao"` da Focus para `StatusNota.PROCESSANDO`.
- `fiscal/nfe_emissao.py:102-103` — resultado `PROCESSANDO` chama
  `aguardar(ref)` (`focus_client.aguardar_processamento`,
  `integracoes/focus_client.py:90`), que polla a Focus por `timeout=60`,
  `intervalo=3`.
- Esgotado o tempo sem a SEFAZ resolver, o resultado **continua**
  `PROCESSANDO`, e a rota devolve `"Falha na emissão: A nota fiscal ainda
  está em processamento"` — a mensagem que o Marcelo viu.
- O prefixo `"Falha na emissão: "` é do `except Exception` genérico — este
  caminho **não é uma exceção**, é um retorno normal com `status=
  PROCESSANDO`, e por isso **não passa** pelo `except FocusError` que o
  F2-17 (item 3 do bloco fiscal) acabou de acrescentar. É outro ramo, não o
  mesmo defeito do item 3.
- `static/index.html:23256` — o botão "Consultar" (que resolveria
  exatamente este caso, perguntando à Focus se já saiu) só é desenhado numa
  linha de emissão **já registrada** (com `DocumentoFiscal` existente); a
  resposta de "Falha" não cria essa linha, então o botão nunca aparece pra
  quem mais precisa dele.

**O defeito:** pendente não é falha. A nota foi aceita pela SEFAZ e está na
fila — muito provavelmente autorizada segundos ou minutos depois, fora da
janela de 60s que o processo HTTP consegue esperar. A mensagem diz ao
usuário que a emissão falhou; o que aconteceu foi só "ainda não terminou".
O usuário conclui, razoavelmente, que precisa emitir de novo — e é aqui que
o ACHADO-51/1a se tocam: a Focus deduplica por `ref`, então reemitir não
duplica a nota na SEFAZ, mas o sintoma (usuário achando que precisa agir de
novo sobre algo que já está resolvendo sozinho) é o problema real.

---

## ACHADO-51 — nada impede carregar a mesma NF-e da fábrica duas vezes · ABERTO 04/09/2026

Observado pelo Marcelo na etapa 15, em Homologação: `NFe-163298.xml`
aparece **duas vezes** na lista de documentos carregados, cada linha com
seu próprio campo de markup e seu próprio botão de emitir — dois caminhos
de emissão abertos para o mesmo documento fiscal.

**Medido em 04/09 (F2-20):** `POST /ciclo/15/nfe-fabrica` (`main.py:14958`)
não faz nenhuma deduplicação — confere a estrutura do XML (ACHADO-31,
`mod_nfe.problemas_de_upload`) e cria um `CicloDocumento` novo
incondicionalmente, sempre. Não há leitura de chave de acesso em lugar
nenhum do upload hoje (`fiscal/mod_nfe.py` não extrai `chNFe`/`Id` do
`infNFe`).

**Contagem real, três ambientes** (script pontual de leitura, não
commitado — extrai a chave do atributo `Id="NFe..."` de `infNFe` de cada
arquivo vivo e agrupa por projeto):

| ambiente | documentos `nfe_fabrica_xml` vivos | duplicata dentro do mesmo projeto | mesma chave em projetos diferentes |
|---|---|---|---|
| Integração | 0 | — | — |
| Homologação | 10 | **1** — `Projeto_3`, chave `NFe4315...2981002365275`, dois documentos (`NFe-163298.xml` × 2) | **2** casos — a mesma chave aparece em `Projeto_3`+`Teste_1`+`Teste_2` (uma) e em `Projeto_3`+`Teste_1` (outra) |
| Produção | 0 (base sem essa migration ainda — `ciclo_documentos` de Produção não tem `removido_em`; medido sem esse filtro, mesmo resultado: zero) | — | — |

A duplicata que o Marcelo viu é exatamente a medida (`Projeto_3`). O
segundo achado da medição — mesma chave em projetos diferentes — é dado
real, não hipótese: acontece hoje em Homologação (projetos de teste
reaproveitando a mesma amostra de XML). **Fica em aberto, decisão do
Marcelo:** mesma chave em projeto DIFERENTE é erro (nota da fábrica não
pode servir dois projetos) ou caso legítimo (reimportação intencional,
mesma compra ressarcida em dois pedidos)? A trava desta rodada (F2-20) é
só DENTRO do mesmo projeto/etapa — não decide esse caso mais amplo.

**Decidido pelo Marcelo em 04/09: bloquear** (não só avisar) uma segunda
carga da mesma NF-e, dentro do mesmo projeto/etapa.

