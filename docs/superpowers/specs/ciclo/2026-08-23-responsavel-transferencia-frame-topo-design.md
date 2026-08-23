# Responsável + Concluir/Transferir + Frame de topo

**Frente:** renomeia "com a bola" → "Responsável"; cada fase do Ciclo ganha um fluxo explícito de
transferência de responsabilidade com aceite ("Receber Projeto"); novo frame fixo no topo da tela
(acima da sidebar) reúne marca/loja, Pendências/Responsabilidades e usuário/tema/Sair — substitui
o que vivia no topo e no rodapé da sidebar. Pedido do usuário, motivado por um caso real (tag
"com a bola" apontando pra pessoa errada num projeto que ainda não tinha passado pela Medição).

**Status:** implementado e mergeado (2026-08-23), branch+PR por fase, suíte verde em cada uma.
Este documento é a referência técnica pós-implementação — não um roteiro pré-código.

---

## 0. Decisões fechadas antes de codificar (não reabrir)

- **Layout do frame:** cobre a tela inteira, acima da sidebar — "OrizonOne" + loja saem do topo
  da sidebar e entram no frame; usuário/tema/Sair saem do rodapé da sidebar e entram no frame.
- **"Concluir" preserva 100% dos gates de cada fase.** Nenhuma regra de negócio existente muda
  (senha gerencial na Aprovação Financeira, parecer na Medição, PDF no Contrato, etc.) — a
  pergunta "deseja transferir?" é um passo que entra DEPOIS que a conclusão específica da etapa já
  foi bem-sucedida.

## 1. O que NÃO mudou (não-objetivos, confirmado no fechamento)

- `mod_ciclo.py` **não foi tocado** — topologia de etapas, `ETAPAS_PRINCIPAIS`,
  `STATUS_CONCLUSIVOS`, `pode_avancar()`, `PREDECESSOR_OVERRIDE` etc. seguem exatamente como
  eram. O espelho no frontend (`ETAPAS_CICLO`/`ETAPAS_PRINCIPAIS`/`PREDECESSOR_OVERRIDE`/
  `STATUS_CONCLUSIVOS` em `static/index.html`) também não foi redefinido — a feature inteira
  entrou como estado ORTOGONAL à topologia (transferência de responsabilidade), nunca mudando
  ordem/gate de etapa.
- Nenhum dos `_renderCard*` (Contrato, Aprovação Financeira, Medição, PE, etc.) teve sua lógica
  interna alterada — ver seção 3 sobre como o "Concluir" foi ligado sem tocar neles.

## 2. Schema (`database.py::CicloEtapa`)

Cinco colunas novas + 4 índices parciais (Postgres não indexa FK sozinho — sem eles a agregação
cross-projeto de Pendências/Responsabilidades faria full scan):

```python
transferencia_status                    = Column(Text, nullable=False, default="nenhuma")
# 'nenhuma' | 'pendente' (destino tem login, aguardando "Receber Projeto") | tema volta a
# 'nenhuma' após o aceite — não existe um terceiro estado persistido "aceita"
transferencia_destino_funcionario_id    = Column(Integer, ForeignKey("funcionarios.id"))
transferencia_destino_terceiro_id       = Column(Integer, ForeignKey("terceiros.id"))
transferencia_solicitada_por_usuario_id = Column(Integer, ForeignKey("usuarios.id"))
transferencia_solicitada_em             = Column(DateTime)
```

Migração idempotente em `_migrar_colunas_pg` (padrão `ADD COLUMN IF NOT EXISTS`).

