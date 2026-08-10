# Design — Simulador de Modelo de Negócios

**Data:** 2026-08-10 · **Requisitos:** `2026-08-10-simulador-modelo-negocios-requisitos.md` (rev2)
**Mockup (fonte literal):** `mockups/2026-08-10-simulador-modelo-negocios-mockup.html`
**Status:** aprovado pelo Marcelo para implementação.

## 1. Decisões de arquitetura

**D1 — Motor puro no backend, front só renderiza.** O cálculo da simulação vive em
`mod_simulador.py`, **puro e sem I/O** (padrão `mod_indicadores`): `simular(modelo, ajustes) ->
resultado`. O frontend NÃO reimplementa a matemática — envia os ajustes do usuário
(`POST /api/simulador/simular`) e renderiza o resultado. Motivos: fonte única de verdade testável
por TDD, e o motor já nasce acoplável a outros sistemas (o contrato de entrada é a fronteira).

**D2 — Contrato `ModeloLoja` (JSON serializável).** Único ponto de acoplamento com o hospedeiro:
unidades de receita (vendedores: valor real do período, média histórica, meta), variáveis
percentuais (provisões, inclusive zeradas), folha (por colaborador: fixo, comissão fixa
`existe_comissionamento_fixo`, pró-labore, faixas de comissão da loja), custos fixos (todas as
contas + amortizações nome/valor/prazo), parâmetros fiscais (carga por contexto), juros e dívida
nominal, médias de contexto (markup seco/com frete médios por janela). Campo `rotulos` opcional
para vocabulário por segmento (abstração de assessoria — **não** implementar UI disso agora).

**D3 — Levantamento (adapter Orizon) separado do motor.** `mod_simulador_dados.py` monta o
`ModeloLoja` consultando o que já existe: config financeira/provisões da implantação, folha e
remunerações (faixas de comissão), `mod_contabil.relatorio_natureza` (custos fixos históricos +
contas do plano), perfil fiscal, e as janelas/médias no padrão de `mod_indicadores.janela_periodo`
(descartando meses zerados — RF-13). Outro sistema no futuro = outro adapter, motor intocado.

**D4 — Acesso: capability nova `acesso_simulador`, só super_admin.** A aba Simulador do Painel
Estratégico só renderiza (e as rotas só respondem) para quem tem a capability — que na v1 pertence
apenas ao perfil super_admin. Não usar `if nivel == "super_admin"` hardcoded (mesma lição do
`acesso_estrategico`, Sessão 181).

**D5 — Autorização por loja (LGPD): tabela própria + step-up + seed.**
- Tabela `simulador_autorizacoes`: `loja_id` (única ativa por loja), `status`
  (ativa/revogada), `concedido_por_usuario_id`, `beneficiario` ("orizon_assessoria"),
  `escopo` ("simulacao_leitura"), `base_legal` (texto do termo aceito), `concedido_em`,
  `revogado_em`, `ip`.
- Conceder = **Master da loja** via step-up por senha (reaproveitar o mecanismo
  `POST /api/auth/step-up` / `LogAcessoDelegado` da frente de Perfis). Revogar = Master, efeito
  imediato.
- **Seed idempotente** (`simulador_autorizacao_seed_v1` em `_run_migracoes`): lojas existentes
  nascem com autorização ativa (decisão do usuário — as lojas atuais já podem entrar autorizadas).
- Trilha própria `simulador_log_acessos`: evento (concessao/revogacao/abertura/levantamento),
  usuario_id, loja_id, quando, ip. **Fora** do log operacional (RF-04).

**D6 — Estado da simulação é efêmero** (por sessão de tela, v1). Nada é gravado de volta nas
fontes (RNF-01). Salvar/comparar cenários = evolução futura.

## 2. Endpoints (todos gated por `acesso_simulador`)

