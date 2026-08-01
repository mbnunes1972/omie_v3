# Orizon Chat full-page — unificação do thread e eliminação do modal legado (design)

**Data:** 2026-07-31 · **Status:** aprovado para implementação (orientação 2026-07-31) ·
**Evolui:** `_geral/2026-07-27-conversa-projeto-no-orizon-chat-design.md` e a F9 do plano
`plans/2026-07-28-orizon-chat-revisao-meta.md` (o commit `90755c2` tirou a LISTA do modal;
esta spec tira o THREAD — e então o modal morre).

## Demanda (sintoma reproduzido ao vivo)

A tela nova full-page "Chat Interno" lista as conversas, mas **clicar em qualquer item abre o
modal antigo por cima** (`#modal-central-com`), com botões "Nova mensagem", "Fórum da Loja",
"Administração" duplicados nas duas camadas. A tela nova é uma casca: lista sem lógica própria
de thread. Resultado exigido pelo Marcelo: **um caminho só por ação** — nenhum botão duplicado,
nenhuma tela que abre outra versão da mesma coisa.

### As 3 portas de entrada que convergem no modal (linhas de `static/index.html` @ 80ff487)

1. Menu lateral "Orizon Chat" (~553): `onclick="abrirCentralComunicacao()"` — direto no modal.
2. Botão "Orizon Chat" na página do Projeto (~1088): `abrirConversaProjeto()` (~12475) →
   `abrirCentralComunicacao()`.
3. A própria tela nova: itens usam `atendAbrir(id)` (~10196) que faz
   `await abrirCentralComunicacao()` + `ccAbrirConversa(idx)`; `intNova`/`intForum`/`intAdmin`
   (~10114-16) idem.

Toda a lógica funcional mora no bloco `cc*` (~12490-13250), que só renderiza dentro do modal;
`ccMembrosAbrir` (~12672) ainda abre um TERCEIRO overlay (`_popupOverlay`).

## Referência de UX/processo: HuntPilot (visto ao vivo — adaptar, não copiar)

O que adotar no Orizon Chat:

1. **Fila com abas** Novos/Meus/Grupos/Arquivados (F7 já tem) — a fila de triagem entra em
   "Novos" (spec de triagem).
2. **Ciclo de vida explícito** por atendimento (Pendente/Iniciado/Concluído + Transferir), cada
   transição virando **evento inline na timeline**. (Fase 2 — exige "dono do atendimento";
   registrado aqui como direção, fora do escopo desta fatia.)
3. **Eventos inline na timeline** para o que hoje é invisível ou popup: transferência (já é
   mensagem), distribuição, mudança de fase (já é `mensagem_passagem_fase`), entrada/saída de
   membro, documento registrado/encaminhado (spec de ciclo/portas).
4. **Painel lateral de contato/conversa** (não popup): membros, dados, notas. Substitui o
   `_popupOverlay` de Membros.
5. Iniciar conversa por número direto da fila. (Fase 2.)
6. **Número/instância WhatsApp visível no header do thread** (a informação já existe em
   "Números Conectados"; é trazê-la para dentro da conversa).

## Decisões

1. **A tela full-page (`#page-chat`) é a única canônica.** O thread e TODAS as ferramentas do
   modal (nova conversa, fórum, administração, membros, transferência/bloqueador, anexo,
   oficializar por e-mail) são portados para dentro dela.
2. Layout do destino: **lista à esquerda · thread à direita** (padrão HuntPilot) dentro de
   `ochat-scr-atend` e `ochat-scr-interno` — a lista atual encolhe para coluna e o thread abre
   ao lado, sem navegar para fora.
3. **Membros na faixa/cabeçalho da conversa** com painel lateral para gerenciar — elimina o
   `_popupOverlay` de membros.
