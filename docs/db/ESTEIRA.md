# A esteira — bancada, Integração, Homologação, Produção

Escrita em 31/08/2026, quando o Marcelo decidiu separar **ambiente** de
**bancada** e formalizar a passagem entre estágios.

## Por que existe

Os três servidores já existiam, com migrations encadeadas, `confirmar.sh` e
procedimento documentado. O que não existia era a **regra de passagem** — e
no marco da Fase 1 implantamos nos três na mesma tarde, sem nada impedir.
Esteira sem regra é desenho.

## Os quatro estágios

| estágio | o que é | quem usa |
|---|---|---|
| **Bancada** | onde se escreve código e a suíte roda em segundos | Vera, Claude |
| **Integração** | primeiro alvo de implantação; prova que o deploy funciona | automático |
| **Homologação** | onde o Marcelo clica, com dado parecido com o real | Marcelo |
| **Produção** | só o que passou pelos três | clientes |

**A bancada não é ambiente.** Ninguém valida nada nela, ninguém tira
conclusão de negócio dela. É oficina. No dia em que existir um servidor de
desenvolvimento remoto, ele entra como estágio 1 e a bancada continua sendo
o que já é.

## O critério de saída de cada estágio

Nada avança sem o seu critério cumprido. **O critério é objetivo de
propósito** — para não depender de quem está com pressa.

**Bancada → Integração**
- `pytest -q` verde;
- **E2E de navegador verde** — ele sobe o próprio servidor a partir do
  código atual, então prova o **código**, e por isso é critério daqui e não
  do estágio seguinte (corrigido em 31/08: a primeira versão deste documento
  colocava o E2E como critério de Integração, errado);
- nenhum `xfail` citando achado da fase corrente;
- nenhuma linha da fase em "SEM PROVA" no `ACEITE.md`;
- tag criada (ver abaixo).

**Integração → Homologação**
- migrations aplicadas, `alembic current` no head;
- `confirmar.sh` **15 OK / 0 FALHA**;
- **smoke**: o serviço sobe, o login responde, e as telas-chave carregam.

O que se prova aqui é **o deploy**, não o código — o código já foi provado
na bancada. Rodar o fluxo completo contra um servidor compartilhado
significaria criar e abandonar projetos nele a cada ciclo.

**Homologação → Produção**
- o Marcelo percorreu o fluxo na tela e aprovou;
- `confirmar.sh` 15/0;
- a lista de defeitos conhecidos do candidato está escrita e aceita — um
  fluxo quebrado conhecido não impede a subida, mas **não pode subir sem
  alguém ter decidido que sobe**.

## Deploy por tag, não por `git pull main`

Hoje não há como responder "o que está rodando em homologação?" sem entrar no
servidor e olhar o `git log`. Passa a valer:

- toda implantação sai de uma **tag** (`v2026.08.31-1`, `-2`, …);
- o servidor faz checkout da tag, não `pull` de `main`;
- rollback é fazer checkout da tag anterior;
- a tag é criada na bancada, depois de a suíte passar, e **nunca** movida.

Isso muda o trabalho da Vera: o fim de um ciclo passa a ser "suíte verde +
tag criada", não "commitado".

Caso real: Produção saiu da esteira três dias antes desta regra existir
(`git checkout main` manual em 28/08, marco em 31/08) e ninguém percebeu
por 7 dias. Diagnóstico completo e o que fazer no rebuild — inclusive um
achado que não tem a ver com estar fora da tag — em `IMPLANTAR.md`,
`### Produção — diagnóstico de 04/09 e o que fazer quando reconstruir`.

## Teste fora da rodada padrão apodrece

Um teste que só roda quando alguém lembra de invocá-lo é da mesma família do
`logging.warning` que ninguém lê. Se um teste precisa ficar fora do
`pytest -q`, o problema é o isolamento dele — resolva o isolamento, não a
convocação. O E2E de navegador ganha banco próprio (`orizon_e2e`) por essa
razão.

E todo teste que abre banco **afirma o nome do banco antes de qualquer
coisa**, recusando rodar se não for o dele. Em 31/08 um `DATABASE_URL`
esquecido na sessão fez o E2E escrever registros órfãos no banco de dev.

## Ninguém edita código em servidor

Servidor recebe checkout e migration. Correção feita direto num servidor não
existe na bancada, some no deploy seguinte, e reaparece como fantasma.

## Paridade

A bancada roda PostgreSQL 18 e a produção roda 16. **A bancada desce para
16.** Já custou uma armadilha documentada (`SET transaction_timeout` no
dump PG18→PG16, ver `IMPLANTAR.md`). Ambiente de desenvolvimento que não
espelha produção mente, e este já mentiu.

**Exceção deliberada: o TZ do sistema operacional.** Desde o ACHADO-48
(02/09), o fuso da competência contábil é configuração
(`Loja.config_financeira_json['fuso_horario']`, resolvida por
`mod_contabil.agora_no_fuso`) — **nunca** o relógio/TZ do processo ou da
máquina. Isso significa que Integração/Homologação (`Etc/UTC`) e Produção
(`America/Sao_Paulo`) rodarem em fusos DIFERENTES deixou de ser dívida de
paridade e virou um canário: qualquer regressão que volte a ler
`date.today()`/`datetime.utcnow()` num caminho de regra de negócio (em vez
de `agora_no_fuso`/`hoje_no_fuso`) tende a se comportar diferente entre
Integração/Homologação e Produção, e falhar em teste ANTES de chegar no
cliente — exatamente o inverso do que aconteceu da primeira vez (a bancada
com TZ local expôs o defeito; um servidor em UTC o escondia). **Não
uniformizar o TZ dos três servidores** — é o que resta pra costurar essa
rede, deliberadamente.

**A bancada também tem banco, e ele fica para trás.** A esteira carimba os
servidores e, até 04/09, não dizia nada sobre o banco de aplicação da bancada.
Medido nesse dia: os três ambientes rodavam o MESMO código
(`v2026.09.04-beta1`), mas o banco `orizon` local estava em `f47f22de46a7` —
duas migrations atrás (`82275b998a4a`, ACHADO-47, e `b0ecb9ce82d2`,
ACHADO-30), ambas de 03/09. Ficou dois dias assim sem ninguém notar porque **a
suíte monta o próprio schema**: `pytest -q` fica verde com o banco de aplicação
desatualizado, e quem quebra é só o app aberto na tela — justamente o percurso
manual, que é o último a acontecer. Por isso o fechamento do deploy passou a
incluir a bancada: ver `IMPLANTAR.md`, `## Conferir o que esta rodando`.

## Acesso remoto à bancada

Recomendação: **rede privada** (Tailscale, WireGuard). Não abrir porta.
A bancada tem o repositório, as chaves e o histórico; expô-la à internet
para ganhar mobilidade é troca ruim.

## O que a esteira não resolve

Ela disciplina a passagem. Não substitui a suíte, não substitui o
`confirmar.sh` e não substitui alguém olhando a tela. Foi exatamente uma
tela não olhada que produziu o ACHADO-25 e o ACHADO-26, com 2466 testes
verdes.
