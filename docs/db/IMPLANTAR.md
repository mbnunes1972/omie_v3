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

### Passo obrigatório — primeiro segredo fiscal em Produção

Medido em 03/09: Produção não tem `config/fiscal.key` (nem a env
`ORIZON_FISCAL_KEY`). `integracoes/cripto_segredos.py` gera uma chave
Fernet sozinho, em silêncio, na primeira vez que qualquer coisa chamar
`encrypt()`/`decrypt()` — e essa chave nasce SEM cópia em lugar nenhum
além do disco daquele servidor.

**No dia em que o primeiro segredo fiscal (token Focus, D4Sign, o que for)
for configurado em Produção — antes de qualquer outra coisa:**

1. Configurar o segredo normalmente (a chave é gerada nesse momento, se
   ainda não existir).
2. `cat /root/orizon-manager/config/fiscal.key` no servidor de Produção e
   copiar os 44 bytes para o gerenciador de senhas do Marcelo, guardado
   por uma pessoa — nunca em automação (mesmo raciocínio do backup:
   segredo não se protege pela automação que o atacante também controla).
3. Só depois seguir com o resto do trabalho do dia.

Sem isso, o primeiro segredo fiscal real de Produção passa a depender de
44 bytes que ninguém guardou — perder o disco perde a chave e tudo que
ela decifra, sem aviso prévio, porque nada quebra até o dia em que quebra.

### Produção — diagnóstico de 04/09 e o que fazer quando reconstruir

Diagnóstico só leitura, pedido depois de o fechamento do F2-20 reportar
Produção fora da esteira. Nada foi tocado — nenhum fetch, checkout,
migration, restart ou mudança de config/permissão.

**Estado:** `git describe --tags` devolve `v2026.08.26i-homolog-88-g5e234bb`;
HEAD em `5e234bb`, de 31/08.

**Como saiu da esteira:** pelo `reflog`, alguém fez `git checkout main` à
mão no servidor em 28/08 04:11:15 -03, saindo de `2f35ec2` (tag
`v2026.08.13b-prod`, vigente de 13/08 a 28/08); depois três `pull --ff`
sucessivos até `5e234bb` em 31/08 01:27. Isso é **três dias antes** de o
`ESTEIRA.md` existir (31/08) — não é violação de uma regra vigente, é o
servidor que ficou de fora quando a regra nasceu. Sem culpar ninguém: o
que importa é que ninguém percebeu por 7 dias.

**Não está quebrado.** `alembic current` = `f47f22de46a7`, que é o head
daquela árvore específica — `migrations/versions/` deste checkout só tem
8 arquivos, e `b0ecb9ce82d2` (ACHADO-30) e `82275b998a4a` (ACHADO-47) não
existem nela. `ciclo_documentos` tem 8 colunas, sem `removido_em`; o
código não tem `_docs_vivos` em lugar nenhum (zero ocorrências). Código e
schema estão em paridade entre si, só que os dois três semanas atrás. O
alarme inicial (código novo lendo coluna que não existe) era falso —
não há código novo ali.

**Sem uso real.** 1 usuário cadastrado (`mbn1972@gmail.com`), 0 sessões
(tabela `sessoes` vazia), 0 upload em `ciclo_documentos` desde 28/08,
~3500 requisições em 9 dias quase todas de scanner automatizado, zero
`POST` de login real. Serviço ativo, journal sem erro desde 29/08.

**Sondagens de bot (`.git`, `.env`, `phpinfo`) não acharam nada.**
Caminhos com prefixo de dicionário (`/wordpress/.env`, `/laravel/.git/
config`, …) → 404. Caminhos exatos (`/.git/config`, `/.env`,
`/.git-credentials`, …) → 301, mas com corpo **fixo de 178 bytes em
todos** — arquivos reais diferentes teriam tamanhos diferentes; é
redirect genérico do app, não o nginx entregando conteúdo do disco.
Zero 200 e zero 206 em toda a base de logs rotacionados. Confirmado no
config: o `server` ativo (`orizonone`) só tem `location = /privacidade`
(alias fora do repositório) e `location /` → `proxy_pass
127.0.0.1:8765` — nenhum `root`/`alias` aponta pro repositório em lugar
nenhum. `/root/orizon.env` em 600; `/root/orizon-manager/.git` em 755,
mas `/root` em si está em 700 — não atravessável por ninguém além de
root, com ou sem nginx.

