# DEV_RULES.md — Regras de Sessão de Desenvolvimento
## Orizon Manager | Dalmóbile

---

## OBJETIVO
Garantir continuidade total entre sessões de desenvolvimento, sem perda de contexto, independente do tempo entre sessões ou da ferramenta usada (Claude Chat ou Claude Code).

---

## DOCUMENTOS DO PROJETO

| Arquivo | Propósito |
|---|---|
| `CLAUDE.md` | Resumo carregado automaticamente pelo Claude Code (aponta para estes docs) |
| `DEV_RULES.md` | Este arquivo — regras do processo |
| `DEV_LOG.md` | Diário de desenvolvimento — estado atual e histórico |
| `REQUIREMENTS.md` | Requisitos do sistema — referência permanente |
| `docs/superpowers/specs/` | Specs de design por frente |
| MCP `orizon` (grafo Neo4j) | Camada de **consulta** estrutural (cobertura, impacto, rastreabilidade). **Não** substitui o DEV_LOG — ver seção própria abaixo |

---

## AO ABRIR UMA NOVA SESSÃO

### No Claude Chat
Cole no início da conversa:
> "Leia os arquivos DEV_LOG.md e REQUIREMENTS.md do projeto Orizon Manager e me ajude a continuar de onde paramos."

Cole o conteúdo da seção `## RESUMO ATUAL` do `DEV_LOG.md`.

### No Claude Code
Digite no terminal dentro da pasta do projeto:
```
claude
```
Depois diga:
> "Leia DEV_LOG.md e REQUIREMENTS.md e continue de onde paramos."

O Claude Code lê os arquivos diretamente — não precisa colar o conteúdo.

---

## AO ENCERRAR UMA SESSÃO

### Checklist obrigatório antes de fechar

- [ ] Todos os arquivos modificados foram salvos
- [ ] O servidor local foi testado (`python3 main.py`)
- [ ] A suíte passou (`python3 -m pytest -q`) e os testes manuais foram feitos (login, funcionalidade alterada)
- [ ] `git add . && git commit -m "descrição"` foi executado
- [ ] `git push` foi executado
- [ ] **Re-ingestão do grafo MCP** (`ingerir` com `fonte: "all"`, ou `POST http://localhost:8767/ingest/all`) — para o grafo refletir o código mergeado
- [ ] Se houver mudanças no servidor: `git pull` + restart do app

### Pedir ao Claude para atualizar o log
> "Atualize o DEV_LOG.md com o resumo do que fizemos hoje. Mantenha o RESUMO ATUAL no topo e adicione ao HISTÓRICO."

### Verificar que o DEV_LOG contém
- [ ] [ESTADO] — o que está funcionando agora
- [ ] [PENDENTE] — bugs e tarefas abertas com prioridade
- [ ] [DECIDIDO] — decisões tomadas hoje que não devem ser revertidas
- [ ] [ARQUIVOS] — arquivos modificados na sessão

---

## REGRAS GERAIS

### Git
- Fazer commit ao final de cada sessão, **sempre**
- Mensagens de commit em português, descritivas: `"feat: modal de autorização delegada"`, `"fix: limite de desconto no modal de parâmetros"`
- Nunca editar arquivos diretamente no servidor — sempre via git pull
- Branch padrão: `main`

