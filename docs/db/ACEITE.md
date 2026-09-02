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
| 25 | tela do aditivo nunca envia forma de pagamento — ninguém completa pela UI | `test_e2e_browser_conciliacao_final.py` (achado de UI — a prova é de NAVEGADOR, não de HTTP: gera o Termo Aditivo, assina loja, assina cliente — a assinatura que completa o par abre o modal de pagamento novo e a assinatura só se registra depois de confirmado) | **CONSERTADO** — F2-4 do ROTEIRO |
| 26 | Conciliação Final não manda veredito — trava, ou contorna via "Resolver" sem auditoria | `test_aceite_fila_provisoes.py` (7 aceites: desvio recusado + projeto não conclui por ele; os 4 vereditos pela fila isolados; controle positivo — Impostos continua funcionando pelo desvio; fluxo completo — fila → conclusão → custo em 5.1.01) | **CONSERTADO** — F2-3 do ROTEIRO |
| 27 | plano de pagamento longo (15x) colapsa o card de ambientes na tela de Negociação — botões Salvar/Aprovar/Imprimir inclicáveis | `test_e2e_browser_negociacao_layout.py` (achado de layout CSS, não de HTTP — a prova é de NAVEGADOR: projeto real, Cartão de Crédito 15x, mede `getBoundingClientRect().height` do card > 100px e clica de verdade nos três botões, não só `is_visible()`) | **CONSERTADO** |
| 28 | CPF de assinatura sem validação de dígito verificador (contrato, aprovação do PE, solicitação de medição) | `test_aceite_achado28.py` (6 aceites — CPF inválido recusado com 400 nomeando a parte, sem avançar o status; CPF válido passa, controle positivo — nos três caminhos, interno e webhook ClickSign via captura de `ValueError` na reconciliação) | **CONSERTADO** — só dígito; conferir contra o cadastro é LP-02 (`docs/db/LISTA_PARALELA.md`) |
| 32 | guarda do F2-3 entrou no servidor (409), a tela da Conciliação Final continuou oferecendo Efetivar/Resolver em toda linha | `test_aceite_conciliacao_ui_item1.py` (flag `exige_veredito` derivada de `_PROV_FORA_DO_VEREDITO`, controle negativo movendo um código pra dentro da constante) + `test_e2e_browser_conciliacao_ui.py` (navegador — os três estados de linha batidos contra o JSON real do endpoint, tooltips do item 3, selo/toast do item 2) + `test_e2e_browser_ciclo_overlay.py` (navegador — item 4, Ciclo aberto esconde a negociação por baixo, `.modal-overlay` continua visível) | **CONSERTADO** — corrigido 01/09: selo desacoplado da rota (não mistura "Na Fila" com o fato do dinheiro), exige movimento real pra "Resolvida", toast do razão + aviso de idempotência no Efetivar |
| 33 | conserto do 32 tirou o Efetivar de rubrica de veredito nomeado (Montagem/Fábrica não têm outro alimentador) | `test_e2e_browser_conciliacao_ui.py` (navegador — linha de Montagem, 2.1.04.02, sem alimentador, com Efetivar habilitado e Resolver ausente; controle negativo removendo Efetivar de toda rubrica de veredito nomeado) | **CONSERTADO** — a restrição da Fila é sobre Resolver, nunca sobre Efetivar; eventos mortos (`execucao_montagem`/`pagamento_fabrica`) ligar-ou-remover é LP-11 (`docs/db/LISTA_PARALELA.md`) |
| 34 | `conciliar_final` exige veredito pelo saldo, não pela decisão — quem zera antes do fechamento atravessa a exigência (`mod_folha`/2.1.04.12 é o caso real) | — | **SEM PROVA** — movido da LP-12 pra fila ativa da Fase 2 em 01/09 (era adiamento, virou próximo passo do roteiro); não trava a Conciliação Final hoje (saldo já zerado antes de chegar lá), mas fica sem veredito registrado |
| 35 | idempotência de `efetivar_provisao` (chave valor+dia) recusa a SEGUNDA efetivação legítima do mesmo dia; antes do item 3 do ACHADO-32, recusava em silêncio dizendo "Efetivado" | `test_aceite_achado35.py` (2 aceites HTTP — valor igual e valor diferente, ambos pedem confirmação, ambos lançam 2 lançamentos com `ref` distintos, `total_hoje` sempre do razão via `efetivado_no_dia`) + `test_e2e_browser_conciliacao_ui.py` (navegador — Custo Financeiro, cancelar não lança nada, confirmar lança e soma 800,00); controle negativo — `main.py`+`mod_contabil.py` revertidos, os 3 testes falham | **CONSERTADO** 02/09 (B1) — recusa virou confirmação, `ref` sequencial dentro do dia |
| 36 | `showToast(..., true)` — recusa/erro do módulo financeiro/provisões passava pelo `mostrarErroModal` manuscrito, fora do design system, em vez de `avisoPopup` | `test_aceite_achado36.py` (estrutural — zero `showToast(..., true)` na faixa do módulo, contagem total do sistema = 164 — antes 200 — e aceite de navegador: `abrirReconciliacaoProjeto()` sem projeto mostra o `avisoPopup` do design system, nunca o `#erro-modal-overlay`); controle negativo — revertida a conversão de um chamador, os 3 testes falham | **CONSERTADO** 02/09 (B2) — 36 chamadas convertidas no módulo financeiro/provisões; 164 restam no resto do sistema (higiene, LP a abrir) |
| 38 | `peConciliacaoAprovar` (frontend) e `POST /ciclo/11d/aprovar` (backend) validavam credencial antes de checar estado — não existia sequer um "AF2 já aprovada" explícito, `_set_etapa_status` sobrescrevia sem olhar o status anterior | `test_aceite_achado38.py` (HTTP — segunda aprovação com senha ERRADA de propósito recusa pelo ESTADO [400 "já aprovada"], nunca pela senha [403] — prova a ORDEM; só um `LogAcaoGerencial` mesmo com 2 chamadas — e navegador — estado mockado `concluido`, `peConciliacaoAprovar()` nunca abre o modal de credenciais); controle negativo em ambas as pontas (backend revertido → 403 em vez de 400; frontend revertido → modal de credenciais abre), as duas falham | **CONSERTADO** 02/09 (B3) — estado (11d já concluído, checagem nova) antes da credencial nas duas pontas; 24 outros chamadores de `pedirCredenciaisGerente` enumerados, nenhum com o mesmo padrão (checam formulário ou pedem confirmação de consequência, não "já concluído") |
| 39 | `_peConcValidasPorSinal` escolhia os botões de decisão pelo sinal de Δ CUSTO de fábrica; a decisão é sobre Δ A COBRAR/ESTORNAR — ambiente com Δ a cobrar zero exigia decisão e bloqueava `fase.completa` mesmo assim | medido antes de mexer: 4 linhas reais em homologação ("Absorver R$ 0,00", projetos Teste_1/Teste_2, Δ custo 793.75/76.27, Δ a cobrar 0) — nenhuma apagada; `test_aceite_achado39.py` (aceite — Δ a cobrar 0 com Δ custo ≠ 0 não é mais pendência, AF2 aprova sem exigir decisão do ambiente; controle positivo — Δ a cobrar ≠ 0 continua pendência normal); controle negativo — revertido, o aceite falha, o controle positivo continua passando | **CONSERTADO** 02/09 (B4) — frontend usa Δ a cobrar; backend ganhou `decisao_e_necessaria` + helper único (`_pe_ambientes_pendentes_decisao`) reaproveitado nos 3 lugares que calculavam `ambientes_com_pe` (GET, `/ciclo/11d/aprovar` e o PATCH genérico — irmão achado ao revisar); `decisao_valida`/sinal de Δ custo no backend não tocado (regra de 2026-08-14, fora do pedido) |
| 40 | célula decidida da coluna Decisão (AF2) era flex livre — rótulo/valor/botão desalinhavam entre linhas conforme o comprimento do texto; link azul de navegador na Fila (fora de escopo) | `test_aceite_achado40.py` — prova por CAPTURA (screenshot real salvo em disco) + bounding box da sub-coluna de valor nas duas linhas ("Manter"/R$100 vs "Estornar"/R$123.456,78); controle negativo — revertido, markup antigo não tem as sub-colunas, teste falha | **PARCIALMENTE CONSERTADO** 02/09 (B5) — sub-colunas de largura fixa (rótulo 64px, valor 90px mono à direita); link azul NÃO tocado — pertence ao redesenho da Parte A (botão "Resolver" volta), fora desta rodada por decisão do Marcelo |
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
