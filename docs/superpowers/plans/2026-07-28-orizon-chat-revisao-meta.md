# Revisão do Orizon Chat — Comunicação externa via Meta (WhatsApp) — Implementation Plan

> **For agentic workers:** cada fatia indica a SUB-SKILL recomendada. Fatias de backend/TDD →
> `superpowers:subagent-driven-development`. Fatias majoritariamente de UI (sem teste JS) →
> `superpowers:executing-plans`. Steps usam checkbox (`- [ ]`). NÃO comece uma fatia sem que as
> dependências marcadas estejam ✅.

**Goal:** transformar o Orizon Chat num módulo de comunicação externa completo sobre a **WhatsApp Cloud
API oficial da Meta** — clientes, fornecedores e parceiros, com triagem, vínculo automático a
Cliente/Projeto, gestão da janela de 24h, templates aprovados e reengajamento automático — sem quebrar a
comunicação interna já existente. Fecha a spec `2026-07-28-orizon-chat-revisao-design.md`.

**Architecture:** ADITIVO sobre o que já existe. Estende `mod_chat.py` / `mod_chat_externo.py` e reusa
os modelos `Conversa`/`ConversaMensagem`/`ConversaParticipante`/`ConversaParticipanteExterno`/
`EnvioExterno` e os cadastros `Cliente`/`Parceiro`/`Fornecedor`/`Projeto`. Regras puras em `mod_chat*`
(padrão `mod_tenancy`/`mod_escopo`); o `main.py` faz as queries e o wiring. Telas novas (Triagem,
Modelos de Mensagem, Fila) entram no painel de Configurações e no modal do Orizon Chat que já existem —
não é app separado. **Config-gated** em todo transporte Meta (sem credencial → `pendente_config`, a rede
não é tocada — invariante já vigente). **Multi-tenancy por loja** em toda entidade nova (RF-14).

**Tech Stack:** Python puro (SQLAlchemy + `http.server`), pytest/TDD (suíte SEMPRE Postgres), frontend
único `static/index.html` (sem teste JS → `node --check` + verificação manual). Design system real
(`orizon-tokens.css`/`orizon-components.css`) — mockup em
`docs/superpowers/specs/comunicacao/mockups/2026-07-28-orizon-chat-mockup.html`.

**Escopo.** DENTRO: RF-01..RF-17 da spec. FORA (spec §13): chatbot/IA autônomo, campanhas de marketing
em massa, canais além do WhatsApp. Também **não** se reconstrói o que já funciona (RF-03 Cliente/Parceiro,
histórico `EnvioExterno`+`ConversaMensagem`, `sac` como 7º segmento já modelado).

**Referências:** spec `docs/superpowers/specs/comunicacao/2026-07-28-orizon-chat-revisao-design.md`;
orientação `.../2026-07-28-ORIENTACAO-CODE-orizon-chat.md`; mockup acima.

---

## Gaps confirmados no código atual (verificados 2026-07-28)

| # | Gap | Evidência no código | Fatia |
|---|---|---|---|
| G1 | `resolver_destino()` não aceita `fornecedor` | `mod_chat_externo.py` — só cliente/parceiro/interno/avulso | F1 |
| G2 | `CANAIS` e `CANAIS_EXTERNOS` sem `compras`/`parceiros` | `mod_chat.py:26` (`CANAIS`) + `mod_chat_externo.py:21` (`CANAIS_EXTERNOS`) — têm até `sac`, faltam os 2 | F1 |
| G3 | `responsavel_sac()` existe mas **não é chamado** | `mod_chat.py:829` def; nenhuma chamada em `main.py` (≠ Financeiro/Logística via `_default_responsavel_faixa`) | ~~F1~~ → **F6** (só há call-site no fluxo de triagem) |
| G4 | Sem cálculo de janela 24h **por conversa** | só `dentro_da_janela_24h(usuario_id)` (chaveado no Usuario interno), não na conversa/contato externo | F1 |
| G5 | Sem tratamento de `HTTPError` da Meta | `_enviar_whatsapp` faz `urlopen` sem capturar HTTPError → motivo real da Meta some | F1 |
| G6 | Transferência **não adiciona** o novo responsável ao grupo | `mensagem_passagem_fase` só chama `enviar_mensagem(natureza="transferencia")`; nenhum `ConversaParticipante` novo. **Gap central da Carteira (§7/RF-11).** | F1 |
| G7 | `_enviar_whatsapp` só monta `"type":"text"` | `mod_chat_externo.py:142` | F3 |
| G8 | Não há tabela/biblioteca de templates (RF-07) | inexistente em `database.py` | F2 |
| G9 | Não há reengajamento automático (RF-17) | inexistente | F4 |
| G10 | Não há telas de Modelos/Triagem/Fila novas (RF-12/15/16, triagem) | inexistente no painel de Config | F5/F6/F7 |

