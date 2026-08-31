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
- nenhum `xfail` citando achado da fase corrente;
- nenhuma linha da fase em "SEM PROVA" no `ACEITE.md`;
- tag criada (ver abaixo).

**Integração → Homologação**
- migrations aplicadas, `alembic current` no head;
- `confirmar.sh` **15 OK / 0 FALHA**;
- E2E do fluxo terminal verde contra o servidor de Integração.

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

## Ninguém edita código em servidor

Servidor recebe checkout e migration. Correção feita direto num servidor não
existe na bancada, some no deploy seguinte, e reaparece como fantasma.

## Paridade

A bancada roda PostgreSQL 18 e a produção roda 16. **A bancada desce para
16.** Já custou uma armadilha documentada (`SET transaction_timeout` no
dump PG18→PG16, ver `IMPLANTAR.md`). Ambiente de desenvolvimento que não
espelha produção mente, e este já mentiu.

## Acesso remoto à bancada

Recomendação: **rede privada** (Tailscale, WireGuard). Não abrir porta.
A bancada tem o repositório, as chaves e o histórico; expô-la à internet
para ganhar mobilidade é troca ruim.

## O que a esteira não resolve

Ela disciplina a passagem. Não substitui a suíte, não substitui o
`confirmar.sh` e não substitui alguém olhando a tela. Foi exatamente uma
tela não olhada que produziu o ACHADO-25 e o ACHADO-26, com 2466 testes
verdes.