4. As 3 portas redirecionam para o full-page:
   - menu lateral "Orizon Chat" → `page-chat` na aba Atendimentos;
   - botão do Projeto → `page-chat` posicionado na conversa do projeto, **preservando
     `_alinharLojaAoProjeto`** (sem o alinhamento de loja dá 403/404 em toda mensagem — é
     tenancy, não cosmética);
   - itens das listas → thread na própria página.
5. **Só depois** de tudo portado e testado: remover `#modal-central-com` (~666-829), a família
   `cc*` e `abrirCentralComunicacao`, com busca exaustiva por `abrirCentralComunicacao`,
   `modal-central-com` e cada função `cc*` — zero referências restantes.
6. A migração é de CASCA, não de contrato: os endpoints e a semântica de permissão
   (`pode_ler/escrever_conversa`, mural só gerência, admin read-only, oficializar só gerência)
   não mudam.
7. O bloco novo vive **contíguo e demarcado** no `index.html`
   (`<!-- ═══ CHAT: início ═══ -->` … `<!-- ═══ CHAT: fim ═══ -->`, prefixo único `ochat`/`oc`)
   — preparação para o destacamento físico do Motor 5.0 (spec de portas).

## 1) Mapa de portagem (função legada → destino)

| Legado (modal) | Destino (full-page) |
|---|---|
| `abrirCentralComunicacao` | morre; `goPageChat()`/`ochatIr('atend'\|'interno')` assume |
| `ccCarregarInbox` | `chatAtendCarregar`/`chatInternoCarregar` (já existem) |
| `ccAbrirConversa(idx)`/`ccAbrirConversaPorId` | `ocAbrirConversa(id, …)` — thread na página |
| `ccCarregarMsgs`/`_ccRenderMsg(Projeto)` | `ocCarregarMsgs`/render com eventos inline |
| `ccEnviar` (+anexo, oficializar, transferência) | `ocEnviar` — mesma lógica, ids `oc-*` |
| `ccNovaAbrir`/`ccCriar`/`ccTipoToggle`/… | tela "Nova conversa" dentro do full-page (Chat Interno) |
| `ccForumAbrir`/`ccForumCarregar`/… | aba/tela Fórum dentro do full-page |
| `ccAdminAbrir`/`ccAdminCarregar`/… | tela Administração dentro do full-page (read-only mantido) |
| `ccMembrosAbrir` (`_popupOverlay`) | painel lateral de membros (decisão 3) |
| `abrirConversaProjeto` | mantém nome; passa a abrir o full-page (decisão 4) |
| `atendAbrir`/`intNova`/`intForum`/`intAdmin` | deixam de tocar o modal |
| `convTransfToggle`/`_convCarregarSeletoresTransf`/`convResolver`/`convDestravar` | mantidos, re-apontados aos ids `oc-*` |
| `ccPollBadge`/`ccAtualizarBadgeTotal` | mantidos (badge do menu não depende do modal) |

## 2) Sequência de execução (dentro da fatia)

1. Construir o thread `oc-*` dentro de `#page-chat` (HTML + JS) reutilizando os endpoints.
2. Re-apontar `atendAbrir` (e as listas) para o thread interno.
3. Nova conversa / Fórum / Administração como telas do full-page; re-apontar `intNova`/etc.
4. Painel de membros lateral; re-apontar botão.
5. Redirecionar portas 1 e 2 (menu, projeto — com `_alinharLojaAoProjeto`).
6. Busca exaustiva (`grep`) e REMOÇÃO do modal + `cc*` + `abrirCentralComunicacao`.
7. `node --check` no `<script>`; Vera nas telas (3 caminhos antigos, tenancy/403, tema
   claro/escuro, duplicidade de caminhos/botões).

## Revisão do usuário (2026-07-31, pós-entrega — SUPERA a seção 1 no que conflitar)

1. **Abas idênticas nos DOIS canais**: **Pessoais** (1:1 — o nome escolhido; nem "Individuais",
   nem "Meus") · **Grupos** (grupo + projeto) · **Arquivadas**. O mesmo conceito vale para
   Atendimentos e Chat Interno.