**O achado que fica, e que muda o rebuild:** o processo do app roda como
**root** (uid 0), não como usuário de serviço próprio. As três camadas
acima (nginx sem root/alias, `.env` 600, `/root` 700) protegem contra o
lado de fora; nenhuma protege contra o próprio app — e o app é root, o
nginx manda toda requisição pra ele, e ele faz parsing de XML de
terceiros (NF-e da fábrica). Uma falha de execução ali não vira "alguém
leu um arquivo", vira a máquina inteira, com o `.env` que o 600
aparentemente guardava. Contradiz a regra permanente de bind em
`127.0.0.1` — que existe pelo mesmo motivo e foi seguida à risca.

**Conclusão registrada, nenhuma ação imediata:** Produção não volta por
`pull` nem por migration avulsa — volta **reconstruída** a partir de uma
tag, pelo procedimento deste documento, quando a linha atual (F2-22 em
diante) tiver sido percorrida em Homologação e aprovada pelo Marcelo. O
usuário de serviço próprio (app fora do root, `.env` e diretório com dono
próprio, não mais `root:root`) é criado **nesse momento** — custa quase
nada dentro de um rebuild que já vai parar o serviço e recriar tudo, e
custa uma janela de parada inteira se for feito isolado depois. Não
tocar Produção antes disso, nem "só" para criar esse usuário.

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

### Quinto deploy por tag — v2026.09.03-beta1 → v2026.09.03-beta2 — 03/09/2026

`v2026.09.03-beta1` (`29e4cdc`) — F2-13 (ACHADO-45 regra corrigida, 46, 47)
+ F2-14 (ACHADO-48, fuso horário como configuração). Primeira migration nova
desde o beta1 de 01/09 (`f47f22de46a7` → `a1b2c3d4e5f6`, colunas Adicional
do ACHADO-47) — backup + `alembic upgrade head` + `alembic current` nos
dois antes de subir. Mesmo procedimento, mesma ordem (Integração, depois
Homologação). `confirmar.sh` 15/0 nos dois, smoke OK.

Ao revisar o deploy, achado: o revision id `a1b2c3d4e5f6` foi digitado à
mão (óbvio demais pra ser gerado), ao contrário de todos os outros da
cadeia. Corrigido para `82275b998a4a` (gerado). Primeira tentativa moveu a
própria `v2026.09.03-beta1` pro commit corrigido — decisão revertida no
mesmo dia: mover tag "só para bookkeeping" é precedente que se reaplica com
menos cuidado depois, e cortar uma tag nova custa só um número que pula.
`v2026.09.03-beta1` foi devolvida ao commit original (`29e4cdc`) e fica
como registro histórico de que existiu e foi superada; `v2026.09.03-beta2`
(`4f7b831`) é quem os servidores rodam de fato. Nos dois: `git checkout
v2026.09.03-beta2`, `UPDATE alembic_version SET version_num=
'82275b998a4a'` (troca de nome, não migration nova — o commit não muda
schema), `alembic current` → `82275b998a4a (head)`, `confirmar.sh` 15/0,
smoke OK. Produção NÃO tocada nesta rodada.

### Sexto deploy por tag — v2026.09.03-beta3 — 03/09/2026

A `v2026.09.03-beta2` nasceu de suíte VERMELHA — o corte da tag aconteceu
antes de rodar `pytest -q` completo depois da correção do revision id (a
suíte só foi rodada por pedido explícito, depois do deploy já feito). 3
falhas: `test_e2e_browser_ciclo_overlay`, `test_e2e_browser_conciliacao_
final`, `test_e2e_browser_negociacao_layout` — as três com a mesma linha,
`page.wait_for_selector("text=140.000,00")`, um locator sem escopo que
casava com uma célula (escondida) da tabela de projetos por baixo do
painel de negociação, e o Playwright trava no primeiro match em ordem de
DOM mesmo com os outros 8 visíveis. Bisectado com `git worktree`: passava
em `ed761b6` (antes do ACHADO-48), falhava em `HEAD` — a mudança em
`_enriquecer_projetos_com_atraso` deslocou o timing o suficiente pra expor
uma fragilidade que já existia no teste, não um defeito novo no app.
Escopado para `#neg-subtotal` (único, dentro do painel de negociação);
controle negativo confirmou a falha em alta frequência com o locator
genérico (não 100% determinístico — é corrida, não travamento duro — mas
o padrão é claro).

