# Relatório — três visões de DRE, ciclo completo (pós-Fase 1)

Gerado por `tests/test_dre_ciclo_completo_e2e.py`. `real` e `competencia_estimada` reconciliam no fechamento do projeto; divergem durante o ciclo por desenho (ver Diagnóstico). `antecipacao_contrato` é só observada — ela diverge por desenho (reconhece no contrato, não na NF-e), não é achado.

Este arquivo é a remedição de docs/db/TAREFA_REMEDICAO_DRE.md, comparada
marco a marco e conta a conta contra o relatório original,
`docs/db/RELATORIO_DRE_CICLO.md` (não sobrescrito — a diferença entre os
dois arquivos é o resultado). `diff` entre os dois mostra que **só o marco
`8_conclusao_projeto` mudou**; todos os demais, incluindo os que já
divergiam antes, são byte a byte idênticos.

**Nota para quem regenerar este arquivo:** `_gravar_relatorio` reescreve o
arquivo inteiro a cada execução do teste e apaga esta seção de
diagnóstico — se rodar o teste de novo, reaplique este bloco (do início
até "## Marco: 1_projeto_criado") por cima do resultado novo antes de
descartar o anterior.

## Diagnóstico

### 1. Onde está a primeira divergência agora

Continua no mesmo lugar de antes: o marco `6a_nfe_produto_emitida`. `real`
mostra `cmv_csp = 0.00`; `competencia_estimada` mostra `42000.00` (o CFO da
provisão). A receita é idêntica nas duas visões nesse marco
(`receita_bruta = 61750.00` em ambas) — a divergência é só de custo, exatamente
como no relatório original. **Fase 1 não moveu esse ponto**, e essa
divergência agora é tratada como esperada, não como falha (ver "Veredito
sobre o xfail" abaixo).

### 2. O projeto ainda fecha com margem de 100%?

**Não.** No relatório original, o marco `8_conclusao_projeto` fechava com
`lucro_liquido = 95000.00` sobre `receita_bruta = 95000.00` — 100% de
margem, o sintoma que abriu a auditoria. Neste relatório, o mesmo marco
fecha com `lucro_liquido = 53000.00` sobre a mesma receita de `95000.00`
(≈ 55,8% de margem) — **idêntico ao que `competencia_estimada` sempre
mostrou**, porque `cmv_csp` em `real` agora também fecha em `42000.00`
(antes: `0.00`). `lucro_bruto` e `ebitda` seguem o mesmo padrão. Essas são
as únicas quatro linhas que mudaram em todo o arquivo (ver `diff` acima).

### 3. O que a `2.1.06` faz com o aditivo

`2.1.06` (Receita a Realizar) **não fica presa** — nem no relatório
original nem neste: `95000.00` (5c) → `33250.00` (6a, baixa parcial pela
NF-e de produto) → `0.00` (6b, baixa total pela NFS-e de serviço) → `0.00`
(7) → `0.00` (8). Idêntica nos dois relatórios. Se o passo 7 resolveu algo
aqui, já estava resolvido antes desta remedição — Fase 1 não alterou essa
trajetória.

A conta que **fica presa em R$ 5.000,00 para sempre** a partir do
recebimento é `1.1.02` (Contas a Receber), não `2.1.06`: `95000.00` (6a/6b)
→ `5000.00` (7) → `5000.00` (8), nos dois relatórios.

**Causa confirmada por leitura de código (Marcelo perguntou: caminho novo
do passo 6-c, ou caminho antigo?):** o fixture EXERCITA o passo 6-c — a
assinatura que completa o aditivo (marco 5c) envia
`forma_pagamento = {"tipo": "avista", "total_cliente": 0}`, satisfazendo a
exigência do endpoint (não é rejeitado) — mas esse payload não tem
`parcelas` nem `entrada_valor`. `mod_recebiveis.materializar` (linhas
59-110) nunca lê `total_cliente`; ela gera linhas a partir de
`entrada_valor` e de `pag["parcelas"]` apenas. Sem nenhum dos dois, o
`for` sobre `parcelas` roda 0 vezes e **nenhum `Recebivel` é criado** para
os R$ 5.000,00 do complemento — só os R$ 90.000,00 do contrato original
(que tem `parcelas` reais) geram `Recebivel`. O marco 7 confirma todo
`Recebivel` do projeto; como o complemento nunca teve um, ele nunca é
"recebido" — daí o 1.1.02 parar em 5.000,00 e nunca zerar.
**Conclusão: é artefato do fixture, não achado** — o caminho novo (passo
6-c) funciona; o teste é que descreve um plano de pagamento vazio para o
complemento. `_materializar_recebiveis_venda_seguro` não acusa isso porque
seu guard de log só dispara quando `forma_pagamento` está TOTALMENTE
ausente (main.py:844-851) — aqui ela está presente, só vazia de parcelas.
Essa lacuna no aviso é real, mas não altera nenhum número de produção;
não abri achado novo para ela.

### 4. A `4.1.01` mudou de valor?

**Não** — `61750.00` nos dois relatórios, em todos os marcos onde a conta
existe. Isso é esperado, não uma falha: o cenário usa forma de pagamento
`avista`, sem custo financeiro, então VAVO (Valor à Vista) e Val_Cont
(valor contratual cheio) coincidem — não há o que o ajuste do passo 10
segmentar aqui. Para observar `4.1.01` divergir seria preciso um cenário
com parcelamento e custo financeiro embutido.

## O que mudou no teste para ele rodar pós-Fase 1

O passo 8 (ACHADO-16) mudou a Conciliação Final: `POST
/ciclo/21/conciliar` agora exige um `veredito` nomeado por rubrica de
provisão em aberto (exceto Impostos/Custo Financeiro, guarda do
ACHADO-01). O corpo vazio `{}` que o teste enviava antes passou a ser
recusado (`400`, "falta veredito para 2.1.04.06"). A única rubrica aberta
neste cenário mínimo era `2.1.04.06` (Custo de Fábrica) — o teste agora
envia:

```json
{"vereditos": {"2.1.04.06": {"veredito": "encerrada_valor_menor", "valor_efetivado": 42000.0}}}
```

**Por quê `encerrada_valor_menor` com `valor_efetivado = 42000.0`, e não
outro veredito:** um XML de fábrica real foi enviado e uma NF-e real foi
emitida contra ele — `nao_se_aplica` (alegar que o custo nunca se aplicou)
seria falso e reproduziria exatamente o problema que o ACHADO-16 existe
para impedir. `ainda_vai_chegar` manteria o projeto aberto para sempre e
impediria o teste de alcançar o marco 8. `42000.0` é o saldo constituído
inteiro de `2.1.04.06` neste ponto — confirmado empiricamente, porque
`resolver_veredito_provisao` rejeita (`ValueError`) um `valor_efetivado`
maior que o saldo aberto, e a chamada não levantou erro. Essa escolha —
reconhecer o custo total no fechamento — é o que muda o resultado da
pergunta 2 acima: **o veredito, não uma mudança na lógica de `real()`, é
o que fecha a lacuna.**

## `competencia_estimada` ainda aparece?

Sim, nas três visões capturadas em todo marco, sem mudança de forma —
continua sendo a visão que sempre mostrou o custo estimado da venda desde
a criação da provisão, independente de efetivação.

## Veredito sobre o xfail (ACHADO-15) — APOSENTADO 31/08/2026

Medição inicial (mesmo dia): as três visões não reconciliavam em todo
marco — divergiam em `6a_nfe_produto_emitida`, `6b_nfse_servico_emitida` e
`7_recebimento`, só fechando em `8_conclusao_projeto`. Pela leitura
estrita da tarefa ("se as visões reconciliarem [em todo marco], remova o
marcador"), isso mantinha o `xfail(strict=True)`.

**Decisão de Marcelo, confirmada por releitura do código:** divergir
durante o ciclo é o MODELO, não o defeito — decisão de 07/08
(mod_contabil.py:1826-1832): a despesa entra em `real()` só na competência
REAL da efetivação, nunca antes; `competencia_estimada` é projeção por
desenho (mostra o constituído) e sai inteira na Fase 4. Um `xfail` sobre
comportamento intencional não mede nada — só documenta uma expectativa
errada.

**Verificação antes de aposentar:** todas as divergências de meio de
ciclo, em todos os marcos, se resumem a uma única causa —
`cmv_csp`/`lucro_bruto`/`ebitda`/`lucro_liquido` (as três últimas são só a
cascata aritmética da primeira). Nenhuma outra linha (`receita_bruta`,
`deducoes`, `despesas_comerciais`, `despesas_administrativas`,
`constituicao_provisoes`, `resultado_financeiro`, `outras_receitas`)
diverge em nenhum marco. Não há divergência sem explicação pelo desenho.

**Ação:** `xfail(strict=True)` removido de
`test_ciclo_completo_tres_visoes_dre`. A asserção mudou de "bate em todo
marco" para "bate no marco `8_conclusao_projeto`" — divergências de meio
de ciclo continuam capturadas e reportadas (variável
`divergencias_meio_ciclo` no teste), só não fazem o teste falhar. Teste
roda **PASSED** (confirmado por execução direta, não `--runxfail`).
ACHADO-15 marcado **RESOLVIDO/APOSENTADO** em
docs/db/ACHADOS_CONTABEIS.md — decisão tomada, não bug pendente.

## Marco: 1_projeto_criado

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 0.00 | 0.00 | 0.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 0.00 | 0.00 | 0.00 | sim |
| cmv_csp | 0.00 | 0.00 | 0.00 | sim |
| lucro_bruto | 0.00 | 0.00 | 0.00 | sim |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 0.00 | 0.00 | 0.00 | sim |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 0.00 | 0.00 | 0.00 | sim |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | (não existe) |
| 1.1.05 | (não existe) |
| 1.1.06.19 | (não existe) |
| 2.1.03 | (não existe) |
| 2.1.06 | (não existe) |
| 2.1.04.13 | (não existe) |
| 2.1.04.19 | (não existe) |
| 4.1.01 | (não existe) |
| 4.3.01 | (não existe) |
| 4.4.03 | (não existe) |

## Marco: 2_negociacao_preview

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 0.00 | 0.00 | 0.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 0.00 | 0.00 | 0.00 | sim |
| cmv_csp | 0.00 | 0.00 | 0.00 | sim |
| lucro_bruto | 0.00 | 0.00 | 0.00 | sim |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 0.00 | 0.00 | 0.00 | sim |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 0.00 | 0.00 | 0.00 | sim |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | (não existe) |
| 1.1.05 | (não existe) |
| 1.1.06.19 | (não existe) |
| 2.1.03 | (não existe) |
| 2.1.06 | (não existe) |
| 2.1.04.13 | (não existe) |
| 2.1.04.19 | (não existe) |
| 4.1.01 | (não existe) |
| 4.3.01 | (não existe) |
| 4.4.03 | (não existe) |

## Marco: 3_contrato_gerado

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 0.00 | 0.00 | 0.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 0.00 | 0.00 | 0.00 | sim |
| cmv_csp | 0.00 | 0.00 | 0.00 | sim |
| lucro_bruto | 0.00 | 0.00 | 0.00 | sim |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 0.00 | 0.00 | 0.00 | sim |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 0.00 | 0.00 | 0.00 | sim |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | (não existe) |
| 1.1.05 | (não existe) |
| 1.1.06.19 | (não existe) |
| 2.1.03 | (não existe) |
| 2.1.06 | (não existe) |
| 2.1.04.13 | (não existe) |
| 2.1.04.19 | (não existe) |
| 4.1.01 | (não existe) |
| 4.3.01 | (não existe) |
| 4.4.03 | (não existe) |

## Marco: 4a_assinatura_loja

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 0.00 | 0.00 | 0.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 0.00 | 0.00 | 0.00 | sim |
| cmv_csp | 0.00 | 0.00 | 0.00 | sim |
| lucro_bruto | 0.00 | 0.00 | 0.00 | sim |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 0.00 | 0.00 | 0.00 | sim |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 0.00 | 0.00 | 0.00 | sim |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | (não existe) |
| 1.1.05 | (não existe) |
| 1.1.06.19 | (não existe) |
| 2.1.03 | (não existe) |
| 2.1.06 | (não existe) |
| 2.1.04.13 | (não existe) |
| 2.1.04.19 | (não existe) |
| 4.1.01 | (não existe) |
| 4.3.01 | (não existe) |
| 4.4.03 | (não existe) |

## Marco: 4b_assinatura_cliente_provisoes_constituidas

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 0.00 | 0.00 | 90000.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 0.00 | 0.00 | 90000.00 | sim |
| cmv_csp | 0.00 | 0.00 | 40000.00 | sim |
| lucro_bruto | 0.00 | 0.00 | 50000.00 | sim |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 0.00 | 0.00 | 50000.00 | sim |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 0.00 | 0.00 | 50000.00 | sim |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | 90000.00 |
| 1.1.05 | 0.00 |
| 1.1.06.19 | 0.00 |
| 2.1.03 | 0.00 |
| 2.1.06 | 90000.00 |
| 2.1.04.13 | 0.00 |
| 2.1.04.19 | 0.00 |
| 4.1.01 | 0.00 |
| 4.3.01 | 0.00 |
| 4.4.03 | 0.00 |

## Marco: 5a_aditivo_criado

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 0.00 | 0.00 | 90000.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 0.00 | 0.00 | 90000.00 | sim |
| cmv_csp | 0.00 | 0.00 | 40000.00 | sim |
| lucro_bruto | 0.00 | 0.00 | 50000.00 | sim |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 0.00 | 0.00 | 50000.00 | sim |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 0.00 | 0.00 | 50000.00 | sim |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | 90000.00 |
| 1.1.05 | 0.00 |
| 1.1.06.19 | 0.00 |
| 2.1.03 | 0.00 |
| 2.1.06 | 90000.00 |
| 2.1.04.13 | 0.00 |
| 2.1.04.19 | 0.00 |
| 4.1.01 | 0.00 |
| 4.3.01 | 0.00 |
| 4.4.03 | 0.00 |

## Marco: 5b_aditivo_assinatura_loja

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 0.00 | 0.00 | 90000.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 0.00 | 0.00 | 90000.00 | sim |
| cmv_csp | 0.00 | 0.00 | 40000.00 | sim |
| lucro_bruto | 0.00 | 0.00 | 50000.00 | sim |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 0.00 | 0.00 | 50000.00 | sim |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 0.00 | 0.00 | 50000.00 | sim |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | 90000.00 |
| 1.1.05 | 0.00 |
| 1.1.06.19 | 0.00 |
| 2.1.03 | 0.00 |
| 2.1.06 | 90000.00 |
| 2.1.04.13 | 0.00 |
| 2.1.04.19 | 0.00 |
| 4.1.01 | 0.00 |
| 4.3.01 | 0.00 |
| 4.4.03 | 0.00 |

## Marco: 5c_aditivo_assinatura_cliente_provisoes_constituidas

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 0.00 | 0.00 | 90000.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 0.00 | 0.00 | 90000.00 | sim |
| cmv_csp | 0.00 | 0.00 | 42000.00 | sim |
| lucro_bruto | 0.00 | 0.00 | 48000.00 | sim |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 0.00 | 0.00 | 48000.00 | sim |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 0.00 | 0.00 | 48000.00 | sim |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | 95000.00 |
| 1.1.05 | 0.00 |
| 1.1.06.19 | 0.00 |
| 2.1.03 | 0.00 |
| 2.1.06 | 95000.00 |
| 2.1.04.13 | 0.00 |
| 2.1.04.19 | 0.00 |
| 4.1.01 | 0.00 |
| 4.3.01 | 0.00 |
| 4.4.03 | 0.00 |

## Marco: 6a_nfe_produto_emitida

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 61750.00 | 61750.00 | 90000.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 61750.00 | 61750.00 | 90000.00 | sim |
| cmv_csp | 0.00 | 42000.00 | 42000.00 | **NÃO** |
| lucro_bruto | 61750.00 | 19750.00 | 48000.00 | **NÃO** |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 61750.00 | 19750.00 | 48000.00 | **NÃO** |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 61750.00 | 19750.00 | 48000.00 | **NÃO** |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | 95000.00 |
| 1.1.05 | 0.00 |
| 1.1.06.19 | 0.00 |
| 2.1.03 | 0.00 |
| 2.1.06 | 33250.00 |
| 2.1.04.13 | 0.00 |
| 2.1.04.19 | 0.00 |
| 4.1.01 | 61750.00 |
| 4.3.01 | 0.00 |
| 4.4.03 | 0.00 |

## Marco: 6b_nfse_servico_emitida

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 95000.00 | 95000.00 | 90000.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 95000.00 | 95000.00 | 90000.00 | sim |
| cmv_csp | 0.00 | 42000.00 | 42000.00 | **NÃO** |
| lucro_bruto | 95000.00 | 53000.00 | 48000.00 | **NÃO** |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 95000.00 | 53000.00 | 48000.00 | **NÃO** |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 95000.00 | 53000.00 | 48000.00 | **NÃO** |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | 95000.00 |
| 1.1.05 | 0.00 |
| 1.1.06.19 | 0.00 |
| 2.1.03 | 0.00 |
| 2.1.06 | 0.00 |
| 2.1.04.13 | 0.00 |
| 2.1.04.19 | 0.00 |
| 4.1.01 | 61750.00 |
| 4.3.01 | 0.00 |
| 4.4.03 | 0.00 |

## Marco: 7_recebimento

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 95000.00 | 95000.00 | 90000.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 95000.00 | 95000.00 | 90000.00 | sim |
| cmv_csp | 0.00 | 42000.00 | 42000.00 | **NÃO** |
| lucro_bruto | 95000.00 | 53000.00 | 48000.00 | **NÃO** |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 95000.00 | 53000.00 | 48000.00 | **NÃO** |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 95000.00 | 53000.00 | 48000.00 | **NÃO** |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | 5000.00 |
| 1.1.05 | 0.00 |
| 1.1.06.19 | 0.00 |
| 2.1.03 | 0.00 |
| 2.1.06 | 0.00 |
| 2.1.04.13 | 0.00 |
| 2.1.04.19 | 0.00 |
| 4.1.01 | 61750.00 |
| 4.3.01 | 0.00 |
| 4.4.03 | 0.00 |

## Marco: 8_conclusao_projeto

| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |
|---|---|---|---|---|
| receita_bruta | 95000.00 | 95000.00 | 90000.00 | sim |
| deducoes | 0.00 | 0.00 | 0.00 | sim |
| receita_liquida | 95000.00 | 95000.00 | 90000.00 | sim |
| cmv_csp | 42000.00 | 42000.00 | 42000.00 | sim |
| lucro_bruto | 53000.00 | 53000.00 | 48000.00 | sim |
| despesas_comerciais | 0.00 | 0.00 | 0.00 | sim |
| despesas_administrativas | 0.00 | 0.00 | 0.00 | sim |
| constituicao_provisoes | 0.00 | 0.00 | 0.00 | sim |
| ebitda | 53000.00 | 53000.00 | 48000.00 | sim |
| resultado_financeiro | 0.00 | 0.00 | 0.00 | sim |
| outras_receitas | 0.00 | 0.00 | 0.00 | sim |
| lucro_liquido | 53000.00 | 53000.00 | 48000.00 | sim |

**Saldos das contas-chave:**

| conta | saldo |
|---|---|
| 1.1.02 | 5000.00 |
| 1.1.05 | 0.00 |
| 1.1.06.19 | 0.00 |
| 2.1.03 | 0.00 |
| 2.1.06 | 0.00 |
| 2.1.04.13 | 0.00 |
| 2.1.04.19 | 0.00 |
| 4.1.01 | 61750.00 |
| 4.3.01 | 0.00 |
| 4.4.03 | 0.00 |