2. **"Pendente" é FILTRO, não estado**: mensagem recebida sem resposta (última mensagem não é
   do viewer — campo `pendente` na inbox). O ciclo de vida do HuntPilot
   (Pendente→Iniciar→Concluir) misturava ideias: filtro é uma coisa; **responder, transferir e
   concluir são AÇÕES do funcionário** no thread.
3. **Arquivar existe de verdade**: flag `ConversaParticipante.arquivada` (por usuário,
   reversível) + endpoint `POST /conversas/<id>/arquivar` + botão no thread. "Concluir" um
   atendimento hoje = arquivar; o status formal com dono do atendimento segue no backburner
   do RF-12. Mural/fóruns não arquivam.
4. **Seletor de segmento sempre com os 7** (não só os presentes na fila).
5. **Camada destacada de botões** (acima das abas) concentra os componentes exclusivos do
   canal: no Chat Interno — Nova mensagem · **Mural** (saiu das abas; badge de não-lidos) ·
   Fórum da Loja · Fórum Orizon · Administração (gerência).
6. Fila de triagem: entra no topo de **Pessoais** (recebida sem dono é pendente por definição).

**Rodada 2 (mesmo dia):**

7. **Trocar de aba abre a primeira conversa da aba** (Pessoais↔Grupos↔Arquivadas, nos dois
   canais) — a lista nunca fica com o painel vazio se houver conversa.
8. **"+ Nova mensagem" eliminado** — modelo WhatsApp: na aba Pessoais do Chat Interno, os
   usuários da loja SEM conversa aberta aparecem listados abaixo das conversas; **clicar no
   usuário abre/cria a 1:1 na hora** com o compositor editável (sem formulário). A criação de
   GRUPO continua, via botão "Novo Grupo" na camada de ações (formulário só-grupo).
9. **Busca padronizada nos dois canais, cada um com seu público**: Chat Interno busca conversas
   E usuários (nome/função); Atendimentos busca a fila (título, projeto, prévia e as entradas
   de triagem por remetente/texto).

**Rodada 3 (mesmo dia):**

10. **Segmento é um SELETOR**, não só etiqueta: coluna `Conversa.segmento` (manual VENCE o
    derivado do tráfego). A triagem INDICA (`segmento_sugerido`, seletor pré-preenchido na
    resolução); entrada sem segmento é a **gerência** quem trata — seletor no header do thread
    (só gerência; endpoint `POST /conversas/<id>/segmento`; vazio limpa e volta a derivar).
11. **"Adicionar Contato"** na camada de ações dos Atendimentos: formulário com nome, WhatsApp/
    e-mail, **motivo (obrigatório — vira evento inline na conversa)**, projeto (opcional) e
    segmento. Cria o contato como **Cliente no cadastro (mais uma fonte de contatos)** e o
    pendura como participante externo na conversa do projeto associado — ou num grupo de lead
    novo. Endpoint `POST /api/comunicacao/contatos`.
    **Revisto na sequência:** o formulário ganhou o campo **Tipo**, que define o destino no
    cadastro — **Cliente · Parceiro (com vínculo ParceiroLoja) · Fornecedor · Convidado** —
    convidado NÃO entra em cadastro nenhum (só participa da conversa; não polui as fontes de
    contato). O evento inline nomeia o tipo.

## Riscos e pontos de atenção

- `ccAbrirConversaProjeto` é chamado também no fluxo `abrir=true` (~15484) — incluir na busca.
- O `cc-badge` do menu e o heartbeat de presença (`ccPollBadge`) NÃO podem morrer com o modal.
- Mural: postar continua só gerência (`pode_ver_todas_conversas` no front espelha o backend).
- Admin view é read-only (`compositor` oculto) — preservar no thread novo.
- `index.html` tem 17k linhas — mudanças cirúrgicas, bloco novo contíguo (decisão 7).
