# SPEC - Infraestrutura e Deploy

Status: [IMPLEMENTADO]
Historias: US-17, US-18, US-19

---

## 1. Stack tecnica

| Camada | Tecnologia | Observacao |
|---|---|---|
| Backend | Python 3.12, http.server nativo | Sem framework |
| Banco | SQLite + SQLAlchemy 2.0 | Migracao futura para MySQL |
| Frontend | HTML/CSS/JS puro (SPA) | Sem framework |
| Autenticacao | Cookie de sessao (token_hex 32) | Server-side, sem JWT |
| Servidor | Hostinger VPS, Ubuntu 24.04 | IP: 167.88.33.121, porta 8765 |
| Repositorio | GitHub | github.com/mbnunes1972/omie_v3 |

---

## 2. Separacao de ambientes

| Ambiente | Servidor | Proposito |
|---|---|---|
| Desenvolvimento local | localhost:8765 | Desenvolvimento e testes |
| Desenvolvimento remoto | 167.88.33.121 | Testes em ambiente real |
| Producao ArchDecorPoints | VPS separado (KVM 2) | NUNCA usar para Omie_V3 |

---

## 3. Estrutura de arquivos

Omie_V3/
 main.py                     # Servidor HTTP + todas as rotas
 database.py                 # Modelos SQLAlchemy e conexao
 auth.py                     # Logica de autenticacao
 auth_routes.py              # Rotas de autenticacao
 mod_omie.py                 # Integracao Omie API
 mod_margens.py              # Calculo de margens
 promob_grupos.py            # Classificacao de grupos Promob
 storage.py                  # Disco, config, perfis, sessao
 mod_fin/
   __init__.py
   base.py
   aymore.py
   cartao.py
   total_flex.py
   venda_programada.py
 static/
   index.html                # Frontend SPA
 config/
   omie.json                 # Credenciais Omie (no .gitignore)
   total_flex.json           # Taxa de juros (no .gitignore)
 docs/                       # Documentacao completa

---

## 4. Workflow de Deploy

1. Desenvolver localmente
2. Testar localmente (localhost:8765)
3. git add . && git commit -m "feat: descricao"
4. git push origin main
5. ssh root@167.88.33.121
6. cd ~/omie_v3 && git pull
7. Reiniciar processo no screen

### Gerenciamento com screen

  screen -ls              # ver sessoes ativas
  screen -r omie_v3       # reconectar
  screen -S omie_v3       # criar nova sessao
  python3 main.py         # iniciar aplicacao
  Ctrl+A D                # desanexar sem matar

### Verificar se esta rodando

  curl http://167.88.33.121:8765/auth/me
  # Deve retornar 401 - indica servidor no ar

---

## 5. Versionamento Semantico

| Versao | Conteudo |
|---|---|
| v0.1.0 OK | Autenticacao, negociacao, Aymore, Cartao, integracao Omie, docs |
| v0.2.0 | Bug toggle, Clientes, Parceiros, Total Flex |
| v0.3.0 | Contratos, boleto, relatorio de comissoes |
| v0.4.0 | Kanban comercial (38 etapas) |
| v1.0.0 | Producao - primeira loja |
| v2.0.0 | Multi-loja / rede Dalmobile |

### Criar tag de versao

  git tag -a v0.2.0 -m "v0.2.0 - descricao"
  git push origin v0.2.0

---

## 6. .gitignore obrigatorio

  config/omie.json
  config/total_flex.json
  *.db
  __pycache__/
  *.pyc
  .env

---

## 7. Protocolo de sessao com IA

Ao iniciar sessao de desenvolvimento, colar no chat:
  - Conteudo do DEV_LOG.md
  - Conteudo do SPEC.md do modulo em trabalho
  - Objetivo da sessao

---

## 8. Historias relacionadas

- US-17 Deploy no VPS Hostinger
- US-18 Workflow Git para deploy
- US-19 Documentacao de sessao continua
