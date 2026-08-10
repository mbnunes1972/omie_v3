# CLAUDE.md — Orizon Manager | Dalmóbile

Instruções carregadas automaticamente pelo Claude Code. Regras completas de processo estão em
`DEV_RULES.md`; **estado atual e histórico** em `DEV_LOG.md` (comece pela seção `## ⏸️ ESTADO ATUAL`,
no fim); requisitos em `REQUIREMENTS.md`; specs de design em `docs/superpowers/specs/`.

## O que é
Sistema de vendas de móveis planejados (loja Dalmóbile). **Backend** Python puro com `http.server`
(sem framework), SQLAlchemy + **PostgreSQL**. **Frontend** é um único arquivo `static/index.html`
(HTML+CSS+JS inline). Multi-loja/rede (tenancy). Ciclo do projeto em etapas.

## Layout do código (reorganização 2026-07-15, EM ANDAMENTO)
A maioria dos módulos ainda é `.py` na **raiz**, classificados por domínio em `modulos.py` (um teste,
`test_arquitetura_modulos`, garante que nenhum fique órfão e que o ratchet de dependência valha). Três
domínios já viraram **pacote**: `fiscal/`, `integracoes/`, `auth/` (+ o `mod_fin/` antigo). Import de
fora: `from fiscal import mod_nfe`; entre irmãos, relativo: `from . import mapa_fiscal`. Falta empacotar
o `comercial` (15 arquivos) — os 4 módulos da importação de contrato (`mod_contrato`,
`mod_documentos`, `mod_documentos_import`, `mod_marcadores`) seguem na raiz.
**ARMADILHA ao empacotar:** caminho relativo a `__file__` dentro de pacote aponta pra pasta do pacote,
não a raiz — suba um nível (`dirname(dirname(__file__))`). Um `__file__` errado devolve 404/`""` em
SILÊNCIO (foi o que sumiu a página de entrada). `test_caminhos_de_pacote.py` é o ratchet disso.

**Motor 5.0 (decisão 2026-07-16, preparação em andamento, execução adiada):** reestruturação maior e
posterior a esta — `app/core/` + `app/modules/*` (12 domínios) + `app/integrations/` + `app/shared/`,
"mesma cara, motor novo". Só começa a execução real depois que esta v1 (empacotamento incremental acima)
estabilizar em produção; até lá, frente paralela **só de documentação/inventário**, sem mexer em código.
Spec: `docs/superpowers/specs/_geral/2026-07-16-motor-5-reestruturacao-app-design.md`.

## Ambiente e execução
- Use **`python3`** (nunca `python`). WSL/Ubuntu.
- Servidor local: **`./run.sh`** → `http://localhost:8765` (lê `DATABASE_URL` do `.env`, sobe no
  **PostgreSQL**). O **SQLite foi REMOVIDO por inteiro** (faxina 2026-07-23, Sessão 113 — o
  aposentar da S85 e o escape `ORIZON_ALLOW_SQLITE` deixaram de existir): sem `DATABASE_URL`
  Postgres o app explica e sai; `init_db` recusa dialeto sqlite. A **integração Omie também foi
  REMOVIDA** na mesma faxina (cookie de sessão virou `orizon_session`; storage local de projetos
  vive em `integracoes/projetos_store.py`). Em produção `ORIZON_HOST=0.0.0.0`. A mensagem
  `gio: ... Operation not supported` é inofensiva.
- **`static/index.html` é lido do disco a cada request** → mudança de frontend = só **Ctrl+F5**, sem
  restart. Mudança em **Python** (`main.py`/módulos) **exige restart** do servidor.
- **MCP `playwright` (navegador p/ verificação visual):** neste WSL não há Google Chrome instalado
  (canal `chrome`) nem `sudo` interativo pra instalar — o `@playwright/mcp` sem flag tenta esse
  canal e falha (`Chromium distribution 'chrome' is not found`). Fix em `.mcp.json`: `--browser
  chromium` (usa o Chromium que o Playwright já baixa sozinho em `~/.cache/ms-playwright/`, sem
  precisar de path fixo). Exige **reconectar o MCP** (reiniciar o Claude Code) depois de editar
  `.mcp.json` — o processo já conectado não recarrega a config sozinho.

