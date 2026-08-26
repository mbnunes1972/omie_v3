# Centro de Custo & Natureza — edição, reclassificação e retroatividade (design, 2026-08-25)

Continuação da frente de Centro de Custo/Natureza implementada em 2026-08-08 (sem spec própria na
época; a proposta viveu num Artifact). Origem: pedido do Marcelo de **substituir o botão "Renomear"
por "Editar"**, permitindo reclassificar Centro de Custo e Natureza de cada conta — o que equivale a
abrir a porta para reclassificar o estado atual.

Esta spec separa as frentes, registra o que foi verificado no código em 2026-08-25 e consolida as
decisões tomadas pelo Marcelo na mesma data (marcadas como **DECIDIDO** em cada frente). O que
continua em aberto está listado no fim.

---

## 0. O que foi verificado (fatos, não suposições)

| Fato | Onde |
|---|---|
| A classificação **já está gravada no banco**, em todos os owners, desde o boot | `main.py:18467` (`migrar_classificacao_grupo5_v1`), `:18470` (v2), `:18473` (v3) |
| O mapa da classificação vive em código | `mod_contabil.py:735` `CLASSIFICACAO_GRUPO5_V1` |
| Os "2 itens em revisão" foram resolvidos por migração, não por aprovação | `mod_contabil.py:784` — Brindes (5.3.12) → **Variável**; Ajuste de Provisões (5.6.10) → **Variável** + Custos Distribuídos (4.5) |
| Combustível (5.2.06) foi alterado depois disso | `mod_contabil.py:813` — de Variável para **Fixo** |
| O endpoint de classificação em lote existe e não é chamado por fluxo automático | `main.py:9840` → `mod_contabil.py:700` `classificar_contas_lote` |
| A etiqueta vive na CONTA, não no lançamento; relatórios leem no momento da consulta | `mod_contabil.py:2352` `relatorio_centro_custo`, `:2390` `relatorio_natureza` |
| `editar_conta` hoje só aceita `nome` e `ordem` | `mod_contabil.py:523` |
| Natureza do plano de contas **não** alimenta a margem do projeto | `mod_provisoes.cust_var_marg_cont` calcula Cust_Var/Marg_Cont das rubricas de provisão, sem ler `Conta.natureza_custo` |
| Cobertura de teste existente | `tests/test_centro_custo_natureza.py`, `tests/test_centro_custo_relatorios.py` |

**Consequência:** a página de proposta que circulou ("nada foi gravado ainda", Brindes Fixo, Ajuste
de Provisões Fixo, Combustível Variável) está desatualizada em quatro pontos e **não pode ser usada
como base de aprovação**.

---

## Frente 0 — Verdade do estado atual  ·  pré-requisito de todas as outras

**Por quê:** decidir sobre uma reclassificação exige saber de que ponto se parte. Hoje o retrato
circulante diverge do banco.

**O que fazer:** gerar o retrato a partir do banco, não do mapa em código — as duas coisas podem já
ter divergido em qualquer ambiente onde alguém tenha editado. Uma tela ou um export simples com:
código, nome, centro de custo, natureza, e uma coluna marcando divergência em relação a
`CLASSIFICACAO_GRUPO5_V1`.

**Entregável:** retrato revisável por Marcelo e Juliana, com data e ambiente.

**Dependência:** nenhuma. É o primeiro passo.

---

## Frente 1 — Blindar a edição contra as migrações  ·  BLOQUEANTE do botão Editar

**Por quê:** as migrações v2 e v3 identificam "ainda no default antigo" **pelo valor**, não pela
origem. O v3 faz, em português: *se 5.2.06 estiver `variavel`, grave `fixo`*.

Se o botão Editar for liberado antes disso, uma reclassificação manual legítima (alguém decidir que
Combustível é Variável, ou que Brindes é Fixo) **será revertida no próximo restart do servidor, em
silêncio, sem log e sem aviso ao usuário**. A pessoa reclassifica, confere na tela, e dias depois
encontra o valor anterior de volta.

**DECIDIDO (Marcelo, 2026-08-25): opção (a) — aposentar v2 e v3, com atualização do mapa.**

**Duas saídas:**

- **(a) Aposentar as migrações v2 e v3.** Elas já rodaram em todos os ambientes; sendo idempotentes
  e tendo cumprido o papel, podem sair do boot. Simples, imediato, e remove a armadilha na raiz.
  Risco: um ambiente novo (banco zerado) passa a nascer com o default do v1, sem as correções — a
  menos que o mapa `CLASSIFICACAO_GRUPO5_V1` seja atualizado com os valores finais na mesma
  mudança. **Se escolhida, atualizar o mapa é parte da tarefa, não opcional.**
