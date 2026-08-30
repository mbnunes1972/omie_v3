# Passo 1 do ROTEIRO — o teste do ACHADO-16

**Não conserte nada.** Este passo escreve a prova, não a correção. O
conserto é o passo 8.

## Por que este teste primeiro

O ACHADO-16 é o mais grave da auditoria — o que produziu o projeto com
receita de 90.000 e custo zero — tem conserto decidido, e **nada hoje viraria
verde quando ele fosse consertado** (`docs/db/ACEITE.md`).

## O defeito, com precisão

`resolver_saldo_provisao` (mod_contabil.py:2035) cancela o saldo da provisão
contra o ativo diferido espelho, **sem tocar a DRE**, e o docstring explica
por quê:

> *"SOBRA (provisionado > efetivado) é dinheiro nunca gasto, não vira
> 'receita'; FALTA (efetivado > provisionado) já teve a despesa real
> reconhecida a cada efetivação."*

O raciocínio está certo — **e pressupõe que houve efetivação.** O caso que
ele não considera é efetivação **nenhuma**: aí a "sobra" é 100% da provisão,
e a regra "dinheiro nunca gasto" é aplicada a um custo que ocorreu — a
fábrica entregou, a nota só nunca foi registrada.

O sistema não consegue distinguir *"não foi gasto"* de *"foi gasto e ninguém
lançou"*. Os dois têm exatamente a mesma aparência no banco. E ele resolve o
empate sozinho, em silêncio, sempre a favor da margem.

## O teste que dá para escrever hoje — e o que não dá

Esta é a parte que economiza um dia de trabalho.

**A tentação (não faça):** um teste que afirma "o custo tem que aparecer em
5.1.01 depois da conclusão". Ele é **infalsificável**. Do ponto de vista do
sistema não existe diferença entre a provisão que sobrou porque o custo não
ocorreu e a que sobrou porque ninguém registrou — é isso o achado. Um teste
que exige o custo no resultado estaria exigindo que o sistema adivinhe.

**O teste certo é sobre a recusa, não sobre o número.** O defeito é o sistema
decidir sozinho; a correção é ele parar de decidir. Então:

### Teste 1 — aceite, `xfail(strict=True)` citando ACHADO-16

Projeto percorre o ciclo até a Conciliação Final com **pelo menos uma
provisão nunca efetivada**. A conclusão do projeto deve ser **recusada**.

Hoje ela é aceita → o teste falha → `xfail`. Quando o passo 8 entrar, a
recusa acontece, o teste passa, e o `strict` quebra a suíte no XPASS
obrigando a remover o marcador. É a prova, e ela é agnóstica a como o
conserto for implementado.

### Teste 2 — medição, sem xfail

Registra a assinatura do defeito de hoje, para que ela não volte por outro
caminho: depois da conclusão com provisão não efetivada, o saldo da provisão
está zerado **e** nenhum débito chegou em `5.1.01` para aquele projeto.
Verde hoje, e continua verde depois — o que ele documenta é o mecanismo, não
a política.

### O que fica para o passo 8, e precisa estar escrito no ACEITE

Os vereditos (*efetivada / encerrada com valor menor / não se aplica / ainda
vai chegar*) **não existem** hoje. Um teste contra uma rota inexistente falha
por 404 ou `AttributeError`, e um `xfail(strict=True)` engoliria isso como
"falha esperada" — depois ficaria verde por qualquer motivo, inclusive um
errado. **Não escreva esse teste agora.** Registre em `ACEITE.md` que o
aceite dos vereditos nasce junto com a implementação, e que ele precisa
cobrir a regra das duas pernas: *encerrada com valor menor* **efetiva pelo
valor real** (é isso que reconhece o custo) e **só então** reverte o resíduo.

## Controle negativo

Antes de dar o teste por bom: mude o código de propósito para que a
conclusão seja recusada, e confirme que o Teste 1 vira XPASS e quebra a
suíte. Um teste de aceite que não sabe ficar verde não prova nada. Desfaça
a mudança depois.

## O que reportar

1. O Teste 1 escrito, vermelho pelo motivo certo (não por erro de setup).
2. A saída do controle negativo.
3. O Teste 2 verde.
4. `ACEITE.md` atualizado: linha do ACHADO-16 sai de "SEM PROVA".
