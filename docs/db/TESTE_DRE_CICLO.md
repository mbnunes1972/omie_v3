# Teste — as três visões de DRE, ciclo completo

## Por que este teste existe

O módulo Financeiro/DRE tem três visões: `real`, `competencia_estimada` e
`antecipacao_contrato`. Precisamos renomeá-las e possivelmente remover uma,
mas **não dá para renomear antes de saber o que cada uma faz de fato**.

O que a leitura de código já estabeleceu:

- `modo='real'` chama `dre()`, cuja docstring diz "DRE societário
  (competência) a partir do livro". **Não é fluxo de caixa** — apesar de o
  pedido original ter sido que refletisse o caixa. O nome não descreve o
  comportamento.
- `competencia_estimada` e `antecipacao_contrato` chamam `dre_simulada()`
  com modos diferentes.

**A hipótese a medir:** `real` e `competencia_estimada` estão tentando ser a
mesma coisa — uma apurada do livro, a outra por simulação. Se for verdade,
elas têm que dar o mesmo número, e uma é redundante. Se derem números
diferentes, a diferença é defeito mensurável, na simulação ou no livro.

Renomear antes de responder isso seria carimbar nome novo sobre dúvida — o
que já produziu o "Total Flex" e a "Retenção de Comissão".

## O que fazer

Um ciclo completo, do nascimento do projeto à conclusão, com retrato das
três visões em cada marco.

### Reaproveite o que existe
- O driver de cenário de `tests/test_ciclo_completo_por_ramo.py`.
- Para assinaturas: o caminho que `tests/test_contrato_assinatura_clicksign_e2e.py`
  já usa.
- Para NF-e: o caminho de `tests/test_nfe_emitir_teste_e2e.py` /
  `test_nfe_etapa15_e2e.py`.

**Não invente atalho para passar pelos portões.** Use os caminhos que a
suíte já exercita — o teste tem que percorrer o código de verdade, senão
mede outra coisa. Nenhuma chamada externa real (ClickSign, Focus NF-e).

### O percurso
1. Criação do projeto (pelo caminho real — isto também exercita a questão
   do registro em `Projeto`)
2. Orçamento e negociação
3. Fechamento da venda / contrato — constituição das provisões
4. Assinaturas (1ª e 2ª)
5. Revisão de PE **com aditivo**
6. Emissão de NF-e — faturamento e efetivação de impostos
7. Recebimento
8. Entrega e conclusão do projeto

### Em CADA marco, registre
**As três visões**, sobre a mesma janela, **linha a linha** — receita bruta,
deduções, receita líquida, CMV/CSP, lucro bruto, despesas comerciais,
administrativas, constituição de provisões, EBITDA, resultado financeiro,
outras receitas, lucro líquido.

Total igual não prova nada: dois erros podem se cancelar. É a linha que
denuncia.

**E os saldos das contas-chave**: `1.1.02`, `1.1.05`, `1.1.06.19`, `2.1.03`,
`2.1.06`, `2.1.04.13`, `2.1.04.19`, `4.1.01`, `4.3.01`, `4.4.03`.

Isso mostra o mecanismo, não só o resultado — e é o que permite dizer
*onde* duas visões se separam.

## O que asserir e o que só observar

**ASSERIR:** `real` e `competencia_estimada` dão o mesmo número, linha a
linha, na mesma janela. Se falhar, a mensagem tem que dizer **qual linha,
qual valor em cada uma, e em qual marco a diferença apareceu pela primeira
vez** — o marco importa mais que o valor, porque diz qual evento causou.

**SÓ OBSERVAR, não asserir:** a `antecipacao_contrato`. Ela reconhece no
contrato, então diverge das outras por desenho, não por defeito. Registre os
números para leitura; qualquer asserção de igualdade aqui estaria errada.

## O que reportar

1. `real` e `competencia_estimada` batem? Se não, a primeira linha e o
   primeiro marco em que divergem.
2. A tabela das três visões por marco, linha a linha.
3. Os saldos das contas-chave por marco.
4. Qualquer portão que exigiu tratamento especial para o ciclo não parar —
   se algum exigiu, é informação sobre o fluxo, não só sobre o teste.

Se as duas baterem, o rename fica trivial e uma delas sai. Se não baterem,
temos um defeito medido e a decisão muda.
