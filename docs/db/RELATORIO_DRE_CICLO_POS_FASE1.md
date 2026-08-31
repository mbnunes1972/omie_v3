# Relatório — três visões de DRE, ciclo completo (pós-Fase 1)

Gerado por `tests/test_dre_ciclo_completo_e2e.py`. **Teste de medição, não de conserto.** `real` e `competencia_estimada` deveriam bater linha a linha (a hipótese de docs/db/TESTE_DRE_CICLO.md); `antecipacao_contrato` é só observada — ela diverge por desenho (reconhece no contrato, não na NF-e), não é achado.

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
como no relatório original. **Fase 1 não moveu esse ponto.**

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
→ `5000.00` (7) → `5000.00` (8), nos dois relatórios. Isso bate com o
cenário do fixture: a forma de pagamento tem `total_cliente = 90000.00`
mas o aditivo eleva a receita para `95000.00` — os `5000.00` que sobram em
aberto em `1.1.02` são o saldo não coberto pela forma de pagamento
original, não um efeito do aditivo em si. **A referência da tarefa a
`2.1.06` parece mirar o sintoma certo (valor preso em R$ 5.000) na conta
errada — o número bate em `1.1.02`.**

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

## Veredito sobre o xfail (ACHADO-15)

As três visões **não reconciliam em todos os marcos** — a divergência
mora em `6a_nfe_produto_emitida`, `6b_nfse_servico_emitida` e
`7_recebimento` (mesmos números do relatório original, inalterados). Ela
só desaparece no marco final, `8_conclusao_projeto`, e apenas porque a
Conciliação Final agora exige um veredito nomeado — que, quando o veredito
reconhece o custo cheio (`encerrada_valor_menor` @ 42000.0), faz `real`
convergir com `competencia_estimada` no fechamento.

Isso não satisfaz a condição da tarefa para remover o marcador ("se as
visões reconciliarem" — sem qualificação). `test_ciclo_completo_tres_visoes_dre`
continua **genuinamente FAILED** sob `--runxfail` (confirmado por execução
direta), então **o `xfail(strict=True)` permanece** — mas seu texto estava
factualmente errado ("nunca mais reconciliam neste cenário") e foi
corrigido para refletir o achado mais estreito: a divergência é
temporária, não permanente, e se fecha no momento da Conciliação Final
por causa do veredito do passo 8, não por uma mudança em `real()`.
ACHADO-15 permanece **aberto**, com escopo revisado — ver
docs/db/ACHADOS_CONTABEIS.md.

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

