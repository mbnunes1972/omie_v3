# Redesenho de UI — Atendimentos e Chat Interno + Concluir + Iniciar Conversa — Implementation Plan

> **For agentic workers:** fatias de backend/TDD → `superpowers:subagent-driven-development`;
> fatias majoritariamente de UI (sem teste JS) → `superpowers:executing-plans`. Steps com checkbox.
> NÃO começar uma fatia sem as dependências marcadas ✅.

**Goal:** implementar a spec `2026-08-04-orizon-chat-atendimentos-ui-design.md` — redesenho visual
das telas de **Atendimentos** e **Chat Interno** no padrão do mockup
(`mockups/2026-08-04-orizon-chat-atendimentos-ui-mockup.html`, referência definitiva), mais
**Concluir atendimento**, **Assunto no Chat Interno**, **responsável atual da conversa**,
**urgência manual** e o fluxo de **Iniciar Conversa por template** (que puxa para esta entrega o
envio `"type":"template"`, ex-Fatia 3 do plano de 28/07).

**Architecture:** ADITIVO sobre o pacote `chat/` (`core.py`/`externo.py`/`triagem.py`) e o
`#page-chat` do `static/index.html` (shell `ochat` já full-page — telas trocadas por `ochatIr`,
thread única `#oc-pane` movida entre slots). Modelos em `database.py`, rotas em `main.py`.
Config-gated em todo transporte Meta (sem credencial → `pendente_config`). Tenancy por loja.

**Baseline (2026-08-04):** suíte **1720 verde** em Postgres. Plano de 28/07: F1/F2 prontas
(`janela_da_conversa` por conversa, transferência aditiva G6, tabela `template_mensagem` + CRUD);
**F3 (envio por template) NÃO feita** — entra aqui na Fatia 1.

---

## Checagens técnicas resolvidas (orientação §1 e spec §14, verificadas no código 2026-08-04)

| # | Pergunta | Resposta factual | Decisão |
|---|---|---|---|
| C1 | "Responsável atual" usa o mecanismo da transferência de etapa? | **Não existe campo.** `natureza="transferencia"` (ConversaMensagem) + `transferido_para_funcionario_id` só persistem estado em `CicloEtapa.responsavel_funcionario_id` (projeto). Direct/grupo/lead não têm onde gravar. | Coluna nova **`Conversa.responsavel_usuario_id`** (FK usuarios, nullable). A transferência automática de etapa PASSA a também atualizar esse campo (mesmo evento, via `_usuario_do_funcionario`) — um único conceito, dois gatilhos. |
| C2 | Abrir/responder exige ser participante? | **Sim** (`pode_ler_conversa` → `eh_participante` p/ direct/grupo/projeto; gerência tem oversight mas não aparece na inbox). | Transferir manual **adiciona o destino como `ConversaParticipante`** (aditivo, reaproveita o padrão `_adicionar_responsavel_ao_grupo` — nunca remove ninguém). |
| C3 | "Fila geral" ainda é estado válido do seletor? | Hoje "sem responsável" é o estado padrão (nada atribui). Mas no fluxo real quem **resolve a triagem assume** o atendimento — batendo com "sempre existe alguém a partir da triagem" (Marcelo). | Seletor de transferência **só pessoas nomeadas** (sem "Fila geral"). Campo nullable cobre legado/pré-triagem. Reversível se Marcelo pedir. |
| C4 | Meta: 1º contato com cliente cadastrado sem histórico — Marketing ou Utility? | Pesquisa 2026-08-04 (doc oficial Meta): categoria é do **conteúdo do template**, não do estágio do relacionamento. Texto operacional ancorado em contrato/projeto = defensável como **Utility** (~R$0,05); tom persuasivo → classificador aprova como **Marketing** (~R$0,35, auto-recategorização desde abr/2025). Opt-in é exigido p/ TUDO (método livre — cláusula no contrato resolve). Template aprovado é obrigatório sem janela, sem exceção. | Nenhuma trava de UI por categoria. A UI usa só `status=="aprovado"` (✓ Meta). Nota no DEV_LOG p/ Marcelo: conferir a categoria com que cada template foi efetivamente aprovado (é ela que define o preço). |

## Decisões de design (fixadas antes de codar)