### Servidor de DEV
- IP: `167.88.33.121` | Portas: `8765` (Instância A) / `8766` (Instância B)
- Acesso: `ssh root@167.88.33.121` (chave ed25519, sem senha)
- **DESDE 2026-07-20 as duas instâncias rodam como serviços SYSTEMD** (`orizon-a`/`orizon-b`,
  `enabled` no boot, `Restart=always`, log em `app.log` de cada diretório) — **NÃO screen**. O
  screen foi aposentado nessa migração; se algo (um comando manual, um runbook velho) subir a
  app via `screen -dm .../python3 main.py`, o processo manual e o systemd BRIGAM pela mesma porta
  — o systemd fica em crash-loop (`OSError: Address already in use`) enquanto o processo manual
  segue servindo por fora do supervisor (sem `Restart=always`, sem sobreviver a reboot).
  **Achado ao vivo (2026-08-10, Sessão 189):** essa colisão aconteceu de verdade — um deploy
  manual seguindo um runbook desatualizado (a versão anterior deste arquivo) deixou `orizon-a` e
  `orizon-b` crash-loopando por **horas** (contador de restart > 1700) sem que ninguém notasse,
  porque a porta continuava respondendo (via o processo screen por fora). Fix: matar o processo
  órfão pelo PID (`ss -ltnp | grep 876[56]` acha o PID real) e deixar o systemd reassumir.
- **Bind:** `main.py` lê `ORIZON_HOST` das envs (`/root/orizon-A.env`/`/root/orizon-B.env`,
  fora do git) — `0.0.0.0` nas duas (bind externo). **Firewall:** portas 8765/8766 TCP liberadas
  (`ufw allow`).

#### Runbook de deploy — USE O SCRIPT, não comandos manuais
```bash
ssh root@167.88.33.121
bash /root/orizon-manager/scripts/deploy_ab.sh <TAG_DE_HOMOLOG>   # ex.: v2026.08.10a-homolog
```
O script (`scripts/deploy_ab.sh`, versionado) já faz tudo certo: `systemctl stop/start` (nunca
`pkill`/`screen`), A atualiza pelo `origin/main` (`git reset --hard`), B faz checkout da TAG
passada como argumento, espera a porta responder (poll, não `sleep` cego) e imprime o resumo
(commit da A + tag da B). **Não existe mais runbook manual pra isso** — se precisar debugar um
passo isolado, use `systemctl status/restart orizon-a` (ou `-b`) e `journalctl -u orizon-a -n 50`,
nunca `pkill -f main.py` (mata a própria sessão SSH se rodado como comando único — o argv contém
"main.py" — E colide com o systemd se rodado à parte dele).

#### Instância B — PRÉ-HOMOLOGAÇÃO (`:8766`), clone e banco separados
Duas instâncias isoladas no `167.88.33.121` (ver `docs/superpowers/specs/_geral/2026-07-16-plano-de-testes.md`):
a **A** (INTEGRAÇÃO, `:8765`, `/root/orizon-manager`, segue o `main`) e a **B** (PRÉ-HOMOLOGAÇÃO,
`:8766`, **clone separado** `/root/orizon-homolog`, roda uma **tag fixada**, nunca o `main`).
Banco: Postgres 16 no mesmo host, user `orizon`, dbs `orizon` (A) e `orizon_homolog` (B) — cada
instância aponta pra um via `DATABASE_URL` no seu `.env` (fora do git). Unit files em
`/etc/systemd/system/orizon-a.service` / `orizon-b.service` (`WorkingDirectory` de cada um aponta
pro diretório certo — não precisa mexer neles pra um deploy normal, só pra provisionar do zero).

#### Runbook de migração de nome — UMA vez (`omie_v3` → `orizon-manager`)
> Rodar **uma única vez** ao migrar o nome. O servidor ainda tem os nomes antigos; depois disto,
> use o runbook de deploy acima normalmente.
```bash
# 1) GitHub: renomear o repositório em Settings → Repository name → "orizon-manager"
#    (o GitHub mantém redirecionamento do nome antigo, mas atualize o remote abaixo)
# 2) No VPS:
ssh root@167.88.33.121
pkill -f main.py; sleep 1
for s in $(screen -ls | grep -oE '[0-9]+\.omie_v3'); do screen -S "$s" -X quit; done
screen -wipe
mv /root/omie_v3 /root/orizon-manager          # renomeia o diretório (preserva tudo)
cd /root/orizon-manager
[ -f omie.db ] && mv omie.db orizon.db          # preserva o banco com o novo nome
git remote set-url origin https://github.com/mbnunes1972/orizon-manager.git
git fetch origin && git reset --hard origin/main
screen -S orizon-manager -dm bash -c 'cd /root/orizon-manager && ORIZON_HOST=0.0.0.0 python3 main.py > app.log 2>&1'
sleep 3; ss -ltnp | grep 8765; tail -8 app.log
```

