# Aceite — como saber que um achado foi mesmo consertado

Criado em 29/08/2026, a pedido do usuário: *"você está registrando cada item
para que façamos um teste completo depois que confirme que todas as correções
estão funcionando?"*

**Resposta honesta: em parte.** Os 22 achados estão documentados e o plano
está ordenado, mas a **prova** de conserto só existe para alguns. Este
arquivo é o índice que faltava — e o valor dele está nas linhas vazias, não
nas preenchidas.

---

## O mecanismo

Um achado provado é um teste com `xfail(strict=True)` que descreve o
comportamento errado de hoje. Quando o conserto entra, o teste passa a
passar; `strict=True` faz o XPASS **quebrar a suíte**, obrigando quem
consertou a remover o marcador. Ninguém consegue consertar em silêncio, e
ninguém consegue declarar consertado sem evidência.

**A regra:** nenhum achado é dado por resolvido sem o teste dele verde e o
`xfail` removido no mesmo commit.

Um achado **sem teste** é um achado que pode ser declarado consertado sem
que nada prove — e é exatamente o que precisa ser escrito antes do conserto,
não depois.

---

## O índice

| achado | o que erra | prova hoje | estado |
|---|---|---|---|
| 01 | provisão de custo financeiro nunca liquidada | `test_ciclo_completo_por_ramo` (2 xfails strict), `test_bateria_ciclo` (cenários com custo financeiro), `test_fase_d_reconciliacao`, `test_provisoes_impostos_custo_financeiro` | **provado** |
| 02 | receita financeira contada duas vezes no ramo loja | `test_bateria_ciclo` (`_XFAILS`, ramo loja) | **provado** |
| 03 | ramo roteado por `if` num lugar e por tabela em outro | citado em comentário de `test_bateria_ciclo`, **sem xfail próprio** | **SEM PROVA** |
| 04 | — resolvido | `test_eventos`, `test_fase_b2_eventos` | fechado |
| 05 | — resolvido | `test_eventos`, `test_partida_dobrada` | fechado |
| 06 | reclassificação de Outros Fornecedores | — | **SEM PROVA** (medir antes) |
| 07 | 2º escape hatch manual sem validação | — | **SEM PROVA** |
| 08 | — artefato de medição, não é defeito | — | fechado |
| 09 | `5.3.01` usada por dois mecanismos | — | **SEM PROVA** (é nome, não número) |
| 10 | `_fin_evento_seguro` código morto | `test_pdv_visao_unificada` | fechado |
| 11 | docstring de `conciliar_final` | — | fechado (documental) |
| 12 | aditivo não é faturado nem cobrado | `test_bateria_ciclo` (cenários `tem_aditivo`), `test_aditivo_costuras` | **provado** |
| 13 | `faturar_segmento` não é delta-aware na receita | `test_aditivo_costuras::test_costura2_...` (strict) | **provado** |
| 14 | — resolvido (rename Parcelamento Loja) | `test_ramo_financiamento` | fechado |
| 15 | `real` × `competencia_estimada` nunca reconciliam | `test_dre_ciclo_completo_e2e` (strict) | **provado** |
| 16 | provisão cancelada em silêncio → margem fictícia | — | **SEM PROVA — e é o mais grave da auditoria** |
| 17 | Retenção de Comissão: nome ≠ comportamento | — | **SEM PROVA** (decisão de produto pendente) |
| 18 | NF-e sem `valor_total` | `test_failsoft_nfe_medicao` (guarda do comportamento atual) | medido; guarda decidida, **não implementada** |
| 19 | seis rotas respondem `ok` a recálculo falho | `test_fail_soft_medicao2`, `test_negociacao_breakdown_excecoes` | medido; **conserto sem teste** |
| 20 | recursão no complemento auto-referente | `test_negociacao_breakdown_excecoes` | medido |
| 21 | aditivo cobrado duas vezes | `test_aditivo_costuras::test_costura4_...` (strict, hoje citando o 12) | **provado** — corrigir a citação para ACHADO-21 |
| 22 | docstring do CMV descreve mecanismo extinto | — | documental, Grupo 5 |
| P5 | `parcela_ambiente.valor_ambiente` | — | **SEM PROVA** |

---

## O que este índice mostra

**Os quatro buracos que importam:**

1. **ACHADO-16 não tem teste.** É o achado mais grave da auditoria — o que
   produziu o projeto com receita de 90.000 e custo zero —, tem conserto
   decidido, e nada hoje viraria verde quando ele for consertado. **Escrever
   este teste antes do conserto é a próxima coisa a fazer no Grupo 1.**
2. **ACHADO-03 não tem xfail próprio**, só menção em comentário.
3. **ACHADO-19 e 18 têm testes de MEDIÇÃO, não de aceite.** Os testes provam
   o que o sistema faz hoje; nenhum vira verde quando o conserto entrar. Para
   esses dois, o aceite precisa ser escrito junto com o conserto.
4. **ACHADO-21 usa a citação do 12.** Mesmo teste, achado errado no motivo —
   quando o 12 for consertado alguém vai remover o marcador achando que
   fechou os dois.

**O que fazer com isso:** antes de consertar qualquer item do Grupo 1,
escrever o `xfail(strict=True)` que o prova. Depois do Grupo 1 inteiro, a
verificação completa é uma coisa só: **rodar a suíte e não sobrar nenhum
xfail citando achado do Grupo 1.** Se sobrar, o conserto não fechou; se algum
XPASS quebrar a suíte, o conserto fechou e o marcador está velho.

## Manutenção

Toda vez que um achado entrar, sair ou ganhar teste, esta tabela muda no
mesmo commit. Uma tabela de aceite desatualizada é pior que nenhuma — ela
afirma cobertura que não existe.
