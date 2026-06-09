# DEV_LOG.md — Diário de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-06-09 (sessão 3)

### [ESTADO] O que está funcionando
- App rodando em `http://167.88.33.121:8765` (servidor DEV) e `http://127.0.0.1:8765` (local)
- Sistema de autenticação completo: login, logout, sessões via cookie
- Três níveis: Diretor (50%), Gerente (20%), Consultor (10%)
- Usuários: `pdm2026` (Pedro/Diretor), `lds2026` (Luiz/Gerente), `mds2026` (Marcia/Consultora)
- Botão de perfil na sidebar com foto, telefone, WhatsApp, email
- Autorização delegada: ao exceder limite, solicita credenciais de Gerente ou Diretor
- Limite autorizado = desconto específico aprovado (não o limite do perfil)
- Limite autorizado persiste durante a negociação, reseta ao trocar de projeto
- Desconto salvo no projeto vira limite autorizado ao reabrir
- Log de autorizações no banco (`log_autorizacoes`)
- Botão OK na sidebar para solicitar autorização de desconto
- Cancelar autorização restaura desconto anterior
- Modal de parâmetros: snapshot correto, restaura ao cancelar
- Toggle "Incluir custos adicionais?" no modal de parâmetros
- Valor bruto do cliente = valor original dos XMLs (parâmetros internos não afetam o cliente)
- Quando "Incluir custos adicionais?" ativo: gross-up aplicado ao valor bruto
- Desconto Total calculado sempre sobre valor bruto original dos XMLs
- Label "Desconto Total" (renomeado de "Desconto total s/ bruto")
- "A Vista" substituído por "1x" no select de parcelas
- Backend (`main.py`) salva `incluir_custos` no projeto.json
- **Módulo Clientes completo**: tabela `clientes` com endereço completo (CEP, logradouro, número, complemento, bairro, cidade, estado), busca por nome/CPF, busca automática de CEP via ViaCEP, máscara de telefone/WhatsApp, CRUD via modal
- **Duplo clique em cliente** abre modal "Cliente encontrado" com lista de projetos vinculados
- **Regras de unicidade**: nome duplicado mostra aviso "É homônimo?" com opção de ver cliente existente; CPF duplicado detectado no blur; modal "Cliente encontrado" mostra projetos e permite criar novo ou abrir existente
- **Projeto vinculado a cliente obrigatório**: `projeto.json` salva `cliente_id`; formulário exige seleção ou cadastro de cliente; botão "+ Cadastrar novo cliente" abre modal com nome pré-preenchido e auto-seleciona ao salvar
- **Módulo Parceiros completo**: tabela `parceiros` (nome, tipo, CPF/CNPJ, email, tel, wpp, comissão padrão, obs), busca por nome/CPF, CRUD via modal, verificação de homônimos, página própria no menu
- **Parceiro no projeto**: campo opcional no formulário de novo projeto (busca + chip + "+ Cadastrar novo parceiro"); `projeto.json` salva `parceiro_id`; ao abrir projeto, parceiro é carregado; ao abrir modal de parâmetros, comissão padrão do parceiro preenche automaticamente "Comissão arquiteto" se ainda não configurada
- **Lista de projetos ordenada**: projetos carregam automaticamente ao entrar na página (mais recente primeiro); botão ↑↓ inverte a ordem; campo de busca filtra/pesquisa; data de alteração exibida em cada card
- **"+ Novo ambiente" bloqueado**: botão só fica habilitado quando o usuário está na página de Negociação com um projeto aberto
- Documentação completa em `docs/`: BACKLOG.md (26 histórias), 7 SPEC.md de módulos, FLUXO_38_ETAPAS.md, DOCUMENTOS_D1_D45.md, VERSIONAMENTO.md

### [PENDENTE]
- **ALTA** — Bug: toggle "Incluir custos adicionais?" não persiste corretamente entre aberturas do modal. Causa: `carregarMargensSalvas` recarrega do servidor após fechar o modal sem salvar, e o servidor retorna o JSON desatualizado. O `projetoAtivo.margens.incluir_custos` fica desatualizado. Arquivos relevantes: `static/index.html` funções `fecharModalParams`, `carregarMargensSalvas`, `abrirModalParams`; `main.py` rota `/projetos/<nome>/margens`.
- **ALTA** — Implementar EP-07: Versionamento de Orçamentos (spec em `docs/modulos/negociacao/VERSIONAMENTO.md`)
- **MÉDIA** — Servidor DEV ainda sem domínio — acessível só por IP
- **BAIXA** — Criar script `deploy.sh` no servidor para automatizar git pull + sed + restart
- **BAIXA** — Projetos antigos (sem `cliente_id`) mostram cliente vazio no chip quando abertos

