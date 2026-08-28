# Achados contábeis — auditoria das pontas abertas do plano de contas

Consolidado da auditoria (docs/db/TAREFA_AUDITORIA_CONTABIL.md), a partir do
mapa em docs/db/AUDITORIA_MAPA_CONTABIL.md. Numeração estável — um achado
novo entra com o próximo número, nunca reordena os existentes. Ordenado por
consequência no número final, não por facilidade de conserto.

---

## ACHADO-01 — Custo Financeiro nunca reconcilia com o recebimento líquido

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

## ACHADO-02 — Ramo "loja": a Receita Financeira pode ser reconhecida duas vezes (achado do teste de ciclo completo, Parte 4)

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

## ACHADO-03 — Constituição do Custo Financeiro diverge por ramo entre dois pontos do código

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

## ACHADO-08 — Contas do PLANO_PADRAO nunca tocadas por nenhum evento

**O que acontece:** 1.1.03 (Estoques), 1.1.04 (Adiantamentos a
Fornecedores), 1.2.1.01-04 (Imobilizado), 1.2.2 (Intangível), 2.1.02
(Obrigações Trabalhistas), 2.2.01 (Financiamentos de Longo Prazo), 4.2.02
(Prestação de Serviços para Terceiros), 4.4.01 (Receita de Aluguéis) e a
maior parte das famílias 5.2/5.3/5.4/5.5.01 nunca aparecem como D ou C de
evento nenhum nem de site direto de `lancar`.

**Evidência:** cross-referência completa em
docs/db/AUDITORIA_MAPA_CONTABIL.md, Parte 2, categoria 4.

**Consequências no número final:** nenhuma esperada — são, com alta
confiança, contas de lançamento manual (`despesa_avulsa`/
`/api/financeiro/lancamentos`) para módulos que ainda não têm motor próprio
(estoque, imobilizado, folha trabalhista formal). Não é bug; é
funcionalidade não implementada ou fora do escopo automático.

**O que bloqueia:** nada.

**Decisão necessária:** nenhuma — item informativo, listado para constar
no mapa. Se algum desses módulos estiver no roadmap, vale conferir contra
esta lista antes de desenhar o motor novo.

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
