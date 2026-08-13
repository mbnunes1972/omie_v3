# Arquitetura do Orizon + Fluxo de Ambientes

> Documento único pedido na Fase 1, item 1 do Plano de Transição. Rascunho gerado a partir de
> `CLAUDE.md`/`DEV_LOG.md`/`DEV_RULES.md` — Marcelo e Juliana revisam e ajustam juntos antes de
> considerar "pronto". Data-base: 2026-08-05 (Sessão 161 do DEV_LOG).

## 1. O que é o sistema

**Orizon Manager** (marca comercial da loja: **Dalmóbile**) é o sistema de gestão de vendas de
móveis planejados: do orçamento até a entrega, passando por negociação, contrato, produção,
NF-e e financeiro. Multi-loja/multi-rede (tenancy) — hoje em produção com pelo menos uma rede
real operando.

## 2. Stack técnica

- **Backend:** Python puro, servidor HTTP com `http.server` da stdlib — **sem framework**
  (não é Flask/Django/FastAPI). Todas as rotas ficam em `main.py` (arquivo grande, `do_GET`/
  `do_POST`/`do_PATCH` despacham por `path`).
- **ORM:** SQLAlchemy. **Banco: PostgreSQL, e só ele** — o SQLite foi removido por completo do
  código em 2026-07-23 (não existe mais fallback nem flag pra religar).
- **Frontend:** **um arquivo só**, `static/index.html` — HTML + CSS + JavaScript inline, sem
  build step, sem framework (não é React/Vue). É lido do disco a cada request, então mudança de
  frontend não pede restart do servidor (só `Ctrl+F5` no navegador). Mudança em Python pede
  restart.
- **Sem suíte de teste de frontend** — verificação é manual no navegador; para sintaxe do JS,
  extrai-se o `<script>` e roda `node --check`.
- **Backend testado com pytest** (`python3 -m pytest -q`) — suíte roda **sempre contra
  Postgres** (banco de teste derivado do `.env`, nunca contra dev/produção — o setup dá `DROP
  SCHEMA CASCADE`). Em 2026-08-05 a suíte tinha **1736 testes**, ~2m45–4m de execução.

## 3. Como o código está organizado

- A maior parte dos módulos ainda são arquivos `.py` soltos na **raiz** do repo, classificados
  por domínio dentro de `modulos.py` — um teste (`test_arquitetura_modulos`) garante que
  nenhum módulo fica órfão dessa classificação.
- Alguns domínios já viraram **pacote** (pasta com `__init__.py`): `fiscal/`, `integracoes/`,
  `auth/`, `chat/` (mais o antigo `mod_fin/`). Import de fora do pacote é absoluto
  (`from fiscal import mod_nfe`); dentro do pacote, relativo (`from . import mapa_fiscal`).
  Falta empacotar o domínio `comercial` (a maioria dos módulos ainda soltos na raiz).
- **Reestruturação maior planejada, NÃO iniciada ("Motor 5.0"):** `app/core/` +
  `app/modules/*` (12 domínios) + `app/integrations/` + `app/shared/` — decisão já tomada
  (2026-07-16) mas a execução foi **deliberadamente adiada** até o empacotamento incremental
  acima estabilizar em produção. Enquanto isso, só documentação/inventário sobre esse plano,
  nada de código. Spec:
  `docs/superpowers/specs/_geral/2026-07-16-motor-5-reestruturacao-app-design.md`.
- **Documentação viva do projeto** (nessa ordem de autoridade):
  1. `CLAUDE.md` (raiz) — carregado automaticamente pelo Claude Code a cada sessão; resumo
     denso do estado atual, áreas sensíveis e armadilhas conhecidas.
  2. `DEV_LOG.md` (raiz) — diário de desenvolvimento completo, sessão a sessão, com o
     "porquê" de cada decisão. É a fonte narrativa — se um documento aqui divergir do
     DEV_LOG, o DEV_LOG vence.
  3. `DEV_RULES.md` (raiz) — regras de processo/deploy (runbooks dos 3 ambientes).
  4. `REQUIREMENTS.md` (raiz) — requisitos de referência.
  5. `docs/superpowers/specs/` — spec de design por frente de trabalho (uma por decisão de
     produto/arquitetura relevante).
  6. **NÃO usar** `docs/arquitetura/`, `docs/processos/`, `docs/modulos/*/SPEC.md`,
     `docs/historias/BACKLOG.md` — parados desde início de julho/2026, bem antes da migração
     pra Postgres e de praticamente todo o Orizon Chat. Ver nota no README desta pasta.

## 4. Áreas sensíveis (resumo — detalhe completo em `CLAUDE.md`)

Áreas do sistema onde já se retrabalhou por falta de contexto — **ler `CLAUDE.md` inteiro
antes de mexer em qualquer uma destas**:

- **Contrato/Proposta:** gerado por HTML+Markdown → PDF via WeasyPrint (não Word/LibreOffice —
  esses foram aposentados na geração; LibreOffice ainda é usado só pra IMPORTAR modelo de
  contrato do cliente).
- **Modelos de documento por loja:** versionados e imutáveis uma vez usados num contrato.
- **Negociação/motor de cálculo:** lógica pura em `mod_negociacao.py`/`mod_provisoes.py` — a
  tela só lê o resultado do motor, nunca recalcula sozinha.
