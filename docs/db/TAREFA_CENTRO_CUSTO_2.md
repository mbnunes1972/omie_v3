# Tarefa 2 — correcoes apos as duas investigacoes

## 1. Nome de 1.1.09 e 2.1.09  (residuo confirmado)
Migration NOVA. Nao edite a c1ab3f8007c4: ela ja esta aplicada no localhost
e o downgrade e declaradamente irreversivel.

- Renomeia para "Creditos com Empresas (conta corrente)" e "Debitos com
  Empresas (conta corrente)" em TODOS os owners onde ainda estiver o nome
  antigo. Idempotente.
- Docstring explica por que o CONTA_NOME_OVERRIDE_POR_OWNER_TIPO da seed
  virou letra morta, para ninguem tentar "consertar" a seed depois.
- Criterio: apos o upgrade, os 3 owners tem o mesmo nome, e o teste de
  comparacao localhost x construido continua com zero diferencas.

REGRA NOVA para o CLAUDE.md: rename de conta do plano padrao vai em
migration, nunca numa lista _RENOMEIA_* no codigo. seed_plano() so cria o
que falta — por desenho — entao rename feito la nunca alcanca base
existente. Foi assim que este residuo nasceu.

## 2. Loja nova sem classificacao  (bug, bloqueia)
Hoje: arvore e plano tem seed-on-first-access; a classificacao do grupo 5
depende de migrar_classificacao_grupo5_v1, que roda so no boot e so para
owner que ja tem linha em `conta` naquele instante. Loja criada em runtime
fica com o grupo 5 em NULL ate reiniciar o servidor.

Faca UMA funcao de gabarito: dado um owner, garante arvore de centro de
custo + plano de contas + classificacao. Idempotente.

- Chamada na CRIACAO da loja (POST /api/admin/lojas e .../pdvs), para a
  loja nascer utilizavel em vez de esperar alguem visitar uma tela.
- Mantida tambem no seed-on-first-access, como rede de seguranca.
- migrar_classificacao_grupo5_v1 deixa de ser o unico caminho; avalie
  aposenta-la junto com as outras entradas boot-only de _migrar_colunas_pg.
- Teste: cria loja nova pela API e afirma que o grupo 5 tem
  centro_custo_id e natureza_custo preenchidos, SEM reboot.

## 3. P3 — decidido: so gabarito propaga
- Os nos do gabarito nascem em todo owner, pela funcao do item 2.
- No criado pela tela fica no owner que o criou.
- Quando quem cria e admin de rede, a tela oferece "aplicar a todas as
  lojas da rede" como acao explicita — nunca automatica.
- Registre a decisao no documento de decisoes e feche o P3.

## 4. O gabarito em dois lugares  (o mais importante)
PLANO_PADRAO (mod_contabil.py) e a copia dentro da c1ab3f8007c4 descrevem
a mesma coisa. Se divergirem, uma loja criada pela tela passa a ter plano
diferente do de um ambiente reconstruido, e a diferenca so aparece num
relatorio que nao fecha meses depois.

Escreva um teste que compara os dois: o gabarito que a migration semeia
tem que ser exatamente o que PLANO_PADRAO produz — mesmos codigos, mesmos
nomes, mesma arvore de centro de custo. Se alguem acrescentar conta a um
lado so, o teste fica vermelho no mesmo dia.

Esse teste vale mais que os itens 1 a 3: eles corrigem tres defeitos, ele
fecha a classe.

## Ordem
4 primeiro (o teste vai nascer vermelho ou verde e ja diz onde estamos),
depois 1, depois 2, depois 3. Relatorio antes de commitar.

## 5. A migration de gabarito nao pode enumerar owners  (BLOQUEIA a implantacao)

Medido nos servidores em 28/08/2026:

    ambiente        alembic_version   owners                    nos/owner
    localhost       bf43dd02888b      rede,1 loja,1 loja,3            16
    integracao      NAO EXISTE        loja,1                          17
    homologacao     NAO EXISTE        rede,1/15/16 loja,1/29..34      17

Nenhum servidor tem Alembic — os tres estao como antes da revisao. Os 17
contra 16 do localhost sao a Producao Propria, que a 0004 removeu so aqui.
Sem duplicata em lugar nenhum: 17 nos, 17 nomes distintos, por owner.

O problema: a c1ab3f8007c4 conhece tres owners fixos (rede,1 / loja,1 /
loja,3). Na Integracao so existe loja,1 — ela criaria arvore e 160 contas
para rede,1 e loja,3, que NAO EXISTEM ali. O owner e polimorfico
(owner_tipo + owner_id), nao ha FK protegendo: as linhas entrariam sem
erro, apontando para lojas inexistentes. Na Homologacao, alem disso,
oito owners reais ficariam sem nada.

### O que fazer
A migration de gabarito NAO enumera owners. Deriva do proprio banco: para
cada linha em `redes` e cada linha em `lojas` do ambiente de destino,
garante arvore de centro de custo + plano de contas + classificacao.

Assim ela fica correta em qualquer ambiente sem saber nada sobre ele:
3 owners no localhost, 1 na Integracao, 10 na Homologacao.

E e a MESMA funcao de gabarito do item 2: a migration chama para todos os
owners existentes, a criacao de loja chama para o owner recem-criado. Uma
implementacao, dois pontos de entrada.

A c1ab3f8007c4 ja esta aplicada no localhost e o downgrade e irreversivel:
isso vai em migration NOVA, que roda o gabarito derivado. No localhost ela
nao muda nada — os 3 owners ja estao corretos — e o criterio continua sendo
zero diferencas contra o localhost.

### Teste
Construa o banco de teste do zero, insira duas lojas e uma rede que NAO
existem no localhost, rode a migration, e afirme que os cinco owners tem o
gabarito completo. E o que prova que ela funciona onde a lista fixa falharia.