Regra da esteira vale igual mesmo quando a ordem de quem pediu empurrou
pra trás: tag só depois de suíte verde. `v2026.09.03-beta2` fica onde
está (`4f7b831`), registro histórico de que existiu e foi superada — não
movida, mesma lição do episódio do id de migration algumas horas antes.
`v2026.09.03-beta3` (`30cb7e0`) é quem os servidores rodam. Nos dois: sem
migration nova (só teste + doc, `git diff --stat` confirmado vazio para
código de aplicação, nenhum serviço reiniciado), `git checkout
v2026.09.03-beta3`, `confirmar.sh` 15/0, smoke OK. `pytest -q`: 2565
passed, 4 xfailed (pré-existentes, ACHADO-01/19/20), 0 failed. Produção
NÃO tocada nesta rodada.

### Sétimo deploy por tag — v2026.09.04-beta1 — 04/09/2026 (madrugada, sem percurso)

**ESTE DEPLOY TEM MIGRATION NOVA — diferente do sexto, que não tinha.** Não
copiar aquele template: aqui houve parar o serviço, `alembic upgrade head` e
subir de novo, nos dois. Entre `v2026.09.03-beta3` e este candidato entrou
uma única migration, `b0ecb9ce82d2` (ACHADO-30, `82275b998a4a` → `b0ecb9ce82d2`).

Candidato de madrugada — só prova por TESTE, sem ninguém pra clicar em tela.
LP-17 resolvida (`b7bb834`/`0e1800c` — os dois testes que comparavam
`datetime.utcnow()` com competência já migrada pro ACHADO-48 passam a derivar
de `hoje_no_fuso`/`agora_no_fuso`); item 5 do bloco fiscal só MEDIDO
(`d8b8c29` — as duas decisões pendentes, nada implementado). `pytest -q`
rodado DUAS vezes completo, `TZ=UTC` e `TZ=America/Sao_Paulo` forçados no
processo (a janela real de discordância já tinha fechado — verde por causa
da hora não conta, regra do ESTEIRA.md): **2601 passed, 0 failed, 4 xfailed**
nos dois fusos.

Tag `v2026.09.04-beta1` (`d8b8c29`) — nome pela data do corte (04/09, não
"beta4"). `v2026.09.03-beta3` fica onde está, não movida. Nos dois
servidores, nessa ordem (Integração, depois Homologação): backup
(`pg_dump`) → `systemctl stop` → `git fetch --tags && git checkout
v2026.09.04-beta1` → `alembic upgrade head` (`82275b998a4a` →
`b0ecb9ce82d2`) → `alembic current` confirma o head → `systemctl start` →
`confirmar.sh` 15/0 → smoke (401 login inválido, 200 index/login) →
`git describe --tags` confirmado exato (`v2026.09.04-beta1`, sem sufixo
`-N-g<hash>`) nos dois. **Produção NÃO tocada** — madrugada, sem ninguém
acompanhando, por instrução explícita.

### Oitavo deploy por tag — v2026.09.04-beta2 — 04/09/2026

**Sem migration nova** — `git diff --stat` de `migrations/` entre
`v2026.09.04-beta1` e este candidato vazio; caso do "sem migration"
(mesmo template do segundo/terceiro deploy), não do template do sétimo.

O F2-20 inteiro (ACHADO-49/50/51, `cef4587`..`cd48760`) tinha ficado
commitado mas nunca tagueado/implantado — este é o primeiro deploy desde
`v2026.09.04-beta1` (`d8b8c29`), e carrega os dois candidatos juntos:
F2-20 (Remover da etapa 12 espelha o upload; nota `PROCESSANDO` ganha
mensagem dedicada; NF-e da fábrica em duplicata bloqueada por chave,
dentro do mesmo projeto) e F2-22 (diagnóstico só-leitura de Produção
registrado — ver `### Produção — diagnóstico de 04/09` acima; ACHADO-52,
remoção da subfase de PE volta a espelhar a porta — execução ou revisão
— que subiu o documento; ACHADO-51 estendido pra bloquear a mesma chave
também ENTRE projetos, com a exceção de projeto cancelado liberando a
chave). `pytest -q` completo: **2615 passed, 0 failed, 4 xfailed**.

