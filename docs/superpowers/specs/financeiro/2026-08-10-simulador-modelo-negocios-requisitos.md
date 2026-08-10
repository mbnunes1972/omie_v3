# Requisitos — Simulador de Modelo de Negócios

**Data:** 2026-08-10 · **Fonte:** `Simulador.docx` (Marcelo) · **Status:** rascunho para aprovação
**rev1 (2026-08-10):** feedback do Marcelo sobre o 1º mockup — markup seco + com frete,
percentuais e salários editáveis, folha com todos os colaboradores em cards lado a lado (faixas de
meta), mínimo garantido sai da tela (vira indicador), sem toggle de plano de contas, layout denso
em desktop.
**rev2 (2026-08-10):** correção do RN-02 (percentual do markup é o **adicional**: 2,18× = 118%) e
mudança do modelo de acesso — módulo **exclusivo do super_admin** (assessoria Orizon), com
**autorização por loja (LGPD)**: lojas atuais nascem autorizadas por seed; mecanismo de
conceder/revogar previsto e funcional desde a v1.
**Posicionamento:** módulo acoplado ao **Painel Estratégico** (aba própria), motor desacoplado para
futuro acoplamento em outros sistemas e assessoria a empresas de outros segmentos.

---

## 1. Visão geral

Ferramenta de **assessoria a lojas**: simula o funcionamento econômico da loja a partir de um motor
que extrai as **variáveis reais do negócio** já configuradas no Orizon — provisões da implantação,
política de salários e comissionamentos, histórico de despesas recorrentes (custos fixos),
parâmetros fiscais (carga tributária por contexto de faturamento) e as médias guardadas pelo
Painel Estratégico (tempo médio de entrega, prazos, valores).

O usuário monta **cenários** (atual, histórico, futuro), altera variáveis (demitir/contratar
vendedor, mudar provisão, travar faturamento, editar markup) e vê no **Snapshot** as consequências
financeiras: margem de contribuição, margem de lucro líquido e markup.

**Definição normativa (RN-01):** neste módulo, **"Faturamento" = valor líquido** usado no sistema
(entrada real descontando financeiro, custos externos e comissionamentos externos destacados no
sistema) — o mesmo Val_Liq do motor de negociação.

**Definição normativa (RN-02, rev2) — convenção de markup:** o percentual exibido é o
**adicional** sobre a base: multiplicador 1,8 = **markup 80%**; multiplicador 2,18 = **markup
118%**. Dois markups distintos: **Markup seco** (base = valor de fábrica) e **Markup com frete**
(base = valor de fábrica + frete fábrica).

## 2. Posicionamento e acesso (rev2)

- **RF-01.** O Simulador é apresentado como **aba do Painel Estratégico**, mas é um **módulo
  distinto**, com capability própria (`acesso_simulador`) concedida **exclusivamente ao
  super_admin** (assessoria Orizon). Nenhum outro perfil — nem o Master da loja — vê a aba na v1.
  Rota própria (`/api/simulador/...`) para permitir desacoplamento futuro.
- **RF-02. Autorização por loja (LGPD):** o Simulador acessa informações sigilosas da loja
  (folha, salários, margens, dívida). Cada loja precisa ter **autorização ativa** para que o
  super_admin abra sua simulação — sem autorização, a loja aparece no seletor **bloqueada**
  (🔒 solicitar acesso). **Lojas atuais já entram autorizadas** (seed idempotente na migração),
  mas o mecanismo de conceder/revogar deve nascer **funcional**, não apenas previsto.
- **RF-03. Concessão juridicamente válida:** a autorização é concedida pelo **Master da loja**
  com autenticação segura (reautenticação por senha — padrão step-up já existente no sistema),
  registrando quem concedeu, beneficiário, escopo (simulação · somente leitura), base legal/termo,
  data/hora e IP. **Revogável a qualquer momento** pelo Master, com efeito imediato.
- **RF-04. Log de auditoria separado:** concessão, revogação e **cada abertura/extração de dados**
  pelo Simulador são registrados em **trilha própria** (tabela dedicada, fora do log operacional),
  consultável para auditoria/LGPD.

## 3. Arquitetura de acoplamento (motor + adapters)

