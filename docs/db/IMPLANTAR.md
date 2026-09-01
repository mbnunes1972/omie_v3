# Implantacao — reconstruir os ambientes pelo procedimento ensaiado

Caminhos reais, colhidos do servidor em 28/08/2026. Ordem: Integracao,
depois Homologacao, depois Producao. Cada uma so comeca quando a anterior
fechou a conferencia.

**Atualizacao de codigo (rotina) vive em `docs/db/ESTEIRA.md`, nao aqui.**
Este documento cobre o rebuild de schema (Passo 0 a 3.8, uma vez por
ambiente) e serve de referencia para os caminhos/armadilhas de cada
servidor. A partir de 31/08/2026 todo deploy de codigo — inclusive o
"Passo 2" abaixo, quando um rebuild precisar de codigo alinhado — sai de
uma tag e usa `git checkout <tag>`, nunca `git pull` de `main`: um so
procedimento, nao dois. Ver `## Conferir o que esta rodando` no fim.

## Mapa
    ambiente      host              servico      diretorio             env                     banco
    Integracao    167.88.33.121     orizon-a     /root/orizon-manager  /root/orizon-A.env       orizon_integracao
    Homologacao   167.88.33.121     orizon-b     /root/orizon-homolog  /root/orizon-B.env       orizon_homologacao
    Producao      179.197.77.9      orizon       /root/orizon-manager  /root/orizon.env (600)   orizon_producao

/root/orizon-homolog-data NAO tem git e NAO deve ser tocado. Sao dados.

PostgreSQL 16.15 nos servidores. Role `orizon` NAO tem CREATEDB: todo
create/drop de banco passa por `sudo -u postgres`.

## Passo 0 — uma vez por servidor: Alembic
Nao esta instalado. Ubuntu 24.04 / Python 3.12 exige a flag do PEP 668.

    pip install alembic --break-system-packages
    python3 -c "import alembic; print(alembic.__version__)"

## Passo 1 — levar o dump de configuracao
config_*.sql esta no .gitignore (tem credenciais). Nao vem pelo git.
Do WSL:

    scp docs/db/config_20260828_0206.sql root@167.88.33.121:/root/

