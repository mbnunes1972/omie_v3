# Orientação da Fase 2 — custo e fechamento

Escrita em 31/08, com a Fase 1 fechada e antes de qualquer tarefa da Fase 2.

## O que muda de natureza

A Fase 1 era aritmética: números errados no livro, cada um com um teste que
vira verde. A Fase 2 é **fechamento de ciclo e processo** — a provisão que
nunca liquida, a fila que precisa de dono, a conta cujo nome promete uma
funcionalidade que não existe. Menos conta, mais desenho, e pelo menos uma
decisão de produto ainda em aberto.

Isso muda o ritmo: espere mais medição e menos conserto por passo.

## Antes de escrever as tarefas: reavaliar o escopo

**A Fase 1 mudou a Fase 2.** O roteiro foi escrito antes dela e três itens
já não são o que eram:

- **ACHADO-01 encolheu muito.** O passo 10 fechou o `loja_antecipacao` por
  completo e deu ao `financeira` a perna de liquidação; sobrou o gatilho
  automático. O passo 12 pode ser um terço do que parecia.
- **ACHADO-06** nunca foi medido — a tarefa começa por medir, não por
  consertar, e pode terminar sem conserto nenhum.
- **ACHADO-17** depende de uma decisão do Marcelo que ainda não veio.

O erro a evitar é escrever a tarefa do passo 12 a partir do texto de três
semanas atrás. A Fase 1 provou duas vezes que reavaliar escopo antes de
escrever economiza um passo inteiro: os ACHADOS 02 e 03 viraram um só, e o
predicado do aditivo se resolveu sozinho no passo 6.

## O primeiro passo da Fase 2 não é conserto

**Rodar de novo a medição de ciclo das DREs** — `docs/db/TESTE_DRE_CICLO.md`,
o teste que abriu esta auditoria e mediu o projeto fechando com receita de
90.000 e custo zero.

A suíte prova as peças. Aquele teste prova o todo, e é a única forma de
responder a pergunta que interessa: **depois da Fase 1, as três visões
reconciliam?** Compare marco a marco com o relatório original
(`docs/db/RELATORIO_DRE_CICLO.md`), linha por linha e nunca por total — dois
erros podem se cancelar.

Se reconciliarem, o `xfail` do ACHADO-15 vira XPASS e quebra a suíte, o que
é a melhor notícia possível. Se não reconciliarem, a divergência restante é
o mapa da Fase 2, medido em vez de suposto.

## As duas decisões que dependem do Marcelo

1. **ACHADO-17** — implementar a retenção de comissão como concebida
   (nasce retida, liberação condicionada, resíduo revertido em receita), ou
   renomear a conta `2.1.04.12` para o que ela de fato é, uma provisão
   simples de comissão? Bloqueia o item 14.
2. **Política de reconhecimento da DRE Diferida** — confirmar que é na
   entrega, não na venda (a venda é contrato, não resultado). Bloqueia a
   Fase 4 inteira, então vale resolver cedo.

## Ordem sugerida

1. Medição de ciclo das DREs (acima) — reavalia tudo o que vem depois.
2. Passo 12 — ACHADO-01, no escopo que sobrou.
3. Passo 13 — fila de provisões em aberto, dona: assistente administrativa
   da loja. Depende do que a medição mostrar sobre volume.
4. Passo 14 — P5, ACHADO-06 (medir antes), ACHADO-17 (se decidido).

## O que continua valendo, sem exceção

- Teste antes do conserto, `xfail(strict=True)` citando o achado.
- Controle negativo em todo aceite novo; positivo quando a recusa for o
  comportamento esperado.
- Achado novo no meio de um passo ganha número na hora e entra na fila —
  não é consertado dentro do passo, salvo se o bloquear.
- Aceite de fase com **duas** travas: suíte sem xfail da fase, e nenhuma
  linha da fase em "SEM PROVA" no `ACEITE.md`.
- Toda migration nova entra na lista de pendências de implantação no mesmo
  passo que a criou.
