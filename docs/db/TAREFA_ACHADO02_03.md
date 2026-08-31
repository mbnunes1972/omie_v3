# Passo 10 do ROTEIRO — o que cada ramo faz com o `cust_fin`

Último conserto da Fase 1. Os ACHADOS 02 e 03 foram fundidos: vivem em
`_fin_provisoes_venda_seguro` e são a mesma decisão — o 02 é a consequência,
o 03 é o roteador que a produz.

## A tabela, decidida em 30/08 (não reabrir)

`cust_fin = Val_Cont − VAVO` é **o preço do crédito cobrado do cliente**.
`4.1.01` recebe **o VAVO em todos os ramos** — o preço do móvel não muda
conforme a forma de pagamento.

| ramo | `cust_fin` vai para |
|---|---|
| à vista | não existe |
| `loja` | **receita financeira** (a loja ficou com ele) |
| `loja_antecipacao` | **receita financeira** também; o deságio que o banco retém na antecipação é custo **separado**, no evento da antecipação |
| `financeira` / cartão | **nada no resultado** — vira **retenção esperada**, posição de balanço |

## Atenção: a tabela que existe no código está errada

`_RAMO_CFIN_EVENTO` (mod_contabil.py:1655) manda `financeira` e
`loja_antecipacao` para o mesmo evento de custo provisionado. O ACHADO-03
foi registrado como "`if` diverge da tabela" — **a medição da decisão mostrou
que nenhum dos dois estava certo**. Não conserte fazendo main.py:749 chamar
a tabela: **a tabela também muda.**

## A retenção esperada — por que fica, e o que ela não é

Pedido do usuário, e é uma necessidade real: no fechamento o sistema prevê a
retenção (10% de R$ 200.000 = R$ 20.000); ao passar o cartão o banco retém
9% = R$ 18.000; os R$ 2.000 de diferença têm que aparecer para o assistente
financeiro conferir. Pode ocorrer o contrário, por tabela desatualizada.

**Ela fica. Mas não é despesa.** Com `4.1.01` recebendo o VAVO, a receita já
nasce líquida da retenção; lançá-la também como custo subtrai duas vezes.
Ela é posição de balanço que abate o recebível:

- recebível contra o cliente/financeira: Val_Cont
- retenção esperada: `cust_fin`
- líquido esperado = VAVO = a receita

**A variância vai para uma conta só, nos dois sentidos** — sobra e falta na
mesma conta, sinais opostos. É a regra que o próprio usuário já decidiu para
os impostos (`_PROV_DESTINO_VARIANCIA`: `2.1.04.13 → 4.3.01`), com a mesma
justificativa: mandar sobra para uma conta e falta para outra infla receita
em vez de corrigir.

## O ACHADO-01 é respondido aqui

A pergunta mais antiga da auditoria — *o que liquida a provisão de custo
financeiro?* — tem resposta: **o evento de conferência**, quando a retenção
real chega. `financeira`: liquidação do cartão. `loja_antecipacao`:
antecipação bancária.

Isso **não** faz o ACHADO-01 sair do roteiro (ele é o passo 12, Fase 2), mas
o conserto dele deixa de ser desenho em aberto. Se a estrutura que este
passo criar já entregar a liquidação de graça, diga — o passo 12 encolhe.

## O nome

"Provisão de Custo Financeiro" descreve uma despesa que, no ramo financeira,
não existe. O que existe é retenção esperada de terceiro. É o quinto lugar
onde a regra 4 do plano aparece. Renomeie a conta para o que ela faz — e
confira, como no `total_flex`, se algum identificador de tela ou API depende
do nome antigo antes de trocar.

## Aceites

Escreva antes do conserto:

1. **`4.1.01` recebe o VAVO nos quatro ramos** — quatro cenários, mesma
   venda, mesma receita de vendas. É o aceite que prova a decisão inteira.
2. **Ramo loja:** `cust_fin` aparece uma vez, como receita financeira.
   Receita de vendas + receita financeira = Val_Cont, sem duplicar (ACHADO-02).
3. **Ramo financeira:** nenhum lançamento de despesa financeira; a retenção
   esperada existe como posição e o líquido esperado é o VAVO.
4. **Conferência, os dois sentidos:** retenção real menor que a esperada
   (R$ 18.000 contra R$ 20.000) e maior (R$ 21.000 contra R$ 20.000) caem na
   **mesma conta**, com sinais opostos.
5. **`loja_antecipacao` no fechamento é igual a `loja`** — receita
   financeira, não custo. O custo do banco só existe no evento da
   antecipação.

Os xfails do ACHADO-02 e do ACHADO-03 saem no mesmo commit, incluindo os
cenários por ramo da bateria.

## O que NÃO fazer

- Não lançar a retenção esperada como despesa.
- Não mandar sobra e falta para contas diferentes.
- Não fazer main.py:749 simplesmente chamar `_RAMO_CFIN_EVENTO` — a tabela
  muda junto.
- Não mexer no ACHADO-23 (passo 11).