## Testes (rodar ANTES de commitar/mergear)
- Backend: **`python3 -m pytest -q`** (deve ficar tudo verde). Siga TDD nos módulos Python.
  A suíte roda **SEMPRE em Postgres** (faxina 2026-07-23): o conftest deriva o banco de teste
  `orizon_test` do `DATABASE_URL` do `.env` (override: `TEST_DATABASE_URL`). NUNCA aponte pro
  banco de dev/produção — o setup dá `DROP SCHEMA CASCADE` por módulo. Postgres local precisa
  estar de pé (~2m45 a suíte inteira).
- Frontend: **não há teste JS** → verificação manual no navegador. Para sintaxe, extrair o
  `<script>` e rodar `node --check`.

## Git — o que commitar
- Branch `main`. Commits descritivos (pt-BR): `feat(...)`, `fix(...)`, `docs: ...`.
- **NÃO commitar ruído local**: `XML/…`, `.claude/…`, `~$*.docx`, `*.tmp`, `*.bak*` e artefatos
  de dado (`orizon.db` legado, `perfis_config.json`) — o `.gitignore` já cobre tudo isso
  (verificado 2026-07-23: `orizon.db` NÃO é mais tracked; a nota antiga de "working tree sempre
  sujo" ficou obsoleta). **Sempre `git add` só os arquivos da mudança** (nunca `git add .`).
- Push: as credenciais do GitHub estão no Git Credential Manager (do usuário) — o push funciona; se
  falhar por credencial, peça ao usuário rodar `!git push origin main`.

## Fechar uma frente (padrão do projeto)
1. Suíte verde. 2. Atualizar **DEV_LOG** (nova `## Sessão N`) e o spec em `docs/superpowers/specs/`.
3. `git add <arquivos> && git commit`. 4. Merge na `main` (ou já está, se commitou direto). 5. `git
push origin main` (atualiza o "servidor web" = GitHub). 6. **Re-ingerir o grafo MCP** (`ingerir`
com `fonte: "all"`, ou `POST http://localhost:8767/ingest/all`) para o grafo refletir o código novo.
Deploy no VPS: runbook em `DEV_RULES.md`.

## MCP `orizon` (grafo Neo4j) — camada de consulta, NÃO substitui o DEV_LOG
Grafo Neo4j que ingere código + requisitos + banco + decisões (projeto `../mcp-orizon`; container
docker-compose já de pé, config em `.mcp.json`). Responde consultas estruturais: `cobertura`
(requisitos/etapas sem uso), `rastrear_requisito`, `impacto_de`, `decisoes_de`, `buscar`,
`entidades_do_arquivo`. **É derivado do código e local (fora do git)** → fica obsoleto se não
re-ingerir, e some com `docker compose down -v`. Por isso o **DEV_LOG continua sendo a fonte
narrativa** (estado, backlog, decisões+porquê, histórico) — o grafo complementa, não aposenta.
Controle de versão segue 100% no **git**. Após mergear mudança relevante, **re-ingerir** (passo 6
acima). Antes de fechar frente, vale rodar `cobertura`/`rastrear_requisito` para pegar requisito sem
implementação.

## Áreas sensíveis (contexto que evita retrabalho)
- **Contrato/Proposta:** HTML (capa) + Markdown (cláusulas) → **PDF via WeasyPrint** (assets em
  `contrato_template/`). `weasyprint` 69 no user-site do `python3.14`. O `.docx`/LibreOffice foi
  **aposentado nos DOIS**: a proposta usa `mod_contrato.gerar_pdf_proposta` (capa + corpo do modelo da
  loja) desde a migração da capa. `mod_proposta.py`/`modelo_proposta.docx` são **código morto** — nada em
  produção os lê; não use de referência. O **LibreOffice segue indispensável** para IMPORTAR modelo
  (`mod_documentos_import.normalizar`): é o único que achata a numeração automática do Word. Medido num
  `.docx` real (2026-07-15): LibreOffice preserva **63** números de cláusula, `python-docx` só **3**.
  O corpo agora vem do lojista → `_html_corpo` **escapa HTML** e o WeasyPrint usa `url_fetcher`
  confinado ao `contrato_template/` (senão `<img src=http://…>` no modelo vira SSRF, e `file://` vira
  leitura de arquivo do servidor a cada contrato gerado).
- **Modelos de documento por loja:** `documento_modelos` (versão **imutável** — `@validates` no
  `corpo_md` bloqueia alteração de linha persistida; uma ativa por loja+tipo).
  `Contrato.modelo_versao_id` congela a versão que gerou o contrato → regerar um assinado reproduz as
  cláusulas originais. **`NULL` significa duas coisas** e `mod_documentos.versao_para_contrato` as separa
  por `gerado_em`: contrato novo (adota e fixa o ativo) vs **legado** (fica no `contrato_template/
  contrato.md` global — adotar reescreveria cláusula já assinada). A **proposta não versiona** de
  propósito: não é assinada, e reemitir deve pegar correções do modelo. Catálogo de marcadores em
  `mod_marcadores.CATALOGO`, travado contra `mod_contrato._montar_mapping` por teste anti-drift.
  Spec: `docs/superpowers/specs/contrato-documentos/2026-07-15-modelos-documentos-loja-design.md`.
- **Negociação/motor:** cálculo puro em `mod_negociacao.py` / `mod_provisoes.py`; a tela lê do motor via
  `negPreview`/`_aplicarPreviewNaTela`. Dois caminhos de ambientes: **EP07** (`_orcAmbientesAtivos !=
  null`, orçamento moderno, valores do motor) vs **legado**. **`_negBaseValues` nunca é populado**
  (sempre `[]`) — não confie nele; use o motor/preview (`_previewNeg.VBNO`, `neg-subtotal`).
- **Ciclo:** etapas em `mod_ciclo.py` (frontend `ETAPAS_CICLO`). Etapas 5/6 foram eliminadas
  (Orçamento 4 → Contrato 7). `_contrato_assinado` (1ª assinatura) vs `_contrato_totalmente_assinado`
  (ambas).
- **Escopo por projetista:** Consultor vê só os projetos que criou (`projetos_meta.criado_por_id`);
  gerente+ veem todos.
- **Fechamento contábil = provisão diferida no contrato + matching pleno na NF-e (FASE D2, implementada
  2026-07-12, Sessão 70 — supera a decisão da Sessão 65):** no **contrato**, `registro_venda_contrato`
  lança a venda cheia (`1.1.02 × 2.1.06` "Receita a Realizar", Val_Cont) e **as 10 rubricas** (as 9 + Custo
  de Fábrica `2.1.04.06`) são constituídas como **ativo diferido** `1.1.06.0X × 2.1.04.0X` — **sem tocar a
  DRE** (impostos no `1.1.05 × 2.1.04.13`). Na **NF-e**, `reconhecer_despesas_nfe` faz o **matching pleno**:
  reconhece TODA despesa de uma vez (`5.6.0X`, ou `5.1.01` p/ a fábrica) × baixa do ativo `1.1.06.0X`; a
  Provisão `2.1.04.0X` **sobrevive** (paga/reconciliada depois). O evento `faturamento_cmv` foi **retirado**.
  `recebimento_venda` abate `1.1.02` (era `2.1.06`). Divergência real×planejado → sobra `4.4.02`/falta
  `5.6.10` (`resolver_saldo_provisao`, pras 10). `reclassificar_provisao` (`2.1.04.06→2.1.04.14` Outros
  Fornecedores) espelha o ativo `1.1.06.06→1.1.06.14` só na proporção não baixada. **Etapa 21 "Conciliação
  Final"** (`mod_contabil.conciliar_final`, endpoint `.../ciclo/21/conciliar`) resolve à força o saldo
  remanescente das 10 e encerra o projeto com status **`concluido`** (distinto de `fechado`). Projetos
  legados (fluxo antigo) **não migram**. Detalhes: spec
  `docs/superpowers/specs/financeiro/2026-07-12-fase-d2-provisao-completa-conciliacao-final-design.md`.
- **Banco de dados: PostgreSQL, e SÓ ele** (migração 2026-07-15; **SQLite REMOVIDO por inteiro**
  na faxina 2026-07-23 — código de migração raw sqlite3, `DB_PATH`, escape `ORIZON_ALLOW_SQLITE`
  e o SQLite dos testes deixaram de existir; `init_db` recusa dialeto sqlite). Local (WSL),
  produção (**`www.orizonone.com.br`**, VPS `179.197.77.9` — domínio trocado 2026-07-23, o antigo
  `orizonsolution.com.br` vira redirect) **e o dev/pré-homolog `167.88.33.121`** (Postgres 16, dbs
  `orizon`/`orizon_homolog`, envs `/root/orizon-A.env`+`/root/orizon-B.env`). Migração de schema =
  `_migrar_colunas_pg` (ADD/DROP COLUMN idempotentes) + `_seed_loja_padrao`. A suíte roda SEMPRE
  contra Postgres (`orizon_test`, derivado do `.env`; override `TEST_DATABASE_URL`) — FK
  enforcement real pega id fabricado. **Alembic ainda não tem baseline** (Etapa 2, pendente).
  Plano/rationale: `docs/superpowers/specs/_geral/2026-07-15-migracao-postgresql.md`.
- **Segmentação Mercadoria/Serviço + distribuidora Orizon Soluções (decisão 2026-07-16, não implementada):**
  motor fiscal já segrega Val_Cont em mercadoria/serviço (`mod_orcamento_params.SEGMENTACAO_DEFAULT`
  65/35, override por Diretor) e já usa isso pra separar NF-e de NFS-e — mas o **contrato** entregue ao
  cliente ainda não mostra esse split, e uma 2ª pessoa jurídica (**Orizon Soluções**, CNPJ em abertura)
  vai assumir o papel de distribuidora (mercadoria), a loja segue com o serviço. Infra fiscal pra isso **já
  existe** (`Rede.emitente_central_id`, spec de 2026-07-06) — falta só o lado do contrato (2ª CONTRATADA +
  marcadores de valor), gated pela presença do `Emitente` da distribuidora (sem CNPJ ainda = contrato
  continua como hoje). Redação jurídica final e substância econômica real da Orizon Soluções ainda
  pendentes de advogado/contador. Spec: `docs/superpowers/specs/contrato-documentos/
  2026-07-16-segmentacao-distribuidora-contrato-design.md`.

## Dicas de modelo
Para **lógica financeira intrincada** (ex.: cálculo reverso da negociação), o **Fable 5** rende — pode
ser chamado pontualmente via subagente sem trocar o modelo da sessão. Opus/Sonnet dão conta do resto.

## Agente de QA (Vera)
Subagente de teste em `.claude/agents/vera.md` (**local, não versionado** — `.claude/…` é ignorado pelo
git, então cada máquina precisa do arquivo próprio). Cobre backend (pytest/TDD + `test_arquitetura_modulos`),
fluxo de telas do frontend (navegação, escopo/tenancy, tema claro/escuro), consistência de design
(`docs/design/`) e simulação financeira ponta a ponta (fluxo real, não script sintético). Chamar
proativamente antes de fechar frente/mergear área sensível, ou sob demanda ("chama a Vera"). Só reporta —
não commita/mergeia/corrige sozinha.
