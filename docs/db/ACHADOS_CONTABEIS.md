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

## ACHADO-12 — Aditivo contratual: a receita constituída nunca é faturada

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

## ACHADO-13 — `faturar_segmento` pode duplicar receita se chamado 2x para o mesmo segmento (não confirmado em produção)

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

## ACHADO-15 — `real` e `competencia_estimada` divergem quando o projeto fecha sem efetivação

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

---

## ACHADO-14 — "Total Flex" virou "Parcelamento Loja" e o rename não chegou · RESOLVIDO 29/08/2026

Produto renomeado; código e nome da conta 2.1.05 no banco não acompanharam.
Mesmo padrão de 1.1.09/2.1.09: rename em código não alcança base existente.

Resolvido: arquivos renomeados, migration 95c7e64afc6a para o nome da conta.
Dívida aceita: o identificador `total_flex` continua no wire do frontend, com
alias. Sai quando alguém tocar naquela tela.

---

## ACHADO-16 — Provisão cancelada em silêncio na Conciliação Final torna a margem fictícia

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

### A decidir
O cancelamento deve exigir **confirmação explícita** de quem fecha o projeto
("declaro que este custo não ocorreu"), ou deve **recusar o fechamento** até
a rubrica ser efetivada ou baixada com justificativa?

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

## ACHADO-18 — NF-e sem `valor_total` não lança nada, em silêncio · MEDIDO 29/08/2026: NÃO ALCANÇÁVEL HOJE

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