- **(b) Marcar a origem da classificação.** Coluna nova (`classificacao_manual` ou
  `classificado_em`/`classificado_por`) e as migrações passam a só tocar em quem nunca foi editado
  manualmente. Mais caro (migração de schema), porém protege qualquer migração futura, não só a v2/v3.

**Teste obrigatório em qualquer das duas:** reclassificar manualmente uma conta para o valor que a
migração considera "default antigo", rodar a rotina de boot, e verificar que a escolha manual
sobreviveu.

---

## Frente 2 — Regime de retroatividade  ·  decisão de negócio, não técnica

**Por quê:** `relatorio_natureza` e `relatorio_centro_custo` leem a etiqueta **da conta** no momento
da consulta e somam os lançamentos do período. Não há vigência nem histórico. Reclassificar uma
conta hoje muda **todos os relatórios de todos os períodos passados**, inclusive meses fechados.

Um relatório de julho impresso hoje deixa de bater com o mesmo relatório impresso na semana que vem,
sem que nada explique a diferença.

**DECIDIDO (Marcelo, 2026-08-25): congelar no fechamento.**

**O marco de fechamento JÁ EXISTE** — verificado em 2026-08-25: `PeriodoContabil`
(`database.py:1168`, com `inicio`, `fim`, `status='fechado'`, `dados_json`),
`mod_contabil.fechar_periodo` (`:2980`), endpoint `POST /api/financeiro/periodos`
(`main.py:10074`) e chamada no front (`static/index.html:15560`). A frente **não** precisa criar o
conceito de fechamento; precisa pendurar o congelamento nele.

**DECIDIDO (Marcelo, 2026-08-25): snapshot no `PeriodoContabil`** — guardar o relatório pronto, não
carimbar lançamento.

Ao fechar o período, gravar junto os resultados de `relatorio_natureza` (`mod_contabil.py:2390`) e
`relatorio_centro_custo` (`:2352`) daquele intervalo. Relatório de período **fechado** passa a
devolver o snapshot; período **aberto** segue calculando ao vivo sobre a classificação corrente.
Aditivo: não toca em `Lancamento`, e `PeriodoContabil.dados_json` já existe como precedente de
serialização (hoje guarda `alocacao_por_projeto`) — avaliar se o snapshot entra ali ou em coluna
própria, para não misturar dois conteúdos no mesmo campo.

Descartado: carimbar `centro_custo_id`/`natureza_custo` em cada `Lancamento` no fechamento. Daria
mais granularidade (cruzamentos futuros do tipo "variável por centro por projeto"), mas exige
migração na tabela mais movimentada do sistema para um ganho que ninguém pediu.

**Premissa confirmada (Marcelo, 2026-08-25):** os períodos são fechados regularmente na operação —
o regime protege de fato. Se esse hábito mudar, a decisão da Frente 2 precisa ser revista, porque um
período nunca fechado se comporta exatamente como o regime "visão atual".

**Três regimes possíveis:**

| Regime | O que significa | Custo | Efeito colateral |
|---|---|---|---|
| **Visão atual** | A etiqueta é sempre "como classificamos hoje". O relatório declara isso na tela. | Baixo — texto e documentação | Nenhum relatório impresso é reproduzível depois |
| **Congelar no fechamento** | Ao fechar o mês, a etiqueta vigente é gravada no lançamento (ou num snapshot do período). Períodos fechados param; abertos acompanham. | Médio | Depende de existir/ criar um marco de fechamento mensal no financeiro |
| **Vigência por período** | A conta passa a ter linha do tempo de classificações; o relatório usa a vigente na data do lançamento. | Alto | Modelo novo, UI de vigência, migração do histórico |

**Recomendação técnica:** "congelar no fechamento" é o melhor equilíbrio — resolve a
irreprodutibilidade sem criar um modelo temporal. Mas **a escolha é de gestão**: depende de vocês
pretenderem ou não comparar séries longas de custo por centro/natureza.

---

## Frente 3 — Botão Editar (substitui Renomear)  ·  depende das Frentes 1 e 2

**Escopo:** um botão "Editar" por conta, abrindo nome + Centro de Custo + Natureza numa só ação.
Substitui o "Renomear" atual.

