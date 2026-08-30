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
| 03 | ramo roteado por `if` num lugar e por tabela em outro | `test_aceite_achado03::test_ramo_loja_antecipacao_diverge_do_dict_canonico` (strict, divergência reproduzida com `ramo_financeiro="loja_antecipacao"` — controle negativo confirmado) | **provado** |
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
| 16 | provisão cancelada em silêncio → margem fictícia | `test_aceite_achado16::test_conciliacao_final_recusa_com_provisao_nunca_efetivada` (strict — aceite da recusa) + `test_aceite_achado16::test_mecanismo_hoje_cancela_saldo_sem_tocar_5101` (medição do mecanismo, verde hoje e depois) | **provado (a recusa)** — controle negativo confirmado (XPASS quebrou a suíte); o aceite dos vereditos (efetivada/encerrada com valor menor/não se aplica/ainda vai chegar) nasce com a implementação do passo 8, cobrindo a regra das duas pernas (efetivar pelo valor real, só então reverter o resíduo) |
| 17 | Retenção de Comissão: nome ≠ comportamento | — | **SEM PROVA** (decisão de produto pendente) |
| 18 | NF-e sem `valor_total` | `test_failsoft_nfe_medicao` (medição) + `test_aceite_achado18::test_gerar_contrato_recusa_valor_total_zero` e `::test_emitir_nfe_recusa_valor_total_zero` (strict, estado construído direto no banco com pré-condição afirmada, controle negativo confirmado nos dois) | **provado** |
| 19 | seis rotas respondem `ok` a recálculo falho | `test_fail_soft_medicao2`, `test_negociacao_breakdown_excecoes` (medição) + `test_aceite_achado19_20::test_parametros_json_malformado_cai_no_default` e `::test_parametros_nao_devolve_sombra_com_recalculo_falho` (strict, controle negativo confirmado nos dois — cobrem 2 das 3 causas; o conserto das 4 rotas restantes segue sem aceite) | parcialmente **provado** |
| 20 | recursão no complemento auto-referente | `test_negociacao_breakdown_excecoes` (medição) + `test_aceite_achado19_20::test_complemento_auto_referente_recusado_com_erro_nomeado` (strict, controle negativo confirmado) | **provado** |
| 21 | aditivo cobrado duas vezes | `test_aditivo_costuras::test_costura4_...` (strict, citação corrigida em 30/08) | **provado** |
| 22 | docstring do CMV descreve mecanismo extinto | — | documental, Grupo 5 |
| P5 | `parcela_ambiente.valor_ambiente` | — | **SEM PROVA** |

---

## O que este índice mostra

**Os quatro buracos que importam:**

1. ~~ACHADO-16 não tem teste.~~ **Resolvido (30/08)** — `test_aceite_achado16.py`
   prova a recusa do fechamento (`xfail(strict=True)`, controle negativo
   confirmado) e mede o mecanismo de cancelamento silencioso (verde hoje e
   depois). Falta só o teste dos vereditos, que nasce com o passo 8.
2. ~~ACHADO-03 não tem xfail próprio~~ **Resolvido (30/08)** —
   `test_aceite_achado03.py` reproduz a divergência com números (ramo
   "loja_antecipacao" cai no evento errado), controle negativo confirmado.
3. ~~ACHADO-19 e 18 têm testes de MEDIÇÃO, não de aceite~~ **Parcialmente
   resolvido (30/08)** — `test_aceite_achado18.py` (2 aceites: contrato e
   NF-e) e `test_aceite_achado19_20.py` (2 das 3 causas do 19: `parametros_
   json` malformado e `/parametros` sem `sombra`; a 3ª causa do 19 —
   `complemento_pe`/ACHADO-20 — também provada no mesmo arquivo) escritos,
   `xfail(strict=True)`, controle negativo confirmado em todos. Falta aceite
   para as 4 rotas restantes do ACHADO-19 (das 6 originais).
4. ~~ACHADO-21 usa a citação do 12~~ **Corrigido (30/08)** — citação trocada
   para ACHADO-21 em `test_costura4_...`; `test_costura2_...` também estava
   citando o 12 por engano e foi corrigida para ACHADO-13.

**O que fazer com isso:** antes de consertar qualquer item do Grupo 1,
escrever o `xfail(strict=True)` que o prova. Depois do Grupo 1 inteiro, a
verificação completa é uma coisa só: **rodar a suíte e não sobrar nenhum
xfail citando achado do Grupo 1.** Se sobrar, o conserto não fechou; se algum
XPASS quebrar a suíte, o conserto fechou e o marcador está velho.

## Manutenção

Toda vez que um achado entrar, sair ou ganhar teste, esta tabela muda no
mesmo commit. Uma tabela de aceite desatualizada é pior que nenhuma — ela
afirma cobertura que não existe.
