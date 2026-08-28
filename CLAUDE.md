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

## Banco de dados — regras permanentes (revisao de 27/08/2026)

O schema e versionado com Alembic. `docs/db/ESTADO_REVISAO.md` registra o estado.

R1  Nenhum DDL fora de migration, em nenhum ambiente, nem para teste.
    O `_migrar_colunas_pg` do database.py esta congelado: nao recebe coluna nova.
R2  Toda coluna terminada em `_id` tem FK declarada — ou uma linha em
    docs/db/excecoes.md explicando por que nao tem (FK externa, polimorfica,
    ou codigo de negocio).
R3  Toda FK tem indice na coluna filha, criado na mesma migration.
    O PostgreSQL indexa o lado do pai automaticamente e nunca o do filho.
R4  `docs/db/schema.sql` e `docs/db/ERD.mmd` sao regerados no mesmo commit
    da migration que os alterou.
R5  Migration so chega a producao depois de rodar sobre um clone real,
    com o tempo de execucao medido.
R6  Migracao de schema e migracao de dados nunca compartilham a mesma revisao.
R7  `alembic stamp` NUNCA e comando de conserto. Ele declara em que ponto o
    banco esta; declarar errado quebra tudo que vem depois. So use apos
    verificar que o schema realmente corresponde aquela revisao.
R8  Duas variaveis, dois consumidores: `DATABASE_URL` (com +psycopg2) para o
    Alembic e o SQLAlchemy; `PGURL` (sem) para psql e pg_dump.
R9  Lancamento automatico resolve centro de custo por CODIGO dentro da arvore
    do proprio owner, nunca por id — cada loja tem sua propria arvore.
R10 Toda migration que cria indice ou constraint tem declaracao
    equivalente no modelo, no mesmo commit. Migration e modelo
    divergentes fazem o autogenerate propor desfazer o que a
    migration fez.
R11 Indice, constraint ou server_default criado fora do modelo e divida
    que o autogenerate vai propor desfazer. Toda estrutura no banco tem
    declaracao equivalente no modelo.
R12 Nenhum teste ou script carrega id de revisao do Alembic escrito a mao
    (nome de migration tipo "0009", hash de candidato a baseline etc.).
    Resolva sempre pelo ScriptDirectory (script.get_heads(),
    get_revision(head).down_revision) — nunca uma constante mantida por
    humano. E' a mesma doenca por tras dos 3 achados desta etapa
    (fk_convmsg_documento_ref, ix_ciclo_etapas_responsavel_terceiro, e a
    constante _STAMP_PONTE_PRE_B3 que tests/_schema_util.py substituiu):
    estado duplicado em dois lugares, com um humano encarregado de manter
    sincronizado — e ninguem lembra na hora certa.
R13 Rename de conta do plano padrao (ou de no de centro de custo) vai em
    migration, nunca numa lista _RENOMEIA_* no codigo. `seed_plano()` e
    `seed_centro_custo()` so criam o que falta, por desenho — nunca
    corrigem o que ja existe. Foi assim que 1.1.09/2.1.09 divergiram entre
    rede (semeada antes do rename) e loja (semeada depois).
R14 Decisao sobre o plano de contas expressa so no codigo (edicao de
    `PLANO_PADRAO`, `CENTRO_CUSTO_PADRAO` ou de tabela de classificacao
    como `CLASSIFICACAO_GRUPO5_V1`) nao alcanca owner ja semeado — mesma
    causa da R13. Toda mudanca nessas estruturas exige migration de dado
    no MESMO commit. `tests/test_gabarito_migration_x_seed.py` e quem
    faz cumprir: compara o que a cadeia de migrations semeia contra o que
    o codigo produziria para um owner novo, owner a owner, codigo a
    codigo — encontrou 5.5.05 (natureza_custo) alem dos 2 renomes na
    primeira rodada.