- **Responsável (spec §7.1-A):** `Conversa.responsavel_usuario_id`. Setado em: (a) resolução de
  triagem `vincular`/`criar` → o **resolvedor** assume; (b) criação de grupo/conversa → o criador;
  (c) transferência automática de etapa (caminho `natureza="transferencia"` em
  `chat/core.enviar_mensagem`) → usuário do funcionário destino; (d) **Transferir manual** (novo
  `POST /api/comunicacao/conversas/<id>/transferir {usuario_id}`) → seta o campo + adiciona
  participante + grava mensagem-evento `responsavel_transferido` (auditoria na própria conversa).
  O manual NÃO toca `CicloEtapa` (spec: "não amarrada a mudança de etapa"). Seletor da UI consome
  `GET /api/comunicacao/usuarios` (Nome/Função já disponíveis).
- **Urgência (spec §6.1):** `Conversa.urgente` (int 0/1) + `POST .../urgente {on}` (qualquer
  participante; admin tb). Mensagem-evento inline `urgencia` registra quem ligou/desligou. Sem
  regra automática (fora de escopo).
- **Origem da conversa (spec §5):** `Conversa.origem_entrada` (`triagem`|`avulsa`|NULL).
  `triagem_resolver_vincular/criar` gravam `triagem`; Iniciar Conversa (Fatia 5) grava `avulsa`;
  NULL (legado/interna) → tag fallback externa "Avulsa". Tag só quando `segmento` é NULL.
- **Concluir (spec §8):** `Conversa.status` (`aberta`|`concluida`) + `concluido_por_id` +
  `concluido_em` + `conclusao_obs`. Global à conversa (≠ `ConversaParticipante.arquivada`, que
  permanece como arquivamento pessoal). Notificação = DM interna (`get_or_create_direct` +
  `enviar_mensagem`, best-effort pós-commit — padrão do notificador de montador `main.py:9698`)
  para **todos** os usuários de `_usuarios_gerencia_loja` (gerente+master, já pronto em
  `chat/core.py:841`). Reabertura automática: `processar_entrada` ao rotear p/ conversa
  `concluida` volta `status="aberta"` (campos `concluido_*` ficam como histórico da última
  conclusão até a próxima).
- **Envio por template (spec §11, ex-F3 de 28/07):** `_enviar_whatsapp_template(env, tpl, params)`
  monta `{"type":"template","template":{name, language, components(body params)}}`;
  `EnvioExterno.template_id` (coluna nova) aponta o template usado; `despachar` roteia quando o
  envio tem template. Corpo **renderizado** (variáveis substituídas) fica em
  `ConversaMensagem.corpo` → histórico legível. Config-gated (`pendente_config`).
- **Iniciar Conversa (spec §11):** novo `POST /api/comunicacao/iniciar-conversa`
  `{contato: {cliente_id | nome+telefone+email?}, template_id|livre, params{}}`. Valida
  bloqueante: template exige `status=="aprovado"`; `livre` só com janela aberta p/ o telefone;
  variáveis não preenchidas → 400 com o campo pendente. Cria/acha o contato, cria a conversa
  (`origem_entrada="avulsa"`, `segmento` herdado do template, responsável = quem inicia,
  participante externo com o telefone) e despacha. Variáveis conhecíveis resolvidas numa função
  central `resolver_variaveis_conhecidas` (usuário logado, nome do contato, loja) — reutilizável.
- **Assunto no Chat Interno (spec §5.1):** modelo `Assunto`/`assunto_tipo` **já existe** — a
  fatia é UI + wiring (`POST /api/comunicacao/conversas` já aceita assunto). Tag "Livre" quando
  `assunto_tipo=="livre"`; busca por assunto nas sugestões.
- **Chips no lugar das abas (mockup):** Atendimentos: Todas · Grupos · Projetos · Arquivadas ·
  Urgentes. Chat Interno: sem "Projetos". "Arquivadas" = arquivadas-por-mim ∪ concluídas (selo
  "Concluída"). Aba "Todas (admin)" da gerência permanece como está (fora do redesenho, oversight).

## Mapa de dependências

```
F1 (fundação: responsável+transferir, urgente, origem, status/concluir-backend, envio template)
 ├─→ F2 (layout novo Atendimentos + Chat Interno)      ─┐
 ├─→ F3 (Concluir atendimento: modal+notificação+selo)  │ F2/F3/F4 paralelizáveis após F1
 ├─→ F4 (Assunto no Chat Interno: modal próprio, busca) ─┘
 └─→ F5 (Iniciar Conversa por template — 3 etapas)  ← depende estritamente de F1
```

