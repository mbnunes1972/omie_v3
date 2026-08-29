# Tarefa — bateria exaustiva de ciclo completo

Amplia tests/test_ciclo_completo_por_ramo.py de 3 cenarios para a matriz
inteira. Pode demorar; o Marcelo prefere profundidade a rapidez.

NAO CONSERTE NADA. Onde a invariante falhar, xfail(strict=True) citando o
achado. Achado novo entra numerado em ACHADOS_CONTABEIS.md.

---

## 0. Pre-requisito: a suite tem que estar verde
Feche o P6 (hermeticidade): test_chat_wa e test_comunicacao tentam envio
real de WhatsApp quando o .env esta carregado. Um conftest limpando essas
variaveis resolve. Suite com dois vermelhos permanentes ensina a ignorar
vermelho — e essa bateria depende de vermelho significar alguma coisa.

## 1. Motor unico, cenarios como dados
Um driver que percorre o ciclo: venda, contrato, provisoes, revisao de PE,
aditivo, NF-e, custos adicionais, recebimento, fechamento.

O cenario e' um dicionario — ramo, toggles, tem_aditivo, tem_custo_adicional,
rubricas a provisionar, valores. `pytest.mark.parametrize` sobre a lista.
Nada de copiar e colar cenario.

## 2. As invariantes — o que TODO cenario afirma
Iguais para todos. Sao elas que julgam certo e errado.

1. **Balancete fecha a cada passo**, nao so' no fim: soma(D) == soma(C)
   depois de cada evento do ciclo. Falhou, diz qual passo.
2. **Contas transitorias zeradas no fechamento**: provisoes, ativos
   diferidos, contas a receber do projeto. Sobrou saldo, diz qual conta e
   quanto.
3. **Receita total == valor da venda, contado uma vez** — incluindo
   aditivos. E' a invariante que o ACHADO-02 viola.
4. **Custo total == soma dos custos reais reconhecidos.** Nenhuma rubrica
   contada duas vezes, nenhuma esquecida.
5. **Toda provisao constituida foi resolvida** ao fim do ciclo.
6. **Nenhum lancamento em 5.6.10** sem marcacao explicita de que foi
   deliberado.
7. **Nenhuma conta fora do PLANO_PADRAO** foi tocada.

A mensagem de falha precisa dizer conta, valor e passo. "Balancete nao
fecha" nao serve.

## 3. A matriz
Dimensoes, combinadas:

- **ramo financeiro**: loja, loja_antecipacao, financeira
- **toggles de parametros**: ENUMERE do codigo quais parametros afetam
  contabilizacao (orcamento_params e config). Nao presuma que e' um so'.
  Cada um entra na matriz com true e false.
- **aditivo contratual**: sem aditivo / com aditivo na revisao do PE
- **custos adicionais**: sem / com

Se a matriz completa ficar grande demais para rodar sempre, marque
`@pytest.mark.slow` e deixe a suite do dia a dia com um subconjunto — mas a
matriz inteira tem que rodar por completo em algum lugar.

**O aditivo e' o caso mais dificil e o que mais me interessa**: ele muda o
valor do contrato DEPOIS de as provisoes existirem. As provisoes sao
recalculadas? A receita ja faturada e' ajustada? O que foi reconhecido antes
reconcilia com o novo valor? Se alguma dessas respostas for "nao", e' achado.

## 4. Cobertura de rubricas
Toda rubrica de provisao — as 15, mais Impostos, mais Custo Financeiro,
mais Arquiteto — exercitada ao menos uma vez, da constituicao a resolucao.

Ao fim da bateria, **reporte quais rubricas nunca foram exercitadas**. Uma
rubrica que nenhum cenario alcanca e' informacao: ou falta cenario, ou a
rubrica esta morta.

## 5. Retrato do balancete — detector de mudanca, NAO verdade
Grave por cenario um retrato dos saldos finais por conta, versionado.

Ele existe para que qualquer mudanca futura de comportamento apareca como
diff. **Nao e' declaracao de que os numeros estao certos** — varios estao
errados hoje e vao entrar no retrato do jeito que estao. Quem julga sao as
invariantes da parte 2. Escreva isso no cabecalho do arquivo de retrato,
para ninguem confundir "o retrato bate" com "a contabilidade esta certa".

## 6. Achados novos
Numere na sequencia de ACHADOS_CONTABEIS.md, com evidencia, consequencia em
reais quando der para medir, e a pergunta objetiva a decidir.

## Ao terminar
Suite verde com os xfail marcados, commit, push. Traga: a matriz executada,
a lista de achados novos, e o relatorio de cobertura de rubricas.
