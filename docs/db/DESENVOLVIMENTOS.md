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

## Em aberto, sem decisão

- **Alternativas de revisão de PE.** Hoje só existe painel de comparação, e
  o usuário registrou insegurança quanto a essa escolha: o cliente às vezes
  faz várias alternativas, com inclusão e remoção de itens, e aquilo vira uma
  negociação nova. O paralelo natural é o que já existe na venda — vários
  orçamentos, um vence. Não decidido; **não confundir com o ACHADO-21**, que
  trata de revisão depois da assinatura e é defeito, não ausência.
