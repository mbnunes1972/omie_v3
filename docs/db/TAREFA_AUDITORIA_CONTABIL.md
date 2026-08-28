# Tarefa — auditoria das pontas abertas do plano de contas

Levantamento COMPLETO antes de consertar qualquer coisa. Tres achados do
mesmo formato apareceram em 28/08 (schema x migrations, gabarito x
bootstrap, custo financeiro x recebivel). Consertar um de cada vez foi o
que produziu isso. Queremos todas as pontas na mesa de uma vez.

**NAO IMPLEMENTE NENHUM CONSERTO.** Esta tarefa produz mapa, testes e
relatorio. Os consertos vem depois, decididos em conjunto.

Pode levar horas. O Marcelo vai estar ausente; profundidade vale mais que
rapidez aqui.

---

## Parte 1 — o mapa: evento x conta x sentido

Derive DO CODIGO (nunca de memoria nem de documento): para cada funcao
contabil e cada entrada de EVENTOS_CONTABEIS, registre

    evento | funcao | conta | sentido (D/C) | contrapartida | condicional?

Cubra tudo que escreve em `lancamento`, incluindo os caminhos manuais por
endpoint. Se uma contrapartida for implicita, calculada em outro lugar, ou
ausente, marque como tal — e' precisamente o que procuramos.

Entregue como tabela ordenada por conta.

## Parte 2 — as pontas, derivadas do mapa

Do mapa acima, extraia cada categoria abaixo com a evidencia (arquivo:linha):

1. **Conta com um sentido so'.** Algo constitui e nada baixa, ou o
   contrario. Foi assim que 2.1.04.19 ficou parada enquanto o ativo drenava.
2. **Par constituido junto com drenagem assimetrica.** Duas contas que
   nascem no mesmo lancamento mas tem numero diferente de caminhos de baixa.
3. **Estimativa sem reconciliacao.** Valor de face (previsto, estimado)
   usado como se fosse realizado, sem codigo que feche a diferenca depois.
4. **Conta do PLANO_PADRAO que nenhum evento toca.** Nao e' bug, mas quero
   saber — pode ser conta morta ou funcionalidade nao implementada.
5. **Evento que grava em conta fora do PLANO_PADRAO.** Se existir, e' bug.
6. **Lancamento sem contrapartida explicita** no mesmo escopo transacional.

Suspeitos ja conhecidos, para ancorar — mas NAO limite a busca a eles:
1.1.01, 1.1.02, 1.1.06.19, 1.1.07, 2.1.01, 2.1.04.13, 2.1.04.19,
4.3.01, 4.4.02, 5.5.03, 5.5.04, 5.6.10.

## Parte 3 — teste de partida dobrada, por funcao

Para CADA funcao que escreve em `lancamento`: teste que afirma
`soma(debitos) == soma(creditos)` no escopo daquela chamada.

E' o teste mais barato do conjunto e o que pega a classe inteira de
lancamento pela metade.

## Parte 4 — teste de ciclo completo, por ramo

O que teria pego o achado de hoje sozinho. Um teste por ramo financeiro
(`loja`, `loja_antecipacao`, `financeira`), percorrendo o ciclo inteiro:
venda, contrato, provisoes, NF-e, recebimento, fechamento.

Ao final, afirme:
- **o balancete fecha**: soma de debitos == soma de creditos no periodo;
- **as contas transitorias do projeto estao zeradas**: provisoes, ativos
  diferidos, contas a receber daquele projeto;
- qualquer saldo remanescente e' **reportado com nome da conta e valor** —
  a mensagem de falha precisa dizer QUAL conta ficou aberta e quanto, nao
  so' que algo falhou.

**Onde o ciclo nao fechar hoje, use `pytest.mark.xfail` com `reason`
citando o achado correspondente** (ex.: "ACHADO-01: recebimento liquido de
venda antecipada nao reconcilia"). Assim a suite fica verde, as lacunas
ficam registradas no codigo, e quem consertar uma delas ve o xfail virar
"unexpected pass" — que e' o aviso de que o conserto funcionou e o marcador
pode sair.

Nao invente conserto para fazer o ciclo fechar. Um xfail honesto vale mais.

## Parte 5 — relatorio consolidado

`docs/db/ACHADOS_CONTABEIS.md`, com numeracao estavel (ACHADO-01,
ACHADO-02...), e para cada um:

- o que acontece, em uma frase;
- evidencia com arquivo:linha;
- as duas ou tres consequencias concretas no numero final;
- o que bloqueia (se bloqueia algo);
- a decisao que precisa ser tomada antes do conserto — formulada como
  pergunta objetiva, nao como recomendacao.

Incorpore o achado da reconciliacao de venda antecipada como ACHADO-01: a
investigacao ja esta feita, so' falta entrar no formato.

Ordene por consequencia no numero final, nao por facilidade de conserto.

## Ao terminar
Suite completa verde (com os xfail marcados), commit e push. Traga o
relatorio consolidado e o mapa da Parte 1.
