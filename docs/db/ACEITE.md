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
| 01 | provisão de custo financeiro nunca liquidada | `conferir_retencao_financeira` (mod_contabil.py) + `test_aceite_achado02_03::test_aceite4_...` (dois sentidos, mesma conta) + `test_resultado_financeiro::test_conferir_retencao_financeira_cancela_par_sem_dre` | **PARCIALMENTE CONSERTADO** — passo 10 (ramo financeira; falta só o gatilho HTTP/conferência manual — loja_antecipacao fechado por completo) |
| 02 | receita financeira contada duas vezes no ramo loja | `test_aceite_achado02_03::test_aceite1_...`/`test_aceite2_...` + `test_ciclo_completo_por_ramo::test_ramo_loja_receita_total_conta_o_custo_financeiro_uma_vez_so` (era `xfail`-free medição, agora fecha certo) + `test_bateria_ciclo` (23 cenários, nenhum xfail) | **CONSERTADO** — passo 10 do ROTEIRO |
| 03 | ramo roteado por `if` num lugar e por tabela em outro | `test_aceite_achado03::test_ramo_loja_antecipacao_usa_o_mesmo_evento_do_dict_canonico` (`xfail` removido no commit do conserto — main.py e o dict concordam) + `test_aceite_achado02_03::test_aceite5_...` | **CONSERTADO** — passo 10 do ROTEIRO |
| 04 | — resolvido | `test_eventos`, `test_fase_b2_eventos` | fechado |
| 05 | — resolvido | `test_eventos`, `test_partida_dobrada` | fechado |
| 06 | reclassificação de Outros Fornecedores | — | **SEM PROVA** (medir antes) |
| 07 | 2º escape hatch manual sem validação | — | **SEM PROVA** |
| 08 | — artefato de medição, não é defeito | — | fechado |
| 09 | `5.3.01` usada por dois mecanismos | — | **SEM PROVA** (é nome, não número) |
| 10 | `_fin_evento_seguro` código morto | `test_pdv_visao_unificada` | fechado |
| 11 | docstring de `conciliar_final` | — | fechado (documental) |
| 12 | aditivo não é faturado nem cobrado | `test_aceite_achado12` (2 aceites: 2.1.06 zera, seleção explícita do orçamento) + `test_bateria_ciclo` (cenários `tem_aditivo` saíram do xfail, herdam ACHADO-01/02 por ramo como os demais) | **CONSERTADO** — passo 7 do ROTEIRO |
| 13 | `faturar_segmento` não é delta-aware na receita | `test_aditivo_costuras::test_costura2_...` (`xfail` removido no commit do conserto, 30/08) + `test_mov_credor_liquido_estorno` (medição do ponto 2, líquido de estornos) | **CONSERTADO** — primeiro conserto da jornada |
| 14 | — resolvido (rename Parcelamento Loja) | `test_ramo_financiamento` | fechado |
| 15 | `real` × `competencia_estimada` divergem de meio de ciclo | `test_dre_ciclo_completo_e2e` (`xfail` removido 31/08 — divergência de meio de ciclo é o modelo, decisão de 07/08; reconcilia no fechamento) | **APOSENTADO** (31/08) — não é defeito |
| 16 | provisão cancelada em silêncio → margem fictícia | `test_aceite_achado16.py` (recusa sem veredito + `encerrada_valor_menor` reconhecendo custo real antes de reverter, via HTTP) + `test_fase_d2_conciliacao_final.py` (sem veredito recusa, sobra+falta com veredito, `nao_se_aplica` sem motivo recusa, `ainda_vai_chegar` mantém aberto, custo financeiro fora da regra, idempotência) + `test_relatorio_projetos_encerrados_por_reversao.py` (ordenação por valor revertido, motivo, endpoint) | **CONSERTADO** — passo 8 do ROTEIRO |
| 17 | Retenção de Comissão: nome ≠ comportamento | — | **SEM PROVA** (decisão de produto pendente) |
| 18 | NF-e sem `valor_total` | `test_failsoft_nfe_medicao` (medição) + `test_aceite_achado18.py` (recusa em contrato e NF-e, `xfail` removido no commit do conserto, 30/08 + `test_emitir_nfe_passa_com_aditivo_assinado_positivo_mesmo_com_contrato_zerado`, o caso do total contratado) | **CONSERTADO** — passo 9 do ROTEIRO |
| 19 | seis rotas respondem `ok` a recálculo falho | `test_fail_soft_medicao2`, `test_negociacao_breakdown_excecoes` (medição) + `test_aceite_achado19_20::test_parametros_json_malformado_cai_no_default` e `::test_parametros_nao_devolve_sombra_com_recalculo_falho` (strict, controle negativo confirmado nos dois — cobrem 2 das 3 causas; o conserto das 4 rotas restantes segue sem aceite) | parcialmente **provado** |
| 20 | recursão no complemento auto-referente | `test_negociacao_breakdown_excecoes` (medição) + `test_aceite_achado19_20::test_complemento_auto_referente_recusado_com_erro_nomeado` (strict, controle negativo confirmado) | **provado** |
| 21 | aditivo cobrado duas vezes | `test_aditivo_costuras::test_costura4_...` (`xfail` removido no commit do conserto, 30/08) + `test_valor_contratado_do_projeto`, `test_aditivo_recebiveis_e_custo_financeiro` | **CONSERTADO** — passo 6 do ROTEIRO (6-a/6-b/6-c) |
| 22 | docstring do CMV descreve mecanismo extinto | — | documental, Grupo 5 |
| 23 | segmentação não congelada silenciosamente (falha engolida na assinatura) | `test_aceite_achado23.py` (4 aceites: recusa por injeção nomeando o projeto, reparo na AF1, controle positivo sem ruído, assinatura completa nos dois casos — confirmado que os dois primeiros falham pelo motivo certo contra o código pré-conserto) | **CONSERTADO** — passo 11 do ROTEIRO |
| 24 | aditivo/contrato com plano de pagamento vazio não gera cobrança | `test_aceite_achado24.py` (2 `xfail(strict=True)`, um por chamador de `_materializar_recebiveis_venda_seguro`, + 2 controles positivos — `xfail` removido no commit do conserto, 31/08) | **CONSERTADO** — F2-1 do ROTEIRO |
| 25 | tela do aditivo nunca envia forma de pagamento — ninguém completa pela UI | — | **SEM PROVA** (achado de UI, não de HTTP; enfileirado, não consertado) |
| 26 | Conciliação Final não manda veredito — trava, ou contorna via "Resolver" sem auditoria | — | **SEM PROVA** (achado de UI, F2-2; enfileirado, não consertado) |
| P5 | `parcela_ambiente.valor_ambiente` | — | **SEM PROVA** |