| Rota | Papel |
|---|---|
| `GET /api/simulador/lojas` | lojas + estado de autorização (ativa/bloqueada) p/ o seletor |
| `POST /api/simulador/autorizacao` | conceder (step-up do Master da loja alvo) |
| `POST /api/simulador/autorizacao/revogar` | revogar (Master da loja) — endpoint acessível ao Master mesmo sem `acesso_simulador` |
| `GET /api/simulador/modelo?loja_id&cenario&janela` | monta e devolve o `ModeloLoja` (registra abertura no log) |
| `POST /api/simulador/simular` | `{modelo_ref ou modelo, ajustes}` → resultado (grupos A–F calculados) |

`cenario` ∈ atual/historico/futuro; `janela` conforme RF-10..RF-12 (atual: mes_fechado|ultimos_30;
histórico: tri|sem|ano; futuro: atual|tri|sem|ano).

## 3. Motor — semântica do cálculo (RF-15..RF-25)

- Faturamento = Σ unidades ativas (Atual: valor real; Histórico/Futuro: média da janela por posto).
- **Trava** (RF-16): travado, demissão redistribui o volume proporcionalmente entre os ativos;
  livre, o faturamento cai para a soma dos que ficaram. (v1 aplica o comportamento padrão; o fluxo
  "perguntar quais variáveis fixar" fica explicitamente fora da v1 — anotar como pendência.)
- Variáveis: `valor = % editado × faturamento`. Markups (seco/com frete) **não** entram na cadeia
  de consequências — iniciam pela média da janela e só mudam por edição direta (RF-18); RN-02:
  % exibido = adicional (2,18× = 118%).
- Folha: fixo = salário editado + comissão fixa (sem encargos sobre ela) + encargos (35% sobre o
  salário CLT; pró-labore sem encargos); variável = comissão pela **faixa de meta** da config da
  loja aplicada ao valor vendido simulado (consultor: sobre a própria venda; gerente: sobre o
  faturamento vs meta da loja; percentuais fixos p/ funções sem faixa). Sem comissão → R$ 0
  ("sem comissionamento" na UI).
- Custos fixos: todas as contas (inclusive zeradas) + amortizações (`impacto_mensal = Σ valor/prazo`).
- Impostos: carga do perfil fiscal aplicada ao faturamento simulado; juros valor mensal; dívida
  nominal só exibida.
- Snapshot: MC = fat − variáveis − comissões; Lucro = MC − folha fixa − custos fixos − juros −
  impostos; margens = fração do fat (guarda `_div`: denominador 0 → None/"—").

## 4. Frontend

Aba **Simulador** dentro do Painel Estratégico (`static/index.html`), **mockup como fonte
literal** (lição da Fatia 7 — copiar estrutura/medidas/tokens, não reinterpretar): barra de
contexto (loja/cenário/janela/trava), grade densa 2 colunas + folha full-width em cards
(mobile empilha), Snapshot sticky sempre completo, modal de solicitação de acesso. Tokens de
`design-system/orizon-tokens.css` — nenhum hex literal novo.

## 5. Fases de implementação (TDD, suíte sempre verde)

1. **F1 — Motor:** `mod_simulador.py` + `tests/test_simulador.py` (cenários, trava/redistribuição,
   markup imutável por efeito, folha com faixas, amortização, snapshot; casos de borda: loja sem
   vendedor ativo, meses zerados, denominadores 0).
2. **F2 — Autorização:** tabelas + migração + seed + step-up + log + `tests/test_simulador_autorizacao.py`
   (super_admin sem autorização → 403 com motivo; Master concede/revoga; seed idempotente; trilha).
3. **F3 — Levantamento:** `mod_simulador_dados.py` + endpoints modelo/simular + testes de
   integração (ModeloLoja montado de uma loja seedada bate com as fontes).
4. **F4 — UI:** aba no Painel Estratégico fiel ao mockup; verificação manual claro/escuro +
   `node --check` do script extraído.
5. **F5 — Fechamento:** Vera (fluxo ponta a ponta: autorizar → abrir → simular → revogar → 403),
   DEV_LOG, re-ingerir grafo MCP.

## 6. Fora de escopo da v1 (registrado)

Fluxo "quais variáveis fixar" da trava (RF-16, segunda parte) · persistência/comparação de
cenários · UI multi-segmento (`rotulos`) · exportação PDF · API pública externa.