- **RF-05. Motor puro:** o cálculo da simulação vive num módulo **puro, sem I/O**
  (padrão `mod_indicadores`/`mod_negociacao`): recebe um **modelo de entrada** (JSON) e devolve o
  resultado. Nenhuma query dentro do motor.
- **RF-06. Contrato de entrada (`ModeloLoja`):** estrutura serializável com: unidades de receita
  (vendedores) e seus valores; variáveis percentuais (provisões); folha (fixa/variável, mínimo
  garantido); custos fixos + amortizações; parâmetros fiscais; juros e dívida; médias de contexto
  (markup médio, prazos). É o **único** ponto de acoplamento com o sistema hospedeiro.
- **RF-07. Adapters Orizon:** camada de levantamento que monta o `ModeloLoja` a partir de:
  implantação (provisões), folha/remunerações, plano de contas + razão (custos fixos históricos),
  perfil fiscal, e Painel Estratégico (médias). Outros sistemas futuros = outros adapters, sem
  tocar o motor.
- **RF-08. Abstração de segmento (não trava o dev):** a terminologia do motor é genérica —
  "unidade de receita" (vendedor), "variáveis percentuais sobre receita" (provisões), "folha",
  "custos fixos", "encargos". A v1 entrega o vocabulário da loja de planejados na UI; um mapa de
  rótulos por segmento fica previsto no contrato (campo `rotulos`), sem esforço adicional agora.

## 4. Cenários

- **RF-09. Três cenários:** **Atual**, **Histórico** e **Futuro** — sempre disponíveis, alternáveis
  sem perder edições do usuário (cada cenário guarda seu próprio estado de simulação).
- **RF-10. Atual:** base = **último mês fechado** ou **últimos 30 dias** (toggle). Cada vendedor
  entra com seu **valor real** de venda no período.
- **RF-11. Histórico:** base = médias históricas tratadas como padrão — cada posto de venda inicia
  **igual para todos**, com a média histórica do período. Janela selecionável:
  **trimestral / semestral / anual**.
- **RF-12. Futuro:** mesma mecânica do Histórico, mas o seletor de janela inclui também **atual**
  (isto é: atual / trimestral / semestral / anual).
- **RF-13. Meses zerados:** no cálculo de médias históricas, meses **sem dados (zero por
  inexistência)** são descartados da janela para não distorcer a média.

## 5. Grupos de dados (estrutura da tela)

Todos os grupos têm **expandir/agrupar** (RF-14): expandido mostra todos os campos; agrupado mostra
só a primeira linha com o **dado mais importante** do grupo. Exceção: o Snapshot (grupo F) aparece
**sempre completo**.

### A. Vendas — dado principal: Faturamento
- **RF-15.** Lista de vendedores com a venda de cada um (real no Atual; média igual por posto no
  Histórico/Futuro). O total fecha a linha **Faturamento**.
- **RF-16. Trava de faturamento (toggle):** com o faturamento **travado**, mudanças da simulação
  se refletem nas demais variáveis — o sistema aplica o padrão ou pergunta **quais variáveis manter
  fixas** e quais absorvem a variação. **Livre**, o faturamento flutua com as mudanças.

### B. Variáveis do modelo — dado principal: % total sobre faturamento
- **RF-17.** Todas as provisões previstas no sistema, **inclusive as zeradas** (não usadas), com
  colunas nome · percentual · valor. Os **percentuais são editáveis** pelo usuário (simulação de
  mudança de política). **Exceto** comissionamentos de pessoal (vendedores, montadores, projeto
  executivo etc.), que ficam na Folha.
- **RF-18. Markups em destaque no topo (rev1/rev2):** duas linhas — **Markup seco** e **Markup
  com frete** (inclui frete fábrica na base) — com nome · percentual **adicional** (RN-02:
  2,18× = 118%) · **multiplicador** editável. Iniciam sempre pela **média do período analisado**;
  **nunca** mudam por efeito de outras variações — só por edição direta.