### Servidor de produção (www.orizonone.com.br) — provisionado
- IP: `179.197.77.9` (Hostinger) | VPS **dedicada** (nada mais rodando nela) | Ubuntu 24.04
- **Domínio OFICIAL: `www.orizonone.com.br`** (troca decidida em 2026-07-23; o antigo
  `orizonsolution.com.br` fica como redirect 301 → novo). Runbook da troca no fim desta seção.
- Diferente do servidor de DEV **de propósito** — nasce já no padrão profissional, não é o mesmo setup
  replicado: **PostgreSQL** (não SQLite, ver `docs/superpowers/specs/_geral/2026-07-15-migracao-postgresql.md`),
  **systemd** (não `screen` — sobrevive a reboot e reinicia sozinho se cair), **nginx + HTTPS** na frente
  (a porta 8765 do Python NÃO fica exposta direto à internet), `ufw` + `fail2ban`, backup automático.
- Acesso: `ssh root@179.197.77.9`, **só por chave** (login por senha será desabilitado no passo 1 — a
  chave já foi confirmada funcionando antes de desabilitar).
- **Pré-requisito ainda pendente:** o código com suporte a `DATABASE_URL` (conexão Postgres) está só
  local, não commitado (branch `feat/migracao-postgresql-v2`, worktree `wt-postgres-migration`) — precisa
  estar commitado/mergeado antes do Passo 2 (deploy do app).

#### Passo 0 — DNS (fora do servidor, no painel do registrador do domínio)
Criar registros A: `orizonsolution.com.br` → `179.197.77.9` e `www.orizonsolution.com.br` →
`179.197.77.9`. Propagação pode levar de minutos a algumas horas — dá pra rodar os Passos 1 e 2
enquanto espera; o Passo 3 (certificado HTTPS) só funciona depois do DNS propagar.

#### Passo 1 — Provisionamento base (rodar uma vez, via SSH)
```bash
apt update && apt upgrade -y && dpkg --configure -a   # garante que não sobrou nada pendente
apt install -y postgresql postgresql-contrib nginx certbot python3-certbot-nginx ufw fail2ban \
  python3-docx python3-openpyxl python3-requests python3-sqlalchemy python3-psycopg2 \
  weasyprint python3-markdown git

# Postgres: usuário + banco dedicados (troque a senha)
sudo -u postgres psql -c "CREATE USER orizon WITH PASSWORD 'TROQUE_ESTA_SENHA';"
sudo -u postgres psql -c "CREATE DATABASE orizon OWNER orizon;"

# Firewall: só SSH + HTTP/HTTPS (a 8765 fica só em localhost, atrás do nginx)
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# Hardening SSH — só desabilite senha DEPOIS de confirmar que a chave funciona numa
# segunda janela SSH aberta em paralelo (mesma lição do incidente de hoje: nunca feche
# a única sessão viva antes de confirmar a próxima)
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl restart ssh
```

#### Passo 2 — Deploy do app (depois que o código do DATABASE_URL estiver commitado)
```bash
cd /root
git clone https://github.com/mbnunes1972/orizon-manager.git
cd orizon-manager
git checkout feat/migracao-postgresql-v2   # trocar por 'main' assim que mergeado
pip install alembic --break-system-packages

cat > /etc/systemd/system/orizon.service <<'EOF'
[Unit]
Description=Orizon Manager
After=network.target postgresql.service

[Service]
Type=simple
WorkingDirectory=/root/orizon-manager
Environment=ORIZON_HOST=127.0.0.1
Environment=DATABASE_URL=postgresql+psycopg2://orizon:TROQUE_ESTA_SENHA@localhost/orizon
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Primeiro start cria o schema limpo no Postgres (create_all, sem migração de dados legados)
# e semeia os usuários iniciais — TROCAR AS SENHAS DE EXEMPLO ANTES DE USO REAL.
systemctl daemon-reload
systemctl enable --now orizon
sleep 3; systemctl status orizon --no-pager; curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://127.0.0.1:8765
```