Tag `v2026.09.04-beta2` (`240103d`) — nome pela data do corte, `-beta1`
já ocupada por `d8b8c29`. Nos dois servidores, nessa ordem (Integração,
depois Homologação): `systemctl stop` → `git fetch --tags && git
checkout v2026.09.04-beta2` → `systemctl start` → `confirmar.sh` 15/0 →
smoke (401 login inválido, 200 `index.html`/`login.html`) → `git
describe --tags` confirmado exato nos dois. **Produção NÃO tocada** —
ela agora tem tratamento próprio (não volta por `pull`/checkout de tag
avulsa; volta reconstruída, ver `### Produção — diagnóstico de 04/09`
acima).

### Nono deploy por tag — v2026.09.05-beta1 — 05/09/2026

**Sem migration nova** — `git diff --stat` de `migrations/` entre
`v2026.09.04-beta2` e este candidato vazio.

F2-23, saído do percurso do Marcelo em Homologação (04/09): ACHADO-54
(NF-e de produto rejeitada era beco sem saída — `ref` por tentativa,
mesma regra da NFS-e, mais a tela voltando a oferecer nova
tentativa/Remover quando a emissão está em `erro`); ACHADO-53 (abrir os
parâmetros de um projeto assinado não dispara mais `POST /parametros`
— dois portões, `_mpPopulando`/`_mpModoLeitura`, no ponto de
consequência); ACHADO-51 estendido de novo (NF-e cancelada libera a
mesma chave da fábrica — terceira condição; e as recusas "mesma etapa"
e "selo do destinatário" passam a dizer o que bloqueou, por quê, e a
saída, mesmo padrão da recusa "outro projeto"); ACHADO-36 estendido
(faixa do ciclo — 31 `showToast(..., true)` convertidos pra
`avisoPopup`). Achado ao rodar a suíte inteira: seis testes
pré-existentes quebraram por dependerem do formato antigo do `ref`
(constante por documento) ou do texto antigo da mensagem de
destinatário — corrigidos pra ler o `ref`/mensagem reais em vez de
reconstruir. `pytest -q` completo: **2630 passed, 0 failed, 4 xfailed**.

Tag `v2026.09.05-beta1` (`5ff46c8`) — nome pela data do corte. Nos dois
servidores, nessa ordem (Integração, depois Homologação): `systemctl
stop` → `git fetch --tags && git checkout v2026.09.05-beta1` →
`systemctl start` → `confirmar.sh` 15/0 → smoke (401 login inválido,
200 `index.html`/`login.html`) → `git describe --tags` confirmado
exato nos dois. **Produção NÃO tocada** — tratamento próprio, ver
`### Produção — diagnóstico de 04/09` acima.

### Décimo deploy por tag — v2026.09.05-beta2 — 05/09/2026

**Sem migration nova** — `git diff --stat` de `migrations/` entre
`v2026.09.05-beta1` e este candidato vazio.

F2-24, saído do percurso do Marcelo em Homologação (05/09, confirmado
na tag NOVA). Três frentes de código, em ordem: ACHADO-55 (a ÚNICA que
mexe em dinheiro) — a decisão do PE (manter/absorver/cobrar/estornar)
corrigia o registro (`ConciliacaoPeFase`) a cada redecisão, mas o
crédito ao cliente só sabia criar, nunca reverter; sair de "estornar"
deixava o crédito órfão no razão. Medido em Homologação: 1 caso real
(`Teste_4`/pool 16, R$ 64.043,46 órfão). Conserto por lançamento, nunca
apagamento (`registrar_credito_cliente_pe`/`reverter_credito_cliente_pe`,
mesmo desenho do `estornar_rateio`); janela nova — redecidir depois da
aprovação do PE pelo cliente (11e concluída) é recusado. ACHADO-58 —
os dois botões Remover (etapa 12 e NF-e da fábrica) continuavam sem
funcionar apesar de teste verde: os testes E2E antigos chamavam a
função JS direto ou conferiam a STRING de HTML de um render isolado,
nunca clicavam no botão real. Construído
`tests/test_e2e_browser_remover_ciclo.py` (clique real no DOM real) e
achado o bug de verdade — `JSON.stringify(nome_original)` interpolado
sem escape dentro de um `onclick="..."` delimitado por aspas duplas,
produzindo `Unexpected end of input` em TODO clique, sempre. Corrigido
com `esc(JSON.stringify(...))` nos quatro lugares com o padrão (regra
dos irmãos), não só os dois relatados. ACHADO-57 — a etapa Montagem se
dava por concluída sozinha, logo após assinar o contrato: a leniência
"toggleável sem linha nenhuma = satisfeita" (pra subfase opcional sem
pendência não travar o grupo) se aplicava também ao código-mãe da
etapa — um projeto novo, sem nenhuma linha de Montagem ainda,
"satisfazia" as duas por omissão. Medido ao vivo em Homologação
(`Projeto_3`/`Teste_2`, condição exata hoje). Também registrado, sem
implementar (PASSO 0): ACHADO-56 (Revisão de PE fecha verde antes do
veredito — família do ACHADO-39), LP-19 (valor estourando coluna,
família do C6), LP-18 ganha confirmação (carga de NF-e na subfase de
recebimento), LP-13 recebe o desenho fechado (Fila no Financeiro, um
componente com dois pontos de montagem). `pytest -q` completo: **2639
passed, 0 failed, 4 xfailed**.