### C. Folha de pagamento — dado principal: valor e % sobre faturamento (fixo e variável)
- **RF-19 (rev1).** Contempla **todos os funcionários e colaboradores configurados na loja**,
  incluindo **diretor e sócios** (pró-labore). Apresentação em **cards por pessoa com as
  componentes salariais lado a lado** (fixo · encargos · comissão); no celular, empilhadas.
  **Salários editáveis** (caso de reestruturação da empresa). Quem tem comissionamento mostra o
  **valor da comissão calculado pela faixa de meta e pelo valor vendido**, conforme a configuração
  da loja; quem não tem mostra apenas **"sem comissionamento"**.
- **RF-19b (rev1). Comissionamento fixo:** o mínimo garantido **não aparece** na tela como linha
  própria — quando a loja usar, exibe-se apenas o indicador **"Existe comissionamento fixo"** no
  card, e o valor é tratado dentro da **componente de custo fixo do salário** (sem
  INSS/FGTS/13º/férias sobre ele).
- **RF-20. Liga/desliga por funcionário (demissão/retorno):** desligar um consultor recalcula o
  faturamento para menor usando a média dos vendedores que permaneceram; com faturamento
  **travado**, o volume do desligado é **redistribuído proporcionalmente** entre os demais.

### D. Custos fixos — dado principal: valor total e % sobre faturamento
- **RF-21 (rev1).** Lista **todas as contas de despesa configuradas na loja** (plano de contas),
  inclusive as sem lançamento no período — sem toggle e sem destaque especial de "conta zerada";
  contas zeradas aparecem apenas atenuadas.
- **RF-23. Amortizações (área destacada):** colunas nome · valor · prazo; o sistema apresenta o
  **impacto médio mensal** ponderado pelos prazos.

### E. Juros, Impostos e Dívida — dado principal: valor total e % sobre faturamento
- **RF-24.** Juros, impostos (via parâmetros fiscais → carga tributária do contexto de faturamento
  simulado) e **dívida nominal**, destacados separadamente.

### F. Snapshot — sempre completo
- **RF-25 (rev1).** Resultados e consequências financeiras do modelo simulado: **margem de
  contribuição**, **margem de lucro líquido** e os **markups** tratados — seco e com frete, na
  convenção RN-02 (% adicional) — mesmos dados do grupo B (uma única fonte).

## 6. Não-funcionais e regras transversais

- **RNF-01.** Simulação é **somente leitura** sobre os dados reais — nunca grava de volta no
  sistema de origem.
- **RNF-02.** Divisões com denominador zero seguem o padrão do projeto: `None`/"—", nunca número
  enganoso (`mod_indicadores._div`).
- **RNF-03.** Tema claro/escuro com os tokens oficiais (`orizon-tokens.css` — cobre/areia/carvão);
  valores monetários em mono alinhados à direita.
- **RNF-05 (rev1). Aproveitamento de tela:** em desktop, layout **denso** — grupos lado a lado e
  cards de funcionário em grade; em celular, tudo **empilhado** (o formato de coluna única fica
  reservado ao mobile).
- **RNF-04.** Estado da simulação é efêmero por sessão na v1 (sem persistência); salvar/compartilhar
  cenário é evolução futura.

## 7. Fora de escopo desta entrega

Multi-segmento na UI (só o vocabulário genérico no contrato — RF-08) · persistência de cenários ·
comparação lado a lado de cenários · exportação PDF · API pública para terceiros (a rota própria
RF-01 já prepara o caminho).

## 8. Rastreabilidade

| Item do doc original | Requisito |
|---|---|
| Seletor de lojas + autorização jurídica (LGPD) + log separado | RF-02, RF-03, RF-04 |
| Acesso exclusivo super_admin (assessoria) | RF-01 |
| 3 cenários (atual/histórico/futuro) + janelas + meses 0 | RF-09..RF-13 |
| Grupos com expandir/agrupar + dado principal | RF-14 |
| Vendas + trava de faturamento | RF-15, RF-16 |
| Variáveis (editáveis) + markups seco/com frete (RN-02) | RF-17, RF-18 |
| Folha completa (cards, faixas de meta, com. fixo) + demissão/retorno | RF-19, RF-19b, RF-20 |
| Custos fixos (todas as contas) + amortizações | RF-21, RF-23 |
| Juros/Impostos/Dívida | RF-24 |
| Snapshot sempre completo | RF-25 |
| "Faturamento" = valor líquido | RN-01 |
| Acoplável a outros sistemas / outros segmentos | RF-05..RF-08 |