#### Passo 3 — nginx + HTTPS (só depois do DNS propagado — Passo 0)
```bash
cat > /etc/nginx/sites-available/orizon <<'EOF'
server {
    listen 80;
    server_name orizonsolution.com.br www.orizonsolution.com.br;
    client_max_body_size 64M;   # > teto do app (50 MB): o 413 amigavel vem sempre do app, nunca do proxy
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/orizon /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d orizonsolution.com.br -d www.orizonsolution.com.br   # HTTPS + redirect automático
# ATENÇÃO: o certbot cria um 2º bloco server { } (443) — conferir que o client_max_body_size 64M
# está presente em CADA bloco server (o default do nginx é 1M e derruba upload de XML > 1 MB
# com "Failed to fetch" no browser, sem status).
```

#### Troca de domínio → www.orizonone.com.br (decidida 2026-07-23; **EXECUTADA 2026-07-24** — mantido como referência)
**Pré-requisito (painel Hostinger, fora do servidor):** o domínio `orizonone.com.br` está no
PARKING da Hostinger (aponta p/ `2.57.91.91`, página "Parked Domain"). Criar registros **A**:
`orizonone.com.br` → `179.197.77.9` e `www.orizonone.com.br` → `179.197.77.9` (apagar/substituir
o apontamento de parking). O certbot abaixo SÓ funciona depois do DNS propagar
(`getent hosts orizonone.com.br` já devolvendo `179.197.77.9`).

```bash
# na VPS de produção (ssh root@179.197.77.9), DEPOIS do DNS propagado:
# 1) site novo (o antigo fica intacto por enquanto)
cat > /etc/nginx/sites-available/orizonone <<'EOF'
server {
    listen 80;
    server_name orizonone.com.br www.orizonone.com.br;
    client_max_body_size 64M;   # > teto do app (50 MB) — pendência da frente de uploads (S104)
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/orizonone /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 2) HTTPS do domínio novo (cria o bloco 443 no arquivo orizonone)
certbot --nginx -d orizonone.com.br -d www.orizonone.com.br
# conferir: client_max_body_size 64M presente TAMBÉM no bloco 443 que o certbot criou
grep -n 'client_max_body_size' /etc/nginx/sites-available/orizonone

# 3) domínio antigo vira redirect permanente: em /etc/nginx/sites-available/orizon,
#    dentro de CADA server block (80 e 443), substituir o "location / { ... }" inteiro por:
#        return 301 https://www.orizonone.com.br$request_uri;
#    (os certificados do domínio antigo continuam sendo renovados — o redirect precisa deles no 443)
nginx -t && systemctl reload nginx

# 4) prova real
curl -s -o /dev/null -w '%{http_code}\n' https://www.orizonone.com.br/login          # 200
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://www.orizonsolution.com.br/  # 301 → orizonone
```

#### Passo 4 — Backup automático (pg_dump diário)
```bash
mkdir -p /root/backups
cat > /root/backup_orizon.sh <<'EOF'
#!/bin/bash
DATA=$(date +%Y%m%d_%H%M%S)
sudo -u postgres pg_dump orizon | gzip > /root/backups/orizon_$DATA.sql.gz
find /root/backups -name "orizon_*.sql.gz" -mtime +14 -delete
EOF
chmod +x /root/backup_orizon.sh
(crontab -l 2>/dev/null; echo "0 3 * * * /root/backup_orizon.sh") | crontab -
```
⚠️ Isso é backup **local** (mesmo disco da VPS) — protege contra erro de aplicação/banco, mas não
contra falha da própria VPS. Ainda falta sincronizar pra fora (ex.: S3/Backblaze) — pendente, não
bloqueia o go-live.