**Implementação recomendada:** estender `mod_contabil.editar_conta` (`:523`) para aceitar
`centro_custo_id` e `natureza_custo`, validando contra a árvore do owner e contra `NATUREZA_CUSTO`
(`:577`) — reusando a validação que `classificar_contas_lote` (`:700`) já faz. Uma chamada, uma
transação.

**Alternativa descartada:** o front chamar `editar_conta` para o nome e `classificar-lote` para a
classificação. Funciona e já está testado, mas são duas chamadas — uma pode passar e a outra falhar,
deixando a conta meio editada.

**Pontos a definir:**

- **Permissão — DECIDIDO (Marcelo, 2026-08-25):** renomear continua com o perfil atual;
  **reclassificar centro de custo/natureza exige gerente adm-fin ou diretor**. Implica separar os
  dois gestos na autorização, não só na tela: `editar_conta` passa a validar o perfil quando os
  campos de classificação vierem preenchidos.
- **Rastro.** Registrar quem reclassificou e quando. Sem isso, a Frente 2 fica sem apoio: um número
  que mudou no relatório não tem como ser explicado.
- **Aviso na tela.** Enquanto o regime da Frente 2 for "visão atual", a tela de edição deve dizer,
  em uma linha, que a mudança afeta relatórios de períodos anteriores.
- **Obrigatoriedade — DECIDIDO (Marcelo, 2026-08-25): classificação obrigatória.** Toda conta do
  grupo 5 nasce classificada (criação passa a exigir centro de custo + natureza) e o botão Editar
  não permite limpar. Consequências a tratar na implementação: (i) `classificar_contas_lote`
  (`:700`) hoje aceita vazio para LIMPAR — decidir se essa capacidade é removida ou fica restrita a
  uso administrativo; (ii) o balde `nao_classificado` de `relatorio_natureza` (`:2390`) deixa de ser
  alimentado no fluxo normal, mas **não deve ser removido** — é a rede de segurança para dados
  legados ou importados; (iii) contas do grupo 5 hoje sem classificação precisam ser varridas e
  resolvidas antes de a obrigatoriedade entrar, senão a primeira edição de cada uma vira um
  formulário travado.

---

## Frente 4 — Higiene do plano de contas  ·  independente, pode correr em paralelo

Itens levantados na revisão de 2026-08-25. **Todos decididos pelo Marcelo na mesma data** — a
frente está fechada e pronta para execução.

**Critério aplicado.** A migração v3 (`mod_contabil.py:813`) fixou o critério que vale para todo o
grupo 5: *variável é o que **decorre da venda**, não o que oscila de mês a mês*. Foi por isso que o
Combustível virou Fixo mesmo variando todo mês. As decisões abaixo aplicam esse mesmo critério de
forma consistente.

- **Semivariável — DECIDIDO (Marcelo, 2026-08-25): sai da UI por enquanto.** O slug **permanece** em
  `NATUREZA_CUSTO` (`:577`) e na validação do backend — remover o valor quebraria dados de quem já o
  tivesse; some apenas da lista de opções da tela. Volta quando houver uso real. Se alguma conta
  chegar a ter `semivariavel` gravado, a tela deve exibir o rótulo normalmente (só não oferece a
  opção para novas escolhas).
- **Duplicidade de manutenção de veículo — DECIDIDO: renomear a 5.4.18.** Passa de
  "Manutenção (loja, veículos, informática)" para **"Manutenção (loja e informática)"**, e a 5.2.10
  "Manutenção de Veículos" fica sendo a única conta de veículo do plano. Resolve por texto: **sem
  mover histórico, sem criar nem remover conta**, e preserva o centro de custo de cada uma — veículo
  de montagem/entrega é Logística/Expedição; manutenção de loja e TI segue em Custos Distribuídos.
  Mesmo padrão das 7 renomeações já feitas nesta frente.
  *Nota:* a 5.4.18 permanece em Custos Distribuídos porque ainda mistura dois centros (Instalações/
  Infraestrutura e Sistemas e TI). Se um dia for preciso ler manutenção predial separada de TI, o
  caminho é **quebrar em duas contas**, não renomear de novo.
- **5.3.07 Marketing/Campanhas — DECIDIDO: continua Fixo.** Pelo critério "decorre da venda",
  campanha é decisão de orçamento, não consequência do volume vendido. Era a candidata natural a
  semivariável; como o semivariável sai da UI, a questão se dissolve.