Tag `v2026.09.05-beta2` (`2d762b2`) — nome pela data do corte, `-beta1`
já ocupada. Nos dois servidores, nessa ordem (Integração, depois
Homologação): `systemctl stop` → `git fetch --tags && git checkout
v2026.09.05-beta2` → `systemctl start` → `confirmar.sh` 15/0 → smoke
(401 login inválido, 200 `index.html`/`login.html`) → `git describe
--tags` confirmado exato nos dois. **Produção NÃO tocada** —
tratamento próprio, ver `### Produção — diagnóstico de 04/09` acima.

### Décimo primeiro deploy por tag — v2026.09.05-beta3 — 05/09/2026

**Sem migration nova** — `git diff --stat` de `migrations/` entre
`v2026.09.05-beta2` e este candidato vazio.

F2-25, saído do Teste 5 do Marcelo em Homologação (05/09). Quatro
frentes: ACHADO-59a (defeito) — `out_forn` digitado na AF1 era aceito
e persistido, mas nunca gerava lançamento (`_AF_ITEM_RUBRICA` excluía
a chave com um comentário desatualizado); conserto de 3 linhas
(EVENTOS + `_PROV_FECHAMENTO`/`_AF_ITEM_RUBRICA`). ACHADO-59b
(DECIDIDO) — Custo de Fábrica vira linha editável na AF1/AF2,
reusando a Conferência contábil da etapa 12 sem mecanismo novo; gate
de duplicação de custo medido e negativo antes de mexer; achado no
meio do caminho — a composição dos dois lançamentos da Conferência
debitava o CFO duas vezes quando a nova chamada passava o valor novo E
o resíduo ao mesmo tempo, corrigido (`max(novo, atual)` no primeiro
lançamento); a etapa 12 em si não mudou (regressão de 19 testes
confirmando). Fila de Provisões (DECIDIDO) — passa a listar as 17
rubricas elegíveis SEMPRE (não só as em aberto), agrupadas EM
ABERTO/FECHADAS-ZERADAS com contagem rotulada por grupo; uma rubrica
resolvida não some mais. Lista de Provisões — `white-space:nowrap`
nas colunas numéricas (família do C6/LP-19); o link que navegava pra
Fila virou botão "Resolver" que abre o box na própria linha, opções
vindas do servidor (antecipa só esta parte da LP-13, já com desenho
fechado). O relabeling de veredito (Absorver/Receber/Encerrar/Adiar)
pedido no percurso original ficou PARADO — registrado como LP-20:
"Receber" revelou depender de lançar receita de verdade no momento
fiscal (NF-e), pergunta em aberto que volta pro Marcelo antes de
qualquer rótulo novo. `pytest -q` completo: **2650 passed, 4 xfailed,
0 failed**.

Tag `v2026.09.05-beta3` (`2efff6e`) — nome pela data do corte,
`-beta1`/`-beta2` já ocupadas. Nos dois servidores, nessa ordem
(Integração, depois Homologação): `systemctl stop` → `git fetch
--tags && git checkout v2026.09.05-beta3` → `systemctl start` →
`confirmar.sh` 15/0 → smoke (401 login inválido via
`/api/auth/login`, 200 `login.html`, 302 `index.html` sem sessão) →
`git describe --tags` confirmado exato nos dois. **Produção NÃO
tocada** — tratamento próprio, ver `### Produção — diagnóstico de
04/09` acima.

### Décimo segundo deploy por tag — v2026.09.05-beta4 — 05/09/2026

**Migration nova**: `a1f2e3c4d5b6` (Contas de Conciliação, 4.5.01/5.7.01
+ sintéticas 4.5/5.7) — dois passos (backfill via `aplicar_gabarito_
completo` pras lojas/redes reais; INSERT literal pros 3 owners históricos
congelados que `test_gabarito_migration_x_seed.py` depende).