R15 Migration de dado que semeia gabarito (arvore de centro de custo, plano
    de contas, classificacao) NUNCA enumera owner por id fixo. Owner e'
    polimorfico (owner_tipo+owner_id, sem FK) — uma lista fixa grava dado
    pra owner que nao existe num ambiente e deixa de fora owner real de
    outro, os dois em silencio (achado real: `redes`/`lojas` tem 1 owner
    na Integracao e 10 na Homologacao, nenhum batendo com os 3 do
    localhost). Deriva sempre de `SELECT id FROM redes`/`lojas` do proprio
    ambiente, chamando a MESMA funcao de gabarito que a criacao de loja usa
    (`mod_contabil.aplicar_gabarito_completo`) — uma implementacao, dois
    pontos de entrada. `tests/test_gabarito_migration_por_owner_dinamico.py`
    prova isso com owners sinteticos que nao existem no localhost.

    A `46a93cfd591b` invoca CODIGO VIVO (`aplicar_gabarito_completo`, que le
    `PLANO_PADRAO`/`CENTRO_CUSTO_PADRAO`/`CLASSIFICACAO_GRUPO5_V1` de
    `mod_contabil.py` em tempo de execucao) de proposito, nao por atalho.
    Consequencia aceita: a cadeia semeia o gabarito de HOJE (o que o codigo
    diz no momento em que `alembic upgrade head` roda), nao o de quando
    `46a93cfd591b` foi escrita — rodar a mesma migration em datas diferentes
    pode semear owner novo com conteudo diferente, se `PLANO_PADRAO` tiver
    mudado no meio.

    Isso e' aceitavel pra DADO DE GABARITO e seria inaceitavel pra SCHEMA:
    - Gabarito e' um TEMPLATE de decisao de negocio deliberadamente mutavel
      (R14 ja estabelece isso) — o correto pra um owner que nasce amanha e'
      a classificacao decidida ATE amanha, nao uma decisao ja revogada.
      Congelar o gabarito na migration (como `c1ab3f8007c4` fez, por
      necessidade — nao dava pra chamar codigo vivo antes de existir a
      funcao) e' exatamente o que causou os 3 residuos do item 1: duas
      copias da mesma coisa, uma trava no tempo, divergindo em silencio.
      Chamar o codigo vivo fecha essa classe de bug pra sempre nos owners
      novos (o `test_gabarito_migration_x_seed.py` continua cobrindo os
      owners ja existentes/frozen — ver nota no proprio teste).
    - Schema NAO pode fazer isso: uma migration de schema descreve o DDL
      exato que foi aplicado NAQUELA revisao — reconstruir o historico
      (rodar a cadeia do zero, bisectar um bug, auditar um estado
      intermediario) tem que reproduzir o schema de ENTAO, nao o modelo
      ATUAL. E' por isso que autogenerate congela `op.create_table(...)`
      com colunas explicitas em vez de chamar `Base.metadata.create_all()`
      — se uma migration de schema importasse os modelos vivos, o
      resultado de rodar a cadeia dependeria do commit atual do
      repositorio, nao da revisao sendo aplicada, e o historico deixaria
      de significar nada.
R16 Todo semeador de gabarito (migration OU script) roda uma varredura de
    orfaos logo depois — `mod_contabil.varrer_orfaos_gabarito`. Motivo:
    `c1ab3f8007c4` grava gabarito incondicional pra rede,1/loja,1/loja,3
    (congelada, nao mexe mais nela — R13), mesmo num ambiente onde algum
    desses 3 nao existe de verdade. Owner e' polimorfico (R15) — a linha
    orfa nao tem FK que a acuse. So remove o que nao tem `lancamento` nem
    outra linha (`conta`/`centro_custo`) apontando pra ele; o resto fica
    retido e reportado, nunca apagado (orfa com movimento e' problema de
    DADO). `scripts/aplicar_gabarito.py` e `tests/test_orfaos_gabarito.py`
    cobrem os dois lados.

