# Primeiro passo da Fase 2 — remedir o ciclo das DREs

Não é conserto. É a medição que responde se a Fase 1 fez o que prometeu.

## Por que este teste, e não a suíte

A suíte prova as peças: 2461 testes, cada um afirmando uma coisa. **Este
teste prova o todo.** Foi ele que abriu a auditoria, medindo um projeto
fechando com receita de 90.000, custo zero e margem de 100% — o número que
nenhum teste unitário teria mostrado, porque cada peça estava individualmente
"certa".

Doze consertos depois, a pergunta é a mesma: **as três visões reconciliam?**

## O que rodar

`tests/test_dre_ciclo_completo_e2e.py`, com `--runxfail` para ver o
resultado real em vez do marcador. Capture os retratos de todos os marcos,
do `1_projeto_criado` até a Conciliação Final.

## Como comparar

Contra `docs/db/RELATORIO_DRE_CICLO.md`, o relatório original, **marco a
marco e conta a conta**. Nunca por total: dois erros podem se cancelar, e
foi assim que este ciclo escondeu o problema da primeira vez.

As perguntas em ordem de importância:

1. **Onde está a primeira divergência agora?** Antes era a emissão da NF-e,
   com `cmv_csp` valendo 0 contra 42.000 e receita idêntica dos dois lados.
2. **O projeto ainda fecha com margem de 100%?** Era o sintoma que abriu
   tudo.
3. **O que a `2.1.06` faz com o aditivo?** Antes ficava presa em R$ 5.000
   para sempre — receita constituída que nunca virava faturada. O passo 7
   deveria ter resolvido; confirme com número.
4. **A `4.1.01` mudou de valor?** Deve ter — agora recebe o VAVO, não mais
   o Val_Cont cheio. Se **não** mudou neste cenário, entenda por quê antes
   de comemorar.

## O que esperar, e o que fazer com cada resultado

**Se as visões reconciliarem:** o `xfail(strict=True)` do ACHADO-15 vira
XPASS e quebra a suíte. É a melhor notícia possível — remova o marcador no
mesmo commit e marque o ACHADO-15 como resolvido.

**Se não reconciliarem:** a divergência que sobrou é o mapa da Fase 2,
medido em vez de suposto. Descreva-a com números, não com hipótese, e não
tente consertar nesta tarefa.

## Duas coisas a reportar mesmo que não perguntadas

1. **O que você precisou mudar no teste para ele rodar depois da Fase 1.**
   O passo 8 mudou o fluxo — o projeto não fecha mais sem veredito por
   rubrica. Se o teste precisou de vereditos, quais deu e por quê: essa
   escolha entra no número medido e precisa estar visível, não escondida no
   fixture.
2. **`competencia_estimada`** ainda aparece? Ela sai na Fase 4, mas se já
   estiver divergindo de forma diferente, é informação sobre o que a Fase 1
   moveu.

## O produto

Um relatório novo, `docs/db/RELATORIO_DRE_CICLO_POS_FASE1.md`. **Não
sobrescreva o original** — a comparação entre os dois é o resultado, e um
apaga o outro se virarem o mesmo arquivo.
