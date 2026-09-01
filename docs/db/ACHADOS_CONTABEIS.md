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

## ACHADO-30 — documentos de fase não têm como ser trocados, nem ficam imutáveis depois

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

---

## ACHADO-31 — o XML da fábrica só é validado na emissão, dois passos depois do upload

Encontrado pelo Marcelo em 31/08, ao não conseguir concluir a etapa 15.

**O upload aceita qualquer arquivo.** `POST /ciclo/15/nfe-fabrica`
(main.py:14680) só verifica que veio um arquivo — a mensagem
*"Anexe o XML da NF-e da fábrica"* dispara com campo vazio, não com conteúdo
errado.

**Quem rejeita é a emissão**, quando `mod_nfe.preview(xml_bytes, markup)`
não acha o `infNFe`. O erro aparece dois passos depois da causa, e não diz
que o problema é o arquivo.

**Conserto:** validar no upload. O arquivo entra ou não entra ali.

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

**Decisão necessária (desenho, do dono do negócio):** quem manda no valor
dos itens da NF-e de saída — o **markup de ajuste** digitado, ou o **rateio
pelo `Val_Cont`**? Os dois não podem mandar. Se for o markup, o rateio sai;
se for o rateio, o campo é informativo e a tela precisa dizer isso. Em
qualquer dos casos, rotular.

**Grupo:** 2.
