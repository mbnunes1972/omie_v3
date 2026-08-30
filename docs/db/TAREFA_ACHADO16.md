# Passo 8 do ROTEIRO — a Conciliação Final para de decidir sozinha

O maior achado da auditoria, e o único cujo conserto muda **fluxo**, não só
número. O teste de aceite já existe desde o passo 1 e está vermelho
esperando este conserto.

## O defeito, em uma frase

`resolver_saldo_provisao` cancela o saldo da provisão contra o ativo
diferido sem tocar a DRE — raciocínio correto **que pressupõe ter havido
efetivação**. Quando não houve nenhuma, a "sobra" é 100% da provisão e a
regra *"dinheiro nunca gasto"* é aplicada a um custo que ocorreu: a fábrica
entregou, a nota só nunca foi registrada. Medido: projeto fechando com
receita de 90.000 e custo zero.

O sistema não distingue *"não foi gasto"* de *"foi gasto e ninguém lançou"*
— os dois têm a mesma aparência no banco. **A correção é ele parar de
tentar.**

## O desenho decidido (não reabrir)

A Conciliação Final **não fecha o projeto com provisão em aberto**. Cada
rubrica aberta exige um veredito nomeado de uma pessoa:

| veredito | efeito no livro |
|---|---|
| **efetivada** | nada a fazer — já lançado |
| **encerrada com valor menor** | **duas pernas:** efetiva pelo valor real (é isto que reconhece o custo, via `reconhecer_despesa_efetivacao`) e **só então** reverte o resíduo |
| **não se aplica** | reverte o saldo integralmente; **exige motivo escrito** |
| **ainda vai chegar** | **não resolve — o projeto não fecha** |

O quarto veredito é o que faz o desenho funcionar sem virar pressão para
chutar: ninguém é obrigado a inventar valor para encerrar.

**A regra das duas pernas é o ponto mais fácil de errar.** Reverter sem
efetivar reproduz o ACHADO-16 com outro nome — o custo real continua fora do
resultado. A única porta pela qual custo entra na DRE é a efetivação
(ACHADO-22); não existe outra.

**Não vale para o custo financeiro.** Lá o deságio já foi retido na origem,
não há pagamento futuro, e o acerto é puro balanço (ACHADO-01). Aplicar a
regra de reversão de custo nele reintroduz aquele erro. As duas provisões se
parecem; o tratamento não.

## O relatório que vem junto, não depois

**Projetos encerrados por reversão**, ordenados pelo valor revertido, com o
motivo escrito ao lado. Reversão de resíduo **melhora** a margem — então um
projeto que fecha com reversão grande é exatamente o que se quer olhar. Sem
esse relatório a decisão vira formalidade em três meses, e ninguém vai
perceber quando isso acontecer.

## A palavra "resolvido"

Hoje a API responde `{"resolvido": {"2.1.04.06": 1000.0}}` para um saldo que
ninguém resolveu. Depois deste passo a resposta diz **qual veredito** foi
dado, **por quem** e, quando for o caso, **com qual motivo**. Um valor
cancelado sob o rótulo de resolvido é a mesma doença da regra 4 do plano.

## Aceites

1. O `xfail(strict=True)` do passo 1
   (`test_conciliacao_final_recusa_com_provisao_nunca_efetivada`) sai neste
   commit.
2. **Novos, e agora escrevíveis** — os vereditos passam a existir:
   - *encerrada com valor menor* com provisão 1.000 e real 700: `5.1.01`
     recebe **700** e o resíduo de 300 reverte. Verificar as duas coisas
     separadamente — só o saldo final não distingue as duas pernas de uma
     perna só.
   - *não se aplica* sem motivo escrito é **recusado**.
   - *ainda vai chegar* mantém o projeto **aberto**.
   - custo financeiro **não** segue a regra de reversão (guarda do
     ACHADO-01).
3. `test_mecanismo_hoje_cancela_saldo_sem_tocar_5101` (passo 1, medição) vai
   quebrar — **é esperado**: ele documentava o mecanismo que este passo
   elimina. Reescreva-o para provar o mecanismo novo, ou remova-o dizendo
   por quê. Não o conserte para continuar verde.

## O que NÃO fazer

- Não aplicar a reversão ao custo financeiro.
- Não deixar o relatório para depois.
- Não inventar um quinto veredito, nem um "outros".
- Não mexer no ACHADO-18 (passo 9) nem no 02/03 (passos 10 e 11).