---

## Decisões de design (fixadas antes de codar)

- **Janela por conversa (RF-04, G4):** função pura-ish `mod_chat_externo.janela_da_conversa(db, conversa)
  → {aberta, ultima_entrada, restante_seg|excedido_seg}`. Resolve o(s) número(s) externo(s) da conversa
  (via `ConversaParticipanteExterno.telefone` e/ou o `Cliente/Parceiro/Fornecedor` vinculado) e olha o
  `EnvioExterno.direcao="entrada"` mais recente que casa (últimos 8 dígitos — mesmo casamento já usado em
  `usuario_por_telefone`). Reaproveita `JANELA_HORAS`.
- **Modelo de template (G8):** tabela `template_mensagem` (por loja): `segmento`,
  `slot_obrigatorio` (NULL ou 1..9 da tabela 4.1), `nome_meta`, `categoria` (utility|marketing),
  `idioma` (pt_BR), `corpo` (com `{{1}}`…), `variaveis_json`, `status`
  (`rascunho`/pendente · `em_analise` = "Em análise na Meta" · `aprovado` · `rejeitado` — rótulos/cores do
  mockup: `badge-err`/`badge-warn`/`badge-ok`), `meta_template_id`, `assinatura_var` (posição da variável do
  responsável real — RF-17a), `ativo`. Os **9 slots obrigatórios** viram uma constante
  `SLOTS_OBRIGATORIOS` em `mod_chat` (fonte única do checklist RF-16).
- **Envio por template (G7):** `_enviar_whatsapp_template(env, template, params)` monta `"type":"template"`
  (name/language/components). `despachar` roteia por um `EnvioExterno` que aponta o template usado.
- **HTTPError (G5):** capturar `urllib.error.HTTPError`, ler o corpo JSON da Meta e expor
  `error.message`/`error.code` no `EnvioExterno.erro` (ex.: 131047 janela fechada) — em vez de "HTTP 400".
- **Reengajamento (RF-17, G9):** engine `reengajar_conversa(db, conversa)` que (a) usa a variável de
  assinatura do responsável real, (b) cria notificação interna no disparo (reusa `notificar_usuario`/
  inbox), (c) conta tentativas por conversa (nova coluna/contagem) e para em `limite` (config, default 2).
  **Gatilho periódico:** endpoint idempotente `POST /api/comunicacao/manutencao/janelas` (avisa 90% +
  reengaja fechadas), chamado por **systemd-timer/cron** no VPS (padrão do projeto p/ jobs) — nada de
  scheduler in-process. Config-gated: sem credencial Meta, tudo nasce `pendente_config`.
- **Transferência aditiva (RF-11, G6):** ao registrar `natureza="transferencia"`, **adicionar** o
  funcionário destino como `ConversaParticipante` do grupo (`gerir_participante`/inclusão direta) — NUNCA
  remover ninguém. Vale para a conversa externa E a interna do mesmo projeto. "Meus" = grupos que integro
  (já é a semântica do inbox atual — só formalizar).
- **Reatribuição de Consultor (RF-11):** única exceção ao vínculo estável; só **Gerente** (`autorizar`);
  registra em `LogAcaoGerencial`.