---

## O que este índice mostra

**Os quatro buracos que importam:**

1. ~~ACHADO-16 não tem teste.~~ **CONSERTADO (30/08, passo 8)** — a Conciliação
   Final recusa sem veredito nomeado; os quatro vereditos e o relatório de
   reversões estão implementados e provados (ver índice acima).
2. ~~ACHADO-03 não tem xfail próprio~~ **Resolvido (30/08)** —
   `test_aceite_achado03.py` reproduz a divergência com números (ramo
   "loja_antecipacao" cai no evento errado), controle negativo confirmado.
3. ~~ACHADO-19 e 18 têm testes de MEDIÇÃO, não de aceite~~ **18 CONSERTADO
   (30/08, passo 9)** — a guarda de `valor_total`/total contratado entrou em
   contrato e NF-e, os dois `xfail(strict=True)` do passo 4 saíram.
   **19 parcialmente resolvido (30/08)** — `test_aceite_achado19_20.py` (2
   das 3 causas: `parametros_json` malformado e `/parametros` sem `sombra`;
   a 3ª causa — `complemento_pe`/ACHADO-20 — também provada no mesmo
   arquivo), `xfail(strict=True)`, controle negativo confirmado em todos.
   Falta aceite para as 4 rotas restantes do ACHADO-19 (das 6 originais).
4. ~~ACHADO-21 usa a citação do 12~~ **Corrigido (30/08)** — citação trocada
   para ACHADO-21 em `test_costura4_...`; `test_costura2_...` também estava
   citando o 12 por engano e foi corrigida para ACHADO-13.

**O que fazer com isso:** antes de consertar qualquer item do Grupo 1,
escrever o `xfail(strict=True)` que o prova. Depois do Grupo 1 inteiro, a
verificação completa é uma coisa só: **rodar a suíte e não sobrar nenhum
xfail citando achado do Grupo 1.** Se sobrar, o conserto não fechou; se algum
XPASS quebrar a suíte, o conserto fechou e o marcador está velho.

## Um padrão que apareceu três vezes (e mais no passo 10)

Todo conserto até agora quebrou pelo menos um teste vizinho que **codificava
o defeito como correto**: `test_cancelar_nfe_estorna_faturamento` (passo 5),
`test_aditivo_lista_api` (passo 6), `test_custos_adicionais_provisao`
(passo 8), `test_ciclo_completo_ramo_loja`/as trocas de ramo de
`test_resultado_financeiro.py` (passo 10 — `4.1.01==Val_Cont` e
`financeira↔loja_antecipacao` no-op eram exatamente o ACHADO-02/03).

Não é descuido de quem escreveu — é o efeito natural de escrever teste sobre
comportamento observado. Mas cria uma armadilha: **um teste verde não
significa comportamento certo, significa comportamento estável.**

A regra, então: quando um conserto quebra um teste vizinho, há duas
hipóteses — o conserto está errado, ou o teste codificava o defeito. **Diga
qual, e por quê.** Nunca conserte o teste para ele continuar verde sem
responder isso.

## Manutenção

Toda vez que um achado entrar, sair ou ganhar teste, esta tabela muda no
mesmo commit. Uma tabela de aceite desatualizada é pior que nenhuma — ela
afirma cobertura que não existe.