---

## Fatia 1 — Fundação de dados e envio por template (backend, TDD) — ✅ FEITA 2026-08-04
**Depende de:** — · **Pronto quando:** suíte verde; campos+endpoints novos testados; template
enviável config-gated; nada de UI. **Suíte 1734 verde (1720 baseline + 14 novos,
`tests/test_atendimentos_ui.py`).**

- [x] `database.py`: colunas novas em `conversas` — `responsavel_usuario_id`, `urgente`,
  `origem_entrada`, `status`, `concluido_por_id`, `concluido_em`, `conclusao_obs`; e em
  `envios_externos` — `template_id`. Migração idempotente (`_migrar_colunas_pg`).
- [x] `chat/core.py`: `transferir_responsavel(db, conversa, ator_id, usuario_destino_id)` —
  seta campo, adiciona participante (aditivo/idempotente), mensagem-evento
  `responsavel_transferido`; caminho `natureza="transferencia"` também atualiza o campo;
  `definir_urgencia(db, conversa, ator_id, on)` com evento `urgencia`;
  `concluir_atendimento(db, conversa, ator_id, obs)` / reabertura em `processar_entrada`;
  `serializar_conversa`/`_atendimento_meta` expõem `responsavel` (id+nome), `urgente`,
  `origem_entrada`, `status`+`concluido_*`.
- [x] Pontos de atribuição: triagem `vincular`/`criar` → resolvedor; `criar_grupo`/
  `get_or_create_direct`/conversa nova → criador; triagem grava `origem_entrada="triagem"`.
- [x] `chat/externo.py`: `_enviar_whatsapp_template` + roteio no `despachar` +
  `registrar_envio(..., template_id)`; `resolver_variaveis_conhecidas`.
- [x] `main.py`: `POST /api/comunicacao/conversas/<id>/transferir` (participante ou gerência),
  `POST .../urgente`, `POST .../concluir` (com notificação à gerência), inbox expõe os campos.
- [x] Testes novos (`tests/test_atendimentos_ui.py`): transferir seta+adiciona participante+não
  remove ninguém; idempotente; urgente liga/desliga com evento; concluir grava quem/quando/obs e
  notifica gerência (DM criada); nova entrada reabre; origem triagem vs avulsa; payload template
  correto (mock urlopen); config-gated `pendente_config`; validação variável vazia; tenancy.
- [x] Suíte verde. → **✅ FEITA 2026-08-04** (+14 testes)

## Fatia 2 — Layout novo das telas (frontend)
**Depende de:** F1. · **Pronto quando:** as duas telas reproduzem o mockup (topbar+chips, lista
com tags/ponto de urgência, cabeçalho com responsável+toggle, barra de ação e composição em
largura total), `node --check` verde, tema claro/escuro ok.

- [x] Topbar: botão ＋, busca com sugestões agrupadas (Contatos/Assunto/Mensagens no Atendimentos;
  Colegas/Assunto no Interno), 📌 Mural (só Interno), + Criar Grupo, divisor, chips na ordem exata
  do mockup. Chips filtram `_atdInbox`/`_intInbox` (Urgentes = flag; Projetos = tipo projeto;
  Arquivadas = arquivada-por-mim ∪ concluída).
- [x] Lista: tag de segmento OU fallback Avulsa/Triagem (por `origem_entrada`) no Atendimentos;
  tag Assunto/Livre no Interno; ponto vermelho 7px antes do nome quando `urgente`; avatar
  redondo/quadrado; seleção com borda âmbar.
- [x] Cabeçalho do chat: nome/subtítulo/tag + selo "segmento automático"; canto direito com
  responsável (só grupo/projeto) + toggle de urgência (`POST .../urgente`).
- [x] Barra de ação (largura total): ✅ Concluir (só Atendimentos) · 🔀 Transferir (seletor de
  usuários reais Nome/Função com busca, `POST .../transferir`) / 📤 Encaminhar (Interno) ·
  ⬇️ Exportar (PDF/TXT — reusa exportação existente); confirmação textual efêmera.
- [x] Barra de composição (largura total): 📎 menu de anexo (Documento/Fotos/Câmera/Áudio/
  Contato — Documento/Fotos usam o upload existente; Câmera/Áudio pedem permissão nativa via
  `getUserMedia`), campo, 🎤↔➤.