F2-27 — a mudança do modelo contábil decidida no F2-26: reconhecimento
de despesa volta a acontecer na EMISSÃO da NF-e (`reconhecer_provisoes_
segmento`), pelo PROVISIONADO INTEGRAL das 17 rubricas de despesa em
tempo real, segmentado Merc/Serv — não mais na efetivação/pagamento.
`efetivar_provisao` ficou perna ÚNICA (provisão×caixa/fornecedores); o
ativo diferido (1.1.06.xx) só se move por constituição/AF/reclassificação/
reconhecimento, nunca por pagamento. Contas de Conciliação novas (4.5.01
Receita/5.7.01 Despesa), bloco próprio na DRE depois do EBIT; vereditos
renomeados/colapsados (Absorver/Receber/Encerrar/Adiar), ACHADO-22
fechado (rótulos "NA NF-E" corrigidos).

Candidato interrompido no meio da verificação (suíte em segundo plano
morta aos 35min sem resultado parcial) — protegido em branch `f2-27-wip`
antes de qualquer coisa, depois verificado em CAMADAS ascendentes em vez
da suíte inteira de uma vez (novos arquivos → 8 modificados → subconjunto
contábil → suíte sem E2E → E2E um por vez). A camada do subconjunto
contábil revelou 49 failed/60 errors — causa raiz: mocks E2E de F2-25 com
strings de veredito antigas, cascateando em timeouts que pareciam falha
de infraestrutura em arquivos não relacionados; rederivados. Achado no
caminho, **ACHADO-60**: `margem_projetada`/`dre_simulada` liam o eixo do
PASSIVO (saldo de provisão não pago) pra medir "o que falta reconhecer"
— correto enquanto reconhecimento e pagamento andavam juntos, virou
duplo-conto quando o F2-27 os separou; corrigido lendo o ATIVO. A camada
seguinte (suíte completa sem E2E) revelou mais 29 falhas, todas a mesma
causa (testes que nunca simulavam a emissão) — rederivadas, incluindo os
21 cenários de `test_bateria_ciclo.py` num único ponto do helper
compartilhado. `pytest -q` completo (com E2E): **2661 passed, 4 xfailed,
0 failed**, 467s, sem travar nenhum E2E.

Tag `v2026.09.05-beta4` (`0fa1653`, merge `1a31fa6`). Nos dois
servidores, nessa ordem (Integração, depois Homologação): `systemctl
stop` → `git fetch --tags && git checkout v2026.09.05-beta4` → `set -a;
. ./.env; set +a && alembic upgrade head` (confirma `a1f2e3c4d5b6 (head)`
nos dois) → `systemctl start` → `confirmar.sh` 15/0 → smoke (401 login
inválido via `/api/auth/login`, 200 `login.html`, 302 `index.html` sem
sessão) → `git describe --tags` confirmado exato nos dois. **Produção
NÃO tocada** — tratamento próprio, ver `### Produção — diagnóstico de
04/09` acima.

### Décimo terceiro deploy por tag — v2026.09.05-beta5 — 05/09/2026

**Migration nova**: `c2d3e4f5a6b7` (`contratos.financeiro_concluido_em`/
`financeiro_concluido_por_id` — só schema, sem backfill de dado).

F2-28 — primeiro percurso do Marcelo conferindo o razão com o modelo do
F2-27 valendo (Teste_6, beta4). Achou que "Atual" no painel de Provisões
nunca refletia a AF/Conferência: `_negociacao_breakdown` recalcula da
negociação salva, nunca lê o razão — corrigido pra Custo de
Fábrica/Outros Fornecedores lerem o saldo vivo da provisão. Confirmou
que o ajuste do CFO não lançava por design correto (o resíduo já levava
o CFO ao valor novo, não por silêncio). DECIDIDO: Custo de Fábrica virou
read-only na AF — só "Outros Fornecedores" é digitado (o incremento), a
contrapartida contra a fábrica é automática (reclassificação); lista de
rubricas ganhou uma linha só de Custo de Fábrica (saldo vivo), o CFO
congelado foi pro bloco de totais. `Contrato.financeiro_concluido_em`
(distinto de `status`, que segue "vigente" intocado): `POST .../
contrato/concluir-financeiro` confere consistência (AF concluída,
documentos do PE vivos, provisão×ativo pareados —
`mod_contabil.conferir_provisao_ativo_par`, nova) antes de fechar a fase
financeira; daí em diante, reabrir a AF exige "autorizar". Princípio
registrado em `docs/db/PLANO_AJUSTES.md` (5ª regra): nenhuma etapa
encerra sem conferir o que prometeu, nenhuma etapa trava o andamento por
causa disso. `pytest -q` completo (com E2E): verde, 4 xfailed, 0 failed
determinístico — `test_fluxo_completo_e2e.py::
test_contrato_real_geracao_e_assinatura` falhou uma vez isolado,
confirmado via `git stash` que já falha identicamente sem nenhuma
mudança deste candidato (flaky pré-existente, reportado).

