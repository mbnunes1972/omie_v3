# Tarefa — fechar centros de custo e plano de contas

## Contexto
A cadeia de migrations foi colapsada numa baseline unica
(0001_baseline_orizon_one.py). O localhost e a referencia: 480 contas,
48 nos de centro de custo, 3 owners (1 rede, 2 lojas).

O gabarito — a arvore de centro_custo, e os campos conta.centro_custo_id e
conta.natureza_custo — existe hoje SO porque foi gravado uma vez pelo
bootstrap do servidor. Nao esta em migration nenhuma. Um ambiente
construido pela baseline nasce com a estrutura certa e o plano de contas
vazio. Isso e o que bloqueia a reconstrucao de Integracao, Homologacao e
Producao.

## O que fazer
Uma migration de dado idempotente que produz a arvore de centros de custo
e a classificacao das contas exatamente como estao hoje no localhost.

### Regras
1. NENHUM id numerico no codigo da migration. Ids diferem entre ambientes.
   Case por chave natural: owner + codigo da conta; owner + nome + pai para
   o no de centro de custo.
2. Idempotente nos dois sentidos: num banco vazio semeia, num banco que ja
   tem a arvore reorganiza. Rodar duas vezes nao pode duplicar nem falhar.
3. Distinga criar de atualizar, e diga na docstring qual bloco faz o que.
   Onde a classificacao decidida difere do gravado, atualize; onde a conta
   nao existe, crie.
4. GERE o conteudo a partir do banco, nao digite a mao. Sao 48 nos e a
   classificacao de dezenas de contas — transcricao manual erra.
5. downgrade(): se nao for reversivel de forma util, escreva isso na
   docstring em vez de fingir que e.
6. NAO inclua dado de instancia — redes, lojas, emitente, usuarios,
   perfis, credenciais de integracao. Esse continua saindo por
   pg_dump (ver docs/db/RESTAURAR.md). So gabarito entra em migration.

### Criterio de aceitacao
O mesmo metodo do B2, agora aplicado a dado:

1. Construa orizon_baseline_teste do zero:
       psql "<url do teste>" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
       DATABASE_URL="<url do teste>" alembic upgrade head
2. Compare `conta` e `centro_custo` linha a linha contra o localhost.
   Compare por ATRIBUTO NATURAL, nunca por id — os ids serao diferentes e
   uma coincidencia de sequence nao prova nada.
   Para conta: owner, codigo, nome, natureza, tipo, natureza_custo, e o
   caminho do centro de custo (nome do no + nome do pai), nao o id.
   Para centro_custo: owner, nome, nome do pai.
3. ZERO diferencas. Traga o diff.
4. O mesmo criterio virando teste no pytest, para nao depender de alguem
   lembrar de rodar isso a mao.

## Verificar de passagem
P3 (replicacao automatica de nos entre owners ao criar centro de custo pela
tela) esta marcado como resolvido no documento de decisoes, mas o texto da
resolucao fala da revisao vazia 963a92661333 — e marcador trocado.
Confirme se P3 continua aberto e reporte.

## Depois desta
Parte B — provisoes de impostos e custo financeiro. Antes de mexer,
reporte o que o codigo faz hoje: houve um mapeamento para remover essas
provisoes e a decisao foi revertida, e o estado atual e desconhecido.
Decidido: as duas provisoes ficam; o ajuste no pagamento; a variancia de
imposto vai para 4.3.01 (deducao de receita), nao 5.6.10; e 5.6.10 =
Ajustes de Reconciliacao, nunca destino padrao e com alerta quando usada.