- [x] `node --check` no `<script>` extraído; verificação visual manual (usuário) pendente.

## Fatia 3 — Concluir atendimento (UI sobre o backend da F1)
**Depende de:** F1 (endpoint pronto). · **Pronto quando:** fluxo do mockup completo.

- [x] Modal: contato da conversa, "Concluído por" = usuário da sessão (somente leitura),
  observação opcional, aviso de notificação; confirmação → `POST .../concluir`.
- [x] Estado: some de "Todas", aparece em "Arquivadas" com selo **Concluída**; reabertura
  automática (F1) devolve para "Todas".
- [x] Confirmação textual na barra de ação ("✓ Atendimento concluído — gerência notificada").

## Fatia 4 — Assunto no Chat Interno
**Depende de:** F1 (nada estrutural — modelo já existe). · **Pronto quando:** fluxo §5.1 completo.

- [x] Modal próprio do "+" do Interno: busca usuário/grupo + campo Assunto (opcional → "Livre");
  cria via `POST /api/comunicacao/conversas` com assunto custom.
- [x] Tag Assunto/Livre na lista e cabeçalho; busca geral do Interno sugere por Assunto.
- [x] Iniciar pela busca direta (clicar em pessoa) continua criando "Livre" (comportamento atual).

## Fatia 5 — Iniciar Conversa por template (modal 3 etapas, Atendimentos)
**Depende de:** F1 (envio por template + endpoint). · **Pronto quando:** fluxo §11 ponta a ponta.

- [x] Etapa 1: busca no cadastro (clientes + contatos, com estado de janela por telefone) OU
  formulário Nome*/Telefone*/Email; avançar não cria nada ainda.
- [x] Etapa 2: cartões dos templates da loja com badge ✓ Meta (só `status=="aprovado"`);
  "Mensagem livre" só aparece com janela aberta (nota 🟢/🔒 como no mockup).
- [x] Etapa 3: campos variáveis (pré-preenchidos quando conhecíveis — consultora logada, nome do
  cliente), preview ao vivo, validação bloqueante de vazio; "Iniciar conversa" →
  `POST /api/comunicacao/iniciar-conversa`; conversa abre na lista.
- [x] Botão Voltar a partir da etapa 2; toast de sucesso.

## Fechamento (transversal)

- [x] Tenancy em todo endpoint novo (teste cross-loja). Config-gated no transporte.
- [x] Suíte inteira verde + `node --check`.
- [x] Verificação manual (Playwright, navegador real): login, Atendimentos + Chat Interno, chips,
  responsável/urgência, barra de ação, Concluir, Transferir, Exportar, Iniciar Conversa (3
  etapas), Nova Conversa Interna, tema claro E escuro. **4 bugs achados e corrigidos**: tag
  Avulsa/Concluir vazando p/ DM interno sem face externa (ex.: a própria notificação de
  conclusão apareceria concluível de novo — cascata); variável "Nome da loja" não pré-preenchia
  no front (só no backend); rótulo Transferir×Encaminhar/Concluir não reetiquetava ao trocar de
  tela com thread aberta (pane compartilhado). Ver `tests/test_atendimentos_ui.py` p/ cobertura
  automatizada do que é testável sem browser.
- [x] Vera antes de fechar a frente — **1 achado 🟠 corrigido**: `temAtendimentoReal` (guard do
  botão Concluir) não considerava `c.segmento` como o guard irmão `faceExterna` já fazia — uma
  conversa nascida do "Iniciar Conversa" ficava sem Concluir até o contato responder. Corrigido
  + teste novo + reverificado no navegador (Playwright). Suíte segue 1741 verde.
- [x] DEV_LOG (Sessão 156) + spec referenciada. **Parado em "local testado"** — aguardando OK do
  Marcelo p/ promover (commit/push + deploy VPS A/B, autorizado; produção real fica de fora até
  OK à parte); re-ingerir grafo MCP após o merge.

## Fora de escopo (spec §16 / orientação)
Chatbot/IA, campanhas em massa, outros canais, urgência automática. Gravação real de
câmera/áudio no compositor entra como menu + permissão nativa; captura/upload de mídia gravada
pode ficar num incremento seguinte se o tempo apertar (registrar no DEV_LOG o que ficou).