Tag `v2026.09.05-beta5` (`1bdd892`). Nos dois servidores, nessa ordem
(Integração, depois Homologação): `systemctl stop` → `git fetch --tags
&& git checkout v2026.09.05-beta5` → `set -a; . ./.env; set +a &&
alembic upgrade head` (confirma `c2d3e4f5a6b7 (head)` nos dois) →
`systemctl start` → `confirmar.sh` 15/0 → smoke (401 login inválido via
`/api/auth/login`, 200 `login.html`) → `git describe --tags` confirmado
exato nos dois. **Produção NÃO tocada** — tratamento próprio, ver
`### Produção — diagnóstico de 04/09` acima.

### Décimo quarto deploy por tag — v2026.09.06-beta1 — 06/09/2026

**Sem migration nova** — F2-29 mexeu só em código/frontend/testes.

F2-29 — montado em FATIAS a pedido do Marcelo (percorrido uma vez só,
depois de as quatro fecharem), retomando o percurso do beta5 (Teste_6).
**Fatia B** (AF1 não reabria): medido `Contrato.financeiro_concluido_em`
NULL (o gate do F2-28 não disparou) e `reabertura_bloqueada_por_contrato`
também não bloqueia reabrir a etapa 8 — nenhum gate encontrado deveria
ter travado; o Marcelo confirmou que era navegação (achou o botão),
não defeito — nenhuma mudança de código. **Fatia A**: o F2-28 cobriu só
`custo_fabrica`/`out_forn` na coluna "Atual" do painel de Provisões —
as outras 17 rubricas continuavam lendo a negociação salva, nunca o
razão (regra dos irmãos, ACHADO-26); corrigido com um mapa novo
(`mod_contabil._PAINEL_ITEM_RUBRICA_TODAS`) lendo o saldo vivo de cada
uma. F2-28 marcado PARCIAL no seu próprio registro. **Fatia C**: dos 8
painéis abertos de dentro do ciclo, 4 não identificavam o projeto
(Provisões só com "Orçamento #N"; Mapa de Atribuições/Retenção/Grupo de
Acompanhamento sem nome nenhum) — corrigidos com o mesmo padrão "Projeto
&lt;nome&gt;" dos outros 4. **Fatia D** (isolamento de testes instáveis):
a varredura mais ampla da LP-17 (pedida no F2-19, nunca feita) saiu
limpa — 0 riscos novos. `test_contrato_real_geracao_e_assinatura`
(reportado como flaky no F2-28) na verdade NUNCA foi aleatório: checava
uma provisão de "venda" ANTES da própria 2ª assinatura (que é quando ela
nasce de verdade) — só "passava" quando um teste vizinho no MESMO
arquivo, com o mesmo orçamento do seed compartilhado, rodava antes e
deixava resíduo; determinístico, corrigido movendo a checagem pro lugar
certo. LP-16 (`test_aceite_achado12.py`) segue aberta — só higiene
aplicada (sessões vazadas fechadas), causa raiz não confirmada, precisa
de bisect real. `pytest -q` completo (com E2E): verde, 4 xfailed, 0
failed.

Tag `v2026.09.06-beta1` (`2421a8f`). Nos dois servidores, nessa ordem
(Integração, depois Homologação): `systemctl stop` → `git fetch --tags
&& git checkout v2026.09.06-beta1` → `alembic upgrade head` (confirma
`c2d3e4f5a6b7 (head)`, sem migration nova) → `systemctl start` →
`confirmar.sh` 15/0 → smoke (401 login inválido via `/api/auth/login`,
200 `login.html`) → `git describe --tags` confirmado exato nos dois.
**Produção NÃO tocada** — tratamento próprio, ver `### Produção —
diagnóstico de 04/09` acima.

### Décimo quinto deploy por tag — v2026.09.06-beta2 — 06/09/2026

