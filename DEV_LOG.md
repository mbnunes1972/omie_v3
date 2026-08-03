# DEV_LOG.md — Diário de Desenvolvimento
## Orizon Manager | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-07-11 (sessão 62 — **RESET: Perfis de acesso CONFIGURÁVEIS por loja (rev3)**. Substitui o modelo hardcoded de 4 perfis pela tabela `perfil_acesso` por loja (3 padrão Master/Gerencial/Operador + custom), com **base+módulos**: acesso a módulo/painel vem do `modulos_json`; capacidades finas = base + override por perfil; `perfis.py` virou adaptador com registro do DB. Painel **Perfis de Usuário editável** (Master) com seletor Perfis|Funções + **Mapa de Funções** (Função→perfil padrão). **Step-up por senha** ao acessar módulo fora do perfil (módulos bloqueados com cadeado no hub → clique pede senha de quem tem, grava `LogAcessoDelegado`). Migração `perfis_v4_2026` (`diretoria→master`, `consultor/suporte→operador`) + seed por loja, idempotentes. Ampla **revisão de design** (modais/campos theme-aware: regra global de select/textarea, fim dos `#111d11`; abas/pills por sombra; Sair no rodapé; Config junto do Admin; cronograma com coluna D0/Data prevista). Suíte **846 passed**. Merge na `main` + deploy no VPS (banco preservado). PENDENTE: step-up dos painéis Admin/Config (semântica de elevação) e o legado `contrato_editar.py:61`. Antes: sessão 44 — manutenção de ambiente + política do MCP. Renomeação do diretório pai `estudo_de_ia → desenvolvimento` (o repo já vinha renomeado `Omie_V3 → Orizon Manager`, commit `c8eb350`); corrigidos os mounts do `.mcp.json` para `E:/2026/desenvolvimento/...` e reconectado o servidor MCP `orizon` (validado com `cobertura`/`ingerir`). **Decisão de processo:** o grafo MCP é **camada de consulta**, não substitui o DEV_LOG nem o git — DEV_LOG segue como fonte narrativa versionada; adicionado o passo de **re-ingestão** ao ritual de fechar frente (docs `CLAUDE.md`/`DEV_RULES.md`). Push da `main` para o `origin` **funciona** (feito nesta sessão) — a antiga pendência de push foi removida. Suíte permanece **395 passed** (sem mudança de código de app). Antes: sessão 43 — padronização da tela de Negociação + "Valor Total do Contrato" editável (cálculo reverso); sessão 42 — lote de ajustes de teste em produção (395 passed))

### [ESTADO] O que está funcionando
- App rodando em `http://167.88.33.121:8765` (servidor DEV) e `http://127.0.0.1:8765` (local)
- Sistema de autenticação completo: login, logout, sessões via cookie
- **12 perfis (`perfis.py`, fonte única):** 10 operacionais — Diretor (50%), Gerente de Vendas (20%), Consultor (10%), Gerente Administrativo/Financeiro, Assistente Logístico, Conferente, Supervisor de Montagem, Assistente Administrativo, Projetista Executivo, Medidor — + 2 **administrativos de tenancy** (F2): `super_admin` e `admin_rede` (gerenciam estrutura, sem capacidade operacional). Permissões centralizadas: `desconto_max`, `ver_parametros`, `autorizar`, `gerir_usuarios`, `aprovar_financeiro`, `registrar_medicao`, `aprovar_medicao_reprovada` + tenancy (`gerir_redes`/`gerir_lojas`/`editar_dados_loja`). Perfil técnico `admin` **aposentado** (via `perfis_v2_2026`). Detalhes em `docs/USUARIOS.md`.
- **Usuários-exemplo (`seed.py`, 1 por perfil):** `pdm2026` (Diretor), `lds2026` (Ger. Vendas), `mds2026` (Consultor), `gaf2026` (Ger. Adm/Fin), `med2026` (Medidor) + demais — **senhas de exemplo, trocar antes de produção**.
- **Painel Admin → Usuários:** CRUD (criar/editar perfil/telefone/ativar-desativar/resetar senha), acesso para Diretor ou Gerente Adm/Financeiro; `nav-07` gateado por `pode_gerir_usuarios`.
- Módulo Clientes completo com ViaCEP, máscaras, CRUD, unicidade
- **Auto-sync Omie:** ao criar cliente, tenta registrar no Omie em background thread; grava `omie_sync_status` (`ok`/`pendente`/`erro`) + `omie_sync_erro` na tabela `clientes`
- Módulo Parceiros completo com tipos, comissão padrão, CRUD
- **Área administrativa (page-07) — console de 3 níveis (F2):** Plataforma (redes + lojas avulsas + admins de rede) → Rede (lojas + diretores) → Loja (dados da loja editáveis incl. testemunhas/CPF · usuários da loja · parceiros), com breadcrumb + drill-down e aterrissagem por perfil. Mantém a fila de sync Omie (clientes pendente/erro, botão "Tentar").
- Projeto vinculado a cliente obrigatório
- **Lista de projetos redesenhada:** tabela com Status | Data | Projeto | Cliente | Último Orçamento
  - Duplo clique ou botão "Abrir →" entra no projeto
  - Filtro de texto simultâneo por nome do projeto, nome do cliente e CPF
  - Filtro multi-seleção de status (OR lógico)
  - Dropdown inline para alterar status direto na lista
- **Pipeline de status por projeto:** `quente` / `morno` / `frio` / `convertido` / `perdido`
  - `convertido` setado automaticamente ao aprovar orçamento (via `bloquear_projeto`)
  - `perdido` grava `perdido_em` automaticamente
  - Botão de status na page-02 (cabeçalho da negociação)
- EP-07 completo: upload, pool, orçamentos, cálculos, desconto individual, limites
- Toggle "Incluir custos adicionais" corrigido: `_incluirCustos` como fonte de verdade global
- **Total Flex (US-14) completo:** `mod_fin/total_flex.py` — juros compostos por dias reais
- **Último orçamento ativo** persistido por projeto em localStorage; ao abrir projeto vai direto para o orçamento que estava ativo na última visita
- **Módulo Ciclo (EP-10):** aba "Ciclo" na page-02 com 20 etapas em 2 colunas; etapas 1-5 auto-completas para projetos com negociação ativa
- **Módulo Contrato (EP-10):** `mod_contrato.py` gera o `.docx` a partir do template por marcadores `modelo_contrato_mapeado.docx` (`_substituir_marcadores` + `_preencher_grade`) → PDF via LibreOffice; **número do contrato** `INS-AAAA-MM-DD-SEQ` no cabeçalho + data; grade de parcelas valor+data (sem ordinal, traços nos vazios); `[TOTAL_CONTRATO]`; 2º signatário = cliente; **empresa/CNPJ, código do número e testemunhas vêm da loja (F3)**, com snapshot por contrato; hash SHA-256 de assinatura
- **Contrato editável protegido:** `.docx` sai somente-leitura com regiões editáveis só nos valores (`permStart/permEnd` + `documentProtection`); botão "Editar contrato" (gate gerencial auditado) abre no Word/LibreOffice e regera o PDF a cada salvamento (watcher `contrato_editar.py`)
- **Status contrato:** `rascunho` → `para_assinatura` → `assinado`; badges CSS dedicados
- **Aprovar Orçamento reformulado:** modal exibe dados do cliente, CPF/endereço de instalação obrigatórios se vazios, condições de pagamento pré-carregadas; salva `valor_negociado` e `forma_pagamento` no orçamento antes de gerar contrato
- **Pós-aprovação:** ao aprovar (etapa 6), a negociação inteira fica **somente-leitura** (`aplicarBloqueioNegociacao`, cobre `#sb-params` + `#page-02`, exceto o `#ciclo-panel`); botões na tela de negociação: **"✍ Assinar Contrato"** + **"✎ Rever Orçamento"** (senha gerencial → `POST /ciclo/desfazer_aprovacao`, libera a edição)
- **Negociação — formas de pagamento por modalidade:** seletores de forma da entrada/parcelas (cartão/aymoré/VP/TF/à vista); modalidade **À Vista** com entrada (valor+data+forma) e liquidação automática; calendário nativo clicável em todos os campos de data; formas levadas ao contrato (`[FORMA_ENTRADA]`, `[TIPO]`)
- **Assinatura do contrato:** bloco de assinaturas normalizado (nome numa linha, CPF/CNPJ embaixo, mesma fonte) via `scripts/organizar_assinaturas.py`/`normalizar_assinaturas.py`
- **UX:** diálogos nativos substituídos por popups estilizados (`confirmarPopup`/`avisoPopup`/`pedirCredenciaisGerente`); `index.html` servido com `Cache-Control: no-cache`
- **Ciclo — gating de sub-etapas:** sub-etapas (`11a`–`11e`, `17a`) desbloqueiam junto com a etapa-mãe (`mod_ciclo.etapa_pai`)
- **Aprovação financeira (etapas 8 e 11d):** exige login+senha de quem tem `aprovar_financeiro` (Diretor ou Ger. Adm/Fin; gerente de vendas não); auditado em `log_acoes_gerenciais`
- **Workflow de Medição (etapas 9 e 10):** etapa 9 = upload da solicitação + senha do medidor; etapa 10 "Medição" = parecer (Aprovado/Reprovado/Parcial+ambientes) + planta promob; **Reprovado em 2 passos** (medidor registra → fica em andamento; Gerente Vendas/Adm-Fin/Diretor anexa doc do cliente + senha → libera). Modelo `Medicao`; arquivos em `PROJETOS/<nome>/medicao/`; guard impede fechar 9/10 pelo toggle genérico
- **Auto-load projetos** ao iniciar app (`DOMContentLoaded → projCarregar()`)
- **LibreOffice gracioso:** `LibreOfficeIndisponivel` salva `.docx` e avança status sem travar o fluxo
- **Parâmetros de negociação — dois escopos (sessões 16 + 20):** os **estruturais** (incluir custos, comissão do arquiteto, fidelidade, custo viagem, brinde, carga tributária) valem para o **projeto inteiro** (`projetos_meta.parametros_json`, compartilhados por todos os orçamentos); **desconto** (global em `orcamentos.margens` + por ambiente em `orcamento_ambientes.desconto_individual_pct`) e **pagamento** são **por orçamento**. Migrações automáticas (`projeto.json`→orçamento e estruturais→projeto)
- **Snapshot completo da negociação (`orcamentos.negociacao_json`):** modalidade, formas, nº de parcelas, entrada e **datas manuais do Total Flex** salvas e reproduzidas ao reabrir; **salvamento garantido ao aprovar** (aprovação bloqueada se falhar; total 0 não sobrescreve) (sessão 17)
- **Trava total pós-assinatura:** a partir da 1ª assinatura, UI esconde Salvar/Parâmetros/Ambientes/Novo Orçamento/Rever (mantém "Assinar Contrato" só enquanto falta a 2ª parte) e backend recusa **403** as mutações (`_contrato_assinado`); na 2ª assinatura, status terminal **"🔒 Fechado"** (sessão 19)
- **Contrato alinhado ao template reestruturado:** `[NOME_EMPRESA]`/`[CNPJ_EMPRESA]` (valores reais), CPFs separados (cliente + 2 testemunhas), cabeçalho robusto a marcadores fragmentados em runs (inclui text-boxes com nº/data) (sessão 18)

### [EP-07] Estado atual do versionamento de orçamentos

**Backend — 100% funcionando:**
- Tabelas: `pool_ambientes`, `orcamentos`, `orcamento_ambientes`
- Criar projeto → Orçamento 1 criado automaticamente ✓
- Upload XML → apenas sistema pool (EP-07); `/ambientes/adicionar` somente para modo legado ✓
- Arquivo salvo no disco SOMENTE após `db.commit()` bem-sucedido (4 endpoints) ✓
- Detecção de duplicata (Sobrescrever / Nova versão) ✓
- Painel pool com status `incluido: true/false` ✓
- Adicionar/remover ambiente com recálculo ✓
- Criar novo orçamento ✓ | Renomear: `PUT /projetos/<nome>/orcamentos/<oid>` ✓
- Cards de projeto: `n_ambientes`/`n_selecionados` lidos do pool via `_enriquecer_projetos_com_pool()` ✓

**Interface — 100% funcionando:**
- Barra de orçamentos com abas, troca de aba, renomear inline ✓
- Painel "Ambientes ▾" com checkbox incluído/disponível ✓
- Upload XML: nenhum arquivo salvo em disco antes da confirmação do usuário ✓
- Tecla Esc fecha qualquer modal ativo sem salvar ✓

**Cálculo de negociação EP-07 — 100% funcionando:**
- Parâmetros (margens, desconto, custos, impostos): compartilhados por projeto ✓
- Base de cálculo: sempre os ambientes do orçamento ativo ✓
- Sequência: `bruto` (gross-up) → `avista` (−desc_global% −desc_individual%) → `final` (÷(1−fin%))
- `neg-subtotal` = bruto gross-up | `neg-avista` = à vista | `neg-total` = com financiamento ✓
- **Desconto individual por ambiente** (EP-07): coluna "Desc.%" editável na tabela ✓
  - Chave em `_descIndividual`: `'ep07_'+pa.id` (não colide com legado por nome de arquivo)
- Modal de parâmetros EP-07: painel de apoio considera desconto individual por ambiente ✓
- Discriminação por ambiente EP-07: usa `_orcAmbientesAtivos` + desconto efetivo combinado ✓
- Cartão/VP: gross-up via `_acrescimoFin` na tabela ✓
- Aymoré/TF: `_ep07DistribuirFinanciado(totalCliente, totalAvista)` ✓
- Painéis de pagamento atualizam ao trocar aba ou alterar parâmetros ✓
- **Limite de desconto total: 35%** sobre bruto original dos XMLs ✓
  - Bloqueia save de parâmetros; reverte desconto individual em tempo real

### [PENDENTE]
- **Sub-projeto 3 — Versionamento de documentos:** novos documentos criam versão; nunca sobrescrevem nem permitem apagar versões anteriores (último item do pedido das sessões 17–19)
- **Plataforma multi-tenant (programa de 4 fases):** o "configurador de lojas" virou um programa `Plataforma → Rede → Loja` com isolamento total. **F1 (fundação de dados) CONCLUÍDA na sessão 21** (tabelas `redes`/`lojas`/`parceiro_lojas`, colunas de tenant, migração `tenancy_v1_2026` + loja seed). **Pendentes:** F2 (perfis `super_admin`/`admin_rede` + CRUD de redes/lojas + UX de abrangência de parceiro); F3 (`mod_contrato.py` puxa dados da loja em vez das constantes `_NOME_EMPRESA`/`_CNPJ_EMPRESA`/`_TESTEMUNHAS` com CPF placeholder + numeração por loja); F4 (isolamento — escopo por loja/rede em todas as queries). Spec/plano em `docs/superpowers/`.
- Módulo Clientes e Parceiros vinculados a orçamentos (planejado)
- **Trocar as senhas de exemplo do `seed.py`** (10 usuários) antes de produção — pelo Painel Admin → Usuários (perfil técnico `admin` foi aposentado)
- Refinar espaçamento visual do bloco de assinaturas no PDF (validado por estrutura, não por render — LibreOffice ausente no dev local)
- **LibreOffice no VPS:** verificar disponibilidade; app funciona sem ele (fallback .docx), mas PDF é o ideal
- **Deploy:** projetos já totalmente assinados em produção podem ficar sem o status "fechado" (o backfill foi feito só no DEV DB) — reassinar não é necessário; setar via banco se quiser consistência
- (Resolvido na sessão 17) `salvarOrcamento()` agora persiste o snapshot completo da negociação

### [DECIDIDO]
- Pool de ambientes permanente por projeto (XMLs nunca deletados)
- Upload EP-07: somente `/pool` (sem `/ambientes/adicionar`) — arquivo salvo após commit
- Pergunta Sobrescrever/Nova versão = apenas quando usuário quer ATUALIZAR o arquivo XML
- Múltiplos orçamentos paralelos, todos editáveis
- Desconto total máximo: 35% de (bruto_original − líquido) / bruto_original
- Banco: SQLite + SQLAlchemy
- Servidor DEV: `167.88.33.121:8765`
- GitHub: `https://github.com/mbnunes1972/orizon-manager`
- Auto-sync Omie ao criar cliente: background thread (não bloqueia HTTP); falha silenciosa → fila no painel admin
- Status "convertido" nunca via dropdown — apenas automático ao aprovar orçamento
- Último orçamento ativo por projeto: localStorage (não backend) — suficiente para uso em loja fixa
- `projetos_meta` (banco): metadados de pipeline; `PROJETOS/*/projeto.json` ainda é a fonte de dados do projeto

### [CONTEXTO] Arquivos e variáveis chave
**Arquivos principais:**
- `main.py` — servidor HTTP, todas as rotas; `_enriquecer_projetos_com_pool()` e `_enriquecer_projetos_com_status()` enriquecem listagens; `do_PATCH` para status; `_tentar_sync_omie()` para sync Omie
- `database.py` — SQLAlchemy: `Usuario`, `Sessao`, `LogAutorizacao`, `LogAcaoGerencial`, `Cliente`, `Parceiro`, `PoolAmbiente`, `Orcamento`, `OrcamentoAmbiente`, **`Projeto`** (projetos_meta), `CicloEtapa`, `Contrato`, `ContratoAssinatura`, **`Medicao`**; migrações de dados em `_run_migracoes` (guard `_tabela_existe`); `Usuario.limite_desconto`/`pode_ver_parametros` delegam a `perfis.py`
- `perfis.py` — **fonte única dos 10 perfis e permissões** (`PERFIS`, `pode/desconto_max/rotulo/existe/slugs`)
- `mod_usuarios.py` — validadores puros do CRUD de usuários
- `mod_ciclo.py` — gating do ciclo (`pode_avancar`, `etapa_pai`, `etapa_anterior`), `ETAPA_NOME` (10 = "Medição"), `ETAPAS_APROVACAO_FINANCEIRA` (8, 11d), `exige_aprovacao_financeira`
- `mod_medicao.py` — `PARECERES` + `validar_parecer`
- `mod_omie.py` — `_listar_projetos()` retorna `cliente_cpf`; `bloquear_projeto()` seta status "convertido"; `_projeto_path()`
- `static/index.html` — frontend SPA completo
- `PROJETOS/*/projeto.json` — dados persistidos de cada projeto (legado; EP-07 usa banco); `PROJETOS/<nome>/medicao/` guarda os arquivos da medição

**Perfis e capacidades (sub-projeto 2/3/4):** ver tabela em `docs/USUARIOS.md`. Capacidades: `autorizar` (desconto: diretor+ger.vendas), `gerir_usuarios` (diretor+adm/fin), `aprovar_financeiro` (diretor+adm/fin), `registrar_medicao` (medidor+diretor), `aprovar_medicao_reprovada` (vendas+adm/fin+diretor).

**Tabelas/rotas novas (sub-projetos 2–4):**
- `medicoes` (1 por projeto); migração de dados `perfis_v2_2026` (gerente→gerente_vendas, admin→diretor)
- `GET/POST/PATCH /api/admin/usuarios` (gate `gerir_usuarios`)
- `POST /api/projetos/<nome>/medicao/{solicitacao,parecer,decisao-reprovado}` + `GET .../medicao` + `GET .../medicao/arquivo/<tipo>`
- `PATCH /ciclo/<codigo>`: gate financeiro (8/11d) e guard de medição (9/10)

**Tabelas novas (sessão 6):**
- `projetos_meta` — `nome_safe` PK, `status`, `status_at`, `perdido_em`
- Campos novos em `clientes` — `omie_sync_status`, `omie_sync_erro`, `omie_sync_at`

**Rotas novas (sessão 6):**
- `GET /api/admin/omie-sync` — lista clientes com sync pendente/erro (role admin)
- `POST /api/admin/omie-sync/<id>/retry` — reprocessa sync de um cliente (role admin)
- `PATCH /api/projetos/<nome>/status` — altera status do projeto (quente/morno/frio/perdido)

**Tabelas novas (sessão 7):**
- `ciclo_etapas` — `projeto`, `numero`, `status`, `concluido_em`, `concluido_por`
- `contratos` — `projeto`, `orcamento_id`, `status`, `arquivo_path`, `arquivo_tipo`, `gerado_em`
- `contrato_assinaturas` — `contrato_id`, `tipo` (cliente/empresa), `hash`, `assinado_em`, `assinado_por`
- Campo novo em `orcamentos` — `valor_negociado`, `forma_pagamento`

**Rotas novas (sessão 7):**
- `GET /api/projetos/<nome>/ciclo` — retorna 20 etapas (auto-cria 1-5 se negociação presente)
- `PATCH /api/projetos/<nome>/ciclo_etapas` — marca etapa como concluída/pendente
- `POST /api/projetos/<nome>/contrato` — gera contrato (PDF ou .docx fallback)
- `PATCH /api/projetos/<nome>/contrato` — atualiza status do contrato
- `POST /api/projetos/<nome>/contrato/assinar` — registra assinatura com hash SHA-256
- `GET /api/projetos/<nome>/contrato` — retorna metadados do contrato (inclui `arquivo_tipo`)
- `GET /api/projetos/<nome>/contrato/pdf` — serve o arquivo (PDF ou .docx com Content-Type correto)
- `PATCH /api/orcamentos/<id>/valor` — salva `valor_negociado` e `forma_pagamento`
- `POST /api/projetos/<nome>/ciclo/desfazer_aprovacao` — valida gerente e reseta etapas 6+7

**Arquivos novos (sessão 7):**
- `mod_contrato.py` — geração de contrato via docxtpl + LibreOffice; `LibreOfficeIndisponivel`
- `config/contrato_template.docx` — template com 13 variáveis Jinja2
- `scripts/configurar_template_contrato.py` — insere variáveis no .docx base

**Variáveis JS chave EP-07:**
- `_orcamentos` — lista de orçamentos do projeto ativo
- `_orcamentoAtivoId` — ID do orçamento sendo visualizado (persistido em `localStorage['lastOrc_<nome_safe>']`)
- `_orcAmbientesAtivos` — ambientes do orçamento ativo (null = modo legado)
- `_descIndividual` — `{ chave: pct }` desconto individual; EP-07 usa `'ep07_'+pa.id`
- `_margemAtual` — desconto total % atualizado por `mpAtualizarApoio()`; base do limite 35%
- `_LIMITE_DESC_TOTAL` — constante `35`
- `_projListaBase` — cache da lista de projetos carregada
- `_projetoStatusAtual` — status do projeto ativo na page-02
- `carregarOrcamentos()` — busca GET /projetos/<nome>/orcamentos; seleciona por localStorage → updated_at → ordem
- `ativarOrcamento(id)` — troca aba, grava em localStorage, chama GET /orcamentos/<id>/ambientes
- `abrirPainelPool()` — abre modal com GET /projetos/<nome>/pool?orcamento_id=<oid>
- `uploadXmls()` — em modo EP-07 usa exclusivamente POST /projetos/<nome>/pool

---

## HISTÓRICO

### Sessão 2026-06-23 (sessão 26 — Motor de Negociação em MODO SOMBRA — Task 8: golden-master)
**Processo:** Task 8 (última) do plano de refatoração do motor de negociação (`feat/motor-negociacao-sombra`). Golden-master: fotografia dos valores HOJE × NOVO para baseline de validação.

**Motor e trava:**
- **`mod_negociacao`** em **MODO SOMBRA**: motor de negociação calcula os derivados (`vavo`, `val_liq`, `markup`, `val_cont`, `desc_tot_pct`) e os grava nas colunas sombra — sem alterar `valor_total`/`valor_liquido` (legado intacto).
- **`mod_qualidade_xml`** — trava de qualidade em modo sombra: bloqueia upload de XML com itens sem acréscimo/markup abaixo do limiar, com mecanismo de override gerencial (Tasks 2/4/5).
- Colunas aditivas (Tasks 3/6): `vbvo`, `cfo`, `vbno`, `vavo`, `cust_ad`, `val_liq`, `desc_tot_pct`, `markup`, `cust_fin`, `val_cont`, `prov_imp` — adicionadas via `_migrar_colunas()`, sem remover nada.
- **Tag de rollback:** `pre-refator-negociacao` — restaura estado anterior a qualquer mudança destrutiva.

**Golden-master:**
- Script: `scripts/snapshot_negociacao.py` — lê todos os `Orcamento` e grava `tests/golden/negociacao_baseline.json` com `{id, projeto, ordem, hoje:{valor_total, valor_liquido}, novo:{vavo, val_liq, markup, val_cont, desc_tot_pct}}`.
- Baseline gerado: **20 orçamentos** — campos `novo` zerados (motor sombra ainda não rodou o `save` de validação nos dados reais; será re-gerado após o primeiro save na interface).
- Arquivo commitado em `tests/golden/negociacao_baseline.json` para servir de referência na fase de validação.

**O que fica fora desta fase (após validação na interface):**
- **Fase B (cutover):** contrato/UI passam a usar os valores novos; integração plena `Cust_Fin` via `mod_fin.calcular(...)`; mover params duplicados de `orcamentos.margens` para o projeto.
- **Fase C (limpeza):** aposentar `orcamentos.valor_liquido`/bloco `margens`; remover `custo_financeiro_pct` duplicado de `mod_margens`.
- Comportamento atual (legado) permanece intacto durante toda a Fase A.

**Arquivos criados/modificados nesta sessão:**
- `scripts/snapshot_negociacao.py` (novo)
- `tests/golden/negociacao_baseline.json` (novo — baseline de 20 orçamentos)
- `DEV_LOG.md` (esta entrada)

---

### Sessão 2026-06-21 (sessão 24 — F4: isolamento operacional) — **fecha o multi-tenant**
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão de **segurança** + qualidade por task → verificação). Spec/plano em `docs/superpowers/specs/multitenant/2026-06-21-multitenant-f4-isolamento-design.md` e `docs/superpowers/plans/2026-06-21-multitenant-f4-isolamento.md`. Branch `feat/multitenant-f4-isolamento` (16 commits).

**Origem:** 4ª e última fase. F1 (schema) → F2 (UI/API de tenancy, escopo só nas telas admin) → F3 (contrato puxa da loja) → **F4 aplica escopo por loja em TODAS as queries operacionais**, que eram globais.

**Decisões do brainstorm:** (1) cada loja vê só o seu; super_admin/admin_rede **sem acesso operacional**; (2) **tudo numa fase** (carimbo na criação + filtro nas listagens + checagem de dono anti-IDOR); (3) registro de outra loja por id/link → **404** (não vaza existência).

**Entregue:**
- **`mod_tenancy.escopo_operacional(ator)` (puro):** `(loja_id, None)` p/ usuário de loja; `(None, motivo)` p/ perfil administrativo → rota traduz em **403**.
- **Helpers em `main.py` (testáveis por stub):** `_obj_da_loja(db, Model, pk, loja_id)` e `_projeto_da_loja(db, nome_safe, loja_id)` (delega no primeiro) → objeto se for da loja, senão `None` (→ 404); `_filtrar_projetos_por_loja` (lista de projetos vem do storage → cruza com `projetos_meta.loja_id`); `_parceiro_visivel_loja` (abrangência loja/rede).
- **~30 endpoints escopados** (clientes, projetos, orçamentos, contratos, pool, medição, ciclo, parceiros): guard 401+403 + checagem de dono (`_obj_da_loja`/`_projeto_da_loja`) **antes** de qualquer query que revele estado; **criação carimba** `loja_id` (cliente/projeto/orçamento; contrato já vinha da F3).
- **`database.py`:** `_backfill_loja_operacional` (idempotente, NULL→loja 1) chamado no `_migrar_dados`; `upsert_projeto_status` passa a carimbar `loja_seed_id` ao criar projeto.
- **Contrato/editar (gate gerencial):** escopo via `autorizador.loja_id` (não a sessão).

**Segurança — IDORs achados e corrigidos na revisão por subagentes** (todos fechados na branch): `POST /clientes/<id>/briefing` (escrita cross-loja) + vazamento de cliente na colisão de CPF; ordem do `POST /parametros` (loja antes do estado); `GET /projetos/<nome>/briefing` (sem auth); **`PUT /orcamentos/<id>/descontos` e `PATCH /orcamentos/<id>/valor` (sem auth nenhuma)**; "Orçamento 1" auto-criado com `loja_id` NULL (quebra funcional); `_origem` (cópia de margens) cross-loja; **`POST /projetos/<nome>/ambientes/...` (sem auth)** e `POST /projetos/<nome>/briefing` (sem checagem de sessão).

**Verificação:** pytest **201** verde (novos em `tests/test_isolamento_f4.py`: `escopo_operacional`, `_obj_da_loja`/`_projeto_da_loja` com stub, backfill idempotente). Cada task passou por revisão de **segurança** + qualidade (subagentes). **Pendente:** smoke com **2 lojas** no ambiente do usuário — checklist + mapa de triagem em `docs/processos/SMOKE_F4_ISOLAMENTO.md`. Com uma única loja (hoje), o comportamento visível é idêntico ao de antes.

**Achado pré-existente (fora da F4, decisão do usuário):** `contrato_editar.py:validar_gerencial` usa nomes de perfil antigos (`"gerente"`/`"admin"`) → hoje só `diretor` edita contrato. Política a definir.

### Sessão 2026-06-21 (sessão 23 — F3: contrato puxa da loja)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação). Spec/plano em `docs/superpowers/specs/multitenant/2026-06-21-multitenant-f3-contrato-loja-design.md` e `docs/superpowers/plans/2026-06-21-multitenant-f3-contrato-loja.md`. Branch `feat/multitenant-f3-contrato-loja`.

**Origem:** 3ª das 4 fases do multi-tenant. A F2 (sessão 22) tornou os dados da loja editáveis (incl. testemunhas/CPF); a F3 faz o contrato **consumir** esses dados em vez das constantes hard-coded. Não toca isolamento operacional (F4).

**Decisões do brainstorm:** (1) **snapshot** dos dados da loja no contrato; (2) loja incompleta → **avisar mas deixar gerar** (não bloqueia, ao contrário do cadastro do cliente); (3) **remover as constantes** — loja vira fonte única (sem fallback); (4) **refoto a cada geração**, congela na assinatura (pela trava pós-assinatura existente). Telefone/email/endereço da loja viraram **obrigatórios no cadastro** (validação).

**Entregue:**
- **`mod_contrato.py` (puro):** removidas as constantes `_NOME_EMPRESA`/`_CNPJ_EMPRESA`/`_CODIGO_LOJA`/`_TELEFONE_LOJA`/`_EMAIL_LOJA`/`_TESTEMUNHAS`. `construir_contexto(cliente, usuario, forma, loja=None)` injeta a loja no `ctx`; `_montar_mapping` lê empresa/testemunhas de `ctx["loja"]`; `gerar_num_contrato(existing, loja_codigo, …)` com código **obrigatório**. Novo validador puro `validar_loja_para_contrato` (campos obrigatórios; CPF placeholder sem dígito conta como faltando; `complemento` opcional).
- **`database.py`:** coluna `contratos.loja_snapshot_json` (TEXT, nullable) no model + `_migrar_colunas` (idempotente).
- **`main.py`:** helper `_loja_dict_para_contrato(db, loja_id)`; nos **2 pontos de geração** (aprovação + regeração) resolve a loja do consultor (`_ator_dict`), valida → responde `precisa_confirmar_loja`/`campos_loja_faltando` (HTTP 400) quando incompleta e sem `confirmar_loja_incompleta`, grava `loja_snapshot_json`, fixa `contrato.loja_id` na 1ª geração e passa a loja para `construir_contexto`/`gerar_num_contrato`.
- **Frontend (`static/index.html`):** **ambos** os fluxos que geram/regeneram o contrato tratam `precisa_confirmar_loja` com diálogo "Gerar assim? / Cancelar" e re-chamam com a flag — `gerarContrato()` (aprovação, reaproveitando o signatário já coletado) e `salvarAdendo()` (PATCH de regeração; achado na revisão final e corrigido).

**Verificação:** pytest **195** verde (novos: `tests/test_contrato_loja.py` — validador da loja, helper `_loja_dict_para_contrato` com db stub, migração da coluna idempotente; + `tests/test_contrato.py` atualizado para a loja como fonte). Cada task passou por revisão de **spec** + **qualidade** (subagentes). **Pendente:** smoke de API/Playwright no ambiente do usuário (loja seed com CPF de testemunha placeholder → deve disparar o diálogo "Gerar assim?"); preencher os CPFs reais em "Dados da loja" e revalidar. **Checklist de verificação + mapa de triagem (sintoma→local) + inspeção do snapshot em `docs/processos/SMOKE_F3_CONTRATO_LOJA.md`** (para acelerar o diagnóstico se algum bug surgir).

**Edge conhecido (registrado p/ revisão final):** loja **sem código** + geração confirmada → `num_contrato` sai com prefixo vazio (`-AAAA-…`); ocorre só se a loja não tiver código (validação avisa). Mantido o comportamento leniente por coerência com a Decisão 2.

### Sessão 2026-06-21 (sessão 22 — F2: perfis e CRUD de tenancy)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação → merge). Spec/plano em `docs/superpowers/specs/multitenant/2026-06-21-multitenant-f2-tenancy-design.md` e `docs/superpowers/plans/2026-06-21-multitenant-f2-tenancy.md`.

**Origem:** 2ª das 4 fases do programa multi-tenant. A F1 (sessão 21) criou o schema; a F2 **expõe a tenancy na UI/API**, sem tocar nenhuma query operacional (isolamento real é a F4).

**Entregue:**
- **Perfis novos (`perfis.py`) — puramente administrativos (operacional 0/False):** `super_admin` ("Administrador da Plataforma", escopo tudo) e `admin_rede` ("Administrador de Rede", escopo sua rede). Capacidades `gerir_redes` (só super_admin), `gerir_lojas` (super_admin+admin_rede), `editar_dados_loja` (+ **Diretor**, só a própria loja). Sessão (`auth._usuario_dict`) passa a expor `loja_id`/`rede_id` + flags `pode_gerir_redes`/`pode_gerir_lojas`/`pode_editar_dados_loja`.
- **`mod_tenancy.py` (novo, puro/testável):** validadores (`validar_rede`, `validar_loja` código 3-letras único, `validar_abrangencia_parceiro`) + política de escopo/atribuição (`pode_ver_rede`, `pode_ver_loja`, `pode_editar_dados_loja`, `atribuir_tenant_usuario`, `_eh_super_admin`/`_eh_admin_rede`). As rotas em `main.py` ficam finas: validam, chamam as funções puras, aplicam `WHERE` por tenant e serializam.
- **Bootstrap:** migração de dados `tenancy_v2_2026` (idempotente, `schema_migrations`) cria o super_admin `sad2026` quando nenhum existe; `seed.py` também o cria via ORM. Hashing de senha unificado em `database._hash_senha`.
- **Endpoints (`main.py`, todos sob `/api/admin/`, com gate + escopo):** `redes` (GET/POST/PATCH, gate `gerir_redes`); `lojas` (GET/POST/PATCH, escopo por rede/loja, `?rede_id=avulsas|N`, edição dos **dados da loja** incl. testemunhas/CPF — destrava a F3); `usuarios` estendido (atribuição de `loja_id`/`rede_id` conforme quem cria + escopo na listagem); parceiros com **abrangência** `'loja'`(M:N em `parceiro_lojas`, comissão por loja) / `'rede'` — **Diretor cria ambos** (rede = a da própria loja).
- **Frontend (`static/index.html`):** page-07 virou **console de 3 níveis** (Plataforma → Rede → Loja) com breadcrumb + drill-down; aterrissagem por perfil; aba "Dados da loja" (form que faz PATCH) e "Usuários da loja" (CRUD de sempre, preservado); UX de abrangência no modal de parceiro (com pré-preenchimento ao editar, p/ não resetar 'rede'→'loja').

**Verificação:** pytest **186** verde (19 novos: perfis, validadores, escopo/atribuição, bootstrap+idempotência). **Smoke de API ao vivo (servidor real, super_admin+diretor):** 19 checagens — atribuição de tenant, escopo do diretor (lista/cria só na própria loja; 403 em `/api/admin/redes`), abrangência loja+rede, cadastro legado intacto, e **parceiro órfão não persiste** quando a abrangência falha (create atômico via `flush`). **Smoke de runtime do frontend via jsdom** (DOM real + backend ao vivo): 16 checagens, **0 erros de JS** — super_admin aterrissa no Nível 1, diretor no Nível 3 (form da loja preenchido + lista de usuários), modal de abrangência e edit-prefill OK. **Pendente:** Playwright em Chromium não rodou (faltam libs de sistema `libnspr4`/`libnss3` no WSL, sem sudo) — coberto funcionalmente pelo jsdom; rodar o pass visual no ambiente do usuário.

**Fixes em revisão (achados e corrigidos durante o ciclo):** import local `urlparse` sombreava o do módulo e quebrava **todo** o `do_GET` (corrigido p/ `parse_qs` só); guard `.isdigit()` no `?rede_id=` (evita 500 por `int()` em input livre); marcador da migração `tenancy_v2` movido p/ dentro do guard de colunas (não marcar aplicada sem agir); **create de parceiro atômico** (`flush`+commit único) p/ não deixar órfão; prefetch das lojas no escopo de usuários (evita N+1); diretor pode parceiro de abrangência rede da própria loja.

### Sessão 2026-06-20 (sessão 21 — F1: fundação da plataforma multi-tenant)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação → merge). Spec/plano em `docs/superpowers/specs/multitenant/2026-06-20-multitenant-f1-fundacao-design.md` e `docs/superpowers/plans/2026-06-20-multitenant-f1-fundacao.md`.

**Origem:** o pedido "configurador de lojas" (tirar nome/CNPJ/testemunhas das constantes de `mod_contrato.py`) foi explorado e revelou a intenção de uma **plataforma multi-tenant com isolamento total** — `Plataforma → Rede → Loja`, com lojas independentes (avulsas) e escalável para muitas redes/lojas; cada loja tem seus usuários. Decomposto em **4 fases**, cada uma com seu ciclo: **F1 fundação de dados** (esta) · F2 perfis + CRUD de redes/lojas · F3 contrato puxa da loja · F4 isolamento (escopo por loja em todas as queries).

**F1 — puramente aditiva (zero mudança de comportamento):**
- **Models novos (`database.py`):** `Rede` (`redes`), `Loja` (`lojas`, com `rede_id` nullable = avulsa, `codigo` 3-letras UNIQUE p/ numeração do contrato, endereço, 2 testemunhas), `ParceiroLoja` (`parceiro_lojas` — vínculo M:N parceiro×loja com `comissao_padrao_pct` por loja).
- **Modelo de parceiros M:N:** parceiro pertence a uma **rede** (ou loja avulsa); `abrangencia` `'loja'`|`'rede'`; mesma pessoa pode ser parceira de 2 lojas (1 cadastro, N vínculos); parceiro "global da rede" via `abrangencia='rede'`. Fronteira de isolamento = rede/loja-avulsa.
- **Colunas de tenant:** `loja_id` em `usuarios`/`clientes`/`projetos_meta`/`orcamentos`/`contratos`; `rede_id` em `usuarios`; `rede_id`+`abrangencia` em `parceiros`. Tabelas-filhas (briefings/medicoes/pool/etc.) herdam pelo pai — não recebem `loja_id`.
- **Migração:** colunas via `_migrar_colunas` (DBs existentes); dados via `_run_migracoes` → `tenancy_v1_2026` (idempotente, em `schema_migrations`): cria a **loja seed** a partir das constantes do contrato (INSPIRIUM, `codigo=INS`; CPFs de testemunha ainda placeholder → corrigir na F2) e faz backfill de `loja_id` em todos os registros + um vínculo `parceiro_lojas` por parceiro.
- **`seed.py`:** `criar_usuarios_seed(db, usuarios, loja_id)` (puro/testável) vincula os 10 usuários-exemplo à loja seed; helper `loja_seed_id(db)`.

**Verificação:** pytest **167** verde (10 novos: schema, colunas, migração+idempotência+não-sobrescreve-abrangência, seed). Smoke do `init_db()` completo sobre uma **cópia do `orizon.db` real**: loja seed criada e **0 registros com `loja_id` NULL** (11 usuários, 6 clientes, 14 projetos, 20 orçamentos, 13 contratos). Sem mudança de UI/rotas/contrato (confirmado por revisão de spec em cada task) — regressão por construção. **Pendente:** regressão Playwright ao vivo não rodada (evitar mutar o DEV DB antes do merge; F1 não tem superfície de UI).

**Fixes em revisão:** guard `_tabela_existe("parceiro_lojas")` na migração (robustez a DBs parciais); restaurado o contador "já existia(m)" no resumo do `seed.py`.

**Infra de desenvolvimento (mesmo dia):** configurado **acesso remoto pelo celular** (Termius/SSH) para tocar/testar as próximas fases com sessão persistente — **Tailscale** (PC `legion-marcelo` = `100.95.134.72`) + **OpenSSH do Windows** (user `mbn19`, porta 22) + **WSL2 Ubuntu** + **tmux**. Fluxo: `ssh mbn19@100.95.134.72` → `wsl` → `tmux attach`. Detalhes na memória `trabalho-mobile-termius`. **Próximo passo de produto:** F2 (perfis `super_admin`/`admin_rede` + CRUD de redes/lojas + UX de abrangência de parceiro).

### Sessão 2026-06-20 (sessão 20 — parâmetros estruturais por projeto)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação API real + Playwright → merge). Spec/plano em `docs/superpowers/`. Refina a sessão 16 (que deixara TODAS as margens por orçamento).

**Correção pedida:** os parâmetros **estruturais** da negociação valem para o projeto inteiro — mexeu num orçamento, vale para todos. Só desconto e pagamento são por orçamento.

**Modelo:**
- **Por projeto** → **`projetos_meta.parametros_json`** (JSON, 10 chaves): `incluir_custos`, `comissao_arq_pct`/`ativa`, `fidelidade_pct`/`ativa`, `fora_da_sede`/`custo_viagem`, `brinde`/`brinde_ativo`, `carga_trib`.
- **Por orçamento** → `orcamentos.margens` (só `desconto_pct` + `custo_financeiro_pct` derivado), `orcamento_ambientes.desconto_individual_pct`, e `orcamentos.negociacao_json` (pagamento).

**Backend:** `PARAMETROS_DEFAULT` + `merge_parametros` (em `mod_orcamento_params.py`); `GET`/`POST /api/projetos/<nome>/parametros` (com gate bloqueio/assinatura); `GET /orcamentos/<id>/ambientes` passou a devolver `parametros` do projeto; `POST /api/orcamentos/<id>/margens` grava **só** `desconto_pct` (ignora estruturais); migração idempotente `migrar_parametros_para_projeto` (copia estruturais de um orçamento → projeto) no startup. `merge_margens` deixou de ser usado em `main.py`.

**Frontend:** ao ativar orçamento, `projetoAtivo.margens` é montado como `parâmetros do projeto + desconto do orçamento` (`Object.assign`); o modal de parâmetros salva estruturais no projeto e desconto no orçamento.

**Verificação:** pytest **155** verde (coluna, módulo puro, migração). API real: **11/11** — salvar parâmetros reflete em todos os orçamentos; desconto isolado por orçamento; estruturais não vazam para o orçamento. Playwright: estruturais compartilhados / desconto isolado entre 2 orçamentos, 0 erros de console.

**Fix de follow-up (mesmo dia):** os parâmetros estruturais sumiam ao reabrir o modal. Causa: `salvarDescontoAutomatico` fazia `projetoAtivo.margens = d.margens` e o endpoint `/margens` (pós-refactor) devolve só `desconto_pct` — apagando os estruturais da memória; e o save do modal não atualizava `projetoAtivo.margens` com os estruturais recém-salvos. Correção: `salvarDescontoAutomatico` passa a atualizar **só** `desconto_pct` (preserva os estruturais); o save do modal atualiza `projetoAtivo.margens` com os `parametros` salvos. Verificado por Playwright (reabrir modal e blur do desconto preservam os estruturais).

**Correção pontual (mesmo dia):** painel de **Cartão** ganhou o campo **"Data da entrada"** (`cc-entrada-data`) na linha de Entrada/Bandeira; o `_planoPagamento.entrada_data` do cartão (antes `''` fixo) passa a lê-lo, refletindo no contrato `[DATA_ENTRADA]`; incluído no snapshot (`negociacao_json`) para persistir por orçamento. Verificado por Playwright.

**Correção pontual (mesmo dia):** **"Data da entrada" em todas as modalidades com entrada** — adicionado também a **Aymoré** (`ay-entrada-data`), **Venda Programada** (`vp-entrada-data`) e **Total Flex** (`tf-entrada-data`); antes essas usavam a *Data do Contrato* como data de entrada. Cada `_planoPagamento.entrada_data` lê o campo novo com fallback para a data do contrato; pré-preenchido com hoje ao abrir o painel; incluído no `negociacao_json`. (Cartão e À vista já tinham.) Tudo reflete no contrato (valor/data/forma da entrada + grade do resíduo). Verificado por Playwright (3/3 modalidades).

**Correção pontual (mesmo dia):** **contrato do cartão** — a grade passa a mostrar **cada parcela na sua posição com o valor e SEM data** (antes despejava o `texto_cartao` na 1ª célula); o campo `[NUM_PARCELAS]` mostra o **número de parcelas** quando parcelado e **"à vista"** quando 1x. Frontend: `_planoPagamento.parcelas` do cartão passa a conter as N parcelas (`{valor, data:''}`). Backend: `_preencher_grade` (ramo cartão) e `_parse_pagamento` (display "à vista"/número; datas vazias do cartão). Verificado: geração de contrato 12x (valores sem data, "12") e 1x ("à vista") + Playwright. pytest **157**.

### Sessão 2026-06-19 (sessão 19 — trava total pós-assinatura + status "Fechado")
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → verificação API real + Playwright → merge). Segundo de 3 sub-projetos. Spec/plano em `docs/superpowers/`.

**Comportamento:** a partir da **1ª assinatura** do contrato (qualquer parte), a negociação/projeto fica **congelada**: o frontend esconde Salvar/Parâmetros/Ambientes/Novo Ambiente/Novo Orçamento e o "Rever Orçamento" (mantém **"Assinar Contrato"** para a 2ª parte); o backend **recusa (403)** as mutações. Quando **ambas** as partes assinam, o projeto recebe o status terminal **"🔒 Fechado"** (automático, não editável — como "convertido").

**Backend (`main.py`):**
- **`_contrato_assinado(nome_safe, db)`** — fonte única (status assinado_loja/cliente/assinado/vigente OU `len(assinaturas)>0`). Exposto em `GET /api/projetos/<nome>/ciclo` como `contrato_assinado`.
- **Guard 403** em: novo orçamento, pool (+ sobrescrever/nova_versão/criar_forçado), adicionar/remover/renomear ambiente, renomear orçamento, PATCH valor, margens, descontos, PATCH status. (Guard de assinatura colocado **antes** do briefing no novo orçamento p/ 403 consistente.)
- **Status "fechado"** setado por `upsert_projeto_status` na 2ª assinatura — **após** o `db.commit()` (corrige bug de lock do SQLite que silenciava o update). Projetos já assinados antigos: backfill manual no DEV DB.

**Frontend (`static/index.html`):**
- `_contratoAssinado` vindo do GET ciclo; `atualizarBotoesAprovacao` esconde a edição quando assinado (caminho não-assinado intacto). Status "🔒 Fechado": label/badge/CSS/filtro + dropdown travado (espelha "convertido", nunca setável manualmente).

**Verificação:** pytest **145** verde (helper `_contrato_assinado` + 4 testes). API real: 403 confirmado em valor/margens/descontos/status/novo-orçamento quando assinado; **status vira "fechado"** ao assinar as 2 partes (sem erro de lock no log). Playwright: botões de edição escondidos, "Assinar Contrato" presente, 0 erros de console.

**Fix de follow-up (mesmo dia):** botão "Assinar Contrato" persistia após a 2ª assinatura. Causa: o ramo assinado de `atualizarBotoesAprovacao` sempre recriava o botão. Correção: novo helper `_contrato_totalmente_assinado` + flag `contrato_totalmente_assinado` no GET ciclo; o botão "Assinar Contrato" só aparece na assinatura **parcial** e some quando ambas as partes assinam; "Rever Orçamento" some em qualquer assinatura (já era o caso — o relato de "Rever ainda aparecia" era **cache** do `index.html` antigo). Verificado por Playwright (parcial: rever ausente/assinar presente; total: ambos ausentes). pytest 149.

**Pendente:** sub-projeto 3 (versionamento de documentos). Configurador de lojas (do sub-projeto do contrato).

### Sessão 2026-06-19 (sessão 18 — alinhar contrato ao template reestruturado)
**Processo:** pipeline superpowers (intercalado durante o sub-projeto 2, a pedido do usuário). Spec/plano em `docs/superpowers/`. Disparado por uma edição do `modelo_contrato_mapeado.docx` no Word (reestruturação do bloco de assinatura), que quebrou 6 testes de contrato.

**Diagnóstico (corrigido após ler o motor):** o motor do corpo (`_subst_paragrafo`) já opera no texto concatenado do parágrafo → já é robusto a marcadores fragmentados em runs. As 6 falhas eram **(a) mapeamentos faltando** e **(b) 2 testes presos à estrutura antiga** ("CPF/CNPJ:" inline).

**Mudanças:**
- **`mod_contrato.py`:** constantes `_NOME_EMPRESA`/`_CNPJ_EMPRESA` com os **valores reais já presentes no template** (`INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA`, CNPJ `19.152.134/0001-56`; TODO: configurador de lojas). `_montar_mapping` ganhou `NOME_EMPRESA`, `CNPJ_EMPRESA`, `CPF_CLIENTE`, `CPF_TESTEMUNHA_1`, `CPF_TESTEMUNHA_2`.
- **Cabeçalho robusto:** o ramo de headers de `_substituir_marcadores` passou a reusar `_subst_paragrafo` (robusto a runs) em parágrafos, tabelas **e text-boxes** do cabeçalho — descobriu-se que `[Num_Contrato]`/`[Data_contrato]` vivem em **caixas de texto** (`wps:txbx`), não em parágrafos comuns.
- **Testes:** 2 atualizados ao novo bloco (nome e CPF em marcadores separados); +3 testes novos (mapping, cabeçalho fragmentado).
- **Template:** o `.docx` reestruturado foi versionado.

**Verificação:** pytest **141** verde. Geração com dados reais (via `preencher_contrato`): zero marcador remanescente; empresa+CNPJ, cliente+CPF, testemunhas e número/data no cabeçalho corretos.

**Pendente:** **configurador de lojas** (origem real de nome/CNPJ/testemunhas/telefone) — projeto futuro; por ora os valores são constantes. Retomar o **sub-projeto 2** (trava pós-assinatura) — a Task 1 dele já está commitada em `feat/trava-pos-assinatura`.

### Sessão 2026-06-19 (sessão 17 — snapshot completo da negociação por orçamento)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → revisão holística → verificação API real + Playwright → merge). Primeiro de 3 sub-projetos decompostos de um pedido maior (1) snapshot da negociação · 2) trava total pós-assinatura · 3) versionamento de documentos). Spec/plano em `docs/superpowers/`.

**Bug relatado:** ao salvar/aprovar, a última negociação de forma de pagamento/parcelamento se perdia. Causa: o plano calculado era salvo em `forma_pagamento`, mas ao reabrir nada restaurava a modalidade, formas, nº de parcelas, entrada e — no Total Flex — as **datas preenchidas manualmente** (limitação anotada na sessão 10).

**Backend:**
- **`orcamentos.negociacao_json`** (coluna JSON nova): snapshot das **entradas** da negociação (separado do `forma_pagamento`, que segue sendo o plano calculado p/ o contrato).
- `PATCH /orcamentos/<id>/valor` grava `negociacao_json` (campo opcional; omitir não apaga); `GET /orcamentos/<id>/ambientes` devolve `negociacao` (parseado).

**Frontend (`static/index.html`):**
- **`_capturarNegociacao()`** (mapa de campos por modalidade) captura modalidade, formas, nº de parcelas, entrada, e as listas de datas/valores manuais (TF: `tf_datas`+`tf_valores`; VP: `vp_datas`). A **taxa TF** (campo mascarado/gated por gerente) é intencionalmente fora do snapshot.
- **`_restaurarNegociacao()`** reinjeta as entradas após `carregarModalidades()` (ordem: modalidade → parcelas → campos → datas/valores → recálculo) e reproduz o plano com as datas salvas.
- **Garantia ao aprovar:** `salvarValorNegociado()` retorna `{ok,erro}`; `aprovarOrcamento`/`salvarOrcamento`/`abrirAprovacaoComDados` **abortam** se o salvamento falhar; salvamento com total 0 é bloqueado (evita sobrescrever valor bom com 0).
- **Race condition do Total Flex** corrigida: `atualizarTF()` ganhou contador de geração `_tfGen` (descarta respostas `inicializar`/`recalcular` obsoletas em voo, ex.: a disparada por `tfMostrarPainel`) — sem ele, a resposta tardia sobrescrevia as datas restauradas.

**Verificação:** pytest **139** verde (coluna + round-trip). API real (login `pdm2026`): **7/7** — grava/lê snapshot, `tf_datas` preservadas, PATCH parcial não apaga o snapshot. Playwright: **datas manuais do Total Flex reproduzidas** ao reabrir (`_tfDatas`/`_tfValores` corretos), 0 erros de console. Dados de demo restaurados depois.

**Pendente (próximos sub-projetos):** trava total pós-assinatura (esconder salvar/criar orçamento, inserir ambientes, alterar parâmetros após contrato assinado); versionamento de documentos (novos criam versão, sem sobrescrever/apagar). Follow-up menor: simetria já aplicada nos guards de geração do TF.

### Sessão 2026-06-19 (sessão 16 — parâmetros de negociação por orçamento no banco)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão em duas etapas por task → revisão holística final → verificação por API real + Playwright → merge). Spec/plano em `docs/superpowers/`.

**Motivação (lacunas pegas em auditoria de persistência):** (1) o **desconto individual por ambiente** vivia só no `localStorage` (sumia ao trocar de máquina/navegador); (2) as **margens** (desconto global, custos, comissões, impostos) ficavam em `projeto.json` **compartilhadas pelo projeto todo**, impedindo orçamentos paralelos com parâmetros distintos. Regra registrada: todo documento/dado do projeto deve ser persistido (banco/disco), nunca só no navegador.

**Backend:**
- **`orcamento_ambientes.desconto_individual_pct`** (Float, default 0) — desconto por ambiente agora é por-orçamento, no banco. Migração de coluna idempotente em `_migrar_colunas`.
- **`orcamentos.margens`** (coluna TEXT que já existia) passa a ser a **fonte oficial** das margens, **por orçamento** (12 chaves).
- **`mod_orcamento_params.py`** (novo, puro): `MARGENS_DEFAULT`, `merge_margens(atual, req)` (merge + coerção de tipos; bool a partir de string; rejeita NaN), `sanear_descontos(pares, ids_validos)` (faixa 0..100, filtra ids fora do orçamento).
- **`POST /api/orcamentos/<id>/margens`** e **`PUT /api/orcamentos/<id>/descontos`** (lote) — ambos com gate `_projeto_esta_bloqueado` (pós-aprovação) e `ValueError→400`.
- **`GET /orcamentos/<id>/ambientes`** agora devolve `margens` do orçamento + `desconto_individual_pct` por ambiente.
- **Novo orçamento copia margens** do orçamento de origem (`origem_id`).
- **Migração `migrar_margens_para_orcamentos`** (startup, após `init_db`, em try/except): copia margens do `projeto.json` para orçamentos sem margens; idempotente (só preenche vazias).
- **Aposentada** a rota `POST /projetos/<nome>/margens` (gravava no `projeto.json`).

**Frontend (`static/index.html`):** ao ativar/trocar de orçamento, margens e descontos por ambiente são carregados **do servidor** (servidor é a fonte de verdade); salvamento via os endpoints por-orçamento; criar orçamento envia `origem_id`; guarda contra salvar margens sem orçamento ativo. Corrigido bug de ordem (o `carregarMargensSalvas` zerava `_descIndividual` recém-carregado) — agora roda antes da repopulação.

**Verificação:** pytest **137** verde (novos: coluna, módulo puro, migração). API real (login `pdm2026`): **16/16** asserts — save+read-back de margens, desconto por ambiente, validação 400, cópia por `origem_id`, **isolamento** entre orçamentos. Playwright: 0 erros de console/página. Dados de teste no DEV DB limpos depois.

**Limitação anotada:** comissão de múltiplos parceiros (hoje só `comissao_arq_pct`) e armazenamento dedicado de "projeto executivo" ficaram para sub-projeto futuro.

### Sessão 2026-06-19 (sessão 15 — fix do bloqueio + atualização de documentação)
- **Bug pego em uso:** no parecer da medição só dava para selecionar "Aprovado". Causa: o `#ciclo-panel` vive dentro de `#page-02`, e o bloqueio pós-aprovação (`aplicarBloqueioNegociacao`) desabilitava todos os `select`/`input` de `#page-02` — incluindo o select de parecer e os uploads da medição. **Correção:** o bloqueio passa a isentar `#ciclo-panel` (fluxo pós-aprovação precisa ficar interativo); a negociação continua travando. Verificado por Playwright. Commit `87679e3`.
- **Documentação atualizada:** DEV_LOG ([ESTADO]/[PENDENTE]/[CONTEXTO] revisados para os 10 perfis, painel de usuários, aprovação financeira, medição e correções de negociação) e `docs/USUARIOS.md` já refletindo os perfis/capacidades.
- **Deploy:** sub-projetos 1–4 + correções empurrados ao GitHub; produção atualizada via runbook (deps já instaladas, `ORIZON_HOST=0.0.0.0`, banco recriado/seedado com os 10 perfis, `no-cache` ativo).

### Sessão 2026-06-18 (sessão 14 — sub-projeto 4: workflow de medição)
Quarto e último sub-projeto da decomposição (fecha os itens 6 e 7).
- **Capacidades** (`perfis.py`): `registrar_medicao` (Medidor + Diretor) e `aprovar_medicao_reprovada` (Gerente de Vendas + Gerente Adm/Fin + Diretor).
- **Modelo `Medicao`** (1 por projeto): arquivos de solicitação/planta/doc-cliente + parecer + ambientes + responsáveis/datas. **`mod_medicao.validar_parecer`** (parcial exige ambientes).
- **Etapa 9 "Solicitação de medição":** upload do arquivo + confirmação por login+senha do Medidor (ou Diretor).
- **Etapa 10 renomeada "Medição":** registro do parecer (Aprovado/Reprovado/Parcial+ambientes) + planta promob, autenticado pelo medidor/diretor. Aprovado/Parcial concluem; **Reprovado em 2 passos** — fica `em_andamento` e só conclui com upload do documento do cliente + senha de Gerente de Vendas/Adm-Fin/Diretor (gravado quem autorizou).
- **Backend:** parser multipart **binário** (`_parse_multipart_arquivos`), helper `_usuario_com_capacidade`, endpoints `/medicao/{solicitacao,parecer,decisao-reprovado,arquivo/<tipo>}`, **guard** no `PATCH /ciclo/9|10` (só fecham pelo fluxo de medição), auditoria em `log_acoes_gerenciais`.
- **Frontend:** cards dedicados das etapas 9 e 10 (upload + popup de credenciais + parecer + campo de ambientes no parcial + 2º passo do reprovado).
- **Verificação:** pytest **125** verde; API real (multipart) confirmou todos os caminhos — etapa 9 (consultor 403, medidor 200), parcial sem ambientes (erro), aprovado (200), guard (400), reprovado 2 passos (medidor não libera 403; vendas libera 200), auditoria registrada. Spec/plano em `docs/superpowers/`.
- **Decomposição concluída:** os 4 sub-projetos (correções do ciclo, perfis+painel, aprovação financeira, medição) estão mesclados na `main`.

### Sessão 2026-06-18 (sessão 13 — sub-projeto 3: aprovação financeira gerencial)
Terceiro de 4 sub-projetos (usa a fundação de perfis do sub-projeto 2).
- **Capacidade `aprovar_financeiro`** em `perfis.py` (Diretor + Gerente Adm/Financeiro; gerente de vendas **não**).
- **`mod_ciclo.ETAPAS_APROVACAO_FINANCEIRA = {8, 11d}`** + `exige_aprovacao_financeira()`.
- **Gate no `PATCH /ciclo/<codigo>`:** concluir as etapas 8 ("Aprovação financeira I") e 11d ("Aprovação financeira II") exige `login`+`senha` de quem tem `aprovar_financeiro` (helper `_aprovador_financeiro`); senão **403**. Registra o aprovador como responsável da etapa e audita em `log_acoes_gerenciais` (ação `aprovar_financeiro`).
- **Frontend:** `concluirAprovacaoFinanceira(codigo)` abre o popup `pedirCredenciaisGerente`; a sub-etapa 11d passou a usar o card de aprovação financeira (igual à 8).
- **Verificação:** pytest **118** verde; API real confirmou — etapa 8 e 11d: gerente de vendas/consultor → 403, senha errada → 403, Gerente Adm/Fin e Diretor → 200, auditoria registrada. Spec/plano em `docs/superpowers/`.

### Sessão 2026-06-18 (sessão 12 — sub-projeto 2: perfis + painel admin de usuários)
Segundo de 4 sub-projetos (fundação reusada pelos sub-projetos 3 e 4).
- **`perfis.py` (fonte única):** 10 perfis oficiais (diretor, gerente_vendas, consultor, gerente_adm_fin, assistente_logistico, conferente, supervisor_montagem, assistente_administrativo, projetista_executivo, medidor) com matriz de permissões (desconto_max, ver_parametros, autorizar, gerir_usuarios). `database.py` (`limite_desconto`/`pode_ver_parametros`), `auth.py` e `main.py` passam a consultar `perfis`.
- **Migração `perfis_v2_2026`:** renomeia `gerente`→`gerente_vendas` e `admin`→`diretor` (idempotente, com guard `_tabela_existe`). Perfil técnico `admin` aposentado.
- **CRUD de usuários no painel admin:** `GET/POST/PATCH /api/admin/usuarios` (gate `gerir_usuarios` = Diretor + Gerente Adm/Fin); validadores puros em `mod_usuarios.py`; seção "Usuários" na page-07 (lista viva, criar, editar perfil/telefone, ativar/desativar, resetar senha). Usuários são desativados, não excluídos.
- **`/api/auth/me`** expõe `rotulo` e `pode_gerir_usuarios`; frontend usa `limite_desconto` do `/me` (removido o hardcode `_LIMITES_NIVEL`); `nav-07` gateado por `pode_gerir_usuarios`.
- **`seed.py`:** um usuário-exemplo por perfil (10); saída ASCII-safe. **`docs/USUARIOS.md`** documenta os perfis.
- **Bug pego na verificação:** variável local `perfis` em `do_POST` (rota `/api/gerente/verificar`) sombreava o módulo → `UnboundLocalError` nos gates novos; renomeada para `_perfis_cfg`.
- **Verificação:** pytest **116** verde; CRUD/gate confirmados via API real (criar/duplicado/perfil-inválido/editar/desativar; consultor 403; adm-fin 200). Spec/plano em `docs/superpowers/`.

### Sessão 2026-06-18 (sessão 11 — sub-projeto 1: correções do ciclo)
Primeiro de 4 sub-projetos decompostos de uma leva de pedidos (perfis, aprovação financeira, medição virão a seguir).
- **Gating de sub-etapas (genérico):** sub-etapas (`11a`–`11e` do PE, `17a` da Montagem e quaisquer `Nx`) estavam desbloqueando antes da etapa-mãe. Agora herdam o gating da mãe e desbloqueiam **junto** com ela. Backend: `mod_ciclo.etapa_pai()` + `pode_avancar()` recursivo na mãe. Frontend: `_etapaBloqueada()` recursa na mãe. (Substituído o teste antigo `test_pode_avancar_subetapa_sempre_livre`.)
- **Botão "Assinar Contrato":** o botão pós-aprovação na tela de negociação passou de "🔒 Orçamento aprovado – assinar contrato" para **"✍ Assinar Contrato"**, com estilo idêntico ao "Rever Orçamento" (`btn btn-ghost`, contorno âmbar).
- **Verificação:** pytest **103** verde; Playwright confirmou sub-etapas 🔒 antes da etapa-mãe e liberando juntas, e o botão renomeado/estilizado. Spec/plano em `docs/superpowers/`.

### Sessão 2026-06-18 (sessão 10b — UX: popups estilizados, assinatura do cliente, botão voltar)
**Processo:** pipeline superpowers (clarificação → branch → subagentes com revisão a nível de controlador → verificação Playwright/dados reais → revisão final → merge local).

- **Diálogos nativos → popups estilizados:** removidos todos os `confirm`/`alert`/`prompt` (que apareciam como "127.0.0.1:8765 diz"). Novos helpers em `static/index.html`: `confirmarPopup` (sim/não), `avisoPopup` (aviso) e `pedirCredenciaisGerente` (login+senha estilizado). Refatorados: signatário do contrato em `gerarContrato` (popup Sim/Não), reabrir etapa (`abrirModalReabrir` — antes `confirm`+2 `prompt` → popup de credenciais), remover ambiente e o aviso de abrir o editor.
- **Assinatura do cliente no contrato:** o nome saía com fonte/negrito diferente das demais. Causa: parágrafo em estilo `Normal` com `\n` inicial; `_subst_paragrafo` herdava o run vazio. Correção: `_subst_paragrafo` ignora run inicial vazio ao escolher a base de formatação; `scripts/normalizar_assinaturas.py` (idempotente) padroniza as 4 linhas de assinatura (empresa/cliente/2 testemunhas) em estilo `Heading 2`, limpa overrides de fonte e remove o `\n` extra — fonte/negrito/alinhamento iguais. 2 testes novos.
- **Botão "Voltar"** também ao final da lista de etapas do ciclo (`renderCiclo`).
- **Verificação:** Playwright (servidor real) sem erros de console/página; popups abrem e resolvem; 2 botões "Voltar" no ciclo. Suíte: **101 testes** passando.

### Sessão 2026-06-18 (sessão 10 — negociação: bloqueio, Rever Orçamento, À Vista, formas)
**Processo:** pipeline superpowers (brainstorm → spec → plano → subagentes com revisão a nível de controlador → verificação Playwright com dados reais → merge). Spec/plano em `docs/superpowers/`.

**Backend (`mod_contrato.py`):**
- `_forma_label` + `_FORMA_LABELS`: converte códigos de forma (pix/ted/boleto/cheque/dinheiro/cartao_credito) em rótulos pt-BR; idempotente.
- `_parse_pagamento`: `entrada_tipo` via rótulo; novo `forma_parcela` (rótulo da 1ª parcela; "Cartão de Crédito" quando cartão).
- `_montar_mapping`: novo marcador `TIPO` (forma das parcelas) + mapeia `NOME_TESTEMUNHA_1`/`NOME_TESTEMUNHA_2`/`NOME_TESTEMUNHA2` (alinha ao template real; corrigiu 3 testes vermelhos pré-existentes).
- `scripts/inserir_marcador_tipo.py` (idempotente): insere `[NUM_PARCELAS] / [TIPO]` no `modelo_contrato_mapeado.docx`.

**Frontend (`static/index.html`):**
- **Bloqueio pós-aprovação:** `aplicarBloqueioNegociacao(travar)` deixa toda a negociação somente-leitura ao concluir a etapa 6 — cobre `#sb-params` (sidebar: desconto, modalidade, parcelas, formas, taxa TF) **e** `#page-02` (tabela, painéis, datas, total). Chamada em `atualizarBotoesAprovacao()`.
- **Rever Orçamento:** substitui "Voltar ao Orçamento" (removido do card 7 do Ciclo); dois botões na action-row da negociação pós-aprovação (`✎ Rever Orçamento` + assinar contrato); senha gerencial → `POST /ciclo/desfazer_aprovacao` → destrava e reexibe Salvar/Aprovar.
- **À Vista:** `painel-avista` com entrada (valor+data+forma) e liquidação (valor automático = total−entrada, somente-leitura; data+forma); alimenta `_planoPagamento` como entrada + 1 parcela (liquidação).
- **Calendário:** `showPicker()` em qualquer clique de `input[type=date]` (delegado em `document`) + CSS do ícone; cobre campos dinâmicos.
- **Formas por modalidade:** seletores `neg-forma-entrada`/`neg-forma-parcela` (`atualizarFormasPagamento`): cartão→entrada Pix/TED/Boleto + parcelas "Cartão de Crédito" fixo; aymoré→parcelas "Boleto" fixo; VP/TF→parcelas Boleto/Cheque; à vista→Pix/TED/Boleto/Cheque/Dinheiro. Estado `_formaEntrada`/`_formaParcela` nos 4 `_planoPagamento`.
- **Aprovação:** modal pré-seleciona formas a partir de `_planoPagamento` (mapeia ted→transferencia; +Dinheiro); `salvarValorNegociado` persiste o plano JSON em `forma_pagamento` (usado pelo backend como fallback do `pagamento_json`).

**Verificação (Playwright, servidor real, login `pdm2026`):** zero erros de console/página; regras de forma por modalidade; à vista com clamp de saldo; bloqueio trava modalidade+datas e destrava ao Rever; dois botões pós-aprovação. Suíte: **99 testes** passando.

**Limitação anotada:** restaurar `_formaEntrada`/`_formaParcela` a partir do `forma_pagamento` salvo ao reabrir orçamento não-aprovado ficou fora de escopo (o recálculo regenera `_planoPagamento`).

### Sessão 2026-06-18 (sessão 9 — contrato: marcadores, pagamento, número, edição protegida)
**Bug-raiz corrigido (F1):** `_capturarPagamento` (frontend) raspava as colunas da tabela de pagamento por índice e saía com **data e valor trocados**, além de incluir Assinatura/Entrada/Total como parcelas (o valor bruto caía na "13ª parcela"). Causa descoberta inspecionando o `pagamento_json` real do `Contrato` 6. Os testes anteriores passaram porque usavam um JSON **fabricado** — lição: verificar com dados reais.

**F1 — Pagamento correto + grade + template por marcadores:**
- Frontend expõe `window._planoPagamento` (estruturado: só parcelas reais com `valor` numérico + `data`, `total_cliente`, `texto_cartao`); `_capturarPagamento` retorna esse global (sem raspar DOM) — robusto aos 4 painéis (aymoré/cartão/vp/tf).
- `modelo_contrato_mapeado.docx` (todo em marcadores `[MARCADOR]`) **promovido a template oficial**; `modelo_contrato_final.docx` aposentado. Geração reescrita: `_substituir_marcadores` (corpo/tabelas/cabeçalho) + `_preencher_grade` (posicional). Removidos `_set_cell`/`_set_para`/`_relabel_cpf_cnpj` (agora é tudo do template).
- Grade: valor+data por parcela **sem ordinal**, **traços** nos slots vazios (linhas preservadas); cartão no 1º campo (`12x R$ ...`); novo `[TOTAL_CONTRATO]`.
- `_parse_pagamento` reescrito para a estrutura real (`valores` em dinheiro, `valor_contrato`, `texto_cartao`).
- Verificado end-to-end com **dados reais** via navegador (Playwright) + `/calcular_aymore`.

**Número do contrato:** `gerar_num_contrato` → `LOJA-AAAA-MM-DD-SEQ` (`INS`, sequência contínua por loja), coluna `contratos.num_contrato` (migração idempotente), gerado uma vez/estável, no cabeçalho com a data abaixo. Ajuste de layout: número e data realinhados à direita (saíam fora da página A4).

**F2 — Contrato editável protegido + edição pontual gerencial:**
- `preencher_contrato(..., protegido=True)`: valores envoltos em `permStart/permEnd` (editáveis) + `documentProtection edit=readOnly` (texto fixo e cabeçalho travados) — `_proteger_editaveis`.
- `_converter_pdf(docx_path)` extraído (converte sem regenerar o docx).
- `POST /api/projetos/<nome>/contrato/editar`: gate gerencial (gerente/diretor/admin, auditado `editar_contrato`), abre o `.docx` no Word/LibreOffice e inicia watcher (`contrato_editar.py`: mtime + lock + debounce + timeout) que regera o PDF a cada salvamento.
- Botão "✎ Editar contrato" + modal gerencial no frontend.

**Processo:** ambos (F1, F2) pelo pipeline superpowers (spec → plano → subagentes com revisão em duas etapas → verificação com dados reais → merge). Suíte: **93 testes** passando.

**Banco:** coluna `contratos.num_contrato` (VARCHAR(30), via `_migrar_colunas`).

---

### Sessão 2026-06-17 (sessão 8 — redesenho do ciclo de vida, sub-projetos A–E)
**Spec e implementação:**
- **A) Etapas — ordem + gating:** códigos renumerados ("2"=Criação do projeto, "3"=Briefing); gating sequencial (PATCH /ciclo rejeita 400 se etapa anterior não concluída; UI mostra 🔒); sub-etapas livres; reabertura em cascata por gerente via POST /api/projetos/<nome>/ciclo/<codigo>/reabrir (auditada em `log_acoes_gerenciais`, bloqueia se contrato assinado); criar projeto marca etapas 1 e 2 (Briefing 3 pendente); módulo `mod_ciclo.py`
- **B) Cadastro completo na aprovação:** criar cliente exige nome+email+telefone (CPF opcional); modal de aprovação não edita mais cliente; `validar_cliente_para_contrato` bloqueia contrato sem cadastro completo (HTTP 400 + `campos_faltando` → popup "Cadastro Incompleto")
- **C) Aprovação — semântica + botão:** "Aprovar Orçamento" conclui Revisão (5) e Aprovação (6) juntas; etapa 5 sem toggle manual; `desfazer_aprovacao` reseta 5/6/7; botão pós-aprovação "Orçamento aprovado – assinar contrato" leva ao card de assinatura
- **D) Briefing obrigatório por-projeto:** briefing agora por-projeto (coluna `briefings.projeto_nome`); endpoints GET/POST /api/projetos/<nome>/briefing; etapa 3 marcada só no projeto; criar projeto → briefing obrigatório → negociação; backend bloqueia orçamentos/pool sem briefing completo do projeto (400)
- **E) Contrato — signatário/testemunhas/formatação + enforcement:** 2º signatário = cliente (não consultor); INSPIRIUM intacta; testemunhas provisórias (Jaime Perinazzo/Felipe Guizalberte); CPF→CPF/CNPJ; tags de nomenclatura (rótulo cinza ~7pt) nos campos editáveis; gate de ambiente (POST /contrato 400 sem ambientes); `signatario_override` (modal "é o cliente cadastrado?"); bug-fixes: popup troca de modal, bloqueio de aprovação sem ambiente
- **Banco novo:** tabela `log_acoes_gerenciais`; coluna `briefings.projeto_nome`; tabela `schema_migrations`

---

### Sessão 2026-06-15 (sessão 7 — ciclo completo 20 etapas + módulo contrato + aprovar orçamento)
**Commits:** `3861470` → `b5d2ad3` (13:39 → 21:19)

**Spec e planejamento:**
- `docs/`: spec ciclo completo com 20 etapas, contrato, NFe cliente (2 iterações com correção de etapa 6 e endereço de instalação)
- Plano de implementação do módulo de contrato (7 tasks, TDD)

**Backend — módulo ciclo + contrato:**
- Models: `CicloEtapa`, `Contrato`, `ContratoAssinatura` (SQLAlchemy)
- `mod_contrato.py`: geração de docx via `docxtpl` + conversão para PDF via LibreOffice; fallback `LibreOfficeIndisponivel` salva `.docx` e avança status sem travar; hash SHA-256 de assinatura
- `config/contrato_template.docx`: template com 13 variáveis Jinja2 (cliente, valores, parcelas, endereços)
- `scripts/configurar_template_contrato.py`: popula automaticamente as variáveis no .docx base
- `main.py`: `_montar_dados()` inclui `valor_liquido`; 9 novas rotas (ciclo, contrato, orcamento valor)
- Auto-criação de etapas 1-5 como concluídas no `GET /ciclo` para projetos com negociação ativa

**Interface — aba Ciclo (page-02):**
- Nova aba "Ciclo" na barra superior da page-02
- 20 etapas em 2 colunas (esq: 1-10, dir: 11-20); toggle clique para concluir/reabrir
- Card 7 (Contrato): botão gerar, preview, download PDF/docx, botão assinar, campo senha gerente
- Card 16 (Adendo): UI placeholder para futuro
- Após gerar contrato: abre aba Ciclo no card 7 automaticamente
- Botões "Salvar Parâmetros" e "Aprovar Orçamento" ocultos quando etapa 6 concluída
- `carregarCicloSilencioso()`: carrega `_cicloData` ao abrir projeto sem exibir o painel

**Interface — Aprovar Orçamento reformulado:**
- `salvarValorNegociado()`: persiste valor negociado e forma de pagamento antes de abrir modal
- Modal de aprovação: dados do cliente, CPF e endereço de instalação destacados se vazios, condições de pagamento pré-carregadas da negociação ativa
- Status renomeados: `gerado` → `para_assinatura`, `vigente` → `assinado`
- Badges CSS para `para_assinatura`, `rascunho`, `assinado`
- Botão Omie removido da action-row (migrado para etapa 12 do Ciclo)
- Campo entrada com máscara moeda `R$ X.XXX,XX` em tempo real; `parseMoeda()` para leitura
- `mascaraMoedaInput()` reescrita: cursor estável, formato centavos-first correto

**"Voltar ao Orçamento" (desfazer aprovação):**
- `abrirModalVoltarOrcamento()`: modal com login/senha de gerente
- `POST /ciclo/desfazer_aprovacao`: valida gerente, reseta etapas 6 e 7; disponível somente antes de contrato assinado

**Bugs corrigidos:**
- Auto-load projetos ao abrir app (`DOMContentLoaded → projCarregar()`)
- LibreOffice indisponível: exceção `LibreOfficeIndisponivel` específica — salva .docx e avança sem crash
- Etapa 6 não era mais hardcoded como concluída — marcada corretamente ao gerar contrato
- Card 7: exibe botão baixar .docx + aviso dourado quando LibreOffice não disponível
- `GET /contrato/pdf` serve .docx com `Content-Type` e `Content-Disposition` corretos; retorna `arquivo_tipo`
- `usuario.id` → `usuario['id']` no PATCH ciclo (fix KeyError)
- `PROJETOS_DIR` absoluto no helper contrato (fix path relativo)
- Botão dourado `Etapas do Projeto` e template do usuário corrigidos

---

### Sessão 2026-06-15 (sessão 6 — admin + omie sync + lista projetos + pipeline)
**Commits:** `0bcc154` → `44863eb`

**Funcionalidades adicionadas:**

**EP-08 — Sincronização Omie e Painel Admin:**
- **Role Admin:** novo nível `admin` no banco — acesso total a vendas + painel exclusivo (page-07). Limite de desconto 50%. Usuário de teste: `admin2026`/`admin123`
- **Auto-sync cliente → Omie:** `POST /api/clientes` tenta `criar_cliente()` em background thread após salvar localmente. Grava `omie_sync_status` (`ok`/`pendente`/`erro`) + `omie_sync_erro` na tabela `clientes`. Pendente = sem CPF ou sem credenciais Omie; Erro = falha da API
- **Painel Admin (page-07):** lista clientes com sync pendente/erro com botão "Tentar" por entrada. Acessível apenas para role `admin`. Nav item `⚙ Admin` aparece na sidebar somente para admin
- **PATCH `/api/projetos/<nome>/status`:** muda status do projeto (quente/morno/frio/perdido). Rejeita "convertido" via API
- **Convertido automático:** `bloquear_projeto()` seta status `convertido` em `projetos_meta` ao aprovar

**EP-09 — Lista de Projetos e Pipeline de Vendas:**
- **Lista redesenhada:** tabela com colunas Status | Data | Projeto | Cliente | Último Orçamento. Substitui cards anteriores
- **Filtro de texto:** busca simultânea em nome do projeto, nome do cliente e CPF do cliente (client-side)
- **Filtro multi-select de status:** dropdown com checkboxes por status (OR lógico); botão mostra contagem ativa
- **Status pipeline:** `quente` / `morno` / `frio` / `convertido` / `perdido`. Tabela `projetos_meta` no banco
  - `perdido` grava `perdido_em` automaticamente
  - Dropdown inline na lista para alterar status
  - Botão de status no cabeçalho da page-02 (negociação)
- **UX lista:** duplo clique ou botão "Abrir →" entra no projeto; `goPage(n)` corrigido para navegar mesmo sem nav item na sidebar
- **Último orçamento ativo:** `ativarOrcamento(id)` grava em `localStorage['lastOrc_<nome_safe>']`; `carregarOrcamentos()` restaura ao reabrir projeto

**Bugs corrigidos:**
- `goPage(2)` bloqueava com `if(!navEl) return` após remoção de `nav-02` — corrigido para `if(navEl && navEl.classList.contains('locked')) return`
- Badge de status `—` (sem status) não era clicável — corrigido para abrir dropdown
- `orcamento_ativo_id` no `projeto.json` sempre apontava para Orçamento 1 — descartado em favor de localStorage + `updated_at`
- Subquery `func.max(updated_at)` indeterminística com empate — substituída por `.order_by(updated_at.desc(), id.desc()).first()`
- Clientes com `omie_sync_status IS NULL` invisíveis no painel admin — corrigido com `or_(in_(), is_(None))`
- Missing `return` após "Cliente não encontrado" no retry endpoint

**Sidebar e navegação:**
- Removidos: `nav-new-amb` (Novo Ambiente), `nav-02` (Negociação), `nav-03` (Exportar)
- Adicionado: `nav-07` Admin (oculto por padrão, visível apenas para role admin)
- Barra de orçamentos: `Ambientes` | `Novo Ambiente` | `Novo Orçamento` (3 botões)
- `unlockNav(2)` e `unlockNav(3)` mantidos por compatibilidade (null-safe)

---

### Sessão 2026-06-12 (sessão 5 — bugs EP-07 + desconto individual + limites + UX)
**Commits:** `5ccb96d`, `019eb6b`, `b6e8d3f`, `74a4710`, `5349427`, `f1a0c30`

**Bugs corrigidos:**
- **BUG-EP07-03:** `uploadXmls` em modo EP-07 não chama mais `/ambientes/adicionar`. Arquivo salvo no disco somente após `db.commit()` bem-sucedido (endpoints: pool/novo, sobrescrever, nova_versao, criar_forcado)
- **Cards 0 ambientes:** `_enriquecer_projetos_com_pool()` em `main.py` sobrescreve `n_ambientes`/`n_selecionados` com contagem real do banco para projetos EP-07
- **Painel de apoio modal EP-07:** `mpAtualizarApoio` agora faz loop per-ambiente e aplica `_descIndividual` antes de somar
- **Discriminação por ambiente EP-07:** `atualizarDiscriminacao` usava `projetoAtivo.ambientes` (vazio); corrigido para usar `_orcAmbientesAtivos` com desconto efetivo combinado

**Funcionalidades adicionadas:**
- **Desconto individual por ambiente (EP-07):** coluna "Desc.%" com input editável na tabela de negociação. Fórmula: `avista = bruto × (1−desc_global%) × (1−desc_individual%)`
- **Limite de 35% no desconto total:** `_margemAtual` atualizado por `mpAtualizarApoio`; bloqueia save de parâmetros; reverte desconto individual via `_onDescIndBlur`
- **Esc fecha modal ativo:** listener global percorre modais do z-index mais alto ao mais baixo e chama a função de cancelar do primeiro visível (15 modais cobertos)

---

### Sessão 2026-06-10 (sessão 4 — EP-07 completo)
**Commit:** `79cec86` — feat: EP-07 versionamento de orcamentos completo (passos 1-12)

**Realizado:**
- EP-07 Versionamento de Orçamentos completo — todos os 12 passos implementados sem bugs
- Passos 1-8: backend (tabelas, rotas, pool, orçamentos, recálculo)
- Passos 9-12: interface (barra de orçamentos, painel Ambientes, novo orçamento, renomear)
- Modal de parâmetros corrigido para calcular sobre ambientes do orçamento ativo
- Upload de XML vincula automaticamente ao orçamento ativo quando ambiente já existe no pool
- Servidor DEV atualizado: `167.88.33.121:8765` rodando com screen

**Documento criado:**
- `docs/modulos/financeiro/FUTURO_CALCULO_FINANCEIRO.md`

**Pendente:**
- Bug toggle "incluir custos adicionais" (da sessão 2) — ainda em aberto
- Total Flex (US-14) — planejado para v0.2.0
- Módulo Clientes e Parceiros vinculados a orçamentos — planejado

### Sessão 2026-06-09 (sessão 3 — documentação)
- BACKLOG.md com 26 histórias (EP-01 a EP-07)
- 7 SPEC.md de módulos
- VERSIONAMENTO.md com spec completo do EP-07

### Sessão 2026-06-09 (sessão 2)
- Módulo Clientes completo
- Projeto vinculado a cliente obrigatório

### Sessão 2026-06-07/08 (sessão 1)
- Sistema de autenticação completo
- Módulo Parceiros
- Toggle custos adicionais

## Sessão 27 — Cutover do motor de negociação (Fase B)

A tela de negociação e o modal passam a usar o motor `mod_negociacao` (não mais o cálculo
legado do frontend):
- **Preview endpoint** `POST /api/orcamentos/<id>/negociacao-preview` (puro, sem gravar):
  display ao vivo da cadeia do motor; helper compartilhado `_negociacao_breakdown`.
- **Persistência autoritativa**: `_recalcular_orcamento` grava `valor_total = Val_Cont` e
  `valor_liquido = Val_Liq` no save de margens e no PATCH; o frontend deixa de enviá-los e o
  PATCH não os aceita mais. O contrato reflete automaticamente (lê `valor_total`/`valor_liquido`).
- **UI**: `negPreview()`/`_aplicarPreviewNaTela()` sobrepõem bruto negociado / à vista / comissão
  arquiteto / fidelidade / líquido / %desc total e o `neg-avista` (que alimenta o pagamento via
  `mod_fin`); limite de 35% sobre o `%Desc_Tot` do motor. `mod_fin` reusado como está.
- **Segurança**: golden-master `scripts/snapshot_cutover.py` (baseline) + `scripts/diff_cutover.py`
  (old×new); rollback na tag `pre-refator-negociacao`.
- **Pós-cutover**: `scripts/reset_para_teste.py` (DESTRUTIVO — cancela contratos, volta o ciclo à
  fase de orçamento, recalcula tudo) para testar o fluxo inteiro + transições de fase. Backup antes.
- **Fase C** (limpeza do legado: `margens` duplicado, `custo_financeiro_pct` do `mod_margens`)
  fica para depois.

## Sessão 28 — Bloqueio dos campos de impostos

Base tributária e provisão de impostos passam a ficar **ocultas (🔒)** por padrão na tela; o
sistema continua calculando, mas só revela mediante senha de **Diretor ou Gerente
Administrativo-Financeiro** (capacidade `aprovar_financeiro`).
- **Backend:** `POST /api/auth/liberar_impostos` (auth_routes.py) — valida usuário+senha e
  `perfis.pode(nivel, "aprovar_financeiro")`; 401 (credencial inválida) × 403 (sem capacidade).
- **Frontend:** `_atualizarImpostos` cacheia em `_impostosValores` e delega a `_renderImpostosLock`
  (único exibidor): valor real se `_impostosLiberados`, senão cadeado clicável. Modal
  `modal-liberar-impostos`. Valor liberado é clicável para re-bloquear. Estado **não persistido**
  (recarregar re-bloqueia — escopo de sessão/timer é tratamento futuro).
- **Cobertura:** os IDs `-r-base-trib`/`-r-impostos` são compartilhados pelos 4 painéis de
  pagamento → a tela do projeto fechado fica coberta automaticamente.
- **Honesto:** é bloqueio de **apresentação** (valores calculados no cliente), não sigilo
  criptográfico.

## Sessão 29 — Fase 2: distribuição brinde/viagem + fonte única da tela + persistência do pagamento

Branch `feat/fase2-autosave-negociacao`. Continuação da faxina single-source.

- **Auto-save incremental da negociação:** "trava" o orçamento ao sair (troca in-app via
  `ativarOrcamento` com `await salvarValorNegociado()`; `beforeunload` com `keepalive`). O front
  não persiste estado — o backend é a fonte.
- **Brinde/viagem distribuídos pelo POOL do projeto** (`mod_negociacao`): brinde **igual** por
  ambiente (`bri/n_total_proj`), viagem **proporcional** ao valor (`cust_via × vbva/vbvo_proj`).
  Um orçamento subconjunto (3 de 7) recupera a sua fração. `_negociacao_breakdown` calcula
  `n_total_proj`/`vbvo_proj` do pool e passa ao motor (preview e `_recalcular_orcamento`).
  Fallback ao comportamento atual quando os args são `None` (âncora LELEU inalterada).
- **Tela de negociação — fonte única (Opção B):** o motor é a única fonte de todos os números da
  tabela por ambiente.
  - **Desconto por ambiente robusto:** `renderTabelaNeg` lê de `pa.desconto_individual_pct`
    (`_descIndividual` só como override de edição) → aparece já na 1ª entrada, sem timing.
  - **Duas colunas por ambiente:** **À vista** (`VAVA`) e **Com financiamento**
    (`VAVA × Val_Cont/VAVO`), ambas escritas por `_aplicarPreviewNaTela`; total à vista (`VAVO`) +
    total de contrato (`Val_Cont`) no rodapé. `_ep07DistribuirFinanciado` aposentado (no-op).
  - **Total único (fim da corrida):** só `_aplicarPreviewNaTela` escreve `neg-total`/
    `neg-total-final` = `Val_Cont`. O fluxo de pagamento parou de escrevê-los; ao trocar a
    modalidade, **auto-salva** `forma_pagamento` (`agendarSalvarPagamento`, debounced) → o motor
    recalcula `Val_Cont` → `negPreview` reexibe. **Guard de assinatura** (dentro do timer) quebra
    o loop preview↔pagamento (só salva se o plano mudou).
- **Persistência do plano de pagamento (3 bugs corrigidos):**
  - **Aymoré:** passou a salvar a **data da 1ª parcela** (`ay-data-primeira` faltava em
    `_NEG_CAMPOS_POR_MODALIDADE`).
  - **Auto-save na carga:** `_carregandoOrcamento` suprime o auto-save do pagamento durante a
    carga do orçamento (defesa contra salvar o estado default antes do restore).
  - **Causa-raiz "perde o parcelamento no hard refresh" (mantinha a modalidade):** confirmada por
    log de console — `carregarMargensSalvas` é re-disparado na **navegação p/ a página 2**
    (e em add-ambiente/save-params) **sem `_negociacaoPendente`**; `carregarModalidades →
    onPagamentoChange(default)` **zerava `neg-parcelas`** (volta a 1) e um auto-save salvava
    `n_parcelas=1`, sobrescrevendo o plano. Só o orçamento ativo (o único recarregado) era afetado.
    **Fix single-point:** se há orçamento ativo e nenhuma restauração pendente, `carregarMargensSalvas`
    **captura a negociação atual da tela e a re-restaura** após o reset — cobre os 3 re-triggers.
- **Pendente (Fase 2, futuro):** seletor de ambientes para brinde/viagem; faxina de schema
  (`custo_financeiro_pct`, `margens` duplicado, `valor_liquido` legado); duplicidade de
  armazenamento `total_cliente` × `Val_Cont`. 301 testes verdes.

## Sessão 30 — Faxina de legado de margem + glossário de nomenclatura

Branch `faxina/schema-fase2`. Objetivo (do usuário): **nomenclatura bem definida** + um
**mecanismo para sempre falarmos a mesma língua**, eliminando legado sem trazer falhas.

- **`docs/referencia/NOMENCLATURA.md`** — glossário **canônico** das siglas fechadas (VBVA/VBNA/VAVA,
  VBVO/VBNO/VAVO, Com_Arq/Pro_Fid/Cust_Via/Bri/Cust_Ad/Val_Liq/Desc_Tot/Markup/Cust_Fin/Val_Cont/
  Prov_Imp), contexto do pool (`n_total_proj`/`vbvo_proj`), onde cada parâmetro fica salvo, a
  nomenclatura **removida** (não reusar) e o **mecanismo**: o motor `mod_negociacao` é a fonte única;
  todo número vem dele.
- **Discriminação por ambiente removida** (decisão do usuário — tinha falhas, não é necessária; no
  futuro refazer pelo motor). Saíram: HTML do painel, `toggleDiscriminacao`/`atualizarDiscriminacao`/
  `lerMargensModal`. `agendarDiscriminacao` → **`agendarParametros`** (só apoio + auto-save).
- **Legado de margem removido:** `mod_margens.calcular_margens` + endpoint `POST /calcular_margens`
  + `ratearViagem` + o path legado Fase 01 de `executarCalculo` (só o EP-07 sobrou) + `test_margens.py`
  + `custo_financeiro_pct` dos defaults de params. **Mantido `mod_margens._normalizar_faixas`/`_pmt`**
  (vivos, servem o endpoint de faixas).
- **Motor** ganhou (aditivo, TDD) o waterfall por ambiente (`Com_Arq/Pro_Fid/Cust_Via/Bri/Val_Liq`,
  Σ por ambiente = agregados) — disponível para uso futuro pelo motor.
- **Vestígios Fase 01 em caminhos mortos** (`lerMargensNegociacao`, `_negBaseValues`, branch legado de
  `renderTabelaNeg`) ficam sinalizados para uma passada futura (entrelaçados com funções vivas).
- **Não-feito (irreversível):** drop da coluna `Orcamento.margens` — exige backup do `orizon.db` +
  aprovação. **295 testes verdes** (caíram 7 do `test_margens` removido).
- **Fix (race do desconto por ambiente):** o desconto só era salvo no blur (`_persistirDescontosOrc`,
  fire-and-forget) e corria com a troca de orçamento (o `_orcamentoAtivoId` mudava antes do commit) →
  desconto não ficava guardado / aparecia stale (intermitente). **Fix:** `ativarOrcamento` aguarda
  `_persistirDescontosOrc` antes de trocar; `_onDescIndBlur` captura o orçamento do blur e aborta se
  trocou durante o `await`. (Race pré-existente, não da faxina.)

## Sessão 31 — Drop da coluna `Orcamento.margens` (fecha a faxina de schema)

Branch `faxina/drop-orcamento-margens`. Usuário autorizou (base é teste; backup feito:
`omie.db.bak-2026-06-24-pre-drop-margens`). A coluna era **duplicação legada** — o motor lê
`Projeto.parametros_json` + `Orcamento.desconto_pct`.

- **Código para de usar `orc.margens`:** `GET /ambientes` e `POST /margens` passam a devolver
  `desconto_pct` (coluna canônica) em vez de um objeto `margens`; criação de orçamento copia
  `desconto_pct` da origem; frontend lê `d.desconto_pct` (não `d.margens.desconto_pct`).
- **Schema:** coluna `margens` removida do modelo `Orcamento`; funções de migração obsoletas
  (`migrar_margens_para_orcamentos`, `migrar_parametros_para_projeto`) e seus call-sites/testes
  removidos; `test_legado_intacto` passa a exigir que `margens` **não** exista.
- **Migração idempotente** `_drop_coluna_margens_orcamentos` (startup, sqlite≥3.35) dropa a coluna
  em DBs existentes; DBs novos já nascem sem ela. **Aplicada ao `orizon.db`** (dados preservados:
  21 orçamentos / 13 contratos). **291 testes verdes** (caíram os 4 testes das migrações obsoletas).
- **Desconto por ambiente — alinhado ao padrão dos campos que funcionam:** era o único campo que
  salvava **só no blur** (`_persistirDescontosOrc`, frágil). Agora:
  - **auto-save debounced no `oninput`** (`agendarSalvarDescontos`, 500ms — espelho do
    `agendarSalvarParametros`); o **`beforeunload`** também persiste (keepalive); a troca de orçamento
    (`ativarOrcamento`) aguarda o save; o limite continua no blur.
  - **Causa-raiz do "input volta ao valor antigo, mas a conta fica certa":** `_persistirDescontosOrc`
    gravava no banco mas **não atualizava `_orcAmbientesAtivos` em memória**; quando `_descIndividual`
    era zerado (`carregarMargensSalvas`) e `renderTabelaNeg` rodava, o input lia o
    `pa.desconto_individual_pct` antigo (o motor lia do banco → conta certa). **Fix:** o save
    sincroniza `pa.desconto_individual_pct` em memória com o valor digitado.

## Sessão 32 — Três frentes: super-admin/árvore, acesso multi-loja, e config financeira/provisões

Três workstreams iniciados hoje (2026-06-24). As duas primeiras com código pronto (TDD +
revisão final opus), **aguardando validação no browser** antes do merge; a terceira em spec.

### Frente A — Super-admin: aterrissagem por papel + árvore estrutural (slice #1+#2)
Branch `feat/super-admin-arvore` (de `main`). super_admin/admin_rede passam a **aterrissar no
Painel Admin** (não em Projetos); menu operacional escondido só p/ super_admin; **árvore** estende
o drill até `Rede › Loja › Projeto › Etapas do ciclo` (estrutural, **sem PII** — PII fica p/ painel
LGPD futuro). Módulo puro novo `mod_arvore.py` + 2 rotas GET finas. Revisão final opus PRONTO P/
MERGE; fix I1 (teste e2e cross-rede 403). **Bugfix pré-existente:** botões "Entrar" rede/loja
quebravam com nome com espaço (onclick aspas duplas + JSON.stringify) → aspas simples + `_attrJson`.
- **Arquivos:** `mod_arvore.py` (novo); `tests/test_arvore.py`, `tests/test_arvore_e2e.py` (novos);
  `main.py` (rotas `GET /api/admin/lojas/<id>/projetos` e `/api/admin/projetos/<nome>/etapas`);
  `static/index.html` (aterrissagem `_aterrissarPorPapel`, nível 4 da árvore, fix dos botões Entrar).
- **Docs:** `docs/superpowers/specs/multitenant/2026-06-24-super-admin-aterrissagem-arvore-design.md`;
  `docs/superpowers/plans/2026-06-24-super-admin-aterrissagem-arvore.md`.

### Frente B — Acesso multi-loja (loja ativa por requisição)
Branch `feat/multi-loja` (empilhada sobre `feat/super-admin-arvore`). Um usuário acessa N lojas e
opera numa **loja ativa** por vez, escolhida via header `X-Loja-Ativa` (lido só em `_ator_dict`;
`escopo_operacional` é o funil — ~51 call sites inalterados). Tabela M:N `usuario_lojas` +
backfill; `usuarios.loja_id` mantido como loja default. `resolver_loja_ativa` fail-closed (header
não-membro → 403). `/api/auth/me` expõe `lojas` + `loja_ativa_id`. Criação/edição de usuário aceita
`loja_ids`. Contrato usa a loja ativa. Frontend: interceptor de `window.fetch` + seletor + modal
multi-loja. Revisão final opus PRONTO P/ MERGE; fixes: `do_PUT` lê o header (contexto obsoleto),
edição não dropa memberships fora do escopo do ator de loja, coerção de `loja_ids`.
- **Arquivos:** `database.py` (`UsuarioLoja` + backfill + `membership_loja_ids`); `mod_tenancy.py`
  (`resolver_loja_ativa`, `escopo_operacional`, `lojas_do_novo_usuario`); `main.py` (`_ator_dict` +
  header nos 4 dispatch, rotas de usuário, contrato); `auth_routes.py` (`/api/auth/me`);
  `static/index.html` (interceptor + seletor + modal); `tests/test_multi_loja.py`,
  `tests/test_multi_loja_e2e.py` (novos); `tests/test_isolamento_f4.py` (3 dicts unit ajustados).
- **Docs:** `docs/superpowers/specs/multitenant/2026-06-24-acesso-multi-loja-design.md`;
  `docs/superpowers/plans/2026-06-24-acesso-multi-loja.md`.

### Frente C — Config financeira da loja / provisões / margem real / comissões (EM SPEC)
Retomada da especificação do painel financeiro com todas as provisões. Consolidada a **tabela
canônica do motor** (config por loja + variáveis de projeto/orçamento/ambiente + fórmulas das
provisões). Decisões fechadas: imposto único (`Prov_Imp`, sem dedup `Imp_Orc`); `%Car_Trib` migra do
modal p/ config da loja (0 até a 1ª versão); margem via `Cust_Var` (inclui `CFO` + `Out_Forn`) e
`Marg_Cont = (Val_Liq − Cust_Var)/Val_Liq`; comissões com base `Val_Liq` (frete local/assist/insumos
sobre `VAVO`; frete fábrica sobre `CFO`). **Comissão de vendas** = rotina por consultor (2
configuradores num modal, regra no backend): faixas por `Val_Liq` mensal acumulado + limitador de
desconto (toggle) que reduz o **%** da venda específica por `%Desc_Orc`. **Faseamento:** v1 = config
`%` simples + margem real (faixas/limitador entram como config); fase 2 = acumulador mensal por
consultor + fechamento de ciclo (provisório→definitivo); fase 3 = custo financeiro absorvido em
`Cust_Var`; futuro = condições de pagamento por loja + divisão de `Com_Adm` por função.
- **Doc/referência (novo):** `docs/modulos/financeiro/PROVISOES_E_VARIAVEIS.md` (tabela + rotina de
  comissão + faseamento).
- **Material âncora:** `FUTURO_CALCULO_FINANCEIRO.md`, `NOMENCLATURA.md`,
  `docs/modulos/financeiro/SPEC.md`, `docs/superpowers/specs/ciclo/2026-06-15-ciclo-completo-projeto-design.md`
  (§Provisões financeiras), `docs/superpowers/specs/negociacao/2026-06-22-mecanismo-negociacao-design.md`.
- **Spec/plano:** ainda **não escritos** (próximo passo do brainstorm).

## Sessão 33 — Testes (config financeira) + ajustes de leitura/contrato

Dia de validação manual no browser da Frente C. Achados e mudanças:
- **Modo somente-leitura em projeto fechado** (commit `3183789`): `btn-params` deixa de ser
  escondido com contrato assinado; o modal de Parâmetros abre travado (inputs disabled/readonly,
  Salvar oculto, badge "🔒 somente leitura") e expõe a margem real sob o cadeado de impostos.
- **Fix de visualização de contrato** (commit `4c8076c`): `contrato.pdf_path` de contratos antigos
  foi salvo como caminho ABSOLUTO do Windows (`E:/.../orizon-manager/...`) — não resolve em WSL/Linux
  (case-sensitive) e o contrato não abria mesmo com o PDF presente. `_resolver_pdf_contrato` cai
  para `CONTRATOS_DIR/<basename>`. Aplicado nas rotas `GET /contrato/pdf` e `GET /contrato`.

### ⚠️ PROBLEMAS REGISTRADOS PARA TRATAR (teste e2e do usuário, em breve)
1. **Contrato defasado vs negociação:** num projeto com vários orçamentos, o contrato foi gerado
   de um orçamento (ex.: Cartão) enquanto a negociação exibida está em outro (ex.: Aymoré). O PDF
   é snapshot do momento da geração e não acompanha mudanças posteriores. **A tratar:** vincular
   claramente o contrato ao orçamento de origem e/ou alertar/regenerar quando o pagamento mudar
   após a geração (guard de staleness). Validar no teste e2e do início ao fim.
2. **super_admin não acessa negociação operacional nem `aprovar_financeiro`** — a margem real só
   é visível para diretor/gerente adm-fin (correto por design; registrado p/ alinhamento de UX).
3. **Dados de teste inconsistentes** (Projeto_2 sem etapa 6; contratos antigos): preferir um teste
   e2e limpo (criar projeto pela UI do início ao fim) a remendar seed.

### DEFERIDOS da Frente C (follow-ups, não bloqueiam):
- Edição de `Out_Forn` (sem rota PATCH ainda); wiring de `parametros_default_loja` na criação do
  projeto (carga_trib da loja ainda não flui ao Prov_Imp); acumulador mensal da comissão (Fase 2).

## Sessão 34 — Close-out da Frente C (autônomo)

Trabalho autônomo (usuário ausente) fechando os follow-ups da Frente C. Tudo na branch
`feat/config-financeira-provisoes` (empilhada). Suíte: **357 passed**.
- **P2 — wiring `parametros_default_loja`** (`3d13947`): `_negociacao_breakdown` carrega a config da
  loja uma vez no topo; projeto sem `parametros_json` herda os defaults de negociação da loja
  (a `carga_trib` da loja passa a fluir ao `Prov_Imp`/margem). Projetos com params próprios: intactos.
- **P1 — edição de `Out_Forn`** (`4911c8d`, `92a2222`, `059c7c5`): rota `PUT /api/orcamentos/<id>/out-forn`
  (espelha `/descontos`, escopo + IDOR), campo editável no painel de apoio do modal de Parâmetros
  (travado em modo read-only), recálculo da margem na hora. Fix de revisão: clamp `out_forn>=0` +
  validação de corpo (400) + testes de IDOR/clamp.
- **P3 — guard de contrato desatualizado** (`1382ad9`, `66f4fcc`): `mod_contrato.contrato_desatualizado`
  compara o snapshot `pagamento_json` com a `forma_pagamento` atual do orçamento de origem (tipo +
  total); `GET /contrato` devolve `desatualizado`; banner de aviso na etapa Contrato. Resolve o
  achado da Sessão 33 (contrato Cartão × negociação Aymoré).

## Sessão 35 — Provisões versionadas + faxina de branches

- **Frente "Provisões versionadas + aprovação financeira"** implementada (SDD, 6 tasks TDD,
  suíte 369, review final READY TO MERGE) e **mergeada na `main`**: tabela `provisao_registro`
  (venda/rev1/rev2), `mod_provisoes.itens_provisao`/`cust_var_marg_cont`, "Venda" congelada na
  geração do contrato, rotas `GET/POST /api/orcamentos/<id>/provisoes` (Concorda/Revisa com senha
  `aprovar_financeiro`, 409/IDOR/clamp), e o botão "Provisões" na etapa de Aprovação Financeira
  (tabelas Venda|Rev1|Rev2|Atual). Spec/plan em `docs/superpowers/{specs,plans}/2026-06-27-*`.
- **Faxina de branches:** apagadas as 5 da Frente C (já mergeadas) + `feat/multitenant-f2-tenancy`
  (mergeada) + `master`. A `master` continha um commit "v2.0.0" (Total Flex / Venda Programada /
  Cartão X) — **conferido**: a `main` já tem esses arquivos (venda_programada/cartao_x idênticos,
  total_flex mais novo), v2.0.0 superado → descartado sem perda.

### Isolamento multi-tenant de pool/medição/ciclo — F4 conferido e DISPENSADO
O worktree `worktree-agent-a3876ec2c1cd36c64` tem o commit `1aa8231` "feat(isolamento): escopo de
pool/medicao/ciclo (F4)" (2026-06-21), que adicionava guard de loja (`escopo_operacional` +
`_projeto_da_loja → 404` + 401/403) a pool/medição/ciclo. **Verificado rota a rota: a `main` JÁ tem
esse guard em todas** — `/ciclo`, `/ciclo/desfazer_aprovacao`, `/medicao`, `/medicao/arquivo`,
`/medicao/solicitacao`, `/medicao/parecer`, `/pool`, `/pool/criar_forcado` (a main tem 31 pontos com
`_projeto_da_loja`, implementados nas frentes multi-loja/árvore posteriores). F4 é **redundante** —
não reaproveitar (aplicá-lo só geraria conflito nas mesmas rotas já reescritas). Worktree mantido
como está (gerenciado pelo ambiente).

## Sessão 36 — E2E do início ao fim + faxina de artefatos de contrato

Suíte: **371 passed**. Tudo na `main`.

### E2E do início ao fim (`tests/test_fluxo_completo_e2e.py`)
Servidor HTTP real + login real (harness do conftest), dois fluxos:
- **`test_fluxo_completo_inicio_ao_fim`** — login → negociação (motor + margem real: VBVO/CFO/Val_Liq/
  Cust_Var/Marg_Cont) → `Out_Forn` reflete no Cust_Var → ciclo carrega → "Venda" registrada (hook) →
  **Provisões**: Venda → Rev 1 (Concorda = cópia) → Rev 2 (Revisa = edita Out_Forn, margem recalcula
  da base congelada) → **consistência** (negociação muda após a Venda → `desatualizado=true`) →
  **IDOR** (diretor de outra loja → 404).
- **`test_contrato_real_geracao_e_assinatura`** — **geração REAL** do contrato via
  `POST /api/projetos/<n>/contrato` (gera o `.docx` por python-docx) → `para_assinatura` (+ aviso de
  LibreOffice ausente, degradação graciosa) → hook real grava a Venda → arquivo servível
  (`GET /contrato/pdf` 200) → **assinatura loja + cliente** → `assinado`, etapa 7 concluída,
  projeto `fechado`. Hermético: fixture `contratos_dir` isola `CONTRATOS_DIR` num temp.

**Limite de ambiente (não do produto):** sem LibreOffice (`soffice`) o contrato sai `.docx` em vez de
PDF — único passo dependente de `soffice`. O PDF real valida-se no ambiente do usuário (com LibreOffice).
Upload de XML coberto por `test_qualidade_upload_e2e`; ambiente montado no banco (PoolAmbiente).

### Faxina — artefatos de teste de contrato
`test_contrato.py` gerava `.docx` de ids mágicos (`contrato_99/8888/9999.docx`) direto na pasta
`CONTRATOS/` do repo (não isolava `CONTRATOS_DIR`). Adicionada fixture `autouse` que redireciona
`CONTRATOS_DIR` para um temp; artefatos antigos (untracked) removidos. Confirmado: rodando a suíte
completa, nenhum `.docx` novo é escrito no repo. Contratos reais (`contrato_1..15`) preservados.

## Sessão 37 — Etapa Orçamento como hub + Imprimir Orçamento (proposta)

Frente desenhada (brainstorm→spec→plano) e implementada (SDD, 5 tasks TDD, suíte 378, review final
READY TO MERGE) e **mergeada na `main`**. É o 1º documento do banco de documentos da loja (#8).
Spec/plan em `docs/superpowers/{specs,plans}/2026-06-28-*`.

- **Renomear** etapa 4 "Primeiro orçamento" → **"Orçamento"** (`mod_ciclo.ETAPA_NOME` + frontend).
- **🖨 Imprimir Orçamento** na negociação (junto de Salvar/Aprovar).
- Card da etapa **Orçamento**: lista os orçamentos (Abrir → negociação; Imprimir → proposta).
  Card da etapa **Aprovação**: orçamento aprovado (`contrato.orcamento_id`) com Abrir/Imprimir.
- **Proposta** (`mod_proposta.py`, reusa `_substituir_marcadores`/`_montar_mapping`/`construir_contexto`
  de `mod_contrato`) a partir do template **global** `modelo_proposta.docx` (base 1ª pág do contrato,
  sem cláusulas). Rota `GET /api/orcamentos/<id>/proposta/pdf` — **sob demanda, sem salvar**
  (gera em `tempfile.mkdtemp`, serve inline, remove o temp), escopo por loja + IDOR 404 + 401.
  Sem LibreOffice → entrega `.docx` (degradação graciosa). `_converter_pdf` ganhou `outdir`
  (default `CONTRATOS_DIR` — contrato inalterado).

### Defers (não bloqueiam; do review final)
- Genericizar o corpo do 500 da rota (`str(e)` pode ecoar caminho interno — padrão do codebase).
- Remover o `import mod_proposta as _mprop` redundante na rota.
- Conferência visual no browser (botão Imprimir, lista de orçamentos, orçamento aprovado, abrir inline).

### Banco de documentos #8 — pendente
A lista "etapa → documento" NÃO foi encontrada (busca em todos os transcripts + docs). Fonte provável:
`1_FLUXO_DE_PROCESSOS.docx` (não está no repo, só com o usuário). Próximo passo do #8: obter essa lista.

## Sessão 38 — Lista de ambientes com valor no contrato (branch `feat/ambientes-valor-contrato`)

Frente desenhada (brainstorm→spec→plano) e implementada por SDD (5 tasks TDD, suíte **385**),
**na branch `feat/ambientes-valor-contrato`** (empilhada sobre a `main`). Spec/plano em
`docs/superpowers/{specs,plans}/2026-07-01-ambientes-valor-contrato*`. **Ainda não mergeada** —
aguarda revisão final de branch + conferência visual do usuário.

- **Capa do contrato** ganha a seção **"4. Ambientes"** (a "Forma de Pagamento" passa a **"5"**),
  uma linha por ambiente do orçamento com o **valor com financiamento** + linha **Total** = `TOTAL_CONTRATO`.
- **Valor por ambiente** = `Val_Cont_Amb = VAVA × (Val_Cont / VAVO)` — rateio do custo financeiro
  proporcional ao VAVA (mesma conta que a tela de negociação já mostra na coluna "Com financiamento",
  `static/index.html:5677`). Reconciliação de centavos no **último** ambiente (Σ = `Val_Cont` ao centavo).
  Função pura `mod_contrato.ambientes_valor_contrato`.
- **`mod_contrato._preencher_ambientes`** monta a tabela em código e a insere **antes** da grade de
  parcelas (via `addprevious`); ambas as colunas justificadas à esquerda; células de valor entram nas
  regiões editáveis do contrato protegido (a linha Total, não).
- **Robustez:** `_preencher_grade` deixou de usar índice fixo (`doc.tables[3]`) e passou a localizar a
  grade **por conteúdo** (`_localizar_tabela`, cabeçalho "forma de pagamento"), imune ao deslocamento.
- **Fiação:** helper `_ambientes_valor_para_contrato` (reusa `_negociacao_breakdown`; mapeia
  `pool_ambiente_id → nome_exibicao`) injeta `_ambientes` no ctx nas **duas** rotas de geração —
  `POST` (criação) e `PATCH` (edição/regeneração). E2E real cobre as duas (guard RED→GREEN da PATCH).

### Escopo / próxima frente
- **Só o contrato** nesta frente. **Recriar o `modelo_proposta.docx`** para espelhar a 1ª página do
  contrato (incluindo esta tabela de ambientes) é a **frente seguinte** (spec própria).

### Notas / follow-ups (não bloqueiam)
- A rota **PATCH** de contrato **não degrada graciosamente** sem LibreOffice (devolve 500, ao contrário
  da POST que entrega o `.docx` com aviso) — **pré-existente**, candidato a follow-up. O `.docx` é
  gerado mesmo assim; o E2E verifica a seção no arquivo (aceita status 200|500).
- Minors (para a revisão final): assertions do E2E checam headers, não valores; `_ambientes_valor_para_contrato`
  usa fallback nome vazio para id sem match (sem log); alinhamento do título "4. Ambientes" não setado explícito.

## Sessão 39 — Contrato em HTML/Markdown → PDF (WeasyPrint); aposenta o Word (branch `feat/contrato-html-pdf`)

Reescrita do gerador de contrato: sai o template `.docx` + LibreOffice, entra **HTML (capa) +
Markdown (cláusulas) → PDF via WeasyPrint**. Motivação: a numeração automática de listas do Word era
frágil (números/alinhamento quebravam de forma imprevisível). Spec/plano em
`docs/superpowers/{specs,plans}/2026-07-02-contrato-html-pdf*`. Executado por SDD (12 tasks TDD),
**na branch `feat/contrato-html-pdf`** (empilhada sobre a `main`). Suíte **376 passed / 0 failed**.

- **Motor** (`mod_contrato.py`): `gerar_pdf_contrato(id, ctx)` monta a **capa em HTML**
  (`_html_capa` — linhas dinâmicas de ambientes/parcelas), converte `contrato.md`→HTML
  (`_html_corpo`), embrulha no shell, substitui `[MARCADORES]` (`_substituir_marcadores_html`) e
  renderiza com **WeasyPrint**. Assets versionados em `contrato_template/`
  (`contrato.md`, `contrato.css`, `contrato.html`, `logo_dalmobile.png`).
- **Cláusulas — números literais (Opção A):** o `contrato.md` tem os números como texto
  (`1.1.`, `a)`); o CSS cuida do recuo por nível + *hanging*. Decisão-chave: **exatidão jurídica >
  numeração automática**. O `_html_corpo` processa **linha a linha** (Markdown só inline) para NÃO
  acionar a lista ordenada do Markdown (`1.` viraria `<ol><li>` com número dobrado).
- **Migração do texto:** `scripts/extrair_clausulas_docx.py` — como a numeração do `.docx` é
  automática (não está em `p.text`), a fonte é o **export em TXT do LibreOffice** (achata a numeração
  em texto literal). Limpeza de tabs, quebras de linha soltas, alínea `d)`, campos de preenchimento
  do 2.3.4.1. **Revisão jurídica final do `contrato.md` recomendada** (pendência: 3.6 ausente na origem,
  mantida).
- **Capa:** cabeçalho corrido (logo Dalmóbile + subtítulo da rede + número/data à direita), linha do
  consultor, seções 1–5 (ambientes 2/linha + traços; grade de parcelas só com linhas usadas). Quebra
  de página → cláusulas na página seguinte; rodapé "Página X de Y".
- **Corte limpo:** removidos do CONTRATO o caminho `.docx` (`preencher_contrato`, `_preencher_*`,
  `_set_cell_text`, `_localizar_tabela`, `_proteger_editaveis`, `_MODELO`), a rota `/contrato/editar`
  e o botão no frontend. **Assinatura inalterada** (hash em DB). Os helpers docx/LibreOffice
  (`_substituir_marcadores`, `_subst_paragrafo`, `_converter_pdf`, `LibreOfficeIndisponivel`) **ficam**
  — `mod_proposta.py` (Proposta, ainda docx) os usa.
- **Deps:** `weasyprint` + `markdown` (apt no servidor; pip no dev). LibreOffice permanece **só para a
  proposta**.

### Escopo / próxima frente
- **Só o contrato.** Migrar a **proposta** (`modelo_proposta.docx`) para o mesmo motor é a frente
  seguinte (reaproveita `_html_capa`/CSS). `contrato_editar.py` ficou órfão (candidato a limpeza).
- **Pendências:** fonte de config do `[REDE_IDENTIFICADOR]` (hoje fallback = cidade da loja);
  revisão jurídica final do `contrato.md`.

## Sessão 40 — Merge do contrato HTML/PDF na `main` + refinamentos de formatação (2026-07-02)

Fecha a frente da Sessão 39: a branch `feat/contrato-html-pdf` foi **mergeada na `main`** (fast-forward).
O merge estava bloqueado por um *lock* do Word sobre `modelo_contrato_mapeado.docx` (git não conseguia
escrever o arquivo); com o Word fechado, foi limpo. Suíte na `main` mergeada: **379 passed / 0 failed**.
Branch `feat/contrato-html-pdf` **removida** após o merge.

**Refinamentos de capa/corpo após o usuário revisar o PDF real** (commit `6b1085f` —
`contrato.md` + `contrato.css` + `mod_contrato.py`):
- **Preâmbulo** num único parágrafo justificado (não mais fragmentado em ~4 quebras).
- **Assinaturas:** rótulo com o nome ao lado (`Contratada:`/`Contratante:`/`Testemunha 1:`/`2:`);
  espaço entre a linha de assinatura e o nome; espaço antes da data (`.data-fecho`) e antes do
  fecho "E assim, por estarem…" (`.fecho`).
- **Cláusulas em recuo de BLOCO** por nível (`text-indent: 0` + `padding-left` 0.6/1.2/1.8cm): a 2ª
  linha alinha com a numeração (antes o *hanging* deslocava à direita).
- **Capa:** removida a barra sobrando ao lado do nº de parcelas em "5. Forma de Pagamento"; logo
  recortada (tira faixa branca à esquerda) p/ alinhar "Dalmóbile" com o subtítulo da rede.

**Pendências (mantidas):** fonte de config do `[REDE_IDENTIFICADOR]` (hoje = cidade da loja);
revisão jurídica final do `contrato.md` (cláusula 3.6 ausente na origem, mantida).

## Sessão 41 — Cadastro de parceiro por usuário de loja (branch `fix/parceiro-vinculo-loja-automatico`)

Bug pego em teste de produção: **consultor/gerente não conseguiam cadastrar parceiro**. O form
montava a lista de lojas via `/api/admin/lojas` (restrito a `gerir_lojas`/`editar_dados_loja`), então
usuários de loja recebiam lista vazia e a validação *"Selecione ao menos uma loja"* barrava tudo.

- **Backend** (`main.py`): `_aplicar_abrangencia_parceiro` vincula automaticamente à **loja ATIVA do
  ator** quando `abrangencia='loja'` e nenhuma loja é enviada; `POST /api/parceiros` **sempre** aplica
  abrangência (default `loja`) → parceiro nunca nasce órfão/invisível.
- **`/api/auth/me`** (`auth_routes.py`): passa a informar `rede_id`/`rede_nome` de cada loja, para o
  front decidir se oferece a abrangência de rede.
- **Frontend** (`static/index.html`, `parCarregarOpcoesTenant`): usuário com loja operacional vê o
  vínculo automático à sua loja e a opção **"Toda a rede — <nome>"** apenas se a loja pertence a uma
  rede; admin multi-loja (super_admin/admin_rede) mantém o seletor de lojas/redes.
- **Permissão inalterada:** qualquer usuário logado da loja pode cadastrar parceiro (decisão do
  usuário) — só fica restrito à própria loja/rede.
- **Testes:** `tests/test_parceiro_vinculo_loja.py` (5 E2E com consultor); seed ganhou um `consultor`
  e o `rede_id`. Suíte **384 passed**. Mergeada na `main` (ff, `d9e6f6e`); branch removida.

## Sessão 42 — Lote de ajustes de teste em produção (branch `fix/contrato-ui-ajustes`)

Rodada grande de ajustes durante teste em produção (13 commits, suíte **395 passed**), mergeada na
`main`. Principais:

- **Etapa Contrato (UI):** remove borda verde do badge "para_assinatura", remove o botão grande de PDF
  (mantém o pequeno), botão **Revisar** pede senha gerencial e devolve o contrato à fase de Orçamento
  (reabre etapa 4), "Editar Adendo" → botão "Inserir"; remove o botão "Avançar — Aprovação Financeira".
- **Contrato (conteúdo):** adendo vai ao **final, após as assinaturas, em itálico** (sem página isolada);
  cache-busting no link do PDF.
- **Negociação/parâmetros:** toggle "incluir custos" nasce **true**; com **parceiro**, comissão do
  arquiteto (% do parceiro; senão default da loja) e **fidelidade** entram ativas; endpoints de
  parâmetros herdam os defaults da loja; **valores salvos são respeitados** (semente do parceiro só
  inicial). Fidelidade entra sempre que há parceiro.
- **Ciclo:** eliminadas as etapas **5 (Revisão)** e **6 (Aprovação do orçamento)** — vai de Orçamento (4)
  direto para Contrato (7). Etapa **2 (Criação do Projeto)** ganha o **parceiro (arquiteto)** com
  inserir/alterar/remover, travado só quando **ambas** as partes assinam. Etapa **1 (Cadastro)** segue
  editável após a assinatura; **fix** do telefone defasado (GET do projeto enriquece o cliente com dados
  vivos).
- **Escopo por projetista:** Consultor vê só os projetos que **criou** (+ legados sem criador); gerente
  de vendas e acima veem todos. Nova coluna `projetos_meta.criado_por_id` (+ migração). Escopo aplicado
  na listagem e na abertura; hardening IDOR dos demais endpoints por-projeto fica como follow-up.
- **Provisões:** "Instalação Local" → **"Insumos Locais"**; **CFO** como 1ª linha; **fix** da Margem de
  Contribuição (era exibida ÷100 no modal); bloco informativo de **custos adicionais** (arq/fidelidade/
  viagem/brinde + total) e **custo financeiro**, sempre visível (já descontados do Val. Líquido, não
  somam no Cust_Var).

Testes novos: `test_parceiro_vinculo_loja`(já), `test_escopo_projetista`, `test_projeto_parceiro`,
mais casos em `test_ciclo`/`test_orcamento_params`/`test_provisoes`. **Pendências:** revisão da opção B
das provisões (custos adicionais editáveis recalculando margem) se o usuário quiser; IDOR completo do
escopo por projetista.

## Sessão 43 — Padronização da tela de Negociação + fix desconto por ambiente (main)

Rodada de UI da negociação (5 commits direto na `main`, após o merge da Sessão 42) + 1 correção.
Frontend-only (`static/index.html`), verificação manual. Spec:
`docs/superpowers/specs/negociacao/2026-07-03-negociacao-ui-uniforme-design.md`.

- **Faixa superior:** Valor Bruto → Desconto → Valor à Vista → **Valor Total do Contrato** (célula
  nova à direita; nas modalidades com financiamento = total parcelado; no À Vista = Valor à Vista).
- **Formulário uniforme (uma linha):** Data do Contrato, Entrada, Data da Entrada + campo específico
  (Aymoré: Carência; Cartão: Bandeira; Total Flex: Prazo; Venda Programada: só os 3). Campos
  calculados/informativos ocultos (1ª parcela, prazo limite).
- **Faixa central** (Contrato a Vista/Parcelado) e **cards de resumo** (`cards-3x2`: Loja Recebe,
  Cliente Paga, Valor/Parcela, Custo Financeiro, Taxa de Retenção, Liquidação…) **removidos de todas
  as modalidades** (ids preservados ocultos; avisos de prazo VP/TF permanecem).
- **Provisão de Impostos:** linha fina uniforme com **cadeado liberável por senha** (mecanismo
  `_renderImpostosLock` intacto; mesmos ids `{p}-r-base-trib`/`-r-impostos`).
- **Fix — desconto por ambiente acima do limite:** revertia o campo mas mantinha o desconto aplicado
  (o motor computava antes da checagem de limite e não re-rodava). Agora re-roda `negPreview()` e
  re-persiste após reverter.
- **"Valor Total do Contrato" editável (cálculo reverso — contraproposta do cliente):** digitar o valor
  de contrato calcula o desconto global e aplica. O campo é o **valor de contrato** (com custo
  financeiro): `financiado = max(0, valor − entrada)`; `valorAvista = entrada + financiado × (1 −
  taxaRet)`; `discPct = (1 − valorAvista/bruto) × 100`. Retenção e entrada capturadas por modalidade
  (globais `_negTaxaRetencaoPct`/`_negEntradaValor`; VP/TF/À-Vista sem retenção; entrada é à vista, sem
  custo financeiro). Bruto robusto via `negValorBrutoAtual` (motor/EP07). Acima do limite do perfil,
  popup "Desconto excede o limite do perfil de usuário, deseja realizar autorização gerencial?" → modal
  gerencial. **Causa raiz do 1º bug:** `_negBaseValues` nunca é populado. Trecho feito com apoio do
  **Fable 5**. Spec (seção 6) atualizado.

## Sessão 44 — Manutenção de ambiente + política do MCP `orizon` (main)

Sessão de infraestrutura/processo (sem mudança de código de app; suíte segue **395 passed**).

- **Renomeação do diretório pai** `E:/2026/estudo_de_ia → E:/2026/desenvolvimento` (feita pelo usuário).
  O repo já vinha renomeado `Omie_V3 → Orizon Manager` (commit `c8eb350`, sessão anterior).
- **`.mcp.json`:** corrigidos os dois mounts do container efêmero do MCP para
  `E:/2026/desenvolvimento/mcp-orizon` e `.../orizon-manager`; arquivo adicionado ao git (`c014884`,
  já pushado). Verificado que **nenhum código Python** tinha o path antigo hardcoded (só entradas
  obsoletas de allowlist em `.claude/`, que são ruído ignorado). MCP reconectado via `/mcp` e validado
  com `cobertura` + `ingerir` (`fonte:"all"` → 893 nós de código, 31 requisitos, 60 banco, 42 decisões).
- **[DECIDIDO] Papel do MCP vs DEV_LOG:** o grafo Neo4j (`../mcp-orizon`) é **camada de consulta**
  estrutural (cobertura, impacto, rastreabilidade), **derivada do código e local (fora do git)** →
  fica obsoleta sem re-ingestão. **Não substitui** o DEV_LOG (fonte narrativa versionada) nem o **git**
  (único controle de versão). Ritual de fechar frente ganhou o passo de **re-ingestão** após o push.
  Codificado em `CLAUDE.md` (passo 6 + seção "MCP `orizon`") e `DEV_RULES.md` (checklist + seção
  dedicada).
- **Push da `main`:** funciona nesta máquina (Git Credential Manager do usuário) — feito nesta sessão.
  A antiga seção "🔼 PENDÊNCIA: PUSH" (que assumia ambiente sem credenciais) foi **removida**.
- **Repositório GitHub renomeado** `omie_v3 → orizon-manager` (via API `PATCH /repos`, HTTP 200, com a
  credencial do GCM) e **remote local atualizado** (`git remote set-url origin
  https://github.com/mbnunes1972/orizon-manager.git`); `fetch` validado, `main` sincronizada com
  `origin` (0 à frente). GitHub redireciona o nome antigo por um tempo, então nada quebra.
- **Deploy completo no VPS de produção (167.88.33.121) — feito e validado.** O servidor estava em
  código de 24/06 (commit `895e5f6`, sessão ~31), diretório `/root/omie_v3`, banco `omie.db`, remote
  antigo. Executado o runbook de migração+deploy via SSH (chave ed25519 instalada nesta sessão →
  login sem senha): **backup** do banco (`orizon.db.bak-...`), parada do app, rename `omie_v3 →
  orizon-manager` e `omie.db → orizon.db` (dados preservados: 11 usuários/2 clientes/3 projetos/6
  orçamentos/1 loja), `git reset --hard origin/main` até `ca05a61`, **weasyprint instalado via apt
  (61.1)**, restart no screen `orizon-manager` com `ORIZON_HOST=0.0.0.0`. **Auto-migração** de schema
  rodou limpa na subida (`usuario_lojas_backfill_2026`). Validado: porta 8765 em `0.0.0.0`, `/login`
  **HTTP 200** externo. **[CONTEXTO] Ajuste no runbook:** o screen de produção chamava-se `omie` (não
  `omie_v3`) e o env var antigo era `OMIE_HOST` — o runbook do `DEV_RULES.md` assume nomes que já não
  batiam; hoje está tudo padronizado (`orizon-manager`/`ORIZON_HOST`).
- **[PENDENTE-BAIXA] weasyprint 61.1 no VPS vs 69 no dev local:** conferir um contrato PDF real gerado
  em produção (possíveis diferenças de CSS entre versões). App não depende dela para subir (import lazy).
- **[PENDENTE-BAIXA/segurança] `authorized_keys` do root no VPS** tem chaves de terceiros
  (`igorferreiradaniel99@hotmail.com`, `idaniel@Mac.bbrouter`) + uma linha corrompida da 1ª tentativa de
  instalação — revisar/limpar quem tem acesso root ao servidor.

## Sessão 45 — Subfases do Projeto Executivo (etapa 11) — branch `feat/pe-subfases`

Frente desenhada via brainstorming (spec `docs/superpowers/specs/ciclo/2026-07-04-projeto-executivo-subfases-design.md`)
e implementada por **subagentes** (plano `docs/superpowers/plans/2026-07-04-projeto-executivo-subfases.md`),
task a task com review de spec + qualidade. **Ainda em branch — não mergeada na `main`.**

- **[ESTADO]** Subfases 11a/11b/11c/11e enriquecidas: upload de documentos **append-only** (nunca
  sobrescreve → registro evolutivo), botões de transição nomeados ("Encaminhar para PE", "Projeto
  Alinhado", "Concluído", "Concluir Projeto Executivo"), e **revisão** (11b/11c) com **reabertura em
  cascata** + relatório complementar obrigatório. Concluir 11e conclui a etapa-mãe 11. Medição (etapa
  10) permanece **inviolável** (o PE só lê/linka).
- **[DECIDIDO] Dados (abordagem B):** 2 tabelas novas `ciclo_documentos` + `ciclo_revisoes` (chaveadas
  por projeto+etapa_codigo); status/datas continuam no `CicloEtapa`. Arquivos em
  `PROJETOS/<nome>/ciclo/<etapa>/<uuid>_...`. Documentos append-only; commit-antes-do-disco (padrão EP-07).
- **[DECIDIDO] Capabilities (`perfis.py`):** `executar_pe` (Projetista Executivo, Conferente, Gerente
  Vendas, Gerente Adm/Fin, Diretor) e `revisar_pe` (Gerente Vendas, Adm/Fin, Diretor). A revisão exige
  capability própria porque o `autorizar` do "reabrir em cascata" existente exclui o Adm/Financeiro.
- **[CONTEXTO] Endpoints (`main.py`):** `POST …/ciclo/<codigo>/documento` (multipart), `…/concluir`
  (JSON), `…/revisao` (multipart, cascata); `GET …/ciclo/pe` e `GET …/ciclo/documento/<id>` (download
  via `storage_ler_binario`). Frontend em `static/index.html` (painéis por subfase, progresso N/4,
  handlers com `pedirCredenciaisGerente`). Correção lateral: `esc()` passou a escapar aspas (XSS de
  atributo) — endurece usos pré-existentes.
- **[ESTADO] Testes:** lógica pura em `tests/test_ciclo.py`; e2e HTTP em `tests/test_ciclo_pe_e2e.py`
  (upload append-only, guardas de conclusão, 11e conclui 11, revisão reabre em cascata, permissões,
  download, medição intocada). Suíte **~412 passed** (1 falha pré-existente do weasyprint no local).
- **[PENDENTE]** Verificação **manual no navegador** do frontend (Tasks 8/9 não têm teste JS): botões
  por perfil, upload/conclusão/revisão, indicador de progresso. Merge na `main` + push + re-ingestão
  do grafo após a conferência.

## Sessão 46 — Etapas operacionais 12/13/14 (Implantação · Produção · Entrega) — branch `feat/etapas-operacionais`

Frente desenhada via brainstorming (spec `docs/superpowers/specs/ciclo/2026-07-05-etapas-operacionais-implantacao-producao-entrega-design.md`)
e implementada por **subagentes** (plano `docs/superpowers/plans/2026-07-05-etapas-operacionais-implantacao-producao-entrega.md`),
task a task com review de spec + qualidade. **Mergeada na `main`** (fast-forward de 9 commits) após
verificação manual no navegador ("Funcionou"); branch `feat/etapas-operacionais` **deletada**; push +
re-ingestão do grafo (código 945 nós) feitos.

- **[ESTADO]** Etapas principais **12/13/14** ganharam painéis dedicados (deixam o card genérico):
  - **12 Implantação do pedido:** upload **append-only** de XMLs ("Carregar Pedidos") + "Encaminhar
    Pedidos à Fábrica" (fecha; exige ≥1 XML). Integração real com a fábrica = **futuro** (o botão só
    fecha por ora).
  - **13 Produção:** "Inserir/Salvar Números dos Pedidos" (lista, texto — os números **vêm da
    fábrica** como resultado da implantação) + "Produção Concluída" (fecha; exige números).
  - **14 Entrega no depósito:** "Salvar Relatório de Entrega" (texto livre de **faltas e avarias**) +
    "Concluir Relatório de Entrega" (fecha; exige relatório não-vazio). Removido o `toggleavel` da 14.
- **[DECIDIDO] Arquitetura C:** **sem tabela nova, sem capability nova, PE intocado.** XMLs reusam
  `CicloDocumento` (tipo `implantacao_pedido_xml`); números/relatório em `CicloEtapa.observacoes` das
  etapas 13/14. Conclusão e salvar-texto reusam o `PATCH /ciclo/<codigo>` existente. **Cycle-gated**
  (qualquer usuário que já pode avançar o ciclo — ao contrário do PE, que exige `executar_pe`).
- **[CONTEXTO] Endpoints (`main.py`):** `POST/GET …/ciclo/<codigo>/pedido-xml` (upload/listagem da 12,
  append-only, cycle-gated) + **guarda operacional** no `PATCH /ciclo` (`mod_ciclo.guarda_conclusao_operacional`)
  que barra a conclusão de 12/13/14 sem XML/números/relatório. Guarda pura em `mod_ciclo`
  (`ETAPAS_OPERACIONAIS`, `tipo_doc_operacional`, `guarda_conclusao_operacional` — falha explícita em
  `exige` desconhecido). Frontend: `_renderCardImplantacao/Producao/Entrega` + handlers com `_patchEtapa`
  DRY; `esc()` em todo conteúdo dinâmico.
- **[ESTADO] Testes:** lógica pura em `tests/test_ciclo.py`; e2e HTTP em `tests/test_ciclo_operacional_e2e.py`
  (upload append-only/listagem, guardas de conclusão de 12/13/14, gating sequencial preservado,
  cycle-gated com consultor, PE intocado). Suíte **431 passed**. Reviews de spec+qualidade por
  subagente em cada task (fixes aplicados: footgun do `exige`, DRY do `encaminhar`, upload não falseia
  sucesso).
- **[PENDENTE]** Verificação **manual no navegador** (Task 4 sem teste JS; `node` indisponível no
  ambiente): botões/gating por etapa, upload/download de XML, salvar/concluir números e relatório,
  reabrir (gerente). Depois: merge na `main` + push + re-ingestão do grafo.

## Sessão 47 — Integração NF-e (Fábrica→Loja): guinada Omie→Focus NFe + Fases 1-2 (branch `feat/nfe`)

**Guinada de arquitetura:** o motor fiscal deixou de ser o **Omie** e passou a ser a **Focus NFe** (API
REST direta, Plano Solo). Decisão-chave descoberta na doc: **a Focus NÃO calcula imposto** — nós
fornecemos CST/CSOSN/CFOP/alíquotas por item. O que o Omie fazia sozinho vira nosso (Fase 3). O
parser/precificação (Fase 1) é engine-agnostic e não muda. Roadmap em 5 fases + cross-cutting
(Rede→Loja→config fiscal, perfil de emissão, NFS-e adiada). Specs/planos em `docs/superpowers/`.

- **[ESTADO] Fase 1 (parser+precificação):** só **spec** (`mod_nfe.py` a implementar). Evidência: 5 NF-es
  reais da fábrica em `E:/2026/desenvolvimento/nfe-dalmobile` (**fora do git**; 149 linhas→95 distintos,
  `cProd=BASE[ID]`, consolida duplicados, IPI 100%, `infAdProd` "COR L A" **não-confiável**). Fixtures
  serão anonimizados. **Fábrica é CRT3-com-IPI; a LOJA emissora é Simples** (CSOSN).
- **[IMPLEMENTADO] Fase 2 (contrato + transporte), suíte 457:** `emissor_fiscal.py` (ABC `EmissorFiscal`
  + DTOs `ResultadoEmissao`/`StatusNota` + normalizador `resultado_de_focus`), `focus_config.py`
  (`base_url_de` homolog/prod + loader `focus_config.json` gitignored), `focus_client.py` (`FocusClient`:
  `enviar_nfe` POST `/v2/nfe?ref`, `consultar_nfe` GET, `cancelar_nfe` DELETE com justificativa 15-255,
  `baixar`, `aguardar_processamento` polling determinístico; retry/backoff 5xx/429/conexão espelhando
  `omie_post`; `FocusError`; tolera corpo JSON não-dict). Testes com `requests`/`time.sleep` mockados —
  **zero rede**. Endpoints/auth (Basic token, senha vazia) confirmados na doc da Focus. Concreto
  `EmissorFocusNfe` + payload/impostos = **Fase 3**.
- **[IMPLEMENTADO] Fase 1 (`mod_nfe.py`, branch `feat/nfe-fase1`):** parser+precificação puros —
  `parse_nfe` (namespace-aware; localiza `infNFe` sob `nfeProc` ou `NFe` puro; vIPI ausente→0; dest
  CNPJ/CPF), `split_cprod` (padrão/sob-medida), `parse_infadprod` (tolerante, dims só se 2 últimos tokens
  inteiros), `consolidar` (soma duplicados por cProd completo), `precificar` (custo=(vProd+vIPI)/qCom,
  markup %), `preview` (pipeline+totais) e **CLI de eyeball** (`python3 mod_nfe.py <xml> [markup]`).
  Testes (`tests/test_nfe.py`) com **fixtures anonimizados**. CLI conferido nos XMLs reais (NFe-170942 →
  linhas=21 distintos=12). **[Atenção Fase 3]** `custo_total`/`venda_total` somam valores unitários **já
  arredondados** → pode divergir do total fiscal por centavos (reconciliar se comparar com a NF-e).
- **[PENDENTE]** (1) **Token da Focus** (contratação em andamento) → smoke de transporte em homologação:
  `FocusClient(token, base_url_de("homologacao")).consultar_nfe("ref-inexistente")` deve dar `FocusError`
  **404** (não 401). (2) **Perfil fiscal Simples do CNPJ 19.152.134/0001-56** (contador:
  CST/CSOSN/CFOP/alíquotas) — insumo central da **Fase 3**; lucro real/presumido depois. (3) **Fase 3**
  (mapa fiscal loja→payload + `EmissorFocusNfe`) e depois Fases 4-5.
- **[IMPLEMENTADO] Painel de Configuração Fiscal · Sub-frente I (backend), branch `feat/perfil-fiscal`,
  suíte 493:** reformulação da "Fase 3" — antes do mapa fiscal, um **`PerfilFiscal` por CNPJ/loja** que
  alimenta o mapa com dado real (ou placeholder). Entregue: `fiscal_cripto.py` (**Fernet isolado**, chave
  fora do banco via `ORIZON_FISCAL_KEY`→keyfile gitignored, `cryptography` já instalada), `mod_fiscal.py`
  (`perfil_padrao_teste`/`validar_config`/`pode_ativar_producao`/`focus_client_para_loja`), modelo
  `PerfilFiscal` (tabela 1:1 com Loja, auto-criada), e **endpoints** GET + PUT config/segredos/ambiente
  gated por `editar_dados_loja`+tenancy. **Segurança:** tokens Focus só **cifrados** no banco, **nunca**
  no GET/log; **certificado A1 NÃO fica conosco** (vai pro painel da Focus — guardamos só validade+CNPJ);
  **produção bloqueada com placeholder pendente**. **[DECIDIDO] Perfil-padrão de teste** (Simples, CFOP
  5102/6102, CNAE placeholder, ISS 5%, homologação) desbloqueia o desenvolvimento sem o contador; campos
  de teste marcados em `placeholders`. **[PENDENTE Sub-frente II]** o painel deve também exigir token de
  produção antes de permitir trocar para produção (guarda hoje é só por placeholder).
- **[PENDENTE integração NF-e]** (1) **Token da Focus** → smoke em homologação. (2) **Valores fiscais reais
  do contador** (CST/CSOSN/CFOP/alíquotas) — entram como **dado** no PerfilFiscal, sem mudar código.
  (3) **Sub-frente II** (painel no frontend) e **Fase 3b** (mapa fiscal + `EmissorFocusNfe`), depois Fases 4-5.
- **[IMPLEMENTADO] Fase 3b (mapa fiscal, branch `feat/nfe-mapa-fiscal`, suíte 507):** `mapa_fiscal.py`
  (`montar_nota` modelos→nota neutra: emitente Loja+perfil, destinatário Cliente PF/PJ, regime→código,
  CST Simples; `montar_payload` nota→payload Focus: CFOP dentro/fora por UF, CSOSN do perfil, ICMS origem
  0, PIS/COFINS 49, `valor_bruto`, `consumidor_final` condicional PJ=0/PF=1) e `emissor_focus.py`
  (`EmissorFocusNfe(EmissorFiscal)` fecha o contrato da Fase 2 com o `FocusClient` injetado; emitir/
  consultar/cancelar → `resultado_de_focus`). **Testes offline** (client fake, sem emissão real).
  **[Fase 4]** PIS/COFINS CST "49" + CSOSN são Simples-only (marcado `# TODO Fase 4`) — ramificar por
  regime com o contador.
- **[IMPLEMENTADO] Painel Fiscal · Sub-frente II (frontend, direto na `main`):** aba **Fiscal** no admin da
  loja (`adminRenderLoja`) consumindo os endpoints da Sub-frente I — 7 seções (identificação, regime, NF-e,
  NFS-e só-dado, certificado ref, credenciais Focus, perfil de emissão), **badges + checkbox de confirmação**
  por campo placeholder, **credenciais Focus write-only** (nunca ecoadas), **troca de ambiente** com confirm
  + dupla guarda (produção exige token de produção + zero placeholder). Espelha o padrão da aba Financeiro.
  Checagem estrutural OK; **backend 507 verde**. **[PENDENTE] verificação manual no navegador** (do usuário).
  **[GAP]** `cert_validade`/`cert_cnpj` read-only (o PUT config da Sub-frente I não os inclui — ajuste
  pequeno depois). *(Usuário autorizou seguir direto sem os gates de review; revisão depois.)*
- **[CONTEXTO] Fechamento:** Fases 1, 2, **Painel Fiscal Sub-frentes I e II** e **Fase 3b** todas na `main`
  (pushadas e re-ingeridas). **A retomar:** Fases 4-5 (dependem do token da Focus + valores do contador).

## Sessão 48 — NF-e Fase 5: emissão na etapa 15 (orquestração + painel) — branch `feat/nfe-etapa15`

Última peça de código da integração NF-e. Liga o pipeline (Fases 1-4) à **etapa 15 do ciclo**, por projeto,
com painel dedicado. Subagent-driven (implementer + revisão spec + revisão qualidade por tarefa); spec/plano
em `docs/superpowers/{specs,plans}/2026-07-06-nfe-fase5-etapa15-emissao*`. **Suíte 522→531** (12 e2e novos).

- **Decisões (brainstorming):** a **NF-e da fábrica entra na própria etapa 15** (upload append-only — a etapa
  12 segue sendo os *pedidos enviados à fábrica*); **markup por emissão** (campo no painel, default 30);
  **emissão restrita a `editar_dados_loja`** (≠ etapas 12-14 cycle-gated); **1:1** (uma NF-e da loja por XML
  da fábrica); etapa **conclui automático** em `emitida` ao autorizar.
- **Backend:** coluna `NfeEmissao.fabrica_doc_id` (+ migração idempotente em `_migrar_colunas`); `nfe_emissao.emitir`
  ganhou `fabrica_doc_id=` e **carimba o nome SEFAZ do destinatário em homologação** (centralizado — beneficia
  também o `emitir-teste` da Fase 4). 5 endpoints `/api/projetos/<nome>/ciclo/15/…` (gated `editar_dados_loja`
  + escopo): `nfe-fabrica` (upload), `GET nfe` (estado), `emitir-nfe` (`ref` estável `NFE-<projeto>-<doc_id>`
  → idempotente), `nfe/consultar`, `nfe/cancelar` (**cancelar reverte a etapa 15** para não-conclusiva).
- **Frontend:** painel `_renderCardEmissaoNfe` na etapa 15 (roteado como 12/13/14) — carregar NF-e da fábrica,
  markup por linha, emitir, status/chave, **baixar XML/DANFE**, consultar/cancelar; botões UX-gated por
  `_NFE_NIVEIS_EMITE = {diretor, super_admin, admin_rede}` (casa com `perfis.py`; backend é a trava real).
- **Testes:** `tests/test_nfe_etapa15_e2e.py` (emissor mockado via `monkeypatch` de `nfe_emissao._emissor_para`
  — zero rede): upload+estado, 403/401/404/400 (sem arquivo, outra loja, sem perfil), emitir autoriza+conclui+
  idempotência, homologação carimba nome SEFAZ (test no `test_nfe_emissao.py`), produção **não** carimba,
  rejeitada **não** conclui, consultar/cancelar + reversão da etapa.
- **Pendente:** **smoke real em homologação** (só depois do certificado A1 na Focus, 2026-07-07) e **verificação
  manual do painel** (etapa 15 + Painel Fiscal II). Merge da branch pendente da conferência do usuário.
- **[obs. de review, não bloqueia]** cancelar já reverte a etapa; `markup_pct` inválido → custo (comentado,
  só homologação); justificativa de cancelamento validada 15-255 no painel (backend também).

## Sessão 49 — Fiscal: Plano de Faturamento multi-CNPJ (Emitente 1ª classe) — branch `feat/fiscal-emitente-multicnpj`

Correção **estrutural na base** fiscal: desacopla "quem vende" de "quem emite", antes de Comercial/Estoque
reforçarem a premissa. Motivada por auditoria (a emissão assumia 1 venda = 1 CNPJ = 1 documento, quem vende
emite). Subagent-driven, TDD, suíte **532 → 545**. Spec/plano: `docs/superpowers/{specs,plans}/2026-07-06-fiscal-plano-faturamento-multicnpj*`.

- **`Emitente`** (1ª classe): 1 CNPJ + config fiscal + tokens + **endereço próprio** — absorve `PerfilFiscal`.
  `Loja.emitente_id` / `Rede.emitente_central_id`. Migração idempotente `perfil_fiscal → emitente` (preserva
  o **token do smoke** da INSPIRIUM) — com fix crítico: o **rename de tabela roda ANTES do `create_all`**
  (`_migrar_pre_schema`), senão o upgrade perderia os dados de `nfe_emissao`.
- **`PerfilEmissao`** (owner loja|rede, tipo_doc, emitente) + `mod_fiscal.resolver_emitente` (override loja →
  default rede → self) / `resolver_plano` / `focus_client_para_emitente`.
- **`NfeEmissao → DocumentoFiscal`** (+`tipo_documento`, +`emitente_id` distinto de `loja_id`).
- **Emissão de produto re-plataformada:** `montar_nota(emitente,…)`, `emitir(…, emitente_id)`,
  `consultar`/`cancelar` resolvem por `reg.emitente_id`; endpoints resolvem `resolver_emitente(loja,"produto")`.
  **Contratos de API trocados:** `focus_client_para_loja` → `focus_client_para_emitente`; `_emissor_para(emitente_id)`.
  **Multi-CNPJ provado:** teste emite o produto sob o CNPJ da **central da rede** (≠ loja vendedora).
- **NFS-e** segue slot modelado (`emitir_nfse_servico` NotImplemented — US-32).

> ### ✅ GAP config divergente — FECHADO (US-36, 2026-07-06)
> ~~O Painel Fiscal escrevia `PerfilFiscal` mas a emissão lê `Emitente`.~~ **RESOLVIDO** (branch
> `feat/fiscal-painel-emitente`, suíte 561): o **Painel Fiscal agora opera o `Emitente` da loja**
> (`loja.emitente_id`, cria se faltar) com **endereço + CSOSN contribuinte** editáveis; o modelo
> `PerfilFiscal` + `focus_client_para_loja` foram **removidos** (tabela `perfil_fiscal` mantida como legado).
> Editar o painel volta a afetar a emissão. ~~Falta só a US-37.~~ **✅ US-37 IMPLEMENTADA** (branch
> `feat/fiscal-perfil-emissao-ui`, suíte 578): **painel Fiscal da rede** (Emitente central) + **Perfil de
> Emissão em 2 níveis** (default da rede + override da loja: produto/serviço → self|central, via selects).
> A configuração multi-CNPJ agora é 100% pela tela. Resta a **NFS-e de serviço** (US-38/US-32).

- **Pendente:** merge desta branch; migração do painel de config → Emitente (EP-11); NFS-e (US-32). O smoke
  real (cert A1) pode rodar nesta branch (usa o `Emitente`) ou na `main` atual (usa `PerfilFiscal`) — **decidir
  em qual trilho** antes de rodar (recomendado: mergear esta branch e rodar no trilho novo).

## Sessão 50 — Validação de CPF/CNPJ nos cadastros (rejeita número falso) — branch `feat/validacao-cpf-cnpj`

Nenhum cadastro validava o **dígito verificador** — números falsos (o placeholder `012.021.345-01`, `123.123.123-00`)
entravam e só quebravam na SEFAZ (o smoke da NF-e revelou "CPF inválido"). Agora se **rejeita CPF/CNPJ falso** na
origem, em **todos os cadastros**. Documento **segue opcional** (cliente/parceiro): valida-se **só se informado**;
vazio é OK (obrigatório mesmo só na geração do contrato, já existente). Subagent-driven, TDD, suíte **613 → 624**.
Spec/plano: `docs/superpowers/{specs,plans}/2026-07-06-validacao-cpf-cnpj*`.

- **`validacao_doc.py`** (novo, puro, offline — só DV, não consulta a Receita): `valida_cpf`/`valida_cnpj` (módulo 11,
  rejeita repetidos), `doc_valido` (11→CPF, 14→CNPJ), `erro_doc(valor, rótulo, tipo)` → mensagem se informado e
  inválido, `None` se vazio/válido. Aceita com/sem pontuação.
- **Backend autoritativo (400):** validação antes de persistir em **Cliente** (`cpf`/`cnpj`), **Parceiro** (`cpf_cnpj`,
  auto por tamanho), **Usuário** (`cpf`), **Rede** (`cnpj`), **Loja** (`cnpj`) — nos create **e** edit (no edit, só se
  o campo veio no payload). Unicidade de CPF do cliente preservada (roda depois da validação).
- **Frontend inline (UX) no modal de cliente:** `_docValidoCPF`/`_docValidoCNPJ` (espelham o util); aviso `cli-aviso-cnpj`
  (novo) + `cli-aviso-cpf` (agora também DV, antes só duplicata); `cliFormatarCNPJ` (máscara); `cliSalvar` **bloqueia**
  doc falso antes de enviar. Demais cadastros mostram o erro do backend.
- **Não retroativo:** placeholders já gravados só somem via edição. Testes existentes que criavam cadastro via endpoint
  com CPF placeholder inválido foram trocados por **docs válidos** preservando a intenção (ex.: teste de colisão de CPF
  ainda testa 409, agora com CPF válido). CPFs de teste válidos: `111.444.777-35`, `390.533.447-05`; CNPJ `11.222.333/0001-81`.
- **Pendente:** merge desta branch na `main` + re-ingerir MCP.

## ⏸️ ESTADO ATUAL (2026-07-31) — retomar aqui

> **✅ FRENTE ORIZON CHAT (orientação `.claude/orientacao-orizon-chat-v2.md`) FECHADA na `main`
> local (2026-07-31)** — ver **Sessão 130**. Cinco commits: specs (`47444f9`), thread full-page +
> eliminação do modal legado (`2b3a41c`), fila de triagem persistente (`7f2d8ed`), eventos do
> ciclo na timeline (`ae03a28`), pacote `chat/` com portas + ratchet (`0c86f9b`) + este docs.
> Suíte completa **1632 verde** (era 1613). **Vera: APTA para promover à VPS** (zero bloqueante;
> relatório na Sessão 130). **Sessão 131**: revisão de UX da F7/Chat Interno aplicada por
> feedback do usuário — abas Pessoais·Grupos·Arquivadas nos dois canais, Pendentes como
> filtro, arquivamento real, 7 segmentos no seletor, Mural na barra de ações.
> **Grafo MCP re-ingerido (2026-08-01, pós-fichário + fix do auto-save)** — fonte `all`:
> código 3313 nodes/3013 edges, banco 210/140, requisitos 31, domínio 19, decisões 17.
>
> **🚀 DEPLOY A+B EXECUTADO (2026-07-31, tag `v2026.07.31b-homolog` = `0d41e81`, a pedido do
> usuário):** VPS A (`orizon-a` :8765, main) e VPS B (`orizon-b` :8766, tag) atualizadas via
> `deploy_ab.sh` — ambas 302; migrações novas verificadas no Postgres da B (`triagem_entradas` ✓,
> `conversas.segmento` ✓, `segmento_config.responsavel_funcionario_id` ✓,
> `conversa_mensagens.evento` ✓); as 4 envs `ORIZON_WA_*` carregadas no processo da B (transporte
> Meta CONECTADO); webhook `https://homolog.orizonone.com.br/webhooks/whatsapp` vivo (403 p/
> token errado; site 302); **número conectado (12) 99602-1234** gravado nas bases A, B e local
> (loja INSPIRIUM). **Plano de Testes COMPLEMENTAR** criado:
> `plano_de_testes/Plano_de_Testes_Complementar_Orizon_Chat.xlsx` — 43 cenários em 5 jornadas
> (Atendimentos · Chat Interno · Triagem e Contatos · Config do Chat · Meta Externo E2E
> MET-001..008 com WhatsApp real na B); fora do git como os demais planos.
>
> **🚀 DEPLOY A+B (2026-08-02, tag `v2026.08.02-homolog` = `a5353b6`):** VPS A (main) e VPS B
> (tag) atualizadas via `deploy_ab.sh` — ambas 302; B com as 4 envs Meta no processo, webhook
> vivo (403 p/ token errado), homolog.orizonone.com.br 302 e número (12) 99602-1234 mantidos.
> Leva à homolog: fichário fases 1+2, fix do auto-save 403, aba Todas, segmentos gerenciáveis.
>
> **Sessão 141 (Agenda Fatia 2):** a Agenda ganhou TELA — nav "Agenda" + visão Calendário
> (grade do mês, badges por Setor, Σ de entregas no dia, drill-down inline) sobre o novo
> `GET /api/agenda` + `mod_agenda.py` (marcos por Setor; entrega 16 por fase). Subfases do
> PE ganham data prevista default (frações da janela da 11). Suíte 1686 verde. Próxima:
> Fatia 3 (cargas + Semana/Mês).
>
> **Sessão 140 (Agenda Fatia 1):** `parcela_projeto.val_liq_congelado` — Val_Liq congelado
> por fase nos 5 caminhos (desmembrar, sucessivo, reter, liberar em ondas, confirmar) com
> Σ == Val_Liq exata; helper `_liquidos_contrato_por_ambiente`; backfill idempotente no
> start; GET /parcelas expõe. Suíte 1677 verde. Próxima: Fatia 2 (marcos + Calendário).
>
> **Sessão 139 (Agenda Fatia 0):** `mod_calendario.py` (dias úteis genérico, 12 testes) +
> seção `agenda` na config da loja + aba Config → Agenda. **Rev do usuário (mesmo dia):**
> `teto_dias_montagem` REMOVIDO (a janela de trabalho vem do CRONOGRAMA de entrega, que já
> prevê cada etapa — a produtividade só converte necessidade diária em recurso);
> `produtividade_pe_rs_dia` NOVA (PE análogo à montagem, R$20k/dia default); painel separado
> por títulos Projeto Executivo · Montagem · Calendário útil. Spec §5/§6/§8 revisados
> (PE também com carga distribuída). Suíte 1672 verde. Próxima: Fatia 1 (`val_liq_congelado`).
>
> **Sessão 138 (design, sem código):** AGENDA DA LOJA — decisões fechadas em debate (Setor,
> Calendário/Semana/Mês, Capacidade; unidade Val_Liq c/ novo congelado
> `val_liq_congelado`; `mod_calendario` de dias úteis; acesso via visao_do_papel). Spec:
> `docs/superpowers/specs/agenda/2026-08-03-...-design.md`; plano em 5 fatias no
> `plans/agenda/`. Próximo passo: Fatia 0 (calendário útil + config). Parecer VAVO×Val_Liq
> nas provisões: convenção documentada (NOMENCLATURA §3b) — migração é frente própria c/
> contador.
>
> **Sessão 137:** retenção por obra RECORRENTE — acionável nas etapas 9/10/11/17, várias
> vezes, com registro histórico (quando, etapa do ciclo, ambientes, motivo, PREVISÃO DE
> LIBERAÇÃO) em `retencao_obra`; modal revisado (nova retenção direta + histórico); split de
> fase preservando congelados; desmembramento pede previsão de liberação + nova previsão de
> entrega por fase (`parcela_projeto.liberacao_prevista/entrega_prevista`). Suíte 1660 verde.
>
> **Sessão 136:** faixa de entrega no fichário (etapas 9→16: "Previsão de entrega" →
> "Entregue em", global ou por fase, ambientes inline SEM modal — padrão de tela decidido
> pelo usuário) via GET /entrega-resumo; desmembramento SUCESSIVO de fases
> (POST /parcelas/<id>/desmembrar + mod_parcelas.desmembrar_fase, congelados da mãe
> preservados, bloqueia liquidada/em expedição). Suíte 1656 verde (+11).
>
> **Sessão 135:** registro do contrato fecha ao centavo — linha "Itens de ordem geral"
> (custo especial fora dos ambientes; era a diferença de R$ 548,29 no Norberto), rodapé
> "Total" nas DUAS colunas (à vista = VAVO, financiado = Val_Cont), "Valor à vista" corrigido
> (mostrava Val_Liq da loja!), Projeto+Cliente no cabeçalho; cartão/aymoré: última parcela
> absorve o resíduo do arredondamento (entrada + Σ parcelas = total_cliente exato).
> OBS: 4 falhas PRÉ-EXISTENTES em test_chat_wa/test_comunicacao (falham na árvore limpa).
>
> **Sessão 134:** pós-assinatura os parâmetros da negociação saem da SIDEBAR e ficam
> registrados (read-only) na aba Contrato: desconto, pagamento, parcelamento, entrada e
> ambientes fechados com valores — dados congelados do orçamento contratado.
>
> **Sessão 133 (fichário fase 2):** AF auditada (3 camadas, front espelha o gate); Briefing e
> Provisões DIRETO na tela das etapas 3/8/11d; desmembramento em fases disponível desde a
> Solicitação de Medição (9 e 10; backend já permitia pós-contrato).
>
> **Sessão 132 (branch feat/ciclo-fichario → main):** Ciclo interno redesenhado em FICHÁRIO
> (lombada + tela cheia; 3 tokens semânticos por estado; Vera APTA). Ver a sessão p/ os 2
> fluxos de verificação manual pendentes e o 403 pré-existente do auto-save de pagamento.
>
> **Pendentes:** (a) executar o plano complementar (em especial MET-001..008 na B); VPS B →
> produção segue gated por OK do usuário. (b) **F3/F4/F6** do plano 2026-07-28 seguem pendentes
> (envio por template — inclusive o ramo fora-da-janela do encaminhamento de documento —,
> reengajamento RF-17, fluxo da triagem automática RF-08/09; o campo `segmento_sugerido` da fila
> já espera a F6). (c) Shims `mod_chat.py`/`mod_chat_externo.py` na raiz: remoção é churn
> mecânico de ~15 imports em `main.py` + testes; o ratchet `test_chat_pacote_nao_importa_host`
> já protege a direção. (d) `datetime.utcnow()` deprecado (achado 🟡 da Vera): a modernização
> tem de ser VARREDURA ÚNICA do codebase — trocar pontualmente para `now(UTC)` mistura datetime
> aware com o schema naive e QUEBRA comparações; não corrigir aos poucos. (e) `.gitignore`
> `COMUNICACAO/` sem âncora engole `docs/superpowers/specs/comunicacao/` (a spec
> 2026-07-28-orizon-chat-revisao-design.md está FORA do git) — decidir trocar para
> `/COMUNICACAO/`; as specs novas foram para `_geral/` por isso.

## ⏸️ ESTADO ATUAL (2026-07-29) — retomar aqui

> **🚀 DEPLOY VPS A (2026-07-29, `90755c2`):** frente **Orizon Chat/Meta (UI-first)** promovida à **VPS A**
> (`167.88.33.121`, `orizon-a` :8765) — ver **Sessão 129**. Entregue e auditado pela Vera: **Números
> Conectados** (RF-01; número por loja + status do transporte Meta como booleanos, secrets só em env var),
> **Consumo/Custos** (§10), **Atendimentos full-page** (F7/RF-12) e **Chat Interno full-page** (sai do modal
> antigo). Correções da Vera aplicadas (janela por conversa; janela não infla pela resposta do funcionário
> via ponte; template padrão só ativo). Suíte **1613 verde**; **MCP reingerido** (fonte `all`: código
> 3224/2935, banco 207/138, requisitos 31, domínio 19, decisões 17). **VPS B intocada** na `Pre_Teste`
> (`9e13753`, :8766). **VPS B → produção pendentes de OK do usuário.**
>
> **Pendentes da frente (backend, p/ a Vera/TDD):** F3 (envio por template + janela na composição — usar a
> `janela_da_conversa` já corrigida), F4 (reengajamento RF-17 + trigger cron/systemd-timer), F6 (fluxo de
> roteamento RF-08/09 + SAC via `responsavel_sac`). **Backburner:** perf de `_atendimento_meta`; aba
> "Outros"/"Arquivados" e semântica plena de triagem/atribuição do RF-12 (exigem "dono do atendimento" e
> inbox loja-wide). **Estudo do Hunt** recebido; rodada complementar da Vera aguarda **prints** (sem login).
>
> **Config do Chat completo** (as 5 sub-abas: Segmentos · Triagem · Modelos · Números · Consumo) + os dois
> destinos de **Comunicação** (Atendimentos · Chat Interno) agora full-page no `#page-chat`. Plano fatiado
> com o status por fatia: `docs/superpowers/plans/2026-07-28-orizon-chat-revisao-meta.md`.

## ⏸️ ESTADO ATUAL (2026-07-27) — retomar aqui

> **🚀 DEPLOY VPS A (2026-07-27, atualizado p/ `734ec69`):** `main` promovida à **VPS A**
> (`167.88.33.121`, `orizon-a` :8765) no commit **`734ec69`** — as DUAS frentes fechadas hoje
> (Desmembramento Operacional 1–5 + gate de PE/montagem do Orizon Chat) **+ a correção da auditoria da
> Vera** (gate de montagem/assistência barra ambiente retido). A-only (stop/`git reset --hard
> origin/main`/restart `orizon-a`, **sem `deploy_ab.sh`**). App responde 302; migração verificada no
> Postgres do A (`sinal_retido` ✓, `parcela_ambiente.valor_ambiente` ✓, `ciclo_etapas.responsavel_terceiro_id`
> ✓). **localhost** reiniciado na mesma versão (302, boot limpo). **VPS B intocada** na `Pre_Teste`
> (`9e13753`, `/root/orizon-homolog` :8766, 302). **Grafo MCP reingerido** (fonte `all`: código 3152
> nodes/2864 edges, banco 192/128, requisitos 31, domínio 19, decisões 17). **VPS B → produção seguem
> pendentes de OK do usuário** (disciplina de versionamento).
>
> **Frente CHAT → Central de Comunicação / "Orizon Chat" (omnichannel).** Código na `main` e na VPS A
> (deploy acima); VPS B/produção pendentes.
>
> **🔧 Refino do Orizon Chat no PROJETO (2026-07-27, commit `579f2c1`, LOCAL — ainda não na VPS A):**
> reporte do lojista no Projeto Norberto (logado como Diretor). (a) Renomeado **"Mensageria" →
> "Orizon Chat"** no ambiente do projeto (`modal-conversa-proj`: botão + título + msg de erro).
> (b) **Diretor/Gerente participam por PADRÃO de toda conversa de projeto** —
> `mod_chat.sincronizar_participantes_projeto` passou a unir a **gerência da loja** (capacidade
> `autorizar`/`aprovar_financeiro`) ao conjunto derivado da equipe; a auto-exclusão manual
> (`removido=1`) é respeitada (não readiciona). (c) **Modal de membros virou TABELA** (Membro |
> Função | Origem equipe/gerência/manual + ação): `mod_chat.listar_participantes` agora traz
> `funcao_nome` (Funcionario→Funcao) e a flag `gerencia`; `ccMembrosAbrir(convId)` renderiza a tabela
> e é reusado pela conversa do projeto (novo botão **"Membros"** no modal, via `_convProjId`) além do
> inbox. Testes `test_membership_projeto.py` (+3). Suíte **1584** verde. **Pendência:** o "Diretor não
> conseguiu enviar" NÃO tem trava de participante no backend do texto (`/conversa/mensagens` não
> checa) — causa provável = página em cache (a correção do compositor readonly foi recém-publicada na
> A); **hard-refresh (Ctrl+Shift+R)** deve resolver; investigar com o erro exato se persistir.
>
> **🧩 UNIFICAÇÃO do Orizon Chat (2026-07-28, LOCAL — ainda não na VPS A; commits `0dc3db1`→`908c2b6`
> + F3).** Frente aprovada em plano (fatiada). **F1 (`0dc3db1`):** o chat do projeto deixa de ser um
> modal separado e passa a abrir DENTRO do modal canônico do painel lateral (`#modal-central-com`) como
> conversa `tipo=projeto`; thread project-aware (mensagens/envio nos endpoints do projeto, anexo nativo);
> **Transferência+Bloqueador portados** para `#cc-transf` (só projeto); canal automático (sai o seletor
> externo); "Direct"→"Individual"; gerir membros vale p/ **grupo** (não só projeto); `#modal-conversa-proj`
> aposentado. **Nova conversa (`d7dde36`):** Individual = seletor de usuários; Grupo = NAVEGA grupos/
> projetos existentes (filtro por nome) + botão **"Novo Grupo"**; **lembrete de assunto** ("Conversas sem
> assunto. Deseja continuar?"); tirado o "1:1". **Usuário EXTERNO (`6c7e9d2`):** tabela
> `conversa_participantes_externos` (contato WhatsApp/e-mail sem Usuario); `mod_chat.adicionar/remover/
> listar_externo`, `listar_participantes` inclui externos (**destacados**); `criar_grupo(exige_dois)`;
> `mod_chat_externo.espelhar_para_externos` (1 EnvioExterno por externo, **config-gated** → `pendente_config`);
> endpoints (POST /conversas aceita `externos`; participantes `add_externo`/`remove_externo`); front:
> "+ contato externo (WhatsApp)" no seletor e nos Membros (chips `--warn`). **F2 (`908c2b6`):** destinatário
> por mensagem — `ConversaMensagem.destinatario_usuario_id` + seletor "Para: todos|<membro>"; **marcação
> visual** ("→ para <nome>", todos leem). **F3 (a commitar):** caixa **"E-mail (oficializar)"** — encaminha
> a mensagem a TODOS os integrantes pelo e-mail cadastrado (interno+externo), reusa `notificar_gerentes_email`
> (SMTP, **config-gated** → `pendente_config`); `mod_chat.oficializar_por_email`. **GO-LIVE do envio real
> (externo+e-mail)** depende de credenciais Meta/SMTP + templates. Testes: `test_comunicacao.py` (+9 no total
> da frente). **Suíte 1589→ (F3) verde.**
>
> **1) Correções de contexto de loja (commits `d08e6c1`, `abf38f0`, `8771877`).** O painel de
> conversa recusava mensagens por **contexto de loja partido**: o interceptor de `fetch` só
> anexava `X-Loja-Ativa` às rotas `/api/`, então `/projetos/<nome>` e `/orcamentos/...` abriam no
> default do backend enquanto a conversa (`/api/...`) usava `_lojaAtiva`. Correção: header em TODA
> requisição same-origin; **auto-alinhar a loja ativa à loja do projeto** ao abrir/usar a conversa
> (`_alinharLojaAoProjeto`, guarda anti-vazamento — só troca p/ loja acessível); backend expõe
> `loja_id` na lista e no detalhe de projeto. **Fonte:** `lojas_acessiveis_ids` passou a **sempre
> incluir a própria loja do usuário** (master da mãe vinha só com o PDV → loja ativa caía no PDV e
> quebrava tudo).
>
> **2) Bug do compositor travado (commit `dbd53fb`).** Causa real do "não consigo escrever
> mensagem": `aplicarBloqueioNegociacao` (lock de projeto assinado) pegava `input/textarea` dentro
> de `#page-02` — e o modal da conversa estava aninhado lá → `#conv-texto` virava `readOnly` +
> `.neg-locked`. Correção: excluir `#modal-conversa-proj` e `#modal-contatos-conf` do lock.
>
> **3) Spec da Central de Comunicação (commit `b87186a`):**
> `docs/superpowers/specs/_geral/2026-07-27-central-comunicacao-omnichannel-design.md`. Inbox única,
> "interno vs externo" vira transporte (web/WhatsApp/e-mail) da MESMA conversa; público = a loja;
> canal por função (automático); destinatário definido ao abrir a conversa; anexos foto+arquivo;
> ponte WhatsApp do funcionário por presença+espelho/template (regras Meta: janela 24h, sem
> WhatsApp pessoal, identidade por celular cadastrado). Engloba a spec 2026-07-25 do chat do projeto.
>
> **4) Fatia 1 entregue (commit `ba63ad1`, suíte 1520 verde).** `Conversa.tipo`
> (projeto|direct|grupo|publico) + `titulo` + `criado_por_id`; tabela `conversa_participantes`;
> `ConversaMensagem.canal_segmento` (derivado da função). `mod_chat`: `get_or_create_direct`,
> `criar_grupo`, `eh_participante`, `listar_inbox`, `serializar_conversa`,
> `canal_segmento_do_usuario`. Endpoints `/api/comunicacao/{inbox,usuarios,conversas,
> conversas/<id>/mensagens}` (auth por participante, tudo escopado por loja). Frontend: entrada na
> sidebar + modal global top-level (fora do `#page-02`) com inbox/thread/nova mensagem. Testes:
> `tests/test_comunicacao.py` (12). Rename inicial Conversa→Mensageria (`8792d93`).
>
> **5) Fatia 2 entregue (suíte 1527 verde).** Rename UI "Comunicação"→**"Orizon Chat"**. Campo
> **Assunto** por conversa: `Conversa.assunto_tipo` (livre|projeto|custom) + `assunto_id` (FK nova
> tabela `assuntos`) + reuso de `projeto_nome`; seletor com **Conversa Livre + lista de projetos +
> assuntos custom** e botão **"criar assunto"**. Direct virou **canônico por (dupla + assunto)** —
> a mesma dupla tem threads distintas por assunto. `mod_chat`: `criar_assunto`, `listar_assuntos`,
> `normalizar_assunto`, `_assunto_do`, `listar_todas_conversas`. Endpoints
> `/api/comunicacao/{assuntos (GET+POST), admin/conversas}`. **Gerente/Diretor veem TODAS as
> conversas** (capacidade `ver_todas_conversas`, master+gerencial) + **painel de administração**
> (filtro por assunto/participante; leitura de qualquer conversa da loja — oversight, sem postar).
> Frontend: seletor de assunto + criar assunto na "Nova mensagem"; botão "Administração" no header
> (gated) com lista filtrável e thread em modo leitura. Testes: +8 em `test_comunicacao.py` (20 no
> total) + metadado de capacidade. Modal "criar assunto" no design (`promptPopup` temático).
>
> **6) Fatia 3 entregue (suíte 1531 verde).** **Mural público da loja:** `get_or_create_publico`
> (conversa única tipo='publico' por loja, audiência = a loja inteira, sem participantes);
> `pode_acessar_conversa` (público = qualquer usuário da loja; direct/grupo = participante);
> aparece sempre no topo da inbox ("📣 Mural da loja"), todos leem e postam; isolado por loja.
> **Não-lidos:** `marcar_lido` (auto ao abrir a conversa, via `lido_ate_mensagem_id`;
> para público cria a linha de participante só como marcador), `_conta_nao_lidas` (exclui as
> próprias mensagens). `listar_inbox` agora inclui o público e devolve `nao_lidas` por conversa.
> Frontend: badge de não-lidas por item + total na entrada da sidebar (poll ~45s). Testes: +5
> (23 no total).
>
> **7) Fatia 4 entregue (suíte 1534 verde).** O canal público único virou **três**:
> **Mural** (avisos, por loja, todos leem, **só gerência posta** — `pode_escrever_conversa`),
> **Fórum da Loja** (`forum_loja`) e **Fórum Orizon** (`forum_orizon`, **CROSS-LOJA pela rede** —
> primeiro dado cross-loja deliberado, gated por `Conversa.rede_id`). Fóruns = **DEBATES**: cada
> conversa é um tópico com título+assunto; busca por título; decisão do lojista. `mod_chat`:
> `get_or_create_mural`, `criar_debate`, `listar_debates`, `pode_ler_conversa`/
> `pode_escrever_conversa`, `_rede_da_loja`. Endpoints `/api/comunicacao/forum` (GET lista/busca +
> POST cria debate). Migração: `publico`→`forum_loja` "Geral". Frontend: botões Fórum da Loja/Orizon
> (Orizon só se a loja tem rede), lista de debates com busca + "Novo debate" (título+assunto), mural
> em leitura p/ quem não é gerência. Testes: +6 (26 no total).
>
> **8) Fatia 5 entregue (suíte 1538 verde).** **Anexos (foto/arquivo)** nas mensagens: tabela
> `mensagem_anexos` (metadados + caminho); binário no storage `COMUNICACAO/<loja>/` (gitignored).
> `mod_chat`: `criar_anexo`, `anexos_por_mensagem` (lote), `tipo_anexo_por_mime`, `permitir_vazio`
> em `enviar_mensagem` (mensagem só-anexo). Endpoints `POST /conversas/<id>/anexos` (multipart,
> mesmas regras de escrita) e `GET /anexos/<id>` (serve o binário, gated por `pode_ler_conversa`).
> Front: clipe no compositor, chip do arquivo escolhido, imagens inline (thumb→abre) e arquivos
> como link. Teste: `HttpClient.post_multipart` novo; +5 (30 no total).
>
> **9) Fatia 6 entregue — FRENTE COMPLETA (suíte 1545 verde).** Ponte WhatsApp do funcionário
> (número da EMPRESA, regras Meta). `mod_chat_externo`: `registrar_presenca`/`esta_online`
> (heartbeat), `usuario_por_telefone` (celular cadastrado, últimos 8 dígitos), `dentro_da_janela_24h`
> (livre dentro; template fora), `deve_notificar_usuario` (pref `Usuario.notificar_whatsapp`
> sempre|quando_offline|nunca + presença), `notificar_usuario`/`notificar_conversa` (registra
> EnvioExterno `destinatario_tipo='usuario'` — **config-gated: sem credencial Meta nasce
> pendente_config**), `processar_entrada_usuario` (resposta do zap casa o número → posta como o
> usuário na conversa da última notificação). Hooks em POST mensagens/anexos (best-effort, nunca
> quebram o envio); webhook tenta o funcionário antes do fluxo externo; heartbeat no poll de 45s.
> Presença = tabela `usuario_presenca`. Testes: `test_chat_wa.py` (8). **GO-LIVE (fora do código):**
> credenciais Meta (`ORIZON_WA_TOKEN`/`ORIZON_WA_PHONE_ID`) + **templates aprovados** p/ envio fora
> da janela de 24h; UI de preferência por usuário fica como refinamento futuro (default
> quando_offline). Orizon Chat: fatias 1-6 concluídas, tudo local na `main` (A/B/produção pendentes).
>
> **10) Frente "Conversa do Projeto no Orizon Chat" + "Equipe por Função" (spec
> `2026-07-27-conversa-projeto-no-orizon-chat-design.md`).** Decisões do lojista: a conversa do
> projeto é a instância do projeto no Chat; membros DERIVADOS da equipe (interno) + cliente/arquiteto/
> **terceiros** como EXTERNOS dirigidos; engrenagens do ciclo mantidas; documento oficial pelo chat;
> autoridade stage-aware; modo privado a remover. **Fonte única da equipe = FUNÇÃO responsável da
> etapa** (`CicloEtapa.funcao_responsavel_id`, do Cronograma Padrão): funcionário DERIVADO — 1
> candidato = auto, >1 = LACUNA (ação gerencial), 0 = sem responsável; **terceiros contam** (têm
> funcao_id); montagem/assistência seguem por AMBIENTE (Mapa). `mod_equipe.equipe_do_projeto`,
> `candidatos_da_funcao`, `responsavel_da_etapa`, `etapa_executavel`, `montar_equipe_no_fechamento`.
> **Bloqueador INVERTIDO** = gate de execução por etapa (`main._bloqueio_execucao_etapa`, 409 na
> lacuna) ligado em medição(10) e operacional(12–16); PE/montagem pendentes. **Montagem no fechamento**
> (2ª assinatura→'fechado'): persiste os autos + resumo na conversa do projeto + **e-mail aos gerentes
> nas lacunas** (config-gated). **Membership**: `conversa_participantes.origem/removido` +
> `sincronizar_participantes_projeto` (derivado ∪ override manual — override vence); conversa de
> projeto na inbox ("📁"); `assunto=projeto` ABRE a conversa do projeto; painel de **Membros**
> (add/remove por gerente, `GET/POST .../participantes`). Testes: `test_equipe_fonte_unica.py`,
> `test_membership_projeto.py`, +`test_chat_wa.py`. **Suíte 1566 verde.** **Convergência do roster
> FEITA:** `CicloEtapa.responsavel_terceiro_id` (montador/medidor/PE terceirizados); `mod_equipe.equipe`/
> `salvar` derivam/gravam da fonte única — medidor/finalizador(=Projetista Executivo) = responsável da
> etapa; Equipe de Montagem = Mapa de Atribuições; Gerente Comercial/SAC/Supervisor informativos;
> `equipe_json` aposentado. **MODO PRIVADO REMOVIDO** (criação tirada da UI+backend; `enviar_mensagem`/
> `serializar_mensagem`/`listar_mensagens` sem privada; capacidade `ver_mensagem_privada` retirada;
> colunas `privada`/`corpo_cifrado` ficam legado; `test_chat_fatia4.py` removido).
> **GATE DE PE/MONTAGEM — FEITO (2026-07-27, fecha o item 10 e a frente do Orizon Chat).** O
> bloqueador invertido passa a cobrir: (a) **PE (etapa 11)** — o upload de documento de subfase e a
> conclusão travam (409) enquanto a função do PE estiver em LACUNA (`_bloqueio_execucao_etapa(...,"11")`
> nos endpoints `/ciclo/<subfase>/documento` e `/ciclo/<subfase>/concluir`); (b) **Montagem/Assistência
> (17/18)** — responsável por AMBIENTE no Mapa: `mod_equipe.montagem_lacunas` trava a conclusão (PATCH
> `/ciclo/17|18`) só quando há **>1 candidato** de montagem e algum ambiente sem responsável (0/1
> candidato = auto/sem_candidato, retrocompatível — projetos sem Mapa seguem como hoje). Testes:
> `test_gate_pe_montagem.py`. **Auditoria da Vera (UI Retenção + gates) → 1 correção + 2 testes:**
> (🟠) o gate de Montagem/Assistência (17/18) não olhava ambiente retido → concluir a etapa do
> projeto inteiro registraria "montado" um ambiente que a obra ainda segura; agora o PATCH `/ciclo/17|18`
> também barra (409) se `mod_retido.ambientes_retidos` não vazio (mesmo padrão do pe/upload e da
> Conciliação Final; NÃO era risco de razão — a 21 já protegia o contábil). +teste da montagem barrada
> por retido; +teste de isolamento por loja (404 cross-loja em `/parcelas` e `/retido/*`). Achados 🟡
> restantes (labels `em_aprovacao`/`liquidada` no front sem wiring ainda; restart local aplica
> migração) = informativos, não bloqueiam. **Deploy:** ✅ VPS A em `734ec69` (repromovida com a
> correção; ver nota de deploy no topo) + localhost + MCP reingerido; **VPS B intocada** na
> `Pre_Teste`; produção pendente.
>
> **11) Frente "Desmembramento OPERACIONAL por ambiente desde a medição" (spec
> `2026-07-27-desmembramento-operacional-desde-medicao-design.md`).** Dor: a obra do cliente segura
> ALGUNS ambientes enquanto outros seguem — hoje o ciclo é do projeto inteiro e um ambiente retido
> trava todos. Decisões FECHADAS do lojista: **parcela UNIFICADA** (reusa `ParcelaProjeto`,
> operacional + reconhecimento contábil na MESMA unidade — a provisão da etapa só reconhece quando o
> operacional executa; só os RECEBIMENTOS do cliente correm por fora); **retido por AMBIENTE**;
> **medidor SINALIZA, gerência CONFIRMA**; **continuação de onde parou**.
> — **Fatia 1 (commit `90eca97`).** `SinalRetido` (por ambiente, medidor sinaliza). `mod_retido`:
> `sinalizar`/`limpar_sinal`/`listar_sinais`/`confirmar` — `confirmar` reusa `mod_parcelas`
> (`particionar_por_selecao` + `congelar_parcelas`) → parcela `aguardando` (pronta, segue) × `retido`
> (aguarda obra), `Σ val_cont_congelado` exato. Endpoints `POST .../retido/{sinalizar,limpar,confirmar}`
> (sinalizar/limpar=`registrar_medicao`; confirmar=`autorizar`) + `sinais_retido` na GET `/parcelas`.
> **NÃO toca no razão.** Testes `test_retido.py` (5).
> — **Fatia 2 (núcleo: o GATE).** Status operacional segue por PARCELA; parcela `retido` fica FORA da
> execução. `mod_retido.parcela_do_ambiente`/`ambiente_retido`/`ambientes_retidos`/
> `gate_operacao_ambiente` (legado/não desmembrado/parcela que segue ⇒ passa). Gate plugado no
> **upload de PE por ambiente** (`POST .../pe/upload`) → **409** se o ambiente está em parcela retida.
> Testes `test_retido.py` (+2 = 7). _Adiado às fatias seguintes:_ linha de `CicloEtapa` por parcela
> (mudar o `UniqueConstraint` rippla todo o ciclo — só quando a visibilidade na tela exigir) e
> estender o gate a montagem/produção (mesmo helper).
> — **Fatia 3 (liberação/continuação).** A obra LIBERA ambientes retidos → a parcela retoma
> (`retido`→`aguardando`, continuação de onde parou — decisão #4). `mod_retido.liberar`: liberação
> TOTAL = flip de status; liberação PARCIAL (ondas) = **SPLIT** (liberados seguem, resto fica retido,
> reusando `congelar_parcelas` p/ `Σ val_cont_congelado` exato). Habilitado por
> `ParcelaAmbiente.valor_ambiente` (valor bruto por ambiente, gravado na confirmação → split exato sem
> reler o contrato). Endpoint `POST .../retido/liberar` (`autorizar`). Testes `test_retido.py`
> (+3 = 10). **NÃO toca no razão.**
> — **Fatia 4 (reconhecimento contábil — área sensível: razão).** `reconhecer_despesas_nfe` ganhou
> `fracao` (default `None` = projeto inteiro, **byte-idêntico** ao legado): quando informado, limita
> o reconhecido de cada rubrica a `fracao × constituído`, deixando o resto DIFERIDO no ativo `1.1.06`
> — **a parcela retida fica diferida**. A fração entra no `ref` (`match:<proj>:fNNNN:<rubrica>`) → ao
> LIBERAR (fração maior), a re-emissão reconhece só o **DELTA**; mesma fração é idempotente. Wiring
> vivo (`_fin_faturamento_segmentado_seguro`) passa `mod_retido.fracao_reconhecivel` =
> `Σ val_cont_congelado(não-retidas)/Σ(todas)` (exato por #5; `None` se não desmembrado). **Não
> duplica** o fluxo de 2026-07-13. Impostos e recebimento do cliente seguem por fora (§2). Testes
> `test_fase_d2_nfe.py` (defer+delta+idemp.) + `test_retido.py` (`fracao_reconhecivel`). _Simplificação:_
> granularidade = fração ELEGÍVEL do projeto; NF-e verdadeiramente por-parcela vem com a Fatia 5.
> **Auditoria da Vera (razão) → 2 correções aplicadas:** (🔴) **Conciliação Final (21)** bloqueia
> (409) enquanto houver ambiente retido — senão reconheceria a provisão retida como sobra (receita
> `4.4.02`) antes da execução, deixando o ativo `1.1.06` órfão (`POST .../ciclo/21/conciliar` checa
> `mod_retido.ambientes_retidos`, padrão do gate de PE); (🟠) `ref` do matching fracionado passou de
> bucket de fração truncada (`f%04d`, colidível) p/ o **ALVO em centavos** (`:a<cents>:<rubrica>`,
> colisão-livre) + `order_by(id)` em `fracao_reconhecivel`. Legado (`fracao=None`) byte-idêntico
> confirmado. Testes +2 (conciliar 409, frações próximas).
> — **Fatia 5 (UI) — FRENTE OPERACIONAL COMPLETA.** Modal **"Retenção por Obra"** (botão na barra do
> Ciclo): não desmembrado → pool com toggle "Marcar retido" (medidor) + "Confirmar desmembramento"
> (gerência); desmembrado → cartões de parcela (status colorido Segue/Retido/Em aprovação/Liquidada +
> Val_Cont + ambientes) com "Liberar selecionados" nas retidas (gerência). Consome `GET /parcelas`;
> sem step-up (backend enforça `registrar_medicao`/`autorizar`). `node --check` verde, tokens OK.
> **Desmembramento operacional: Fatias 1–5 COMPLETAS**, razão auditado pela Vera. **Deploy:** ✅ na
> VPS A (`6e0a08e`, ver nota de deploy no topo); VPS B/produção pendentes. **Gate de PE/montagem do
> chat FEITO** (item 10 — ver acima).
>
> **(Anterior, 2026-07-23 — mantido abaixo por referência.)**

## ⏸️ ESTADO ATUAL (2026-07-23) — retomar aqui

> **FAXINA Omie+SQLite COMPLETA na branch `chore/faxina-omie-sqlite`** (empilhada sobre
> `feat/ponto-de-venda`), suíte **1422 verde 100% em Postgres** (orizon_test derivado do `.env`).
> Omie não existe mais (integração, endpoints, colunas — DROP no PG —, UI, credenciais; cookie
> `orizon_session`); SQLite não existe mais (nem runtime, nem migrações, nem testes). Ver
> `## Sessão 113`. **Push RESOLVIDO em definitivo:** chave SSH desta máquina cadastrada no
> GitHub + remote em SSH — push funciona de dentro das sessões. Branches pushadas e **MERGEADAS
> na `main`** (PDV → faxina; conflitos com as Sessões 110–111 paralelas resolvidos — minhas
> sessões renumeradas 112/113; `_detalhe_grupo` combinou o batch de queries com a semântica
> "plano inteiro"). `orizon.db` destracked + `.gitignore` atualizado. **PENDENTE:** deploy A/B
> (atenção: re-login geral pelo cookie novo + DROP das colunas omie_* ao subir) e re-ingestão
> do grafo (Docker Desktop precisa estar aberto). DESCOBERTA: `orizon-manager` é o WORKTREE da
> `main` deste repo (não um clone à parte) — é dele que a `main` roda local.
>
> **(Anterior, 2026-07-22 — mantido abaixo por referência.)**

## ⏸️ ESTADO ATUAL (2026-07-22) — retomar aqui

> **Frente PONTO DE VENDA (PDV avançado) COMPLETA na branch `feat/ponto-de-venda`** — 4 fatias,
> 1 commit cada, suíte **1449 verde** (38 testes novos). PDV = Loja com mãe (`loja_mae_id`/`tipo`):
> fiscal pela mãe, contrato/modelos da mãe (código próprio na numeração), razão contábil PRÓPRIO,
> visão unificada com seletor de unidade + Consolidado com eliminações (1.1.09×2.1.09 por refs
> `rateio:*`), ação Rateio ao PDV reversível em par, financeiro oculto na UI do PDV (lançamentos
> vivos). Ver `## Sessão 112` e o spec `_geral/2026-07-22-ponto-de-venda-design.md`.
> **PENDENTE:** merge na `main` + push + re-ingestão do grafo; rodar
> `scripts/criar_pdv_caraguatatuba.py` no VPS (produção) p/ criar o PDV real; verificação manual
> no navegador (seção Pontos de Venda no Admin, seletor de unidade/Consolidado no Financeiro,
> modal Rateio, temas claro/escuro); definições do Diretor (metas do PDV, lista de rateios
> recorrentes).
>
> **(Anterior, 2026-07-20 — mantido abaixo por referência.)**

## ⏸️ ESTADO ATUAL (2026-07-20) — retomar aqui

> **Tudo na `main`, pushado.** A branch `feat/fatia2-datas-assinatura` (Fatias 2+3 + retirada do SQLite,
> Sessões 84–85) foi **mergeada na `main` e apagada** — o estado de 19/07 abaixo ("NÃO mergeada") ficou
> histórico. Depois do merge entraram ainda: spec do **Motor 5.0** (`docs/superpowers/specs/_geral/
> 2026-07-16-motor-5-reestruturacao-app-design.md`, execução adiada até a v1 estabilizar) e a migração do
> VPS dev/pré-homolog `167.88.33.121` para **Postgres 16** (runbook A/B via `/root/orizon-A.env`/`-B.env`).
>
> **Deploy 2026-07-20:** instância **A** (integração, `:8765`) atualizada para o topo do `main`
> (`b367b96`); instância **B** (pré-homolog, `:8766`) promovida para a tag **`v2026.07.20-homolog`**
> (mesmo commit). Ambas no ar (HTTP 302 interno e externo). Acesso ao VPS agora por **chave SSH**
> (ed25519 desta máquina autorizada no root). Script de deploy A+B aprimorado (mata só o processo da
> instância certa via cwd, poll até 302) — candidato a entrar no repo em `scripts/`.
>
> **Fatia 4 FECHADA no mesmo dia (Sessão 86): frente A+B CONCLUÍDA** — sinal de atraso geral na lista
> de projetos (spec §6), mergeada na `main`. QA da Vera pegou bug grave pré-merge (`status="fechado"`
> tratado como terminal — mataria a feature; corrigido + regressão).
>
> **Fatia 4 promovida à B no mesmo dia:** tag **`v2026.07.20.1-homolog`** na instância B (`:8766`);
> A no `main` (`01f2acd`). Script de deploy versionado em `scripts/deploy_ab.sh` (uso no VPS:
> `bash deploy_ab.sh <TAG>`).
>
> **Retomada (ainda 2026-07-20):** grafo MCP **re-ingerido** (código 2608 nós/2352 arestas — pendência 1
> resolvida; `docker.exe compose up -d` em `../mcp-orizon` funciona de dentro do WSL com o Docker Desktop
> aberto). As instâncias A/B do VPS viraram **serviços systemd** `orizon-a`/`orizon-b` (boot + auto-restart;
> antes eram screens manuais que não sobreviviam a reboot — era por isso que o pré-homolog "caía");
> `deploy_ab.sh` atualizado para systemctl (`da0957b`), auto-restart testado matando o processo.
>
> **Sessão 87 (ainda 2026-07-20):** frente **Custo Especial** (custo adicional não rateado nos ambientes,
> toggle no modal de parâmetros + provisão própria 1.1.06.20 × 2.1.04.20 / despesa 5.3.17) implementada
> ponta a ponta — motor, params, provisões/AF, contábil (FASE D2 + matching + conciliação data-driven) e
> frontend; QA da Vera com 1 achado corrigido (orçamento vazio). Nome mudou de "Custo Fixo" → "Custo
> Especial" antes do commit (colisão com o conceito contábil). Ver `## Sessão 87` e o spec
> `financeiro/2026-07-20-custo-especial-nao-rateado-design.md`.
>
> **Sessão 88 (2026-07-21):** fix do Total Flex — última parcela negativa ao remover ambiente (plano
> digitado p/ total antigo + guard furado que salvava o plano negativo). Reinit automático quando o
> total muda (`_tfAvistaRef`) + validação backend (`mod_fin.validar_plano_pagamento`). Ver `## Sessão 88`.
>
> **Sessões 90–91 (2026-07-21):** Revisão de PE reformada por decisão de processo — 11c compara
> VENDA à vista (motor 2× via `vbva_override`, motor inalterado) com coluna Renegociar; CFO mudou
> para a AF2 ("Comparar Valores", read-only). Ver `## Sessão 91` e o spec
> `ciclo/2026-07-21-revisao-pe-venda-renegociacao-design.md`.
>
> **Sessões 92–93 (2026-07-21):** Fatia 3 implementada e CORRIGIDA por feedback — complemento POR
> DIFERENÇA (3º XML `xml_compl` por ambiente marcado; fator exato 1/(1−p) dos custos adicionais;
> descontos do contrato; desc global travado; XML idêntico ⇒ diferença zero), modal comparativo,
> Termo Aditivo sobre a diferença negociada e **Aprovação do PE assinável** substituindo o upload
> de PE Assinado (gate da 11e). Ver `## Sessão 93`.
>
> **PENDENTE (retomar por aqui):** Verificação manual no navegador — marcadores no PDF (S85),
> coluna Entrega + selo Atrasado (S86), Custo Especial (S87), Total Flex + remover ambiente (S88),
> comparação de venda/coluna Complemento na 11c e CFO na AF2 (S91), fluxo completo da 11e (S92–94:
> importar modelos de **Termo Aditivo** e **Aprovação de PE** em Config → Documentos; carregar XML
> de complemento por ambiente; modal comparativo; negociar a diferença com desconto por ambiente —
> pagamento nasce à vista/entrada 0; gerar/assinar Aprovação do PE e Termo Aditivo; concluir a 11e),
> temas claro/escuro.
>
> **Frente CONCLUÍDA (S95+S97): Ajustes Excepcionais de Fábrica** — backend contábil E frontend
> (painel Admin "Acordos c/ Fábrica" + preview/aplicação na etapa 12) prontos; spec
> `financeiro/2026-07-21-descontos-acrescimos-excepcionais-fabrica-design.md`. Verificação manual
> pendente: aba nova no Admin (criar acordo, ajustes, acertar/liquidar/encerrar, extrato) e o
> preview na conferência, temas claro/escuro. Frentes candidatas seguintes: Agenda Global,
> empacotar `comercial`, baseline Alembic.
>
> **(Anterior, 2026-07-19 — mantido abaixo por referência.)**

## ⏸️ ESTADO ATUAL (2026-07-19)

> **Frente A+B — Fatias 2 e 3 + retirada do SQLite na branch `feat/fatia2-datas-assinatura`, suíte 1295 verde
> (SQLite) e 1293+2skip (Postgres), NÃO mergeada.** Fatia 3: prazo contratual em dias úteis (`somar_dias_uteis`,
> parâmetro `prazo_contratual_dias_uteis`), aviso de coerência na Config → Cronograma, e 4 marcadores no contrato
> (`DATA_PREVISTA_ENTREGA`/`PREVISAO_MEDICAO`/`PRAZO_CONTRATUAL`/`VENDA_PROGRAMADA`). **SQLite APOSENTADO no runtime**
> (o app exige Postgres via `DATABASE_URL`; use `./run.sh`) — resolveu o incidente de "projetos sumindo" (fallback
> silencioso pro SQLite defasado). Refinamentos da Fatia 2: modal do design no override, `folga_autorizada` +
> recheck na assinatura, bloqueio desde a 1ª assinatura. Ver `## Sessão 85`. **PENDENTE:** verificação manual da
> Fatia 3 no navegador + **merge da branch** (grande: Fatia 2 + Fatia 3 + infra); depois Fatia 4 (sinal de atraso).
>
> **(Anterior, 2026-07-18 — mantido abaixo por referência.)**

## ⏸️ ESTADO ATUAL (2026-07-18)

> **Frente A+B — Fatia 2 na branch `feat/fatia2-datas-assinatura`, suíte 1285 verde, NÃO mergeada.** Datas do
> acordo (previsão de medição + expectativa de entrega) agora obrigatórias na assinatura; folga do trecho
> medição→entrega (`mod_cronograma.folga_medicao_entrega`); bloqueio de folga<0 com override gerencial auditado;
> trava da 2ª assinatura pelas duas datas; UI de entrada no card (medição + entrega + checkbox venda programada +
> fluxo de override). `Projeto` ganhou `previsao_medicao`/`venda_programada`. Ver `## Sessão 84`. Plano:
> `docs/superpowers/plans/2026-07-18-fatia2-datas-assinatura-enforcement.md`. **PENDENTE:** verificação manual no
> navegador + merge/push + re-ingerir MCP; depois Fatia 3 (prazo contratual em dias úteis + marcadores no contrato)
> e Fatia 4 (sinal de atraso geral + UI final). Nota de polish: `autorizarDataEntrega` usa `prompt()` (trocar por
> modal com senha mascarada).
>
> **(Anterior, 2026-07-17 — Fatia 1, já mergeada na `main`; mantido abaixo por referência.)**

## ⏸️ ESTADO ATUAL (2026-07-17)

> **Frente A+B (cronograma/data de entrega) — Fatia 1 na branch `feat/fatia1-cronograma-data-entrega`, suíte
> 1270 verde, NÃO mergeada.** Corrigidos: o bug da data de entrega que "sumia" do card (vinha do `Projeto`,
> mas não era serializada no GET contrato), a semântica do Cronograma Padrão (`prazo_dias`=duração, não
> acumulado; default reescrito + `cronograma_formato`), a acumulação em `gerar_cronograma_projeto` (que
> destravou um bug latente: data persistida ≠ preview da tela), e a normalização de config legada na leitura.
> Spec completa da frente (4 fatias) em `docs/superpowers/specs/ciclo/2026-07-17-ancora-entrega-folga-venda-programada-design.md`;
> plano da Fatia 1 em `docs/superpowers/plans/2026-07-17-fatia1-correcoes-cronograma-data-entrega.md`. Ver
> `## Sessão 82` abaixo. **PENDENTE:** verificação manual no navegador (o card reexibir a data após validar/
> sair/voltar) + merge/push; depois Fatias 2–4.
>
> **(Anterior, 2026-07-16 — mantido abaixo por referência.)**

## ⏸️ ESTADO ATUAL (2026-07-16)

> **Tudo na `main`, suíte 1184 verde, pushado.** Sessões 78 (modelos de documento) e 79 (faxina +
> pacotes) fechadas. Ver essas seções para as decisões.
>
> **Frente em andamento (Sessão 80) — super_admin god-mode:** branch `feat/super-admin-acesso-pleno`
> (suíte **1188 verde**), desbloqueia super_admin p/ criar perfis/usuários e acessar o Cadastro (liberdade
> plena "por enquanto"). **NÃO mergeada ainda** — pendente verificação manual no navegador + merge/push.
> Detalhes e decisões na seção `## Sessão 80` abaixo.
>
> **PENDENTE Nº 1 — ninguém clicou na tela dos modelos de documento.** Toda a frente da Sessão 78 foi
> verificada no nível do contrato JSON (curl contra servidor real) + `node --check`, nunca por
> navegador. O pipeline de importação foi provado ponta a ponta num `.docx` real (LibreOffice → 42
> cláusulas → marcadores/cravados detectados), mas a **interface** que o expõe nunca foi exercitada por
> um humano. Roteiro: Config › Documentos → card Contrato abre modal → subir `.docx` real → revisão
> mostra marcadores ausentes/desconhecidos e dados da loja cravados com trechos → "Ver PDF de exemplo"
> → "Ativar" → card mostra "Versão 1 ativa"; subir `.pdf` → erro explicativo; logar como **gerencial**
> → cards não clicáveis.
>
> **PENDENTE Nº 2 — reorganização de pacotes está NO MEIO.** 3 dos 4 domínios grandes viraram pacote
> (`fiscal/`, `integracoes/`, `auth/`); falta o **`comercial` (15 arquivos)** — o mais arriscado (ciclos
> `mod_contrato`↔`mod_documentos`, e `mod_fin/` já empacotado dentro). **Recomendação registrada: NÃO
> empacotar o comercial sem antes tratar os caminhos relativos a `__file__`** — foi um deles
> (`_LOGIN_HTML`) que derrubou a página de entrada nesta sessão, em silêncio, com a suíte verde. Os 4
> módulos da importação de contrato (`mod_contrato`, `mod_documentos`, `mod_documentos_import`,
> `mod_marcadores`) seguem na raiz e funcionam; empacotá-los quebraria `CONTRATO_TEMPLATE_DIR` do mesmo
> jeito (e `_carregar_md` engole arquivo ausente como string vazia → contrato sairia SEM cláusulas,
> verde). `tests/test_caminhos_de_pacote.py` é o ratchet que pega isso — mas só dentro de pacote.
>
> Pendente também: re-ingerir o grafo MCP (código mudou de lugar — o grafo está obsoleto).
>
> **Nota:** a frente PostgreSQL commitou na `main` em paralelo (`c9f3324`, backfill de loja seed em
> banco não-SQLite). Não é desta sessão; as branches `feat/migracao-postgresql{,-v2}` seguem vivas.

## ⏸️ ESTADO ATUAL (2026-07-15)

> **(superado pelo de 2026-07-16 acima — mantido por referência.)** Frente "Modelos de documentos da
> loja" pronta mas ainda não mergeada; a Sessão 79 mergeou e seguiu com a faxina.

## ⏸️ ESTADO ATUAL (2026-07-14, tarde)

> **Maratona 2026-07-14 (branch `feat/desmembramento-fatia2-ciclo`, suíte 1033 verde).** Sequência de
> testes manuais do usuário + implementações:
> - **Bug do select da sidebar** (opções invisíveis) — `color-scheme:dark` + opções opacas.
> - **Gate do PE** (`_podePE`) usava nomes de função obsoletos → destravado p/ níveis-base.
> - **Comparação PE enxuta** (11c): valor do projeto + Δ CFO por ambiente com % + média final (sem provisões).
> - **Desmembramento "parcela" → "Fase"** (rótulos; endpoints/tabelas mantidos).
> - **F0 (bug ①):** os 4 custos adicionais + Custo Financeiro viram LINHA ajustável no painel de Provisões
>   (`itens_provisao` inclui-os; `cust_var_marg_cont` soma SÓ `_RUBRICAS` → sem double-count; `_AF_ITEM_RUBRICA`
>   ganha os 4; custo financeiro read-only). Box inferior removido.
> - **Revisão amarrada à etapa** (Rev1↔etapa 8 / Rev2↔11d): NÃO auto-avança p/ Rev2; reeditável pelo ger
>   adm/fin **até a etapa ser aprovada** (trava por aprovação, não por registro; depois exige Diretor).
> - **AF no modal:** botões só **Revisar** + **Aprovar** (Aprovar salva a revisão E aprova a etapa,
>   `_provAprovar`); "Aprovar (gerencial)" saiu do card. **Devolução removida das AF**; **Cancelamento só na AF1**.
> - **Cancelamento de contrato (opção B):** `mod_contabil.cancelar_contrato` (estorno total do diferido +
>   juros; reusa `devolver_venda` f=1.0) + endpoint `POST /api/orcamentos/<id>/cancelamento` (gate Diretor,
>   bloqueio pós-NF-e, status **"cancelado"**) + botão marrom (tokens `--cancel`). Reembolso físico → Tesouraria (futuro).
> - **Auditoria Contábil:** `mod_contabil.auditoria_contabil(projeto_id)` (view do razão) + endpoint GET
>   `/api/projetos/<nome>/auditoria-contabil` + botão/modal no topo do ciclo (estornos destacados). **Falta o PDF.**
> - **UI:** verdes do "design antigo" corrigidos (botão Provisões → `--accent`; "concluída" → `--text`).
> - **Fase A (cronograma):** `mod_cronograma.limite_etapa`/`prazo_excede_limite`/`garantir_cronograma`/`tem_cronograma`
>   + `ParcelaProjeto.prazo_conclusao` (campo+migração). **Fase B (núcleo):** `mod_parcelas.particionar_por_selecao`.
>
> **Specs novas (rascunho/design, em `docs/superpowers/specs/`):** `2026-07-14-conferencia-registro-provisoes-af3`,
> `2026-07-14-agenda-global-projetos`, `2026-07-14-fases-por-ambiente-prazos-devolucao` (as 6 decisões confirmadas
> pelo usuário; gate do prazo = Diretor `autorizar`).
>
> **⏭️ PENDENTE (retomar):** **Fase B.2** (endpoint que orquestra `particionar_por_selecao`+`congelar_parcelas`+
> gate de prazo → cria `ParcelaProjeto`; frontend: checkbox de ambientes por etapa 9+ + input de prazo). **Fase C**
> (modal "Carregar PE" na 11c: desmembrar + Aprovar por fase dourado→verde, sem botão de revisão). **Fase D**
> (documentos por fase). **Fase E** (Devolução/Cancelamento FORA do ciclo, supervisionado pela auditoria).
> **PDF da auditoria.** Além do backlog anterior (FASE D2 Conferência spec `2026-07-12` — não implementada;
> registro único ordenado de rubricas F0b; `com_adm` vira provisão `2.1.04.20` F1; bug ② efetivado).
> **Tokens a criar (Fase C):** dourado escuro (Aprovar) + verde escuro (Aprovado).
>
> **➕ Frente CRONOGRAMA (iniciada 2026-07-14 tarde; backend COMPLETO+TDD, suíte 1042 verde).**
> - **ADR** `2026-07-14-arquitetura-ciclo-um-fluxo-duas-visoes`: ciclo é UM fluxo (fonte única, escopo do
>   projeto), apresentado em DUAS visões — **Comercial** (etapas 1–7) × **Execução** (8+); assinatura = handoff;
>   NÃO parte o dado. AF (8) cai em Execução. Auditoria/agenda/cronograma no nível do projeto.
> - **Dois cronogramas** do MESMO Cronograma Padrão (âncoras opostas): `mod_cronograma.cronogramas(etapas,
>   inicio, entrega, codigo_entrega)` → **Progressivo** (cedo, do início) + **Regressivo** (Prazo Limite, da
>   entrega) + **Folga** (=Reg−Prog; negativa = não cabe → cronograma próprio + senha). + `cronograma_do_projeto`
>   + `cabe_no_cronograma` + `cronograma_projeto_view` (3 colunas **Prazo Limite / Planejado / Executado** por
>   etapa). Fase A: `limite_etapa`/`prazo_excede_limite`/`garantir_cronograma`.
> - **Âncoras:** `Projeto.data_entrega` (regressivo, def. na assinatura) + `data_inicio` (progressivo) +
>   `ParcelaProjeto.prazo_conclusao` + migrações. **Modelo:** DERIVAR as datas (não persistir) — guarda só
>   âncoras + prazos (editáveis = cronograma próprio) + `concluido_em`. Entrega = etapa 16 (âncora); Recebimento
>   = etapa 14 (marco destacado).
> - **Spec `fases-por-ambiente-prazos-devolucao` refinada:** subfase 11c "Revisão de PE" → **"Projeto Executivo"**
>   (etapa-mãe 11 → "Especificação Técnica"; **rename SÓ display**, IDs `pe_*` mantidos). 4 botões da subfase
>   (mesma linha, mesmo tamanho): **Carregar Projeto Executivo** (sobrescreve; indicador [Rev1,Rev2…]), **PE×PV**
>   (fábrica vendido×executivo), **Desmembrar Fases**, **Aprovar por fase** (dourado→verde). **Botão Revisão
>   eliminado** (feito). **Senha:** livre até concluir; concluir = senha do PRÓPRIO usuário; reabrir = gerencial.
>   **Devolução/cancelamento pós-AF1 = FORA do ciclo** (supervisionado pela auditoria); devolução removida das AF.
>
> **✅ Feito na continuação (Sessão 76, suíte 1049 verde):** bug do briefing (etapa 3 abria o do CLIENTE →
> projeto errado; agora `abrirBriefingProjeto`); **Cronograma Passo 2** (campo "Data de entrega esperada" +
> Validar no card do Contrato → `POST .../data-entrega` + folga; campo SEMPRE editável); **gate da AF**
> (`PATCH .../ciclo/<8|11d>` só fecha com data de entrega DEFINIDA **E** contrato totalmente assinado, independente
> da sequência — `test_af_gate_data_entrega.py`); gates `_podeEditarMapaFront`/`_NFE_NIVEIS_EMITE` corrigidos.
>
> **⏭️ PENDENTE (revisado):** **Cronograma Passo 3** — botão **"Cronograma próprio"** (editar prazos + senha
> gerente/diretor quando a folga é negativa); o endpoint `GET /api/projetos/<nome>/cronograma`, o modal e as 3
> colunas (Prazo Limite/Planejada/Executada) já existem. **Fase B.2** (endpoint do desmembramento por seleção +
> UI checkbox por etapa 9+). **Fase C** (subfase Projeto Executivo: 4 botões + senha). **Rename display**
> (Especificação Técnica/Projeto Executivo) + **Medição→subfase** (🔴 estrutural, separado). **PDF da auditoria.**
> **Navegação 2 visões** (ADR, depois). Backlog anterior mantido.

## ⏸️ ESTADO ATUAL (2026-07-14)

> **🏗️ Frente ATIVA — "Resultado da Venda + Aprovações Financeiras" + desmembramento do ciclo.**
> Branch **`feat/desmembramento-fatia2-ciclo`** (NÃO mergeada; suíte **1022 verde**). Spec:
> `docs/superpowers/specs/financeiro/2026-07-13-resultado-venda-aprovacoes-financeiras-design.md`. É a implementação do
> "Backlog (1)" do estado de 2026-07-12 (os custos adicionais viram provisão), + o custo financeiro, as 3
> margens, o gate de AF, a devolução e o desmembramento do ciclo em parcelas.
>
> **INVARIANTE MESTRE (não violar):** nada toca a DRE exceto a **NF-e real**. Todo ajuste — AF, troca de
> ramo, conferência, devolução — é **ativo × provisão** (`1.1.06.0X × 2.1.04.0X`), nunca despesa.
>
> **✅ Feito na branch (commits `ab8e4b1`…`16665dd`, ver `git log main..HEAD`):**
> - **Custos adicionais como provisão (Fatia A):** os 4 (Comissão de Arquiteto+retenção · Fidelidade · Custo
>   Viagem · Brinde) são constituídos no contrato como ativo diferido (`1.1.06.15-19 × 2.1.04.15-19`).
>   **Constituídos pelos toggles individuais** (`comissao_arq_ativa`/`fidelidade_ativa`/`fora_da_sede`/
>   `brinde_ativo`), **nunca** por `incluir_custos` (senão o caso "empresa absorve" fica sem lançamento).
>   Contas novas: `1.1.06.15-19`, `2.1.04.15-19`, `1.1.07`, `2.1.07`, `4.4.03`, `5.5.04`, `5.3.15`.
> - **Custo financeiro, 3 ramos (Fatia B):** `mod_fin.ramo_financiamento(codigo)` resolve pela forma de
>   pagamento → **loja** (receita financeira; juros a apropriar `1.1.07×2.1.07`; SEM despesa) · **loja_
>   antecipacao** (despesa provisionada `5.5.03`) · **financeira** (despesa provisionada `5.5.04`). `Orcamento`
>   ganhou `ramo_financeiro`+`ramo_financeiro_seq`. Troca de ramo idempotente. Gatilhos de reconhecimento
>   completos (antecipação/financeira/loja) — fecharam o 🔴 da Vera (receita fictícia): `2.1.04.19` é
>   **excluída** de `conciliar_final` (custo financeiro tem rota própria).
> - **3 margens (Fatia B):** `mod_provisoes.margens_venda(vavo,cust_ad,cust_var,val_cont)` → **Contribuição**
>   (base Val_Liq) ≥ **Venda** (VAVO) ≥ **Contrato** (Val_Cont) — invariante só vale com margem positiva.
>   "Margem Operacional" reservada pra DRE (4ª). Cadeia de bases: **Val_Cont → VAVO** (−Cust_Fin) **→ Val_Liq**
>   (−Cust_Ad). Comissões de loja sobre Val_Liq; arquiteto/fidelidade sobre VAVO; custo financeiro sobre Val_Cont.
> - **Gate AF (Fatia C):** rev1/rev2 agora tranca (`travada_em`) + checa limite (`exige_aprovacao_diretor`,
>   AF1=1%/AF2=2%) + dispara `disparar_deltas_af` (delta **convergente por valor** — lê saldo atual da provisão
>   e ajusta ao alvo; idempotente; ativo×provisão). ⚠️ **Sutileza aberta:** o gate usa `perfis.pode(nivel,
>   "autorizar")`, mas **`autorizar` NÃO é exclusivo do Diretor** (master E gerencial têm por padrão) — decidir
>   se quer capability Diretor-específica.
> - **Devolução (Fatia D):** `devolver_venda(fracao)` estorna proporcional, **capado ao saldo aberto**, ativo×provisão.
> - **Desmembramento do ciclo:** Fatia 1 (`mod_parcelas`: congelar/validar partição, fração #5 com Σ==Val_Cont
>   exato, gate AF #10) + Fatia 2 **#1** (criação de parcela, endpoint + modal na 11c) + **#13 Conferência e
>   Implantação** (`conferencia_pedido`: ajusta Custo de Fábrica pela diferença do PE + reclassifica p/ Outros
>   Fornecedores `2.1.04.14`, ambos ativo×provisão; endpoint + UI na etapa 12, renomeada "Conferência e
>   Implantação do Pedido").
> - **Fix CSS** (`16665dd`): opções de `<select>` da sidebar ficavam brancas-no-branco (só visíveis no hover)
>   nos dois temas — a sidebar é escura sempre e re-mapeia `--surface-2→item-active` translúcido + `--text→branco`,
>   mas o `color-scheme` seguia o tema. Fix: `.sidebar{color-scheme:dark}` + opções em fundo opaco. **Bug
>   latente, existe na `main` também** → entra no merge da branch.
>
> **🔎 Teste manual em curso** pelo usuário (roteiro artifact `scratchpad/roteiro-teste-manual.html`).
> **Credenciais:** Diretor **`pdm2026`** (Pedro da Mota, nível master) · Consultora **`mds2026`** (Marcia dos
> Santos, operador). Achados: (a) modalidades "só à vista" = eram invisíveis, **CORRIGIDO**; (b) venda associada
> à Marcia com Pedro logado = **ESPERADO** (venda é da criadora Marcia; Diretor vê/gere todos — escopo gerente+).
>
> **⏭️ PENDENTE:**
> - **#7 (ciclo por parcela)** — única peça do desmembramento **não iniciada**: `CicloLogistico` por parcela,
>   progresso por parcela nas etapas 12-16, `CicloEtapa` agregado, trava pós-Implantação por parcela. **Invasivo
>   → chamar a Vera** antes.
> - **Decisão de merge** da branch na `main` (frente madura, 1022 verde). Ao mergear: escrever a Sessão no
>   DEV_LOG (este bloco serve de base) + **re-ingerir o grafo MCP**.
> - Fatia C: decidir capability do gate (ver ⚠️ acima).
>
> _(Estado anterior 2026-07-12 — FASE D2 mergeada — logo abaixo.)_

## ⏸️ ESTADO ATUAL (2026-07-12)

> **🏗️ Frente ATIVA — infraestrutura contábil ponta a ponta (p/ o Projeto Simulação popular DRE/Balanço/
> Provisões/Reconciliação pelo fluxo REAL de fechamento).** Fases: **A** (caixinhas) ✅ **no VPS**. **B1**
> (segmentação de receita Mercadoria × Serviço — default 65/35 na Loja + override do Diretor) ✅ **mergeada**
> (Sessão 64). **B2** (eventos: Adiantamento → receita segmentada → CMV=CFO → constituição COMPLETA das
> provisões + impostos-provisão diferida + custo financeiro direto; face fiscal reescalada; bug reconciliar)
> ✅ **mergeada** (Sessão 65). A DRE representa o projeto e reconcilia com o motor centavo a centavo.
> **C** (painel de Provisões por tipo A/B/C/D) ✅ **mergeada** (Sessão 66).
> **D** (reconciliação Provisionado × **Efetivado** × Saldo × Destino: efetivar_provisao 2.1.04.x×2.1.01
> competência; sobra→4.4.02 receita / falta→5.6.10 despesa; Contas a Pagar MVP; painéis Financeiro + aba no
> Projeto; DRE passa a incluir 4.4) ✅ **mergeada** (Sessão 67). **Validado ponta a ponta pela Simulação
> Claude** (3 XMLs Promob reais + Aymoré 10x): Val_Cont 278.769, ganho da 2ª aprovação vira sobra reconciliada,
> lucro líquido 93.598, Balanço fecha.
> **A infra contábil (A→D) está COMPLETA.** Backlog contábil: **estorno de cancelamento fiscal** (B2) e
> **sub-razão de Contas a Pagar** por fornecedor/vencimento (aging). `[CONFIRMAR CONTADOR]` pendentes seguem
> documentados no razão.
> Processo da frente: auditoria + plano por fases → OK do usuário → implementa 1 fase de cada vez, TDD, **para
> antes de mergear** p/ conferência dos números. Dinheiro = seguir NOMENCLATURA.md + prova de não-duplicação.
> `[CONFIRMAR CONTADOR]` pendentes (documentados no razão): receita no doc fiscal · adiantamento passivo no
> Simples · timing dos impostos-provisão · custo financeiro direto · estorno de cancelamento fiscal.
>
> **🏗️ Próxima frente ATIVA (definida em 2026-07-12) — FASE D2.** Spec:
> `docs/superpowers/specs/financeiro/2026-07-12-fase-d2-provisao-completa-conciliacao-final-design.md` (desenho
> FECHADO, sem pontos em aberto, verificado com Fable 5 usando números reais — **implementação ainda não
> começou, próximo passo**). Projetos legados (fluxo antigo) ficam como estão, sem migração. Surgiu da
> **Simulação
> Claude 2** (rodada pela Vera, `.claude/agents/vera.md`, via API real até a assinatura do contrato). Três
> ajustes: **(1)** seletor de orçamento trava sempre no orçamento **contratado** após o fechamento (hoje
> usa localStorage/último-atualizado — frontend, baixo risco). **(2)** **provisionar TUDO no ato do
> contrato** (as 10 rubricas, incl. Custo de Fábrica 2.1.04.06, hoje fora de `_PROV_FECHAMENTO`) com
> **matching pleno** da despesa na NF-e (valores planejados) e ajuste depois via reconciliação (sobra→
> 4.4.02/falta→5.6.10, mecanismo que já existe, agora pras 10 rubricas) quando o real diverge — exige
> `2.1.06` virar "Receita a Realizar" (valor cheio) + grupo novo `1.1.06` "Custos a Apropriar" (espelha o
> padrão de `1.1.05`/Impostos). **(3)** nova etapa do ciclo **"Conciliação Final"** (após a `20` Aprovação
> final) que resolve à força qualquer saldo remanescente das provisões e leva o projeto a um status novo
> no painel, **"Concluído"**. **Nota:** as contas `2.1.04.14` (Outros Fornecedores) e
> `reclassificar_provisao` (commits `bb2f7d1`/`f00c94e`, já na `main`) **existem no código mas não têm
> Sessão registrada aqui** — ao fechar a FASE D2, também escrever a sessão retroativa dessas duas.
>
> **✅ FASE D2 COMPLETA (Sessão 70) — as 6 fases mergeadas na `main` (suíte 946 verde; auditada pela Vera:
> não-duplicação provada centavo-a-centavo, Balanço fecha em cada etapa, veredito APTA PARA MERGE).** Fase 1
> (`af0c334`, grupo `1.1.06` + rename `2.1.06`) · Fase 2 (`afe4c1c`, constituição das 10 rubricas via
> `1.1.06.0X`, `registro_venda_contrato`, `recebimento_venda` abate `1.1.02`) · Fase 3 (`d6bb760`, matching
> pleno na NF-e, `reconhecer_despesas_nfe`, `faturamento_cmv` retirado) · Fase 4 (`ef09947`,
> `reclassificar_provisao` espelha `1.1.06`, sobra/falta cobre as 10) · Fase 5 (`ba827cd`, seletor trava no
> contratado, `contratado_id` aditivo) · Fase 6 (`25a84df`, etapa 21 "Conciliação Final" +
> `mod_contabil.conciliar_final` + status "Concluído" distinto de "fechado"). Sessão retroativa 69 escrita
> p/ `2.1.04.14`/`reclassificar_provisao`. 🟡 aberto (não-bloqueante, herdado da FASE D): o painel de
> Reconciliação mostra `saldo` bruto (provisionado−efetivado) mesmo após a resolução — a resolução vive na
> coluna `resolvido`; avaliar se num projeto "Concluído" isso confunde.
>
> **Backlog registrado em 2026-07-12, tratar assim que a FASE D2 fechar (sem spec própria ainda):**
> **(1)** revisado — em vez de uma "Provisão de Custos Adicionais" genérica, são **5 rubricas novas**,
> mesmo padrão das 10 já existentes (`2.1.04.x` + espelho `1.1.06.x`, entram em
> `_PROV_FECHAMENTO`/matching pleno/reconciliação): **Comissão de Arquiteto** e **Retenção de Comissão de
> Arquiteto** (espelha `2.1.04.12`, conta própria — não misturar com a retenção de comissão de vendas,
> gatilhos diferentes) · **Fidelidade** · **Custo Viagem** · **Brinde** (já existe `5.3.12 Brindes` no
> plano, solta, sem evento — reaproveitar como lado despesa do matching). Confirmado no motor
> (`mod_negociacao.py`): comissão de arquiteto e fidelidade são custos reais recuperados no preço
> (`com_arq`/`pro_fid`), não desconto ao cliente — hoje nenhuma das 5 tem lançamento contábil.
> **⚠️ Sutileza confirmada no motor:** o toggle master "Custos Adicionais" (`incluir_custos`/`tog_cadi`)
> **não** controla se o custo existe — só se ele é **repassado ao preço** (cobrado do cliente) ou
> **absorvido** (empresa paga, margem cai, cliente não vê). `com_amb`/`pro_amb`/`num_via`/`num_bri` são
> calculados pelos **toggles individuais** (`comissao_arq_ativa`, `fidelidade_ativa`, `fora_da_sede`,
> `brinde_ativo`) e **sempre** entram em `liq_amb`, mesmo com `tog_cadi=False`. **Constituir as 4/5
> provisões pelos toggles individuais, nunca pelo `incluir_custos`** — senão o caso "empresa absorve o
> custo" (o que mais precisa de provisão, por não ter cobertura no preço) fica sem lançamento. **(2)**
> mudar o **tema padrão de iniciação do sistema para claro** (hoje `Usuario.tema` default é `'escuro'` —
> confirmado pelo usuário). **(3)** nova **aba Fiscal com as notas emitidas** (lista de `DocumentoFiscal`
> — NF-e/NFS-e já emitidas, histórico/consulta).
>
> _(Frente anterior — Perfil-4/perfis por loja — abaixo. Follow-up ainda válido: re-chave do escopo operacional
> para Função, dormente desde o Perfil-4.)_

## ⏸️ ESTADO ATUAL (2026-07-10)

> **🚀 Deploy no VPS mais recente (2026-07-10, `4fe9955`):** `http://167.88.33.121:8765` no ar (HTTP 302),
> **banco preservado**, migrações idempotentes rodaram no start (`funcoes_seed_v1`, `perfis_v3_2026`,
> colunas `usuarios.funcao_id`/`Terceiro.usuario_id`/cronograma, tabela `atribuicoes_ambiente`). Usuários
> migrados aos 4 perfis (nenhum cargo-nível antigo). MCP re-ingerido (código 1813 nós). **Suíte 816 verde.**
>
> **Frentes fechadas (jul/2026, sessões 52–61):** Modulos_Orizon **v10** (sub-entidades Endereço/Bancário/
> PIX + Tabela de Funções + Folha de Pagamento) · **v11** (Cronograma do Ciclo: acesso corrigido + datas +
> reauth) · **v12** (responsável por função + Função×Perfil) · design **v8/v9/v10** (inputs, botão primário,
> token próprio) · **Fase 0** (perfis.py fonte única + seed de Funções) · **Fase 1** (Mapa de Atribuições +
> `mod_escopo` + 404 fora de escopo) · **Perfis de Usuário** (tela Admin, matriz) · **Perfil-4** (Perfil =
> 4 níveis de ACESSO por módulo/painel; cargos viram Função; enforcement da matriz).
>
> **Os três eixos (modelo vigente):** **Perfil** (acesso, `perfis.py`/`Usuario.nivel` — diretoria/gerencial/
> consultor/suporte) × **Função** (cargo, tabela `Funcao`) × **Escopo de visibilidade** (posse +
> `atribuicoes_ambiente`/`mod_escopo`). Specs em `docs/superpowers/specs/perfis/2026-07-10-*`.
>
> **⚠️ Próxima frente pendente (retomar aqui):** **re-chave do escopo operacional para Função.** No Perfil-4
> os operacionais (Medidor/Projetista/Supervisor) viraram **Consultor=posse**, então a visibilidade-por-Mapa
> deles ficou **dormente** (`mod_escopo._ESCOPO_ATRIBUICAO` ainda chaveia nos slugs-cargo antigos, que não
> existem mais como perfil). Re-chavear para `Funcao` reativa a Fase 1. Não vaza dados — só relaxa a
> restrição fina. Outros follow-ups: precisão de capacidades por Função; gate backend dos módulos
> operacionais p/ Suporte (hoje só escondido na UI); semear Funções ao criar loja nova.
>
> _(Histórico do deploy anterior, fiscal/Financeiro, abaixo.)_

> **🚀 Deploy no VPS (2026-07-09, `3d60a43`):** servidor online `http://167.88.33.121:8765` — **Módulo
> Financeiro completo (#1–#6) + wiring do faturamento + atualização v2→v5 (5 fronts)**. Migrações idempotentes rodaram
> no start (colunas `lancamento.ref/motivo/ia_sugestao`; backfill das 3 provisões no 1º acesso ao Plano de Contas por
> owner). **Banco preservado**, HTTP 302 local / **200 externo**, sem erros. _(Antes → `7ff3cf0`: Financeiro #1–#6 +
> tabelas conta/lancamento/periodo_contabil criadas no start; e `f36b72b`: modularização + design.)_ **Banco PRESERVADO desta vez** (a pedido): NÃO houve
> `rm orizon.db`/seed — as **migrações idempotentes rodaram no start** e adicionaram as colunas novas
> (`Loja.modulos_ativos`, `Usuario.tema` → confirmado presente). Dados de teste do VPS mantidos. **Contexto:** o VPS
> é ambiente **de dev/teste aberto a pessoas remotas**, ainda **não** há produção operacional; dados são falsos.
> **Emitente configurado no VPS (2026-07-08):** o Emitente INSPIRIUM (CNPJ 19.152.134/0001-56, homologação, IM/IBGE/
> cód-serviço/ISS/CSOSN/endereço = espelho do local) foi replicado e `lojas.id=1.emitente_id=1` apontado → `prontidao`
> **pronta p/ produto e serviço** e `resolver_emitente` OK (igual ao localhost). **Segredo tratado com cuidado:** o
> token Focus **homologação** foi decifrado no local, enviado **pelo canal SSH** (nunca no transcript) e **re-cifrado
> com a chave própria do VPS** — a `config/fiscal.key` **local (chave-mestra) NÃO** foi exportada; o VPS gerou a sua
> (perm 600). Temporários (`tok_tmp`) apagados. Token de **produção** segue indefinido. Senhas são acessíveis de fora.
> **Nota:** este commit de doc (o próprio banner)
> fica 1 à frente do VPS — doc-only, não exige re-deploy. **Runbook via arquivo** (`bash /root/deploy_once.sh`, deixado
> no VPS): evita o self-kill do `pkill -f main.py` (o argv inline conteria `main.py`); ver `DEV_RULES.md`.
> _(Deploy anterior: 2026-07-07, `ca05a61`→`ce209ad`, com banco recriado limpo.)_

**Módulo Fiscal / NF-e completo e na `main`** (suíte **650**, tudo mergeado+pushado; auditoria fiscal 100% endereçada):
Fase 5 (etapa 15) · **multi-CNPJ** (Emitente 1ª classe, DocumentoFiscal) · **destinatário 3 tipos**
(contribuinte/isento/não-contribuinte) · **painel de config → Emitente** (US-36) · **UI do Perfil de Emissão**
(US-37: painel Fiscal da rede + política produto/serviço → self|central em 2 níveis) · **NFS-e de serviço**
(US-38: emite montagem via `/v2/nfse`, valor manual, no painel da etapa 15 — **faturamento produto+serviço
completo**). Tudo **mergeado na `main`** (US-36/37/38).
**🎉 SMOKE REAL AUTORIZADO** — NF-e de **produto** da INSPIRIUM emitida pela SEFAZ.
**🎉 SMOKE NFS-e AUTORIZADO (2026-07-07)** — a INSPIRIUM emitiu NFS-e **autorizada** por São José dos Campos
(homologação): nº 1, cód. verificação `LWWCfsDUg`, XML + DANFSE gerados (`homol-notajoseense.sjc.sp.gov.br`).
O smoke foi na camada do emissor com **ref único** (RPS rejeitado é morto → emite-se novo) e **sem gravar
DocumentoFiscal**. Sequência de correções descoberta (cada uma destravou o próximo motivo de rejeição):
> 1. **E70** (Inscrição Municipal ausente) → **DADO**: preenchido no Emitente (IM `322176`, cód. serviço
>    `14.13.03`, município IBGE `3549904`, CNAE `4330404`, ISS 5%). ✅
> 2. **E188** (Simples Nacional conflita com Regime Especial de Tributação) → **CÓDIGO**: o payload NFS-e
>    precisa enviar, no topo, `optante_simples_nacional` (derivado de `emitente.regime_tributario=='simples'`),
>    `regime_especial_tributacao="6"` (ME/EPP do Simples) e `natureza_operacao="1"`. **Hoje `montar_payload_nfse`
>    NÃO envia** → o endpoint real ainda cairia aqui.
> 3. **L999** ("Tomador Não Identificado para a atividade") → **CÓDIGO**: o tomador precisa de
>    `endereco.codigo_municipio` (IBGE). Isolado: o `codigo_municipio` **sozinho** resolve (CEP inválido é
>    tolerado). **Hoje `montar_payload_nfse` NÃO envia** o IBGE do tomador — e o **Cliente não tem `municipio_ibge`**
>    (só cidade/UF): falta origem do dado (resolver por cidade/UF ou novo campo).
>
> ### ✅ US-39 — payload NFS-e completo — IMPLEMENTADO (2026-07-07, branch `feat/nfse-payload-us39`, suíte 632)
> `mapa_fiscal.montar_payload_nfse` agora envia, no topo, `optante_simples_nacional` (derivado de
> `emitente.regime_tributario=='simples'`), `regime_especial_tributacao="6"` (ME/EPP do Simples; só quando optante)
> e `natureza_operacao="1"`; e `codigo_municipio` (IBGE) no `tomador.endereco`. Novo campo `Cliente.municipio_ibge`
> (migração idempotente), capturado via **ViaCEP** no modal (o ViaCEP devolve `ibge`) + **backfill best-effort**
> por CEP na emissão (`_ibge_por_cep`, offline-safe) para clientes antigos. **Smoke pelo caminho real de código →
> NFS-e AUTORIZADA** por SJC. RET=6/natureza=1 são defaults documentados (MEI seria 5; refinar quando o Emitente
> distinguir). **Pendente:** merge + re-ingerir MCP.

Pendências fiscais: re-smoke via **endpoint da etapa 15** (server+login, com um projeto de serviço) — o caminho de
código já foi provado · refinamentos (CSOSN por operação; não-contribuinte PJ; RET MEI=5) · **dados reais** (CPFs/CEPs
válidos dos clientes; muitos hoje são placeholder → sem IBGE resolvível) · verificação manual dos painéis.

**Validação de CPF/CNPJ (Sessão 50, na `main`, suíte 624):** todos os cadastros
(Cliente/Parceiro/Usuário/Rede/Loja) **rejeitam número falso** (dígito verificador) no backend + inline no
modal de cliente; documento segue **opcional** (valida só se informado). Mergeado + MCP re-ingerido.

**Avaliação + Auditoria fiscal (2026-07-07):** docs em `docs/avaliacao/` — revisão por frente (02-07/07),
mapa de testes para leigo (22 testes de tela) e **auditoria adversarial do módulo fiscal** (14 achados).
Veredito: isolamento multi-tenant e segredos sólidos; riscos em chave local, beco-sem-saída da NFS-e e
hardcodes fiscais. **🔴 Altos corrigidos** (branch `feat/fiscal-altos-auditoria`, suíte 641): **A1**
(.gitignore da chave Fernet), **US-42** (`prontidao_emitente`: barra produto fora do Simples / UF vazia e NFS-e
sem IM/IBGE/cód-serviço/alíquota — A2/A3/A5), **US-41** (NFS-e rejeitada re-emite com ref por tentativa — A4).
**🟠 Médios corrigidos** (branch `feat/fiscal-medios-auditoria`, suíte 648): **A6** (config da rede exige
`pode_editar_dados_rede`), **A7** (justificativa NFS-e 15-255 no backend), **A9** (atomicidade: autorização
persiste antes de baixar XML/DANFE — `consultar` rebaixa), **A10** (RET MEI=5/ME-EPP=6), **A11** (backfill IBGE
alinha cidade/UF). A8 mitigado.
**🟡 Baixos corrigidos** (branch `feat/fiscal-baixos-auditoria`, suíte 650): **A12** (unicidade do PerfilEmissao —
constraint + índice + dedup), **A13** (2º clique concorrente → idempotente, não 500), **A14** (NFS-e autorizada
conclui a etapa 15). **✅ Auditoria fiscal 100% endereçada.** Ver `docs/avaliacao/2026-07-07-auditoria-fiscal.md`.

**Modularização — Fase 1 (fundação) implementada (2026-07-07, branch `feat/modularizacao-fase1`, suíte 670):** o
mapa lógico de `docs/ARQUITETURA-MODULOS.md` virou **executável e imposto**, sem mover código. **`modulos.py`**
(manifesto: camada/arquivos/tabelas/rotas/depende_de/desligável por módulo); **`tests/test_arquitetura_modulos.py`**
impõe a fronteira via `ast` (Núcleo não importa domínio; domínio só o que declara; tudo classificado) — **nasceu
verde** (acoplamento real já respeita a arquitetura) e foi **provado não-vacuoso** (4 mutações A/B/C/D falham como
esperado); **`mod_ciclo.faixa_da_etapa`** (titularidade do ciclo explícita); **`Loja.modulos_ativos` +
`mod_tenancy.modulo_ativo`** + endpoints `/api/admin/lojas/<id>/modulos` + guard no dispatch (piloto no fiscal
etapa 15) — liga/desliga domínio por loja, **default tudo-ligado** (zero mudança de comportamento). Subagent-driven,
6 tasks, cada uma revisada (spec+qualidade). Plano: `docs/superpowers/plans/2026-07-07-modularizacao-fase1.md`.

**Modularização — Painel + Menu reativo (2026-07-08, branch `feat/painel-modulos`, suíte 676):** deu **cara
visível** à Fase 1. `modulos.py` ganhou rótulos/ordem + `topologia_valida` (fecho de dependência); `GET
/api/admin/lojas/<id>/modulos` devolve os domínios com rótulo/ativo/deps e o `POST` rejeita topologia quebrada
(ex.: Comercial sem Cadastro → 400); `/api/auth/me` expõe `modulos_ativos` da loja do usuário; **painel "Módulos"**
no Admin da loja (checkboxes liga/desliga, aviso de dependência) + **menu reativo** (esconde Clientes/Parceiros se
Cadastro off; esconde abas Fiscal/Financeiro conforme o módulo na loja administrada). Default **tudo-ligado** em
todos os caminhos (revisado: nunca esconde por ausência/erro de rede). Frontend sem teste JS → verificado por
balanço + revisão. **Nota honesta:** domínios sem tela (Comercial/Produção/Estoque/Pós-venda/Expedição) têm toggle
mas reagem só no backend. Plano: `docs/superpowers/plans/2026-07-08-painel-modulos-menu-reativo.md`.

**Modularização — Hub de módulos (aterrissagem) + Credenciais no Admin (2026-07-08, branch `feat/hub-modulos`,
suíte 680):** a aterrissagem do usuário operacional deixou de abrir na lista de Projetos e virou um **hub de
módulos** — cards agrupados por **faixa de titularidade do ciclo** (Vendas · Execução do Projeto · Logística/
Expedição *(Fiscal aqui)* · Pós-venda/Montagem · Financeiro transversal), consistente com `mod_ciclo.FAIXA_POR_ETAPA`.
`modulos.py` ganhou `faixa` por domínio + `hub_layout()`; `/api/auth/me` inclui `usuario["hub"]`. Só **Comercial→
Projetos** e **Cadastro→Clientes** navegam; o resto é card **"em breve"** (honesto). **Credenciais** saiu do menu
lateral e virou **"Credenciais e Tokens" dentro do Admin (Plataforma)**, **só super_admin** — a seção **não é
renderizada** (não é cadeado) para os demais; **Diretor deixou de ver**. Subagent-driven, 5 tasks, revisão
frontend combinada aprovada (sintaxe + invisibilidade real + refs limpas). Plano:
`docs/superpowers/plans/2026-07-08-hub-modulos-credenciais.md`.

**Navegação Orizon v1 — Cadastro em abas + sidebar (2026-07-08, branch `feat/nav-cadastro-sidebar`, suíte 680):**
aplicadas as ações imediatas dos docs de spec oficial (`docs/design/navegacao-orizon-v1.md` + `padrao-design-orizon-v2.md`).
**Clientes e Parceiros saíram da sidebar** e viraram **abas do módulo Cadastro** (`page-10`: Clientes/Fornecedores/
Parceiros/Funcionários/Terceiros — 3 stubs "em breve"); o conteúdo foi **movido preservando os IDs internos**
(`cli-*`/`par-*`), então renders/modais seguem intactos; `goPage` ajustado para `n≥10` (senão `page-010`). **Sidebar
em 3 seções:** Módulos (topo→Hub) · **Atalhos** (Projetos, divisor, máx. 2) · Admin (último). **Faixa do hub
confirmada autoritativa** (5 grupos, Fiscal na Logística) — versão simplificada do design v2 superada. Specs
versionadas em `docs/design/`; **backlog de migração de design** (tema claro/escuro, tinta laranja legada, fonte
única, tokenizar status) em `docs/design/backlog-migracao-design.md` — **paralelo, não bloqueia**. Subagent-driven,
3 tasks, revisão frontend combinada aprovada (`node --check` OK). Plano:
`docs/superpowers/plans/2026-07-08-navegacao-cadastro-abas-sidebar.md`.

**Aba Parceiros na página Projetos + rename "Financeiro"→"Provisões" (2026-07-08, suíte 681):**
(a) a página Projetos ganhou uma **3ª aba "Parceiros"** (ao lado de Projetos|Clientes) — lista os parceiros da loja e,
para cada um, os **projetos relacionados** (via `parceiro_id` de cada projeto; nomes clicáveis → `abrirProjeto`). Backend:
a lista `/projetos` passou a expor **`parceiro_nome`** (enricher `_enriquecer_projetos_com_parceiro`, resolve do
`parceiro_id`). Rota real da lista é **`/projetos`** (não `/api/projetos`). Branch `feat/aba-parceiros`, subagent-driven.
(b) a sub-aba **"Financeiro" do Admin da loja** foi renomeada para **"Provisões"** (edita %s de provisão/custo-padrão =
domínio Financeiro; evita confusão com o módulo Financeiro do hub). Gate por `financeiro` mantido (correto); destino
final = dentro do módulo Financeiro quando tiver tela (registrado no `ARQUITETURA-MODULOS.md` §6).

**Alinhamento front-end — passo 1: escopo do Admin (2026-07-08, branch `feat/escopo-admin`, suíte 681):** correção
estrutural derivada dos docs de spec (`docs/design/`). O **Admin é Núcleo** (administra conta/loja, não domínios).
As abas **Projetos, Fiscal e Provisões saíram do Admin** (não tinham respaldo em doc — escolha fora do alinhamento);
**Admin da loja = Dados · Usuários · Módulos**; **Credenciais e Tokens** fica na Plataforma (super_admin). Para não
orfanar a config, os cards **Fiscal** (Emitente/NF-e) e **Financeiro** (Provisões/custos) do **Hub deixaram de ser
"em breve"** e abrem esses painéis (pages 11/12), reaproveitando `adminFiscalCarregar`/`adminFinanceiroCarregar` para
a loja do próprio usuário, gateados por `pode_editar_dados_loja` **dentro do módulo** (evita o erro de fronteira da
Expedição). Frontend puro (`node --check` OK), backend intocado. **Próximos passos do alinhamento:** (2) migração
visual (doc 3 §5, itens 1–7 — tema claro/escuro petróleo/dourado, aposentar tinta laranja legada, etc.); (3)
templates de diagramação (doc 4 Parte 1) conforme as telas forem tocadas. `Modulos_Orizon.docx` ainda não está no repo.
**Pendente:** passos 2 e 3 do alinhamento · **Fase 2** (extração física piloto = Fiscal) e domínios novos.

**Alinhamento front-end — passo 2, itens 1-2: paleta claro/escuro + fim da tinta laranja (2026-07-08, branch
`feat/design-paleta`, suíte 681):** migração visual mais transversal, feita primeiro. **Item 1** — o `:root` do
`static/index.html` deixou o dark-terminal verde-menta e passou aos **tokens claro/escuro do
`Padrao_Design_Orizon_v2.docx`** (accent **petróleo** `#4FA89E` escuro / `#1F4B4B` claro; **dourado** como accent
secundário de marca). Tema **dual**: padrão = escuro; `:root[data-theme="light"]` já definido, aguardando o toggle
(item 7). Estratégia de **aliases** — os nomes antigos (`--card→--surface-2`, `--ok→--accent`, `--dalm-gold→--gold`,
`--border2→--border-strong`, `--section→--info`, `--sb-bg→--surface`) apontam para os novos, então as ~250 referências
`var(--…)` herdam a paleta **sem editar cada linha**. A auditoria de tokens pegou dois **indefinidos pré-existentes**
usados por inputs de modais: `--fg` (herdava o texto, ok) e `--input` (caía no fallback `#0d1a0d` **verde** → destoaria
da superfície petróleo) — resolvidos com `--fg:var(--text)` e `--input:var(--surface)`. **Item 2** — as **8 ocorrências**
da tinta laranja legada `rgba(232,97,26,…)` (hover/ativo do menu, hover de card/linha/drop-zone, card destacado) foram
trocadas por `var(--accent-tint)` (fundos) / `var(--accent)` (borda) → grep = 0. Frontend puro (backend intocado, suíte
681); **sem teste visual → conferência no navegador (Ctrl+F5) fica com o usuário**. Cores hardcoded remanescentes
(status `#f05a50`… e cartões teal/amber/coral) **persistem de propósito** (itens 4/futuro). Plano:
`docs/superpowers/plans/2026-07-08-migracao-design-itens-1-2.md`; checklist derivado (fonte = `.docx`):
`docs/design/backlog-migracao-design.md` (itens 1-2 = ✅). **Pendente do passo 2:** itens 3 (unificar `login.html`),
4 (tokenizar status), 5 (`btn-primary` sem `.btn`), 6 (tipografia única + mono só em números), 7 (toggle persistido).

**Alinhamento front-end — passo 2, item 3: unificar `login.html` (2026-07-08, branch `feat/design-login`, suíte 681):**
o `login.html` tinha `:root` próprio verde-menta (`--bg #0d160d`, `--card #111d11`, `--accent #9FE1CB`, `--input-bg
#0a120a`) + hardcodes (`#0d160d` no botão/spinner, `rgba(224,92,92,…)` no erro). Como é **página standalone**
(servida antes do app → **não** herda o `<style>` do `index.html`), os tokens do **tema escuro do app** foram
**replicados inline** (`--bg #171B1C`, `--card #20262A`, `--border #2C3335`, `--accent #4FA89E` petróleo, `--text
#EDEFEE`, `--muted #8C979A`, `--err #E2876C`, `--input-bg #1D2224`) e os hardcodes trocados por `var(--…)`. Só CSS
mudou (JS intocado, confirmado por diff); backend intocado (suíte 681). **Fonte Epilogue mantida** (troca p/ Inter =
item 6). **Achado sinalizado (fora de escopo):** a logo do login ainda diz **"Promob → Omie"** (Omie foi aposentado;
produto é Orizon Manager) — correção de copy aguardando decisão do usuário. **Pendente do passo 2:** itens 4-7.

**Alinhamento front-end — passo 2, item 4: tokenizar cores de status (2026-07-08, branch `feat/design-status`, suíte
681):** os hexes hardcoded dos badges de status (`#f05a50` quente, `#d4a017` morno, `#c8a84b` fechado) foram trocados
por `var(--st-*)` nos **6 badges** (`.proj-status-badge.quente/morno/frio/convertido/fechado/perdido`) **e** no **JS do
botão** (`negAtualizarStatusBtn`, ternário de cor). Também normalizados `frio`/`convertido`/`perdido`, que liam dos
aliases antigos (`--section`/`--ok`/`--muted`), para o token semântico `--st-*` (mesmo valor hoje, mas single-source e
segue o tema claro/escuro — os `--st-*` já existiam no `:root` desde o item 1). Fundos rgba dos badges (padrão uniforme)
e o `#c8a84b` **decorativo** (separador "→"/rótulo do valor do contrato ~L829/831 = dourado, não status) ficam fora do
item — este último é hardcode de **marca** (deveria virar `var(--dalm-gold)`), sinalizado p/ limpeza futura. Só
frontend (backend intocado, suíte 681); diff = troca de valores (ternário intacto). **Pendente do passo 2:** itens 5
(`btn-primary` sem `.btn`), 6 (tipografia única + mono só em números), 7 (toggle persistido).

**Alinhamento front-end — passo 2, item 5: `btn-primary` sem `.btn` (2026-07-08, branch `feat/design-btn`, suíte
681):** `.btn` dá a base (padding/fonte/display) e `.btn-primary/-ghost/-danger` só trocam cor → quem tiver só o
modificador perde padding/fonte. Varredura (estáticos + dinâmicos: aspas simples, template literals, `classList`)
achou **um** infrator: o botão **"+ Novo Cliente"** (`cli-busca-home`), corrigido `class="btn-primary"` →
`class="btn btn-primary"`. Todos os demais já tinham a base (incl. o ternário `btn btn-sm ${ativo?'btn-primary':
'btn-ghost'}`). Uma linha de HTML; backend intocado (suíte 681). **Pendente do passo 2:** itens 6 (tipografia única +
mono só em números), 7 (toggle persistido).

**Alinhamento front-end — passo 2, item 6: tipografia única Inter + mono só em números (2026-07-08, branch
`feat/design-tipografia`, suíte 681):** o estado estava **invertido** vs. a spec — o `body` (`index.html:46`) usava
**`IBM Plex Mono` como default** (corpo/inputs/labels/tabelas herdavam mono) e a **Epilogue** era aplicada
explicitamente ao display (títulos/nav/botões, 65×). Migração (subagent-driven, 2 tasks + docs): fontes **tokenizadas**
no `:root` (`--font-sans:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif` e
`--font-mono:'IBM Plex Mono',ui-monospace,…`); **`body` virou `var(--font-sans)`**; as **65** `font-family:'Epilogue',
sans-serif` → `var(--font-sans)` (pesos/tamanhos intocados → hierarquia preservada); as **40** declarações mono de
valor/`<td>` → `var(--font-mono)`. Link do Google Fonts trocou **Epilogue→Inter** (mantém IBM Plex Mono 400/500 e
carrega Inter 400/500/600/700/900). **`login.html`** (standalone, não herda o `:root`): `@import` e as 3
`font-family` → **Inter** (stack literal). **"mono só em números" por construção:** auditoria confirmou que todo mono
explícito era numérico (13 campos `mp-a-*` + 9 `<td>` alinhadas à direita + demais spans de valor; **zero** em texto),
então virar o default para sans + preservar o mono explícito satisfaz a regra sem demoções. Contagens pós-migração:
Epilogue 0 (ambos arquivos), `var(--font-sans)` 66 (65+body), `var(--font-mono)` 40, `'IBM Plex Mono'` restante 1 (o
token). Só frontend (backend intocado, suíte 681); **sem teste visual → conferência no navegador com o usuário**.
**Achado de copy (re)sinalizado:** "Promob → Omie" está no **`<title>` do `index.html:6`** *e* na logo do `login.html`
(Omie aposentado; produto = Orizon Manager) — correção aguardando decisão. **Passo 2 quase completo — resta só o
item 7** (toggle de tema claro/escuro persistido por usuário).

**Alinhamento front-end — passo 2, item 7: toggle de tema persistido por usuário (2026-07-08, branch
`feat/design-toggle-tema`, suíte 687):** último item do passo 2 — e o único que **mexe em Python**. **Backend:** coluna
`Usuario.tema` (`'claro'|'escuro'`, default escuro, migração idempotente em `_migrar_colunas`); `tema` no
`auth._usuario_dict` (serializador único → chega ao front por login **e** `/api/auth/me`); função testável
`auth.set_tema(id, tema)`; **`POST /api/auth/preferencias`** (auth-scoped, valida 'claro'/'escuro'). **Frontend
(index.html):** `aplicarTema()` seta/remove `data-theme="light"` no `<html>` (a paleta clara já vinha do item 1),
aplicado no **boot** (após `_usuarioAtual = d.usuario`) e por um **toggle na sidebar** (rodapé, sol/lua); `alternarTema()`
inverte + grava via fetch. Persistência **por usuário no backend** (coluna), **não** localStorage/SO → acompanha o
usuário em qualquer máquina; custo aceito = "flash" curto de escuro antes do `/me` p/ quem usa claro. **Testes (suíte
681→687):** 3 unit (coluna/dict-default/`set_tema` válido-inválido-inexistente) + 3 HTTP end-to-end (endpoint
200+persistência, 400 inválido, 401 sem auth). Subagent-driven (backend TDD + frontend), revisado. **Mudança em Python
→ servidor precisa de restart** para valer localmente. **✅ PASSO 2 (migração visual) 100% CONCLUÍDO — itens 1 a 7.**
**Follow-ups de higiene (fora dos itens, aguardando decisão):** copy "Promob → Omie" (`<title>` do index + logo do
login); `#c8a84b` decorativo (~L829/831); e **hardcodes verdes** descobertos nesta frente — avatar `color:#0d160d`
(~L510) e `#modal-perfil` (`#111d11`/`#1e2e1e`, ~L527) — resíduos que o item 1 (aliases só no `:root`) não cobriu.
**Próximo do alinhamento = passo 3** (templates de diagramação, doc 4 Parte 1, conforme as telas forem tocadas).

**Passo 3 (diagramação) — 1ºs ajustes do hub + tema claro (2026-07-08, branch `feat/design-hub-ajustes`, suíte 687):**
guiado por observação do usuário sobre o hub no tema claro. **(1) Contraste** — `--muted` do **tema claro** escurecido
`#8A8880`→`#6B6860`: contraste vs. fundo subiu de **3.55/3.31:1 → 5.56/5.19:1** (passa WCAG **AA** 4.5:1; antes falhava,
sobretudo sobre `--surface`). Só o bloco `:root[data-theme="light"]` (dark intocado). **(2) "Abrir →" em `--accent`** —
nova regra `.hub-card:not(.soon) .hub-card-tag{color:var(--accent)}`: os cards ativos passam a mostrar "Abrir →" em
petróleo, distinto de "Em breve" (`--muted`, que competia visualmente). **(3) Distribuição do grid** — `.hub-cards`
passou de `minmax(200px,1fr)` (esticava) para **card fixo `280px` + `max-width:1280px`**: grupos com 1–2 cards (ex.
Financeiro) não espalham em telas largas; card quebra linha. Frontend puro (suíte 687). **Achado sobre a sidebar
(ponto reportado como "labels arroxeados"):** varredura exaustiva confirmou que **`.sb-nav-title` já usa `var(--muted)`**
e **não há nenhuma cor arroxeada hardcoded** no arquivo — não é resíduo não-migrado. O tom lavanda percebido é o próprio
`--muted` **escuro** `#8C979A` (cinza-frio) sob **contraste simultâneo** com o petróleo. Como já é o token correto, **não
houve mudança** (evitar no-op); se o tom ainda incomodar, opções = hard-refresh (cache) ou ajustar o token `--muted`
escuro levemente mais quente (afeta todo texto muted) — decisão do usuário.

**Passo 3 (diagramação) — sidebar/abas + projeto no cabeçalho (2026-07-08, branch `feat/design-sidebar-tabs`, suíte
687):** 3 ajustes estéticos guiados pelo usuário. **(a) Realce ativo mais leve** — `.nav-item.active` deixou de usar
`background:var(--accent-tint)` (o "botão" que no escuro puxava pro verde-petróleo e no claro era o único item com
fundo, destoando): agora é só `color:var(--text)` + `font-weight:700` + borda-esquerda fina `--accent`. Vale p/ todo
item ativo. **(b) Abas Projetos/Clientes/Parceiros sem dourado** — `.home-tab` usava `--dalm-gold`/`-light` (amarelo
que destoava): inativo → `--muted`, ativo → `--text` + sublinhado `--accent`, hover → `--text`; a borda do `#home-tabs`
dourada virou `--border`. O seletor passou a cobrir **`.ativo` E `.active`** → as abas do **Cadastro (page-10)**, que
não tinham realce ativo (usavam `.active`, sem regra), agora também destacam. **(c) Nome do projeto saiu da sidebar**
— removido o widget "Projeto ativo" do topo (a sidebar fica só navegação/acesso) e o **nome+cliente** foram para o
**cabeçalho da page-02 (Negociação)**, acima do título (novos `#proj-ctx-nome`/`#proj-ctx-cli`; o JS de `abrirProjeto`
e de criação de projeto passou a escrever neles — antes só a sidebar exibia o nome; o `.proj-header-nome` do CSS era
morto). Frontend puro (suíte 687; um e2e de NF-e piscou flaky e passou no re-run). **Pendências de higiene seguem**
(Promob→Omie, `#c8a84b`, hardcodes verdes do avatar/modal-perfil, e o `--muted` escuro se o tom ainda incomodar).

**Módulo Financeiro — sub-projeto #1: Plano de Contas (2026-07-09, branch `feat/financeiro-plano-contas`, suíte
687→699):** início da **camada contábil nova** (a spec `Especificacao_Financeiro_Orizon_v2.docx` é greenfield sobre o
financeiro atual, que era só provisões/custos). O módulo vai em **6 sub-projetos** (Plano de Contas → Livro de
Lançamentos → Motor evento→lançamento → DRE societário → DRE por projeto → Auditoria/Reconciliação); este é o #1.
**Entregue:** modelo **`Conta`** (árvore por `pai_id`, `owner_tipo/owner_id`, `codigo`, `grupo` 1–5, `tipo`
sintética/analítica, `natureza`, `ativa`); **`mod_contabil.py`** com `PLANO_PADRAO` (**99 contas**: grupos 1–5 +
subgrupos + 78 analíticas nível 3 do Pontta — tudo do `.docx` §2/§2.1), `resolver_owner` (loja→rede; loja avulsa =
própria), `seed_plano` idempotente (seed-on-first-access), `listar_contas` (árvore) e **CRUD** (`criar_conta` torna o
pai sintético; `editar_conta` nome+ordem; `remover_conta` = **apaga folha sem lançamento / inativa o resto** — regra
"inativar-não-apagar"; `_tem_lancamentos` é stub `False` até o #2); **API** `/api/financeiro/contas` (GET árvore /
POST criar / PUT editar / **POST /remover** — o dispatch não tem `do_DELETE`) com gate do módulo financeiro +
capability (`aprovar_financeiro` OU `editar_dados_loja`) e barra **cross-owner**; **UI** = aba **Plano de Contas** na
page-12 (árvore add/renomear/inativar), ao lado de **Provisões**. **Tenancy por owner** (rede compartilha; loja avulsa
tem a sua) — espelha o Emitente. Manifesto `modulos.py` atualizado (financeiro += `mod_contabil.py`/`conta`/rota) →
`test_arquitetura_modulos` verde. **Executado inline** (a infra de subagente deu 529), TDD, 8+4 testes novos.
**Cortes conscientes:** "mover conta" (reparent) fica p/ o #2; sinal de dedução na DRE = #4. **Restart do servidor**
para valer localmente. Spec/plano: `docs/superpowers/specs|plans/2026-07-09-plano-de-contas*`; **fonte de verdade do
plano de contas = o `.docx`**. **Próximo:** #2 Livro de Lançamentos (introduz `projeto_id` e ativa `_tem_lancamentos`).

**Módulo Financeiro — sub-projeto #2: Livro de Lançamentos (2026-07-09, branch `feat/financeiro-lancamentos`, suíte
699→707):** modelo **`Lancamento`** (partida dobrada: `conta_debito_id`/`conta_credito_id`, `valor`, `data` de
competência, **`projeto_id`** = nome_safe da dimensão gerencial, `origem`, `historico`) + motor em `mod_contabil`:
`lancar` (valida valor>0, contas distintas, **ambas analíticas ativas do mesmo owner**), `saldo_conta` (na natureza:
devedora D−C / credora C−D), `razao` (extrato com saldo corrido), `listar_lancamentos`; e **`_tem_lancamentos` agora é
real** → conta com lançamento **não apaga, inativa** (fecha a regra do #1). API: `POST /api/financeiro/lancamentos`,
`GET /api/financeiro/lancamentos?projeto=&ini=&fim=`, `GET /api/financeiro/contas/<id>/razao`. UI: **aba Lançamentos**
na page-12 (form débito/crédito/valor/projeto/histórico + lista). Manifesto += `lancamento`/rota. TDD (5 unit + 3 HTTP);
**app_db é module-scoped** → cada teste do livro usa contas distintas (isolamento). **Corte:** o motor evento→lançamento
que **popula** o livro é o #3; entrada manual existe via UI/API. **Próximo:** #3 (as 5 regras evento→lançamento).

**Módulo Financeiro — sub-projeto #3: Motor evento→lançamento (2026-07-09, branch `feat/financeiro-eventos`, suíte
707→714):** as **5 regras do `.docx` §5** viraram `mod_contabil.EVENTOS` + `registrar_evento(...)`: `fechamento_venda`
(D 5.6.01 Constituição de Provisão / C 2.1.04.03 Provisão de Garantia — segue o pareamento 5.6↔2.1.x do próprio plano),
`faturamento` (D 1.1.02 Contas a Receber / C 4.1.01 Receita), `recebimento` (D 1.1.01 Caixa / C 1.1.02),
`pagamento_comissao` (D 2.1.04.01 / C 1.1.01), `execucao_assistencia` (D 2.1.04.03 / C 1.1.01). Contas resolvidas por
**código** (estável: rename não muda código; reparent adiado); o evento gera lançamento com `origem=tipo` + `projeto_id`.
API: `POST /api/financeiro/eventos {tipo,valor,projeto_id,data?}`. TDD (5 unit + 2 HTTP). **Follow-up consciente:** o
**wiring nos fluxos vivos** (fechar contrato → `fechamento_venda`; NF-e emitida → `faturamento`; recebimento/comissão/
assistência) **não** foi feito — toca contrato/emissão e exige idempotência; o motor+endpoint estão prontos p/ plugar.
**Próximo:** #4 DRE societário (relatório do livro por competência).

**Módulo Financeiro — sub-projeto #4: DRE societário (2026-07-09, branch `feat/financeiro-dre`, suíte 714→718):**
`mod_contabil.dre(owner, ini, fim)` monta a DRE do `.docx` §3 a partir do livro por **competência**: Receita Bruta
(4.1+4.2) − Deduções (4.3) = Receita Líquida − CMV/CSP (5.1+5.2) = Lucro Bruto − Comerciais (5.3) − Administrativas
(5.4) − Constituição de Provisões (5.6) = EBITDA − Depreciação = EBIT ± Resultado Financeiro (5.5) = Resultado antes
de impostos − Impostos = Lucro Líquido. **Resolvido o corte de sinal do #1**: `_mov(prefixo, sentido)` computa cada
linha no sentido natural (receita = C−D; deduções/despesas = D−C, sempre positivas) e a estrutura aplica o sinal —
então **dedução reduz** a receita corretamente, independentemente da `natureza` cadastrada. Depreciação e Impostos = 0
(sem conta dedicada; Simples/DAS já em Deduções) — anotado p/ refinar com contador. API: `GET /api/financeiro/dre?
ini=&fim=`. UI: **aba DRE** na page-12 (demonstrativo formatado, subtotais destacados). TDD (3 unit + 1 HTTP; owner
distinto por teste pelo escopo de módulo). **Próximo:** #5 DRE por projeto (margem de contribuição via `projeto_id`).

**Módulo Financeiro — sub-projeto #5: DRE por projeto / margem de contribuição (2026-07-09, branch
`feat/financeiro-dre-projeto`, suíte 718→721):** `margem_projeto(owner, projeto_id, ...)` (do `.docx` §4) = receita
(4.1+4.2) − custo direto produto (5.1) − custo direto serviço (5.2) − comercial/comissão (5.3) − provisão de garantia
(5.6), tudo **filtrado por `projeto_id`** (a dimensão gerencial do #2). `_totais_conta`/`_mov` ganharam o filtro de
projeto (a DRE societária segue sem projeto = total). `projetos_com_lancamento` + `margem_todos_projetos` (ordenada por
margem desc). **NÃO aloca custo fixo** — isso é o rateio do #6 (a soma das margens ≠ Lucro Líquido, como o `.docx`
alerta). API: `GET /api/financeiro/projetos-dre?ini=&fim=`. UI: **aba Margem/Projeto** (tabela receita/custos/margem por
projeto). TDD (2 unit + 1 HTTP). **Próximo:** #6 Auditoria/Reconciliação (rateio de custo fixo → margem plena +
divergência residual).

**Módulo Financeiro — sub-projeto #6: Auditoria/Reconciliação (2026-07-09, branch `feat/financeiro-reconciliacao`,
suíte 721→726):** modelo **`PeriodoContabil`** (snapshot: inicio/fim/status/metodologia/resultado_societario/
soma_margem_plena/divergencia_residual/dados_json) + `mod_contabil.reconciliar(owner, ini, fim, metodologia)` (do
`.docx` §6): rateia a **despesa fixa do período (grupo 5.4)** aos projetos por uma **base de vigência** —
`proporcional_receita` | `proporcional_custo_direto` | `linear_por_projeto` — gerando **margem plena** (full cost) =
margem de contribuição − rateio; e a **divergência residual** = resultado societário (DRE) − soma das margens plenas
(estrutural: itens não alocados a projeto + provisões não realizadas; tende a um piso, não a zero). `fechar_periodo`
persiste o snapshot; `listar_periodos`. API: `POST /api/financeiro/reconciliar` (preview), `POST /api/financeiro/
periodos` (fecha), `GET /api/financeiro/periodos`. UI: **aba Reconciliação** (base de rateio + tabela margem→rateio→
margem plena + soma/societário/divergência + fechar período). TDD (3 unit + 2 HTTP). **✅ MÓDULO FINANCEIRO COMPLETO —
sub-projetos 1 a 6** (Plano de Contas · Livro de Lançamentos · Motor evento→lançamento · DRE societário · DRE por
projeto · Auditoria/Reconciliação). **Follow-ups conscientes** (registrados ao longo): wiring dos eventos nos fluxos
vivos (contrato/NF-e), "mover conta" (reparent), Depreciação/Impostos com conta dedicada, e refino contábil/tributário
com contador antes de produção (aviso do `.docx`). Suíte 687→726 (+39 testes). **Fonte de verdade = o `.docx`.**

**Módulo Financeiro — wiring do motor de eventos nos fluxos vivos (2026-07-09, branch `feat/financeiro-wiring`,
suíte 726→730):** o motor evento→lançamento (#3) passou a ser **disparado automaticamente** pela emissão fiscal.
`Lancamento` ganhou coluna **`ref`** (idempotência; migração idempotente p/ DBs existentes) e `registrar_evento(ref=)`
ficou **idempotente** (mesmo `ref` não duplica; `lancamento_por_ref`). Helper `_fin_evento_seguro(loja_id, tipo, valor,
projeto_id, ref)` no `main.py` (SHELL): **sessão própria + fail-soft** (contabilidade NUNCA aborta a emissão; try/except
que só loga), resolve owner da loja, respeita o **gate do módulo financeiro**. Wirado o evento **`faturamento`** na
**NF-e de produto autorizada** (D Contas a Receber / C Receita, valor = venda do preview, `ref=fat:NFE-<proj>-<doc>`) e
na **NFS-e de serviço autorizada** (valor do serviço, `ref=fat:NFSE-<proj>-<n>`). **Arquitetura:** o wiring vai no
`main.py` (SHELL) porque `nfe_emissao` é domínio **fiscal** e não pode importar `mod_contabil` (financeiro) — fronteira.
Prova **end-to-end**: teste que emite NF-e produto (emissor fake) e confirma o lançamento de `faturamento` com o `ref`
esperado. TDD (3 unit + 1 e2e). **Follow-ups conscientes (ainda não wirados — sem gatilho/valor claro no app):**
`fechamento_venda` (na criação do contrato — falta definir o valor da provisão de garantia), `recebimento`,
`pagamento_comissao`, `execucao_assistencia` (não há fluxos de pagamento/pós-venda ainda) — entram por lançamento
manual / API de eventos por ora. Suíte **687→730** no módulo Financeiro inteiro.

**Módulo Financeiro — atualização v2→v5 (`Especificacao_Financeiro_Orizon_v5.docx` agora é a FONTE DE VERDADE).**
Front 4 — **três provisões distintas (v5 §5/§6, branch `feat/fin-v5-provisoes`, suíte 730):** o seed ganhou
`2.1.04.05 Provisão de Assistência Técnica` (e `2.1.04.03` "Garantia Técnica"→"Garantia"), e `5.6` passou a ter 3
filhos de constituição (`5.6.01` Garantia, `5.6.02` Montagem, `5.6.03` Assistência). **`seed_plano` virou backfill
idempotente** — planos já existentes (ex.: local/VPS) ganham as contas novas no próximo acesso, sem recriar. Os
**EVENTOS** foram reestruturados em 3 provisões **independentes**: abre `fechamento_venda_{montagem,assistencia,
garantia}` (D 5.6.x / C 2.1.04.x) e reverte `execucao_{montagem,assistencia,reparo_garantia}` (D 2.1.04.x / C Caixa) —
partida dobrada de duas pontas, sem conta de "Reserva" no Ativo (§6.1). `margem_projeto` (§5) agora subtrai
produto(5.1) + as 3 provisões(5.6.x) + comissão(5.3); **Garantia entra pelo valor bruto** (repasse à fábrica é
controle à parte, §6.2). Códigos **estáveis** (rename não muda código) → não quebra lançamentos existentes. UI
Margem/Projeto atualizada. Testes de evento/DRE/margem migrados. **Follow-up:** o **painel de provisões DA VENDA**
(as 3 linhas por venda desde o fechamento) e o **wiring `fechamento_venda_*` na criação do contrato** exigem a fonte
dos valores (negociação) — próximo passo da integração.
Front 2 — **Balanço Patrimonial (v5 §4, branch `feat/fin-v5-balanco`, suíte 730→732):** `balanco(owner, data_corte)`
= saldo **acumulado** (do início até a data) dos grupos 1/2/3; o **resultado do exercício** (Receitas−Despesas
acumuladas) entra no PL → **fecha por partida dobrada** (`Ativo = Passivo + PL`, flag `confere`). Diferente do DRE (é
posição num instante, não fluxo). API `GET /api/financeiro/balanco?data=`; **aba Balanço** na page-12. TDD (2 unit).

> **⚠ Incidente (2026-07-06) — servidor obsoleto:** durante a conferência manual, o painel Fiscal "não
> persistia" — causa: o `main.py` na 8765 era um processo de **ontem** (pré US-36/37/38; rotas novas davam
> 404). **Fix:** matar os `main.py` presos e subir fresco (`pythoncore-3.14-64\python.exe main.py`). **SOP:
> toda mudança em Python exige reiniciar o servidor** (o `main.py` é lido só no start; o `index.html` é lido
> do disco a cada request).

### 🧾 Módulo Fiscal / Integração NF-e (Fábrica→Loja via Focus NFe) — mapa e continuação (Sessão 47)

**Objetivo:** a fábrica entrega direto ao cliente; a loja emite **sua** NF-e (com markup) via **Focus NFe**
(a Focus **não** calcula imposto — nós montamos o bloco fiscal). Pipeline em código, ponta a ponta (offline):
`mod_nfe.preview` → `mapa_fiscal` → `EmissorFocusNfe` → `focus_client`, com `PerfilFiscal` alimentando o mapa.

| Fase / peça | O quê | Estado |
|---|---|---|
| **Fase 1** | `mod_nfe.py` — parser XML fábrica + consolidação + markup (`preview`) + CLI | ✅ na `main`, testado |
| **Fase 2** | `emissor_fiscal.py` (contrato `EmissorFiscal`/DTOs) + `focus_client.py` + `focus_config.py` | ✅ na `main`, testado |
| **Painel Fiscal I** | `PerfilFiscal` (tabela) + `fiscal_cripto` (Fernet) + `mod_fiscal` + endpoints GET/PUT (config/segredos/ambiente) | ✅ na `main`, testado |
| **Painel Fiscal II** | Aba **Fiscal** no admin da loja (frontend) — 7 seções, badges de placeholder, segredos write-only, troca de ambiente | ✅ na `main` — **⚠️ verificação manual no navegador PENDENTE** |
| **Fase 3b** | `mapa_fiscal.py` (nota→payload Focus) + `emissor_focus.py` (`EmissorFocusNfe`) | ✅ na `main`, testado (offline) |
| **Fase 4** | `NfeEmissao` (rastreio por `ref`) + `nfe_emissao.py` (`emitir`/`consultar`/`cancelar`: emite→polling→baixa XML/DANFE→guarda; idempotente; **recusa produção**) + endpoint `POST …/nfe/emitir-teste` | ✅ na `main`, testado (offline) — **⚠️ smoke real em homologação PENDENTE do token** |
| **Fase 5** | Orquestração por projeto na **etapa 15**: upload da NF-e da fábrica → `preview(markup)` → `montar_nota` → `nfe_emissao.emitir` (`ref` estável `NFE-<projeto>-<doc_id>`, idempotente, conclui a etapa em `emitida`) + consultar/cancelar (cancelar **reverte** a etapa) + **painel da etapa 15**. Coluna `NfeEmissao.fabrica_doc_id`; regra do nome SEFAZ do destinatário em homologação centralizada no `nfe_emissao.emitir` | ✅ branch `feat/nfe-etapa15`, e2e (emissor mockado) — **⚠️ smoke real + verificação manual do painel PENDENTES** |

**Smoke em homologação (2026-07-06):** **token validado** ✅ (autentica; consulta de `ref` inexistente →
404 "Nota fiscal não encontrada"). **Emissão real testada** com um XML real da fábrica (NFe-170942,
markup 30% → 12 produtos, custo 730,89/venda 950,16): o **payload foi aceito estruturalmente** (a Focus
NÃO rejeitou campo nenhum → `preview→mapa_fiscal→payload→transporte` validado ponta a ponta) e parou num
erro **de negócio**: **"Empresa ainda não habilitada para emissão de NFe, por favor contate o suporte
técnico."** → o pipeline está correto; falta o **cadastro/habilitação do CNPJ 19.152.134/0001-56 na
Focus** (empresa + certificado A1 + liberação pelo suporte). Nada de código muda até lá.

**🎉 SMOKE REAL AUTORIZADO (2026-07-06) — NF-e emitida em homologação, ponta a ponta.**
Após o merge multi-CNPJ + o certificado A1 na Focus, o smoke rodou pelo **trilho novo (Emitente)** e
**autorizou**: `status=AUTORIZADO`, `sefaz="Autorizado o uso da NF-e"`, chave
`NFe35260719152134000156550010000000011051879962` (CNPJ INSPIRIUM na chave → emitiu sob o self-emitente),
XML+DANFE baixados (`DocumentoFiscal` xml_doc/danfe_doc). Toda a integração (Fases 1-5 + multi-CNPJ) validada
contra a SEFAZ real. O smoke descobriu e destravou:
- **2 bugs de código (corrigidos + testados, commit `b443c0a`):** `modalidade_frete` obrigatório (estava
  ausente → "Modalidade frete não pode ser vazio"); **CPF/CNPJ/CEP só com dígitos** no payload (`_so_digitos`
  no `montar_nota` — SEFAZ rejeitava "CPF inválido" com pontuação).
- **2 achados de DADO (não código):** (a) **CSOSN 101 → 102** — venda a consumidor final (não contribuinte)
  exige CSOSN **102** (sem crédito); ajustado no `Emitente` da INSPIRIUM. *(Ideal: CSOSN por tipo de
  destinatário contribuinte×não-contribuinte — refinamento fiscal, contador; registrar.)* (b) o cliente 2
  (Marcelo) tem **CPF placeholder inválido** (`012.021.345-01`) — para emissão real precisa do CPF real (o
  smoke usou um CPF de teste válido).
- **✅ Refinamento do destinatário IMPLEMENTADO** (branch `feat/fiscal-destinatario-contribuinte`, suíte 562):
  Cliente ganha **tipo (Contribuinte/Isento/Não contribuinte)** + CNPJ + IE; cadastro com seletor condicional;
  contrato exige CPF ou CNPJ conforme o tipo (IE não bloqueia); **IE pedida na emissão e persistida no Cliente**;
  `mapa_fiscal` ramifica **indicador IE (1/2/9)**, envio de IE, **CSOSN** (default no código 101/102 + override no
  Emitente `csosn_contribuinte`) e `consumidor_final`. Resolve o achado (a) acima. *(Pendente: CSOSN por operação
  ST/devolução; não-contribuinte PJ — fora do escopo.)*
- **Emitente da INSPIRIUM completo** no `orizon.db`: endereço (Av. Barão do Rio Branco, 736, São José dos
  Campos/SP, CEP 12242-800), IE 645636985117, IBGE 3549904, CSOSN 102, token homolog. *(bairro do emitente
  ficou vazio e a SEFAZ aceitou — usa o cadastro da empresa; preencher por higiene.)*

**Smoke PREPARADO (2026-07-06) — runbook em `docs/RUNBOOK-smoke-nfe.md`** (dados locais em `orizon.db`,
gitignored — não vão pro repo):
- **`config/fiscal.key`** criada (chave Fernet estável; gitignored) — token salvo hoje decripta amanhã.
- **`PerfilFiscal` da loja 1 (INSPIRIUM, 19.152.134/0001-56)** provisionado: `ambiente_ativo=homologacao`,
  perfil-padrão (Simples, CSOSN 101, CFOP 5102/6102, ISS 5%, placeholders → **produção bloqueada**).
  **Token de homologação salvo (encriptado)** e **revalidado** via `focus_client_para_loja` (404 em `ref`
  inexistente = autentica).
- **Projeto-alvo do smoke: `Projeto_Teste_Neg`** (loja 1, cliente **Marcelo Buonocore Nunes** com CPF; ciclo
  concluído até a etapa 14 → **etapa 15 destravada**). **Dry-run offline OK** (perfil INSPIRIUM + cliente 2 +
  `NFe-170942.xml` → preview 12 itens/custo 730,89/venda 950,16 → `montar_nota` → `montar_payload` sem erro).
- **⚠️ GAP de dado (só o usuário tem):** a **loja INSPIRIUM está sem endereço** (Loja: logradouro/cidade/UF/CEP)
  e **sem IE** (perfil). `montar_nota` monta o emitente a partir daí → sem a **UF do emitente** o CFOP sai 6102
  (interestadual) e a Focus pode rejeitar campos do emitente quando habilitada. **Preencher** o endereço (painel
  de dados da loja) + IE/município IBGE (aba Fiscal) antes/durante o smoke. (Oferecido preencher se o usuário
  passar os valores.)

**Insumos do usuário (gatilham as próximas fases, não bloqueiam o que já existe):**
- **Habilitar o CNPJ na Focus** — cadastrar a empresa 19.152.134/0001-56, enviar o **certificado A1** e
  pedir liberação para emissão de NF-e (suporte Focus). É o bloqueio atual do smoke real. **Token já OK
  (homologação, autentica); confirmado que a empresa segue "não habilitada" pois o certificado A1 ainda
  NÃO foi enviado — o usuário fará isso amanhã (2026-07-07). Depois disso, rodar o smoke novamente.**
- **Valores fiscais reais do contador** (CST/CSOSN/CFOP/alíquotas) do CNPJ **19.152.134/0001-56 (Simples)** —
  entram como **dado** no `PerfilFiscal` (perfil-padrão de teste já destrava o desenvolvimento).
- **Nota homologação:** o destinatário vai com o nome SEFAZ "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO -
  SEM VALOR FISCAL" — **✅ implementado (Fase 5)**: `nfe_emissao.emitir` carimba automático quando
  `ambiente_ativo == "homologacao"`.

**Pendências/gaps conhecidos (ajustes pequenos, registrados):**
- **[teste]** conferência do **Painel Fiscal (Sub-frente II)** e do **painel da etapa 15** (Fase 5) no
  navegador — o usuário fará **amanhã**, junto do smoke real.
- **[Fase 5]** cancelar reverte a etapa 15 para `em_andamento` incondicionalmente — se houver **duas** NF-e
  autorizadas (append-only permite vários XMLs da fábrica no mesmo projeto), cancelar uma "desconclui" a
  etapa mesmo com a outra ainda válida. Caso de borda (fluxo típico = 1 nota); reavaliar se virar comum.
- **[GAP]** `cert_validade`/`cert_cnpj` são read-only no painel — o `PUT …/perfil-fiscal` (Sub-frente I) não
  os inclui na allowlist; torná-los editáveis é ~2 linhas no backend.
- **[Fase 4]** `mapa_fiscal`: PIS/COFINS CST "49" e o CSOSN são **do Simples** (marcado `# TODO Fase 4`) —
  ramificar por regime normal/presumido com o contador.
- **[Fase 4/5]** `custo_total`/`venda_total` do `preview` somam valores unitários **já arredondados** →
  pode divergir do total fiscal por centavos (reconciliar se comparar com a NF-e).

**Specs/planos:** `docs/superpowers/specs|plans/2026-07-05-nfe-*` e `…-perfil-fiscal-*` e `…-painel-fiscal-*`
(todos com Status **IMPLEMENTADO**, exceto o que resta das Fases 4-5). XMLs reais da fábrica em
`E:/2026/desenvolvimento/nfe-dalmobile` (fora do git).

Servidor: `python3 main.py` (porta 8765) — **atenção:
o `python3` do Bash aqui é o stub do WindowsApps (exit 127); subir com o interpretador real
`C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe main.py`, e sempre matar servidores
`main.py` obsoletos que fiquem presos na 8765 (senão o navegador fala com código velho).**
Branches: `main` + `worktree-agent-a3876ec2c1cd36c64` (worktree do harness, mantido).
Contrato agora é **HTML/Markdown → PDF (WeasyPrint)** — o caminho `.docx`/LibreOffice do contrato
foi aposentado (a **proposta** ainda usa docx/LibreOffice). **Diretório de trabalho:**
`E:/2026/desenvolvimento/orizon-manager` (pai renomeado nesta sessão). **MCP `orizon`** ativo e
ingerido; re-ingerir ao fechar frente (grafo re-ingerido após o merge da Sessão 45: código 920 nós,
banco 66 — inclui `CicloDocumento`/`CicloRevisao`). **[AMBIENTE — fix] `mcp-orizon/.env`:** o
`TARGET_PROJECT_PATH` ainda apontava para o path antigo `E:/2026/estudo_de_ia/omie_v3` (obsoleto desde
a renomeação da Sessão 44) — corrigido para `E:/2026/desenvolvimento/orizon-manager`. Sem isso o
container `mcp-orizon-api` monta diretório inexistente e a ingestão lê o projeto errado. Análogo ao fix
do `.mcp.json` na Sessão 44. (`.env` é gitignored → não vai pro repo; corrigir na máquina que rodar o
stack.) Para subir o stack quando o Docker Desktop está fechado: iniciar o Docker Desktop pela sessão do
usuário (`Start-Process` no PowerShell funciona; `cmd start` não pegou), aguardar `docker info`, então
`docker compose up -d` em `../mcp-orizon` e `POST http://localhost:8767/ingest/all`. **Produção (VPS 167.88.33.121:8765)** atualizada para
`ca05a61` (sessão 44) nesta sessão: `/root/orizon-manager`, banco `orizon.db`, remote novo, screen
`orizon-manager` (`ORIZON_HOST=0.0.0.0`), weasyprint 61.1, `/login` HTTP 200. **SSH por chave** já
configurado (deploy pode ser conduzido pelo agente). Pendências-baixa: conferir contrato PDF real em
prod (weasy 61 vs 69) e revisar chaves de terceiros no `authorized_keys` do root.

**Já na `main` (frentes recentes):** super_admin aterrissagem+árvore; acesso multi-loja; Frente C
(config financeira/provisões/margem real); provisões versionadas (Venda/Rev1/Rev2 + aprovação);
etapa Orçamento como hub + Imprimir Orçamento (proposta = 1º doc do banco #8). Fixes de contrato
(path PDF, staleness, tela cheia). E2E do início ao fim + geração real de contrato/assinatura.

**Status das specs:** atualizado o cabeçalho das specs implementadas+mergeadas (as 5 frentes recentes
+ multitenant F2/F3/F4). Specs anteriores a 24/06 não foram relabeladas (verificar caso a caso ao retomar).

**Pendências / próximos (backlog):**
1. **Banco de documentos da loja #8 (continuação):** ~~falta a lista "etapa → documento"~~ **RESOLVIDO
   (2026-07-06):** o `1.FLUXO_DE_PROCESSOS.docx` foi transcrito para `docs/referencia/01-fluxo-de-processos.md`
   (fonte editável do usuário; ver `docs/referencia/README.md`) — inclui a lista **etapa → documento (D1–D45)**.
   Ainda pendente: modelo de proposta/contrato **por loja** (Padrão/Personalizado).
2. **Conferência visual** dos 4 itens de UX do Imprimir Orçamento (botão/cards) no browser.
3. **Defers** (cosméticos): genericizar corpo do 500 da rota de proposta; remover `import _mprop` redundante.
4. **Seed Orizon (#6)**, **busca LGPD (#4)**, **config de rede (#7)**.
5. ~~**Não-pushed**~~ **OK (2026-07-06):** `main` sincronizada com `origin` (push funciona nesta máquina).
6. **EP-10 — Reconciliação do Ciclo (4 lacunas)** — do mapa 38 etapas ↔ ciclo (`docs/processos/FLUXO_38_ETAPAS.md`,
   canônico em `docs/referencia/01-fluxo-de-processos.md`; faixas em `docs/ARQUITETURA-MODULOS.md`). Registradas
   em `docs/historias/BACKLOG.md`: **US-32** NFS-e de montagem *(→ módulo Fiscal, o próximo item natural ao
   retomar o fechamento fiscal)*, **US-33** pós-entrega (follow-up/recompra), **US-34** posição da Aprovação
   Financeira (11d × Fase 3 — decisão de negócio), **US-35** marcos de Conferência/Transferência ao CD.

> **Nota (2026-07-04):** a antiga seção "🔼 PENDÊNCIA: PUSH" foi removida — o `git push origin main`
> funciona nesta máquina (Git Credential Manager do usuário). Remote:
> `https://github.com/mbnunes1972/orizon-manager.git`. Se algum dia falhar por credencial, peça ao
> usuário rodar `!git push origin main` no próprio shell.

Front 3 — **DRE Analítico×Resumido (v5 §3.1, branch `feat/fin-v5-dre-toggle`, suíte 732→733):** `dre()` passou a devolver `detalhe` (composição nível 3 por linha, só contas com movimento); UI ganhou toggle **Resumido** (padrão, nível 2) / **Analítico** (expande nível 3 sob cada linha). Sem dado novo. TDD (1 unit).

Front 4b — **Controle de Repasse à Fábrica (v5 §6.2, branch `feat/fin-v5-repasse`, suíte 733→736):** `Lancamento` ganhou `motivo` (‘defeito_fabrica’|‘outro’, migração idempotente) — dimensão do reparo em garantia, no padrão do projeto_id. `registrar_evento(motivo=)` propaga; `total_a_cobrar_fabrica()` soma os `execucao_reparo_garantia` marcados defeito de fábrica. API `GET /api/financeiro/repasse-fabrica`; aba **Repasse Fábrica** (total + registrar reparo com motivo). **Não** cria Contas a Receber (só fase 2, se a fábrica reembolsar). TDD (2 unit + 1 HTTP).

Front 4c — **IA de apoio à classificação (v5 §6.3, branch `feat/fin-v5-ia`, suíte 736→740):** `sugerir_conta(owner, texto)` — **heurística sem LLM externo**: sobreposição de tokens (sem acento) entre o texto e o nome da conta + histórico de lançamentos, **ponderada por IDF** (token raro como ‘aluguel’ pesa mais que comum como ‘loja’). API `POST /api/financeiro/sugerir-conta`; na aba Lançamentos, campo “descreva o evento” → pré-preenche o Débito. **Nunca lança sozinha** — funcionário confirma/troca; a **sugestão + a escolhida** ficam registradas em `Lancamento.ia_sugestao` (mesmo princípio de snapshot dos gates). Arquitetura plugável p/ LLM depois. TDD (3 unit + 1 HTTP). **✅ ATUALIZAÇÃO v2→v5 COMPLETA** — 5 fronts (selo de posição §2.3 · DRE Analítico×Resumido §3.1 · Balanço Patrimonial §4 · 3 provisões §5/§6 · Repasse à Fábrica §6.2 · IA §6.3). Suíte 730→740. **Follow-up:** painel de provisões DA VENDA + wiring `fechamento_venda_*` no contrato.

**Módulo Financeiro — v5→v6 + integração das Provisões da Venda (`Especificacao_Financeiro_Orizon_v6.docx` agora é a
FONTE DE VERDADE; branch `feat/fin-v6-provisoes-venda`, suíte 740→744):** a v6 = v5 + **§6.4** (origem do valor das
provisões = **percentual configurável**) e **§6.5** (conexão com o Gate I). Implementado: **config `provisoes_contabeis`
{montagem_pct, garantia_pct}** no painel de Provisões do Financeiro (default + validação 0–100; UI com 3 campos), e
**assistência HERDA `provisoes.assist_pct`** (não recria o dado). `mod_contabil.pcts_provisao_venda(cfg)` +
`constituir_provisoes_venda(...)` (valor = % × valor da venda; idempotente por ref; só constitui % > 0) — **wirada na
criação do contrato** (`_fin_provisoes_venda_seguro`, fail-soft/isolado, após `_registrar_provisao_venda`, valor =
`orc.valor_total`). **Fronteira preservada:** os % ficam no Financeiro, desacoplados do motor de preço do Comercial
(§6.4). **Painel de Provisões da venda:** `provisoes_da_venda(owner, projeto)` = as 3 provisões com **saldo em aberto**
(constituído − revertido = saldo credor da conta 2.1.04.x por projeto); API `GET /api/financeiro/provisoes-venda?
projeto=` + lookup na aba Margem/Projeto. TDD (4 unit). **§6.5 (Gate I):** os valores das 3 provisões já ficam
**queryáveis** (via `provisoes_da_venda`) para compor o snapshot do Gate I — as regras do gate não mudam (aprovação
humana, IA só apresenta, snapshot auditável); **surfacing na tela de revisão do gate = conexão a fazer** quando o Gate
I for tocado. **✅ v6 completa.**

**Reconstrução visual v4 (`Padrao_Design_Orizon_v4.docx` + imagens de referência regeradas são a FONTE DE VERDADE de front-end; substitui v2/v3):** frente puramente visual, sem impacto nas regras do Financeiro (v6). **Front A — tokens (§2):** `:root` recalibrado nos 2 temas (escuro menos "terminal": `--accent` #4FA89E→#5BB8AC, superfícies/borda/texto revisados; light borders); **`--shadow` novo** (profundidade por sombra, não borda). **Front B — botões (§4):** secundário (`.btn-ghost`) **sem borda** → `--surface-2` + `--shadow` (corrige o "terminal"); primário com sombra; **altura fixa** 28/36/44 (sm/md/lg), peso 500, transição 150ms. **Front C — navegação (§4, item 8, a mais visível):** as 8 seções do Financeiro saíram das **tabs no conteúdo** e viraram **submenu na sidebar** (`#sb-submodulo`, indentado sob "FINANCEIRO", renderizado por `finSubmenuRender`); o painel central mostra **só a seção selecionada**; título vira "Financeiro / <Seção>"; `finTab` reescrito (corrigiu bug: só 4 dos 8 painéis trocavam). Item ativo do nav = `--surface-2` + `--shadow` + `--accent` (não borda); ícone em anel ○. **Toggle de tema (item 7)** virou **controle segmentado** (Claro | Escuro) no rodapé, sem borda. **Contradição resolvida na v4:** seções principais **só na sidebar**; componente Tabs reservado a sub-navegação dentro de uma seção. Suíte 744 (frontend puro). **Próximo:** Dashboard do Financeiro (§5, cards de saldo/DRE/cobertura de caixa) + Diagramacao_v2 (Dashboard/Kanban/Negociação/Seletor de Status) conforme os módulos forem tocados.

**Dashboard do Financeiro (v4 §5 + Diagramacao_v2 §1.3, branch `feat/fin-dashboard`, suíte 744→746):** a seção **Provisões** virou o **dashboard do mockup** — `dashboard_financeiro(owner)` agrega o **saldo em aberto das 3 provisões** (Montagem/Assistência/Garantia, saldo credor das contas 2.1.04.x no nível owner) + **resumo do DRE** (receita líquida/EBITDA/lucro) + **indicador de cobertura de caixa** (Caixa 1.1.01 ÷ provisões em aberto — v6 §6.1, alerta se <1×). API `GET /api/financeiro/dashboard`; UI = cards com profundidade por `--shadow` (sem borda), + botão **"Configurar 
**Comercial — Kanban (funil de vendas, v4 §5 + Diagramacao_v2 §1.4, branch `feat/comercial-kanban`, suíte 746):** a aba Projetos ganhou um toggle **Lista | Funil**. O Funil renderiza o board Kanban do template §1.4: colunas fixas por status (Quente/Morno/Frio/Convertido/Fechado/Perdido, cada header com a cor do token `--st-*` + contador), cards com profundidade por `--shadow` (nome peso 500 + cliente muted), clique no card abre o projeto. **Mover é ação explícita** (menu 'mover ▾' no card → `projStatusSet` PATCH `/api/projetos/<nome>/status`), nunca automático — mesmo princípio dos gates. Frontend puro (reaproveita a lista `/projetos` + o endpoint de status existente; sem backend novo). **Follow-up:** drag-and-drop (hoje é por menu); Kanban da Expedição; submenu de sidebar para os demais módulos.

**Expedição — Kanban (pedidos por etapa, v4 §5 + Diagramacao_v2 §1.4, branch `feat/expedicao-kanban`, suíte 746→748):** nova tela **page-13** (Expedição/Logística) alcançada pelo card do Hub (`_HUB_DESTINO.expedicao`). Endpoint `GET /api/expedicao/kanban` (gate pelo módulo `expedicao`): agrupa os projetos da loja pela **etapa do ciclo em andamento** entre 12–16 (Implantação/Produção/Entrega no depósito/Emissão NF-e/Entrega no cliente) — usa a etapa mais avançada `em_andamento` de cada projeto. Board com cards de profundidade `--shadow` (nome_safe + cliente); clique abre o projeto (o avanço da etapa continua no fluxo do ciclo, com seus gates — não se move a etapa direto do Kanban). Manifesto: domínio `expedicao` += rota. **Gotcha corrigido:** `import mod_tenancy` dentro do handler tornava o nome local do `do_GET` inteiro (UnboundLocalError em 69 testes) — removido, pois já é import de módulo. TDD (2 HTTP). **Follow-up:** drag-and-drop; submenu de sidebar para Expedição (hoje só via Hub).

**Sidebar — ícones Tabler (fix visual):** os itens da sidebar renderizavam círculos genéricos (`::before`) herdados do PNG de referência. Trocado por **Tabler Icons webfont** (`@tabler/icons-webfont@3.31.0` via CDN, ao lado do Google Fonts): um ícone outline distinto por item — Módulos `ti-layout-grid`, Projetos `ti-diamond`, Admin `ti-settings`, Config `ti-adjustments`; submenu do Financeiro (`_FIN_SECOES` ganhou campo `ic`): Provisões `ti-shield-dollar`, Plano de Contas `ti-list-tree`, Lançamentos `ti-receipt`, DRE `ti-report-money`, Balanço `ti-scale`, Margem/Projeto `ti-chart-dots`, Reconciliação `ti-refresh`, Repasse Fábrica `ti-truck-delivery`. CSS: `.nav-item:has(>.ti)::before{display:none}` esconde o círculo onde há ícone (fallback preservado); o glifo herda `currentColor` → muted/accent como o resto. Sem emoji, stroke uniforme do webfont. Frontend puro (Ctrl+F5).

## Sessão 46 — Diagramação/Navegação v4 (2 correções)
**Correção 1 — Sidebar em acordeão (Diagramacao_v4 §2, suíte 748→749):** a sidebar deixou de mostrar só o módulo aberto. Novo `#sb-modulos` renderizado por `sbNavRender()` reusa `_usuarioAtual.hub` (mesmas faixas do Hub) e lista os módulos de domínio por faixa; `_SB_MODULOS` dá o ícone Tabler distinto de cada módulo/seção e as seções do submenu. Um só módulo expandido por vez (`_sbModuloAberto`); clicar num módulo com seções expande o acordeão e abre a 1ª seção, clicar noutro colapsa o anterior. Módulos-folha (Comercial→Projetos, Fiscal, Expedição) navegam direto; módulos sem tela (Produção/Estoque/Pós-venda) aparecem como 'em breve' (muted). Cadastro: seções (Clientes/Parceiros + stubs) migradas das abas do conteúdo para o submenu da sidebar (§2.5) e a barra de abas do page-10 foi ocultada (`#cad-tabs display:none`) p/ não duplicar navegação; `cadTab`/`finTab` passaram a sincronizar o acordeão. `goPage` chama `sbSyncActive(n)` (mapa `_PAGE_MODULO`) p/ realçar/expandir o módulo da página. Removido `finSubmenuRender`/`#sb-submodulo`.
**Correção 2 — Painel de Provisões data-driven (Diagramacao_v4 §1.3):** `mod_contabil.dashboard_financeiro` deixou de hardcodar as 3 provisões; agora enumera as contas ANALÍTICAS do grupo `2.1.04` que existirem no Plano de Contas (nome vem da conta), então criar uma provisão nova no plano faz surgir um card sem tocar na tela. Teste novo `test_dashboard_provisoes_data_driven`.
**Decisões/ambiguidades registradas (usuário pediu p/ documentar):**
- (C2) O doc diz 'um card por conta do grupo 2.1.x que existir' MAS também 'hoje são 3' — o PLANO_PADRAO tem 5 contas de provisão (inclui Comissão 2.1.04.01 e Devolução 2.1.04.04). Reconciliei enumerando o grupo e EXCLUINDO essas duas (`_PROV_PAINEL_EXCLUI`): Comissão é despesa de venda (baixa via pagamento_comissao), Devolução não tem evento/percentual hoje (saldo sempre 0). Assim 'hoje = 3' vale por exclusão explícita, e uma conta 2.1.04.06+ nova aparece sozinha. Descrição do card: mapa opcional `_PROV_PAINEL_SUB` com fallback genérico.
- (C1) 'os 8 módulos SEMPRE visíveis' vs tenancy (módulos desligáveis por loja): segui o Hub (`hub_layout`) e mostro os módulos ATIVOS agrupados por faixa — com tudo ligado (default) aparecem os 8. Prioriza consistência com o Hub e respeita o gating por loja.
- (C1) '§2.4 Remover Clientes e Parceiros da sidebar': no build atual eles NÃO estavam como itens de topo da sidebar; agora existem só como submenu de Cadastro (caminho único ao dado), cumprindo a intenção.
- (C1) Ordem do submenu de Cadastro: funcionais primeiro (Clientes, Parceiros) e depois os stubs (Fornecedores/Funcionários/Terceiros); o doc permite reordenar por frequência ('decisão de negócio').
- (C1) Projetos segue como único Atalho; na page-0 realço o Atalho (nav-00), não o módulo Comercial, p/ evitar realce duplicado do mesmo destino.

**Painel de Projetos — colunas Consultor e Especificador (lapidação):** a lista de projetos (`renderProjResultados`) ganhou duas colunas. **Consultor** = criador do projeto (`projetos_meta.criado_por_id`), resolvido no backend em `_enriquecer_projetos_com_status` (novo `consultor_id`/`consultor_nome` via `Usuario`). **Especificador** = 'Sim/Não' conforme houver parceiro cadastrado (`parceiro_nome`, já resolvido por `_enriquecer_projetos_com_parceiro`); no 'Sim' o nome do parceiro aparece no tooltip (atributo title). Teste e2e `test_lista_projetos_traz_consultor`.

**Projetos — consultor na criação + botão Editar (lapidação, suíte 750→755):** 
- **Criação:** o consultor responsável (`criado_por_id`) é o usuário logado por padrão. Gerente+ (níveis fora do escopo-próprio) veem um seletor `#novo-proj-consultor` (via `GET /api/projetos/consultores`, campo `pode_atribuir`) e podem indicar outro consultor da loja; o consultor cria sempre para si (seletor escondido e ignorado no backend). Enforcement em `/projetos/novo`.
- **Editar:** botão 'Editar' ao lado de 'Abrir' na lista abre modal `#modal-proj-editar` (Nome, Cliente, Parceiro/especificador, Consultor) pré-preenchido do `_projListaBase`; salva via `POST /api/projetos/<nome>/editar` enviando só os campos alterados. Regras: renomear altera só o rótulo (nome_safe/chave preservada); reatribuir consultor exige gerente+; Cliente e Parceiro travam após contrato totalmente assinado (mesmo princípio do endpoint de parceiro), Nome e Consultor seguem editáveis. Novo endpoint GET consultores + `_usuarios_atribuiveis_da_loja`/`_usuario_pertence_a_loja`. Testes: `test_projeto_editar_e2e.py` (5). 
**Decisões (confirmadas via AskUserQuestion):** consultor atribuível por gerente+ (consultor travado nele); Editar cobre Nome/Cliente/Parceiro/Consultor; pós-contrato trava Cliente e Parceiro. Nota: no form de criação o seletor do gerente vem pré-selecionado nele mesmo — ele troca para o consultor real.

## Sessão 47 — Revisão de módulos e navegação (Modulos_Orizon_v4)
**Manifesto (`modulos.py`):** renomeados os RÓTULOS (ids preservados) `producao`→'Projetos' e `expedicao`→'Expedição'. Removido o módulo `posvenda` (virou FAIXA, não módulo). Novos domínios stub `captacao` (faixa vendas), `montagem` e `assistencias` (faixa montagem). `DOMINIOS_ORDEM` atualizado (Captação primeiro; Montagem/Assistências ao fim). FAIXAS inalteradas. Testes ajustados em test_modulos.
**Navegação (frontend):** 
- **Hub removido** — page-08 repurposada como tela genérica **EM CONSTRUÇÃO** (`emConstrucao(rotulo)`); item 'Módulos' saiu da sidebar; `hubRender` não é mais chamado. Operacional aterrissa em **Projetos** (page-0).
- **Sidebar em lista PLANA** — `sbNavRender` achata `_usuarioAtual.hub` (sem cabeçalhos de faixa), todo módulo clicável. Módulo sem `go`/`secoes` → `sbModuloClick` mostra EM CONSTRUÇÃO (realce mantido via `sbSyncActive` no page-8). Ícones Tabler novos: captacao `target-arrow`, producao/Projetos `ruler-measure`, montagem `hammer`, assistencias `lifebuoy`.
- **Financeiro:** aba 'Repasse Fábrica' removida do submenu (`_FIN_SECOES`) — migra p/ Assistências (§6.2 v7). Endpoint/painel `repasse-fabrica` seguem existindo, só não são mais aba.
**Escopo desta passada = estrutural (módulos + navegação + stubs EM CONSTRUÇÃO), conforme o doc.** O **motor de lançamento de Assistências** (Especificacao_Financeiro v7 §6: casos motivo→custo Paga/Loja/Fábrica, venda no Comercial, Provisão Assist.Técnica/Garantia, relatório 'a cobrar da fábrica') fica como PRÓXIMA frente — depende do módulo Assistências (casos), hoje EM CONSTRUÇÃO. Nomenclatura das contas mantida (Assistência Técnica/Garantia; Loja/Fábrica é só mapeamento conceitual).

## Sessão 48 — Módulo Expedição: CicloLogistico + Kanban com painel de Detalhe (Modulos_Orizon_v5 §7 / Diagramacao_v5 §1.4)
O antigo Kanban (agrupava projetos por etapa do ciclo 12–16) foi substituído pela entidade dedicada **CicloLogistico** (`database.py`): status_atual (7 estágios: Pedido Enviado→Em Produção→Aguardando Recebimento→Recebido no Depósito→NFe Emitida→Em Trânsito→Entregue), prazos planejados + datas realizadas (4 pares), transporte (transportadora/CT-e/rastreio), referências por ID (projeto_nome, nfe_id) sem duplicar dado, e **CicloLogisticoTransicao** (histórico auditável quem/quando). `create_all` cria as tabelas.
**`mod_expedicao.py`** (novo módulo de domínio, registrado no manifesto): STATUS, mapeamentos REALIZADO_AO_ENTRAR (captura) e PRAZO_POR_STATUS (badge de atraso), `criar_ciclo`/`mover`/`atualizar_detalhe`/`card_kanban`/`card_detalhe`/`esta_atrasado`.
**Endpoints (main.py):** GET `/api/expedicao/kanban` (7 colunas por status + meta), GET `/api/expedicao/cards/<id>` (detalhe+histórico), POST `/api/expedicao/cards` (criar), POST `.../mover` (transição+captura), POST `.../<id>` (editar prazos/transporte). Gating por módulo + isolamento por loja.
**Frontend:** Kanban read-only (card = projeto/cliente + nº pedido + badge Atrasado; clique abre Detalhe). Painel de Detalhe (modal, template Detalhe/Formulário) com seções Identificação/Prazos/Transporte/Histórico; '+ Novo pedido' (projeto+nº+prazos). Regra de captura: ao trocar o status no seletor, os campos Realizado que ele captura são pré-preenchidos com hoje (editáveis) antes de 'Mover'. Planejado entra na criação. Testes: `test_expedicao.py` reescrito (7). Suíte 755→760.
**Decisões documentadas:** (a) card criado manualmente ('Novo pedido' pelo Assistente Logístico ao enviar o pedido à fábrica — é a única forma de gravar Planejado 'uma vez na criação'). (b) Como há 7 status e só 4 pares Planejado/Realizado, produção-concluída e saída-da-fábrica são capturadas juntas ao entrar em 'Aguardando Recebimento' (não há status próprio de saída); NFe Emitida e Em Trânsito não capturam prazo. Tudo editável no Detalhe. (c) 'Mover' altera só status+realizados; edições de prazo/transporte usam 'Salvar'.
**Nota:** o Diagramacao_v5 Parte 2 (Navegação) ainda descreve o modelo antigo (acordeão c/ faixas + Hub); como o usuário pediu 'navegação segue como estava' e esta frente é só Expedição, mantida a sidebar plana da Sessão 47. Frente futura: motor de lançamento de Assistências (Financeiro v7 §6).

## Sessão 49 — Módulo Assistências: motor de lançamento (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6)
Assistências deixou de ser EM CONSTRUÇÃO e ganhou o motor completo. **Duas dimensões independentes por caso:** sub_tipo (Assistência Montagem × Pós-Conclusão) e tipo_custo (Paga/Loja/Fábrica) DERIVADO do motivo (tabela dos 6 motivos). Modelo `AssistenciaCaso` (`database.py`); `create_all` cria a tabela.
**`mod_assistencias.py`** (novo domínio, depende_de += financeiro): MOTIVOS→tipo_custo, SUB_TIPOS, EVENTO_POR_CUSTO, `criar_caso`/`realizar_caso`/`listar`/`a_cobrar_fabrica`/`meta`. **Motor (v7 §6):** realizar um caso posta o lançamento via `mod_contabil.registrar_evento` (idempotente por ref `assist:<id>`): **Loja** → `execucao_assistencia` (baixa Provisão Assist.Técnica 2.1.04.05); **Fábrica** → `execucao_reparo_garantia` (baixa Provisão Garantia 2.1.04.03) + entra no relatório 'a cobrar da fábrica'; **Paga** → novo evento `venda_assistencia` (Contas a Receber 1.1.02 × Receita c/ Vendas de Assistência 4.1.02), sem tocar provisão.
**Endpoints (main.py):** GET `/api/assistencias/casos?tipo=` (lista + meta + a_cobrar_fabrica), POST `/casos` (criar; tipo_custo derivado), POST `/casos/<id>/realizar` (posta o razão via resolver_owner). Gating por módulo + isolamento por loja.
**Frontend:** nova page-14 (módulo Assistências agora abre tela, não EM CONSTRUÇÃO): card 'A cobrar da fábrica', filtro Todos/Loja/Fábrica/Paga, tabela de casos com badge de tipo de custo e ação Realizar, modal '+ Novo caso' (motivo mostra o tipo de custo derivado ao vivo). Testes: `test_assistencias.py` (7, incl. razão de cada tipo). Suíte 760→767.
**§6.2 honrado:** a classificação/relatório de repasse saiu do Financeiro (aba Repasse já removida na Sessão 47) e vive aqui; 'a cobrar da fábrica' NÃO é Contas a Receber formal (só controle p/ negociação; reembolso real = fase 2, flag `reembolsado_fabrica`). Nomenclatura das contas mantida (Assist. Técnica/Garantia). Montagem segue EM CONSTRUÇÃO.

## Sessão 50 — Correção Admin/Config: dois itens distintos do Núcleo (Modulos_Orizon_v8)
Desfaz a fusão da v7. **Admin** (identidade/acesso) ganhou a aba **Perfis de Usuário** (o antigo page-9 de limites de desconto por perfil migrou p/ dentro do Admin — `adminPerfisCarregar` renderiza os cards e chama `cfgRenderizarPerfis`). **Config** virou item distinto (page-9 repurposado) com abas **Provisões · Comissão de Vendas · Documentos**:
- **Provisões:** painel de % migrou do Financeiro/Admin p/ Config → Provisões (`adminFinanceiroCarregar` agora renderiza em `#cfg-panel-provisoes`), + **novo campo `comissao_pct`** (Provisão de Comissão de Vendas) em `provisoes_contabeis` (mod_provisoes default+validação).
- **Comissão de Vendas:** botão que abre o modal de faixas/limitador (deslocado do Financeiro p/ cá).
- **Documentos:** cards de modelos (contrato/proposta/demais) — edição em construção [NOVO].
**Financeiro → Provisões** ficou só monitoramento (removido o botão 'Configurar %'). Testes de config ajustados (comissao_pct). Suíte 767 verde.
**Decisões:** (a) Admin/Config são páginas com abas internas (consistente com o padrão de abas do Admin já existente), não submenu de sidebar. (b) O antigo 'Config' do rodapé (limites de desconto/perfil) era o mais próximo de 'Perfis de Usuário' → movido p/ Admin; a sidebar segue com Admin e Config como itens distintos (Admin no menu, Config no rodapé, como já era). (c) `comissao_pct` é persistido como config; a auto-constituição da Provisão de Comissão no fechamento fica como próxima frente (mesma cautela contábil das demais).

**Nova tela de entrada (static/login.html do usuário) ligada ao acesso:** a página substituída tinha o formulário (#email/#senha) mas só o script do toggle de tema — sem submit. Adicionado o handler que faz `POST /api/auth/login` ({login, senha}, credentials same-origin), exibe erro inline (#loginErro) e redireciona p/ `/` no sucesso; `<form>` com `novalidate` + estado 'Entrando…' no botão. Backend: `auth.fazer_login` passou a aceitar **login OU e-mail** (case-insensitive) — a tela nova usa e-mail e as contas antigas seguem entrando pelo login. `/login` já era servido de static/login.html (auth_routes) — sem mudança ali. Teste `test_login_email.py`. Suíte 768 verde.

**Numeração de contrato padronizada + proposta = 1ª página do contrato:** `gerar_num_contrato` passou ao formato **`<SIGLA><AAAAMMDD><SEQ:5>`** (sigla da loja de 3 letras + ano-mês-dia + 5 dígitos sequenciais, contínuos por prefixo) — ex. `INS2026071000001`; ganhou parâmetro `prefixo`. Novo `gerar_num_proposta` = mesmo formato com prefixo fixo **`PV`**. A **proposta comercial** agora é a **capa (1ª página) do contrato** via WeasyPrint (novos `montar_html_proposta`/`gerar_pdf_proposta` em mod_contrato — reaproveitam `_html_capa`, sem as cláusulas e sem a quebra de página), numerada com `PV...`. Endpoint `GET /api/orcamentos/<id>/proposta/pdf` repointado do .docx/LibreOffice para o PDF-da-capa; nº da proposta gerado 1x e persistido em `orcamentos.num_proposta` (nova coluna + migração). Testes: formato novo, sequência contínua, ignora formato antigo, prefixo PV, e capa da proposta com PV. Suíte 771. Legado (modelo_proposta.docx/mod_proposta) permanece mas sai do fluxo.
**Decisão registrada:** número concatenado sem separadores (sigla+data+seq); a sequência recomeça em 00001 para o formato novo (números antigos com traços não contaminam). Data no número é a de emissão; só o SEQ é sequencial.

**Tela Orçamentos (atalho) — ajuste do Diagramacao_v6 aplicado:** o atalho do topo da sidebar (ícone diamante) foi renomeado de 'Projetos' para **Orçamentos** (título da tela idem) — resolve a colisão com o módulo de execução 'Projetos' (producao), que fica intacto mais abaixo. Removidas as abas **Clientes | Parceiros** da tela (viviam duplicadas; já estão só no submenu de Cadastro) — sobra só a lista de orçamentos, sem seletor de abas (funções homeMostrarTab/cli/parHomeCarregar viraram código morto, sem callers). Filtros acima da tabela: Status (já existia) + **Faixa de valor** (mín/máx sobre ultimo_orcamento_valor) + **Data** (início/fim sobre atualizado_em). Busca estendida para casar **projeto · cliente · CPF · parceiro** (parceiro_nome já vinha da enrichment). Frontend puro (Ctrl+F5).

**Negociação — migração de design v4 (itens do usuário) + auditoria geral:** a tela de Negociação (page-02) recebeu os 4 ajustes pedidos: (1) cards de resumo (Valor Bruto/Desconto/à Vista/Total do Contrato) passaram de verde-terminal/dourado fixo para `--surface-2` + `--shadow`, labels `--muted`, valores `--text`/`--err`/`--accent`; (2) botão 'Fechado' virou o componente **Seletor de Status** (`.status-selector`, Diagramacao_v6 §1.5) — badge com chevron, fundo/tinta pelo token do estado (`color-mix` theme-aware), inclusive `--st-fechado`; 'Etapas do Projeto' virou botão secundário normal (`btn btn-ghost btn-sm`, sem o preto+dourado `.btn-ciclo`); (3) verde-terminal do tema escuro trocado pelos tokens reais; (4) linhas Entrada/Parcela do plano (2 mapas BADGE) mapeadas a tokens semânticos — Assinatura=`--muted`, Entrada=`--warn`, Parcelas=`--accent` (tint via `color-mix`), e corrigido o border inválido `${color}40`. **Auditoria completa** de todas as telas em `docs/auditoria_design_v4.md` (✅ migradas: Login, Orçamentos, Em-construção, Config, Financeiro, Expedição, Assistências; 🟡 parciais: Negociação[agora], Admin, Cadastro, Fiscal; 🔴 Ciclo/Etapas badges).

**Negociação — correções de botões/hierarquia (Padrao_Design_v5 §4 + Diagramacao_v7 §1.5):** (1) botão secundário `.btn-ghost` ganhou **borda condicional por tema** — `:root[data-theme=light] .btn-ghost{border:1px solid var(--border)}` (no claro --bg≈--surface-2, sombra sozinha não separa; no escuro segue só sombra). (2/3) rodapé: **Aprovar** passou a **primário único** (`--accent`, era o `btn-amber` preto+dourado), **Salvar** e **Imprimir** viraram secundários (`btn-ghost`); rótulos simplificados (removido 'Orçamento' dos três). (4) o **'Orçamento N'** (`renderOrcamentosBar`) deixou de ser pills soltas e virou o componente **Seletor de Status** (`.status-selector` + chevron + dropdown `.proj-status-dd` p/ trocar o orçamento ativo; renomear via item do menu) — mesmo componente do badge 'Fechado', duas instâncias na tela, nenhuma é botão de ação. Frontend puro. Auditoria (`docs/auditoria_design_v4.md`) atualizada.

**Plano de Pagamento migrado + Indicador de Conclusão (Padrao_Design_v6 / Diagramacao_v8):** as 4 tabelas de parcelas da Negociação (Aymoré/Cartão/VP/Total Flex) — 2 delas ainda com cores fixas (#0d1e0d, rgba…) — passaram a um helper único `_planoLinha` + `.badge-plano` (Badge de status padrão §4): linha **Assinatura=--surface** (agrupamento), **Entrada=--warn-tint** (novo token nos 2 temas), **parcelas=--accent-tint**, rótulo sem pill/borda/fonte próprias. **Indicador de Conclusão** (`.ind-conclusao`): substitui o badge '✓ concluído' repetido em Etapas do Projeto por ícone isolado (círculo cheio --accent + check branco quando concluído; contorno --accent em andamento; contorno --border pendente) — legível nos dois temas, corrige o bug de contraste do claro. Parâmetros verificada: já token-based, sem o problema. Frontend puro; auditoria atualizada (Negociação → ✅).

## Sessão 51 — Cadastro detalhado: Funcionário/Fornecedor/Terceiro (Modulos_Orizon_v9)
Módulo 2 (Cadastro) ganhou 3 entidades reais (antes stubs 'em breve'). Modelos em `database.py` (`funcionarios`/`fornecedores`/`terceiros`, loja-scoped) + **`Usuario.funcionario_id`** (migração) — a **fronteira Funcionário×Usuário**: RH é dado do Cadastro, login é conta do Admin, ligados por referência, sem duplicar. Domínio `mod_cadastro.py` (serialize/aplicar/listar + `func_sync_acesso`), registrado no manifesto.
**Fronteira (o ponto central):** a tela de Funcionário tem a seção condicional 'Este funcionário tem acesso ao sistema?' — se sim, e-mail + Perfil (nivel); ao salvar, `func_sync_acesso` **cria/atualiza a conta de login vinculada** (login=e-mail, nivel=perfil, `funcionario_id`, senha inicial=dígitos do CPF), valida e-mail único; 'não' **desativa** a conta (nunca apaga). Nenhum dado pessoal duplicado.
**Fornecedor:** PJ/PF, categoria (matéria-prima/transportadora/serviços/outro), prazo de pagamento, dados bancários (referenciável por 'Fornecedores a Pagar'). **Terceiro:** sempre PF, tipo de serviço (Montador/Outros), PIX/dados bancários, condição MEI/autônomo (o Montador é a mesma pessoa da Execução da Montagem — referência).
**Endpoints (main.py, dispatch genérico `_cad_ent`):** GET/POST `/api/{funcionarios|fornecedores|terceiros}` (+/<id>) — lista com filtro por status e busca nome/documento, criar/editar. **Frontend:** as 3 abas do Cadastro deixaram de ser stub — Lista/Tabela (busca+status+Novo) + modal Detalhe/Formulário genérico (`_CAD_DEFS`), Funcionário com a seção de acesso condicional. Testes `test_cadastro.py` (5, incl. boundary). Suíte 771→776.

**Correção dourado (reincidência) + Campo de Entrada (Padrao_Design_v7):** (1) o botão 'Voltar' e o título 'Etapas do Projeto' (borda/texto dourado) foram corrigidos NA ORIGEM (o componente do painel de Ciclo, `renderCiclo`): 'Voltar' virou botão secundário padrão (`btn btn-ghost btn-sm` + `ti-arrow-left`), título usa `--text` peso 800. Mesma varredura pegou os demais botões dourados do componente (Editar Cadastro, Parceiro, Briefing, Abrir/Imprimir orçamento — todos `btn-ghost btn-sm`) e o título dourado do ciclo no Admin. (2) **Campo de Entrada** ganhou regra única: `input[type=text|password|number|email|tel|search|date]` → fundo `--surface-2`, borda `--border` (foco `--accent`), 36px, radius `--r-sm` (token novo), pad 12px, placeholder `--muted`, Mono p/ número/data e Inter p/ texto — resolve o 'R$ máx branco fixo' e os inputs `date` nativos. Variantes pequenas da sidebar (`.sb-input-sm`/`.sb-select`) protegidas por especificidade elevada. Frontend puro. Restam dourados só nos modais Briefing/Parceiro (telas 🟡 da auditoria).

## Sessão 52 — Sub-entidades (Endereço/Bancário/PIX) + Tabela de Funções + Folha de Pagamento (Modulos_Orizon_v10)
Três frentes do v10, backend+frontend+testes, tudo na `main`. Suíte 776→**783**.
**(1) Sub-entidades reutilizáveis (Endereço + Dados Bancários + PIX).** `database.py`: blocos `cep/logradouro/numero/complemento/bairro/cidade/uf` e `banco_nome/banco_codigo/agencia/conta/pix` adicionados a **Funcionário/Fornecedor/Terceiro** (Terceiro já tinha `pix`), e `pix` ao **Parceiro** (única sub-entidade bancária dele). Migração idempotente ao final de `_migrar_colunas` (`_ENDERECO`/`_BANCO` + `_add_cols`, por PRAGMA+ALTER). `mod_cadastro.py`: helpers `_aplicar_campos`/`_serial_campos` + constantes `ENDERECO_CAMPOS`/`BANCO_CAMPOS`, aplicados nos serialize/aplicar das 3 entidades. **Frontend:** o modal genérico (`_CAD_DEFS`/`cadEntRender`) ganhou tipos de campo `secao` (divisor), `cep` (ViaCEP → preenche logradouro/bairro/cidade/uf) e `select_funcoes`; seções **Endereço** e **Dados Bancários** entram via spread `..._CAMPOS_ENDERECO`/`..._CAMPOS_BANCO` nas 3 defs. Parceiro (modal hand-built): campo **Chave PIX** + wiring em `parAbrirModal`/`parSalvar` e no backend (`_parceiro_dict` + create/editar).
**(2) Tabela de Funções (Config).** Novo modelo `Funcao` (`funcoes`, loja-scoped, status). `Funcionario.funcao_id` e `Terceiro.funcao_id` (FK) **referenciam o catálogo** em vez de texto livre (o `tipo_servico` do Terceiro fica só p/ legado). Endpoints `/api/funcoes` no mesmo dispatch `_cad_ent`. **Frontend:** nova aba **Config → Funções** (`cfgFuncoesRender`: CRUD inline, adicionar/editar/inativar-reativar) e selects `Função` nos cadastros de Funcionário/Terceiro (cache `_funcoesCache`, invalidado ao editar o catálogo).
**(3) Folha de Pagamento (§2.1) — MOTOR, não digitação.** Novo `mod_folha.py` + modelo `FolhaPagamento` (`folha_pagamento`, competência AAAA-MM, status aberta/paga). `calcular_folha`: **parte fixa** = `remuneracao_fixa` do cadastro; **parte variável** (só `fixa_variavel`) = Σ vendas líquidas FECHADAS do consultor no mês (`vendas_liquido_consultor`, por `criado_por_id`+`status_at`) × % da faixa de meta (`mod_provisoes.resolver_comissao_venda`). `gerar_folha` idempotente (1 por Funcionário ativo; folha paga não recalcula). `pagar` posta a despesa via `registrar_evento` nas contas **5.3 já existentes** (fixa→`5.3.06` Salários de Vendas, variável→`5.3.01` Comissão de Vendedor — EVENTOS novos em `mod_contabil`), idempotente por `ref="folha:<id>"`, usando os Dados Bancários/PIX cadastrados (`_pagamento_str`). Endpoints GET `/api/folha`, POST `/api/folha/gerar`, POST `/api/folha/<id>/pagar`. Domínio `folha` no manifesto (`modulos.py`, depende cadastro/comercial/financeiro). **Frontend:** seção **Financeiro → Folha de Pagamento** (`folhaCarregar`/`folhaRender`) — seletor de competência, botão Gerar, tabela (fixa/vendas/faixa/variável/total/pagamento) + Totais e ação **Pagar** por linha. Testes: `test_folha.py` (cálculo, geração idempotente, postagem 5.3, endpoints HTTP), `test_cadastro.py` (catálogo+referência, endereço/banco persistem), `test_parceiro_vinculo_loja.py` (PIX round-trip). JS validado por balanço de chaves por-função (extração `<script>` + scan, node ausente).

## Sessão 53 — Campo de Entrada: largura por tipo + autofill (Padrao_Design_v8 §4, 2 achados)
Fecha a lacuna de largura do Campo de Entrada (v7 só padronizou fundo/borda/altura). **Frontend puro** (`static/index.html`), sem tocar backend — suíte inalterada.
**Achado 1 — filtro "R$ máx" com fundo branco (reincidência do v7):** a **causa-raiz** não era o token não aplicado — a regra `input[type=…]` (§v7, linha 116) já força `background:var(--surface-2)` e cobre `type=number`; e `.inp` sequer é definida no CSS (é no-op). O que pintava branco **só nesse campo** era a **camada de autofill do Chrome** (o campo com valor lembrado ganha fundo próprio que o `background` não vence; o irmão vazio fica correto — assinatura clássica de autofill). Fix: regra `input:-webkit-autofill` com `box-shadow:0 0 0 1000px var(--surface-2) inset` + `-webkit-text-fill-color:var(--text)` + `transition` longa (mata o flash), válida p/ TODOS os inputs.
**Achado 2 — datas do "Período" viraram 2 barras full-width empilhadas:** causa-raiz = a regra global de input tem `width:100%` por padrão; os campos de moeda escapavam por `width` inline (92px), mas os de **data não tinham largura** → herdavam 100% e, no flex `wrap`, empilhavam. **Decisão:** NÃO inverter o default global (`width:100%`) — auditoria mostrou **78 inputs** sem largura inline que dependem do 100% (formulários de Cliente/Parceiro/Plano de Pagamento em grid o querem cheio); invertê-lo quebraria esses forms (não verificável sem browser). Em vez disso, **largura compacta explícita nos filtros** (Padrao_Design_v8 §4): `R$ mín/máx` 92→**130px**, `Data início/fim` **160px** (cabe dd/mm/aaaa + ícone). Agora Status · R$ mín · R$ máx · Data início · Data fim ficam **lado a lado**, nunca empilhados; só a busca livre (`proj-search`, `flex:1`) segue flexível. _(Ressalva registrada: o default global segue 100% por compatibilidade com os forms; a regra v8 "nunca 100% por padrão" foi honrada no resultado — filtros compactos — sem o flip arriscado.)_

## Sessão 54 — Botão primário: borda sutil + investigação do "vazamento" de cor (Padrao_Design_v9 §4)
**Investigação "+ Novo Projeto" com duas cores (petróleo claro × verde-menta escuro):** grep completo por cor hardcoded em botão — **causa-raiz NÃO reproduz no fonte atual**. As duas instâncias (`page-00` linha 680 e modal `mceCriarProjeto` linha 1727) usam `class="btn btn-primary btn-sm"` desde 2026-06-15 (`git log -S`), e `.btn-primary{background:var(--accent)}` já é 100% token; `--accent` só é definido nos dois `:root` (escuro default / `[data-theme=light]`), sem override escopado. Os hexes `#1F4B4B`/`#5BB8AC` aparecem **só** na definição dos tokens. Conclusão: a divergência observada é **deploy defasado** (VPS atrás dos commits v8/v10), não bug de fonte — recomendado deploy.
**Regra nova implementada (v9 §4):** o botão **Primário** ganha contraste por **sombra + borda sutil 1px no mesmo matiz do accent, ~15% mais escura** — `.btn-primary{…;border:1px solid color-mix(in srgb, var(--accent) 85%, #000)}`. Theme-adaptive (resolve por tema sozinho), sem cor literal. `box-sizing:border-box` global absorve a borda (sem shift de layout).
**Dourado → accent nos botões de ação (decisão do usuário: converter p/ primário, com "1 primário por tela"):** o `.btn-ciclo` acabou sendo um **componente compartilhado de ~30 botões** (Baixar/Carregar/Consultar/Emitir/Cancelar + as ações principais), não só 16 Aprovar/Confirmar. Correção **na origem** (como o v9 recomenda): (a) `.btn-ciclo` redefinido como **secundário token-based** (`--surface-2`/`--muted`/`--border`/`--shadow`, hover accent) — utilitários viram secundários; (b) `.btn-amber` (o "Aprovar" da Negociação, referenciado pelo JS — nome preservado) vira **primário accent**; (c) as ações "fecham o negócio" de cada etapa/tela (Confirmar medidor, Liberar, Registrar parecer, Produção Concluída, Concluir Relatório, peConcluir, concluirAprovacaoFinanceira, revisa, gerarContrato, sig-ok, data-act ok, encaminhar Pedidos) trocaram o dourado literal (`#b8960c`/`#1a1200`) e o `var(--dalm-gold)`-como-fundo por **`var(--accent)`+texto branco** — 1 primário por painel de etapa. `--dalm-gold` **mantido** onde é marca legítima (cabeçalhos de documento/seção, bordas de tab — permitido pelo v9). Verificação: CSS 310/310, **scan JS delta zero** (HEAD=CURRENT `(7,4)`), nenhum `<button>` com `b8960c`. _(Fora de escopo, anotado: banners de aviso `#1a1200` e as caixas de modal "Aprovar Orçamento"/"signatário" com borda/heading dourado literal — não são botões; ficam p/ um passe de chrome dedicado.)_

## Sessão 141 — Agenda da Loja FATIA 2: marcos + endpoint + visão Calendário (primeira TELA da Agenda)

Fatia 2 do plano — a Agenda aparece na interface.

- **Subfases do PE ganham data prevista default** (`mod_cronograma.SUBFASES_PE_FRACOES`):
  frações da janela da etapa 11 no `gerar_cronograma_projeto` — 11a 20% · 11b 40% · 11c 70% ·
  11d 85% · 11e 100%. Só preenche subfase SEM data (edição manual nunca é sobrescrita); sem
  isso os marcos de Planta de Pontos/Revisão/assinatura do PE não existiam.
- **`mod_agenda.py`** novo (puro, domínio ciclo): `SETOR_POR_ETAPA` (refinamento de exibição do
  FAIXA_POR_ETAPA: medição 9-10 · pe 11a-e · expedição 12-16 · montagem 17-20 · financeiro
  8/11d/21), `marcos_do_projeto` (executado substitui previsto; medição com fallback na
  `previsao_medicao`; **entrega 16 POR FASE** com a prioridade da faixa de entrega: card da
  expedição > previsão da fase > prevista da 16 > data do projeto; fase retida marcada) e
  `marcos(projetos, de, ate, setor)` ordenado.
- **`GET /api/agenda?de&ate&setor`**: agrega os marcos de TODOS os projetos com contrato da
  loja (exclui `perdido`); consultor filtrado por posse (`criado_por_id`), operacional por
  atribuição E com **valores omitidos** (`visao_do_papel`); valor do marco = Val_Liq (fase
  congelada / orçamento contratado). Payload granular por dia — Semana/Mês (Fatia 3) consomem
  o mesmo endpoint.
- **Frontend:** nav "Agenda" (abaixo de Projetos) + page-16. Visão **Calendário**: grade do
  mês (Dom–Sáb), badges por Setor com contagem, rodapé do dia com Σ das ENTREGAS (R$), hoje
  destacado, navegação ‹ hoje › e chips de filtro por Setor; clique no dia abre o detalhamento
  INLINE (padrão sem modal): Setor | Marco | Projeto·Cliente | Valor | Previsto/Realizado.
  Switcher já mostra Semana/Mês desabilitados (Fatia 3).
- **TDD** `tests/test_agenda.py` (9): motor puro (previsto/realizado, fallback da medição,
  setores/títulos das subfases, entrega por fase com prioridade e retida, filtros), offsets do
  PE (frações + não sobrescrever edição) e endpoint (dados, filtro de setor, isolamento de
  loja).

Suíte **1686 verde** (+9); `node --check` ok; 4 falhas pré-existentes de chat/e-mail seguem.
Próxima: **Fatia 3** (cargas distribuídas + visões Semana/Mês).

## Sessão 140 — Agenda da Loja FATIA 1: `val_liq_congelado` por fase (unidade da Agenda)

Fatia 1 do plano. **Val_Liq (VAVO − Cust_Ad, base das comissões) congelado POR FASE** — a
unidade de volume da Agenda (decisão da Sessão 138; congela-se porque recalcular on-the-fly
divergiria da comissão paga se a proporção VAVO/Cust_Ad mudar).

- **Schema:** `parcela_projeto.val_liq_congelado` (Float, NULL = legado) + migração
  idempotente. **Backfill único no start** (`main._backfill_val_liq_fases`, fail-soft por
  projeto, junto dos backfills existentes): fases legadas ganham o rateio líquido do motor
  ATUAL (melhor aproximação disponível).
- **Helper:** `_liquidos_contrato_por_ambiente(orcamento_id, db)` — gêmeo de
  `_valores_contrato_por_ambiente`, rateia o Val_Liq proporcional ao VAVA reusando
  `mod_contrato.ambientes_valor_contrato` (resíduo no último → Σ EXATA).
- **Congelado nos 5 caminhos** (mesma partição do Val_Cont, última fatia absorve o resíduo):
  POST /parcelas (2× `congelar_parcelas`) · POST /parcelas/<id>/desmembrar (2×
  `desmembrar_fase`; mãe legada sem o campo → aproxima pelo rateio atual) · `mod_retido.reter`
  (criação e split; params novos `liquidos_por_ambiente`/`val_liq`) · `mod_retido.liberar`
  (split em ondas: liq acompanha a PROPORÇÃO do split de Val_Cont; mãe legada segue None) ·
  `mod_retido.confirmar` (legado, params novos). Funções puras de `mod_parcelas` INALTERADAS
  (chamadas 2×) — proporções idênticas pois ambos os rateios são proporcionais ao VAVA.
- **GET /parcelas** expõe `val_liq_congelado` ao lado do `val_cont_congelado`.
- **TDD:** `tests/test_val_liq_congelado.py` (4 testes; cenário com comissão arq 10% repassada
  → Val_Liq 3000 ≠ Val_Cont 3333,33, liq/ambiente = 1000 exato): invariante
  `Σ val_liq_congelado == Val_Liq` no desmembramento, no sucessivo, na retenção com split e na
  liberação em ondas; backfill idempotente.

Suíte **1677 verde** (+4? novos+ajustes); 4 falhas pré-existentes de chat/e-mail seguem.
Próxima: **Fatia 2** (offsets das subfases do PE + mod_agenda marcos + endpoint + Calendário).

## Sessão 139 — Agenda da Loja FATIA 0: mod_calendario (dias úteis genérico) + config "Agenda e Capacidade"

Primeira fatia do plano (`docs/superpowers/plans/agenda/2026-08-03-agenda-da-loja-plan.md`).

- **`mod_calendario.py`** novo (puro, TDD — `tests/test_calendario.py`, 12 testes):
  `eh_dia_util` / `proximo_dia_util` / `adicionar_dias_uteis` / `dias_uteis_entre` (inclusivo) /
  `espalhar` (valor→{dia: fatia} em dias úteis, ÚLTIMA fatia absorve o resíduo — Σ exata ao
  centavo, padrão da casa). `cfg` = seção `agenda` da config da loja (`sabado_util`,
  `feriados[]` AAAA-MM-DD; feriado malformado é ignorado, nunca lança). Genérico de propósito:
  candidato futuro a calcular o prazo contratual. Classificado no domínio `ciclo` (modulos.py).
- **Config da loja — seção `agenda`** em `config_financeira_default()`:
  `produtividade_montagem_rs_dupla_dia=7000` · `duplas_disponiveis=2` · `sabado_util=false` ·
  `feriados=[]` · `teto_dias_montagem=10` · `horizonte_capacidade_semanas=6`.
  `validar_config_financeira` valida a seção (produtividade>0, duplas≥0, teto≥1, horizonte
  1–26, feriados AAAA-MM-DD). Ratchet `test_default_tem_estrutura_completa` atualizado.
- **Config → aba "Agenda"** nova no painel (entre Cronograma e Funções): produtividade, duplas,
  teto, horizonte, sábado útil e lista de feriados (chips com adicionar/remover), salvando pelo
  MESMO PUT `/api/admin/lojas/<id>/config-financeira` (merge preserva o resto da config).

Suíte **1672 verde** (+12); `node --check` ok; as 4 falhas pré-existentes de chat/e-mail seguem.
Próxima: **Fatia 1** (`val_liq_congelado`).

**Rev (mesmo dia, correção do usuário):** o `teto_dias_montagem` NÃO fazia sentido — o
cronograma de entrega já prevê a montagem por projeto; a janela de trabalho vem DELE, e a
produtividade só converte a necessidade diária em recurso (duplas). Removido do default, da
validação e do painel (o save também apaga a chave de configs já gravadas). Acrescentada a
**estimativa de Projeto Executivo**: `produtividade_pe_rs_dia` (default R$ 20.000/dia,
configurável), análoga à da montagem — PE passa a ter carga distribuída e ocupação diária no
painel Capacidade. Aba Config → Agenda reorganizada com títulos **Projeto Executivo** ·
**Montagem** · **Calendário útil**. Spec §5/§6/§8 e plano (Fatias 3/4) revisados.

## Sessão 138 — Agenda da Loja: design fechado em debate (SEM código) + parecer VAVO×Val_Liq

**Formato pedido pelo usuário:** debater formato e nomenclatura ANTES de qualquer linha de
código. Debate em 2 rodadas → decisões fechadas e registradas na spec
`docs/superpowers/specs/agenda/2026-08-03-agenda-da-loja-design.md` + plano em fatias em
`docs/superpowers/plans/agenda/2026-08-03-agenda-da-loja-plan.md`.

**Decisões:** módulo "Agenda da Loja"; agrupamento por **Setor** (refina `FAIXA_POR_ETAPA`, v1
sem Comercial: Medição · PE · Expedição · Montagem · Financeiro); visões **Calendário/Semana/
Mês** + painel **Capacidade**; três naturezas de dado (Marco/Carga/Capacidade); Agenda 100%
DERIVADA dos cronogramas (sem tabela nova de datas). **Unidade = Val_Liq** (VAVO−Cust_Ad, base
das comissões — decisão do usuário, corrigindo a proposta inicial de val_cont): novo congelado
`parcela_projeto.val_liq_congelado` em TODOS os caminhos de criação/split de fase (motivo:
on-the-fly divergiria da comissão paga se VAVO/Cust_Ad mudar). Consolidação = entrega no
período, EXCETO Montagem (carga distribuída em dias úteis); Capacidade v1 = dimensionamento de
duplas (⌈Σ carga/produtividade⌉, R$7.000/dupla/dia CONFIGURÁVEL), Gantt nominal fica pra v2.
**`mod_calendario.py` novo** (dias úteis genérico — confirmado que não existe hoje; feriados
configuráveis já na v1). Acesso: reusa `main._bloqueio_comercial` → `mod_escopo.visao_do_papel`
(operacional vê marcos/contagens SEM R$ e sem Capacidade; consultor filtrado por posse).

**Parecer (achado do usuário, fora do escopo):** `frete_loc/assist/ins_loc/prov_mont/prov_gar`
sobre VAVO **têm motivo documentado** — `docs/referencia/NOMENCLATURA.md §3b` (convenção
canônica; motor deve espelhar `mod_contabil.constituir_provisoes_venda`, bug antigo da
assistência nasceu de base divergente). Migrar p/ Val_Liq é RECALIBRAÇÃO de negócio (encolhe
provisões pelo fator Val_Liq/VAVO; % das lojas foram calibrados sobre VAVO) → frente própria
com o contador; a Agenda não depende (usa Val_Liq por definição própria).

## Sessão 137 — Retenção por obra RECORRENTE (9→17) com registro histórico + previsões no desmembramento

**Pedido do usuário:** a retenção deixa de ser um ato único da Medição — pode ser acionada na
Solicitação de Medição (9), Medição (10), PE (11) e até na Montagem (17), VÁRIAS vezes; cada
retenção registra quando foi e em qual fase do ciclo; o modal (revisado) indica quais ambientes
ficam retidos e o motivo, com **data prevista de liberação**; e o desmembramento passa a
solicitar, por nova fase, a previsão de liberação p/ prosseguimento e a NOVA previsão de entrega.

**Schema:** tabela **`retencao_obra`** (evento: etapa_codigo do ciclo, motivo,
liberacao_prevista, ambientes_json, criado_em/por, liberado_em/por) + colunas
**`parcela_projeto.liberacao_prevista`/`entrega_prevista`** (migração idempotente); manifesto
`modulos.py` atualizado (ratchet `test_tabelas_batem_com_o_schema`).

**Backend (TDD, +6 testes / `tests/test_retencoes.py`):**
- `mod_retido.reter(...)` — retenção DIRETA multi-evento: não desmembrado → cria [segue, retida]
  (tudo retido → fase única retida); desmembrado → fase inteira vira `retido` ou SPLIT
  (original segue com o resto; retida nova no fim) via `mod_parcelas.desmembrar_fase`
  (congelados da mãe EXATOS); grava valor_ambiente nos splits (liberação em ondas continua
  exata); recusa ambiente já retido, fase liquidada e fase em expedição; marca sinais do
  medidor como confirmados; registra o evento.
- `mod_retido.listar_retencoes` + `estampar_liberacoes` (fecha o registro quando o ÚLTIMO
  ambiente dele sai de fase retida — chamado no `retido/liberar`, que agora também limpa/carrega
  a `liberacao_prevista` no split de liberação).
- Endpoints: `POST/GET /api/projetos/<n>/retencoes` (gerência `autorizar`; GET com nomes de
  ambientes); `POST /parcelas` e `POST /parcelas/<id>/desmembrar` aceitam
  `previsoes: [{liberacao, entrega}]` (helper `_previsoes_fases`; sucessivo herda da mãe quando
  vazio); `GET /parcelas` e `GET /entrega-resumo` expõem as datas novas (previsão da fase >
  global; faixa mostra "retida — liberação prevista X").

**Frontend:** bloco "Retenção por obra" nas etapas 9/10/11/17 (contexto da etapa vai pro
registro); modal REVISADO — seção "Nova retenção" (checkboxes elegíveis c/ sinais do medidor
pré-marcados, motivo, data de liberação prevista; gerência retém direto, medidor sinaliza),
"Fases do projeto" (liberar + liberação prevista) e "Histórico de retenções" (tabela Quando ·
Etapa · Ambientes · Motivo · Liberação prevista · Situação). O fluxo antigo em 2 atos
(`retidoToggle`/`retidoConfirmar`) foi aposentado no front (endpoints seguem p/ compat).
Desmembramento (inicial e sucessivo) ganhou o **passo 2 inline**: datas por nova fase antes de
confirmar (`_desmPedirPrevisoes`/`_desmExecutar`).

**Validação:** suíte **1660 verde** (+4 novos arquivos/testes; as 4 falhas de
`test_chat_wa`/`test_comunicacao` seguem pré-existentes); `node --check` ok. Pendente:
verificação manual no navegador.

## Sessão 136 — Faixa de entrega no fichário (9→16) + desmembramento SUCESSIVO de fases

**Pedido do usuário (3 mensagens na mesma frente):** (1) da Solicitação de Medição até a
Entrega no cliente, manter visível a data de entrega — "Previsão de entrega" enquanto previsão,
"Entregue em" após o fato — por fase quando desmembrado, com os ambientes da fase; (2) padrão de
tela: bloco INLINE como o do desmembramento (SEM modal adicional — substituiu o pedido inicial
de hover+modal); (3) desmembramento pode ser SUCESSIVO: desmembrou em 2 na Medição, e no PE
decide-se dividir uma fase em novas fases.

**Backend (TDD, +11 testes):**
- `GET /api/projetos/<n>/entrega-resumo` (main.py, junto do GET /parcelas): global previsão =
  `Projeto.data_entrega`, entregue = `CicloLogistico` projeto-wide `.data_entrega` OU etapa 16
  concluída; por fase previsão = `CicloLogistico(parcela_id).prazo_entrega` (expedição) com
  fallback na global, entregue = `.data_entrega` do card da fase; ambientes via
  `ParcelaAmbiente→PoolAmbiente`. Sem desmembramento → "fase única" com os ambientes do
  orçamento CONTRATADO. Tenancy espelhada do GET /parcelas (404 fora da loja).
  `tests/test_entrega_resumo.py`.
- **Sucessivo:** `mod_parcelas.desmembrar_fase(amb_ids_fase, grupos, val_mae, fracao_mae,
  valores_por_amb)` — partição sobre os ambientes DA fase, preserva EXATAMENTE os congelados da
  mãe (última nova fase absorve o resíduo; invariante #5 segue no total; rateio proporcional ao
  valor de contrato por ambiente, igual se tudo zero). Endpoint
  `POST /api/projetos/<n>/parcelas/<id>/desmembrar`: novas fases herdam a POSIÇÃO da mãe
  (ordem; desempate por id), a mãe sai e renumera 1..N; **recusa fase liquidada (409) e fase já
  em expedição** (`CicloLogistico.parcela_id`, 409). `tests/test_desmembramento_sucessivo.py`.

**Frontend:** faixa `#entrega-faixa` injetada no `_fichaRenderConteudo` para mãe 9..16 (aparece
até em etapa não iniciada); `_entregaFaixaRender()` — sem desmembramento uma linha
(data + ambientes), desmembrado tabela `Fase | Entrega | Ambientes` ("Entregue em" em `--ok`,
fase retida marcada). Na tabela do desmembramento (`peDesmembrarRender`), botão **Desmembrar**
por fase (só com 2+ ambientes e não liquidada) → form inline `peDesmembrarFase/…Criar` (mesmo
padrão de inputs por ambiente) → POST sucessivo → re-render + faixa.

**Validação:** suíte **1656 verde** (+11) com as MESMAS 4 falhas pré-existentes de
`test_chat_wa`/`test_comunicacao`; `node --check` ok. Pendente de verificação manual no
navegador (fichário 9→16 com/sem desmembramento; sucessivo no PE).

## Sessão 135 — Registro do contrato fecha ao centavo: linha de itens gerais, totais nas 2 colunas, parcela residual

**Pedidos do usuário (3 achados na tela da Sessão 134 + 1 na conferência):**

1. **Divergência 224.456,92 × 225.005,21:** a tabela de ambientes não fechava com o Total do
   contrato. Causa raiz (validada no banco de dev, `_negociacao_breakdown` do orçamento 10): no
   motor `VAVO = ΣVAVA + custo especial repassado` — o Norberto tem **custo especial de
   R$ 500,00** (linha do ORÇAMENTO, fora dos ambientes) que × fator financeiro 1,096556 =
   R$ 548,29. Fix: a tabela ganhou a linha **"Itens de ordem geral (custo especial fora dos
   ambientes)"** (residual `VAVO − ΣVAVA`, nas 2 colunas) e o rodapé virou **"Total"** com a soma
   fechando exata: à vista = VAVO (205.192,68), financiado = Val_Cont (**225.005,21** ✓). A nota
   de rodapé agora só aparece se o recalculado divergir do total CONGELADO (>R$ 1) — vigia de
   staleness, não mais explicação de rotina.
2. **"Valor à vista" do cabeçalho estava ERRADO:** mostrava `o.valor_liquido` = **Val_Liq
   (líquido da LOJA, pós-comissões — número sensível)**, não o à vista do cliente. Agora usa o
   VAVO do motor (mesma base da coluna); sem preview (perfil bloqueado) mostra "—".
3. **Projeto + Cliente no painel:** linha "Projeto X · Cliente Y" sob o título
   (`projetoAtivo.nome_projeto` / `.cliente.nome`, fallback `nome_cliente`).
4. **Os 4 centavos do parcelamento (15×13.000,35+30.000 = 225.005,25 ≠ 225.005,21):** resíduo de
   arredondamento — `mod_fin/cartao.py` fazia `round(financiado/n, 2)` e listava as N parcelas
   IGUAIS sem absorver a sobra (a `venda_programada` já absorvia). Fix (TDD,
   `tests/test_cartao.py` +2): **cartão e aymoré** agora ajustam a ÚLTIMA parcela
   (`ajuste_ultimo`), invariante `entrada + Σ parcelas = total_cliente` ao centavo (Norberto:
   14× 13.000,35 + última 13.000,31). Frontend persiste/exibe as parcelas REAIS do plano
   (cartão gerava N iguais na mão; aymoré gravava `d.valor_parcela`; VP/TF já estavam certos), e
   o registro do contrato mostra "Nx de V (última: V′)". **Norberto: a pedido do usuário, o
   plano congelado foi REGRAVADO no banco de dev LOCAL** (última parcela 13.000,35 → 13.000,31 +
   `texto_cartao`; backup do JSON original no scratchpad da sessão) — VPS A/B seguem com o plano
   antigo até ordem de promover.

**Validação:** headless no banco de dev (tabela e plano novos batem ao centavo, acima);
`node --check` ok; suíte **1645 verde + 4 falhas PRÉ-EXISTENTES** em `test_chat_wa`/
`test_comunicacao` (falham na árvore limpa `a4701ba` — investigar à parte, não relacionadas).

## Sessão 134 — Pós-assinatura: parâmetros saem da sidebar; registro congelado na aba Contrato

**Pedido (detalhe cosmético importante):** após a assinatura, os PARÂMETROS da negociação
(desconto, modalidade, parcelas, entrada) não aparecem mais na barra lateral — o registro passa
a viver na aba Contrato do fichário, acessível e read-only. Custos adicionais: fora do escopo.

**Sidebar:** `_sbParamsAtualizar()` decide pela MESMA fonte do lock pós-assinatura
(`_negSaveTravado`: `_contratoAssinado` com exceção do complemento de PE, que segue negociável e
mantém a sidebar). Hooks: `goPage(2)`, `atualizarBotoesAprovacao` (cobre projeto sem contrato
após visitar um assinado — flag stale) e fim de `aplicarBloqueioNegociacao` (troca de orçamento
contratado↔complemento).

**Aba Contrato:** `_contratoParamsResumo()` (efeito da etapa 7) monta o painel "Parâmetros da
negociação — registro do contrato" com dados CONGELADOS do orçamento CONTRATADO
(`GET /projetos/<n>/orcamentos` → `contratado_id`; `GET /orcamentos/<id>/ambientes`): desconto
global, forma de pagamento, parcelamento (Nx de R$V), entrada (valor/forma/data), total do
contrato, valor à vista e a lista de ambientes fechados com seus valores.

**Correção (mesmo dia, achado do usuário):** a primeira versão listava os ambientes com
`order_total` do pool — que é o **CUSTO DE FÁBRICA** (CFA), não o valor de fechamento
(`budget_total` = venda bruta; `order_total` = pedido à fábrica). Agora os valores vêm do MOTOR
via `POST /api/orcamentos/<id>/negociacao-preview` (breakdown com `pool_ambiente_id` →
pareamento exato): colunas **À vista (VAVA)** e **Com financiamento (VAVA × Val_Cont/VAVO)** —
as MESMAS da tabela de negociação; rodapé soma a coluna financiada e uma nota explica a
diferença residual para o Total do contrato (itens de ordem geral fora dos ambientes, ex.
brindes/custos especiais — no Norberto, R$ 548,29). Perfil sem visão comercial
(`_bloqueio_comercial`) degrada para a lista de nomes sem valores.

**Validação headless:** Norberto (assinado) → sidebar oculta + painel completo (20% · Cartão
15x de R$ 13.000,35 · entrada R$ 30.000 pix · 4 ambientes com valores); Projeto_Reuniao_2 (sem
contrato) aberto NA SEQUÊNCIA → sidebar volta a aparecer (stale resolvido); zero pageerror.
Nota: Projeto_A tem contrato COM assinatura no banco de dev (por isso esconde lá também —
correto). Suíte completa **1647 verde**.

## Sessão 133 — Fichário fase 2: telas diretas (sem modal) + desmembramento desde a Medição

**Pedido do usuário (2026-08-02):** confirmar que a aprovação financeira é só de gerentes/
diretores; Briefing e Provisões podem renderizar DIRETO na tela da etapa (como a Comparação de
Valores, que já ficou boa); e o desmembramento de fases deve estar disponível desde a
Solicitação de Medição.

**1) Auditoria do acesso à AF — CONFIRMADO em três camadas:** `GET /api/orcamentos/<id>/provisoes`
exige `perfis.pode(nivel, "aprovar_financeiro")` (403); `POST /provisoes/rev1|rev2` revalida
login+senha do aprovador (403 "Senha/perfil inválido"); concluir 8/11d no PATCH do ciclo passa
por `exige_aprovacao_financeira` + `_aprovador_financeiro` (403). O FRONT agora espelha: o
painel só carrega para `pode_aprovar_financeiro`; os demais veem aviso claro em vez de um botão
que levaria a 403.

**2) Briefing na tela (etapa 3):** o formulário (#bf-box) virou nó ÚNICO que MIGRA — na etapa 3
do fichário monta direto na tela (✕ oculto, dados carregados por `_bfCarregarProjeto`); nos
fluxos de cadastro de cliente/pós-criação continua no modal (`_bfEstacionar` devolve o nó ao
modal antes de qualquer re-render do ciclo, senão o innerHTML destruiria o form do app inteiro
— guardas em renderCiclo e _fichaRenderConteudo). Sobrevivência a troca de etapa verificada em
headless.

**3) Provisões na tela (etapas 8/11d):** `abrirProvisoes` ganhou alvo inline — com
`#prov-inline-slot` presente (tela de AF do fichário) o painel renderiza direto na etapa, sem
overlay e sem botão Fechar (rodapé Fechar moveu para o caminho de overlay, mantido por compat);
`_fichaEfeitos` dispara o carregamento ao selecionar a etapa. Revisar/Aprovar continuam dentro
do painel (reautenticação preservada); refresh pós-ação re-renderiza o slot.

**4) Desmembramento desde a Solicitação de Medição:** o backend do `POST /parcelas` só exige
contrato assinado (etapa 7) — nenhuma trava adicional; as telas 9 e 10 ganharam o mesmo bloco
"Desmembrar em fases" da 11c (append central em `_fichaCorpoEtapa`; id único por vez — o
fichário renderiza uma etapa por tela). A 11c permanece como estava.

**Verificação:** headless — briefing inline preenchido + sobrevive re-render; provisões com
tabela e Aprovar na tela do gerente e aviso "restrita ao Gerente Adm/Financeiro e Diretores"
sem a capability; desmembramento renderizando o pool de ambientes na 9; zero pageerror.
`node --check` ok. Suíte completa **1647 verde**.

## Sessão 132 — Ciclo interno em FICHÁRIO (lombada + tela cheia) — branch feat/ciclo-fichario

**Frente independente** (spec `docs/superpowers/specs/ciclo/2026-08-01-ciclo-fichario-design.md` +
mockup aprovado). Redesign de APRESENTAÇÃO apenas: `mod_ciclo.py`, `database.py` e endpoints
intocados (diff = só `static/index.html`, +168/−66; conferido pela Vera).

**Implementado:** o acordeão vertical de cards deu lugar a **lombada** (as 19 etapas de
`ETAPAS_PRINCIPAIS`, uma aba por etapa com dot de status) + **tela cheia** da etapa selecionada
(cabeçalho com badge de status, nome, cronograma `_cronoLabelEtapa`; corpo = o MESMO switch de
`_renderCard*` de antes — movido p/ `_fichaCorpoEtapa`, não reescrito). **Decisão de design
registrada:** os 3 estados usam TOKENS SEMÂNTICOS distintos em vez do `--accent` em dois
tratamentos — não-iniciada `--text-3/--surface-2/--border-strong` · andamento
`--info/--info-soft/--info-line` · concluída `--ok/--ok-soft/--ok-line`; `.ind-conclusao`
permanece INTOCADO (outras telas dependem dele) — classes novas `.ficha-*`. Seleção default =
primeira etapa não concluída (`_fichaEtapaAtual`); troca de projeto reseta. **Sub-abas** da 11
(Visão geral + 11a–11e) e da 17 (17a) como mini-fichário dentro do conteúdo. **Placeholder**
"Etapa não iniciada" em etapa futura (não chama `_renderCard*` — zero botões/inputs, conferido).
Faixa "✓ Concluída em DD/MM/AAAA" padronizada. Preservados: barra de ações do projeto, tag "com
a bola", `toggleCicloCard` virou alias de `_fichaSelecionar` (deep-links tipo "abrir na etapa 7"
seguem funcionando), efeitos sob demanda (`carregarDadosContrato` na 7, `peComplementoRender`
na 11e) disparam na seleção via `_fichaEfeitos`.

**QA (Vera, relatório completo na sessão):** APTA — paridade de constantes JS×backend, 18/18
medidas de token via getComputedStyle nos DOIS temas (valores distintos entre estados e entre
claro/escuro), placeholder sem ações, deep-link ok nos 3 projetos, estados da lombada validados
contra réplica independente do `_statusFichario` sobre o JSON da API (3×19 abas + 12 sub-abas,
zero divergência), console pageerror ZERO, `check-design-tokens` ✔, pytest de ciclo/arquitetura
verde. Suíte completa **1646+8 verde** (1 error de colisão de execuções paralelas no
`orizon_test`; isolado, passa).

**Achados registrados (não são desta frente):** (a) 🟡 `PATCH /orcamentos/<id>/valor` → 403
recorrente no console ao abrir projeto com contrato assinado — auto-save do preview de pagamento
(`agendarSalvarPagamento`/`ativarOrcamento`) dispara e o servidor rejeita (orçamento travado
pós-contrato); PRÉ-EXISTENTE, fora do diff — tratar como pendência própria. (b) Sub-etapa de mãe
desbloqueada sem status aparece "em andamento" (fórmula da spec §3.2, igual ao acordeão antigo);
se quiserem sequenciamento visual dentro do PE, é decisão de produto futura.

**Verificação manual pendente (sem massa de dados p/ testar leitura-só):** projeto 100% concluído
(etapa 21) e reabertura por gerente com cascata (`codigos_a_resetar`) — o front recalcula
`_statusFichario` a cada `carregarCiclo`, mas vale o olho humano nesses 2 fluxos.

## Sessão 131 — Revisão de UX da F7/Chat Interno (feedback do usuário sobre a Sessão 130)

**Feedback:** o seletor de segmento só mostrava "comercial" (populava dos dados); as abas
misturavam conceitos; faltava como arquivar; e o ciclo Pendente→Iniciar→Concluir do HuntPilot
"mistura ideias". **Decisões do usuário** (registradas como revisão na spec de unificação):
abas IDÊNTICAS nos dois canais — **Pessoais** (1:1; o nome escolhido) · **Grupos** (grupo+projeto)
· **Arquivadas**; **Pendente é FILTRO** (recebida sem resposta), não estado; responder/transferir/
concluir são AÇÕES do funcionário; camada destacada de botões concentra os componentes exclusivos
do Chat Interno (Nova mensagem · **Mural** — saiu das abas, com badge — · Fórum da Loja · Fórum
Orizon · Administração).

**Implementado:** (a) `serializar_conversa`/`listar_inbox` ganham `pendente` (última mensagem não
é do viewer) e `arquivada` (flag POR usuário — a coluna `ConversaParticipante.arquivada` existia
no schema sem uso); (b) `arquivar_conversa` + `POST /api/comunicacao/conversas/<id>/arquivar`
(mural/fóruns não arquivam; só participante; 404 cross-loja) + botão Arquivar/Desarquivar no
thread — "concluir" um atendimento hoje = arquivar (reversível; status formal com dono do
atendimento segue no backburner do RF-12); (c) abas unificadas `_OC_TABS` + `_ocDaTab` nos dois
canais, chip-filtro **Pendentes** em ambos, seletor de segmento SEMPRE com os 7, fila de triagem
no topo de **Pessoais**, Mural via botão (`ocAbrirMural`) com badge de não-lidos; rótulo do badge
de tipo "Individual"→"Pessoal". `tests/test_chat_arquivar.py` (+4). Bateria de chat 88 verde;
`node --check` ok.

**Rodada 2 (mesmo dia):** trocar de aba abre a PRIMEIRA conversa da aba (nos dois canais, ida e
volta); **"+ Nova mensagem" eliminado** — modelo WhatsApp: na aba Pessoais do Chat Interno os
usuários da loja sem conversa aparecem sob a seção "Usuários" e o clique abre/cria a 1:1 na hora
(`ocAbrirUsuario`, compositor já editável); grupo continua nascendo pelo botão **Novo Grupo** da
camada de ações (formulário só-grupo, sem rádios Individual/Grupo); **busca padronizada** nos dois
canais, cada um com seu público (Interno: conversas+usuários; Atendimentos: título/projeto/prévia
+ triagem por remetente/texto).

**Rodada 3 (mesmo dia):** **segmento virou SELETOR** — coluna `Conversa.segmento` (manual vence o
derivado; `_atendimento_meta` respeita), seletor no header do thread p/ GERÊNCIA (endpoint
`POST /conversas/<id>/segmento`; vazio volta a derivar), seletor na resolução da triagem
pré-preenchido pelo `segmento_sugerido` (o escolhido vence o indicado; sem nenhum, a gerência
trata depois — pedido do usuário). **"Adicionar Contato"** na camada de ações dos Atendimentos:
nome + WhatsApp/e-mail + **motivo obrigatório** (vira evento `contato_adicionado` na conversa) +
projeto opcional + segmento — cria **Cliente no cadastro** (mais uma fonte de contatos) e o
participante EXTERNO na conversa do projeto (ou grupo de lead); resposta do número roteia à
conversa (`mod_chat.adicionar_contato`, `POST /api/comunicacao/contatos`).
`tests/test_chat_contato_segmento.py` (+5). Suíte completa **1641 verde**.

**Rodada 4 (mesmo dia):** **segmento = CANAL DE ENTRADA** com gestão própria — (a) guard de face
externa em `definir_segmento`: grupo/chat interno NÃO tem segmento (seletor do thread só com
face externa + gerência); (b) `segmento_config.responsavel_funcionario_id` (RESPONSÁVEL por
segmento, funcionário da loja; roteamento automático fica p/ F6); (c) tela Segmentos com
"+ Novo segmento" (custom da loja, slug do rótulo) e apagar (só custom — conversas voltam a
"sem segmento"; os 7 base sustentam templates/Meta e só desativam); (d) seletores da
F7/triagem/contato dinâmicos via `GET /api/comunicacao/segmentos/ativos` (qualquer usuário);
validações (triagem config, definir_segmento) aceitam customs da loja.
`tests/test_chat_segmentos_crud.py` (+5). Suíte completa **1647 verde**; headless validado
(seletor oculto em conversa interna; tela com responsável/novo/apagar).

**Rodada 5 (mesmo dia):** **aba "Todas" da gerência** nos dois canais (Pessoais = conversas do
usuário; `ver_todas_conversas` → aba Todas: comunicação entre funcionários no Chat Interno,
atendimentos/projetos nos Atendimentos). `listar_todas_conversas` inclui tipo `projeto` +
`segmento`/`projeto_nome` (split por canal). Abrir de Todas: normal se participa, senão somente
leitura. **Painel de Administração removido** (botão/view/família ocAdmin* — a aba assume; um
caminho só). Headless: gerente vê DMs alheias na aba, operador não vê a aba. Número conectado
da loja INSPIRIUM corrigido no banco local (+55 (12) 99602-1234 — não havia registro).

**Ajuste na sequência (pedido do usuário):** o "Adicionar Contato" ganhou o campo **Tipo** — o
destino no cadastro é definido no formulário: **Cliente · Parceiro** (Parceiro + vínculo
`ParceiroLoja` com a loja) **· Fornecedor** (telefone no campo `telefone` — o model não tem
whatsapp) **· Convidado** (SEM cadastro — só participante externo da conversa; não polui as
fontes de contato). `mod_chat.adicionar_contato(tipo=...)` valida contra `CONTATO_TIPOS`; o
evento inline nomeia o tipo; endpoint devolve `cadastro_id` (NULL p/ convidado). +1 teste.
Suíte completa **1642 verde**.

## Sessão 130 — Frente Orizon Chat 2026-07-31: triagem persistente, full-page canônico, eventos do ciclo e pacote destacável

**Entrada:** orientação `.claude/orientacao-orizon-chat-v2.md` (Claude Cowork, com teste ao vivo no
sandbox e no HuntPilot real), executada na ordem da seção 6: leitura completa → 3 specs → Parte 5 →
Parte 2 → Parte 3 → Parte 4 → fechamento. Specs novas (em `docs/superpowers/specs/_geral/`, porque o
`.gitignore` engole `specs/comunicacao/` — ver ESTADO ATUAL): `2026-07-31-triagem-pipeline-entrada-design.md`,
`2026-07-31-chat-fullpage-unificacao-eliminacao-legado-design.md`,
`2026-07-31-chat-modulo-destacavel-portas-design.md`.

**Parte 5 (`2b3a41c`) — o modal morreu; um caminho só por ação.** Atendimentos e Chat Interno
viraram duas colunas (lista · thread, padrão HuntPilot) com painel de conversa ÚNICO (`#oc-pane`)
que migra entre as telas (`ocMontarPane` — ids não duplicam). Thread, nova conversa, fórum,
administração, membros (painel LATERAL — sai o `_popupOverlay`), transferência/bloqueador, anexo e
oficializar portados do modal (família `cc*` → `oc*`). As 3 portas redirecionadas: menu lateral →
`ocAbrirPagina('atend')`; botão do projeto → `abrirConversaProjeto` abre o full-page PRESERVANDO
`_alinharLojaAoProjeto` (tenancy, não cosmética); itens das listas → thread na página. Número
conectado da loja no header do thread (best-effort, gerência). Removidos `#modal-central-com`,
família `cc*` e `abrirCentralComunicacao` — busca exaustiva, zero referências vivas (a família
`cc*` do CARTÃO DE CRÉDITO da Negociação é homônima não relacionada — não confundir em greps).
Badge/heartbeat viraram `ocPollBadge`/`ocAtualizarBadgeTotal`.

**Parte 2 (`7f2d8ed`) — mensagem nenhuma é descartada em silêncio.** Tabela `triagem_entradas`
(model `TriagemEntrada`): idempotente por `id_externo` (wamid — a Meta reentrega 5-6x, comprovado),
candidatos em JSON, `segmento_sugerido` esperando a F6. `processar_entrada` PERSISTE o que não
roteia (antes o status 'triagem' morria sem rastro) e deduplica reentrega de roteada E de
enfileirada. `_rotear_com_candidatos`: a lista de candidatas não se perde; conversa de projeto
CONCLUÍDO não reabre sozinha (vira candidata → decisão humana); reply citado segue determinístico.
`_loja_da_entrada`: cliente cadastrado → loja dele; `NumeroConectado` único → loja do número;
fallback primeira loja. Resolução na F7 (aba Novos, itens de triagem antes dos não-lidos): vincular
(posta a mensagem original + `EnvioExterno` com o wamid + evento `triagem_vinculo`) · criar (lead
novo: Cliente + grupo com externo — a próxima mensagem do número roteia sozinha) · descartar
(registro auditável). Endpoints `GET /api/comunicacao/triagem/fila` e `POST .../fila/<id>/resolver`
(404 cross-loja); webhook agora LOGA o destino de cada entrada. `tests/test_triagem_fila.py` (+12,
os 7 casos obrigatórios da spec).

**Parte 3 (`ae03a28`) — o diferencial é o ciclo.** Coluna `conversa_mensagens.evento` (faixa de
sistema na timeline; render `oc-evento`). `sincronizar_grupo_da_fase`: transição re-deriva
equipe∪gerência e cada entrada/saída vira evento ("Fulano (Montador) entrou no acompanhamento —
fase Montagem"); override manual segue vencendo; gancho best-effort no PATCH da etapa.
`registrar_documento_na_conversa`: upload no ciclo vira evento `documento_registrado` com
`documento_ref_id` (gancho `_chat_registrar_documento` nos 4 pontos de criação).
`encaminhar_documento_externo`: documento segue por WhatsApp aos externos DENTRO da janela como
mídia (upload `/media` + `type=document`, config-gated); fora → erro claro pedindo template (ramo
da F3); endpoint + botão no thread. Teste que TRAVA o roteamento pós-transição (responsável muda →
mesma conversa; janela intocada). `tests/test_chat_ciclo_eventos.py` (+6).

**Parte 4 (`0c86f9b`) — módulo destacável.** `mod_chat.py`→`chat/core.py`,
`mod_chat_externo.py`→`chat/externo.py` (git mv), triagem → `chat/triagem.py`. `chat/ports.py` =
contrato host↔chat (porta ativa `identity.pode`; tenancy/assunto/storage/notify reservadas;
EventosPort pub/sub in-process best-effort). `auth.perfis` saiu do pacote (entra pela porta);
`chat_host.py` (raiz) registra os adaptadores; shims na raiz fazem bootstrap + `sys.modules` (zero
churn nos ~15 imports). RATCHET `test_chat_pacote_nao_importa_host`: dentro de `chat/` só
stdlib/libs + `database` (schema compartilhado). `modulos.py` atualizado (pacote + tabela nova).
Efeito colateral honesto: as limpezas dos e2e de ciclo/NF-e deletavam `ciclo_documentos` que os
eventos novos agora seguram por FK — cleanups passaram a desreferenciar antes (produção é
append-only; 23 falhas → 0).

**Fechamento:** suíte completa **1632 passed** (era 1613; +19 da frente). **Vera** auditou
(duplicidade, DOM, sintaxe `node --check`, tokens, app vivo com login seed, tenancy estática,
suíte-alvo): **APTA para promover à VPS**, zero 🔴; 🟡 = este DEV_LOG + re-ingestão (quitados) e o
`utcnow()` deprecado (deliberadamente NÃO corrigido pontualmente — varredura única, ver ESTADO
ATUAL). Deploy: **avisar o Cowork** (tag homolog + deploy VPS B + E2E WhatsApp real); produção
segue gated.

## Sessão 129 — Orizon Chat/Meta (UI-first): Números, Consumo, Atendimentos (F7) e Chat Interno full-page
Continuação da frente **Revisão do Orizon Chat — Meta/WhatsApp** (plano
`docs/superpowers/plans/2026-07-28-orizon-chat-revisao-meta.md`), em modo **UI-first** (backend de envio
fica para a Vera/TDD). Tudo promovido à **VPS A** ao longo da sessão, com auditoria da Vera antes de cada
promoção. Entregas:

- **Correções da 1ª auditoria da Vera (`22873ce`):** `mod_chat_externo.janela_da_conversa` reescrita para
  escopar pela CONVERSA (join `EnvioExterno→ConversaMensagem→conversa_id`) — não vaza mais a janela de 24h
  entre lojas da mesma rede com o mesmo número; `segmentos_config_salvar` só aceita template ATIVO como
  padrão + `remover_template` limpa o `slot_obrigatorio`.
- **Números Conectados (RF-01, `16de36e`):** tabela `numero_conectado` (1 por loja) + `mod_chat.
  numero_conectado_get/salvar` + `_status_transporte_whatsapp` + `GET/POST /api/comunicacao/numeros`
  (gerência, tenancy) + tela no `#page-chat`. Número exibível editável por loja; **status do transporte
  Meta como booleanos** — os secrets (`ORIZON_WA_TOKEN`/`ORIZON_WA_PHONE_ID`) ficam em variável de
  ambiente e **NUNCA** saem no JSON (teste prova o não-vazamento). Número real da loja: **+55 12 996049888**.
- **Consumo / Custos (§10, `431bd1e`):** `mod_chat.consumo_por_segmento` (agrega `EnvioExterno` WhatsApp/
  saída × status, escopado por `Conversa.loja_id`) + `GET /api/comunicacao/consumo` + tela. Sem R$ de
  propósito (tarifa Meta varia por categoria/país, não cadastrada).
- **Atendimentos full-page (F7/RF-12, `b7a4dc9`):** `listar_inbox` enriquece cada conversa não-mural com
  `segmento` (canal do último externo) e `janela` (na/aberta/fechando/fechada) via `mod_chat._atendimento_
  meta`. Tela full-page no `#page-chat` (sidebar Comunicação → Atendimentos sai do modal): abas Novos/Meus/
  Grupos/Arquivados + filtro por segmento + selos (segmento, Janela aberta/fecha em Xh/fechada, Vinculado ao
  Projeto); clique reusa a thread do modal. Limites honestos: aba Arquivados vazia (`Conversa` sem coluna de
  arquivo) e aba "Outros" adiada (exige inbox loja-wide + atribuição de atendente).
- **Correção da auditoria da Vera na F7 (`b6d98ad`):** 🟠 a resposta do FUNCIONÁRIO pela ponte
  (`processar_entrada_usuario` grava entrada `canal='interno'`) inflava a janela como se o cliente tivesse
  voltado; `janela_da_conversa` agora exclui `canal='interno'` (mantendo entrada do cliente com
  segmento/NULL) + teste. 🟡 `atendAbrir` ganha `showToast` quando a conversa some do inbox.
- **Chat Interno full-page (`90755c2`):** sidebar Comunicação → Chat Interno sai do modal antigo e vira
  tela full-page espelhando Atendimentos — abas Todas/Individuais/Grupos/Mural (só tipos de equipe;
  projeto fica em Atendimentos), barra de ações (Nova mensagem/Fórum da Loja/Fórum Orizon/Administração com
  o mesmo gating do modal), clique reusa a thread do modal. Modal segue como motor de thread/nova/fórum/
  admin até a aposentadoria final.
- **Backburner registrado** (não bloqueia): perf de `_atendimento_meta` (~2 queries/item; gerência é
  auto-participante de toda conversa de projeto fechado → medir/paginar antes de produção); semântica plena
  de triagem/atribuição do RF-12 (abas Novos=não-lidas / Meus=não-grupo até existir "dono do atendimento").

Suíte **1613 verde** (Postgres). `node --check` verde nas telas. **Vera** auditou cada leva (veredito "pode
promover" nas três). **Estudo do Hunt** (avaliação ao vivo do usuário) recebido como insumo — Vera **não**
tem login no app autenticado, então a rodada complementar aguarda prints do usuário. **VPS B / produção
seguem pendentes de OK.**

## Sessão 128 — Fatias 6-7 CONCLUÍDAS (código): transportes ao vivo SMTP + Meta WhatsApp
Implementado o `despachar()` real (a última peça): **e-mail via smtplib** (STARTTLS, login,
send_message; Message-ID gerado + In-Reply-To/References quando é resposta — threading da decisão
14 no e-mail) e **WhatsApp via Meta Cloud API** (POST graph.facebook.com/v20.0/<phone>/messages,
Bearer token, parse do wamid). **5 endereços/números por canal = override de env**
(`ORIZON_SMTP_FROM_<CANAL>`, `ORIZON_WA_PHONE_ID_<CANAL>`; fallback à base) — config, não código.
Exceção de rede → envio 'falhou' com a mensagem; sem credencial → 'pendente_config' (rede
intocada). Testes com **boundary de rede mockado** (smtplib.SMTP e urllib.urlopen): e-mail
montado certo (To/From/corpo), override por canal, WhatsApp com URL/Bearer/payload corretos e
wamid retornado, falha vira erro, sem-config não toca a rede — 16 testes de canal externo no
total. **Fatias 6-7 ficam completas em CÓDIGO e testadas**; para ir ao ar falta só: credenciais
SMTP e WhatsApp por ambiente + aprovação da Meta (ação do usuário). Nenhuma dependência nova
(smtplib/urllib são stdlib).

## Sessão 127 — V_pre_teste + deploy A/B + Fatias 6-7 (fundação dos canais externos)
**Tag `V_pre_teste`** criada no HEAD (9e13753) e no GitHub. **Deploy A/B** (167.88.33.121) via
deploy_ab.sh: A=integração(:8765, main), B=pré-homolog(:8766, tag V_pre_teste); ambos 200
externo. **Chave do modo privado configurada** nos envs (`/root/orizon-A.env`, `/root/orizon-B.env`)
a partir de `keys/orizon_chat_enc_key_{A,B}.txt` — confirmado carregada nos dois processos; o
backfill de funções (Ajudante de Montagem) rodou no restart. MCP re-ingerido.
**Fatias 6-7 — FUNDAÇÃO testável (spec seção 6c/6d):** modelo **`EnvioExterno`** (tabela nova —
create_all cuida; sem migração de coluna); **`mod_chat_externo.py`** com **config-gating** por
meio (`meio_configurado`: SMTP p/ email, Meta p/ whatsapp — sem credencial, envio nasce
`pendente_config`, a rede NÃO é tocada, nunca um 'enviado' fantasma), **`resolver_destino`**
(seletor interno/parceiro/cliente/avulso — decisão 19, contato do cadastro ou avulso, erro claro
sem contato), **`rotear_entrada`** (decisão 14: reply citado > número com 1 conversa ativa >
triagem humana). `enviar_mensagem` relaxado só via `_permitir_externo` (canal externo exige a
porta de saída registrada). Endpoint POST `.../conversa/mensagens/externo`. Frontend: compositor
de canal externo (meio/canal/destinatário filtrado + avulso), rótulo do canal na linha do tempo,
exclusivo da transferência. Testes `tests/test_chat_externo.py` (7). **Transportes AO VIVO
pendentes de credencial (AÇÃO DO USUÁRIO, por ambiente):** e-mail `ORIZON_SMTP_HOST/PORT/USER/
PASS/FROM`; WhatsApp `ORIZON_WA_TOKEN/PHONE_ID/VERIFY_TOKEN` + **aprovação da Meta** (prazo
externo). `despachar()` e o webhook de entrada ficam prontos-para-ativar (a lógica de roteamento
já é testada). Registrado no relatório ao usuário.

**Entrada (resposta externa) — também construída/testada:** `processar_entrada` (roteia por
rotear_entrada e persiste a resposta como Mensagem autor-NULL + EnvioExterno direcao=entrada;
ambíguo → triagem, sem criar mensagem) e o **webhook** `GET/POST /webhooks/whatsapp` (Meta Cloud
API): GET = handshake de verificação (ORIZON_WA_VERIFY_TOKEN); POST = **dormiente sem
ORIZON_WA_TOKEN** (só ack), e quando configurado exige **assinatura HMAC** X-Hub-Signature-256
(ORIZON_WA_APP_SECRET) antes de parsear e rotear. `iter_mensagens_whatsapp` parseia o payload
aninhado. 11 testes no total (incl. handshake, inerte-sem-config, roteamento com assinatura
válida, e 403 com assinatura inválida). O único bloqueio real para ativar o WhatsApp é a
credencial+aprovação Meta (ação do usuário); o e-mail, as credenciais SMTP.

## Sessão 126 — Equipe de Montagem filtrada por função + Grupo de Acompanhamento com equipe interna
**Feedback do teste (2 pontos).** (1) **Seletor de Equipe de Montagem** ofertava TODOS os
funcionários da loja; agora só **Montador** e **Ajudante de Montagem** (o Supervisor já é papel
próprio/automático). Função nova **"Ajudante de Montagem"** entra em `FUNCOES_PADRAO`; como não
havia backfill de funções para lojas EXISTENTES (só na criação da loja), criei
`database.backfill_funcoes_todas_lojas` (idempotente, roda no `init_db` após
`_backfill_funcao_flags`) — semeia funções novas do catálogo em todas as lojas. Novo
`mod_equipe.candidatos_montagem` (funcionários só das `FUNCOES_MONTAGEM` + todos os terceiros —
mão de obra terceirizada); GET /equipe passou a devolver `candidatos_montagem` e o multi-select
de montagem no frontend usa essa lista. (2) **Grupo de Acompanhamento** agora inclui os
**integrantes da loja que participam**: seção "Equipe interna" no painel, montada a partir do
roster do GET /equipe (reuso, sem endpoint novo), acima da seção "Externos" (cliente/arquiteto).
**Incluir pessoas avulsas** segue para as Fatias 6-7. Testes:
`tests/test_equipe_montagem_filtro.py` (4). Backfill aplicado no banco LOCAL (lojas 2/3/4 estavam
sem funções — agora com catálogo completo, todas com Ajudante de Montagem). Nos VPS/produção o
backfill roda no próximo restart do serviço.

## Sessão 125 — Fix UX do gate de contatos + "Grupo de Acompanhamento" no ciclo (teste do usuário)
**Bugs do teste (frontend-only):** (1) o modal de confirmação de contatos usava `.modal-overlay`
(z-index 400), mas dispara DENTRO do fluxo de aprovação do contrato, cujos modais são
`_popupOverlay` em z-index 99999 → o de contatos renderizava ATRÁS, visível o bastante para
travar o fluxo e invisível o bastante para confundir. Corrigido: `z-index:100001`. (2) Painel
"mal diagramado" → reforma: cartões com ícone/rótulo/WhatsApp/e-mail, título "Grupo de
Acompanhamento", nota de rodapé sobre origem no cadastro e evolução nas fatias 6-7. (3) "Só o
cliente aparece" NÃO é bug — o arquiteto só entra quando o projeto tem `parceiro_id`; agora,
sem arquiteto, o painel mostra estado explícito "Nenhum arquiteto associado" + link "Associar
arquiteto" (reusa `abrirAssociarParceiro`). **Feature pedida:** botão **"Grupo de
Acompanhamento"** no topo do ciclo reabre o painel em modo VISUALIZAÇÃO (botões "Fechar"/
"Reconfirmar"); o modo GATE (durante o contrato) segue com "Seguir sem WhatsApp"/"Confirmar".
Um só `abrirModalContatosConf(onDone)`: com callback = gate; sem = visualização. **Incluir
outras pessoas no grupo fica para as Fatias 6-7** (canais externos), como o usuário sinalizou —
por ora o painel só exibe cliente/arquiteto do cadastro. Sem mudança de backend.

## Sessão 124 — Chat: revisão do teste — criador com a bola + passagem automática de fase
**Feedback do teste, mantendo tudo Funcionário-based** (a ideia de mover responsabilidade p/
Usuário foi levantada e DESCARTADA pelo usuário — spec decisão 16 revertida; sem pivô, o v12
segue intacto). **Item 1 — "com a bola" nunca mais "não atribuído":** a cadeia de resolução do
responsável por etapa (GET /ciclo) ganhou o CRIADOR do projeto como último degrau
(`Projeto.criado_por_id` → Funcionário pela ponte `Usuario.funcionario_id`); precedência
preservada (override > Mapa > faixa > criador). Quando o criador não tem Funcionário vinculado,
o endpoint expõe `criado_por_nome` e a tag mostra o nome do usuário criador "(criador)" — só
exibição, a responsabilidade formal segue por Funcionário. **Item 2 — passagem oficial
automática (decisão 17):** concluir uma fase no `PATCH /ciclo/<cod>` posta na Conversa uma
mensagem `natureza=transferencia` apontando a PRÓXIMA etapa principal (`mod_ciclo.etapa_seguinte`,
novo) e o responsável dela (mesma resolução, extraída em `_responsavel_funcionario_etapa`);
só documenta — NÃO grava `responsavel_funcionario_id` da próxima (o default segue resolvendo);
best-effort (falha na mensagem não derruba a conclusão da etapa); última fase ou próxima sem
responsável → não posta nada. **Código sensível:** baseline da suíte de ciclo (56) IDÊNTICA
antes/depois. Testes: `tests/test_responsavel_criador_transicao.py` (5). Spec atualizada
(decisões 16 revertida/17, seção 6b).

## Sessão 123 — Chat Fatia 5: documento compartilhável na transferência
**`documento_ref_id` virou FK REAL** de `ciclo_documentos` (modelo + constraint nas bases
existentes via DO-block idempotente no `_migrar_colunas_pg` — ADD CONSTRAINT não tem IF NOT
EXISTS). Segue válido SÓ em `natureza=transferencia` (regra da Fatia 2, inalterada e
retestada). **Validação no envio:** o documento precisa ser do MESMO `projeto_nome` da
conversa — de outro projeto (ou inexistente) = 400, sem vazar referência entre projetos.
**Serialização resolve** `documento_nome`/`documento_tipo` (batch na listagem; não sai id
cru). **Frontend:** seletor "Anexar documento" no compositor de transferência (populado pelo
`GET /ciclo/pe`, que já devolve TODOS os CicloDocumento do projeto com tenancy — nenhum
endpoint novo) e chip com clipe na linha do tempo linkando o download existente
(`GET /ciclo/documento/<id>`, com as checagens que ele já faz — nada duplicado). Testes:
`tests/test_chat_fatia5.py` (3). Com esta fatia, restam da spec só os CANAIS EXTERNOS
(Fatias 6-7, e-mail e WhatsApp) — `enviar_mensagem` segue recusando canal ≠ interno.

## Sessão 122 — Chat Fatia 4: modo privado (criptografia real no servidor)
**Spec seção 4 / decisão 8.** `ConversaMensagem` ganhou `privada` + `corpo_cifrado` (ADD
COLUMN idempotente). Privada=True cifra com **Fernet** (`cryptography`; entrou no
requirements.txt e na linha apt como `python3-cryptography`) usando a chave da env
**`ORIZON_CHAT_ENC_KEY`** — o corpo em claro NUNCA persiste (fica `""`; teste bate no banco
pra provar). **Sem a chave no ambiente, o envio privado FALHA com erro claro** ("Modo privado
indisponível — chave de criptografia não configurada") — deliberadamente SEM fallback de
chave descartável, que tornaria as mensagens ilegíveis para sempre no próximo restart.
**⚠ REQUISITO DE DEPLOY:** a `ORIZON_CHAT_ENC_KEY` precisa existir nos 3 ambientes
(integração `/etc/systemd/system/orizon-a.service`, pré-homolog `orizon-b.service`, produção
`orizon.service` — Environment= no unit, ou nos envs `/root/orizon-A.env`/`-B.env`) ANTES de
alguém usar o modo privado nesses ambientes; chave gerada com
`python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
(uma POR ambiente; ajuste manual do usuário, fora do código). **Quem decripta:** capacidade
NOVA `ver_mensagem_privada` (True master+gerencial, False operador/default; em CAPACIDADES e
CAPS_SELECIONAVEIS → aparece e é sobreponível na matriz Admin › Perfis; decidido via
`perfis.pode`, nunca comparação de string de nível). Metadados (autor/natureza/etapa/
destinatário/bloqueador) seguem visíveis a todos — transferência privada continua gravando
`responsavel_funcionario_id` normal; só o TEXTO é secreto: quem não pode vê a MÁSCARA fixa
("🔒 Mensagem privada — visível apenas à gerência"), nunca o cifrado bruto; chave trocada no
ambiente → máscara própria ("não foi possível decifrar"), sem 500. Frontend: checkbox
"Privada 🔒" (vale p/ interação e transferência), cadeado sempre visível na linha do tempo,
tag "privada" discreta pra quem lê o claro, SEM botão de revelar. Testes:
`tests/test_chat_fatia4.py` (5).

## Sessão 121 — Chat Fatia 3: bloqueador como GATE REAL em pode_avancar (código sensível)
**Protocolo de rigor cumprido:** baseline da suíte de ciclo ANTES de tocar (56 verdes:
test_ciclo, test_ciclo_faixas, test_ciclo_operacional_e2e, test_ciclo_pe_e2e) e regressão
DEPOIS — comportamento idêntico, incluindo teste explícito de que `pode_avancar` SEM o
parâmetro novo é igual ao anterior (default None; set vazio ≡ None).
**Implementado:**
- **`mod_ciclo.pode_avancar(codigo, status_por_codigo, bloqueadores_ativos=None)`** —
  retrocompatível; set de etapas com bloqueador ativo; **`"*"` = bloqueador SEM etapa, trava o
  ciclo INTEIRO** (decisão de design mantida como a spec da sessão pediu: transferência
  bloqueadora sem etapa não tem alvo específico → o conservador é travar tudo, que é o
  comportamento de emergência esperado). Bloqueador vence tudo (False antes das outras
  checagens); sub-etapa herda o da mãe pela recursão de sempre.
- **`mod_chat.bloqueadores_ativos(db, projeto)`**: transferências bloqueadoras não resolvidas
  → set de etapas ('*' quando sem etapa). O PATCH do ciclo monta o set e passa ao
  pode_avancar; quando a causa é o bloqueador (sem ele teria passado), o erro é DISTINTO
  ("Bloqueador ativo — resolva a transferência na Conversa…", `codigo: bloqueador_ativo`) —
  não se confunde com "Conclua a etapa anterior".
- **Resolução normal** `POST .../conversa/mensagens/<id>/resolver`: EXCLUSIVA de quem recebeu
  (ponte Usuário↔Funcionário generalizada em `_funcionario_do_usuario` — o
  `_consultor_funcionario_id` da Fatia 2 agora a reusa); outro usuário = 403; valida
  bloqueador/não-resolvida; seta `resolvido_em`.
- **Válvula de emergência** `POST .../destravar-emergencia`: `_usuario_com_capacidade(...,
  "autorizar", sessao=)` (sessão-primeiro, master/gerencial — capacidade EXISTENTE, nenhuma
  nova), `motivo` obrigatório (400 sem), `LogAcaoGerencial(acao="destravar_bloqueador",
  etapa_alvo, contexto={mensagem_id, motivo})`. Funciona sem ser o destinatário (o objetivo).
- **Frontend:** compositor de transferência no painel da Conversa (etapa opcional +
  destinatário + checkbox bloqueador com aviso de que trava o ciclo — e de que sem etapa
  trava TUDO); linha do tempo com badge vermelho "BLOQUEADOR ATIVO" + botões Resolver (todos
  veem; backend faz o 403 falar) e "Destravar (emergência)" (só master/gerencial via
  `_podeAutorizarFront`, reusando `pedirCredenciaisGerente` sessão-primeiro + motivo);
  bloqueador resolvido vira selo verde com data. `_patchEtapa` intercepta
  `codigo=bloqueador_ativo` e oferece "Abrir Conversa" (confirmarPopup) — causa distinta da
  trava sequencial na tela, como pedido.
**Testes novos:** `tests/test_chat_fatia3.py` (9 — cobre o checklist a-f do pedido, inclusive
o log de auditoria e a liberação do avanço após resolver).

## Sessão 120 — Chat Fatia 2: Responsabilidade + transferência (extensão do v12, spec seção 6)
**Implementado exatamente como a seção 6 manda — estender, nunca duplicar:**
- **`ConversaMensagem` ganhou** `natureza` (interacao|transferencia), `etapa_codigo`,
  `transferido_para_funcionario_id`, `documento_ref_id`, `bloqueador`, `resolvido_em`
  (ADD COLUMN idempotente no `_migrar_colunas_pg` — a tabela da Fatia 1 já existe nas bases).
- **Transferência oficial escreve NO v12**: mensagem `transferencia` com `etapa_codigo` grava
  `CicloEtapa.responsavel_funcionario_id` da etapa (o MESMO campo do override manual — chat e
  tela são a mesma operação por baixo). Validações no endpoint: destinatário obrigatório e DA
  LOJA; etapa precisa existir no ciclo do projeto; interação RECUSA campos de transferência
  (quem achou que transferiu precisa saber que não transferiu). **Decisão técnica:** a
  restrição por Função do override do painel NÃO se aplica à transferência do chat, de
  propósito — transferir ENTRE faixas é a razão de existir dela.
- **Defaults por FAIXA** estendendo o `_ETAPA_PAPEL` no `GET /ciclo` (resolve-e-cacheia por
  request): Vendas (1,2,3,4,7) = `Briefing.consultor_id` → ponte `Usuario.funcionario_id`
  (fallback reverso `Funcionario.usuario_id`; consultor sem funcionário → sem default, sem
  erro) · Financeiro (8, 11d, 21) = Função "Gerente Administrativo/Financeiro" · Logística
  (12-16) = Função "Assistente Logístico". Precedência intacta: override/transferido > Mapa
  de Atribuições > default de faixa > nada.
- **SAC fora do v12**: `mod_chat.responsavel_sac(db, loja_id)` via Função "SAC" (helper
  genérico `funcionario_por_funcao` — ativo, 1º da loja; >1 pega o primeiro, regra da spec).
- **Bloqueador SÓ grava o flag** — `pode_avancar()` NÃO foi tocado; teste de regressão prova
  o comportamento idêntico com mensagem bloqueadora gravada (o gate real é a Fatia 3).
- **Tag "quem está com a bola"** no topo da tela do Ciclo: responsavel_efetivo da primeira
  etapa não-conclusiva (dado do GET /ciclo de sempre; "não atribuído" em âmbar; "Ciclo
  concluído" quando tudo fechou). Sem campo novo em Projeto.
**Pendências anotadas:** UI de ENVIO de transferência no painel da Conversa (seletor de
etapa/destinatário) ficou de fora do escopo desta sessão — o endpoint está pronto; entra
junto da Fatia 3 (bloqueador precisa da UI de resolução de qualquer jeito). `resolvido_em`
só existe como coluna (fecha na Fatia 3).

## Sessão 119 — Confirmação de contatos na fase de contrato (decisão 13 antecipada, mini-frente)
**Aprovada pelo usuário com "seguir sem WhatsApp" aceito.** Implementado: tabela
**`contato_confirmacoes`** (append-only, a mais recente vale; snapshot `contatos_json` do que
o operador VIU — o dado vivo segue no cadastro, decisão 12) no módulo `chat`;
`mod_chat.contatos_do_projeto` (cliente via `Projeto.cliente_id`, arquiteto via
`parceiro_id` do projeto.json — Parceiro usa `whatsapp` com fallback telefone; **Cliente
ainda não tem campo WhatsApp próprio: o telefone é o candidato exibido**, campo dedicado
fica pra fatia dos canais); endpoints GET `/api/projetos/<n>/contatos-comunicacao` (contatos
vivos + confirmação vigente) e POST `.../confirmar` (`modo` confirmado|sem_whatsapp).
**Gate BLOQUEANTE-SUAVE no POST do contrato** (o handler REAL de geração — cuidado de rota:
há um PATCH homônimo p/ adendo que NÃO ganhou gate): sem confirmação → 400 com
`codigo: contatos_nao_confirmados`; o frontend intercepta, abre o modal (lista contatos com
aviso de WhatsApp faltando, botões "Confirmar contatos" / "Seguir sem WhatsApp") e re-chama
`gerarContrato` com os MESMOS argumentos após o registro. Nunca passa sem ver; sempre há
saída explícita. Testes: `tests/test_confirmacao_contatos.py` (4) + 2 e2e de contrato
existentes atualizados para confirmar antes de gerar (como o fluxo real). Spec: decisão 13
marcada como FECHADA (bloqueante-suave).

**Duas pegadinhas desta sessão:** (1) o import local `from integracoes.projetos_store import
_carregar_projeto` SEM alias tornou o nome local ao do_POST/do_GET inteiros e derrubou 11
testes de parceiro/escopo — a MESMA armadilha de escopo já documentada no preview do
construir_contexto; corrigido com alias `_cp_chat` e comentário-sentinela. (2)
`test_perfis::test_acesso_matriz` estava DEFASADO da decisão "Operador sem Fiscal" (sessão
paralela de 2026-07-24, que mudou o perfil sem atualizar o teste — passava por sorte de cache
do registro); teste atualizado à decisão vigente.

**Correção do mesmo dia (pedido "adicione o whatsapp do cliente"):** constatado que o campo
JÁ EXISTIA de ponta a ponta (coluna `clientes.whatsapp` pré-Postgres, modal `cli-wpp` com
máscara, criar E editar persistindo) — a nota da S119 estava ERRADA. O gap real era o
`contatos_do_projeto` ignorar o campo: agora usa `whatsapp` com fallback telefone (teste
cobre a preferência). Spec (decisão 12) corrigida.

## Sessão 118 — Chat do Orizon, Fatia 1 (Fundação): Conversa por projeto + mensagens internas
**Spec `_geral/2026-07-25-chat-projeto-porta-externa-whatsapp-email-design.md` (decisões 1-10
fechadas — nada foi reaberto).** Implementado SÓ o escopo da Fatia 1: **modelo** `Conversa`
(âncora flexível: `projeto_nome` e `cliente_id` AMBOS opcionais — cobre projeto, cliente sem
projeto e reclamação institucional sem vínculo) + `ConversaMensagem` (autor, corpo, canal,
criado_em); **endpoints** GET `/api/projetos/<nome>/conversa` (get-or-create idempotente +
histórico ASC) e POST `.../conversa/mensagens` (guardas iguais às do ciclo: sessão + escopo +
`_projeto_da_loja`); **UI**: botão "Conversa" na barra do projeto (ao lado de Etapas do
Projeto/Reconciliação) abrindo painel-modal com histórico cronológico (balões, minhas à
direita) e campo de nova mensagem (Enter envia, Shift+Enter quebra). TDD:
`tests/test_chat_fundacao.py` (8: âncora flexível, idempotência, validações, cronologia,
tenancy 404, 401).
**Decisões técnicas DESTA sessão (não estavam na spec):**
- `Conversa.loja_id` obrigatório (tenancy — a reclamação institucional pertence à loja que a
  registrou; a spec não citava o campo).
- Tabela de mensagem = **`conversa_mensagens`** ("mensagens" seco era genérico demais).
- Módulo **`chat` registrado como NÚCLEO** no manifesto (`modulos.py`) — comunicação
  transversal, sempre ligada; promover a domínio se um dia for desligável por loja.
- Coluna `canal` já nasce no modelo (é do consolidado da spec), mas o **backend recusa**
  canal ≠ 'interno' (não é só a UI que esconde — a validação relaxa nas fatias 6-7).
- `cliente_id` da conversa é herdado do projeto NA CRIAÇÃO (vínculo de nascença, não
  sincronização posterior).
- `autor_usuario_id` NULL fica RESERVADO para resposta externa (fatias 6-7); nenhum caminho
  interno cria mensagem sem autor.
- UI sem polling: o histórico atualiza ao abrir e após enviar — tempo-real/polling fica como
  melhoria de UX para quando o chat tiver mais gente simultânea (anotar na Fatia 2+).
**Adendo à spec (mesmo dia, validado pelo usuário):** decisões 11-14 registradas —
arquiteto é participante externo DERIVADO do `parceiro_id` do projeto (nada por conversa);
contatos externos vêm do CADASTRO (nunca do contrato — Parceiro já tem `whatsapp`; Cliente
ganha o campo quando o canal chegar); **confirmação de contatos na fase de contrato**
(verifica preenchimento e pede confirmação explícita do canal, com registro de quem/quando —
travar × avisar fica pra implementação); threading de resposta externa: reply citado é
determinístico, resposta solta ambígua cai em fila de TRIAGEM humana (v1 sem bot); N projetos
do mesmo arquiteto = N conversas (âncora no projeto já garante).
**Pendente para a Fatia 2 (não implementado de propósito):** `natureza`
(interacao|transferencia) + campos da transferência; resolução da pessoa responsável pelos 3
mecanismos já mapeados na spec (Consultor/`AtribuicaoAmbiente`/Função p/ Financeiro-Logística-
SAC); tag "quem está com a bola" no topo do Ciclo. Nada da fundação bloqueia a Fatia 2 — o
modelo foi desenhado para ganhar as colunas novas por `_migrar_colunas_pg` (ADD COLUMN
idempotente), sem recriar tabela.

## Sessão 117 — PRODUÇÃO atualizada + domínio www.orizonone.com.br no ar (troca EXECUTADA)
**Acesso SSH à produção liberado** (chave desta máquina autorizada pelo usuário via painel;
login por senha segue desabilitado). **Deploy:** backup fresco (`backup_orizon.sh`, 12:48) →
produção saiu do `c9f3324` (≈S8x!) para a tag **`v2026.07.24-prod`** (= `1476fe4`, main) —
salto de ~30 sessões; migrações idempotentes aplicaram no start (conferido no banco: perfis
"Gerente" ✓, `documento_tipos` criada ✓; plano de contas ainda sem owner — nasce direto no
formalismo no 1º acesso ao Financeiro). Serviço `orizon.service` ativo, 302 local. **Troca de
domínio executada** (runbook S116): site nginx `orizonone` com `client_max_body_size 64M`
(pendência da S104 QUITADA em produção — o certbot moveu o 64M pro bloco 443, conferido),
certificado Let's Encrypt emitido p/ `orizonone.com.br`+`www`, HTTP→HTTPS, e o
`orizonsolution.com.br` virou **redirect 301** preservando o path (certs antigos renovando).
**Provas reais:** `https://www.orizonone.com.br/login` 200 · apex 200 · http→https 301 ·
antigo→novo 301 · Content-Length 100MB → 413 do nginx ✓ (o probe de 51MB headers-only não
atravessa o proxy_request_buffering — inconclusivo por natureza; o teto do app foi provado no
A/B). **Correção de informação:** o super admin de PRODUÇÃO é `mbn1972@gmail.com` (senha
própria, NÃO a do seed — conferido por hash); o `sad2026`/`trocar123` do seed não existe lá.
**Nota de segurança:** a senha do Postgres local da VPS aparece no unit do systemd (Postgres
só escuta localhost; risco baixo — rotacionar se quiser higiene extra).

## Sessão 116 — Troca do domínio de produção: www.orizonone.com.br (preparada; execução gated)
**Pedido:** trocar produção de `orizonsolution.com.br` para **`www.orizonone.com.br`**.
**Levantamento (2026-07-23):** `orizonone.com.br` → `2.57.91.91` = **parking da Hostinger**
(página "Parked Domain"; SSH nem responde — não é servidor nosso); produção segue em
`179.197.77.9` (`orizonsolution` responde 301/200). **Dois gates fora do nosso alcance direto:**
(1) **DNS na Hostinger** — criar A `orizonone.com.br` e `www` → `179.197.77.9` (hoje parking);
(2) **SSH da produção** — a chave desta máquina NÃO está autorizada em `179.197.77.9`
(Permission denied; só a VPS de dev tem). **Preparado no repo:** runbook completo da troca no
`DEV_RULES.md` ("Troca de domínio → www.orizonone.com.br"): site nginx novo `orizonone`
(80 → certbot 443) já com o `client_max_body_size 64M` PENDENTE da S104, domínio antigo virando
`return 301 https://www.orizonone.com.br$request_uri;` nos dois blocos (certs antigos seguem
renovando — o redirect no 443 precisa deles), provas reais com curl. CLAUDE.md atualizado
(produção = www.orizonone.com.br). Execução: DNS propagado + acesso (runbook manual do usuário,
ou autorizar a chave e a IA executa).

## Sessão 115 — Cadastro de Funcionários de volta ao módulo Cadastro
**Pedido do usuário:** o cadastro de Funcionários vivia como sub-aba do módulo Folha (entrada
única `cadEntCarregar('funcionarios')`, painel criado dinamicamente lá). Voltou ao **módulo
Cadastro**: seção "Funcionários" no submenu da sidebar (entre Clientes e Parceiros), aba+painel
estático na page-10, `cadTab` alternando o painel (o lazy-load já tratava 'funcionarios' desde
sempre). A Folha ficou só com a folha do mês + um atalho "Cadastro de funcionários (módulo
Cadastro)" (`cadIr('funcionarios')`); `_folhaAba`/`folhaAba` removidos. Sem mudança de backend
(a rota `/api/funcionarios` exige só sessão+escopo — quem tem o módulo Cadastro acessa).
Frontend-only (Ctrl+F5).

## Sessão 116 — UX de permissões: contexto fixa a loja, senha só quando falta permissão, operador sem Fiscal
Três decisões do usuário (2026-07-24), num commit:
**(1) Modal de usuário sensível ao contexto.** Dentro de loja/PDV o cadastro NÃO pergunta a
loja — mostra "Loja: <nome>" fixa (`loja_fixa` no ctx; salvar usa ela). No contexto amplo
(gestão geral do super_admin/admin_rede) a lista de lojas do escopo continua.
**(2) Autorização SESSÃO-PRIMEIRO.** Logado com a permissão não redigita senha; a senha
gerencial só aparece quando o logado NÃO tem a permissão (aí valem credenciais de um
terceiro que tem — fluxo antigo preservado). Backend: `_usuario_com_capacidade(...,
sessao=)` é o ponto único (+ `_aprovador_financeiro` delega; 14 call sites, os 3 blocos
inline de reabrir/desfazer/data-prevista, o override de data-entrega e o
`/api/gerente/verificar`). Frontend: `pedirCredenciaisGerente` ganha `capacidade` (default
`autorizar`; AF/razão=`aprovar_financeiro`, medição=`registrar_medicao`, decisão
comercial=`aprovar_medicao_reprovada`; cancelar contrato=null — SEMPRE pergunta) e resolve
sem modal quando `_usuarioAtual.pode_<capacidade>`; `tfAbrirModalSenha` e Rever Orçamento
idem. `auth._usuario_dict` expõe as flags novas (pode_autorizar etc.). ARMADILHA: variável
de sessão muda de nome entre handlers (`usuario`×`solicitante`) — 4 sites corrigidos após
500 no teste.
**(3) Operador sem Fiscal + painéis vedados.** Matriz (`perfis.py`) e seed
(`perfil_store.PERFIS_PADRAO`) tiram `fiscal` do operador; `backfill_perfis_todas_lojas`
remove o fiscal dos operadores de SISTEMA já semeados (custom não é tocado). Painéis:
Financeiro/reconciliação já eram vedados (acesso_financeiro); AF/provisões já exigiam
`aprovar_financeiro` no GET; Auditoria Contábil já caía no `_contabil_ctx`; agora a UI
também esconde do operador os botões Auditoria Contábil, Comparar Valores (AF2, gate
`ver_parametros`) e Concluir Conciliação Final (gate `aprovar_financeiro`).
Testes: `test_autorizacao_sessao.py` (9) + 3 expectativas antigas atualizadas
(operador×fiscal). Suíte **1446 verde**. PENDENTE: nome novo p/ o perfil `admin_rede`
(rótulo atual "Administrador de Rede") — aguardando escolha do usuário.

## Sessão 115 — PDV: Diretor da mãe acessa o Ponto de Venda como acessa a própria loja
Pedido do usuário (teste na VPS A). `database.lojas_acessiveis_ids(db, usuario_id, nivel,
loja_id)`: memberships + PDVs ATIVOS da(s) loja(s) do usuário quando ele é Diretor (base
master) — acesso DERIVADO, nada gravado em `usuario_lojas` (PDV novo/diretor novo entram
sozinhos; desativar o PDV o tira do escopo). Aplicado nos 2 consumidores: `_ator_dict`
(X-Loja-Ativa passa a aceitar o PDV → escopo operacional completo dentro dele) e
`/api/auth/me` (o seletor multi-loja da sidebar mostra o PDV). Direção ÚNICA (usuário do
PDV não ganha a mãe); gerencial/operador da mãe inalterados; cadastro do PDV segue
exclusivo do super_admin (PATCH bloqueado). Também na sessão: selo "PDV de <mãe>" na lista
de lojas da Plataforma + banner no painel Fiscal do PDV ("emissão pelo CNPJ da mãe";
`perfil-fiscal` devolve `pdv_de`) — feedback do teste ("aparece como loja avulsa").
Testes: `test_pdv_acesso_diretor.py` (7). Suíte 1437 verde.

## Sessão 114 — UX: endereço automático pelo CEP em TODOS os formulários
Pedido do usuário: digitou o CEP → endereço carrega sozinho, "pedindo só o número".
Existiam 4 cópias do autofill ViaCEP (cliente, endereço de instalação, cadastros genéricos,
contraparte) e 2 formulários SEM (modal de Loja `ml-*` do console e o modal Novo Ponto de
Venda `pdv-*`). Agora: helper único `cepAuto(el, prefixo)` (máscara + debounce 400ms +
preenche logradouro/bairro/cidade e uf OU estado + **foca o campo Número** quando vazio);
`cadCepBuscar`/`afCpCepBuscar` viraram atalhos dele; `ml-cep` e `pdv-cep` ligados; os dois
handlers de cliente (que têm extras próprios, ex. IBGE p/ NFS-e) ganharam só o foco no
número. Frontend puro — suíte inalterada.

## Sessão 113 — FAXINA: Omie removido por inteiro + PostgreSQL como único banco (fim do SQLite)
**Pedido do usuário:** "não deve existir mais nada do Omie; hoje é para estar tudo em Postgres."
Branch `chore/faxina-omie-sqlite` (empilhada sobre `feat/ponto-de-venda`), 4 decisões confirmadas:
suíte Postgres-sempre; DROP das colunas omie_*; cookie renomeado; branch empilhada.
- **Perf pré-requisito:** `mod_contabil._mov/_detalhe_grupo/_totais_conta/saldo_conta` agregavam
  em Python com 2 queries POR CONTA — o painel de Indicadores (DRE por mês da série) estourava
  milhares de round-trips no Postgres (timeout). Agora `_somas_por_conta` (SUM/GROUP BY): 2
  queries por chamada, mesmos números.
- **Omie:** `integracoes/mod_omie.py` APAGADO; as funções LOCAIS de projeto (criar/carregar/
  salvar/listar, XMLs Promob, bloqueio+hash, integridade) viraram `integracoes/projetos_store.py`.
  Fora: auto-sync de cliente, fila/retry omie-sync, fluxo legado de exportação (endpoints
  `/exportar`, `/buscar_cliente`, `/vincular_cliente`, `/limpar_cliente`, `/cancel`, `/confirm`,
  `/logs`, `/config` — todos SEM caller vivo; `aprovarOrcamento()` do frontend era código morto),
  bloco Omie na criação de projeto, campos `omie_*` do cliente (modelo + **DROP COLUMN** no PG),
  credenciais no storage/startup, modal de exportação e card de credenciais na UI. **Cookie de
  sessão: `omie_session` → `orizon_session`** (re-login geral único no deploy); localStorage
  `omie_user_extras_*` → `orizon_user_extras_*` com leitura de migração.
- **SQLite:** motor de migrações raw sqlite3 REMOVIDO do `database.py` (`_migrar_pre_schema/
  _migrar_colunas/_migrar_dados/_run_migracoes/_backfill_loja_operacional/_drop_coluna_margens`,
  `DB_PATH`, `_resolver_config_db`); `init_db` = create_all + `_migrar_colunas_pg` +
  `_seed_loja_padrao`, e **recusa dialeto sqlite** com erro claro; guard do `main()` exige
  `postgresql` (escape `ORIZON_ALLOW_SQLITE` extinto); `reset_ep07.py` apagado (utilitário do
  orizon.db morto). ARMADILHA vivida: o corte por faixa de linhas levou junto as constantes
  `_SEED_*` e `FUNCOES_PADRAO` que moravam no MEIO do bloco de migrações — py_compile não pega
  NameError de runtime; a suíte pegou. Restauradas.
- **Suíte 100% Postgres:** conftest deriva `orizon_test` do `.env` (override `TEST_DATABASE_URL`)
  e ganha `_reset_schema_pg` + fixtures por função `db_pg_limpo` (init_db) e `db_pg_schema`
  (create_all puro) — herdeiras dos sqlite descartáveis por teste. 6 arquivos de teste de
  migração sqlite APAGADOS (config_db, tenancy_migracao/bootstrap/colunas, migracao_perfis,
  perfil_migracao_nivel); 16 arquivos convertidos; FKs fabricadas (que só o SQLite deixava
  passar) corrigidas com linhas reais (lojas/usuário/emitente/ciclo_documento). Suíte **1422
  verde em ~2m45** (contagem caiu pelos testes de migração removidos; antes 1450 em SQLite).
- Docs: CLAUDE.md atualizado (backend PostgreSQL; faxina; suíte Postgres-sempre).
- **Nota:** `orizon.db`/`omie_config.json` locais continuam no disco (e `orizon.db` segue
  TRACKED no git, sempre sujo) — recomendação: `git rm --cached orizon.db` + ajuste do
  `.gitignore` numa frente própria (o CLAUDE.md hoje manda nunca tocar nesses arquivos).

## Sessão 112 — Ponto de Venda (PDV avançado): frente completa em 4 fatias
**Spec:** `docs/superpowers/specs/_geral/2026-07-22-ponto-de-venda-design.md` (caso Caraguatatuba).
Branch `feat/ponto-de-venda`, 1 commit por fatia. **PDV = Loja com mãe**: `lojas.loja_mae_id`
(self-FK) + `tipo` (loja|ponto_venda), migração leve SQLite+PG. Tenancy/painel/razão vêm de graça.
- **Fatia 1 (fundação):** `resolver_emitente` ganha o elo da mãe (PDV sem resolução própria emite
  pela cadeia COMPLETA da mãe; override próprio do PDV ainda vence); documentos do PDV usam modelos
  (`mod_documentos.ativo_de`/`tipo_existe` com fallback) e dados da CONTRATADA da mãe
  (`_loja_dict_para_contrato`), mantendo `codigo` do PDV na numeração e testemunhas próprias;
  endpoints `GET/POST /api/admin/lojas/<id>/pdvs` (lojista vê; criar/editar SÓ super_admin; PDV de
  PDV negado; `rede_id` herdado e bloqueado no PATCH); PDV nasce sem emitente, com config
  financeira/segmentação copiadas da mãe e perfis padrão semeados; seção "Pontos de Venda" no
  cadastro da loja (Admin). Testes `test_pdv_fundacao.py` (17).
- **Fatia 2 (visão unificada — a sensível):** `resolver_owner` dá ao PDV razão PRÓPRIO
  (`("loja", pdv.id)`) mesmo com rede herdada — loja plena inalterada; `_lojas_do_escopo(ator)`
  ([mãe]+PDVs só p/ quem abre o Financeiro da mãe); seletor de unidade OPT-IN via
  `?unidade=`/`X-Unidade-Financeira` no `_contabil_ctx` (todos os painéis financeiros), unidade
  fora do escopo = 403, `escopo_operacional` global intocado; painel financeiro some da UI do PDV
  (auth/me) e a API acompanha (403), MAS o wiring de lançamentos segue vivo (`modulo_ativo`
  intacto — o que some é a tela). `GET /api/financeiro/unidades` alimenta o seletor.
  Testes `test_pdv_visao_unificada.py` (11).
- **Fatia 3 (consolidação+rateios):** `unidade=consolidado` em DRE/Balanço
  (`dre_consolidada`/`balanco_consolidado`, merge estrutural por owner); eliminação intercompany
  medida SÓ pelos refs `rateio:*` na 1.1.09 (não toca saldos de acordos com lojas fora do
  perímetro), abatida dos DOIS lados com linha "eliminações" quando ≠ 0; **Rateio ao PDV**
  (`rateio_ao_pdv`): par ref espelhada `rateio:<n>` — mãe DR 1.1.09 × CR 1.1.01; PDV DR 5.x ×
  CR 2.1.09 — legítimo lançar nos dois razões (ator da mãe COM escopo sobre ambos);
  `estornar_rateio` reverte EM PAR (idempotente); modal com lista/estorno na visão unificada;
  contas 1.1.09/2.1.09 já existiam (frente Acordos; seed idempotente). Testes
  `test_pdv_consolidacao.py` (10).
- **Fatia 4 (Caraguatatuba):** `scripts/criar_pdv_caraguatatuba.py` — idempotente (código `CAR`),
  vincula à Inspirium (`INS`), herda rede/config, semeia perfis; **SEM migração de histórico**
  (projetos/lançamentos ficam na mãe; vendas novas nascem no PDV). Rodar no VPS com o
  `DATABASE_URL` de produção; completar endereço/testemunhas/equipe no Admin.
**Nota de dialeto:** loja de REDE segue compartilhando o razão da rede (inalterado) — dir de loja
irmã enxerga a perna da mãe do rateio no ledger compartilhado (consistente com lançamentos), mas o
estorno exige TODAS as pernas no escopo. `mod_negociacao.py` intocado.
## Sessão 111 — DRE/Balanço analíticos com o PLANO INTEIRO + diagnóstico do "sumiu da DRE"
**Relato:** "lançamento de reconciliação não apareceu na DRE". **Diagnóstico (sem bug de DRE):**
na tela de Reconciliação de Provisões há DUAS ações com destinos diferentes — **Efetivar**
(`efetivar_provisao`: Provisão `2.1.04.x` × Fornecedores `2.1.01`) é lançamento SÓ de balanço
POR DESENHO (a despesa já foi reconhecida na NF-e; efetivar de novo na DRE duplicaria) e
**Resolver** (`resolver_saldo_provisao`: sobra → `4.4.02` receita / falta → `5.6.10`) — esse
sim toca a DRE ("Outras Receitas"/"Ajustes de Provisões"). O botão "Reconciliar" (rateio de
fixas) NÃO persiste nada (relatório; persistência é `fechar_periodo`). **Requisito REVISADO
pelo usuário (2ª revisão do dia — supera o "sem movimento → fora" da S102):** a DRE analítica
mostra **TODAS as contas de receita e despesa** e o balanço analítico **TODAS as de ativo e
passivo** — analíticas ativas sempre listadas (sem movimento = 0,00), e conta com lançamento
no período SEMPRE aparece mesmo sintética/inativa (movimento nunca some). `_detalhe_grupo`
atualizado; testes da S102 reescritos p/ o requisito novo (grupo inteiro presente, período
filtra o VALOR e não a LISTA, inativa sem movimento fora, zeradas não alteram o total).

## Sessão 110 — Gestão geral: usuário sem loja no modal + perfis por loja honrando o alvo + títulos
**Relato do usuário (super_admin na gestão geral):** modal de novo usuário "pede loja mas não
disponibiliza opções" e os perfis mostram só Master/Gerencial/Operador ("cadê o Diretor?").
**Diagnóstico:** (a) na gestão geral o contexto não tem loja/rede → a lista de lojas vinha VAZIA
e o salvar exige ≥1 loja — beco sem saída; (b) `perfis-permitidos` IGNORAVA o `loja_id` do
request (usava só a loja do ATOR — super_admin não tem) → caía no fallback genérico, sem os
perfis customizados da loja-alvo; (c) "Diretor" não é perfil por DESENHO (Perfil-4: cargo virou
Função; o antigo nível diretoria é o Master — o próprio usuário confirmou "o Master é o usuário
diretor"). **Correções:** modal na gestão geral carrega TODAS as lojas do escopo (backend já
filtra tenancy); marcar loja recarrega o dropdown de perfis com os DAQUELA loja
(`_musrLojaMudou`); `perfis_atribuiveis(ator, escopo, loja_id=)` honra a loja-alvo, com guarda
`pode_ver_loja` na rota (dir de uma loja não enxerga perfis customizados de outra — testado);
`criar_perfil` invalida o cache do registro ELE MESMO (antes só a rota fazia; teste em outro
caminho pegou o cache velho). **Decisões do usuário (AskUser + mensagens):** títulos padronizados
**Master** (acesso a tudo — é o perfil do diretor/dono) · **Gerente** (rename do rótulo de
"Gerencial"; slug não muda) · **Operador** (escopo de trabalho); SEM perfil "Diretor" novo.
`backfill_perfis_todas_lojas` no start: semeia os 3 padrão em toda loja + renomeia
Gerencial→Gerente (custom preservado). **Super Admin cria outros Super Admins:** já suportado
(Painel Orizon → Gestores → "+ Novo gestor", escopo plataforma) — travado por teste novo.

## Sessão 109 — Formalismo pleno: família 5.6 suprimida, rubricas nos grupos contábeis formais
**Decisão do usuário (fechando o arco 107→109):** "as contas de constituição… granularidade
desnecessária… deixar correto" — cada rubrica de despesa mora no grupo FORMAL: **CMV**
`5.1.02` Frete de Fábrica · **Custo de Serviço** `5.2.01` Montagem, `5.2.08` Frete Local,
`5.2.09` Insumos Locais, `5.2.12` Garantia, `5.2.13` Assistência Técnica · **Despesas
Comerciais** `5.3.18` Comissão de Medidor, `5.3.19` Comissão de Projeto/Executivo, `5.3.20`
Retenção de Comissão de Vendas. Da 5.6 sobra só `5.6.10` Ajuste de Provisões (grupo "Ajustes de
Provisões"). Os 9 eventos `reconhecimento_despesa_*` debitam as contas formais; constituição
(ativo diferido × provisão), efetivação, pagamento e conciliação seguem IGUAIS — nenhuma perda
de lançamento ou de gestão (a granularidade por rubrica continua, mudou o endereço).
**Consequência buscada: o Lucro Bruto da DRE virou FORMAL** (CMV+CSP agora contém as rubricas;
comissões descem em Despesas Comerciais; margem bruta dos Indicadores idem, sem tocar
`mod_indicadores`). `margem_projeto` atualizada (prov_* lêem as contas formais; `custo_servico`
= grupo 5.2 puro, sem dupla soma; frete de fábrica agora ENTRA na margem via 5.1 — antes ficava
de fora, gap corrigido de carona). **Migração `migrar_plano_formalismo`** (substitui a da
faxina; roda no start ANTES do backfill): RECODIFICA a mesma linha de conta (id preservado →
histórico junto); código formal ocupado sem movimento → apaga e recodifica por cima; ocupado
POR DUPLICATA COM MOVIMENTO → merge (reponta lançamentos — é a reclassificação da duplicação);
aceita todas as gerações de nome (original/S107/S108 + duplicatas antigas); custom preservado.
Rótulo DRE → "(−) Ajustes de Provisões" (chave `constituicao_provisoes` inalterada). Testes:
`test_plano_formalismo.py` (6, substitui o da faxina) + expectativas de 6 arquivos atualizadas
(D2/NF-e agora espera CMV+CSP=62.150 com comissões=1.100 no exemplo canônico).

## Sessão 108 — Plano de contas: mesma linha nos pares restantes + família 5.6 com nome PURO
**Decisão do usuário (fechando a observação da S107):** "a despesa sair de um processamento
contábil de provisão ou ocorrer de um fato direto não muda o teor contábil" → cada rubrica tem
UMA conta de despesa, a da família 5.6. **Removidas do seed** (verificado: mortas no motor —
assistências baixa provisões `2.1.04.x`, e o DRE só agrega o grupo `5.2` por prefixo):
`5.2.01 Montagem`, `5.2.08 Frete Local`, `5.2.09 Insumos` — mesma linha da `5.1.02` (S107).
**Família 5.6 com nome puro** (sem o "— Despesa Reconhecida" da S107, que só existia para
desambiguar das duplicatas — mortas as duplicatas, o sufixo perdeu a função): grupo "Despesas
de Provisões", contas "Garantia"/"Montagem"/"Frete de Fábrica"/etc. `migrar_plano_faxina_frete`
ampliada: remove/desativa as 4 duplicatas e renomeia aceitando **qualquer geração de nome**
(seed original "Constituição — …" OU o da S107 — as bases A/B já tinham rodado a S107); nome
customizado segue preservado. Rótulo da DRE → "(−) Despesas de Provisões" (chave inalterada).
Testes reescritos cobrindo os dois estados históricos (6). Suíte verde nas duas pontas.

## Sessão 107 — Plano de contas: fim da conta duplicada de frete fábrica + renome da família 5.6
**Dúvida do usuário (procedente):** "duas contas de despesa associadas a frete fábrica —
`5.1.02 Frete Fábrica` e `5.6.04 Constituição — Provisão de Frete de Fábrica` — receio de
duplicação". **Diagnóstico:** no fluxo automático (D2) a duplicação é impossível — a despesa do
frete nasce SEMPRE na 5.6.04 (matching da NF-e: `5.6.04 × 1.1.06.07`); a **5.1.02 não é usada por
NENHUM evento do motor** (só existia no seed) e o risco era exclusivamente operacional: lançar a
nota real do frete à mão nela (DRE em dobro + provisão `2.1.04.07` órfã que a Etapa 21 ainda
"resolveria" como sobra → receita `4.4.02` — distorção dupla). O destino correto da nota real é
`efetivar_provisao` (`2.1.04.07 × 2.1.01`). **Decisão do usuário:** (1) remover a 5.1.02;
(2) renomear a família 5.6 tirando o "Constituição —" (herança pré-D2 — o que cai nelas desde a
D2 é o RECONHECIMENTO; lançamento avulso direto nelas fica permitido). **Implementado (TDD):**
5.1.02 fora do `PLANO_PADRAO`; família 5.6 renomeada no seed ("<Rubrica> — Despesa Reconhecida",
grupo "Despesas Reconhecidas de Provisões" — chave da DRE segue `constituicao_provisoes`, só o
rótulo visível mudou); **`migrar_plano_faxina_frete`** roda no start (junto do backfill,
idempotente): remove a 5.1.02 sem movimento / **desativa** a com movimento (histórico fica — e
movimento nela é indício de duplicação manual a reclassificar), renomeia só quem ainda tem o nome
antigo do seed (custom do usuário preservado). Testes `tests/test_plano_faxina_frete.py` (5).
**Observação anotada (sem ação, decidir depois):** o mesmo padrão de par existe para Montagem
(`5.2.01`×`5.6.02`), Frete Local (`5.2.08`×`5.6.05`) e Insumos (`5.2.09`×`5.6.06`) — as contas
5.2 podem ter uso legítimo fora do ciclo de venda, mas valem a mesma avaliação.

## Sessão 106 — Cabeçalho no Aditivo + Painel de Documentos: Upload por seletor, Novo Documento e exemplos
**Spec `contrato-documentos/2026-07-22-cabecalho-aditivo-painel-documentos-design.md`.**
**Cabeçalho:** `_html_cabecalho()` compartilhado (extraído da capa — um lugar só) agora injetado
nos documentos de **corpo-só** (`_montar_html_corpo_documento`): Termo Aditivo, Aprovação do PE e
customizados saem com logo + rede + nº (TA/AP) + data, aos moldes do contrato. **Tipos
customizados:** tabela `documento_tipos` (loja, slug `doc_<nome>`, nome, `etapa_ciclo` opcional;
único por loja; registrada no manifesto `modulos.py` — o ratchet pegou). Slug path-safe por
construção (`doc_[a-z0-9_]+` vira diretório em `documentos_loja/`): forma validada nos pontos
db-free (staging), EXISTÊNCIA onde há banco (`tipo_existe` em criar_versao/endpoints). Endpoints
`GET/POST /api/documentos/tipos` (POST exige `gerir_documentos`; duplicado/nome vazio = erro
claro). Todo o fluxo importar→analisar→ativar é REUSADO para os slugs custom. **Painel Config →
Documentos:** barra de ações com **"Upload de Modelo"** (seletor com nativos + customizados →
desemboca no modal de importação existente) e **"Novo Documento"** (nome + seletor de etapa do
ciclo — a INSERÇÃO da geração no ciclo é frente futura, o vínculo fica gravado); card de
Aprovação do PE entrou (saiu o placeholder "em construção"); cards de customizados mostram a
etapa. **"Ver exemplo"** em todo card: preview do modelo ATIVO sem importar nada — o endpoint de
preview agora renderiza POR TIPO (contrato/proposta = capa+corpo; termo_aditivo = corpo-só com
`_aditivo` de EXEMPLO — ordinal/blocos preenchidos; aprovacao_pe e custom = corpo-só com
cabeçalho) e sem `corpo_md` resolve o ativo da loja (fallback: padrão do sistema p/ contrato e
termo_aditivo). **Suíte de formatação (decisão):** a v1 É o pipeline existente (LibreOffice
achata numeração → corpo_md → análise de marcadores com aprovação humana → preview → ativar);
proposta v2 registrada na spec: "Formatar com IA" (LLM propõe diff de formatação/cravamento, o
operador revisa — mesma filosofia dos cravados). Testes: `test_documentos_tipos_e2e.py` (CRUD de
tipos com permissão/duplicado, importar+ativar+preview de tipo custom, preview por tipo nativo)
+ cabeçalho no `test_aditivo_modelo.py`. Suíte **1409** (SQLite).

## Sessão 105 — Termo Aditivo: modelo jurídico do advogado + wizard de 5 modais sequenciais
**Frente da spec `contrato-documentos/2026-07-22-termo-aditivo-modelo-modais-design.md`:** o corpo-
esqueleto do `termo_aditivo` (3 linhas) deu lugar ao modelo do advogado (`mod_aditivo.doc` →
`contrato_template/termo_aditivo.md`, texto jurídico INTACTO, generalizado com marcadores).
**Backend (TDD):** 8 marcadores novos no `CATALOGO` + `_montar_mapping` NO MESMO commit (anti-drift
verde): `ORDINAL_ADITIVO` (PRIMEIRO/SEGUNDO…, `ordinal_aditivo()`, >10 vira "11º"), `DATA_ADITIVO`,
`DATA_CONTRATO_ORIGINAL` (novo DE PROPÓSITO — `DATA_CONTRATO` segue sendo a do documento corrente;
vem da 1ª assinatura do contrato, fallback `gerado_em`) e os 5 blocos `ADITIVO_*` (considerandos/
lista_integral/inclusoes/exclusoes/valores). Defaults em `montar_defaults_aditivo` (mod_contrato):
considerandos = os 3 LITERAIS do advogado (um por parágrafo, p/ apagar os inaplicáveis); lista
integral = rol COMPLETO pós-alteração (inclui ambientes não alterados; helper
`_aditivo_dados_calculo` no main soma contrato inteiro: original → novo → diferença ao centavo);
inclusão detectada = ambiente do complemento fora do orçamento contratado; exclusão = contratado
que zera; **sem inclusões/exclusões/alteração → frase NEGATIVA automática** (valor do marcador,
não condicional no template — numeração 1.1/1.2/2 estável). **Armadilha real:** a substituição de
marcador roda DEPOIS de o corpo virar `<p>` por linha → valor multi-linha colapsaria; `\n`→`<br>`
no mapping do corpo-documento (só nesse caminho). **Endpoint:** POST `/aditivo` aceita `blocos`
(editados no wizard; vazio → default), `preview` (PDF inline SEM persistir nada — rollback) e
`novo` (após assinado, abre o PRÓXIMO aditivo; regerar assinado segue 403); congela
`modelo_versao_id` na 1ª geração e **semeia o modelo padrão** do `contrato_template/` p/ loja sem
modelo ativo; blocos+ordinal persistidos no `dados_json` (parte do documento assinado, não
recalculável). GET `/aditivo/defaults` alimenta o wizard (defaults + blocos salvos p/ regerar).
Os 6 marcadores da Fatia 3 (`AMBIENTES_COMPLEMENTO` etc.) seguem válidos. **Frontend:** wizard de
5 passos num modal (textarea editável + "Restaurar texto padrão" + Voltar/Avançar + Visualizar PDF
+ Gerar); "Novo Termo Aditivo" aparece só com o anterior assinado. **Testes:**
`test_aditivo_modelo.py` (13: ordinal, 4 combinações com/sem inclusões×exclusões, valores com/sem
alteração, mapping, render do modelo real com `<br>`) + `test_aditivo_wizard_e2e.py` (contrato →
Revisão de PE com ambiente alterado + ambiente INCLUÍDO → defaults ao centavo 88.888,89→103.333,33
/ Δ 14.444,44 → preview sem persistir → geração com bloco editado → congelamento → 2º aditivo
SEGUNDO com o 1º intacto). Suíte SQLite **1405**.
**Cosmético (pedido em voo):** etapas do ciclo — datas do cronograma agora em DUAS COLUNAS
explícitas "Planejado" × "Executado" (rótulo em cima, data empilhada embaixo, borda delimitando,
largura fixa alinhando entre etapas; sem data = "—" pra coluna nunca sumir).

## Sessão 104 — Uploads grandes: teto de body no app (413 amigável) + nginx 64M no runbook
**Causa-raiz do `Failed to fetch` ao subir XML de 6,3 MB em produção** (diagnóstico de 2026-07-21):
nginx sem `client_max_body_size` (default **1 MB**) cortava a conexão com o corpo ainda em trânsito;
e o app não tinha teto NENHUM (dívida anotada no do_POST). Spec
`_geral/2026-07-21-uploads-grandes-limite-body-design.md`. **Backend (TDD):** `max_body_bytes()`
(env `ORIZON_MAX_BODY_MB`, default 50 MB, validação fail-fast no bootstrap, padrão
`porta_do_ambiente`) + `Handler._ler_body()` — ponto ÚNICO de leitura do body usado por
do_POST/do_PUT/do_PATCH; `Content-Length` acima do teto → **413 JSON amigável SEM ler um byte**
(o teste de socket cru envia só headers e a resposta imediata prova o não-read) + `Connection:
close`; header ausente/inválido segue `b'{}'`. App 50 MB **<** nginx 64M de propósito: o erro
amigável vem sempre do app, nunca do reset seco do proxy. Dívida do importar de modelos quitada.
**Frontend:** helper único `uploadFormData(url, fd)` — traduz 413 (usa a mensagem JSON do app,
fallback p/ 413-HTML de proxy) e falha de rede em mensagem amigável (nunca mais `TypeError` cru) —
adotado nos **13** uploads FormData (pool, adicionar/atualizar legado, importar modelo, medição ×3,
PE upload ×2, ciclo documento/revisão, pedido-xml da 12, NF-e fábrica da 15); os 3 da medição não
tinham NENHUM try/catch (rejeição de fetch virava unhandled). `node --check` ok. **Testes:**
`tests/test_max_body.py` (11: unidade do env, 413 em POST/PUT/PATCH via socket cru, override com
mensagem dinâmica, rota intocada sob o teto). **Infra:** runbook do `DEV_RULES.md` (Passo 3) ganhou
o `client_max_body_size 64M` no template + alerta do 2º server block do certbot; **VPS A/B
(167.88.33.121) NÃO tem nginx** (acesso direto na porta; conferido — nginx inativo, sem sites) →
teto do app cobre. Produção (`orizonsolution.com.br`) fica p/ o próximo deploy de produção: aplicar
o 64M nos DOIS blocos server. Suíte SQLite **1389 passed** / Postgres **1386+2 skipped, 1 falha PRÉ-EXISTENTE**
(`test_endpoint_indicadores_e2e`: timeout dos 5s do HttpClient contra Postgres — reproduz IGUAL no
código sem as mudanças desta sessão, via stash; herança da Sessão 103, anotar na frente de
indicadores, fora do escopo aqui). Deploy A+B (`deploy_ab.sh`). Aceite manual com os XMLs reais
de 6,3/6,7 MB pendente de gente.
**Correção no mesmo dia (aceite do usuário: "não deu o erro, mas não carregou o XML"):** o teto
era só METADE da causa — reproduzido com o XML real de 6,3 MB pelo endpoint (harness + multipart de
verdade): **`AttributeError: 'Header' object has no attribute 'split'`** no `_parse_multipart`. O
browser manda o **filename em UTF-8 cru** no Content-Disposition e o policy compat32 devolve
`email.header.Header` (não str) p/ header não-ASCII → o `.split(';')` estourava, a conexão morria
SEM resposta e o fetch reportava o MESMO "Failed to fetch" do nginx. **Era por isso que
`Cozinha.xml` subia e `ASuíte Master.xml` não** (a diferença real era o ACENTO, não só o tamanho —
os 4 XMLs novos do usuário têm acento no nome). Fix: `_header_texto()` (via
`email.header.decode_header`, que preserva os bytes crus → UTF-8; `str(Header)` NÃO serve, troca
os bytes por U+FFFD) aplicado nos DOIS parsers (`_parse_multipart` e `_parse_multipart_arquivos`).
TDD: `tests/test_upload_filename_acentuado.py` (3: unidade dos 2 parsers + E2E no /pool); repro
com o XML real de 6,3 MB devolveu `ok/criado/budget_total=65278.02` (o valor validado na spec).
Suíte SQLite **1392** / Postgres **1389+2** (mesma falha pré-existente de indicadores). Redeploy A+B
(tag B `v2026.07.21b-homolog`).

## Sessão 103 — Snapshot de Indicadores (desafio do usuário): liquidez, giro, KPIs, tendências
**Aba nova "Indicadores"** (1ª do Painel Financeiro): `mod_indicadores.py` PURO (liquidez corrente/
imediata/**ajustada** — exclui os ativos diferidos 1.1.05/06, que a fórmula clássica contaria e
inflaria o índice — capital de giro, margens bruta/EBITDA/líquida, PMR/PMP/giro de carteira,
tendência, KPIs do funil) + endpoint `/api/financeiro/indicadores?meses=3..24` (coleta razão via
mod_contabil + funil + séries mensais) + frontend com stat tiles e sparklines SVG (skill dataviz:
série única em token --accent, tendência SEMPRE seta+texto, tooltips por ponto, janela 3/6/12m,
"—" p/ denominador zero). **QA Vera (1 alto + 3 médios, todos corrigidos + regressão):**
🔴 contratos sem filtro de loja vazavam vendas/ticket de QUALQUER loja do banco — escopo agora é
ÚNICO em todos os blocos (lojas do owner contábil; loja avulsa/outra rede nunca entra);
🟠 venda passa a contar pela **1ª ASSINATURA** (rascunho gerado não conta; projeto cancelado fora;
regerar PDF não move a venda de mês — `gerado_em` era resetado a cada regeração);
🟠 tendência de métricas de FLUXO compara meses FECHADOS (mês parcial × mês cheio leria "queda" o
mês inteiro; caixa é saldo, compara normal) — rótulo "(meses fechados)" na UI;
🟠 N+1 dos orçamentos removido (mapa único). + fix de TZ: janelas em UTC (como o banco) — venda
assinada perto da virada de dia sumia da série. 🟡 perf medida (~63ms/24m em base pequena;
reavaliar com volume). Suíte **1378/1376+2**.

## Sessão 102 — DRE/Balanço: período selecionável + TODAS as contas com lançamento
**Relato do usuário:** a DRE analítica não mostrava todas as contas com lançamento; pediu seletor de
datas início/fim (e idem no Balanço), com contas sem movimento fora. **Bug REAL encontrado na
investigação:** `_mov`/`_detalhe_grupo` filtravam `tipo="analitica"` — mas o `seed_plano` CONVERTE um
pai em sintética quando ele ganha filho no backfill; lançamentos diretos anteriores à conversão
SUMIAM da DRE/Balanço (do total E do analítico). Fix: toda conta com lançamento no período entra
(sem dupla contagem — totais são por lançamento direto); movimento que zera no líquido aparece com
0,00 (teve lançamentos); sem movimento, fora. **Frontend:** DRE ganhou "Período: [de] a [até]" (+
Limpar) — o backend já aceitava `?ini&fim`, o fetch é que nunca enviava; sublinhas zeradas sem
detalhe somem. **Balanço:** seletor "Posição em" (`?data`, corte) + nota explicando por que balanço
não tem data-início (saldo patrimonial é acumulado; recorte quebraria Ativo = Passivo + PL).
4 testes novos (`test_dre_balanco_periodo.py`), incluindo o cenário do pai-convertido e o corte do
balanço. Suíte **1369/1367+2**.

## Sessão 101 — cadastro completo de Credor/Devedor (modal) + reorganização do painel
**Pedidos do usuário (em teste):** (1) cadastro completo da contraparte — **CNPJ, telefone/e-mail
do contato financeiro e endereço** — num MODAL (com ViaCEP preenchendo logradouro/bairro/cidade/UF;
10 colunas novas migradas SQLite+PG; PUT parcial preserva campos não enviados; editar abre o modal
populado). (2) Bug de rótulo: com duas fábricas cadastradas, o card do acordo mostrava só "fábrica"
sem dizer QUEM — agora a contraparte é SEMPRE nomeada em destaque ("crédito com **Fábrica X**
(fábrica)"). (3) Painel reorganizado em **4 seções** numeradas em caixas (1·Credores e Devedores,
2·Novo acordo com campos ROTULADOS, 3·Acordos vigentes, 4·Descontos/Acréscimos), cada uma com
subtítulo explicativo. Suíte **1365/1363+2**.

## Sessão 100 — Acordos Financeiros: opção B (contrapartida no resultado) + polimentos
**Decisões do Diretor sobre a análise de consistência contábil:** (1) **opção B** — Acrescer/Abater
sem caixa ganham SELETOR de contrapartida: "resultado (fato atual)" → ganho `4.4.04`/perda `5.5.05`
(contas novas; 4.4.03 já era Receita Financeira — colisão pega no TDD) ou "PL (saldo antigo)" →
`3.5` (CPC 23). Default da UI = resultado; da API = PL (retrocompat). Fim da distorção DRE×PL
apontada na análise. (2) **Aviso na tela** (cards de dívida): competência OU caixa para o MESMO
juro, nunca ambos. (3) **Vigência** com rótulo+datas na mesma linha (grupo inline). Data de geração
do contrato mantida como âncora da vigência (ok do usuário); juros só de bancos por ora.
**Pedido adicional:** contrapartes agora têm **editar** (espelha nome/tipo nos acordos vinculados)
e **apagar** (só sem acordos vinculados — histórico não órfã), com duplicata por nome+tipo barrada
(explicação do "unique" dada ao usuário). Suíte **1364/1362+2**.

## Sessão 99 — 2ª revisão dos Acordos Financeiros: Credores/Devedores, juros e desacoplamento
**Feedback de teste do usuário:** (1) **cadastro de Credor/Devedor** (`contraparte_financeira`) com
seletor na criação do acordo; (2) **pagamento de empréstimo com NOMINAL + JUROS separados** (nominal
baixa o passivo; juros direto a despesa `5.5.02 × caixa`, evento novo, nonce cobre os dois); (3)
**desacoplamento total**: descontos/acréscimos são SEMPRE de custo (% na provisão da conferência,
`consumir_saldo` DESCONTINUADO → 400) e o lado financeiro de crédito/dívida é lançado MANUALMENTE
no acordo (**acrescer/abater sem caixa**, × 3.5); (4) **vigência avaliada pela DATA DA VENDA**
(contrato.gerado_em) — desconto de período aplica se o pedido foi vendido na janela, mesmo
conferido depois; (5) sem campo % nos acordos. Pergunta do Diretor sobre PL respondida no spec
(passivo já vive em contas de credores; 3.5 é só implantação de saldos pré-existentes, CPC 23;
empréstimo novo entra pelo caixa). Consequência assumida e documentada: CMV = custo real da nota
(Loja 3 → 104.500). Testes reescritos (Loja 3 c/ abater manual; triangular 100% manual c/ cadastro;
pagamento nominal+juros; reconferência só-custo). **QA Vera (2ª rodada, sem bloqueantes):** 1
médio corrigido — o guard genérico do /movimento barrava parcela SÓ de juros (nominal 0, caso de
carência bancária) antes do check interno correto; + regressão. Vestígio `if True:` e docstrings do
consumir_saldo limpos; nome de contraparte sem unique registrado como aceitável. Suíte
**1361/1359+2**.

## Sessão 98 — REFORMA "Acordos Financeiros" (feedback de teste: acerto/data-corte eliminado)
**O usuário reprovou o acerto consolidado por data-corte ("bem confuso") e generalizou o conceito:**
créditos/dívidas com a FÁBRICA, com EMPRESAS (cada loja registra só o seu lado — Verano cadastra a
Inspirium como devedora, Inspirium cadastra a Verano como credora) e com BANCOS (empréstimos), + 
**desconto por período** sem crédito/dívida. **Implementado:** contraparte no acordo
(`contraparte_tipo/nome`, migrado), conta `2.1.10` Empréstimos Bancários + renames 1.1.09/2.1.09
("Créditos/Débitos com Empresas") + 11 eventos; tabela `acordo_movimento`; endpoint `/movimento`
(pagar|receber|atualizar juros 5.5.02|transferir crédito→crédito da mesma loja) SUBSTITUI
`/acertar`+`/liquidar`; captação de empréstimo entra no caixa (1.1.01×2.1.10; pré-existente vai pelo
PL); dívida-EMPRESA financiando desconto ACUMULA sem cap; saldo por acordo derivado da trilha
(aplicações com sinal + movimentos — `pendente_acerto` morreu; verificado ZERO dado legado em
local+VPS); vigência exposta nos ajustes avulsos (desconto por período). Painel renomeado "Acordos
Financeiros" (rotas/tabelas internas mantêm nome antigo — precedente parcela→Fase). **QA Vera (2
médios corrigidos + regressão):** acordo esgotado agora REATIVA quando juros/transferência devolvem
saldo; `/movimento` idempotente por nonce (duplo clique não lança juros 2×; botão trava no voo).
Testes: triangular reescrito manual, empréstimo bancário ciclo completo, vigência. Suíte
**1360/1358+2**.

## Sessão 97 — Acordos com a Fábrica: fatia FRONTEND (painel Admin + preview na etapa 12)
**Fecha a A2 da spec dos Ajustes Excepcionais.** Aba nova **"Acordos c/ Fábrica"** no painel Admin
(acordos cruzam lojas — a lista mostra todos os visíveis ao ator): cards com os TRÊS saldos
(implantado · contábil · pendente de acerto · disponível), status, ajustes aninhados com toggle
ativo, criação de acordo (implantação ×3.5 no ato), criação de ajuste (consumir_saldo no acordo /
custo avulso), **Acertar** (data-corte), **Liquidar** (loja+papel+valor capado), **Encerrar** (com
confirmação de baixa de resíduo) e **Extrato** expansível (endpoint novo read-only:
implantação + aplicações por loja/projeto/status + acertos agrupados). Na **etapa 12**: preview
debounced dos ajustes ao digitar o custo do PE (aplicações, capados, CMV final e A PAGAR à fábrica)
e o resumo APLICADO após a confirmação. **Fix de bug pré-existente:** o parser de moeda da
conferência (`_num`) dava `NaN→0` com o prefixo "R$ " da máscara — a tela nunca conseguiria
registrar; substituído por `_moedaNum` tolerante. **QA Vera (sem bloqueantes; 2 fixes):** 🟠 o
rótulo "APLICADOS" pós-conferência mostrava o TOTAL recalculado (numa reconferência ≠ movimento do
razão) — agora exibe os DELTAS lançados nesta ação (`aplicadas[].delta_lancado`); 🟡 `afEncerrar`
avisava erro de rede; nota no extrato ("implantação líquida de baixas"). Observação registrada:
ajustes `pontuais`/base alternativa ficam para o painel do projeto (escopo intencional, spec).
Suíte 1357/1355+2.

## Sessão 96 — polish do Complemento (teste do usuário): flash do contratado + rótulos
**Relatos:** (1) ao abrir a negociação do complemento, a tela mostrava por instantes o TOTAL do
CONTRATO antes de atualizar — causa: `Negociar Complemento` chamava `carregarOrcamentos()` (que ativa
o CONTRATADO por default) e só depois trocava; agora `carregarOrcamentos(selecionarId)` ativa DIRETO o
complemento, sem dupla ativação. (2) Ao lado do XML na 11e aparecia o valor INTEGRAL do ambiente novo
— agora mostra a DIFERENÇA (Δ, com o contratado no tooltip). (3) Nome do ambiente no formato pedido:
"Complemento <nome>" (prefixo, ex.: "Complemento Aquarto2 - Closet"). Frontend-only (sem restart).

## Sessão 95 — Ajustes Excepcionais de Fábrica: fatia backend contábil (TDD)
**Frente da spec `financeiro/2026-07-21-descontos-acrescimos-excepcionais-fabrica-design.md`** (A2;
motor de negociação INTOCADO). **Entregue:** `mod_ajustes_fabrica.py` puro (ordem fixa desconto sobre
o conferido → acréscimo sobre o pós-descontos; caps ao DISPONÍVEL compartilhados por acordo;
esgotamento; vigência/pontual; round por aplicação); 5 contas (`1.1.08`/`2.1.08` saldos, `1.1.09`/
`2.1.09` conta corrente intercompany, `3.5` PL p/ implantação CPC 23) + 10 eventos; 3 tabelas
(`acordo_fabrica`/`ajuste_fabrica`/`ajuste_fabrica_aplicacao` — trilha e ponte entre razões);
endpoints Admin (criar acordo c/ implantação ×3.5, criar ajuste c/ validações, acertar consolidado
por data-corte idempotente, liquidar capado, encerrar c/ baixa de resíduo, GET lista c/ os 3 saldos)
+ GET preview e aplicação na CONFERÊNCIA (etapa 12, idempotente por `ajx:<proj>:<ajuste>`); devolução
reverte aplicações proporcionalmente (acertada → pendente NEGATIVA, absorvida no próximo acerto).
**Intercompany desacoplado decidido por OWNER** (lojas da mesma rede compartilham razão → consumo
direto; owners distintos → 2.1.09 só na compradora + acerto só na credora). **Bug real achado pelo
TDD e corrigido na fonte:** re-rodar a conferência REVERTIA os ajustes (delta zero da 1ª não grava
ref) — `conferencia_pedido` ganhou `excluir_ajustes` (efeito líquido das aplicações) e mira o alvo
certo em qualquer re-run. **E2E com os exemplos da spec ao centavo:** Loja 3 (100k → CMV 95k / a
pagar 104,5k / dívida −9,5k → matching → pagamento → conciliação SEM sobra/falta) e triangular
Inspirium/Verano (lojas avulsas de teste; invariantes Σ2.1.09 == aplicações; acerto idempotente;
liquidação bilateral zera). **QA Vera (2 achados bloqueantes, ambos corrigidos + regressão):**
🔴 devolução com ajuste `custo` re-adicionava o valor que o `devolver_venda` genérico já revertera
(resíduo fantasma no par) — reversão de aplicações agora filtra `tratamento=consumir_saldo`;
🟠 reconferência com PE diferente congelava os ajustes no valor antigo e o payload divergia do
razão — aplicação passou a lançar o DELTA (rebase, refs `:rN`), com o cap devolvendo o consumo do
próprio projeto antes de capar; 🟡 soma de descontos `custo` recorrentes >100% barrada na criação
+ piso na base dos acréscimos; 🟡 conta corrente não segregada por acordo registrada como
limitação conhecida no spec. Suíte **1357/1355+2**. Frontend (painel Admin + bloco da etapa 12)
fica para a próxima fatia.

## Sessão 94 — fix pós-teste do usuário: pagamento do CONTRATADO vazava para o complemento
**Sintomas (teste manual):** a negociação do complemento puxava o valor TOTAL do contrato (apesar
das linhas mostrarem as diferenças), e a modalidade/entrada vinham do contrato. **Causa única:** ao
ativar orçamento SEM negociação salva, `carregarMargensSalvas` capturava o estado da TELA (ainda o
pagamento do contratado) e o restaurava; o auto-save persistia, e o motor lia o `total_cliente` do
contrato no plano salvo → `cust_fin = total − diferença` → Val_Cont do complemento = total do
contrato. **Fix:** (a) `_pagamentoDoOrc` rastreia o dono do estado do painel — na troca para
orçamento sem negociação salva, `_resetPagamentoPadrao()` (À VISTA, entrada R$ 0,00; re-triggers do
MESMO orçamento preservam a tela como antes); (b) cada "Negociar Complemento" zera
`forma_pagamento`/`negociacao_json` do complemento (padrão à vista por decisão do usuário +
descontamina vazamentos já salvos — projetos de teste se curam sozinhos); (c) regressão E2E
simulando a contaminação. Suíte **1340 passed**.

## Sessão 93 — Correção da Fatia 3: complemento POR DIFERENÇA + Aprovação do PE assinável
**Feedback do usuário sobre a S92:** a negociação do complemento deve ser SÓ sobre a diferença; a
memória do projeto guarda 3 XMLs por ambiente (contrato/pool, Executivo/`xml_pe`, **Complemento/**
`xml_compl` — novo upload por ambiente marcado, "pode até ser idêntico ao PE"); e o botão "Carregar
PE Assinado" da 11e não fazia sentido. **Fórmula exata:** `à_vista_compl_i = venda_XML_i ×
(VAVA_contratado_i/VBVA_contratado_i)` — razão do PRÓPRIO ambiente (descontos + custos adicionais
idênticos aos negociados); diferença = compl − contratado. **Propriedade testada em QUALQUER
composição** (arq/fid/viagem/brinde/Custo Especial): XML idêntico ⇒ diferença ZERO. *(O fator único
`1/(1−p)` da 1ª versão falhava com brinde e re-cobraria o Custo Especial — pego no QA; `p` segue
como INFO no Apoio e fallback.)* Orçamento de complemento = as diferenças (params neutros,
desc global FORÇADO 0 — alavanca única é o desconto por ambiente; nasce à vista; nome "X —
Complemento"; diferença negativa permitida = crédito). Modal comparativo na 11e (contratado ×
complemento × diferença, critérios por extenso) com o Negociar Complemento DENTRO. Aditivo documenta
a diferença NEGOCIADA. **Aprovação do Projeto Executivo** (novo doc assinável, decisão do usuário):
substitui o upload de PE Assinado — tabelas `aprovacoes_pe*`, modelo tipo `aprovacao_pe` (congelado),
marcadores `NUM_APROVACAO_PE`/`AMBIENTES_APROVADOS`, nº AP+data+seq, PDF imprimível, assinatura
loja+cliente, registra os ambientes aprovados (desmembramento); gate da 11e = aprovação ASSINADA
(doc legado retrocompat). E2E reescrito (propriedade do zero, desc global sem efeito, desc por
ambiente sobre a diferença, aditivo, aprovação, gate). Suíte **1339/1337+2**. Spec: seção "Correção
da Fatia 3" do `ciclo/2026-07-21-revisao-pe-venda-renegociacao-design.md`.

## Sessão 92 — Fatia 3 da Revisão de PE: COMPLEMENTO contratual + Termo Aditivo
**Conceito (corrigido pelo usuário em voo):** não é "renegociação" — o PE aumentou valores e
contrata-se o **complemento** (adicional dos ambientes marcados). **A trava do contrato NÃO é
retirada**: contratado/contrato imutáveis (E2E prova o 403); negociável é um orçamento NOVO
(`Orcamento.complemento_pe`, "Complemento PE", badge no dropdown) com base nos VALORES DO PE
(breakdown lê `arquivo_pe`), isento das travas SÓ nos endpoints de negociação; parâmetros do projeto
seguem travados (compartilhados com o contratado); nunca vira default; a tela destrava só com ele
ativo. **11e:** lista dos marcados + "Negociar Complemento" (get-or-create + sync com as marcas da
11c) + Termo Aditivo (gerar/assinar/baixar). **Termo Aditivo:** tabelas próprias `aditivos`/
`aditivos_assinaturas` (FORA de `contratos` de propósito — lá viraria "o último contrato" e
derrubaria `_contrato_assinado`); tipo `termo_aditivo` em documento_modelos (card em Config →
Documentos, modelo obrigatório, versão congelada na 1ª geração); 6 marcadores novos (anti-drift ok);
diferença POR AMBIENTE (linhas do orçamento, ex. Custo Especial, ficam fora — já cobradas no
original); nº TA+data+seq; PDF WeasyPrint confinado; assinatura interna loja+cliente; regerar após
assinado recusado; SEM contabilidade (decisão: gerencial, acerto na liquidação). Armadilha real
corrigida: import não-aliased de `calcular_hash_assinatura` dentro do do_POST shadowava o handler de
assinatura do CONTRATO (UnboundLocalError) — alias `_cha`. E2E `tests/test_complemento_pe_e2e.py`.
**QA Vera:** trava sólida (contratado 403 nos 3 endpoints; `complemento_pe` não é aceito de request;
zero contaminação de contrato/provisões/contabilidade; tenancy e confinamento do PDF ok). 1 achado
médio CORRIGIDO: `atualizarBotoesAprovacao` re-travava o complemento no 1º "Salvar" (divergia do
`ativarOrcamento`) — decisão centralizada no helper `_orcamentoComplementoAtivo()`, usado pelos dois.
1 baixo registrado sem ação: numeração TA é sequência global (mesma convenção do PV da proposta).
Suíte **1338 passed** / **1336+2 skipped** (Postgres). Spec: seção Fatia 3 do
`ciclo/2026-07-21-revisao-pe-venda-renegociacao-design.md`.

## Sessão 91 — Revisão de PE por VENDA + Renegociar (Fatias 1–2 de 3) — decisão de processo
**Demanda:** a Revisão de PE (11c) deve tratar de VALORES DE VENDA; a comparação de custo de fábrica
pertence à AF2 (11d, botão "Comparar Valores", sem carregar). Na 11c, checkbox **Renegociar** por
ambiente; os marcados vão à 11e ("Negociar Ajuste", tela de negociação só com eles). **Decisões do
usuário (AskUser):** efeito gerencial por ora MAS com **Termo Aditivo** (modelo no painel de documentos,
assinatura loja+cliente, só a diferença); base = valores do PE. **Viabilidade confirmada:** o XML de PE
tem o `total` (venda) — mesmo parser do pool; `_negociacao_breakdown` ganhou `vbva_override` e roda o
MESMO motor 2× (original × PE) → VAVA por ambiente, **motor inalterado**.
**Fatia 1 (feita):** `extrair_venda_pe`/`montar_comparacao_venda` (puras); colunas `arquivo_pe.
valor_venda` + `pool_ambientes.renegociar_pe` (migração SQLite+PG); GET `/pe/comparacao` devolve
`comparacao_venda`+`venda_totais` (backfill lazy do valor_venda re-parseando o XML salvo); POST
`/pe/renegociar`; tabela da 11c: À vista contrato × PE × Δ × Δ% × Renegociar × Carregar (venda
maior = verde). E2E `tests/test_pe_comparacao_venda_e2e.py`. **Fatia 2 (feita):** o espelho da 11d
virou a casa definitiva do CFO — "Comparar Valores", read-only, container próprio (fim da colisão de
id com a 11c). **Fatia 3 (próxima frente):** orçamento de ajuste (base PE, isenção gated da trava
`_contrato_assinado`) + Termo Aditivo (tipo novo em documento_modelos, WeasyPrint, assinatura).
Spec: `docs/superpowers/specs/ciclo/2026-07-21-revisao-pe-venda-renegociacao-design.md`. Suíte 1335.

## Sessão 90 — Ciclo/Revisão de PE: "Carregar PE" fundido em "Carregar e Comparar Valores"
**Demanda:** dos 3 botões da Revisão de PE (Carregar Projeto Executivo · Comparar Valores · Desmembrar),
eliminar o "Carregar" e renomear o de comparação para **"Carregar e Comparar Valores"**. Implementado como
FUSÃO (não só rename): o botão novo abre o seletor de arquivo, faz o upload do PE (`peUpload` — segue
pedindo credencial de executor e contando revisão Rev1/Rev2…) e, no sucesso, renderiza a comparação
(`peUploadEComparar`; a comparação vem depois porque o upload re-renderiza o ciclo e recria o container).
`peUpload` agora retorna bool (upload cancelado/falho não dispara comparação). O botão genérico
`btnCarregar` só some na 11c (11a/11b/11e intactas). Sem permissão `executar_pe`, resta o botão
"Comparar valores" read-only (o PE já carregado continua visível). Frontend-only (sem restart; Ctrl+F5).
Suíte 1330 passed.
**Correção no mesmo dia (feedback do usuário):** o seletor de arquivo do conjunto era desnecessário — a
tabela de comparação JÁ carrega o PE **por ambiente** (coluna "Carregar" → `pePeUpload` → `/pe/upload`,
grava `ArquivoPE`). O botão "Carregar e Comparar Valores" virou só abrir a comparação (sem file picker;
`peUploadEComparar` removido). Consequência no backend: o gate da 11c (`guarda_conclusao`) exigia o
**documento único** da subfase (`CicloDocumento` tipo `pe_projeto_executivo`), que ficou sem UI de upload
— agora aceita **PE por ambiente completo** (`pe_ambientes=(total_pool, com_pe)`; barra com contagem
"N/M carregados"; pool vazio barra; doc único legado segue valendo — retrocompat). TDD em
`tests/test_ciclo.py`. Mudança de Python → restart (local + orizon-a). Suíte **1331 passed**.

## Sessão 89 — "Custo Especial não entra no total": era servidor com Python DEFASADO (não era bug)
**Sintoma reportado:** campo aparece no modal, mas o total do projeto não inclui o valor. **Causa:** o
servidor local rodava desde ANTES da Sessão 87 — `static/index.html` é lido do disco a cada request
(modal novo aparece), mas o Python em memória era antigo: o `merge_parametros` velho **descartava em
silêncio** as chaves `custo_especial`/`custo_especial_ativo` no save, e o motor não conhecia `Cust_Esp`.
Clássico do CLAUDE.md ("mudança em Python exige restart"), agravado por o descarte ser silencioso.
**Prova de que o código está certo:** novo E2E HTTP `tests/test_custo_especial_e2e.py` — salva parâmetros
com custo especial 1.000 + ambiente 50k, faz round-trip do GET (merge não descarta), preview com
`Cust_Esp`=1.000 e `Val_Cont`≈51.000, e `Orcamento.valor_total` persistido idem. Verde de primeira.
**Ação:** servidor local reiniciado com o código novo; instância A do VPS atualizada ao topo da `main`
(`0e53e7e`, via systemd) — B segue pinada na tag de homolog. Suíte **1330 passed**.

## Sessão 88 — fix: Total Flex fechava a última parcela NEGATIVA ao remover ambiente
**Bug (reportado em produção de teste):** com um plano Total Flex montado (parcelas 1..n-1 digitadas, a
última fecha o saldo), remover um ambiente do orçamento derrubava o total — mas `atualizarTF()`
reaproveitava os valores digitados relativos ao total ANTIGO (memória `_tfValores`/snapshot restaurado do
`forma_pagamento`), o saldo estourava e a última parcela saía negativa. **Duas falhas:** (1) semântica —
valor digitado é relativo ao total para o qual foi negociado, e nada invalidava o plano quando o total
mudava por fora do painel; (2) guard furado — o modal `ultima_negativa` bloqueava só a 1ª passada
(`_tfRevertendo`); o 2º disparo (a tela dispara vários no reload) atravessava, renderizava e SALVAVA o
plano negativo; e `tfFecharAviso` sem `_tfUltimoEditIdx` (caso sem edição) não revertia nada → loop.
**Fix (frontend):** novo `_tfAvistaRef` — o à-vista para o qual os valores foram montados (persiste no
snapshot como `tf_avista_ref`); se o à-vista atual CAIU >R$0,01, descarta e REINICIALIZA o plano (toast
avisa). AUMENTO de total NÃO reseta (última absorve, digitação preservada — QA da Vera, 2ª rodada) e
mudar a ENTRADA não passa pelo gate (muda o financiado, não o à-vista). Guard endurecido:
`ultima_negativa` nunca renderiza/salva; `tfFecharAviso` sem edição descarta o plano inteiro. Planos
negativos JÁ salvos se auto-curam ao reabrir (modal → OK → reinit).
**Fix (backend, cinto de segurança):** `mod_fin.validar_plano_pagamento` (puro, 6 testes) — o PATCH do
orçamento rejeita com 400 forma_pagamento com parcela/entrada negativa OU não-numérica (endurecido
pós-QA: antes não-numérico viraria 500 cru); legado texto-curto segue aceito. QA da Vera: bug reproduzido
no módulo puro (recalc de 150k→50k com digitação antiga → última −70.563,60), endpoint validado via HTTP
real (400/200/legado), ponto único de escrita de `forma_pagamento` confirmado, formatos das 5 modalidades
compatíveis com o validador. Suíte **1329 passed** (SQLite) / **1327+2 skipped** (Postgres).

## Sessão 87 — Custo Especial: custo adicional NÃO rateado nos ambientes (toggle + provisão própria)
**Demanda do usuário:** custo de valor fixo por projeto que não se distribui nos ambientes (3 ambientes
80k+50k+20k + custo 1.000 → 151.000; removendo 2 ambientes → 51.000, fica integral), configurável no modal
de parâmetros como as rubricas irmãs (arquiteto/fidelidade/viagem/brinde), com provisão própria.
**Nome:** a 1ª proposta era "Custo Fixo"; a pedido do usuário avaliei a colisão com o conceito contábil
consagrado (custo de estrutura, invariante ao volume — o oposto deste, que é custo direto da venda) e o
usuário bateu o martelo em **"Custo Especial"** — renomeado ponta a ponta ANTES do 1º commit (chaves,
sigla, contas, rótulos; sem migração, nada existia em banco).
**Motor:** chaves `custo_especial`/`custo_especial_ativo` + sigla `Cust_Esp` — linha do ORÇAMENTO, fora do
loop de ambientes (é o que o torna não-rateado; ignora `n_total_proj`/`vbvo_proj`). Repassado: `VBNO/VAVO
+= ce` fora do fator de desconto (blindado; `Val_Liq`/`Desc_Tot` intactos); absorvido: só `cust_ad += ce`.
Comissões arq/fid não incidem. Consequência assumida: Σ `Val_Liq` por ambiente ≠ total quando ativo — a
diferença é a própria linha. **Contábil (5º da família Cust_Ad):** contas novas `1.1.06.20 × 2.1.04.20` +
despesa `5.3.17`; eventos de constituição no contrato (FASE D2, sem tocar DRE) e matching na NF-e; AF,
conciliação final, devolução e reconciliação pegam a rubrica por serem data-driven; `seed_plano` backfilla
owners existentes. **Frontend:** bloco no modal (após Brinde), linha "− Custo Especial" no apoio, payloads
dos 2 caminhos de save + snapshot/restore, rubrica na tabela da AF; de propósito FORA dos gross-ups por
ambiente. **QA (Vera):** validou motor (simulações independentes), ciclo contábil e tokens de design; 1
achado baixo — orçamento SEM ambientes gerava `Val_Cont` do custo sem venda — corrigido no motor (zera sem
ambientes) com regressão. **Testes:** +13 (motor com o exemplo literal da demanda, params, provisões, ciclo
contábil completo, sets de chaves dos E2E). Suíte **1322 passed** (SQLite) e **1320+2 skipped** (Postgres).
Spec: `docs/superpowers/specs/financeiro/2026-07-20-custo-especial-nao-rateado-design.md`.

## Sessão 86 — Fatia 4 (sinal de atraso GERAL na lista) FECHA a frente A+B + deploy A/B + chave SSH
Suíte **1314 verde (SQLite) e 1312+2skip (Postgres `orizon_test`)**. Branch `feat/fatia4-sinal-atraso`
mergeada na `main`. **Frente A+B (spec 2026-07-17) CONCLUÍDA** — o §7 (UI do card) já tinha sido
antecipado nas Fatias 2–3; esta fatia entrega o §6.

**1. Sinal de atraso geral (spec §6).** `mod_cronograma.projeto_em_atraso(etapas, data_entrega, hoje)`
(pura): atrasado se qualquer etapa aberta (`concluido_em` nulo) tem previsão vencida, OU entrega vencida
com a "16" aberta (**ausente conta como aberta**). `_enriquecer_projetos_com_atraso` em `main.py` anota
`atrasado` + `data_entrega` nos itens de `/projetos` e `/projetos/buscar` (2 queries em lote por request;
reusa o `p['status']` do enriquecimento anterior — ordem documentada). Lista de projetos ganhou coluna
**Entrega** com selo **Atrasado** (`.proj-atraso-badge`, tokens `--err`/`--err-soft`); o Kanban de
Expedição passou a reusar a mesma classe (era estilo inline).

**2. QA da Vera pegou bug GRAVE antes do merge:** a 1ª versão excluía `status="fechado"` do sinal como
se fosse terminal — mas "fechado" é o estado de **EXECUÇÃO** (atribuído na 2ª assinatura, vale pelas
etapas 8–20, só vira "concluido" na Etapa 21): o selo nunca acenderia pra população-alvo. Corrigido:
terminais são `perdido/concluido/cancelado`; "fechado" acende. Teste de regressão dedicado
(`test_lista_projeto_fechado_em_execucao_ACENDE`). Lição: cobrir o status que o ciclo REALMENTE usa.

**3. Deploy/infra (início da sessão).** Instância **A** (`:8765`) no topo do `main`; **B** (pré-homolog,
`:8766`) promovida à tag **`v2026.07.20-homolog`** — ambas 302 interno/externo. Acesso ao VPS
`167.88.33.121` agora por **chave SSH** (ed25519 desta máquina no root — deploys sem senha). Script
`deploy_ab.sh` (scratchpad): mata só o processo da instância certa (via cwd em `/proc`), poll até 302 —
melhor que o `pkill -f main.py` do runbook, que derrubaria as duas.

**[PENDENTE]** verificação manual no navegador (coluna/selo na lista, tema claro/escuro — Vera não teve
navegador); re-ingerir grafo MCP (Docker Desktop parado no Windows); promover Fatia 4 à B quando
homologada. **[ARQUIVOS]** `mod_cronograma.py`, `main.py`, `static/index.html`,
`tests/test_cronogramas_dois.py`, `tests/test_lista_projetos_atraso.py` (novo), spec (status concluída),
plano `docs/superpowers/plans/2026-07-20-fatia4-sinal-atraso.md`.

## Sessão 85 — Fatia 3 (prazo contratual + marcadores) + retirada do SQLite + refinamentos da Fatia 2 (branch `feat/fatia2-datas-assinatura`)
Continuação da frente A+B com testes manuais do usuário. Execução subagent-driven. Suíte **1295 verde (SQLite) e
1293+2skip (Postgres)**. Branch **não mergeada** — acumula Fatia 2 + Fatia 3 + infra Postgres/SQLite.

**1. INCIDENTE Postgres↔SQLite (resolvido; dado NÃO perdido).** Ao testar a Fatia 2, "os projetos sumiram". Raiz:
o app escolhe o banco por `DATABASE_URL` — **setada = Postgres**, **ausente = SQLite** (`orizon.db`). O servidor
subiu sem `DATABASE_URL` → caiu no **SQLite antigo** (snapshot de ~16/07, com projetos Marcelo), mascarando o
**Postgres real** (com os projetos Teste de 17-18/07). Correção: subir no Postgres (dados intactos). **SQLite
APOSENTADO no runtime:** `main.py` agora RECUSA subir no SQLite sem `DATABASE_URL` (guard, escape `ORIZON_ALLOW_SQLITE=1`);
novo `run.sh` + `.env` (git-ignored) sobem sempre no Postgres. O pytest segue em SQLite via conftest (não passa por
`main()`). **Bug real da Fatia 2 achado:** `_migrar_colunas_pg` não tinha as colunas de `projetos_meta`/`ciclo_etapas`
(só a migração SQLite tinha) → app quebrava no Postgres; corrigido (paridade). **[ARQUIVOS]** `main.py`, `database.py`,
`run.sh`, `.env`(local), `.gitignore`, `.gitattributes`.

**2. Refinamentos da Fatia 2 (testes manuais).** (a) Override da folga usa **modal do design** (senha mascarada,
padrão `modal-crono`), não `prompt()`. (b) `Projeto.folga_autorizada` (flag): save marca 0 se cabe / 1 se gravado sob
override; a **assinatura RECALCULA a folga** e bloqueia se `folga<0 e não autorizada` (pega config mudada pós-save).
(c) A trava de datas/folga vale **desde a 1ª assinatura** (antes só a que completava); o frontend não abre a tela de
assinatura sem as datas. (d) Card volta ao estado SALVO quando a autorização é cancelada/recusada (não ilude).

**3. Fatia 3 — prazo contratual (dias úteis) + marcadores no contrato.** Parâmetro `prazo_contratual_dias_uteis`
(default 50) na config da loja. `mod_cronograma.somar_dias_uteis` (seg–sex; único prazo em dias úteis). Aviso de
coerência (não bloqueia) na aba Config → Cronograma quando o padrão (dias corridos) não cabe no prazo contratual
(`padrao_cabe_no_prazo_contratual` + flag `padrao_cabe_prazo` no GET config-financeira). **4 marcadores** no contrato
(`DATA_PREVISTA_ENTREGA`, `PREVISAO_MEDICAO`, `PRAZO_CONTRATUAL` = cláusula "N dias úteis a partir da assinatura",
`VENDA_PROGRAMADA`) em `CATALOGO` + `_montar_mapping` (teste anti-drift), alimentados pelo `Projeto` via
`_extras_marcadores_contrato` (`variaveis.update` nos 2 chamadores reais da geração — sem mexer em assinaturas).
**Data-limite do Contrato:** na assinatura (D0) grava `Projeto.data_limite_contratual = D0 + prazo em dias úteis`
(`somar_dias_uteis`; coluna migrada SQLite+PG, serializada no GET contrato) — completa as 3 datas do acordo (Medição,
Entrega, Data-limite) para a **Agenda** monitorar o esgotamento do prazo. O prazo (`prazo_contratual_dias_uteis`)
ganhou **campo editável na aba Config → Cronograma**: é a **fonte única** que alimenta o marcador `[PRAZO_CONTRATUAL]`
(texto do contrato) E a Data-limite — não divergem quando o modelo usa o marcador.

**[DECIDIDO]** `PRAZO_CONTRATUAL` = cláusula em texto (a assinatura ainda não ocorreu na geração). **[PENDENTE]**
verificação manual no navegador da Fatia 3 (marcadores no PDF exigem o modelo referenciá-los); merge da branch;
Fatia 4 (sinal de atraso geral). **[ARQUIVOS Fatia 3]** `mod_provisoes.py`, `mod_cronograma.py`, `mod_marcadores.py`,
`mod_contrato.py`, `main.py`, `static/index.html`, `tests/test_provisoes.py`, `tests/test_cronogramas_dois.py`,
`tests/test_marcadores.py`, plano em `docs/superpowers/plans/2026-07-18-fatia3-prazo-contratual-marcadores.md`.

## Sessão 84 — Fatia 2 da frente A+B: datas da assinatura, folga medição→entrega e enforcement (branch `feat/fatia2-datas-assinatura`)
Execução subagent-driven (implementer + revisão de spec + revisão de qualidade por task; 7 tasks). Segue a spec
`docs/superpowers/specs/ciclo/2026-07-17-ancora-entrega-folga-venda-programada-design.md` (Fatia 2 de 4). Suíte
**1285 verde** na branch. **NÃO mergeada** — pendente verificação manual no navegador + merge/push.

**1. Duas datas do acordo, obrigatórias na assinatura.** `Projeto` ganhou `previsao_medicao` (DateTime) e
`venda_programada` (Integer 0/1, migração com `DEFAULT 0` p/ backfill de linhas legadas). O `POST /data-entrega`
passa a exigir **expectativa de entrega E previsão de medição** (400 se faltar), persiste as duas + a classificação
venda programada, e a **2ª assinatura** (loja+cliente) exige ambas as datas (guard estendido).

**2. Folga do trecho MEDIÇÃO→ENTREGA.** `mod_cronograma.folga_medicao_entrega(cfg, previsao_medicao, data_entrega)`
= `(entrega − medição) − Σ durações das etapas após a medição até a "16"`. Só o trecho sob controle da loja (PE,
produção, entrega) conta — as etapas até a medição dependem da obra do cliente. Âncora da medição: "10", senão "9",
senão a 1ª etapa; precondição documentada (config em ordem). Substitui, neste fluxo, a folga início→entrega antiga.

**3. Bloqueio real + override gerencial auditado.** `folga < 0` → **não grava**, retorna `requer_autorizacao`.
Com reautenticação Gerente+ (`login`/`senha` + `perfis.pode(nivel,"autorizar")`) grava assim mesmo e audita em
`LogAcaoGerencial(acao="data_entrega_sem_folga")`. Endpoint com `try/except` (rollback + 500), 403 explícito em
credencial inválida/nível insuficiente, e `venda_programada` preservado em update parcial (só grava se enviado).

**4. UI mínima de entrada (deployabilidade).** Card do Contrato ganhou os campos **previsão de medição** +
**expectativa de entrega** + checkbox **venda programada**; `salvarDataEntrega` posta os três e, em folga<0, oferece
"Registrar com autorização" (Gerente+ via `_podeAutorizarFront`), que reposta com `login`/`senha`. Feedback de
sucesso do override corrigido (branch em `requer_autorizacao`, não em `cabe`). GET contrato serializa os 3 campos.

**[DECIDIDO]** semântica: `cabe:false` é correto mesmo após override gravar (override = "gravar apesar de não
caber"); o front distingue "gravado" por AUSÊNCIA de `requer_autorizacao`. UI de entrada trazida da Fatia 4 para cá
porque a exigência das datas na assinatura travaria produção sem campo para inseri-las. **[PENDENTE]** verificação
manual no navegador (validar folgado/apertado, override, reexibição, trava da assinatura) + merge; `autorizarDataEntrega`
usa `prompt()` (MVP) — trocar pelo modal com senha mascarada (padrão `modal-crono`) numa passada de polish; Fatia 3
(prazo contratual em dias úteis + marcadores no contrato) e Fatia 4 (sinal de atraso geral + UI final).
**[ARQUIVOS]** `database.py`, `mod_cronograma.py`, `main.py`, `static/index.html`, `tests/test_cronograma.py`,
`tests/test_cronogramas_dois.py`, `tests/test_data_entrega.py`, `tests/test_af_gate_data_entrega.py`,
`tests/test_fluxo_completo_e2e.py`, plano em `docs/superpowers/plans/2026-07-18-fatia2-datas-assinatura-enforcement.md`.

## Sessão 83 — Folha de Pagamento & Remunerações: motor pela Função, comissão por papel (Mapa), adiantamentos, comissão fixa, aprovação e base LÍQUIDA por ambiente

Frente longa (Fases 3–6 + refinamentos), spec `docs/superpowers/specs/2026-07-17-comissao-papel-adiantamentos-design.md` + planos por fase. Consolidada na `feat/fatia1-cronograma-data-entrega` (mesclada na `main` via FF nesta finalização). Suíte **1273 passed**.

**Motor da Folha (Fase 3):** `mod_folha.calcular_folha` passou a resolver a remuneração pela **Função** do funcionário (Config → Remunerações) — `salario_fixo`, `beneficios_json` (AT/VA/PS), `comissao_json`/`usa_comissao_vendas`. Colunas novas `folha_pagamento.{base_comissao,beneficios}` (migração SQLite `_add_cols` + Postgres `_migrar_colunas_pg`). Conta `5.3.16 Benefícios a Funcionários` + evento `folha_beneficios`; `pagar` posta fixa→5.3.06, variável→5.3.01, benefícios→5.3.16.

**Comissão por papel (Fase 4):** tabela **`comissao_folha`** (itens por funcionário/competência; `origem` papel|venda). Novo `mod_comissao.py`: `papel_da_etapa` (10=medição, 11x=PE, 17=montagem, 18=assistência), gatilho na conclusão de etapa (`_set_etapa_status`) + cancelamento na reabertura. **Executor vem do MAPA de Atribuições** (`atribuicoes_ambiente`, não do `responsavel_funcionario_id` da etapa) e a função/% vêm do próprio Funcionário; suporta vários executores por papel. `gerar_folha` soma os itens em `parte_variavel`; o Consultor virou item `origem='venda'`. `PATCH /api/comissao/<id>` + endpoints de composição.

**Base da comissão de papel = VALOR LÍQUIDO por ambiente (correção crítica):** primeiro erro usei `order_total` (= **custo de fábrica**, cf. `promob_grupos.py`); depois ratear `valor_liquido` por `budget_total` (bruto). O correto (confirmado pelo usuário): **`Val_Liq_Amb = VAVA − Cust_Ad × (VAVA/VAVO)`** — o VAVA do ambiente menos a fatia proporcional dos custos adicionais, respeitando o toggle `incluir_custos`. `mod_comissao._breakdown_projeto` espelha `main._negociacao_breakdown` e usa `mod_negociacao.calcular_orcamento` para obter VAVA/VAVO/Cust_Ad/Val_Liq por ambiente. Projeto inteiro → base = Val_Liq do projeto.

**Adiantamentos/Empréstimos (Fase 5):** tabela `adiantamento_funcionario` + `mod_adiantamento.py` (saldo de débito, abatimentos, **Adiantamento Oficial** 40% do salário fixo em carteira, quitação na paga). Config `folha.adiantamento_oficial_{ativo,pct}` (box em Config→Remunerações, auto-salva no onchange). Folha do mês expõe **líquido a pagar** e **saldo de débito**. Endpoints `POST/PATCH /api/adiantamentos`.

**Comissão fixa por função (Fase 6):** `Funcao.comissao_fixa` + `FolhaPagamento.comissao_fixa` (parcela mensal isenta de encargos — planejamento); somada no total.

**Fluxo de aprovação:** status `aberta → aprovada → paga`; `pagar` exige aprovação; `gerar_folha` não sobrescreve aprovada; endpoints `/aprovar` `/reabrir`; botões na Folha do mês.

**UI da folha (muitos ajustes cosméticos com o usuário):** colunas renomeadas **Base** (valor sobre o qual incide) e **Comissões** (valor); coluna % removida; alinhamento vertical das linhas (`.fcell` de altura fixa); BASE **somada** (um valor) com **"?"** (círculo pequeno) que abre modal de **composição** — por **contrato/projeto** na venda (`vendas_liquido_detalhe`) e por **ambiente** nos papéis (líquido por ambiente). Endpoint `GET /api/folha/<id>/comissoes-base`.

**Fix do seletor de consultor:** o seletor de consultor do projeto passou a filtrar por **função Consultor de Vendas / Gerente de Vendas** (não por perfil operacional); `func_sync_acesso` faz o login **herdar a função** do funcionário + senha provisória; backfill `usa_comissao_vendas=1` na função Consultor de Vendas.

**Pendências [contador]:** contas exatas dos adiantamentos/benefícios no contracheque, encargos trabalhistas, comissão de **terceiros** (repasse, não folha), e a **reconciliação** previsto (Provisões) × realizado (Folha). Backfills de comissão rodados no Postgres de dev local (não no VPS).

## Sessão 82 — Fatia 1 da frente A+B: correções de cronograma + persistência da data de entrega (branch `feat/fatia1-cronograma-data-entrega`)
Brainstorm → spec → plano → execução subagent-driven (implementer + revisão de spec + revisão de qualidade por task).
Origem: teste manual do usuário no card do Contrato — a data de entrega "sumia" depois de validar/assinar, e a
folga do cronograma era incompreensível. A frente A+B foi desenhada inteira (spec
`docs/superpowers/specs/ciclo/2026-07-17-ancora-entrega-folga-venda-programada-design.md`, 4 fatias); esta sessão
implementou só a **Fatia 1** (correções que destravam o uso). Suíte **1270 verde** na branch. **NÃO mergeada** —
pendente verificação manual no navegador + merge/push.

**1. Semântica do Cronograma Padrão fixada: `prazo_dias` = DURAÇÃO da etapa (dias corridos), não offset acumulado
desde D0.** O default de `mod_provisoes.config_financeira_default()` foi reescrito em durações realistas (soma ~72
dias corridos ≈ 50 dias úteis, o prazo contratual-alvo) e ganhou o marcador `cronograma_formato: 2`.

**2. `mod_provisoes.normalizar_cronograma_formato(cfg)` (nova, pura):** converte config LEGADA (acumulado, sem o
marcador) → durações por diferença consecutiva, idempotente (`cronograma_formato` ausente/1 = converte; ≥2 = mantém).
Robusta: parsing defensivo via `_f()` e ignora itens não-dict (config malformada não quebra o read). Aplicada na
**leitura** da config (`_cfg_financeira_loja` e o GET config-financeira) **ANTES** do merge com o default — senão o
merge herdaria `formato:2` do default e nunca converteria o legado.

**3. `mod_cronograma.gerar_cronograma_projeto` passou a ACUMULAR** (`data_prevista = D0 + Σ durações até a etapa`).
Isto conserta um **bug latente pré-existente**: como o default já era duração e a função usava offset direto, a
`data_prevista_conclusao` persistida estava dessincronizada do preview da própria tela de Config (`cronoTplRecalc`,
que já acumulava). Teste de regressão e2e prova que, p/ loja legada, normalizar+acumular reproduz os offsets originais.

**4. Bug da data que "sumia" (raiz encontrada):** o card lê `contrato.data_entrega`, mas a serialização do
`GET /api/projetos/<nome>/contrato` **nunca** devolvia esse campo — a data É gravada em `Projeto.data_entrega`, só
não voltava. Corrigido: o payload passa a incluir `data_entrega` do projeto (reusando o lookup `_projeto_da_loja`).
Nenhuma mudança de JS (o card já lia o campo).

**[DECIDIDO na spec]** entrega esperada = previsão editável no `Projeto`; folga ≥ 0 bloqueia com override gerencial
(Fatia 2); prazo contratual ~50 dias úteis desde a assinatura, único em dias úteis (Fatia 3); medição esperada +
expectativa de entrega obrigatórias na assinatura; venda programada = classificação + marcador no contrato; sinal de
atraso GERAL. **[PENDENTE]** Fatias 2–4 (colunas `previsao_medicao`/`venda_programada`, folga medição→entrega +
bloqueio, prazo contratual + marcadores, sinal de atraso). Verificação manual no navegador + merge desta Fatia 1.
**[ARQUIVOS]** `mod_provisoes.py`, `mod_cronograma.py`, `main.py`, `tests/test_cronograma.py`, `tests/test_data_entrega.py`,
`tests/test_provisoes.py`, spec+plano em `docs/superpowers/{specs/ciclo,plans}/2026-07-17-*`.

## Sessão 81 — Reforma de navegação (Painel Orizon + Admin plano + seletor) + 9 tópicos (Grupos A e C)
Sequência de frentes de UI/admin, todas mergeadas na `main` por FF a partir de worktrees isoladas.

**Navegação consistente (Fase 1)** — spec/plano em `docs/superpowers/{specs,plans}/2026-07-16-navegacao-*`.
O **Painel Admin** deixou de ser drill-down (Plataforma→Rede→Loja) e virou **plano de 4 abas** iguais p/
todo perfil: **Dados da empresa · Usuários · Perfis de Usuário · Módulos** (renomeados de "…da loja").
A administração **do sistema** (redes/lojas/gestores) saiu para um **Painel Orizon** novo na sidebar, só
`super_admin` (gate `pode_gerir_redes`). **Seletor de empresa** no topo de Admin/Config arma o `X-Loja-Ativa`
(reaproveita o god-mode da Sessão 80) → Admin/Config passam a funcionar p/ o super_admin escolhendo a
empresa. Backend: `GET /api/admin/empresas` (lojas administráveis, com `cnpj`) + caps de aba no `/auth/me`.
**[DECIDIDO]** super_admin=técnico (Orizon) × gestor de rede=negócios (**dashboard consolidado = frente
futura**); admin_rede usa Admin/Config padrão escopado à sua rede. **[PENDENTE] Fase 2:** abas de Admin/Config
visíveis a todo perfil com **cadeado + step-up** (não feita).

**Grupo A (4 ajustes cosméticos):** Funcionários fora do módulo Cadastro (sidebar + aba interna; entidade
permanece); ícone da Folha `wallet→cash-banknote`; rótulos `modulos.py` "Comercial (Vendas)"→"Comercial",
"Fiscal (NF-e/NFS-e)"→"Fiscal"; sidebar 220→250px (cabe "Folha de Pagamento").

**Grupo C (cadastro de loja/rede — itens 7,8,9):** (C1) `cnpj` no `GET /api/admin/empresas`; (C2) seletor de
empresa vira **combobox buscável por nome/CNPJ** (agrupado por rede) no canto sup. esq.; (C3) `Usuario.senha_provisoria`
+ migração, login/`auth/me` sinalizam `precisa_trocar_senha`, `POST /api/auth/trocar-senha`; (C4) **modal
bloqueante de troca de senha no 1º login**; (C5) `POST /api/admin/lojas` **completo** (endereço/contato/
responsável/módulos + cria **1º diretor** `master` com senha provisória) e o `PATCH /api/admin/lojas/<id>`
existente estendido (responsável+módulos, respeitando gating `gerir_lojas`×`editar_dados_loja`) — `Loja.responsavel`
nova coluna+migração; (C6) **modal "Cadastro de Loja"** completo no Orizon › Lojas (+Editar por linha); (C7)
aba **Redes ganha "+ Loja nesta rede"** abrindo o mesmo modal pré-preenchido. **[DECIDIDO]** dados no nível da
loja (fiscal segue no Painel Fiscal); diretor com senha provisória (troca no 1º login); item 2 (Comissões)
só front nesta rodada; item 1 (Funções) "Atribuições"=papéis operacionais. Suíte **1212 verde**.

**[PENDENTE]** Itens **1 (Config › Funções editáveis)** e **2 (Config › Comissões)** dos 9 tópicos; **Fase 2**
das travas de navegação; **re-ingerir grafo MCP**.

## Sessão 80 — super_admin acesso pleno (god-mode) — desbloqueio urgente (branch `feat/super-admin-acesso-pleno`)
Pedido do usuário: o **super_admin não conseguia criar perfis nem usuários e "não acessava o cadastro"**;
quer o perfil com **liberdade plena e irrestrita por enquanto** (revisitar limites / eventual 2º perfil de
admin depois). Diagnóstico achou **3 causas-raiz somadas**, não uma:
1. **super_admin nunca ganhava loja ativa.** `mod_tenancy.resolver_loja_ativa` só resolve loja para quem é
   membro (memberships ∪ default); super_admin não tem loja própria nem membership → `active_loja_id` sempre
   None, nem passando o header `X-Loja-Ativa` → sem escopo operacional → **Cadastro morto**.
2. **`acesso_operacional=False`** no dict de `super_admin` em `perfis.py` (+ várias capacidades finas False).
3. **Endpoints de Perfis escopavam por `usuario.loja_id`** (=None p/ super_admin): `GET /api/admin/perfis`,
   `GET /api/admin/perfis-matriz` e `POST /api/admin/perfis` → painel vinha **vazio** e criar perfil gravava
   **órfão** (`IntegrityError: NOT NULL perfil_acesso.loja_id`).

**Solução (TDD, por subagentes, suíte 1184→1188 verde):**
- **`auth/perfis.py`:** bypass explícito do slug `super_admin` em `pode`, `acessa_modulo`, `acessa_painel`
  (retornam True) — god-mode irrestrito. Flags `acesso_operacional/financeiro/fiscal` do dict viram True
  (honestidade da matriz read-only; o bypass já cobre o enforcement). Bypass **só** no slug exato
  `super_admin` — `_eh_super_admin` (deriva de `gerir_redes`) e `admin_rede` intactos; teste garante que
  operador/gerencial não ganham acesso lateral.
- **`mod_tenancy.resolver_loja_ativa(..., is_super=False)`:** super_admin **adota a loja do header** como
  ativa (ou None se nenhuma escolhida). `main._ator_dict` passa `is_super = (u.nivel == "super_admin")`.
- **`main.py`:** helper `_loja_admin_alvo(usuario)` — super_admin usa a loja do header (`_REQ_LOJA_ATIVA`),
  demais usam a própria; os 3 endpoints de Perfis passam a usá-lo, e o POST erra claro se nenhuma loja
  selecionada ("Selecione uma loja para criar o perfil.").
- **`static/index.html`:** `adminEntrarLoja` seta `_lojaAtiva=id` (o interceptor de fetch já envia
  `X-Loja-Ativa` nas chamadas do console Admin); `adminIrNivel(1/2)` e `adminEntrarRede` limpam `_lojaAtiva`.
  `node --check` OK (via WSL).
- **Testes** (`tests/test_super_admin_god_mode.py`, novo): unit do bypass; unit do `resolver_loja_ativa`
  (super e não-super); e2e — super_admin cria perfil e lê a matriz na loja escolhida; erro sem loja; cria
  **usuário** de loja; **Cadastro** (`GET /api/funcionarios`) dá **403 sem loja / 200 ao entrar na loja**.
  `HttpClient` (conftest) ganhou header `X-Loja-Ativa` opcional. **Fallout do god-mode corrigido:**
  `test_perfis_novos_sem_poder_operacional` (separa admin_rede restrito de super_admin irrestrito) e
  `test_override_negado_sem_permissao` (ator negativo super→operador `cons_l1`).

**[DECIDIDO]** god-mode total agora (escolha do usuário sobre "mínimo cirúrgico"); reuso do canal `_lojaAtiva`
(super_admin "entra" numa loja e opera como ela). **[FORA DE ESCOPO]** `admin_rede` (não pedido); limites/2º
perfil de admin (futuro). **[PENDENTE]** verificação manual no navegador (o backend está coberto por e2e, mas
ninguém clicou); merge na `main` + push + re-ingerir grafo. **[ARQUIVOS]** `auth/perfis.py`, `mod_tenancy.py`,
`main.py`, `static/index.html`, `tests/test_super_admin_god_mode.py`(novo), `tests/conftest.py`,
`tests/test_perfis_tenancy.py`, `tests/test_qualidade_upload_e2e.py`,
`docs/superpowers/plans/2026-07-16-super-admin-acesso-pleno.md`(novo).

## Sessão 79 — Faxina do projeto + piloto de pacotes (raiz 49→32 .py)

Suíte **1184 verde**, tudo na `main`. Sessão de higiene, a pedido do usuário ("quero uma verdadeira
faxina, arquivos organizados"). Quatro frentes, todas com o mesmo padrão de achado: **a operação que
deixa verde escondia uma verificação desligada, e a verdade só apareceu executando de verdade.**

**1. Faxina do working tree.** `git status` de ~50 linhas → 1. A causa do ruído eterno era fixável e
o CLAUDE.md mandava conviver com ela: `/CONTRATOS/` estava no `.gitignore` **e** rastreado (commitado
antes da regra; `.gitignore` não desrastreia). `git rm --cached` no ruído + `.gitignore` cirúrgico.
Descoberto por execução (esconder 15 candidatos e rodar a suíte): 13 `.docx`/XML eram órfãos, mas
`modelo_proposta.docx` era fixture — `*.docx` em bloco teria quebrado a suíte num clone novo.
Recuperados **do lixo**: `docs/audit/` (Auditoria Florence, 8 auditorias, citada pelo DEV_LOG, estava
só no disco) e `SIMULACAO_CLAUDE_LOG.md`. Removidos 107 MB de worktrees do Postgres (o achado técnico
delas foi pro spec da migração antes de apagar; as branches foram destravadas).

**2. Specs organizados.** `docs/superpowers/specs/` de 75 arquivos soltos → 8 subpastas por área, via
`git mv` (histórico preservado). 84 referências corrigidas, conferidas por `os.path.exists`. Os 3
wildcards (`fase-d2-*`, `2026-07-10-*`) precisaram de mão — e um deles JÁ era impreciso, a subpasta o
deixou correto.

**3. Faxina da raiz.** 105 → 75 itens: `.docx` → `docs/especificacoes/`, `.md` soltos → `docs/`
(cada um pra pasta do assunto que já existia), `.bat` → `scripts/`. **Duas referências não precisaram
de conserto — o movimento as consertou**: apontavam pro lugar novo antes do arquivo chegar lá.
Conferir o CONTEXTO de cada citação antes de substituir evitou um `sed` cego trocar link certo por
errado.

**4. Piloto de pacotes.** 3 dos 4 domínios grandes viraram pacote: `fiscal/` (6), `integracoes/` (5),
`auth/` (6). Raiz 49 → 32 `.py`. Seguiu o precedente do `mod_fin/`. Decisões e sustos:

- **Empacotar DESLIGAVA a trava de arquitetura.** `test_arquitetura_modulos` fazia `if not
  arquivo.endswith(".py"): continue` — um pacote é diretório, então o ratchet PULAVA o pacote inteiro
  e ficava verde sem checar. Não era hipótese: o `mod_fin/` estava fora do ratchet desde que virou
  pacote, escondido por um `| {"mod_fin"}` hardcoded. **Consertado ANTES de mover** (expande diretório
  nos .py; detecta pacote por `__init__.py`). O mesmo buraco estava em `modulos.modulo_de_arquivo`.
- **O `auth` cobrou 3 bugs**, todos da colisão "pacote E módulo se chamam `auth`": o script de
  reescrita comeu a própria saída (`from auth.auth import perfis`); um comentário no fim da linha
  derrotou o regex (`storage.py`); e um `as` dentro de lista por vírgula (`import ..., perfis as
  _perfis`) não casou. **E minha varredura de conferência tinha os mesmos bugs do script** — disse "0
  pendentes" com o servidor caindo. Só o traceback real do servidor contou a verdade.
- **A PÁGINA DE ENTRADA quebrou, e o usuário achou, não a suíte.** Mover `auth_routes.py` pra `auth/`
  quebrou `_LOGIN_HTML = join(dirname(__file__), "static", "login.html")` — passou a apontar pra
  `auth/static/`. O `except FileNotFoundError` de `_serve_login` devolvia **404 em silêncio**: `/` →
  302 → `/login` → 404, com 1181 testes verdes. Eu ajustei todos os imports e esqueci uma classe
  inteira: os **caminhos relativos a `__file__`** (4 deles). Import quebrado explode alto; caminho
  quebrado devolve 404 educado. Corrigidos (sobem um nível, como o `mod_fin/base.py` sempre fez) +
  `tests/test_caminhos_de_pacote.py` (ratchet que pega `dirname(__file__)` sozinho dentro de pacote).

**A verificação mentiu de 3 jeitos diferentes numa sessão:** `.pyc` obsoleto (conteúdo reordenado do
mesmo tamanho não invalida o bytecode), **servidor fantasma** (dois `python.exe` velhos na 8765 que o
`pkill -f "python3 main.py"` não pegava), e **verificador com o mesmo bug do código**. Lição:
*o que confirma não pode compartilhar o defeito do que é confirmado.*

**Fora de escopo (recomendação registrada):** NÃO empacotar o `comercial` sem tratar os caminhos
`__file__` — `mod_contrato.CONTRATO_TEMPLATE_DIR` quebraria igual, e `_carregar_md` engole arquivo
ausente como `""` → contrato sairia sem cláusulas, verde.

## Sessão 78 — Modelos de documentos da loja (Config › Documentos deixa de ser tela-morta)

Branch `feat/modelos-documentos-loja`, suíte **1187 verde** (+130). Pedido do usuário: a aba Documentos
vira ambiente de configuração — o lojista sobe um Word, o sistema aplica o modelo Orizon e pede os dados
complementares. Spec: `docs/superpowers/specs/contrato-documentos/2026-07-15-modelos-documentos-loja-design.md`; plano:
`docs/superpowers/plans/2026-07-15-modelos-documentos-loja.md`.

**O que entrou** (11 tasks, TDD, 1 subagente implementador + 2 revisores por task):
`mod_marcadores` (catálogo travado contra `_montar_mapping` por teste anti-drift) · `mod_documentos_import`
(arquivo → Markdown, via LibreOffice) · `mod_documentos` (registro versionado) · tabela `documento_modelos` ·
`Contrato.modelo_versao_id` · capacidade `gerir_documentos` · 5 endpoints `/api/documentos/*` · painel +
wizard · corpo da proposta.

**Decisões que mudaram o desenho, e por quê:**

- **Importação via LibreOffice, não `python-docx`.** O `.docx` usa numeração automática do Word
  (`numId/ilvl`) — os números não estão em `paragraph.text`. **Medido num `.docx` real:** LibreOffice
  preserva **63** números de cláusula; `python-docx`, **3**. Sessenta numerações sumiriam em silêncio de
  um contrato. Isso justificou o pipeline inteiro (e deu de brinde `.odt`/`.doc`/`.rtf`).
- **PDF é recusado**, com mensagem acionável: extração de PDF perde a hierarquia das cláusulas.
- **Modelo por loja, global como fallback** → migração zero.
- **Versão imutável + `Contrato.modelo_versao_id`.** `gerar_pdf_contrato` regenera o PDF pelo id lendo o
  modelo do disco na hora: sem isso, trocar o modelo reescreveria cláusula de contrato **já assinado**.
- **Proposta não versiona, de propósito** — não é assinada; reemitir deve pegar correções do modelo.

**O que a sessão errou (e o que isso ensina).** Foram **onze afirmações falsas** pegas pelas revisões,
quase todas em comentários/planos, não em código. As quatro que doeram:

1. **`CLAUDE.md:53` dizia que a proposta usava docx/LibreOffice.** Falso desde a migração da capa —
   `mod_proposta.py` é código morto (seu único import, `main.py:1821`, nunca era usado). Uma seção inteira
   do spec nasceu dessa premissa e teve de ser reescrita. **Corrigido nesta sessão.**
2. **O bug do D6 dentro da função escrita para garantir o D6.** `_resolver_corpo_contrato` caía no modelo
   **ativo** da loja quando `_modelo_versao_id` era `None` — mas `None` é a resposta *deliberada* para
   contrato legado. Resultado: contrato antigo regeraria com cláusula nova. **Nenhum teste unitário pegou**
   (eles provavam que `versao_para_contrato` devolve `None`, não o que o consumidor fazia com isso); só
   apareceu num teste que sobe o servidor de verdade.
3. **Dois furos de segurança criados por esta frente**, demonstrados por execução: **SSRF/LFI** (o corpo
   vinha do lojista e não era escapado → `<img src=http://…>` no modelo fazia o WeasyPrint buscar a URL a
   cada contrato gerado) e **path traversal** (`os.path.basename(".")` devolve `"."` → mandar `staging: "."`
   movia o `_staging/` inteiro). Ambos onde o comentário afirmava estar fechado.
4. **O órfão reintroduzido pela própria correção do órfão**, três linhas abaixo (move-antes-do-commit no
   segundo commit de `criar_versao`).

Padrão: **verificar por execução acha o que ler não acha**. As correções mais importantes vieram de teste
E2E, experimento de concorrência (8 threads → 5 `IntegrityError` vazando) e sonda HTTP — nenhuma de leitura
de código. Por isso cada correção veio com teste que trava o comportamento: comentário apodrece, teste não.

**Dívidas registradas (fora de escopo):**
- **Caminho docx morto:** `mod_proposta.py`, `modelo_proposta.docx`, `_substituir_marcadores`,
  `_converter_pdf`, `tests/test_proposta*.py`. Cuidado: `_libreoffice_cmd()` **continua necessário**
  (base da importação) e `contrato_editar.py:48-50` também o usa.
- **Upload sem cap de `Content-Length`** — gap sistêmico do `main.py` (nenhum POST limita), não desta frente.
- **`documentos_loja/<loja>/<tipo>/_staging/` sem limpeza** — quem sobe e desiste deixa lixo.
- **Flake pré-existente com causa-raiz achada:** a fixture `projetos_dir` (`conftest.py`) muta
  `main.PROJETOS_DIR`/`storage.PROJETOS_DIR` **globalmente sem teardown** → quem usar por último decide o
  valor para o resto da sessão. Explica os flakes de `test_isolamento_f4_e2e` e `test_projeto_editar_e2e`.
- **`pytest.ini` novo** (`norecursedirs`): worktrees dentro da raiz (`wt-postgres-migration/`) carregavam
  uma cópia de `tests/` e a suíte **não rodava** — 162 erros de colisão antes de coletar. O comando do
  CLAUDE.md estava inviável nesta árvore.
- **"+ documentos" (tipos novos)** fica para spec próprio: a pergunta em aberto é *o que dispara um
  documento custom* — um "Termo de Medição" no painel não serve se nada no ciclo o emite. A coluna `tipo`
  já nasce preparada.

## Sessão 77 — IA da navegação: "Orçamentos" → "Projetos", retirada do módulo vazio + dashboard Comercial

Branch `feat/desmembramento-fatia2-ciclo`, suíte **1054 verde** (+5). Reorganização a pedido do usuário
(diálogo de IA/navegação), em 3 incrementos testados:

- **Rename "Orçamentos" → "Projetos" (display-only).** A `page-00` já era "Projetos" por dentro (botão
  "+ Novo Projeto", `criarProjeto`, comentários); só 2 strings diziam "Orçamentos" (atalho + título). A
  entidade **Orçamento** (versões EP-07) e todos os endpoints (`/api/orcamentos`, model, `projeto_id`)
  ficam intactos — o rename corrige uma inconsistência que já existia.
- **Retirada do módulo `producao` (rótulo UI "Projetos", tela-vazia "EM CONSTRUÇÃO")** que duplicava o nome.
  No manifesto (`modulos.py`) ele não era vazio — dono de `mod_medicao.py`/`mod_qualidade_xml.py` + tabela
  `medicoes` + rota `/api/medicoes`. Como **Medição vive no ciclo** (etapas 9/10), rehospedei esses arquivos
  em **`comercial`** e removi o domínio `producao`: ajustados `DOMINIOS_ORDEM`, `depende_de` de
  `estoque`/`expedicao` (→ `comercial`), `COMPARTILHADOS` (mod_nfe), seed `_OP` (`database.py`), listas de
  acesso (`perfis.py`/`perfil_store.py`), `_SB_MODULOS`/`_PFA_GRUPO_OPERACIONAIS` (frontend) e os testes
  `test_modulos`/`test_auth_me_modulos` (faixa `execucao_projeto` some do hub por ficar sem módulo ativo).
  Teste de arquitetura/fronteira segue verde.
- **Dashboard Comercial (o módulo "Comercial" agora abre um dashboard, não a lista).** `mod_comercial_dash.py`
  (puro, **view derivada da fonte única**, escopo por loja): **funil de conversão** (total → com Orçamento
  etapa 4 → com Contrato etapa 7 + %), **carteira por status** (quente/morno/frio), **volume contratado**
  (contratos assinados × valor do orçamento) + **ticket médio**. Endpoint `GET /api/comercial/dashboard`
  (escopo_operacional). Frontend: `page-15` com KPI-tiles + barras (tokens `--accent`/`--warn`/`--text-3`,
  sem cor literal). TDD: `tests/test_comercial_dash.py` (métricas + escopo por loja + vazio + endpoint 200/401).

⚠️ Mudanças em `.py` (main/modulos/database/perfis/mod_comercial_dash) → **restart do servidor**. Frontend → **Ctrl+F5**.

## Sessão 76 — Continuação maratona 2026-07-14: bug do briefing + Cronograma Passo 2 (data de entrega no Contrato) + gate da AF (data E contrato assinado)

Branch `feat/desmembramento-fatia2-ciclo`, suíte **1049 verde** (+3). Continuação dos testes manuais do usuário:

- **Bug do briefing (projeto errado):** o card da etapa 3 chamava `cliAbrirBriefing(cliente_id)` (briefing do
  CLIENTE) → o `POST /api/clientes/<id>/briefing` salva no briefing mais RECENTE do cliente. Como o cliente tinha
  vários projetos, o preenchimento do Marcelo_7 caía no Marcelo_6 **sem o usuário abrir o 6** → etapa 3 seguia
  "pendente" e travava o orçamento. Fix: etapa 3 passa a abrir `abrirBriefingProjeto(nome_safe)` (briefing DO
  projeto). Frontend-only.
- **Cronograma Passo 2:** card do Contrato ganhou campo **"Data de entrega esperada"** + botão **Validar** →
  `POST /api/projetos/<nome>/data-entrega` (grava `data_entrega`+`data_inicio`, calcula folga do Cronograma
  Padrão, retorna `cabe`/`folga_min`). A pedido do usuário o campo é **sempre editável** (removido o `disabled`
  em `assinado`/`vigente`; Validar sempre visível); **sem prefill do briefing** (avaliado e descartado).
- **Gate da AF (bug de teste manual: "aprovei AF sem validar a data"):** a trava de `data_entrega` vivia SÓ na
  assinatura (`main.py` ~5806, bloqueia a assinatura que COMPLETA o contrato). A AF (etapa 8) é posterior e NÃO
  re-checava → projeto assinado ANTES do gate existir chegava à AF sem data. **Novo gate no
  `PATCH /api/projetos/<nome>/ciclo/<cod>`** para as AFs (8/11d, via `mod_ciclo.exige_aprovacao_financeira`): a
  etapa só FECHA com **data de entrega DEFINIDA E contrato totalmente assinado** — "valida data E contrato
  assinado, **independente da sequência**". TDD: `tests/test_af_gate_data_entrega.py` (sem data → 400; contrato
  não assinado → 400; ambos → 200). O frontend já exibe o `erro` do backend no modal da AF (sem mudança).
- **Gates audit (restante):** `_podeEditarMapaFront` e `_NFE_NIVEIS_EMITE` usavam nomes de função obsoletos
  (`diretor`/`gerente_*`, que nunca casam) → corrigidos p/ níveis-base (`master`/`gerencial`/`admin_rede`).

⚠️ Mudança em `main.py` (gate da AF) → **restart do servidor**. Frontend → **Ctrl+F5**.

## Sessão 75 — Design system v1.7 (rótulo flutuante + Linha de Total) + Fatia 1 do desmembramento de PE (mergeada)

Ordem de trabalho em 5 passos (usuário ausente). Fechados os passos 1 e 2, ambos na `main`.

**Passo 1 — Design v1.7 na `main` (`d801e86`).** Aplicados os 3 itens canônicos do
`design-system/orizon-styleguide.html` (04c/07c) + `orizon-tokens.css` changelog v1.7:
- `.field-float` (rótulo estático DENTRO do campo, `--control-h-float` 52px) e `.total-line`
  (valor num tamanho ÚNICO `--fs-h3` mono; `.emphasis` = box) adicionados ao `orizon-components.css`.
- Painel **À Vista** (Negociação) migrado de `.mod-grid` 3×2 → padrão 04c: 2 linhas (Entrada /
  Liquidação), Valor da liquidação como campo calculado readonly (`--surface-2` + etiqueta "calculado").
- **"Total do Contrato"** migrado de `.total-contract` (valor 22px) → `.total-line.emphasis`; CSS órfão removido.
- Vera (revisão estática): 🔴 especificidade — `.field-float .input` passou a declarar background/fonte
  (0,2,0) p/ vencer a global legada `input[type=…]` (0,1,1); 🟡 `negTotalConfirmar` não força mais verde.
  Ambos corrigidos. Deixado como follow-on: os outros 4 painéis de pagamento (Aymoré/Cartão/VP/TF) e as
  KPI-tiles do fluxo seguem no padrão antigo; contraste de `--text-3` no rótulo (~3,4:1) é token canônico
  do styleguide (decisão de design system do usuário, não alterado).

**Passo 2 — Fatia 1 do desmembramento (spec `2026-07-13-desmembramento-pe-parcial-design.md`, mergeada na `main`).**
Backend já pronto (`mod_pe_comparacao.py` puro + `ArquivoPE` + endpoints `GET .../pe/comparacao`, `POST
.../pe/upload`; tabelas de parcela criadas mas **dormentes** até a Fatia 2). UI **nascida no padrão v1.7**:
- **11c (Revisão de PE):** comparação de CFO por ambiente (venda × PE × Δ, `.tbl`) + upload de XML por
  ambiente + painel "Reconciliação estimada" (dashed `--warn` = estimativa gerencial, NÃO contábil; KPIs de
  margem contratada×estimada em R$ e %; rubricas Provisionado×Estimado×Δ; `.total-line.emphasis` no Δ total).
- **11d (Aprovação Financeira):** espelho READ-ONLY da mesma comparação (spec §5/§6 "+ botão espelho em 11d").
- Só a rubrica Custo de Fábrica (`2.1.04.06`) se move na Fatia 1 (decisão #4/#9); é snapshot puro, não lança
  no razão. Vera: endpoint com `pool_ambiente_id` OK, invariantes §6 OK, **suíte 958 verde**, read-only
  confirmado no banco. O único 🟠 (faltava o espelho 11d) foi fechado antes do merge.

Pendente da ordem: passo 3 (Fatia 2 — ciclo, branch `feat/desmembramento-fatia2-ciclo`), passo 4 (Fatia 3 —
contabilidade, branch a partir da Fatia 2), passo 5 (e2e da Vera). Fatia 2/3 ficam nas branches aguardando
aprovação do usuário (não mergear).

## Sessão 74 — Faxina: verde hardcoded (painel de testes) + emojis nativos → ícones Tabler
- **Verde puro fora do design system:** achado num `teste_financeiro_v4.html` — **painel de testes standalone**
  (paleta própria: monospace, laranja legado `#e8611a`, teal `#19c9a0`; não referenciado pelo produto, não
  importava tokens). O **produto (`index.html`) já estava correto** (confirmação "Aprovação financeira
  concluída" em `color:var(--ok)`; barra de subfases e `.nav-item.done` em `var(--ok)`) — a premissa de um
  componente de confirmação com verde fixo no produto **não se confirmou**. Corrigido migrando o painel
  inteiro ao design system: importa `orizon-tokens.css` e tokeniza tudo (verde→`--ok`, laranja→`--accent`,
  âmbar→`--warn`, azul→`--info`, vermelho→`--err`, bg/`-soft`, borda/`-line`; fundos→`--surface-2`; fontes→
  `--font-mono`/`--font-display`). Fica theme-aware. Varredura repo-wide (hex saturado + nomeados `green`/
  `lime`/… + `hsl`) não achou verde em nenhum outro arquivo de UI.
- **Emojis nativos → ícones Tabler (currentColor).** Correção da premissa: o projeto **não usa lucide-react**
  (não há React; frontend é `index.html` em JS puro) — o set carregado é o **Tabler** (`ti ti-*`). Trocados
  os 18 emojis do produto (🔒/🔓→lock/lock-open, 🔥/❄→flame/snowflake, ⚠→alert-triangle, 🏢/🏪/👤→building/
  building-store/user, 🧾/📄/📎/💾/📷→receipt/file/paperclip/device-floppy/camera, 💳→credit-card, 🚧→tools,
  👁→eye, ✎→pencil, ✕→x): ~62 em conteúdo HTML→`<i>`, 10 `textContent` estático→`innerHTML`+ícone, 3 em
  `title="…"` (glifo removido — ícone não renderiza em atributo), 2 em comentário. **2 casos** ficaram sem
  ícone (dado dinâmico não escapado, mantido `textContent`/`.value`): título do painel de cartão (era `💳 `)
  e o `input.value` "⚠ maior que base". Painel de testes: 🧪/📊/📋 (título/abas)→Tabler; ▶ e ✓/⚠ do log
  mantidos (marcadores tipográficos). Verificado: `node --check` limpo (WSL), 0 emojis-alvo restantes, chaves
  balanceadas, check de tokens verde, sem cor literal introduzida.

## Sessão 73 — Design system v1.5 (paleta unificada em cobre) + consolidação da marca + fix do tema claro
Consolidação definitiva das duas frentes de design sobre a base da Sessão 72.

- **Design system atualizado para tokens v1.5:** paleta unificada nos dois temas em torno do cobre
  (accent), com areia no tema claro e carvão quente no tema escuro — fim da divergência entre temas.
  Semânticas (erro/aviso/sucesso/info) em vinho/ocre/sálvia/azul empoeirado. Grades de altura e largura
  de controles padronizadas. Template Barra de Filtros adicionado. Página de login atualizada para a
  composição vertical da marca.
- **Identidade visual do produto atualizada para v1.0:** logo azul substituído pelo glifo cobre
  (bússola), conforme `design-system/marca/REGRAS_MARCA.md`. Emblema completo mantido apenas para uso
  em marketing, fora do produto. Assets reorganizados em `design-system/marca/`.
- **Corrigido: área de conteúdo no tema claro renderizava sem estilo (serifa, inputs nativos, sem cor).**
  Causa-raiz: o `design-system/*.css` não chegava ao browser (404) porque o servidor rodava o `main.py`
  anterior à rota `.css` (mudança em Python exige restart); como na Sessão 72 os *fallbacks* literais do
  app foram trocados por aliases puros, sem os tokens o conteúdo perde fonte/cor/raio/inputs. A sidebar
  "parecia OK" por ser quase só texto (degrada legível). Fix: servidor reiniciado com a rota `.css` ativa
  (200 confirmado). **Descoberta adicional corrigida:** `.sidebar` usava `var(--surface)` (segue o tema →
  branca no claro), então, com os tokens carregando, o lockup branco ficaria invisível no claro;
  reescopei os tokens theme-following para os `--sidebar-*` dentro de `.sidebar` → sidebar escura nos dois
  temas (§7) sem editar cada propriedade. Mesmo padrão aplicado ao card de login (09b, sobre carvão).

**Também nesta sessão:**
- Tokens v1.5 são os do usuário (areia `#FAF8F6`/`#FFFFFF`, accent cobre `#8C5230`, primário cinza-quente
  `#5C5650`). Os aliases do produto (Sessão 72) seguem resolvendo — mesmos nomes de token.
- Varredura de hex/rgb: `index.html` e `login.html` permanecem **sem cor literal** (check verde).
- Trava: `check-design-tokens.sh` passou a **excluir `orizon-styleguide.html`** (doc/demo de referência,
  mostra swatches e o glifo de marca com cores literais legítimas); varre a UI enviada + `orizon-components.css`.
- Docs marcados como superados (banner → fonte única `orizon-tokens.css` v1.5): `docs/design-tokens.md`
  e `docs/design/padrao-design-orizon-v2.md`. Specs históricas datadas **não** foram reescritas (registro).
  `modelo_proposta.docx` (marketing, caminho docx/LibreOffice) fica para um passe à parte.

**Auditada pela Vera** (estática + contraste + `node --check` via WSL; confirmou 200 do design-system/*.css no
servidor real). 3 achados corrigidos: (1) 🔴 pill ativo do alternador de tema sumia na sidebar (usava
`--surface`→`--sidebar-bg` = o próprio fundo) → pill agora com borda+tint+texto cobre (padrão status-selector),
trilho transparente; (2) 🔴 botão "Entrar" do login a ~2,6:1 (o `.btn-primary` próprio da landing resolvia
`--accent`→`--sidebar-accent` como fundo) → passa a usar o componente `--btn-primary-*` (cinza-quente, 09b/regra
nº 2); (3) 🟠 hover de "Sair" com `--err` vinho ilegível no carvão → `:root:not([data-theme=dark]) .sidebar`
reaponta `--err`→`--err-line` (rosa claro) só no claro (no escuro o `--err` já é claro). Confirmado OK por ela:
sidebar carvão + lockup, nav/creds legíveis, composição do login 09b, e o conteúdo herdando tokens no claro.

## Sessão 72 — Design system v1.4 (cobre/carvão) + Identidade visual v1.0 (glifo da bússola)
Consolidação de duas frentes de design entregues fora do código (arquivos em `design-system/`).
Supera o rebrand da **Sessão 68** (navy/azul-elétrico/ciano da logo antiga), que fica aposentado.

- **Design system atualizado para tokens v1.4:** paleta migrada de menta/petróleo para cobre/bronze
  sobre carvão quente (tema escuro); semânticas (erro/aviso/sucesso/info) suavizadas para
  vinho/ocre/sálvia/azul empoeirado; grades de altura e largura de controles padronizadas; template
  Barra de Filtros adicionado.
- **Identidade visual do produto atualizada para v1.0:** logo azul substituído pelo glifo cobre
  (bússola), conforme `design-system/marca/REGRAS_MARCA.md`. Emblema completo mantido apenas para uso
  em marketing, fora do produto.

**Como foi feito (implementação):**
- **Marca:** `/logomarca` → `design-system/marca/` (fonte da verdade, ao lado do styleguide). Nenhum
  caminho de código apontava para `logomarca/`.
- **Tokens globais:** `orizon-tokens.css` importado no `<head>` de `index.html` (+ `login.html`) **antes
  de qualquer outro CSS**. Como o app usa nomes de token próprios (`--muted`, `--card`, `--st-*`,
  `--teal/amber/coral-*`…) e tema-padrão invertido, o bloco `:root` local virou uma **ponte de aliases**
  para os tokens v1.4 (que reresolvem por tema) — migra navy/azul/ciano → carvão/cobre em bloco, sem
  reescrever as ~250 refs `var(--…)`. `main.py` ganhou rota para servir `.css` de `design-system/`
  (fonte única, sem cópia em `static/`).
- **Varredura de hex/rgb:** `index.html` zerado de cor literal — removidos ~70 fallbacks mortos
  `var(--x,#hex)` (navy/verde-terminal/ouro), semânticas hardcoded → tokens (`--err/--warn/--ok/-soft`),
  `#fff`→`--btn-primary-text`, e 53 `rgba` coloridas mapeadas por hue → `-soft`/sólidos. `login.html`
  idem. Restam só scrims/sombras neutras preto/branco (sem token v1.4 equivalente).
- **Tema padrão:** por decisão do usuário, **claro** (era escuro); toggle invertido (dark = atributo
  explícito). Títulos/KPIs adotam **Montserrat** (`--font-display`); corpo segue Inter.
- **Marca no produto:** favicon → `glifo-favicon.svg` (copiado p/ `static/`); sidebar = lockup
  horizontal (glifo mono-branco inline via `currentColor` + wordmark), carvão nos dois temas (§7);
  login = lockup **vertical sobre carvão** no card (§5). Glifos a ≥40px (peso fino válido, §4); geometria
  oficial não redesenhada.
- **Camada de componentes + trava:** `design-system/orizon-components.css` (classes do styleguide,
  importado global no app) + `scripts/check-design-tokens.sh` (falha em hex/rgb colorida fora do
  `orizon-tokens.css`) instalado em `.git/hooks/pre-commit`.
- **Verificação:** suíte **952 passed**; `main.py` OK; servidor serve `/` (index), `/login`,
  `design-system/*.css` (200 text/css), `/glifo-favicon.svg` (svg); check de tokens **verde**.

**Auditada pela Vera** (estática + `node --check` via WSL): 1 achado **bloqueante corrigido** — `.btn-ghost`
tinha a borda só em `:root[data-theme="light"]`, que deixou de casar com o novo padrão (claro = sem
atributo) → botão secundário sumia no claro; reescrito como base (claro, com borda) + override no escuro
(`[data-theme="dark"] .btn-ghost{border-color:transparent}`), atende à regra inegociável #4. Também subido
o glifo do nav do login de 30→40px (peso fino válido, §4 — asset de peso médio não existe). Diferido
(não-bloqueante): `--text-3` no claro ~3,1:1 (abaixo de AA; valor do token no orizon-tokens.css, usado em
`.badge-bloqueado`/`--st-perdido`); `--font-mono` do produto (IBM Plex) diverge do token
(JetBrains, não carregado) — alinhar num passe futuro; drift potencial da cópia `static/glifo-favicon.svg`.

**Tema claro migrado para COBRE (v1.5, decisão do usuário):** encerrada a pendência que o v1.4 deixava
aberta — o tema claro do `orizon-tokens.css` sai de petróleo/menta (`--accent #0E5F50`) para **cobre**
(marca §3: `--accent #8C5230`, `--accent-vivid` dourado `#B8823D`, hover/soft/line derivados). Claro e
escuro agora ambos na família cobre; o descasamento marca(cobre)×UI(petróleo) que o padrão claro exporia
deixa de existir. Botão primário segue neutro por decisão de design (v10, ≠ accent).

## Sessão 71 — Ajuste pós-merge FASE D2: painel de Reconciliação mostra saldo LÍQUIDO (+ manutenção de repo)
Achado da Vera (não-bloqueante, herdado da FASE D). O `saldo` de cada rubrica na `reconciliacao()` é `provisionado − efetivado` e **exclui de propósito** as resoluções (`resolucao_provisao_sobra/falta`) — certo p/ não misturar resolução com efetivação real. Efeito colateral: depois que `conciliar_final`/`resolver-saldo-provisao` fechava o saldo ao resultado, o painel continuava mostrando o saldo original como se estivesse em aberto.
**Correção (TDD):** `reconciliacao()` passa a expor **`saldo_aberto`** (líquido = o que falta resolver), descontando `resolvido` na direção do sinal (sobra `saldo>0`: `saldo − resolvido`; falta `saldo<0`: `saldo + resolvido` — `resolvido` é magnitude positiva nos dois casos). `saldo` (bruto) e `resolvido` seguem no payload p/ auditoria (+ `totais.saldo_aberto`). Frontend (Reconciliação, painel + modal do Projeto): "Saldo" exibido = `saldo_aberto`, bruto no `title`; botão **Resolver** só aparece com `saldo_aberto ≠ 0`. Teste cobre sobra/falta (total e parcial), não-resolvido, totais e **projeto conciliado → `saldo_aberto=0` em todas as rubricas**. Suíte 946→**952**.
**Manutenção de repo (ambiente, sem commit):** `.git/objects/pack/multi-pack-index` velho (pré-merge da D2) dava `error: improper chunk offset` no `fsck`/`log` (git caía p/ ler os packs direto, comandos corretos) — regenerado com `git multi-pack-index write`.

## Sessão 70 — FASE D2: provisão completa no contrato (ativo diferido) + matching pleno na NF-e + Conciliação Final
Branch `feat/financeiro-fase-d2` (mergeada). Área sensível (dinheiro); desenho FECHADO com o usuário (spec `docs/superpowers/specs/financeiro/2026-07-12-fase-d2-provisao-completa-conciliacao-final-design.md`, verificado com Fable 5); TDD; **parando antes de mergear cada fase** p/ conferência dos números. **Auditada pela Vera** (não-duplicação centavo-a-centavo, Balanço fecha em cada etapa → APTA). Suíte 909→**946**.
**O modelo (por que 2 famílias de conta):** reconhecer a Receita cheia na NF-e exige debitar uma conta que ZERA ali; mas a Provisão de Fábrica (2.1.04.06) precisa SOBREVIVER (é o que a reconciliação monitora). Logo, Receita e Custo ganham contas de **deferimento** (ativo) separadas da Provisão (passivo).
**Fase 1** — Plano de Contas: grupo `1.1.06 "Custos a Apropriar"` (ativo diferido, 11 subcontas espelho de `2.1.04.x`, generaliza o padrão dos impostos `1.1.05`); `2.1.06` "Adiantamento de Clientes" → **"Receita a Realizar"** (migração **pontual** idempotente, só renomeia o default antigo — não name-sync geral).
**Fase 2** — Contrato: novo `registro_venda_contrato` (`1.1.02 × 2.1.06`, Val_Cont cheio); as 10 rubricas (9 + **Custo de Fábrica**, 10ª nova) constituídas como `1.1.06.0X × 2.1.04.0X` **sem tocar a DRE**; `recebimento_venda` passa a abater `1.1.02` (era `2.1.06`).
**Fase 3** — NF-e: `reconhecer_despesas_nfe` (**matching pleno**) reconhece TODAS as despesas de uma vez (`5.6.0X`, ou `5.1.01` p/ fábrica) × baixa do ativo `1.1.06.0X`; a Provisão sobrevive. `faturamento_cmv` **retirado** (o CMV agora é `5.1.01 × 1.1.06.06`, sem re-creditar a provisão) → **resolve o duplo-hit**.
**Fase 4** — `reclassificar_provisao` (`2.1.04.06→2.1.04.14`) espelha o ativo `1.1.06.06→1.1.06.14` **só na proporção ainda não baixada na NF-e** (robusto p/ reclass antes/depois da NF-e); matching reconhece Outros Fornecedores (`5.1.01 × 1.1.06.14`); sobra/falta (`resolver_saldo_provisao`) e `reconciliacao` cobrem as 10.
**Fase 5** — Ajuste 1 (frontend): `carregarOrcamentos()` trava no **orçamento contratado** quando há contrato (backend expõe `contratado_id` no `/orcamentos`, aditivo).
**Fase 6** — `mod_ciclo` etapa **21 "Conciliação Final"** (após a 20); `mod_contabil.conciliar_final` resolve à força o saldo remanescente das 10 (impostos fora); endpoint `POST .../ciclo/21/conciliar` (gate financeiro) concilia + encerra o projeto com status **`concluido`** (distinto de `fechado`); frontend: card + badge "Concluído". _(bug de rota corrigido: `_re` só existe no `do_POST` a partir da l.3790 → usei `re` global.)_
**Decisão:** projetos legados (fluxo antigo, 9 rubricas batendo DRE no fechamento) **ficam como estão — sem migração retroativa**; o modelo novo vale só p/ contratos gerados daqui em diante. **🟡 aberto** (não-bloqueante): painel de Reconciliação mostra `saldo` bruto (provisionado−efetivado) mesmo pós-resolução (a resolução vive em `resolvido`) — avaliar se confunde num projeto "Concluído".

## Sessão 69 (retroativa) — Outros Fornecedores (2.1.04.14) + reclassificar_provisao
Registro retroativo dos commits `bb2f7d1`/`f00c94e` (já na `main` desde a frente anterior, sem Sessão própria). `2.1.04.14 "Provisão de Outros Fornecedores"` + `reclassificar_provisao(cod_de, cod_para, valor)` (passivo × passivo, origem `reclassificacao_provisao`, idempotente): permite a **substituição de custo** — parte da Provisão de Custo de Fábrica (2.1.04.06) migra p/ Outros Fornecedores, de modo que **cada provisão reconcilia com o seu efetivado** e a soma dos saldos = a economia total. `reconciliacao` já trata a origem reclass (provisionado = créditos + reclass-in − reclass-out). Na FASE D2 (Sessão 70) essa função ganhou o espelho do ativo diferido `1.1.06`.

## Sessão 68 — Rebrand de cor: paleta da logo Orizon Manager (dourado/laranja removidos)
Frente de design, **só tokens** (baixo risco, frontend = Ctrl+F5). Fonte da verdade: `docs/design-tokens.md §2.0` (CANÔNICA, validada com o chat do Claude). Diff do `:root` mostrado e aprovado antes de aplicar.
**Nova paleta (logo):** navy `#0B1D3A` (`--surface`) / `#081120` (`--bg`) / `#12294A` (`--surface-2`) · accent **ciano** `#00B8C9` (dark) / `#0E7C8C` (light) · **primário/links azul elétrico** `#0066FF` · texto `#E6EBF1`/`#0B1D3A` · muted `#8A96A3`/`#5A6572` · borders `#1C3459`/`#DCE3EC`. `--warn` (âmbar) e `--err` (coral/vermelho) mantidos.
**Removido:** `--gold` / `--gold-tint` / `--dalm-gold` / `--dalm-gold-light`. Status **"fechado"** deixou de ser dourado → **azul** (`--info` `#5B9BFF` dark / `#0066FF` light). Botão primário passou do petróleo próprio (v10) para o **azul da marca**.
**Repointing do legado (`index.html`):** 17× `var(--dalm-gold…)` → `--accent` (títulos de seção/modais/links); status "processando" NF-e/NFS-e → `--info`; badge `.fechado` fundo dourado → tint azul `rgba(91,155,255,.16)`; fallbacks `var(--warn,#b8960c)` → `var(--warn)`. **Sem laranja legado** (`#E8611A`/`rgba(232,97,26)`) no código atual. **`login.html`:** `:root` próprio divergente alinhado à mesma paleta (+ `--primary`/`--primary-tint`, gold removido).
**De-green total (2ª rodada, a pedido — "botão de usuário estava verde"):** o accent antigo era **verde-menta**, e sobrou verde legado fora dos tokens dourados. Corrigido: **avatar** do botão de usuário + modal "Meu Perfil" → **azul `--primary`** (texto branco); família **`--teal-*`** repontada de verde-menta p/ **ciano** (mantidos os nomes, cards de valor financeiro agora ciano); todos os `rgba(93,202,165,…)` (mint) e `rgba(25,201,160,…)` (emerald) → `rgba(0,184,201,…)` (ciano); badges verdes (`para_assinatura`, `aprovado`) → fundo ciano-escuro + `var(--ok)`; fallbacks mortos (`#5DCAA5`, `#0d1a0d`, `#2a4a3a`, `#6a7a6a`, `#4caf82`) neutralizados p/ ciano/navy. **`--warn` (âmbar) e `--err` (coral/vermelho) seguem mantidos.** Grep de verde (mint/emerald/teal/#4caf/#80e090) em `static/*.html` → **ZERO**.
**Verificação:** grep por `b8960c|D4B348|E8611A|dalm-gold|--gold|gold-tint` em `static/*.html` → **ZERO resíduo** nos dois arquivos. (`node --check` indisponível nesta máquina; mudanças foram só troca de valores de cor, sem alterar estrutura JS.) Prints/contraste nos 2 temas = conferência visual do usuário (Ctrl+F5). **Docs:** `Padrao_Design_Orizon_v10.docx` ganhou seção "REBRAND DE COR" (paleta nova + antiga marcada como superada). **Pendência:** imagens `orizon_design_reference_dark/_light.png` desatualizadas (não regeneráveis por código).

## Sessão 67 — Infra contábil FASE D: reconciliação (Provisionado × Efetivado × Saldo × Destino) + Contas a Pagar + Simulação Claude
Branch `feat/financeiro-fase-d-reconciliacao` (mergeada). Área sensível; TDD; decisões contábeis com o usuário. Suíte 909→**923**.
**Princípios que o usuário fixou (memória):** (1) **fonte única = razão** — lançamentos por conta+`projeto_id` são a verdade; painéis são views (`reconciliacao(projeto_id)` serve consolidado=None e granular=X). (2) **rigor contábil > escopo** — no efetivado, escolheu **competência** (Fornecedores a Pagar) em vez de caixa direto, mesmo abrindo o MVP de Contas a Pagar.
**D1 (backend):** contas `4.4.02 Reversão de Provisões` (sobra→receita) / `5.6.10 Ajuste de Provisões` (falta→despesa) + evento `pagamento_fornecedor` (2.1.01×1.1.01). Funções: `efetivar_provisao` (2.1.04.x × **2.1.01**, competência — reconhece o custo real como obrigação, não baixa em caixa) · `resolver_saldo_provisao` (sobra→4.4.02, falta→5.6.10, zera a provisão) · `reconciliacao(projeto_id)` (provisionado=créditos, efetivado=débitos, saldo, resolvido; resoluções excluídas p/ não contaminar) · `contas_a_pagar` (saldo 2.1.01 em aberto, MVP conta/projeto). `total_lancado` ganhou filtro por origem.
**D2 (endpoints+front):** GET `reconciliacao-provisoes`/`contas-a-pagar`, POST `efetivar-provisao`/`resolver-saldo-provisao`/`pagar-fornecedor` (gate `aprovar_financeiro`). Painéis Financeiro: **Reconc. Provisões** (seletor consolidado/projeto; efetivar manual + resolver) e **Contas a Pagar**. **Aba Reconciliação no Projeto** (modal, granular — mesma fonte). Sub-razão de títulos por fornecedor/vencimento = fase futura.
**Bug crítico resolvido:** "contas a pagar falha ao carregar" + "Projetos vazio" — causa: **4 processos `main.py` fantasmas**, um servia a 8765 sem a D2 (front novo × backend velho). Diagnóstico: endpoint dava 404 cru; matou todos, subiu **um** limpo. (Mudança de Python exige restart; múltiplos servidores mascaram.)
**Simulação Claude (dados REAIS dos 3 XMLs Promob):** parser `promob_grupos` (venda+custo por ambiente) → motor real (Aymoré 10x/entrada 20k via `mod_fin.aymore`, arq 6%, fid 2%, viagem 5k) → orçamento (VBVO 223.530 · CFO 80.406 · **Val_Cont 278.769** = VAVO 247.651 + Cust_Fin 31.118 · impostos 12%) → fechamento → faturamento segmentado 65/35 + CMV=CFO congelado + impostos → **2ª aprovação** (PE −5%, pedido fábrica 20% menor + outros forn. 10% ⇒ real 90% do CFO_PE; montagem insumos 1,5%/assist 3%/gar 1%) → efetivação pelas NFs reais → reconciliação. **CMV congelado; ganho vira SOBRA** (Custo Fábrica 80.406 vs efetivado 68.747 = **sobra 11.659→receita**). Regra: só resolve provisão **efetivada**; as demais ficam abertas (custo futuro). Balanço fecha; Σ receitas=Val_Cont; Contas a Pagar 82.368.
**Furo que a simulação revelou + corrigiu:** a `dre()` montava `receita_bruta=4.1+4.2` e **ignorava o grupo 4.4** → a **falta** (5.6.10) entrava na DRE mas a **sobra** (4.4.02) ficava órfã. Corrigido: DRE inclui **Outras Receitas (4.4)** no resultado → lucro líquido da simulação **81.939 → 93.598** (a reversão de 11.659 agora aparece), simétrico com a falta.
**Backlog (anotado):** eventos de **estorno de cancelamento fiscal** (B2); sub-razão de Contas a Pagar por fornecedor/vencimento (aging).

## Sessão 66 — Infra contábil FASE C: painel de Provisões por tipo A/B/C/D
Branch `feat/financeiro-fase-c-provisoes-tipos` (mergeada na `main`). TDD (backend) + verificação manual (frontend). Suíte 906→**909**.
**C1 (backend):** `_PROV_PAINEL_TIPO` mapeia `2.1.04.x → A/B/C/D` (data-driven; conta nova sem tipo → **"O" Outros**, aparece mesmo assim). `contas_provisao_do_plano` passa a devolver `tipo`; `dashboard_financeiro` ganha `provisoes_por_tipo` (grupos na ordem A→B→C→D→O, cada um com `rotulo`/`itens`/`subtotal`; mantém `provisoes` plana + `total_provisoes_abertas` p/ compat). Invariante testada: Σ subtotais = total. Mapeamento: A=comissões/pessoas (.10/.11/.12) · B=custos futuros (.02/.03/.05) · C=aquisição/fábrica (.06/.07/.08/.09) · D=fiscal (.13).
**C2 (frontend):** painel `Financeiro › Provisões` renderiza **um card por grupo** (cabeçalho `tipo · rótulo` em accent + subtotal; linhas de provisão por dentro), tokens/`.surface-2`, 2 temas. **Fallback robusto:** se o backend não devolve `provisoes_por_tipo` (servidor não reiniciado / versão antiga), cai na lista plana — nunca fica vazio (foi o sintoma reportado: a C1 é Python e exige restart; sem ele o front antes zerava). Verificado no navegador com projeto-demo populado (A 9.865,78 · B 17.040,89 · C 70.047,00 · D 15.540,63) e depois limpo.
**Próximo: FASE D** — reconciliação (Provisionado × **Efetivado** × Saldo × Destino, por provisão/projeto): o custo real (NF fábrica + outros forn. + insumos) entra como **Efetivado**; a diferença CFO−real (e provisionado−efetivado das demais) vai ao resultado. + eventos de **estorno** de cancelamento fiscal (backlog anotado na B2).

## Sessão 65 — Infra contábil FASE B2: eventos (Adiantamento → receita segmentada → CMV=CFO → provisões completas)
Branch `feat/financeiro-fase-b2-eventos` (mergeada na `main`). Área sensível; TDD; design intrincado via **Fable 5**; plano por sub-fase, parou antes de mergear p/ conferência dos números. Suíte 891→**906**.
**Contexto:** fecha a infra contábil p/ o Projeto Simulação popular DRE/Balanço/Provisões pelo fluxo REAL de fechamento. Decisões do usuário validadas número a número (o razão reconcilia com o motor **centavo a centavo**: lucro líquido = Val_Liq − Cust_Var do motor; margens diferem só pela base Val_Cont × Val_Liq = Cust_Fin).
**B2.1 — eventos + Adiantamento + CMV:** 7 eventos novos (`recebimento_venda` 1.1.01×2.1.06; faturamento **segmentado** Mercadoria 4.1.01 / Serviço 4.2.01 com split adiantado/a-receber; `faturamento_cmv` 5.1.01×2.1.04.06 = **CFO** congelado, 1×/projeto; `pagamento_fabrica` 2.1.04.06×1.1.01). Orquestrador `faturar_segmento()` saca `min(pool, segmento)` do Adiantamento → 2.1.06 **nunca negativo** (prova por indução + crash-safe) e **Σ receitas = Val_Cont**. Congela a segmentação na assinatura (`_congelar_segmentacao_no_projeto`, A6). O evento `faturamento` legado sai do wiring. Fail-soft.
**B2.2 — bug `reconciliar`:** `margem_projeto` expõe `custo_servico` (5.2 + provisões 5.6.x) → destrava `reconciliar(proporcional_custo_direto)` (KeyError). Margem inalterada.
**B2.3 — face fiscal (decisão do usuário: reescalar):** `mod_nfe.rescalar_itens_para_total` reescala os itens da NF-e p/ Σ = parcela Mercadoria (fecha ao centavo, resíduo no último item); NFS-e = parcela Serviço. Markup vira output/fallback. ICMS/alíquotas ficam p/ a frente Fiscal (contador). `_valores_segmentados_do_projeto` = fonte única (face fiscal + wiring contábil).
**B2.4/B2.5 — constituição COMPLETA + custo financeiro:** contas `5.6.04-09` + `constituir_provisoes_fechamento(valores do motor)` constitui TODAS as rubricas rastreadas (montagem/garantia/assist + frete fáb/local/insumos/com med/proj/retenção), cada Despesa 5.6.x × Provisão 2.1.04.x. Custo Fábrica NÃO entra aqui (é CMV=CFO). **Custo financeiro** (Cust_Fin = Val_Cont − VAVO) = despesa DIRETA no contrato (5.5.03×2.1.05) — decisão do usuário (o fechamento É a antecipação).
**B2.6 — impostos = PROVISÃO diferida (decisão do usuário):** contas `1.1.05 Impostos a Apropriar` (ativo diferido) + `2.1.04.13 Provisão de Impostos`. CONTRATO: `1.1.05 × 2.1.04.13` (passivo nasce, **DRE intocada**). EMISSÃO (proporcional Merc/Serv, emissões separadas mesma data): `4.3.01 × 1.1.05` (dedução entra na DRE, baixa o ativo) + `2.1.04.13 × 2.1.03` (obrigação fiscal real). Helpers `total_lancado`/`efetivar_impostos_segmento`. Chave: imposto **é** provisão (Balanço); "dedução" é só a linha da DRE onde imposto sobre venda se apresenta — e só surge na emissão.
**B2.7 — wire do fechamento completo:** o composition root lê `_negociacao_breakdown` (motor) → `constituir_provisoes_fechamento` (todas + impostos-provisão) + custo financeiro; no faturamento efetiva a parcela de impostos do segmento junto com a receita. `_fin_provisoes_venda_seguro` reescrito (motor, não mais só 3 provisões).
**Simulação ponta a ponta (Projeto 21):** Val_Cont 194.257,89 · CFO 64.523,73 · Σ provisões 47.970,57 + custo fin 14.880,15. DRE: receita 194.257,89 − deduções(impostos) 15.540,63 − CMV 64.523,73 − constituição 32.429,94 − res. financeiro 14.880,15 = **lucro líquido 66.883,44** = Val_Liq − Cust_Var (motor). Balanço fecha em cada passo; CFO 1×; Σ receitas = Val_Cont. Margem contábil 34,43% (Val_Cont) × negociação 37,29% (Val_Liq).
**Testes:** `test_fase_b2_eventos.py` (21), `test_nfe_rescalar.py` (6), e2e do wiring/face fiscal reescritos, `test_fold_nao_duplica` adaptado ao novo wire. `[CONFIRMAR CONTADOR]`: T1 receita no doc · T2 adiantamento passivo (Simples) · impostos-provisão diferida · custo financeiro direto · cancelamento fiscal sem estorno (backlog FASE D). **Próximo: FASE C** (painel de Provisões por tipo A/B/C/D) e **FASE D** (reconciliação: Provisionado × Efetivado × Saldo × Destino).

## Sessão 64 — Infra contábil FASE B1: segmentação de receita Mercadoria × Serviço
Branch `feat/financeiro-fase-b1-segmentacao` (mergeada na `main`). Área sensível (dinheiro); TDD; plano aprovado antes de codar; parou antes de mergear p/ conferência. Suíte 879→**880**.
**Contexto:** parte da frente "infraestrutura contábil ponta a ponta" (contas + eventos + painéis p/ o Projeto Simulação popular tudo). FASE A (caixinhas: Adiantamento de Clientes 2.1.06 + Provisão Custo Fábrica 2.1.04.06 + demais provisões) já fechada e no VPS. **B1** monta a base da **receita segmentada** (decisão do usuário: NÃO desligar a NFS-e; o Val_Cont divide-se em Mercadoria + Serviço, cada parte no seu documento, sem duplicar — e já prepara a futura **distribuidora**: parcela Mercadoria = receita da distribuidora, Serviço = receita da loja).
**Regra de segmentação (estabelecida agora):** `Val_Cont = pct_mercadoria%·Mercadoria + pct_servico%·Serviço` (soma obrigatória 100). **Default por loja** em Admin › Dados da Loja (`Loja.pct_mercadoria`/`pct_servico`, **seed 65/35**, migração idempotente com backfill). **Override por projeto** em `parametros_json`, editável **só pelo Diretor** (gate `aprovar_financeiro`, mecanismo atual do `perfis.py` — NÃO amarrado à refatoração Master/Gerencial/Operador). Sem override, herda a loja.
**Funções puras** (`mod_orcamento_params.py`): `SEGMENTACAO_DEFAULT`, `segmentar(Val_Cont, pct_merc)` (serviço = **resto**, soma fecha exato no Val_Cont), `validar_segmentacao` (soma=100 + faixa), `resolver_segmentacao` (NULL→65/35), `segmentacao_efetiva` (override vence loja).
**Endpoints:** `PATCH /api/admin/lojas/<id>` aceita `pct_*` (gate `editar_dados_loja`, valida soma=100); `POST /api/projetos/<nome>/parametros` aceita `pct_*` override (gate `aprovar_financeiro`, valida, persiste preservando override anterior — `merge_parametros` ignora chaves fora do `PARAMETROS_DEFAULT`, então `pct_*` é tratado à parte). `_loja_dict` expõe `pct_*`.
**Frontend:** Admin › Dados da Loja ganha os 2 campos % (checa soma=100). No **modal de Parâmetros**, a segmentação fica **sob o MESMO cadeado 🔒 da margem real** (`_impostosLiberados`, liberação por senha de diretor/gerente adm-fin) — sempre visível, campos revelados só após a senha; **auto-salva ao alterar** (debounce, chamada isolada — um 403 não quebra o save dos outros parâmetros); os 2 campos espelham-se p/ somar 100. _(Iteração de UX: primeiro bloco dependia de flag de perfil `pode_aprovar_financeiro` no payload — exigia restart e "não aparecia"; trocado pelo cadeado, flag revertida.)_
**Testes:** `test_segmentacao.py` (8, puras), `test_loja_segmentacao.py` (2, ORM 65/35), `test_endpoints_segmentacao.py` (7, incl. gates + "override sobrevive a salvamento de outros parâmetros"). `node --check` OK.
**Próximo — FASE B2 (design com Fable 5):** eventos de dupla-partida (recebimento_venda 1.1.01×2.1.06; faturamento com **receita segmentada** — Mercadoria 4.1.01 na NF-e + Serviço 4.2.01 na NFS-e — baixando o Adiantamento; CMV 5.1.01×2.1.04.06 = **CFO** congelado; pagamento_fabrica 2.1.04.06×1.1.01), com prova de não-duplicação (CFO 1×) e o timing marcado `[CONFIRMAR COM CONTADOR]`. **CMV = `orc.cfo`** (custo real da fábrica + outros forn. + insumos entram como **Efetivado** na reconciliação/FASE D; diferença CFO−real vai ao resultado). Bug latente a corrigir junto: `reconciliar(proporcional_custo_direto)` → KeyError `custo_servico` (alinhar `custo_servico` à segmentação). Depois: FASE C (painel de Provisões por tipo A/B/C/D) e FASE D (reconciliação com Efetivado).

## Sessão 63 — Frente Financeira: painel de provisões consolidado + fold Montagem/Garantia na aprovação (FASE 1–2)
Branch `financeiro-provisoes` (NÃO mergeada — aguardando conferência). Área sensível (dinheiro); TDD; design intrincado via **Fable 5** (subagente). Suíte 850→**857**.

**FASE 1 — `contas_provisao_do_plano`:** extraída de `dashboard_financeiro` a enumeração data-driven das contas analíticas de `GRUPO_PROVISOES` (2.1.04.%) com saldo em aberto (exclui .01 Comissão / .04 Devolução). Reusável (FASE 3). Comportamento idêntico; teste `test_contas_provisao_do_plano.py`.

**FASE 2 — fold de Montagem/Garantia na Marg_Cont (modal de APROVAÇÃO financeira por orçamento):** a modal (colunas Venda/Rev1/Rev2/Atual, Concorda/Revisa) mostrava a Marg_Cont **antes** de Montagem/Garantia (elas não estavam no `Cust_Var` do motor). Agora `mod_provisoes.provisoes_orcamento` inclui `Prov_Mont = round(montagem_pct% × VAVO, 2)` e `Prov_Gar = round(garantia_pct% × VAVO, 2)` no `Cust_Var` (12 rubricas). **Base = VAVO** (ver correção abaixo) e mesmo arredondamento da constituição no fechamento → a linha da modal bate centavo a centavo com o lançamento `5.6.x`.

**Correção de base (achado do Fable 5) + convenção canônica (NOMENCLATURA §3b):** as provisões % **sobre a venda** (Montagem, Garantia, Assistência, Frete Local, Insumos Locais) usam **VAVO** (valor à vista, após extrair o `Cust_Fin`); Frete Fábrica-Loja usa CFO; Prov Impostos usa Val_Cont; comissões seguem a cadeia (inalteradas). **Bug corrigido:** a **assistência** constituía em `Val_Cont` (`constituir_provisoes_venda` recebia `orc.valor_total`) enquanto o motor usava VAVO — divergiam quando `Cust_Fin>0`. Fix: `_fin_provisoes_venda_seguro(orc, projeto_id, ref)` passa `orc.vavo`; `constituir_provisoes_venda(..., vavo, ...)` (renomeado); o fold em `mod_provisoes` passou de Val_Cont→VAVO. Agora os DOIS lados (motor e razão) usam VAVO → montagem/garantia/assist da modal == constituição, centavo a centavo. **Não-duplicação mantida** (`test_fold_nao_duplica.py`, incl. `test_constituicao_usa_vavo_nao_val_cont` com Cust_Fin>0). Suíte **859**.
- **[HISTÓRICO]** Constituições **já lançadas** com base `Val_Cont` (antes do fix) ficam divergentes. Em **dev**: recriar o banco via `seed.py` resolve. Se houver **dado real** em produção: tratar como **correção contábil** (lançamento de ajuste da diferença), **não** reescrever silenciosamente o razão. `itens_provisao`/`cust_var_marg_cont` **sem mudança de assinatura** (as siglas propagam por `d.update(prov)` em `_negociacao_breakdown` — evita 2ª fórmula divergente). `main.py`: comparador `desatualizado` passa a comparar só as chaves do snapshot (snapshot pré-fold não vira falso-positivo). Frontend: `_PROV_RUBRICAS` +2.
- **[DECIDIDO] Modelo:** foldar na própria Marg_Cont (opção escolhida pelo usuário entre 3). **Snapshots antigos:** aceitar defasagem (não recomputar/migrar — registro não guarda Val_Cont da época; rev1/rev2 são atos aprovados); colunas antigas mostram "—". **Revisa:** Montagem/Garantia **editáveis** como as demais (precedente da assistência; o Revisa nunca toca o razão).
- **[DECIDIDO] Não-duplicação (crítico):** o fold é VISÃO (`mod_provisoes`, puro); `mod_contabil`/`database` **zero mudanças**; DRE/Balanço inalterados — prova mecânica em `tests/test_fold_nao_duplica.py` (fotografa DRE/Balanço + nº de lançamentos antes/depois). Docs: NOMENCLATURA §3 + `PROVISOES_E_VARIAVEIS.md`.

**[PENDENTE — Custo Fábrica / CMV] (achado ao validar o Projeto_21):** o **custo do produto (CFO) NÃO é lançado no razão** hoje — não existe evento de CMV (nenhum débito em `5.1` no mapa `EVENTOS`), então `dre()["cmv_csp"]` é estruturalmente **0** (o próprio DRE tem `obs: "Refinar com contador"`). Receita é lançada só na **autorização da NF-e** (`faturamento`, `4.1.01`, `main.py:5648`); provisões na assinatura (VAVO). Próxima fase = a **Provisão Custo Fábrica** (a FASE 2 original, adiada): CMV entra como `DÉBITO 5.1 (custo do produto) × CRÉDITO 2.1.04.06 (Provisão Custo Fábrica = CFO)` — CFO uma vez só no resultado, contrapartida = caixa reservado à fábrica; + reconciliação (baixa contra remessas do "Controle de Entrega de Material"). Decisão de modelo + Fable 5 + OK antes de implementar. A **base VAVO da correção foi validada no Projeto_21 real** (orç 24, Cust_Fin>0): modal Montagem 14.350,22 / Assist 1.793,78 / Garantia 896,89 == o que a constituição lançaria, centavo a centavo; Marg_Cont na venda 44,95%, Markup 2,78.

**[PENDENTE — FASE 3] Individualização por projeto (módulo Projetos):** tabela por projeto (provisões por conta com saldo do projeto; Marg_Cont recalculada ao editar; Markup = Val_Liq/CFO; extensível). **REGRA (decidida agora):** na **reconciliação**, o valor **"provisionado"** vem da **constituição no razão (2.1.04)** — o saldo contábil da conta de provisão do projeto —, **NÃO** do valor editado no Revisa (que é previsão gerencial da aprovação, sem efeito contábil). O Revisa informa a visão; a reconciliação (provisionado × efetivo) usa o razão.

## Sessão 62 — RESET: Perfis de acesso CONFIGURÁVEIS por loja (rev3) + step-up + revisão de design
Substitui o modelo hardcoded de 4 perfis (Sessão 61) por **perfis configuráveis no banco, por loja**, com 3 padrão. Executado via subagentes com TDD; suíte 793→**846** (0 regressão). Branch `perfis-configuraveis` → merge na `main`. Deploy no VPS (banco preservado; migrações idempotentes no startup).

**Arquitetura (base + módulos):** tabela `perfil_acesso` (`loja_id, slug, nome, base, modulos_json, capacidades_json, sistema`). Acesso a **módulo/painel** vem de `modulos_json`; **capacidades finas** têm preset da `base` (master/gerencial/operador em `perfis.py`) + override por perfil em `capacidades_json`; `desconto_max` segue da base. Plataforma (`super_admin/admin_rede`) fica fora da tabela (fallback hardcoded). `perfis.py` virou **adaptador com registro cacheado do DB** (`recarregar()` após escrita e no fim de `init_db`); `pode(slug,cap)` resolve override→base; `acessa_modulo/painel/matriz_loja/slugs_da_loja` leem o registro. Truque p/ não tocar ~40 gates: slug **global único** → `pode(slug)` sem `loja_id`.

**Matriz dos 3 padrão:** Master (operacionais+fiscal+financeiro/folha+admin+config), Gerencial (idem sem admin/config), Operador (operacionais+fiscal, sem financeiro/folha/admin/config). Migração `perfis_v4_2026`: `diretoria→master, consultor/suporte→operador`. Seed `perfil_acesso_seed_v1` por loja (idempotente).

**Novos arquivos:** `perfil_store.py` (seed + `criar/editar_perfil`), `mod_perfis.py` (validadores puros). **DB:** `PerfilAcesso`, `LogAcessoDelegado`, `Funcao.perfil_padrao`.

**Endpoints:** `GET/POST/PATCH /api/admin/perfis` (criar/editar restrito ao Master via `gerir_perfis`; sistema não editável); `perfis-matriz` por loja; `perfis.existe` + `mod_tenancy.perfis_atribuiveis` reconhecem perfis do DB (assinalar perfil custom a usuário). **Mapa de Funções:** `Funcao.perfil_padrao` no serialize/aplicar.

**Step-up por senha:** `POST /api/auth/step-up` valida senha de quem tem o recurso, grava `LogAcessoDelegado`, concede grant em memória (TTL 30 min); `_sem_acesso_modulo` honra o grant e retorna `precisa_stepup`. Frontend: interceptor de fetch trata `403 precisa_stepup` → modal → refaz a requisição; **módulos bloqueados aparecem no hub/sidebar com cadeado** → clique dispara o step-up. Painéis Admin/Config ficaram **hidden** (elevação de painel = decisão de modelo futura, ver PENDENTE).

**Frontend (painel Perfis de Usuário):** editável (Master), seletor **Perfis | Funções**, modal com 2 tabelas (módulos + capacidades finas), botão "?" abre detalhe read-only. Sem o conceito "Base" na UI (detalhe interno).

**Revisão de design (theme-aware):** modais migrados p/ `.modal-overlay/.modal-box` (fim dos `#111d11/#0a120a`); **regra global de `select` e `textarea`** (fim dos campos brancos/quinados no escuro); abas/pills por fundo+sombra (sem sublinhado/linha gold/verde); botão primário com borda teal suave; toggle de tema neutro; **Config movido p/ junto do Admin**; **botão "Sair" no rodapé** (modal "Meu Perfil" mantido, restilizado); caixas de alerta com tints translúcidos; bordas gold de campos → neutras. Cronograma (template): coluna **Início (Dn acumulado)** + **Data prevista** (D0 = assinatura, ou solicitação se compra programada; simulação ao vivo).

**Fixes de brinde:** `_PERFIS_ESCOPO_PROPRIO`/`_ESCOPO_POSSE` (escopo "vê só os próprios projetos") e `mod_cadastro` default → dirigidos pela **base** (`operador`); `_NIVEIS_AUTORIZAR` no cronograma do projeto → slugs novos (o lápis de editar data prevista voltou a aparecer). Dados: reatribuído "Consultor de Vendas" a 3 contas operador que ficaram sem função na migração v3.

**[PENDENTE]** (MÉDIA) Step-up dos **painéis Admin/Config** — hoje escondidos; precisa definir a semântica de elevação (quais capacidades uma autorização de painel concede). (BAIXA) `contrato_editar.py:61` usa slugs pré-Perfil-4 (`gerente/diretor/admin`) — gate efetivamente sempre-verdadeiro, bug pré-existente a corrigir.
**[DECIDIDO]** Perfis por LOJA (rede fica p/ painel de gestão de rede futuro; tabela já nasce com `loja_id`). Base+módulos (não derivar finas dos módulos). Slug global único. Capacidades finas selecionáveis por perfil (override sobre a base).
**[ARQUIVOS]** `perfis.py`, `perfil_store.py`(novo), `mod_perfis.py`(novo), `database.py`, `main.py`, `auth.py`, `auth_routes.py`, `mod_cadastro.py`, `mod_escopo.py`, `mod_tenancy.py`, `modulos.py`, `seed.py`, `static/index.html`, `tests/*`, `docs/superpowers/plans/2026-07-10-perfis-configuraveis-por-loja.md`.

## Sessão 61 — Perfil vira 4 níveis de acesso; cargos viram Função (Regras rev2 §2)
Refactor de núcleo (plano aprovado, TDD). ~13 níveis-cargo → **4 perfis de acesso por módulo/painel**; cargos viram Função. NÃO trata escopo por Etapa/ambiente (frente posterior) — só não quebra os gates. Suíte 813→**816**.
**perfis.py:** `PERFIS` = diretoria/gerencial/consultor/suporte (+super_admin/admin_rede), com `acesso_operacional/financeiro/fiscal/admin/config` + capacidades preservadas grosseiras + desconto 50/20/10/0. Helpers `acessa_modulo`/`acessa_painel`; `CAPACIDADES` ganha grupo "Acesso"; `matriz()` recalcula. _(Decisões: mapa do doc; escopo-por-Mapa dos operacionais dormente até re-chave por Função; consultor mantém executar_pe/registrar_medicao p/ não travar o ciclo.)_
**Migração `perfis_v3_2026`** (idempotente, guardada): colapsa `nivel` pelo mapa (diretor→diretoria, gerente_vendas→gerencial, gerente_adm_fin→diretoria, resto→consultor) e seta `Usuario.funcao_id` (nova coluna) com o cargo antigo via `Funcao` da loja.
**Enforcement da matriz:** `_contabil_ctx` bloqueia Financeiro por `acesso_financeiro`; `/api/folha` e `/perfil-fiscal` por acesso; `auth_routes` filtra o **hub** pelos módulos do perfil + expõe `acessa_admin`/`acessa_config`; frontend esconde navs Admin/Config e módulos fora do perfil.
**Usuários da Loja:** Função = do Funcionário vinculado OU `Usuario.funcao_id` (cargo migrado); Perfil = nivel. `seed.py`/`conftest` nos 4 perfis; `_NIVEIS_ATRIBUIVEIS` deriva de `acesso_operacional`.
**Testes:** `test_perfis.py` reescrito; `test_acesso_perfil.py` (§9: Consultor 403 em Financeiro/Folha, hub/`auth/me` reflete a matriz, Suporte só painéis, Função fallback); `test_migracao_perfis` (cadeia v2+v3); ~11 arquivos migrados aos novos slugs (teste "sem capability" do PE passa a usar Suporte). _(Follow-ups: re-chave do escopo p/ Função; precisão fina por Função; gate backend dos operacionais p/ Suporte; resto de docs/USUARIOS.md.)_

## Sessão 60 — Perfis de Usuário: formalizar os níveis de acesso (frente irmã §8)
Plano aprovado; TDD. Dá rosto ao que `perfis.py` **já** governa (surface read-only, sem editor). Suíte 812→**816**.
**Mostrado ao usuário (pedido dele):** a matriz real de `perfis.py` — 12 perfis × 11 capacidades + desconto_max, tudo já acionando o enforcement (nada a desenhar do zero).
**`perfis.py`:** `CAPACIDADES` (metadados legíveis: rótulo/descrição/grupo por capacidade) + `matriz()` (perfis com capacidades resolvidas, escopo loja/plataforma, desconto_max) — derivado de `PERFIS`, read-only.
**`main.py`:** `GET /api/admin/perfis-matriz` (gate `gerir_usuarios`).
**Frontend:** a aba **Admin › Perfis de Usuário** — que ainda tinha a ferramenta legada single-user ("perfil ativo" + editor de desconto, vestigial desde a Fase 0) — foi **substituída** pela matriz real (tabela perfil × capacidades em chips, escopo, desconto máx + legenda das capacidades). Read-only; **aposenta a tela legada**. `docs/USUARIOS.md` ganhou nota da tela + os três eixos (Perfil × Função × Escopo). Testes `test_perfis_matriz.py` (trava anti-órfão de capacidade, derivação, gate). _(Fora de escopo: editor de perfis por loja = P1 futuro.)_

## Sessão 59 — Fase 1: Mapa de Atribuições + escopo de visibilidade (Regras_Funcoes_Perfis §4–§9)
Plano aprovado antes de codar; 6 incrementos TDD. Suíte 799→**812**. Backend fronteira no padrão puro do `mod_tenancy`.
**F1.1 modelo:** `atribuicoes_ambiente` (papel PE/Medição/Montagem/Assistência × ambiente; `pool_ambiente_id` NULL=projeto inteiro; `UniqueConstraint(projeto,ambiente,papel)`) + `Terceiro.usuario_id` (conta opcional, só coluna) + migração; módulo núcleo `escopo` no manifesto. _(NULL é distinto no SQLite → unicidade de "projeto inteiro" vem do upsert do CRUD.)_
**F1.2 `mod_escopo.py` (puro):** `pode_ver_projeto/ambiente`, `resolver_responsavel` (ambiente>projeto-inteiro>None), `projetos_visiveis`, `visao_do_papel`, `funcao_compativel` (§7). Gerência+ tudo, Consultor posse, operacional (projetista_executivo/medidor/supervisor_montagem) só o atribuído, admin nada.
**F1.3 CRUD:** `GET/POST /api/projetos/<nome>/atribuicoes` — upsert 1:1 (substitui), alvo vazio limpa, alvo da loja + **função compatível** com o papel, auditado em `LogAcaoGerencial`; edita só Gerência+/Supervisor de Montagem.
**F1.4 enforcement:** `_projeto_visivel_ao_ator`/`_filtrar_projetos_por_loja` roteados por `mod_escopo` (resolve o Mapa via `Funcionario.usuario_id`/`Terceiro.usuario_id`). Fora de escopo → **404**. §9: Consultor A não vê projeto de B (link→404), operacional só o atribuído, Gerência+ tudo, F4 intacto.
**F1.5 ciclo + visão do papel:** `/ciclo` expõe `responsavel_efetivo` = override da etapa (v12) OU default do Mapa (etapa→papel §7). Operacional barrado (403) no comercial (`margens`, `negociacao-preview`) via `_bloqueio_comercial`.
**F1.6 frontend:** modal **Mapa de Atribuições** (botão no painel do Ciclo, só Gerência+/Supervisor): grade papel × [projeto inteiro + ambientes], dropdown funcionário/terceiro filtrado por função. Testes `test_atribuicoes.py` (13). _(Follow-ups: conta do Terceiro; seed de funções em loja nova; campo `papel` na Tabela de Funções; redação campo-a-campo do comercial.)_

## Sessão 58 — Fase 0: perfis.py fonte única + seed da Tabela de Funções (Regras_Funcoes_Perfis §0)
Pré-requisito da frente "Mapa de Atribuições". Separa Perfil (acesso) × Função (cargo). Backend+frontend+testes TDD. Suíte 793→**799**. **Plano aprovado antes de codar** (processo da frente).
**(0a) perfis.py fonte única:** `perfis.py` ganha `slugs_loja()`/`opcoes_loja()` (perfis de loja, exclui super_admin/admin_rede). `mod_cadastro` aposenta a tupla `PERFIS_ACESSO=("consultor","gerente","diretor")` — que tinha o **órfão "gerente"** (não é slug real → conta caía sem permissão); `func_sync_acesso` valida `perfis.slugs_loja()`, `META["perfis_acesso"]=perfis.opcoes_loja()`. `storage.perfis_carregar` **deriva** de perfis.py (chaves legadas consultor/gerente/diretoria → slugs reais), sem a `senha_gerente:"1234"` embutida; perfis_config.json deixa de ser fonte. Frontend: dropdown "Perfil de Usuário" do Funcionário lê `META.perfis_acesso` (slugs reais). _(Fora de escopo: `POST /api/gerente/verificar` ainda tem fallback "1234" no handler — passe dedicado.)_
**(0b) seed da Tabela de Funções:** `database.FUNCOES_PADRAO` (11 cargos = rótulos de cargo de perfis.py + Montador/Terceiro). `seed.criar_funcoes_seed(db, loja_id)` idempotente por (loja_id, nome), chamado em `seed()`; backfill único `funcoes_seed_v1` em `_run_migracoes` semeia lojas existentes (DB preservado ganha o catálogo sem reseed). _(Follow-up: semear na criação de loja nova.)_ Testes `test_perfis_fonte_unica.py` + `test_funcoes_seed.py`. Evidência: META lista 10 slugs sem "gerente"; perfis derivados 10/20/50; catálogo com Medidor/Montador/Projetista Executivo. **Fase 1 (Mapa de Atribuições + mod_escopo + 404 fora de escopo) é a próxima frente — plano detalhado a seguir.**

## Sessão 57 — Responsável por função no Cronograma + Função×Perfil em Usuários da Loja (Modulos_Orizon_v12)
Três frentes do v12. Backend+frontend+testes. Suíte 790→**793**.
**(1) Usuários da Loja — Função × Perfil (correção com achado surfaced):** a coluna "Perfil" bindava `Usuario.nivel`, que **é** o campo de acesso (perfis.py deriva tudo dele) — a premissa do spec ("Perfil guarda Função") estava factualmente invertida. Decisão do usuário (Opção 1): **não** mexer no nivel; adicionar **Função** nova = `funcao_nome` **derivada** do Funcionário vinculado (`funcionario_id → Funcionario.funcao_id → Funcao`), referenciada e não duplicada. Perfil = nivel, inalterado. Backend serializa `funcao_nome` (batch) em `/api/admin/usuarios`; tabela ganha coluna "Função". _(Pendência anotada: formalizar níveis de acesso partindo do que já existe em `perfis.py`.)_
**(2) Cronograma Padrão (Config) — função responsável por fase:** `cronograma_padrao[*].funcao_id` (→ Tabela de Funções) = o cargo que executa a fase, não uma pessoa. `mod_cronograma` normaliza. Config → Cronograma ganha dropdown **Função responsável** por fase (do `/api/funcoes`), ao lado do prazo.
**(3) Cronograma do Projeto — funcionário filtrado por função:** `CicloEtapa.funcao_responsavel_id` (herdada no D0) + `responsavel_funcionario_id` (nasce vazio); migração idempotente. `gerar_cronograma_projeto` herda a função no D0. `POST /ciclo/<cod>/responsavel {funcionario_id}` valida loja + **função exigida** (`funcao_id == funcao_responsavel_id`); vazio limpa. `GET /api/funcionarios?funcao_id` filtra o dropdown. `/ciclo` serializa função+funcionário. Frontend: cada card de etapa mostra "Responsável — função <X>: <select>" (só funcionários da função; aviso se nenhum). Testes `test_cronograma.py` (herança, restrição Montador≠Medidor, filtro, funcao_nome com nivel intocado). Verif.: CSS 310/310, scan JS delta zero.

## Sessão 56 — Botão primário com token próprio (Padrao_Design_v10)
Decisão de design (não bug): o **botão primário** rompe a paleta do resto da UI — deixa de usar `--accent` e passa a ter tokens próprios. `--accent` (petróleo/menta) segue valendo p/ nav ativo, links, foco, badges, sublinhado de aba. Frontend puro (`static/index.html`).
**Tokens novos (nos dois `:root`):** `--btn-primary-bg` (claro `#666666` cinza neutro · escuro `#193430` petróleo bem escuro, perto do fundo) · `--btn-primary-text` (claro `#FFFFFF` · escuro `#EAF5F2`) · `--btn-primary-border` (claro `none` · escuro `1.5px solid #59C0B2` — a linha viva é o destaque, não o fill) · `--btn-primary-shadow` (claro `0 2px 8px rgba(0,0,0,.12)` · escuro `0 6px 20px rgba(0,0,0,.55)`). Lógica: no claro, contraste tonal (cinza sobre superfície clara); no escuro, contraste por borda+sombra, fill de propósito perto do fundo.
**Aplicação:** `.btn-primary` e `.btn-amber` (o "Aprovar" da Negociação — nome preservado p/ o JS) passam a `background/color/border/box-shadow: var(--btn-primary-*)` (some o `color-mix` do v9). Os ~18 botões primários **inline** que o v9 pôs em `var(--accent)` (Confirmar/Liberar/Concluir/Autorizar/gerarContrato/sig-ok/data-act/… + Salvar de modais) trocaram `background:var(--accent);color:#fff|#0d160d;border:none` por `var(--btn-primary-*)` — 1 primário por tela, sempre via variável, nunca hex. `--accent` **mantido** onde não é botão: `.sb-logo-mark`, `.ind-conclusao.feito`, toggle `.sw`, avatares. Verificação: CSS 310/310, scan JS delta zero, nenhum `<button>` com `background:var(--accent)`.

## Sessão 55 — Cronograma do Ciclo: acesso corrigido + automação (Modulos_Orizon_v11)
Seção "Cronograma do Ciclo" do v11 (as demais seções do doc são contexto/futuro). Backend+frontend+testes. Suíte 782→**790**.
**(1) Bug de acesso (frontend):** `renderCiclo` suprimia o `onclick` do cabeçalho quando `bloqueada` → etapas futuras **inacessíveis**. Fix: cabeçalho **sempre clicável**. Futura = visível + corpo leitura ("🔒 Conclua a etapa anterior") + cadeado; Atual = visível+edição; Concluída = visível ("✓"). `bloqueada` mantém o sentido "futura" (os corpos já escondem ações) — só a inacessibilidade saiu.
**(2) Datas:** `CicloEtapa.data_prevista_conclusao` (coluna+migração); `data_conclusao` = `concluido_em` (reuso). `/ciclo` serializa as duas; cada card mostra 📅 prevista e ✓ concluída.
**(3) Config → Cronograma (nova aba):** `config_financeira_json.cronograma_padrao` = `[{codigo, prazo_dias}]` (dias a partir de D0), default em `mod_provisoes` (etapas 8–20). Edita prazo/etapa, salva pelo `PUT config-financeira`. GET config e `_cfg_financeira_loja` fazem **merge com o default** (lojas antigas ganham a chave sem perder config).
**(4) Gatilho — D0 = assinatura TOTAL** (decisão do usuário; ponto onde a etapa 7 conclui/projeto "fechado"): `mod_cronograma.gerar_cronograma_projeto(db, projeto, cfg, D0)` cria `data_prevista = D0 + prazo` por etapa. Idempotente (recomputa do D0, preserva conclusão), fail-soft (não bloqueia a assinatura).
**(5) Editar data prevista — reauth + auditoria:** `POST /ciclo/<cod>/data-prevista {login,senha,data_prevista}` → reautenticação **Gerente+** (`check_senha` + `perfis.pode "autorizar"` = diretor/gerente_vendas, padrão dos gates financeiros) → auditado em `LogAcaoGerencial(acao="editar_data_prevista", contexto={valor_antigo,valor_novo})`. Frontend: lápis só p/ Gerente+ (`_podeAutorizarFront`) → modal `modal-crono` (confirma a própria senha). Testes `test_cronograma.py` (motor idempotente + HTTP reauth/audita/barra consultor/barra senha errada). _(Fora de escopo, anotado: bloqueio pleno de EDIÇÃO em etapas concluídas exigiria reescrever ~15 renderizadores de card num fluxo sensível sem teste visual — o acesso, bug reportado, está corrigido.)_