### [PRÓXIMA TAREFA] EP-07 — Versionamento de Orçamentos

Spec completo em: `docs/modulos/negociacao/VERSIONAMENTO.md`

**Implementar na sequência:**
1. Criar tabelas `pool_ambientes`, `orcamentos`, `orcamento_ambientes` em `database.py`
2. Criar projeto → Orçamento 1 automático
3. Upload XML com detecção de duplicata
4. Modal de duplicata (Sobrescrever / Nova versão)
5. Painel "Ambientes" — listar pool com status
6. Adicionar ambiente ao orçamento
7. Remover ambiente com confirmação
8. Recálculo automático de totais
9. Botão "Novo orçamento" + nome
10. Navegação entre orçamentos
11. Renomear orçamento inline
12. Sobrescrever → atualizar todos os orçamentos

**Regra:** implementar um passo por vez, aguardar confirmação antes de avançar.

### [DECIDIDO]
- Banco: SQLite + SQLAlchemy (migração futura para MySQL)
- Limites: Consultor 10%, Gerente 20%, Diretor 50%
- Servidor DEV: `167.88.33.121:8765` (main.py usa 0.0.0.0 no servidor via sed -i após git pull)
- GitHub: `https://github.com/mbnunes1972/omie_v3`
- Parâmetros internos (arquiteto, fidelidade, viagem, brinde) nunca alteram valor do cliente
- Toggle "Incluir custos adicionais?" permite gross-up no valor bruto quando ativo
- Desconto Total sempre calculado sobre bruto original dos XMLs
- Foto e dados extras do perfil em localStorage (não no banco por ora)
- Autorização delegada registrada no banco mesmo quando negada
- Clientes e Parceiros são cadastros separados
- Um parceiro por projeto (pode expandir no futuro)
- Busca de cliente e parceiro por nome ou CPF
- Pool de ambientes permanente por projeto (XMLs nunca deletados)
- Múltiplos orçamentos paralelos e editáveis por projeto
- Sobrescrever ambiente atualiza todos os orçamentos automaticamente
- Nova versão de ambiente cria registro separado no pool (sufixo _v1, _v2...)

### [CONTEXTO] Arquivos e variáveis chave
**Arquivos principais:**
- `main.py` — servidor HTTP, rotas
- `database.py` — SQLAlchemy: `Usuario`, `Sessao`, `LogAutorizacao`, `Cliente`, `Parceiro`
- `auth.py` — login, logout, validação, autorização delegada
- `auth_routes.py` — rotas HTTP de autenticação
- `seed.py` — cria usuários iniciais
- `static/index.html` — frontend SPA completo
- `static/login.html` — tela de login
- `PROJETOS/*/projeto.json` — dados persistidos de cada projeto

**Variáveis JS chave:**
- `_usuarioAtual` — usuário autenticado (via `/api/auth/me`)
- `_LIMITES_NIVEL` — `{ consultor: 10, gerente: 20, diretor: 50 }`
- `_limiteAutorizado` — desconto específico autorizado (null = usa limite do perfil)
- `_mpSnapshot` — snapshot dos parâmetros ao abrir modal (restaura ao cancelar)
- `_resolveAutorizacao` — Promise resolver do modal de autorização (modal params)
- `_resolveAutorizacaoSidebar` — Promise resolver do modal de autorização (sidebar)
- `cfgGetDescontoMax()` — retorna `_limiteAutorizado` se existir, senão limite do perfil
- `calcularValorBrutoCliente(mg)` — calcula bruto com gross-up se `mg.incluir_custos`
- `mpRecalcularEstruturalModal()` — recalcula `_negBaseValues.estrutural` com toggles atuais
- `lerMargensNegociacao()` — lê margens do `projetoAtivo.margens` + toggle `incluir_custos` do modal se aberto

**Rotas de autenticação:**
- `GET /login`, `GET /logout`, `GET /api/auth/me`
- `POST /api/auth/login`, `POST /api/auth/logout`
- `POST /api/auth/verificar_desconto`, `POST /api/auth/autorizar_desconto`

