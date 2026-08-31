# O que não existe — desenvolvimentos, separados dos consertos

Criado em 29/08/2026. A auditoria achou duas coisas diferentes e elas
estavam misturadas no mesmo plano:

- **Defeito**: existe código, faz a coisa errada. Vai em `ACHADOS_CONTABEIS.md`.
- **Ausência**: não existe código. Vai aqui.

A distinção importa porque o teste de um defeito descreve o erro atual; o
teste de uma ausência descreve um comportamento que ninguém escreveu ainda.
São trabalhos diferentes e não devem ser estimados juntos.

---

## A parte perigosa — o sistema promete o que não tem

Levantada pelo usuário: *"identifiquei falhas de ausência de códigos que achei
que tinham sido implementados."* Não é desatenção dele. É um padrão do
código, e a auditoria o encontrou cinco vezes:

| onde | o que promete | o que existe |
|---|---|---|
| conta `2.1.04.12` "Retenção de Comissão de Vendas" | retenção, liberação condicionada, reversão em receita | provisão simples (ACHADO-17) |
| docstring de `_fin_faturamento_segmentado_seguro` | CMV reconhecido na NF-e, ref `cmv:<projeto>` | mecanismo extinto em 07/08 (ACHADO-22) |
| `PeriodoContabil` | controle de fechamento de período | retrato de conciliação, `status` fixo em "fechado" |
| DRE "Antecipação no Contrato" | a DRE Antecipada do desenho novo | outra semântica; será substituída |
| conta `5.3.01`, "Total Flex" | ver ACHADO-09 e ACHADO-14 | nome ≠ mecanismo |

**A regra que sai disso:** um nome de conta, um docstring ou um rótulo de
tela **não são evidência de que o mecanismo existe**. Antes de assumir que
algo está implementado, procurar quem chama. Foi assim que o ACHADO-22
nasceu — e foi assim que ele foi corrigido.

---

## Desenvolvimentos que substituem algo existente

1. **DRE Antecipada** substitui "Antecipação no Contrato". Lê o
   **constituído** por safra (débitos no ativo diferido), nunca o saldo —
   ver PLANO_AJUSTES 19-a. Somente leitura, nunca lança.
2. **DRE Diferida** substitui "Real"; **`competencia_estimada` sai**.
3. **`periodo_fechado(owner_tipo, owner_id, ano, mes)`** — tabela nova e
   mínima, com `lancar()` recusando mês fechado. Não sobrecarregar
   `PeriodoContabil`.

## Desenvolvimentos novos

4. **Fila de provisões em aberto** — dona: assistente administrativa da
   loja. Toda provisão que fecharia sem efetivação.
5. **Vereditos da Conciliação Final** (ACHADO-16): efetivada / encerrada com
   valor menor / não se aplica / ainda vai chegar. O quarto mantém o projeto
   aberto.
6. **Relatório de projetos encerrados por reversão**, ordenado pelo valor
   revertido, com o motivo escrito. Sem ele, o item 5 vira formalidade.
7. **Coleta de forma de pagamento na assinatura do aditivo** + recebíveis
   próprios.
8. **Tela de comparação de ambientes PE × Projeto Vendido**, com os
   parâmetros da venda. Medir antes quanto o motor já entrega.
9. **Exportação Excel da Antecipada**, com cabeçalho declarando instante da
   geração e situação do período.
10. **Relatório de variância por safra** — provisionado × realizado, rubrica
    a rubrica.
11. **Relatório de endividamento e carteira.**
12. **Decomposição do mês por safra.**
13. **`scripts/conferir_valor_total.py`** — conferência somente-leitura
    (medição 5 de TESTE_NEGOCIACAO_VALOR_TOTAL).
14. **Retenção de comissão** — só se a decisão do ACHADO-17 for implementar
    em vez de renomear.

## Solicitação de Medição — a data não é capturada

Encontrado pelo Marcelo em 31/08, clicando em Homologação.

`SolicitacaoMedicao` (database.py:1428) é o Termo de Responsabilidade da
etapa 9 — tem `status`, PDF, assinaturas, canal ClickSign. **Não tem campo
de data nenhum.** A única data de medição no sistema é
`Contrato.previsao_medicao`, coletada lá atrás na tela de contrato
(`ct-previsao-medicao`), junto com `data_entrega`.

São coisas diferentes: `previsao_medicao` é **previsão**, dada no
fechamento da venda; o que falta é a **data acordada** no momento de
solicitar a medição — que é o que o cliente assina no termo.

15. **Modal do botão "Solicitar Medição" captura a data da medição**, e ela
    entra no documento gerado. Decidir se substitui, corrige ou apenas
    complementa a `previsao_medicao` do contrato (as duas informações têm
    valor: previsto × acordado é variância, e variância é o que ensina).

16. **Cadastro de funcionários na Homologação.** A transferência de
    responsabilidade na medição oferece uma lista vazia porque não há
    medidor cadastrado. Duas coisas: popular a Homologação com um conjunto
    de funcionários de teste; e a tela dizer *"nenhum medidor cadastrado"*
    em vez de oferecer uma transferência impossível — lista vazia sem
    explicação é a mesma família do `logging.warning` que ninguém lê.

## Em aberto, sem decisão

- **Aditivo criado manualmente entre a assinatura e o PE.** Pedido do
  Marcelo em 31/08: hoje o botão "Gerar Termo Aditivo" só existe dentro da
  seção de PE (static/index.html:21731) — o aditivo nasce **exclusivamente**
  da divergência do Projeto Executivo, o que é fiel à regra que o próprio
  usuário definiu. A pergunta é se deve existir um segundo caminho, na aba
  de contrato, depois da assinatura. As consequências estão avaliadas na
  resposta de 31/08; em resumo: (a) o aditivo passaria a ter duas naturezas,
  valor calculado e valor digitado; (b) a base do complemento de PE muda,
  corretamente mas não obviamente; (c) o caminho novo precisa herdar as
  quatro guardas dos ACHADOS 21, 24, 25 e do congelamento de segmentação, ou
  reabre os quatro; (d) a própria regra "XML novo ⇒ projeto novo" limita o
  escopo a mudança de valor em ambiente existente. **Não decidido.**

- **Alternativas de revisão de PE.** Hoje só existe painel de comparação, e
  o usuário registrou insegurança quanto a essa escolha: o cliente às vezes
  faz várias alternativas, com inclusão e remoção de itens, e aquilo vira uma
  negociação nova. O paralelo natural é o que já existe na venda — vários
  orçamentos, um vence. Não decidido; **não confundir com o ACHADO-21**, que
  trata de revisão depois da assinatura e é defeito, não ausência.
