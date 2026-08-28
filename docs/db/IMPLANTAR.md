# Implantacao — reconstruir os ambientes pelo procedimento ensaiado

Caminhos reais, colhidos do servidor em 28/08/2026. Ordem: Integracao,
depois Homologacao, depois Producao. Cada uma so comeca quando a anterior
fechou a conferencia.

## Mapa
    ambiente      host              servico      diretorio             env                banco
    Integracao    167.88.33.121     orizon-a     /root/orizon-manager  /root/orizon-A.env orizon_integracao
    Homologacao   167.88.33.121     orizon-b     /root/orizon-homolog  /root/orizon-B.env orizon_homologacao
    Producao      179.197.77.9      orizon       (a confirmar)         (a confirmar)      orizon_producao

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
/root/orizon-manager esta em main:

    cd /root/orizon-manager && git fetch origin && git pull

/root/orizon-homolog esta em HEAD DESTACADO na tag v2026.08.26i-homolog.
Precisa sair da tag primeiro:

    cd /root/orizon-homolog && git fetch origin && git checkout main && git pull

Confira nos dois que o commit bate com o do WSL antes de seguir.

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

## Producao — NAO EXECUTAR AINDA
Decisao: nasce so com estrutura e gabarito, sem configuracao.
Mas `usuarios` vazio significa que ninguem consegue entrar para criar a
rede e a loja reais.

ANTES de reconstruir a Producao, responder: o app cria um usuario admin
inicial no primeiro boot com o banco vazio? Se nao cria, o procedimento
precisa de um passo a mais — inserir um usuario master — e esse passo tem
que ser definido antes, nao improvisado com a Producao fora do ar.

Confirmar tambem o diretorio e o arquivo .env do servico `orizon` em
179.197.77.9, que ainda nao foram levantados.

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
- Producao: NAO executada. Bloqueada na pergunta do primeiro usuario.