- **Ciclo do projeto:** etapas numeradas em `mod_ciclo.py`, front em `ETAPAS_CICLO`.
- **Escopo por projetista:** Consultor só vê os projetos que criou; gerente+ vê todos.
- **Fechamento contábil (FASE D2):** provisão diferida no contrato + matching pleno na NF-e —
  é a lógica financeira mais intrincada do sistema.
- **Banco de dados:** só Postgres, local (WSL) e nos 3 ambientes remotos (seção 5).
- **Orizon Chat:** o módulo mais recente e mais mexido (triagem automática via WhatsApp,
  segmentação por Função, Atendimentos × Chat Interno) — ver `chat/` (pacote) e as sessões
  mais recentes do DEV_LOG (130+) pro histórico completo de decisões.

## 5. Os 3 ambientes hoje

| Ambiente | Onde | Porta/URL | Banco | Como sobe | Código que roda |
|---|---|---|---|---|---|
| **Integração (Instância A)** | VPS `167.88.33.121` | `:8765` | Postgres `orizon` (local à VPS) | systemd `orizon-a` (`Restart=always`) | `main` (sempre a ponta) |
| **Homolog (Instância B)** | mesma VPS `167.88.33.121`, clone separado | `:8766` | Postgres `orizon_homolog` (mesma VPS) | systemd `orizon-b` | uma **tag fixa** (`vAAAA.MM.DDx-homolog`), não o `main` |
| **Produção** | VPS dedicada `179.197.77.9` | `https://www.orizonone.com.br` (nginx + HTTPS na frente; :8765 só em localhost) | Postgres `orizon` (local à VPS, com backup diário automático) | systemd `orizon.service` | uma **tag fixa** (`vAAAA.MM.DDx-prod`) |

Cada ambiente tem sua própria `DATABASE_URL` (arquivo `.env` fora do git, um por instância) —
nunca compartilham banco. Script único de deploy A+B: `scripts/deploy_ab.sh <tag-de-homolog>`
(roda **no VPS de dev**, via SSH). Produção é deploy manual, sempre com backup antes
(`bash /root/backup_orizon.sh`).

## 6. O fluxo antigo (até 2026-08-12 — referência histórica, 1 dev + IA)

Até a Sessão 197: commit direto na `main` (sem PR, sem revisão de terceiro) → push → deploy
manual na Instância A → teste visual/técnico (localhost ≈ Instância A, mesmo rigor) → tag nova →
`deploy_ab.sh` promove a Instância B → teste aberto (usuário comum) → tag nova → deploy manual
em Produção com backup antes. Funcionou por ser 1 dev só (Marcelo, via Claude Code); deixou de
ser suficiente assim que Juliana passou a desenvolver também.

## 7. O fluxo atual (ATIVO desde 2026-08-13, Sessão 197)

O que muda é **antes** da Instância A: cada dev deixa de commitar direto na `main` compartilhada
e passa a trabalhar isolado. Confirmado nessa sessão: **VPS A/Instância A é definitivamente o
ambiente de teste técnico** (equiparado ao localhost, mesmo rigor) — não uma parada informal;
**VPS B/Instância B fica reservada só para homologação com equipe/usuário real**, nunca para
depuração de dev; **o banco de Produção segue limpo por ora** (sem dado real de cliente ainda).

1. **Cada dev trabalha na própria máquina** (clone próprio do repo, não mais um WSL
   compartilhado) — branch de feature a partir da `main`.
2. **Abre Pull Request** no GitHub (`mbnunes1972/orizon-manager`) quando terminar — suíte verde
   localmente é pré-requisito pra abrir o PR, não pra depois.
3. **Juliana revisa e aprova** — critério mínimo: suíte passa, `node --check` limpo se mexeu em
   `static/index.html`, e a mudança bate com a spec/decisão registrada (se houver uma).
4. **Merge na `main` = vira a ponta da Instância A automaticamente** no próximo deploy (o
   runbook de deploy da A já faz `git reset --hard origin/main` — não muda).
5. **Gate de aprovação visual de Marcelo** antes de qualquer promoção **entre ambientes**
   (A → B e B → Produção) — isso já é a prática hoje e continua sendo o freio antes de
   qualquer coisa chegar em usuário real ou em produção.

O que **não muda**: os 3 ambientes em si, a disciplina de testar em cada tier antes de
promover (ver `[[pipeline-testes-promocao]]`, memória do Claude Code — vale documentar
formalmente aqui se a equipe for usar Claude Code também), o runbook de deploy
(`DEV_RULES.md`), a suíte de testes como critério de "pronto" técnico.

## 8. Mapa de onde procurar cada coisa

| Preciso saber... | Vou em... |
|---|---|
| Estado atual, o que foi feito quando, porquê de uma decisão | `DEV_LOG.md` (procurar a sessão pelo assunto) |
| Regra de processo, runbook de deploy completo | `DEV_RULES.md` |
| Design de uma frente específica (ex.: Orizon Chat, Fase D2) | `docs/superpowers/specs/<área>/` |
| Requisito de negócio de referência | `REQUIREMENTS.md` |
| Convenções de código/áreas sensíveis (resumo rápido) | `CLAUDE.md` |
| Estrutura de módulos (o que é núcleo, o que é comercial, etc.) | `modulos.py` |