**1 migration nova** — `655716ac5fd8` (conta `5.3.22 Despesa Avulsa de
Projeto`, backfill nos owners já existentes; mesmo padrão de
`a1f2e3c4d5b6`).

F2-30 — em fatias (ordem 1→2→3→4), retomando o percurso do beta5
(Teste_6). **Fatia 1** (rescaldo do F2-28): duas revisões sucessivas da
AF1 deixavam o snapshot da revisão com Custo de Fábrica desatualizado
(a contrapartida da migração ANTERIOR, não da desta submissão) — a tela
só manda o prefill de quando o box abriu, nunca o resultado da migração
DESTA submissão. Corrigido calculando a migração ANTES de montar o
registro; restrito à branch "revisa" (achado ao rodar
`test_rev1_concorda_copia_venda`: o primeiro conserto recomputava até em
"concorda", zerando o valor antes de qualquer fechamento real ter
postado no razão). **Fatia 2** (DECIDIDO 06/09): compra complementar
descoberta na entrega, sem provisão que sirva, não é operação de AF —
`despesa_avulsa` ganhou `projeto_id` opcional e a conta nova `5.3.22`
(grupo 5.3, de propósito — `margem_projeto` só desconta 3 contas
nomeadas do 5.2, mas o 5.3 inteiro via `comissao`); recusa as contas de
Conciliação (4.5.01/5.7.01) explicitamente. **Fatia 3** (só
documentação): registrado no MODELO_CONTABIL.md os três destinos de um
gasto de projeto (consome/excede/avulsa) e a regra da porta DERIVADA
(mesmo princípio do ACHADO-41). **Fatia 4**: LP-16 reexaminado com a
lente do F2-29 Fatia D — achado estrutural que o descarta da classe
"resíduo de vizinho" (é o primeiro teste do próprio arquivo, sem vizinho
de módulo possível); bisect real com `pytest-randomly` não reproduziu
(não é prova de aleatoriedade, registrado honestamente em aberto).
**Achado incidental, fora das 4 fatias** (LP-21): `test_bateria_ciclo.py`
mostra o MESMO padrão de instabilidade não determinística do LP-16, numa
área de código sem relação — confirmado pré-existente via A/B com o
F2-30 inteiramente stashed (a suíte completa já falhava, com contagens
diferentes a cada rodada, em `main` sem nenhuma mudança deste candidato).
Verificação em camadas: (a)/(b)/(c) verdes (549 testes no subconjunto
contábil/AF/contrato/perfil/dre/conciliação); (d) suíte completa sem E2E
instável (LP-21, pré-existente, não atribuível ao F2-30); (e) os 6 E2E
de navegador, um por vez, nenhum travou.

Tag `v2026.09.06-beta2` (`4f63666`). Nos dois servidores, nessa ordem
(Integração, depois Homologação): `systemctl stop` → `git fetch --tags
&& git checkout v2026.09.06-beta2` → `alembic upgrade head` (roda
`655716ac5fd8`) → `systemctl start` → `confirmar.sh` 15/0 → smoke (401
login inválido via `/api/auth/login`, 200 `login.html`) → `git describe
--tags` confirmado exato nos dois. **Produção NÃO tocada** — tratamento
próprio, ver `### Produção — diagnóstico de 04/09` acima.

## Conferir o que esta rodando

Nao entrar no servidor pra olhar `git log` — perguntar direto:

    cd /root/orizon-manager && git describe --tags
    cd /root/orizon-homolog && git describe --tags

Retorna a tag exata quando o HEAD esta nela (`v2026.08.31-beta1`) ou
`<tag-anterior>-N-g<hash>` se alguem rodou `pull`/`checkout` de um commit
fora de tag — nesse segundo caso o servidor esta fora do procedimento da
esteira e precisa voltar pra uma tag antes de qualquer outra coisa.

E a bancada, no mesmo fechamento. Ela não aparece no `git describe` de servidor
nenhum, e por isso já ficou duas migrations atrás sem ninguém notar (04/09, ver
`ESTEIRA.md`, `## Paridade`):

    cd /mnt/e/2026/DESENVOLVIMENTO/orizon-manager
    set -a && . ./.env && set +a && python3 -m alembic current

Tem que devolver a MESMA revisão que os servidores. Se não devolver,
`alembic upgrade head` antes de qualquer percurso local — a suíte monta o
próprio schema e não denuncia esse atraso; o app aberto na tela, sim.