### Banco de dados
- **Servidor de DEV:** SQLite: `orizon.db` na raiz — **NÃO versionado** (está no `.gitignore`); cada
  ambiente tem o seu. Não comitar `orizon.db`.
- **Servidor de produção:** PostgreSQL (ver seção acima) — nasce limpo, sem dados do DEV.
- Para recriar usuários (ou um banco novo): `python3 seed.py` (cria schema via `init_db` + usuários)
- Migrações: SQLAlchemy + `_migrar_colunas`/`schema_migrations` (SQLite, legado) — Postgres usa Alembic
  a partir da migração (ver ADR).

### Dependências
- Listadas em `requirements.txt`. Local: `python3 -m pip install -r requirements.txt` (o contrato usa
  `weasyprint`; a proposta ainda usa docx/LibreOffice).
- Servidor (Ubuntu 24.04, PEP 668): instalar via `apt` (ver runbook) — `pip install`
  system-wide é bloqueado (`externally-managed-environment`).

### Testes após cada mudança
1. **Automatizados (backend):** `python3 -m pytest -q` — deve ficar tudo verde ANTES de commitar/mergear.
2. **Manuais (frontend, `static/index.html` — sem teste JS):** login com cada nível (Consultor, Gerente,
   Diretor); limite de desconto respeitado; autorização delegada funcional; logout redireciona para
   `/login`. Para sintaxe do JS: extrair o `<script>` e rodar `node --check`.

---

## MCP `orizon` — grafo de conhecimento (camada de consulta)

O projeto `../mcp-orizon` sobe um **grafo Neo4j** (via docker-compose) que ingere código, requisitos,
banco e decisões do Orizon Manager. O Claude Code fala com ele via servidor MCP (config em `.mcp.json`,
mounts para `E:/2026/desenvolvimento/...`). Ferramentas: `cobertura`, `rastrear_requisito`,
`impacto_de`, `decisoes_de`, `buscar`, `entidades_do_arquivo`, `etapa`, `ingerir`, `criar_relacao`.

**Papel e limites — leia antes de confiar nele:**
- É uma **camada de consulta/análise** ("o que implementa o requisito X? o que quebra se eu mexer no
  arquivo Y? quais requisitos não têm código?"). **Não** é controle de versão nem diário.
- É **derivado do código e local** (container Neo4j, fora do git). **Fica obsoleto** se o código muda e
  não re-ingere; **some** com `docker compose down -v` — aí é só re-ingerir.
- **Não substitui o DEV_LOG.** O DEV_LOG continua sendo a fonte narrativa versionada (estado, backlog,
  decisões + porquê, histórico) e a continuidade entre sessões. O grafo complementa.

**Controle de versão:** segue **100% no git** — o MCP não muda nada nisso.

**Ritual:** após mergear mudança relevante, **re-ingerir** (`ingerir` `fonte: "all"` ou
`POST http://localhost:8767/ingest/all`). Antes de fechar frente, vale rodar
`cobertura`/`rastrear_requisito` para pegar requisito sem implementação.

## TAGS DO DEV_LOG

| Tag | Uso |
|---|---|
| `[ESTADO]` | O que está funcionando agora |
| `[PENDENTE]` | Bug ou tarefa aberta — incluir prioridade (ALTA/MÉDIA/BAIXA) |
| `[DECIDIDO]` | Decisão de arquitetura — não reverter sem discussão |
| `[CONTEXTO]` | Variáveis, funções ou arquivos chave que o Claude precisa saber |
| `[BLOQUEIO]` | Impedimento que precisa ser resolvido antes de avançar |
