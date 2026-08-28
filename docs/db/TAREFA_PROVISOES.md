# Tarefa — provisoes de Impostos e Custo Financeiro

Baseada no relatorio de 28/08/2026. Decisao 1 ja esta no codigo; 2, 3 e 4
nao estao.

## Principio que organiza tudo
O problema nao e' que essas duas provisoes precisam de tratamento especial.
E' que nunca receberam o tratamento que as outras 15 rubricas ja tem: um
evento `reconhecimento_despesa_*` roteando a variancia para a conta da
propria rubrica. Ficaram de fora e caem na "rota antiga"
(sobra->4.4.02, falta->5.6.10).

Custo Financeiro entra no padrao sem exceção — e' custo, grupo 5.
Imposto usa o mesmo padrao com destino em outro grupo, porque imposto nao
e' custo: e' deducao de receita.

## 1. Guarda no endpoint  (nao depende de decisao, faca primeiro)
`POST /api/financeiro/resolver-saldo-provisao` aceita qualquer codigo de
conta. Restrinja as contas de provisao legitimas e recuse o resto com erro
explicito. Hoje da' para chamar com qualquer codigo e cair na rota 5.6.10.

## 2. Custo Financeiro (2.1.04.19) -> conta de despesa da propria rubrica
Decisao do Marcelo, 28/08/2026. Crie o evento
`reconhecimento_despesa_*` correspondente, como as outras 15. A variancia
deixa de passar pela rota antiga.

## 3. Imposto (2.1.04.13) -> 4.3.01, NOS DOIS SENTIDOS
Decisao do Marcelo (P4). Imposto sobre venda e' parcela da receita que
nunca foi da empresa.

IMPORTANTE, e a decisao original nao cobria isso: a rota antiga manda
**sobra para 4.4.02** (outras receitas). Se a falta vai para 4.3.01, a
sobra tem que voltar para 4.3.01 tambem — mesma conta, sinal contrario,
deduzindo menos. Mandar sobra para 4.4.02 infla receita em vez de corrigir
deducao, e os dois lados da mesma variancia acabam em contas diferentes.

## 4. 5.6.10 deixa de ser destino implicito
`resolver_saldo_provisao` nunca deve rotear para 5.6.10 por falta de
alternativa. Se uma rubrica chegar la sem destino definido, **falhe com
erro nomeando a rubrica** em vez de gravar em silencio. 5.6.10 passa a ser
so' destino explicito, para diferenca sem origem identificavel.

E quando for usada de proposito: alerta no momento da escrita, na propria
funcao contabil — nao so' o alerta de saldo que ja existe na tela.

## 5. Fechamento do projeto — PROPONHA, nao implemente
`conciliar_final` exclui explicitamente {2.1.04.13, 2.1.04.19} da resolucao
automatica. O Marcelo definiu que o ajuste e' feito no pagamento, por acao
do assistente administrativo — entao o caminho manual e' o mecanismo certo.

Mas isso significa que um projeto pode fechar com provisao em aberto, em
silencio, se ninguem executar o ajuste. O principio declarado dele foi:
"o lancamento da provisao obriga o reconhecimento ajustado".

Traga uma proposta de como o fechamento deveria se comportar quando essas
provisoes ainda tem saldo — recusar, avisar, listar — com o custo de cada
opcao. Nao implemente antes de eu decidir.

## Testes
Cada item acima precisa de teste. E' dinheiro; leitura de codigo nao basta.
Em particular: hoje nenhum teste cobre o branch "falta" para essas duas
contas, nem referencia 4.3.01 como destino de variancia. A suite atual
testa e valida o comportamento pre-decisao — ou seja, ela esta protegendo o
que queremos mudar. Ajuste esses testes de proposito, com comentario
dizendo qual decisao mudou o esperado.

## Ordem
1 (guarda) -> 4 (parar de rotear para 5.6.10) -> 2 e 3 (destinos certos) ->
5 (proposta). O item 4 antes do 2 e 3 de proposito: com ele no lugar,
qualquer rubrica sem destino definido aparece como erro em vez de sumir na
conta de ajustes.
