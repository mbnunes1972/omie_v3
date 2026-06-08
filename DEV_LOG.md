# DEV_LOG.md — Diário de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-06-08

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
- Documentos: DEV_RULES.md, DEV_LOG.md, REQUIREMENTS.md criados

### [PENDENTE]
- **ALTA** — Bug: toggle "Incluir custos adicionais?" não persiste corretamente entre aberturas do modal. Fluxo do bug: (1) marcar toggle → salvar → ok. (2) entrar/sair sem salvar → ok. (3) entrar novamente → toggle aparece desmarcado mesmo sem ação do usuário. Causa: `carregarMargensSalvas` recarrega do servidor após fechar o modal sem salvar, e o servidor retorna o JSON desatualizado. O `projetoAtivo.margens.incluir_custos` fica desatualizado. Arquivos relevantes: `static/index.html` funções `fecharModalParams`, `carregarMargensSalvas`, `abrirModalParams`; `main.py` rota `/projetos/<nome>/margens`.
- **MÉDIA** — Servidor DEV ainda sem domínio — acessível só por IP
- **BAIXA** — Atualizar servidor DEV com git pull após testes locais validados

### [DECIDIDO]
- Banco: SQLite + SQLAlchemy (migração futura para MySQL)
- Limites: Consultor 10%, Gerente 20%, Diretor 50%
- Servidor DEV: `167.88.33.121:8765`
- GitHub: `https://github.com/mbnunes1972/omie_v3`
- Parâmetros internos (arquiteto, fidelidade, viagem, brinde) nunca alteram valor do cliente
- Toggle "Incluir custos adicionais?" permite gross-up no valor bruto quando ativo
- Desconto Total sempre calculado sobre bruto original dos XMLs
- Foto e dados extras do perfil em localStorage (não no banco por ora)
- Autorização delegada registrada no banco mesmo quando negada
- Patches aplicados via scripts Python (patch_*.py) na raiz do projeto

### [CONTEXTO] Arquivos e variáveis chave
**Arquivos principais:**
- `main.py` — servidor HTTP, rotas (incluindo `/projetos/<nome>/margens` que salva `incluir_custos`)
- `database.py` — SQLAlchemy: `Usuario`, `Sessao`, `LogAutorizacao`
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

### Sessão 2026-06-07 (continuação — 2026-06-08)
**Objetivo:** Implementar sistema de autenticação, perfis e controle de descontos

**Realizado:**
- Sistema de autenticação completo (database.py, auth.py, auth_routes.py, seed.py)
- Login/logout com cookie de sessão
- Botão de perfil na sidebar (foto, dados editáveis)
- Modal de autorização delegada com log
- Limites de desconto por nível aplicados no modal e na sidebar
- Botão OK na sidebar para solicitar autorização
- Toggle "Incluir custos adicionais?" no modal de parâmetros
- Correção do valor bruto (parâmetros internos não afetam cliente)
- Gross-up quando "Incluir custos adicionais?" ativo
- Desconto Total calculado sobre bruto original
- "1x" em vez de "A Vista" no select de parcelas
- DEV_RULES.md, DEV_LOG.md, REQUIREMENTS.md criados
- Bug pendente: toggle incluir_custos não persiste entre aberturas do modal

**Arquivos modificados:**
- `main.py` — autenticação integrada, bind 0.0.0.0, salva incluir_custos
- `static/index.html` — todas as features acima
- `static/login.html` — novo
- `database.py`, `auth.py`, `auth_routes.py`, `seed.py` — novos
- `DEV_RULES.md`, `DEV_LOG.md`, `REQUIREMENTS.md` — novos
- `omie.db` — banco SQLite criado

### Sessão 2026-06-07 (primeira)
- Descoberto servidor DEV com EasyPanel + ArchDecorPoints
- Criado repositório GitHub `mbnunes1972/omie_v3`
- Push do código local e clone no servidor
- App subindo via screen com `python3 main.py`