- **Triagem (RF-08/09):** config por loja (`config_financeira_json` ou tabela própria) com formato
  `lista|livre`, rótulos/ordem/ativo por segmento; o fluxo de entrada (webhook) identifica projeto ativo →
  pergunta de confirmação → senão triagem manual. `compras` nunca aparece na triagem de cliente (só
  fornecedor).

## Mudança de ordem vs. a orientação (e o porquê)

A orientação sugeriu: F2 = *envio por template + janela + RF-17*; F3 = *biblioteca de templates*. **Troquei
essas duas** (biblioteca vira F2; envio+janela vira F3; RF-17 vira F4 próprio). Motivo de **dependência
real**: o envio por template (RF-06 troca a composição para *selecionar template*) e o reengajamento
automático (RF-17 precisa mapear *segmento → template*) **só funcionam se o modelo/biblioteca de templates
já existir** para referenciar. Além disso RF-17 é um engine substancial (gatilho periódico + assinatura +
notificação + limite de tentativas) que merece fatia própria e depende do envio (F3). Resultado: **8 blocos
lógicos** mas mantendo o espírito das 7 fatias — F3 e F4 saem do "F2 gordo" da orientação. As demais
(triagem, fila, carteira-UI) seguem a ordem original. Se preferir manter 7 exatas, F3+F4 podem ser uma
fatia só (mais pesada) — deixo explícito.

## Mapa de dependências

```
F1 (fundação: janela, canais, fornecedor, sac, HTTPError, transferência→participante)
 ├─→ F2 (modelo/biblioteca de templates)
 │     ├─→ F3 (envio por template + janela na composição + aviso 90%)  ─┐
 │     │     └─→ F4 (reengajamento automático RF-17)                     │
 │     └─→ F5 (Config → Modelos de Mensagem: checklist RF-15/16)         │  (F3/F4/F5 paralelizáveis
 ├─→ F6 (Config → Triagem + fluxo RF-08/09)                             │   após F1+F2)
 └─→ F7 (Fila de Atendimentos RF-12)  ← usa janela/segmento da F1
F8 (Carteira aditiva na UI RF-11 nav)  ← adiável; depende do mecanismo da F1/G6
F9 (casca de navegação: Configurações do Chat hub + Atendimentos/Chat Interno + placeholders)
```

## Cobertura da navegação do mockup (sidebar) — mapa completo

O mockup tem **7 destinos** na sidebar, em 2 grupos. Mapeamento para as fatias:

| Grupo | Item da sidebar | Detalhado no mockup? | Fatia |
|---|---|---|---|
| Comunicação | **Atendimentos** (fila) | ✅ (abas, filtro, selos) | F7 |
| Comunicação | **Chat Interno** (equipe) | — (aponta p/ a mesma tela no mockup) | F9 (separar o destino; a função já existe) |
| Configurações | **Segmentos** (ativar/editar canais, template padrão) | placeholder | F9 (stub) + dados em F1 (canais)/F2 (template padrão) |
| Configurações | **Triagem** | ✅ (lista/livre + preview) | F6 |
| Configurações | **Modelos de Mensagem** | ✅ (cards + checklist 9) | F5 |
| Configurações | **Números Conectados** (número/status Meta por loja — RF-01) | placeholder | F9 (stub) |
| Configurações | **Consumo / Custos** (templates enviados + custo por segmento — §10) | placeholder | F9 (stub) |

