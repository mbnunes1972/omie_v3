# Passo 5 do ROTEIRO — `faturar_segmento` delta-aware na receita

**Este é o primeiro conserto da jornada.** Tudo antes foi medição e prova.
A partir daqui muda comportamento, e a regra do roteiro passa a valer:
o `xfail(strict=True)` do ACHADO-13 fica verde e **o marcador sai no mesmo
commit**.

## O defeito

`faturar_segmento` (mod_contabil.py) recebe `valor` e o credita **inteiro**
em 4.1.01 (mercadoria) ou 4.2.01 (serviço). O split usa/resto decide apenas
**qual conta absorve o débito** — 2.1.06 até o saldo do adiantamento, 1.1.02
pelo resto. Não existe nenhuma noção de "quanto desta receita já foi
reconhecido". Segundo documento fiscal para o mesmo segmento do mesmo
projeto credita tudo de novo. Medido: 4.1.01 fechou em R$ 182.222,22 onde o
correto era R$ 93.333,33.

A idempotência por `ref` protege contra **o mesmo documento** duas vezes.
Não protege contra **dois documentos** para o mesmo segmento — que é
exatamente o que o aditivo vai produzir a partir do passo 7.

## O conserto

`valor` passa a significar **"o total que deve estar reconhecido para este
projeto neste segmento"**, e a função fatura a **diferença** entre isso e o
que o livro já registra.

O já-reconhecido se lê do próprio livro: movimento credor de 4.1.01
(mercadoria) ou 4.2.01 (serviço) para aquele `projeto_id`. A função já faz
leitura de razão — `saldo_adiantamento_projeto` — então isto não fere o
layering: ler quanto já foi lançado numa conta não é cálculo de negócio, é
consulta ao livro. O que continua fora daqui é *quanto vale a venda*, que
vem do motor.

O split usa/resto não muda: ele passa a repartir o delta em vez do total.

## Os quatro pontos que decidem se o conserto está certo

### 1. Delta ≤ 0 — recusar, com nome

Se o total a reconhecer for **menor** que o já reconhecido, **não lance
crédito negativo**. Reduzir receita reconhecida é estorno, e a regra deste
projeto já está decidida: *refaturar uma vez só, sempre; correção passa por
estorno* (ACHADO-13). Recuse com erro nomeado dizendo os dois números.

Não invente a rota de estorno nesta tarefa.

### 2. O estorno já existente entra na conta? — **medir antes de escrever**

A leitura do já-reconhecido precisa ser **líquida**: se houve estorno, ele
tem que reduzir o total. Confirme o que `_mov(..., "credor")` devolve — o
crédito bruto, ou crédito menos débito. Se for bruto, um estorno anterior
não reduziria a conta e o delta sairia errado **para menos**, deixando
receita legítima sem faturar.

Este é o ponto onde o conserto pode introduzir um defeito pior que o que
corrige. Meça, não presuma.

### 3. Os chamadores

Enumere quem chama `faturar_segmento` e confirme que todos passam o
**total**, não um incremento. Um chamador que já passasse incremento
passaria a faturar quase nada. Se algum passar incremento, o conserto muda
de forma — reporte antes de seguir.

### 4. O docstring

A docstring diz *"soma das pernas == valor"*. Depois do conserto é
*"soma das pernas == delta"*. **Atualize.** O ACHADO-22 nasceu de uma
docstring que continuou descrevendo um mecanismo extinto por três semanas, e
me fez construir uma hipótese errada em cima dela. Não repita isso no mesmo
arquivo.

## O que reportar

1. A medição do ponto 2, antes do código.
2. A lista de chamadores (ponto 3).
3. O conserto, com o `xfail` do ACHADO-13 removido no mesmo commit.
4. A suíte completa verde, e quantos xfails sobraram citando achado.
5. `ACEITE.md` atualizado: linha do 13.

## O que NÃO fazer

- Não implemente a rota de estorno.
- Não toque na soma contrato+aditivos (ACHADO-12) — é o passo 7, e a ordem
  existe porque somar antes disto transforma defeito raro em defeito de todo
  projeto com aditivo.
- Não mude o split usa/resto.