## Passo 2 — atualizar o codigo
Deploy por tag (docs/db/ESTEIRA.md, 31/08/2026): o servidor faz checkout da
tag alvo, nunca `pull` de `main` — `pull` desfaz qualquer fixacao anterior
numa tag e deixa "o que esta rodando" dependente de quando alguem olhou o
`git log`. Mesmo comando nos dois diretorios (nao ha mais tag "so de
homolog" — Integracao e Homologacao acompanham a mesma linhagem de tags):

    cd /root/orizon-manager  && git fetch origin --tags && git checkout <tag>
    cd /root/orizon-homolog  && git fetch origin --tags && git checkout <tag>

Confira nos dois com `git describe --tags` (ver `## Conferir o que esta
rodando`) que a tag bate com a criada na bancada antes de seguir.

## Passo 3 — por ambiente

### 3.1 Parar o servico
    systemctl stop orizon-a          # ou orizon-b

### 3.2 Backup do que existe hoje
    mkdir -p /root/backups
    sudo -u postgres pg_dump orizon_integracao > /root/backups/integracao_pre_$(date +%Y%m%d_%H%M).sql
    ls -lh /root/backups/ | tail -2

Confira o tamanho antes de continuar. Sem backup nao se derruba nada.

### 3.3 Recriar o banco vazio
    sudo -u postgres psql -c "DROP DATABASE orizon_integracao;"
    sudo -u postgres psql -c "CREATE DATABASE orizon_integracao OWNER orizon;"

### 3.4 Estrutura pelas migrations
    cd /root/orizon-manager
    set -a; . /root/orizon-A.env; set +a
    DATABASE_URL="${DATABASE_URL}" alembic upgrade head
    alembic current

Se o DATABASE_URL do .env tiver +psycopg2 e algum comando reclamar, use
"${DATABASE_URL/+psycopg2/}" para psql e pg_dump.

### 3.5 Configuracao pelo dump
    sudo -u postgres psql -d orizon_integracao -v ON_ERROR_STOP=1 -f /root/config_20260828_0206.sql

### 3.6 Gabarito
    cd /root/orizon-manager
    set -a; . /root/orizon-A.env; set +a
    python3 scripts/aplicar_gabarito.py

Ele aplica o gabarito a cada owner restaurado e varre orfaos. Espere
"0 orfaos" se a configuracao veio inteira.

### 3.7 Conferencia
    psql "${DATABASE_URL/+psycopg2/}" -c "SELECT 'conta' t,count(*) FROM conta
      UNION ALL SELECT 'centro_custo',count(*) FROM centro_custo
      UNION ALL SELECT 'lojas',count(*) FROM lojas
      UNION ALL SELECT 'usuarios',count(*) FROM usuarios
      UNION ALL SELECT 'orcamentos',count(*) FROM orcamentos ORDER BY 1;"

Esperado com a configuracao do localhost: conta 1120, centro_custo 112,
lojas 6, usuarios 15, orcamentos 0.

### 3.8 Subir e olhar
    systemctl start orizon-a
    systemctl status orizon-a --no-pager | head -15
    journalctl -u orizon-a -n 40 --no-pager

No primeiro boot o init_db roda o _migrar_colunas_pg. O
test_schema_boot_estavel prova que ele nao altera o schema — mas leia o log
mesmo assim, e refaca a conferencia do 3.7 depois de subir. Se algum numero
mudou, o boot mexeu em dado e precisamos saber.

## Producao — reconstruida (rebuild de schema resolvido, ver `## Executado`)
Esta secao descrevia o rebuild de schema, ainda nao feito quando foi
escrita. Ja aconteceu (ver `## Executado`) e a pergunta do usuario admin
inicial ja tinha resposta no proprio codigo (`scripts/criar_primeiro_
admin.py`). Fica so como registro de que essa pergunta precisava ser
respondida ANTES, nao improvisada com a Producao fora do ar — mesmo
raciocinio vale pra proxima decisao pendente sobre ela.

Diretorio e `.env` do servico `orizon` em 179.197.77.9, levantados em
31/08/2026 (item 29 do Grupo 5, docs/db/PLANO_AJUSTES.md): diretorio
`/root/orizon-manager`, unidade `orizon.service`. A senha do banco vivia
em `Environment=` na propria unidade — qualquer um com `systemctl cat`
lia. Movida para `/root/orizon.env` (modo 600, `EnvironmentFile=`);
`systemctl cat orizon` hoje nao mostra credencial nenhuma. Backup da
unidade anterior em `/root/backups/orizon.service.bak.20260831_1604`.

## Armadilhas encontradas na execucao real (28/08/2026)

Quatro coisas que o ensaio no WSL nao revelou. Todas custaram tentativa.

1. **pip nao instala alembic sem --no-deps.** Ele tenta trocar o
   typing_extensions que veio do Debian, nao consegue remover o pacote do
   sistema, e aborta a instalacao inteira — inclusive a do alembic.

       pip install --break-system-packages --no-deps alembic Mako MarkupSafe

   Confira depois: `python3 -c "import alembic; print(alembic.__version__)"`.
   Servidor ficou com alembic 1.19.1 e SQLAlchemy 2.0.50 (WSL tem 2.0.51 —
   diferenca de patch, mas e' o primeiro lugar a olhar se algo divergir).

2. **Os .env usam `export`.** `grep '^DATABASE_URL='` nao acha nada. Use
   `set -a; . /root/orizon-A.env; set +a` e leia a variavel.

3. **O usuario postgres nao le dentro de /root** (modo 700). Restaurar com
   `-f /root/arquivo.sql` da "Permission denied". Deixe o root abrir o
   arquivo e entregar pela entrada padrao:

       ... | sudo -u postgres psql -d BANCO -v ON_ERROR_STOP=1 -q

4. **Dump gerado no PostgreSQL 18 nao restaura em 16 sem filtro.** O
   pg_dump 18 escreve `SET transaction_timeout = 0;` no cabecalho, e o 16
   recusa o parametro. Com ON_ERROR_STOP=1 aborta na primeira linha:

       grep -v '^SET transaction_timeout' config_AAAAMMDD_HHMM.sql | \
         sudo -u postgres psql -d BANCO -v ON_ERROR_STOP=1 -q

   O parametro vale zero (o padrao), entao remove-lo nao muda nada.

## Executado

- Integracao (orizon_integracao), 28/08/2026 06:20 — reconstruida.
  conta 1120, centro_custo 112, lojas 6, usuarios 15, redes 1, orcamentos 0.
  0 orfaos. Numeros identicos depois do boot. HTTP 302. Head 46a93cfd591b.
- Homologacao (orizon_homologacao), 28/08/2026 — reconstruida.
  Mesmos numeros, 0 orfaos, identicos depois do boot. HTTP 302.
  Os 10 owners anteriores dela foram substituidos pelos 7 do localhost,
  conforme a decisao "mista". Backup em /root/backups/homologacao_pre_*.
- Producao: reconstruida em algum momento entre 28/08 e 31/08 (fora deste
  fluxo — encontrada ja no head 46a93cfd591b, com 1 loja/1 usuario/0 redes,
  usuarios/lojas reais, HTTP 302). A pergunta do primeiro usuario admin
  ficou resolvida (`scripts/criar_primeiro_admin.py` existe no codigo).

### Marco da Fase 1 (docs/db/TAREFA_IMPLANTAR_FASE1.md) — 31/08/2026

**Registro historico — o metodo de atualizacao de codigo usado aqui
(`git pull` de `main`) foi substituido no mesmo dia pelo deploy por tag
(docs/db/ESTEIRA.md, ver "Primeiro deploy por tag" abaixo). Nao repita
`git pull` num deploy novo — o Passo 2 no topo deste documento ja reflete
o metodo atual.**

Upgrade INCREMENTAL nos tres ambientes (`git pull` + `alembic upgrade head`),
sem DROP/recriar banco — decisao do Marcelo: o `confirmar.sh` ja reconstroi
do zero num banco descartavel e compara, entao a garantia de schema vem sem
o risco de tocar na config real. Contagens de `lancamento`/`contratos`/
`orcamentos` ZERO nos tres ANTES de aplicar — nenhuma decisao sobre dado de
teste foi necessaria (a autorizacao "pode apagar" do Marcelo, acima, nao
precisou ser exercida).

Tres migrations aplicadas em sequencia (Integracao → Homologacao → Producao),
cada uma: backup (pg_dump) → systemctl stop → git pull → alembic upgrade
head → alembic current (confirma f47f22de46a7) → systemctl start → HTTP 302
→ `confirmar.sh` (15 OK / 0 FALHA nos tres). Contagens ZERO confirmadas de
novo depois do boot, nos tres — nenhum movimento apareceu.

### Primeiro deploy por tag (docs/db/ESTEIRA.md) — 31/08/2026

Tag `v2026.08.31-beta1` (9fc3d3c) — F2-4/ACHADO-25 resolvido, sem migration
nova. Integracao e Homologacao, nessa ordem, pelo procedimento novo da
esteira: `systemctl stop` → `git fetch --tags && git checkout <tag>`
(HEAD destacado, nao `pull` de `main`) → `systemctl start` → `confirmar.sh`
→ smoke (`POST /api/auth/login` com credencial inexistente responde 401
estruturado, nao 404/500; `/static/index.html` e `/static/login.html` 200).
`confirmar.sh` 15 OK / 0 FALHA nos dois. Producao NAO tocada — falta a
aprovacao do Marcelo na tela e a lista de defeitos conhecidos do candidato
(criterio Homologacao → Producao da esteira).

**Duas armadilhas novas, nao documentadas antes (nenhum dos dois servidores
tinha rodado `confirmar.sh` remotamente ate agora):**

5. `orizon_baseline_teste` (o banco descartavel que `confirmar.sh` usa pra
   comparar) nao existe nos servidores — so no WSL. Precisa ser criado uma
   vez por servidor postgres (`sudo -u postgres psql -c "CREATE DATABASE
   orizon_baseline_teste OWNER orizon;"`) antes da primeira conferencia.
   Integracao e Homologacao dividem o MESMO postgres (167.88.33.121) —
   so precisou uma vez la; Producao (179.197.77.9) precisou da sua propria.

6. **Senha com `$`/`#` quebra `confirmar.sh` de duas formas diferentes** (a
   senha do `orizon` em Producao tem os dois caracteres). Sourcing de um
   `.env` com o valor SEM aspas faz o bash tentar expandir `$...` como
   variavel e cortar a linha no `#` (comentario) — o `.env` precisa
   `KEY='valor'`, com aspas simples, mesmo padrao que orizon-A.env/
   orizon-B.env ja usavam (por isso so' Producao pegou essa). Separado
   disso, `#` **sempre** termina a autoridade de uma URI (RFC 3986) —
   mesmo escapando pra `%23`, valeu a pena so' pra `psql`/`pg_dump`
   (`PGURL`); pro alembic (SQLAlchemy, mais tolerante), o `DATABASE_URL`
   original sem escapar funciona. A solucao mais robusta: tirar a senha
   da URI de vez pro `PGURL` (`postgresql://orizon@localhost/db`) e
   deixar `~/.pgpass` (`host:port:*:user:senha`, 600) resolver a
   autenticacao — sem escapar nada.

### Segundo deploy por tag — v2026.08.31-beta2 — 31/08/2026

Tag `v2026.08.31-beta2` (a2889df) — ACHADO-27 resolvido (colapso do card de
ambientes na Negociacao com plano de pagamento longo), sem migration nova.
Mesmo procedimento do beta1, mesma ordem (Integracao, depois Homologacao):
`systemctl stop` → `git fetch --tags && git checkout v2026.08.31-beta2` →
`systemctl start` → `confirmar.sh` → smoke. `git describe --tags` confirmado
exato (`v2026.08.31-beta2`, sem sufixo `-N-g<hash>`) nos dois antes de
seguir. `confirmar.sh` 15 OK / 0 FALHA nos dois. Producao NAO tocada — mesmo
motivo do beta1 (falta aprovacao do Marcelo + lista de defeitos aceita, essa
atualizada em `docs/db/DEFEITOS_CONHECIDOS_beta1.md` pra registrar a
promocao pro beta2).

### Terceiro deploy por tag — v2026.08.31-beta3 — 31/08/2026

Pedido original era "tag v2026.08.31-beta2" de novo — já existia (deploy
acima), e tag não se move (`ESTEIRA.md`). `v2026.08.31-beta3` (54e35d0) no
lugar: ACHADO-28 resolvido (CPF de assinatura sem validação de dígito, nos
três caminhos + webhook ClickSign), sem migration nova. Mesmo procedimento,
mesma ordem. `git describe --tags` confirmado exato (`v2026.08.31-beta3`)
nos dois antes de seguir. `confirmar.sh` 15 OK / 0 FALHA nos dois.

Junto (Homologação, antes do deploy): funcionários semeados direto no banco
(`orizon_homologacao`, loja 1) — um por função-chave do ciclo (Medidor,
Consultor de Vendas, Projetista Executivo, Montador, Assistente
Administrativo), CPFs de teste válidos. Sem isso a transferência de
responsabilidade da etapa de Medição oferecia lista vazia — o que travava
o teste do Marcelo. Confirmado que os cinco sobrevivem ao restart do
serviço (checkout não toca banco). Producao NAO tocada — mesmo motivo do
beta1/beta2.

### Quarto deploy por tag — v2026.09.01-beta1 — 01/09/2026

Primeiro candidato com data de 01/09 (nome pela data real da construção,
não da linha anterior do ROTEIRO que especulava `-beta4`). Tag
`v2026.09.01-beta1` (`7c75e38`) — ACHADO-33 resolvido (Efetivar restaurado
em rubrica de veredito nomeado, Montagem/Fábrica sem outro alimentador);
itens 7/8 medidos, sem implementar (LP-11/LP-12); sem migration nova (o
único commit desde o beta3 que toca schema é nenhum — `7c75e38` é só
`TAREFA_BLOCO_FISCAL.md`, documentação do PRÓXIMO candidato, não deste
ciclo). Mesmo procedimento, mesma ordem (Integração, depois Homologação).
`git describe --tags` confirmado exato (`v2026.09.01-beta1`) nos dois.
`confirmar.sh` 15 OK / 0 FALHA nos dois. `alembic current` nos dois:
`f47f22de46a7 (head)` — reportado por pedido explícito (não o histórico do
repositório). Produção NÃO tocada nesta rodada.

## Conferir o que esta rodando

Nao entrar no servidor pra olhar `git log` — perguntar direto:

    cd /root/orizon-manager && git describe --tags
    cd /root/orizon-homolog && git describe --tags

Retorna a tag exata quando o HEAD esta nela (`v2026.08.31-beta1`) ou
`<tag-anterior>-N-g<hash>` se alguem rodou `pull`/`checkout` de um commit
fora de tag — nesse segundo caso o servidor esta fora do procedimento da
esteira e precisa voltar pra uma tag antes de qualquer outra coisa.