---

## HISTÓRICO

### Sessão 2026-06-09 (sessão 3 — documentação e planejamento)
**Objetivo:** Reorganizar documentação, criar histórias de usuário e especificar EP-07

**Realizado:**
- Criado `docs/historias/BACKLOG.md` com 26 histórias (EP-01 a EP-07, US-01 a US-26)
- Criado SPEC.md para todos os 7 módulos: autenticacao, negociacao, financeiro, integracao_omie, clientes, parceiros, infraestrutura
- Criado `docs/processos/FLUXO_38_ETAPAS.md` — 38 etapas em 6 fases do processo comercial
- Criado `docs/processos/DOCUMENTOS_D1_D45.md` — mapa completo dos documentos de governança
- Criado `docs/infraestrutura/SPEC.md` — stack, deploy, versionamento semântico
- Criado `docs/modulos/negociacao/VERSIONAMENTO.md` — spec completo do EP-07
- Tag `v0.1.0` já existente; próxima versão será `v0.2.0` ao concluir EP-07
- Modelo de dados EP-07 definido: 3 novas tabelas (`pool_ambientes`, `orcamentos`, `orcamento_ambientes`)
- Sequência de 12 passos de implementação definida e documentada

**Arquivos modificados:**
- `docs/historias/BACKLOG.md` — criado/atualizado
- `docs/modulos/*/SPEC.md` — 7 arquivos criados
- `docs/processos/FLUXO_38_ETAPAS.md` — criado
- `docs/processos/DOCUMENTOS_D1_D45.md` — criado
- `docs/infraestrutura/SPEC.md` — criado
- `docs/modulos/negociacao/VERSIONAMENTO.md` — criado
- `DEV_LOG.md` — este arquivo

### Sessão 2026-06-09 (sessão 2)
**Objetivo:** Corrigir e completar módulo de Clientes; vincular projeto a cliente obrigatório

**Realizado:**
- Diagnóstico: 34 processos Python acumulados na porta 8765 causavam 404 nas rotas de clientes — resolvido com kill de todos e reinício de instância única
- Migração do banco: tabela `clientes` sem colunas CEP/logradouro/numero/complemento/bairro — `_migrar_colunas()` executada
- Correção frontend: `numero` e `complemento` faltavam no payload de save
- Máscara de telefone aplicada ao abrir modal de edição
- `db.query(Cliente).get()` substituído por `db.get(Cliente, ...)` (SQLAlchemy 2.0)
- Formulário de novo projeto reformulado: chip de cliente, botão "+ Cadastrar novo cliente"
- `criarProjeto()` agora exige `cliente_id`
- Backend `/projetos/novo` busca dados do cliente no banco, rejeita sem `cliente_id`
- DEV_LOG atualizado

**Arquivos modificados:**
- `main.py`, `mod_omie.py`, `static/index.html`, `database.py`, `DEV_LOG.md`

### Sessão 2026-06-07 (continuação — 2026-06-08)
**Objetivo:** Implementar sistema de autenticação, perfis e controle de descontos

**Realizado:**
- Sistema de autenticação completo (database.py, auth.py, auth_routes.py, seed.py)
- Login/logout com cookie de sessão
- Botão de perfil na sidebar (foto, dados editáveis)
- Modal de autorização delegada com log
- Limites de desconto por nível aplicados no modal e na sidebar
- Toggle "Incluir custos adicionais?" no modal de parâmetros
- Correção do valor bruto (parâmetros internos não afetam cliente)
- Gross-up quando "Incluir custos adicionais?" ativo
- "1x" em vez de "A Vista" no select de parcelas
- DEV_RULES.md, DEV_LOG.md, REQUIREMENTS.md criados
- Bug pendente: toggle incluir_custos não persiste entre aberturas do modal

**Arquivos modificados:**
- `main.py`, `static/index.html`, `static/login.html`, `database.py`, `auth.py`, `auth_routes.py`, `seed.py`
- `DEV_RULES.md`, `DEV_LOG.md`, `REQUIREMENTS.md` — novos

### Sessão 2026-06-07 (primeira)
- Descoberto servidor DEV com EasyPanel + ArchDecorPoints
- Criado repositório GitHub `mbnunes1972/omie_v3`
- Push do código local e clone no servidor
- App subindo via screen com `python3 main.py`