**Onde mora o "alvo" da transferência:** nas colunas da etapa SEGUINTE (a que ficaria "com a
bola" depois da conclusão), não na etapa que acabou de ser concluída. O código do alvo
(`etapa_alvo_codigo`) é calculado no **frontend** com a mesma lógica que já alimenta a tag
"Responsável" (`ETAPAS_CICLO.find(et => !STATUS_CONCLUSIVOS.has(...))` — primeira etapa
não-conclusiva na ordem) e mandado explícito no payload; o backend só valida que o código é
conhecido e pertence ao projeto, não recomputa "é mesmo a próxima". Risco residual: cosmético
(marcar a etapa errada como "em transferência"), nunca financeiro/gating.

## 3. Backend (`main.py`, `chat/core.py`)

- **`POST /api/projetos/<nome>/ciclo/<codigo>/pos-conclusao`** — `{etapa_alvo_codigo, transferir,
  funcionario_id|terceiro_id}`. Exige que `codigo` já esteja com status conclusivo no banco
  (400 senão) — é o "encaixe depois do sucesso" garantido no servidor, não só confiado à tela.
  - `transferir=false`: só posta aviso no chat (`mensagem_etapa_concluida`).
  - `transferir=true`, destino **com** login: grava `transferencia_status='pendente'`, avisa no
    chat (`mensagem_transferencia_pendente`).
  - `transferir=true`, destino **sem** login (terceiro sem conta — ninguém pra clicar "Receber
    Projeto"): efetiva na hora (`responsavel_funcionario_id`/`_terceiro_id`), avisa como aceite
    automático (`mensagem_transferencia_aceita(..., automatica=True)`).
- **`POST /api/projetos/<nome>/ciclo/<codigo>/transferencia/aceitar`** ("Receber Projeto") — só o
  destino gravado pode chamar (403 pra qualquer outro); efetiva o responsável, limpa o estado,
  adiciona a pessoa ao grupo do chat.
- **`GET /api/me/ciclo/pendencias`** / **`GET /api/me/ciclo/responsabilidades`** — agregação
  cross-projeto pro usuário logado, restrita às lojas que ele acessa (`ator["lojas_ids"]`).
  `responsabilidades` cobre só overrides explícitos (inclusive transferências já aceitas) — **não
  recalcula a cadeia de fallback do responsável efetivo** (Mapa de Atribuições → faixa →
  criador do projeto). Rodar essa resolução pra toda etapa de todo projeto aberto seria caro;
  fora do pedido original desta rodada. Documentado no docstring do endpoint.
- **3 eventos novos de chat** (`chat/core.py`): `etapa_concluida`, `transferencia_pendente`,
  `transferencia_aceita` — via `evento=` (faixa inline na timeline), **não** reaproveitam
  `natureza="transferencia"`/`transferido_para_funcionario_id` (mecanismo do responsável do
  ATENDIMENTO — `Conversa.responsavel_usuario_id` — conceito diferente, usado por
  `transferir_responsavel`/o gate de bloqueador; ver comentário em `chat/core.py`).
- **`GET /ciclo`** expõe `transferencia_status`/`transferencia_destino_nome`/
  `transferencia_pode_aceitar` por etapa; a listagem de projetos ganha `em_transferencia`
  (`_enriquecer_projetos_com_fase_ciclo`).

## 4. Frontend (`static/index.html`)

### 4.1 "Concluir" → "deseja transferir?" — desvio deliberado do plano original

O plano original prevê plugar a pergunta em ~10 funções `_renderCard*` diferentes (uma por tipo
de etapa). Implementado diferente, e melhor: **`carregarCiclo()` é o único ponto por onde TODOS
os fluxos de conclusão já passam** para recarregar a tela (30+ call sites — contrato, aprovação
financeira, medição, PE, operacionais, genéricas). Em vez de tocar em cada um, `carregarCiclo()`
tira um snapshot do `status` de cada etapa ANTES do fetch e compara DEPOIS
(`_cicloDetectarConclusoes`): qualquer etapa que virou conclusiva entre uma chamada e a próxima é
uma conclusão de verdade — dispara `_aposConcluirEtapa(codigo)`, que calcula o alvo e mostra o
prompt. Mesmo comportamento da decisão "preserva os gates" (nenhum gate mudou), um ponto de risco
em vez de dez, cobre qualquer fluxo futuro automaticamente.

`carregarCicloSilencioso()` (refresh em background — ex.: auto-conclusão da etapa 4 ao salvar
orçamento, ou o load inicial da tela) **deliberadamente não participa do diff** — só ações
visíveis no fichário (que passam por `carregarCiclo()`) disparam a pergunta; evita popup
surpresa em bookkeeping silencioso ou no primeiro carregamento do projeto.

- `_cicloRenderTransferPrompt()` — faixa inline logo abaixo do cabeçalho do painel "Etapas do
  Projeto" (não modal). "Sim" troca pelo seletor buscável já existente (`_selBuscavelHtml` +
  `mapaProfissionaisGarantir()`, que já combina funcionário+terceiro e já expõe `funcao_nome` —
  busca por nome OU função de graça).
- **Codificação do destino no seletor:** `_selBuscavelHtml` insere o id do item **sem aspas** no
  `onclick` (`_selBuscavelEscolher('id', 42)`) — só aceita literal numérico. Terceiro é codificado
  como id **negativo** (funcionário positivo); `_cicloTransferConfirmar` decompõe pelo sinal.
- `_tagComABola()` ganha o estado "Em transferência para: X" quando a etapa atual tem
  `transferencia_status` pendente; a coluna "Fase do Ciclo" da lista de projetos mostra
  "Em transferência" no mesmo caso (`.proj-fase-transf-badge`, mesma paleta `--warn` do badge de
  fase crítica já existente).

### 4.2 Frame de topo (`<header class="topframe">`)

- `body` virou `display:flex;flex-direction:column`; novo wrapper `.app-body` é a linha
  flex de `.sidebar`+`.content` que `body` era antes. `.sidebar`/`.topframe` **compartilham** o
  bloco de remapeamento de tokens pra paleta escura (`--surface`/`--text`/etc. →
  `--sidebar-*`) e o `color-scheme:dark` dos `<select>` nativos — o seletor de loja (múltiplas
  lojas), deslocado da sidebar pro frame, preserva a legibilidade que tinha.
- Wordmark "Orizon" + "One" (era "Manager"); nome da loja abaixo dele quando o usuário só tem 1
  loja (`_renderSeletorLoja()` alterna entre texto fixo e o `<select>` de 2+ lojas).
- Usuário/tema/Sair migraram com os MESMOS IDs (`sb-user-btn`, `tema-claro`, `tema-escuro` etc.)
  — só trocaram de container; nenhum JS que os popula precisou mudar.

### 4.3 Pendências / Responsabilidades (`#tf-central`)

- Poll a cada 45s (`_meFramePoll`, mesma cadência do badge de chat não lido `ocPollBadge`),
  chamado também em `_atualizarUIUsuario()`.
- Dropdowns reaproveitam a classe `.proj-status-dd` já existente no app (mesmo padrão visual de
  outros menus da tela de projetos).
- **Achado ao vivo, corrigido durante a implementação:** o app já tem um listener global
  (`document.addEventListener('click', ...)` perto de `projStatusSet`) que fecha QUALQUER
  `.proj-status-dd.open` a cada clique no documento — os botões/toggles que abrem/interagem com
  os dropdowns novos precisam de `event.stopPropagation()` pra não se autofechar no mesmo clique
  (mesmo padrão já usado em `projStatusClick`/`projEditarAbrir`). Um listener de
  fechar-ao-clicar-fora escrito à parte para os dropdowns novos foi removido por ser redundante
  com esse global.
- "Receber Projeto" confirma **inline** dentro do próprio item da lista (sem navegar); se o
  projeto pendente é o que está aberto na tela, a ficha recarrega na hora.
- Lista vazia de Responsabilidades mostra "Sem atribuição definida no momento" — é o pedido do
  item "função sem atribuição" aplicado aqui (a superfície nova mais direta pra essa expressão;
  os dois lugares antigos que já mostravam responsável em branco —
  `_cronoRespBlock`/Mapa de Atribuições — já tinham placeholder próprio: "— selecionar —"/
  "— ninguém —", não precisaram de mudança).

## 5. Verificação

Cada fase rodou a suíte completa (`python3 -m pytest -q`) antes do merge — 2282 → 2293 passed ao
longo da sequência (8 fases: vocabulário, schema+backend de transferência, botão
Concluir/Transferir, endpoints de agregação, frame de topo, painéis ligados). Fases de frontend
(Concluir/Transferir, frame de topo, painéis) verificadas ao vivo via Playwright contra o
localhost, incluindo um teste ponta a ponta com dado real inserido direto no Postgres simulando
uma transferência pendente (badge → dropdown → Receber → Confirmar → responsável efetivado →
badge some → aparece em Responsabilidades).

**Não testado ao vivo** (coberto só por pytest): o fluxo de conclusão de uma etapa gated pesada
(Aprovação Financeira com senha, Medição com parecer+arquivo) disparando o prompt de transferência
de ponta a ponta — o mecanismo central (`_cicloDetectarConclusoes`) foi validado simulando a
transição de status no cliente (etapa Medição), não completando o fluxo real de upload+senha.
