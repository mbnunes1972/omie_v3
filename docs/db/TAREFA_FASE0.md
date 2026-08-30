# Passos 2, 3 e 4 do ROTEIRO — fechar a Fase 0

**Não conserte nada.** A Fase 0 só escreve provas. O passo 1 (ACHADO-16) já
está fechado; estes três encerram a rede.

Mesmas regras do passo 1: `xfail(strict=True)` citando o achado, controle
negativo em cada aceite novo, e vermelho **pelo motivo certo** — nunca por
erro de setup.

---

## Passo 2 — teste do ACHADO-03

Hoje o ramo do custo financeiro é roteado por `if` num lugar e por tabela em
outro. Só existe menção em comentário de `test_bateria_ciclo`, sem xfail
próprio: se alguém consertar, nada fica verde; se alguém regredir, nada fica
vermelho.

Escreva o aceite que prova a divergência entre os dois roteamentos para o
mesmo ramo. Se a divergência não se reproduzir com os cenários atuais,
**reporte isso** em vez de forçar — pode ser que o achado esteja mais estreito
do que foi registrado, e isso é informação.

## Passo 3 — corrigir a citação da costura 4

`test_costura4_revisao_apos_aditivo_assinado_duplica_cobranca` cita
ACHADO-12; o achado dele é o **ACHADO-21**. Quando o 12 for consertado
(passo 7), alguém vai remover o marcador achando que fechou os dois.

Trocar a citação. Um minuto de trabalho, e evita um conserto declarado sem
prova.

## Passo 4 — aceites do 18 e do 19

Os testes de hoje desses dois são de **medição**: provam o que o sistema faz
agora e continuam verdes depois do conserto. Faltam os que viram verdes
**por causa** do conserto.

### ACHADO-18 — a guarda de `valor_total > 0`

Aceite: gerar contrato, e emitir NF-e, para orçamento com `valor_total` nulo
ou zero deve ser **recusado** com mensagem.

**Cuidado que este teste exige:** o estado é inalcançável pelos caminhos
normais — foi isso que a medição concluiu. O teste precisa construir o estado
**direto no banco** e, antes de exercitar a rota, **afirmar que o estado
existe** (`assert orc.valor_total in (None, 0)`). Sem essa asserção
intermediária, um setup que silenciosamente recalculou o valor faria o teste
passar por motivo errado — e um `xfail(strict=True)` esconderia isso até
alguém confiar nele.

### ACHADO-19 e ACHADO-20 — os três consertos de causa

Um aceite para cada, todos escrevíveis hoje:

1. `parametros_json` malformado **não derruba** `_negociacao_breakdown` —
   cai no default com falha nomeada, como o `config_financeira_json` vizinho
   já faz.
2. Complemento auto-referente é **recusado com erro nomeado**, não
   `RecursionError` (ACHADO-20).
3. `/parametros` **não devolve `sombra`** quando algum recálculo do laço
   falhou — igual ao que `/margens` já faz.

O terceiro é o único dos seis casos do ACHADO-19 em que o sistema mostra ao
usuário um número que nunca existiu no banco. É o primeiro a consertar,
quando chegar a Fase 5.

---

## O que reportar

1. Passo 2: o aceite escrito e vermelho, ou o relato de que a divergência não
   se reproduz — com o que foi tentado.
2. Passo 3: feito.
3. Passo 4: os quatro aceites, cada um com a saída do controle negativo.
4. `ACEITE.md` atualizado — as linhas do 03, 18, 19 e 20 mudam de estado.

Ao fim deste passo a Fase 0 está fechada e a Fase 1 pode começar pelo
ACHADO-13.