Os 3 *placeholders* são destinos reais mas **sem detalhamento no mockup** (mesma convenção visual, "não
detalhada") — entram como **stubs navegáveis** na F9, para detalhar depois; não bloqueiam a operação.

---

> **Auditoria da Vera (2026-07-29, `99a018e`→`59cda0c`): pode promover; 2 correções aplicadas.**
> (🟠) `janela_da_conversa` varria o histórico global casando só por telefone → vazava a janela entre
> lojas da mesma rede com o mesmo número; **reescrita para escopar pela CONVERSA** (join
> `EnvioExterno→ConversaMensagem→conversa_id`) — mais preciso e resolve o perf (#3). (🟡) Segmentos
> aceitava template **inativo** como padrão → filtro `ativo=1` + `remover_template` agora **limpa o
> slot**. Testes +2 (janela por conversa; padrão não aceita inativo). _Backburner (Vera):_ #4
> `UniqueConstraint(loja,slot)` no template (hoje só app-level) e #5 guardrail de categoria por slot.

## Fatia 1 — Fundação de backend (sem UI nova) — ✅ FEITA 2026-07-28 (`tests/test_orizon_chat_meta.py`, 6)
**Depende de:** — · **Sub-skill:** `superpowers:subagent-driven-development` (TDD, tasks paralelizáveis).
**Pronto quando:** suíte verde; os gaps de F1 fechados com teste; nada de UI.

- [x] **Fornecedor como destinatário (G1, RF-03):** branch `destinatario_tipo == "fornecedor"` em
  `resolver_destino()` (usa `whatsapp` se existir, senão `telefone` — Fornecedor só tem `telefone`/`email`).
  Testes: fornecedor com telefone → destino; sem telefone → erro claro.
- [x] **Canais (G2, RF-02):** incluir `compras`, `parceiros` em `CANAIS` (`mod_chat.py`) e
  `CANAIS_EXTERNOS` (`mod_chat_externo.py`). Teste anti-drift entre as duas listas.
- [ ] ~~**Roteamento SAC (G3)**~~ → **movido para a F6** (ajuste 2026-07-28): o roteamento de segmento por
  entrada só existe DENTRO do fluxo de triagem (`processar_entrada` retorna `{status:"triagem"}` quando
  ambíguo) — que é construído na F6. Não há call-site limpo hoje em F1. `responsavel_sac()` já existe;
  a chamada entra junto com o fluxo de triagem/roteamento.
- [x] **Janela por conversa (G4, RF-04):** `janela_da_conversa(db, conversa)` (ver Decisões). Testes:
  entrada há 1h → aberta + restante; há 30h → fechada + excedido; sem entrada → fechada.
- [x] **HTTPError da Meta (G5):** `_enviar_whatsapp` captura `HTTPError`, `_erro_meta` extrai
  `error.message`/`code` → `despachar` grava em `EnvioExterno.erro`. Testes: `_erro_meta` (131047) +
  `_enviar_whatsapp` com `urlopen` mockado levantando HTTPError → `RuntimeError` com a mensagem real.
- [x] **Transferência aditiva (G6, RF-11 mecanismo):** `enviar_mensagem` com `natureza="transferencia"`
  chama `_adicionar_responsavel_ao_grupo` (via `Funcionario.usuario_id`) → `ConversaParticipante`
  (origem=auto), sem remover ninguém. Testes: destino entra; criador permanece; idempotente.
- [x] Suíte verde (F1 sem tabela/arquivo novo).

## Fatia 2 — Modelo e biblioteca de templates (RF-07) — ✅ FEITA 2026-07-28 (`test_orizon_chat_meta.py`, +3)
**Depende de:** F1 (canais). · **Sub-skill:** `superpowers:subagent-driven-development`.
**Pronto quando:** tabela + CRUD por loja + constante dos 9 slots, com testes de tenancy.

- [x] `database.py`: tabela `template_mensagem` (ver Decisões) + create_all + `modulos.py`.
- [x] `mod_chat`: `SLOTS_OBRIGATORIOS` (as 9 linhas da tabela 4.1) como fonte única; `SEGMENTOS`;
  `listar/criar/editar/remover_template` (por loja; slot obrigatório único por loja).
- [x] `main.py`: `GET /api/comunicacao/templates` (+ slots) e `POST /api/comunicacao/templates[/<id>[/remover]]`
  (criar/editar/soft-delete), gated a gerência (`autorizar`), escopados por loja. Testes: CRUD; slot único;
  loja 2 não vê/edita (404); operador 403.
- [x] Suíte verde.

## Fatia 3 — Envio por template + janela na composição (RF-05, RF-06)
**Depende de:** F1 (janela, HTTPError) + F2 (templates). · **Sub-skill:** `subagent-driven-development`.
**Pronto quando:** dá pra enviar template config-gated e a composição troca por janela.

- [ ] `_enviar_whatsapp_template(env, template, params)` (`"type":"template"`) + roteio em `despachar`;
  `EnvioExterno` aponta o template usado. Testes (mock do boundary): payload template correto;
  config-gated → `pendente_config`.
- [ ] **RF-06 na UI:** GET de mensagens/estado da conversa expõe `janela` (da F1) e, se fechada, a lista
  de templates aprovados do segmento; o compositor troca texto-livre ↔ seletor de template com
  preenchimento das variáveis. `node --check` + verificação manual.
- [ ] **RF-05 aviso 90%:** função `avisar_janela_fechando(db, conversa)` que dispara o template do slot #3
  quando ~90% do prazo sem resposta (idempotente por conversa/janela). Teste da regra (puro) + envio
  config-gated.
- [ ] Suíte verde.

## Fatia 4 — Reengajamento automático (RF-17)
**Depende de:** F3 (envio por template) + F2 (mapping segmento→template). · **Sub-skill:**
`subagent-driven-development`. **Pronto quando:** engine dispara por segmento, assina, notifica e para no limite.

- [ ] `reengajar_conversa(db, conversa)`: escolhe o template de reengajamento do segmento; injeta a
  variável de **assinatura do responsável real** (RF-17a); cria **notificação interna** ao responsável no
  disparo (RF-17b); incrementa e respeita o **limite de tentativas** (config, default 2) → além disso
  marca "decisão manual" (RF-17c). Testes: assina com o responsável certo; notifica; para no limite;
  config-gated.
- [ ] **Gatilho periódico:** `POST /api/comunicacao/manutencao/janelas` (idempotente) que varre conversas
  da loja, chama `avisar_janela_fechando` (90%) e `reengajar_conversa` (fechadas dentro do limite).
  Runbook: systemd-timer/cron no VPS (documentar no DEV_RULES). Teste do endpoint (auth + idempotência).
- [ ] Suíte verde.

> **Decisão do lojista (2026-07-29): UI-primeiro + reconstruir no mockup.** A UI atual está datada e,
> sem tela, é difícil testar; o backend fica com a Vera (auditoria). Começar por **Modelos de Mensagem**.
> O Orizon Chat vira **módulo de PÁGINA CHEIA** (`#page-chat`, casca do mockup: sub-sidebar Comunicação/
> Configurações). Entrega incremental: as telas de Config nascem no `#page-chat`; **Atendimentos/Chat
> Interno** por ora abrem o modal atual (migração da fila = fatia dedicada). Nav novo **"Config do Chat"**.

## Fatia 5 — Configurações → Modelos de Mensagem (RF-15, RF-16) — ✅ UI FEITA 2026-07-29 (frontend)
**Depende de:** F2 (dados, pronta). · **Sub-skill:** `superpowers:executing-plans` (UI).
**Pronto quando:** a tela do mockup renderiza o checklist das 9 e o resumo, consumindo a F2.

- [x] Frontend: `#page-chat` (casca full-page do mockup, tokens reais) + tela **Modelos de Mensagem** —
  3 cards de resumo (Configurados/Aprovados/Pendentes) + checklist 1–9 (badge Aprovado/Em análise/
  Pendente + Editar/Configurar) + modal de cadastro/edição/remoção (consome `GET`/`POST
  /api/comunicacao/templates`). Segmentos/Triagem/Números/Consumo = placeholders navegáveis.
  `node --check` verde. **Verificação visual: pendente (usuário).**
- [ ] (Backburner) `checklist` endpoint dedicado + flag "loja pronta p/ WhatsApp" (RF-16) — hoje o
  cálculo é no front a partir de `GET /templates`; formalizar no backend se necessário.

## Fatia 6 — Configurações → Triagem + fluxo real (RF-08, RF-09) — 🟡 TELA+CONFIG FEITAS 2026-07-29
**Depende de:** F1. · **Sub-skill:** `superpowers:executing-plans` (UI) + backend do fluxo em TDD.
**Pronto quando:** config lista/livre salva e o webhook roteia via triagem.

- [x] Config de triagem por loja (tabela `triagem_config`; `formato` lista|livre; rótulos/ordem/ativo por
  segmento; `compras` nunca na lista de cliente). `mod_chat.triagem_config_get/salvar` + endpoints
  `GET/POST /api/comunicacao/triagem` (gerência, tenancy). Testes: default, salvar, tenancy 403 + loja
  própria. (`test_orizon_chat_meta.py` +2)
- [x] Frontend: tela **Triagem** no `#page-chat` — toggle Lista/Texto livre + rótulos/ativo/reordenar por
  segmento + **pré-visualização** (bolha, tokens) atualizando ao vivo + Salvar. `node --check` verde.
- [ ] **(Backend p/ a Vera)** Fluxo de entrada (estende `rotear_entrada`/`processar_entrada`): identifica Cliente+Projeto ativo →
  pergunta de confirmação (RF-09); senão → triagem manual pelo formato configurado (RF-08); só depois
  expõe na fila do segmento. Testes: número de Cliente c/ projeto → pergunta; número novo → triagem.
- [ ] **Roteamento SAC (G3, movido da F1):** ao rotear uma entrada para o segmento `sac`, resolver o
  responsável via `responsavel_sac()` (já existe/testado) — fora da cadeia de etapa/ciclo; SAC **sem**
  vínculo obrigatório a Cliente (exceção RF-10). Teste: entrada `sac` → responsável de SAC; sem Cliente ok.
- [ ] Frontend: aba **Triagem** (toggle Lista/Texto livre + reordenar/rótulo/ativo + pré-visualização
  WhatsApp), como no mockup. `node --check` + manual.

## Fatia 7 — Fila de Atendimentos (RF-12)
**Depende de:** F1 (janela/segmento). · **Sub-skill:** `superpowers:executing-plans`.
**Pronto quando:** o inbox do Orizon Chat ganha abas + selos do mockup (adaptação, não do zero).

- [x] Backend — ✅ FEITA 2026-07-29: `listar_inbox` enriquece cada conversa (não-mural) com `segmento`
  (canal do último externo) e `janela` (`estado` na/aberta/fechando/fechada + restante/excedido),
  via `mod_chat._atendimento_meta` (reusa a janela escopada por conversa). Teste `test_inbox_atendimento_
  segmento_e_janela` (aberta→fechando→fechada). **`Conversa` não tem `arquivado`** → aba Arquivados fica
  como estado vazio (feature futura); **Outros** exigiria inbox loja-wide + modelo de atribuição de
  atendente (o inbox atual é escopado ao usuário) → adiado.
- [x] Frontend — ✅ FEITA 2026-07-29: tela **Atendimentos** full-page no `#page-chat` (sidebar Comunicação →
  Atendimentos deixa de abrir o modal). Abas **Novos/Meus/Grupos/Arquivados** + filtro por segmento +
  selos (segmento; **Janela aberta/fecha em Xh/fechada**; **Vinculado ao Projeto**). Clicar numa linha
  reusa a thread do modal (`abrirCentralComunicacao`+`ccAbrirConversa`) — modal só será aposentado depois.
  Tokens reais, `esc()` no render (XSS-safe), `node --check` verde.

## Fatia 8 — Carteira aditiva na navegação (RF-11) — adiável
**Depende de:** F1/G6 (mecanismo já pronto). · **Sub-skill:** `superpowers:executing-plans`.
**Pronto quando:** Contatos → Carteiras reflete "grupos que integro" + reatribuição pelo Gerente.

- [ ] Navegação **Contatos → Carteiras**: "Meus" = clientes/projetos cujos grupos eu integro (deriva dos
  participantes). Endpoint + testes.
- [ ] UI de **reatribuição de Consultor** pelo Gerente (única exceção; auditada em `LogAcaoGerencial`).
  Testes: só `autorizar` reatribui; histórico registrado.

## Fatia 9 — Casca de navegação (Configurações do Chat + Atendimentos/Chat Interno + placeholders)
**Depende de:** — (pode começar cedo; hospeda F5/F6). · **Sub-skill:** `superpowers:executing-plans` (UI).
**Pronto quando:** a navegação do mockup existe inteira; F5/F6 renderizam DENTRO do hub de Configurações
do Chat; os 3 placeholders são destinos navegáveis (stub).

- [ ] **Hub "Configurações do Chat"** com as 5 sub-abas do mockup (Segmentos · Triagem · Modelos de
  Mensagem · Números Conectados · Consumo/Custos), gated a gerência. As telas de **Triagem (F6)** e
  **Modelos (F5)** entram aqui como conteúdo real; as outras 3 como stub.
- [ ] **Comunicação:** separar os destinos **Atendimentos** (fila, F7) e **Chat Interno** (equipe — o
  modal/aba que já existe), sem duplicar função.
- [x] **Segmentos** — ✅ FEITA 2026-07-29: os **7 segmentos** com ativar/desativar, rótulo editável e
  **template padrão** por segmento (consome F2). Tabela `segmento_config` + `mod_chat.segmentos_config_get/
  salvar` + `GET/POST /api/comunicacao/segmentos` (gerência, tenancy) + tela no `#page-chat`.
  Testes `test_orizon_chat_meta.py` (+2). (Correção: a Triagem incluiu o 7º segmento **SAC**.)
- [x] **Números Conectados (RF-01)** — ✅ FEITA 2026-07-29: número exibível **editável por loja** (E.164
  + rótulo) + **status do transporte Meta** (chip conectado/pendente + token/Phone Number ID presente,
  IDs por canal) — tudo como **booleanos**, os secrets ficam em variável de ambiente e NUNCA saem no
  JSON (teste prova isso). Tabela `numero_conectado` + `mod_chat.numero_conectado_get/salvar` +
  `_status_transporte_whatsapp` + `GET/POST /api/comunicacao/numeros` (gerência, tenancy) + tela no
  `#page-chat`. Testes `test_orizon_chat_meta.py` (+2, config-gated e não-vazamento de secret).
- [x] **Consumo / Custos (§10)** — ✅ FEITA 2026-07-29: tabela de envios de WhatsApp de **saída** por
  segmento, com quebra enviadas/na fila/pendentes/erro + linha de totais (leitura). `EnvioExterno` ainda
  não tem flag de template → a agregação é por `canal` (segmento) × `status`, escopada por
  `Conversa.loja_id`; **sem R$** (tarifa Meta varia por categoria/país, não cadastrada).
  `mod_chat.consumo_por_segmento` + `GET /api/comunicacao/consumo` (gerência, tenancy) + tela no
  `#page-chat`. Testes `test_orizon_chat_meta.py` (+2, agregação e isolamento por loja).
- [ ] `node --check` + verificação manual (tema claro/escuro); tokens reais.

---

## Fechamento (transversal a cada fatia)

- [ ] **Tenancy (RF-14):** toda entidade/endpoint novo escopado por loja; teste cross-loja (404/403).
- [ ] **Config-gated:** todo transporte Meta sem credencial → `pendente_config` (nunca "enviado" fantasma).
- [ ] Suíte inteira verde (`python3 -m pytest -q`, Postgres); `node --check` nas fatias de UI.
- [ ] **Vera** antes de fechar cada fatia sensível (chat/tenancy/Meta) e ao fim da frente.
- [ ] DEV_LOG (nova Sessão) + marcar a spec como implementada; commit/push; parar em "local testado" e
  aguardar OK para promover (localhost → VPS A → B → produção). Re-ingerir MCP após merge relevante.

## Fora de escopo desta frente (spec §13)
Chatbot/IA autônomo · campanhas de marketing em massa · canais além do WhatsApp.