- **5.5.05 Perdas com Acordos Financeiros — DECIDIDO: passa de Fixo para Variável.** É a
  contrapartida-resultado de acréscimo/abatimento em acordo financeiro (`main.py:7352` — ganho em
  4.4.04, perda em 5.5.05), ou seja, nasce da renegociação de recebível de venda. As duas contas
  irmãs, 5.5.03 Antecipação de Recebíveis e 5.5.04 Custo Financeiro sobre Vendas, já são variáveis.
  **A correção entra no mapa `CLASSIFICACAO_GRUPO5_V1` (`mod_contabil.py:755`), junto da
  aposentadoria das migrações v2/v3 (Frente 1)** — não como migração nova.
- **5.4.20 "Outras Despesas" — DECIDIDO: revisão no fechamento mensal.** Conta-lixo por construção;
  o saldo dela passa a ser olhado no mesmo momento em que o período é fechado — rotina que já existe,
  sem cerimônia nova. Se crescer, é sinal de que falta conta, não de que sobra despesa.

---

## Frente 5 — Vocabulário: dois "variável" convivendo  ·  documentação

Existem hoje duas definições de custo variável no sistema, e elas **não conversam**:

- **Motor da venda** — `mod_provisoes.cust_var_marg_cont`: Cust_Var e Marg_Cont saem do CFO e das
  rubricas de provisão da venda. É o número que aparece na Negociação e nas Aprovações Financeiras.
- **Plano de contas** — `Conta.natureza_custo`: etiqueta de gestão por conta, alimenta
  `relatorio_natureza`.

Já divergem na prática: Combustível é **fixo** no plano de contas, enquanto Frete Local e Insumos
Locais entram como variáveis no motor.

**Boa notícia registrada:** reclassificar natureza **não altera** a margem de contribuição de projeto
nenhum — os dois mundos são independentes por construção.

**O que fazer:** escrever essa fronteira (nesta spec e na tela do relatório de natureza), para que
ninguém do financeiro cobre reconciliação entre dois números que nunca foram feitos para bater. Se a
decisão futura for uni-los, isso vira uma frente própria, bem maior.

---

## Ordem sugerida

1. **Frente 0** — retrato do estado real (sem isso, aprovar é aprovar às cegas).
2. **Frente 1** — blindar contra as migrações (sem isso, o botão Editar mente para o usuário).
3. **Frente 2** — escolher o regime de retroatividade (define o que a Frente 3 precisa avisar/gravar).
4. **Frente 3** — botão Editar.
5. **Frentes 4 e 5** — em paralelo, quando houver decisão de gestão.

## Decisões tomadas (Marcelo, 2026-08-25)

| # | Frente | Decisão |
|---|---|---|
| 1 | Frente 1 | Aposentar as migrações v2 e v3, atualizando `CLASSIFICACAO_GRUPO5_V1` com os valores finais. |
| 2 | Frente 2 | Congelar no fechamento, apoiado no `PeriodoContabil` que já existe. |
| 3 | Frente 3 | Reclassificar exige gerente adm-fin ou diretor; renomear segue com o perfil atual. |
| 4 | Frente 4 | Semivariável sai da UI (slug preservado no backend). |
| 5 | Frente 2 | Congelamento = snapshot do relatório no `PeriodoContabil`; nada é carimbado no lançamento. |
| 6 | Frente 3 | Classificação obrigatória em toda conta do grupo 5; não é possível limpar pelo Editar. |
| 7 | Frente 4 | 5.4.18 renomeada para "Manutenção (loja e informática)"; 5.2.10 vira a única conta de veículo. |
| 8 | Frente 4 | 5.5.05 Perdas com Acordos Financeiros passa a **Variável** (correção no mapa, junto da Frente 1). |
| 9 | Frente 4 | 5.3.07 Marketing/Campanhas permanece **Fixo**. |
| 10 | Frente 4 | Saldo de 5.4.20 "Outras Despesas" revisado no fechamento mensal. |

## Dúvidas em aberto

Nenhuma. Todas as decisões foram tomadas pelo Marcelo em 2026-08-25 e estão registradas acima e na
tabela abaixo. As seis frentes estão prontas para virar tarefa.

## Processo

DEV_RULES: branch `feat/<assunto>` a partir da `main`, `pytest -q` verde, `node --check` limpo se
mexer em `static/index.html`, PR contra a `main`, DEV_LOG atualizado. **Uma frente por PR.**
As Frentes 1 e 3 têm testes obrigatórios descritos acima; reusar
`tests/test_centro_custo_natureza.py` e `tests/test_centro_custo_relatorios.py` como base.