Caso real que justifica a R1 (nao curiosidade): contratos.assinatura_canal
e aprovacoes_pe.assinatura_canal tinham server_default='interno' no banco
sem nenhuma migration correspondente e sem o modelo declarar. Alguem rodou
um ALTER COLUMN direto, fora do fluxo do Alembic, em algum momento nao
documentado. So foi descoberto porque o autogenerate da TAREFA_ALINHAR_
MODELOS.md acusou a divergencia (revisao de 27/08/2026). Sem R1, esse tipo
de alteracao nao deixa rastro nenhum — nem em migration, nem em commit.

Segundo caso real que justifica a R1: conversa_mensagens.documento_ref_id
tinha a FK nomeada fk_convmsg_documento_ref no banco, sem o modelo declarar
esse nome (ForeignKey("ciclo_documentos.id") sem `name=`). Origem rastreada
desta vez: veio do `_migrar_colunas_pg` (DO-block com ADD CONSTRAINT
nomeado), nao de um ALTER manual sem rastro — mas o efeito e o mesmo, porque
`_migrar_colunas_pg` esta congelado (R1) e nunca foi replicado pro modelo.
So apareceu ao comparar constraint-a-constraint contra uma baseline gerada
do zero (revisao B1/B2 de 27/08/2026) — o autogenerate contra o banco
principal nunca acusou, porque sem `name=` no modelo ele nao compara nome
de FK, so estrutura. Renomeado na migration 0008 para o nome padrao do
Postgres (conversa_mensagens_documento_ref_id_fkey), alinhando com o que a
baseline gera. A entrada que recriava fk_convmsg_documento_ref saiu de
`_migrar_colunas_pg` no mesmo commit (27/08/2026) — ela roda em todo boot
via init_db(), e teria recriado a FK com o nome velho a cada restart,
desfazendo a 0008 silenciosamente (o EXCEPTION duplicate_object so' pega
nome igual, nao estrutura igual — o resultado seria uma FK duplicada, nao
um no-op). Confirmado por tests/test_schema_boot_estavel.py, que compara
o schema produzido por `alembic upgrade head` contra o produzido por
`init_db()` e pegou a duplicata antes da remocao.

Terceiro caso, mesma classe: `_migrar_colunas_pg` tinha `CREATE INDEX IF NOT
EXISTS ix_ciclo_etapas_responsavel_terceiro ON ciclo_etapas
(responsavel_terceiro_id)` — nome sem o sufixo `_id`, duplicando
ix_ciclo_etapas_responsavel_terceiro_id (que o `index=True` do modelo ja
gera). Confirmado via pg_index (colunas cobertas, nao nome) que as duas sao
o mesmo indice em cima da mesma coluna. Achado tambem pelo
test_schema_boot_estavel.py. A entrada saiu de `_migrar_colunas_pg` e a
migration 0009 dropa a duplicata nos bancos que ja a tinham — no MESMO
commit, senao um desfaz o outro no proximo boot.

### Divida de Onda 2 — os 3 ciclos de FK bidirecional (registrado 27/08/2026)

O baseline Alembic (B1/B2) so' consegue ordenar a criacao das 82 tabelas com
`use_alter=True` em um FK de cada par abaixo, porque os 3 sao referencia
bidirecional entre duas tabelas — quase sempre sinal de redundancia de
modelagem, nao de necessidade real:

  usuarios.funcionario_id <-> funcionarios.usuario_id
      1:1 modelado nos dois lados. Precisa de decisao de modelagem: qual
      lado e' a fonte de verdade.
  redes.emitente_central_id <-> emitente.rede_id
      redes.emitente_central_id esta 100% NULA no banco (auditoria Dia 0) —
      candidato forte a remocao. Sem ela, o ciclo desaparece na origem.
  orcamentos.parcela_id <-> parcela_projeto.orcamento_id
      parcela_id foi criada pela migration 0002 sobre uma relacao que ja
      existia no sentido inverso (parcela_projeto.orcamento_id). Avaliar se
      as duas pontas ainda servem, ou se uma e' redundante.

`use_alter=True` resolve a CONSTRUCAO (a baseline consegue criar as tabelas).
Nao resolve a MODELAGEM — os 3 ciclos continuam sendo o que sao. Revisitar
quando a Onda 2 chegar.
