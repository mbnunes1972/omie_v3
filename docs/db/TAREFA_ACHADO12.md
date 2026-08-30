# Passo 7 do ROTEIRO — o aditivo passa a ser faturado

O ACHADO-12 é o último dos três defeitos do aditivo. Os outros dois já
saíram: o 13 (receita creditada pelo valor cheio a cada emissão) no passo 5,
e o 21 (cobrança em dobro) no passo 6. **Esta ordem existia por isto:** somar
antes do 13 transformaria defeito raro em defeito de todo projeto com
aditivo, e somar antes do 21 somaria um valor já duplicado.

## O conserto

`_valores_segmentados_do_projeto` (main.py:1293) resolve o valor a faturar
lendo `Contrato.orcamento_id → Orcamento.valor_total` — sempre o contrato
original. Passa a usar `valor_contratado_do_projeto` (extraída no passo 6):
contrato + aditivos **assinados**.

Com o passo 5 no lugar, a segunda emissão fatura só o delta — a soma não
duplica nada. Confirme isso com número, não por dedução.

**Uma consequência boa do passo 6:** o predicado deixa de ser problema. A
tarefa anterior registrava o risco de `complemento_pe=1` não distinguir
aditivo de complemento por fase, e de o conjunto ser inferido por
`parcela_id`. Como `valor_contratado_do_projeto` já define o conjunto
explicitamente — aditivos com `status == "assinado"` —, a soma para faturar
herda essa definição em vez de inventar outra. **Não escreva um segundo
predicado.** (A seleção do endpoint `POST /aditivo`, que pega o
`complemento_pe=1` de maior id, é outro assunto — ver abaixo.)

## Os três pontos a resolver

### 1. `cfo` — decidir e justificar

`_valores_segmentados_do_projeto` devolve `cfo`, e a medição do passo 6
mostrou que **nenhum dos três consumidores usa esse campo**. As provisões de
custo de fábrica do aditivo já são constituídas por
`_fin_provisoes_venda_seguro` na assinatura.

Duas saídas legítimas, e a escolha precisa estar escrita:
- somar o `cfo` junto com o `val_cont`, mantendo a coerência do retorno; ou
- **remover o campo**, já que ninguém o usa e ele hoje é uma promessa sem
  consumidor — exatamente o material de que o ACHADO-22 é feito.

Prefira remover se a remoção for limpa. Um campo que ninguém lê é uma
armadilha esperando o próximo leitor.

### 2. Seleção do orçamento no `POST /aditivo`

O endpoint filtra por `parcela_id` só quando a requisição manda a chave; sem
ela pega o `complemento_pe=1` de **maior id** do projeto. Depois do passo 6
existem mais orçamentos de complemento por projeto — uma revisão pós-assinatura
agora cria um novo —, então essa seleção por ordem de criação ficou **mais**
perigosa, não menos.

Torne a seleção explícita. Se o passo 6 já resolveu, diga como e siga.

### 3. Segmentação congelada — **medir, e trazer a decisão**

A segmentação Mercadoria/Serviço vem de `Projeto.parametros_json` ao vivo.
Um aditivo assinado depois de uma mudança de parâmetro seria faturado com a
segmentação **atual**, não com a que valia quando foi negociado.

Isto muda o que vai na nota do cliente, então **não é decisão de método —
é decisão do Marcelo.** A sua parte é medir e reportar:

1. É alcançável? Que caminhos mudam `pct_mercadoria`/`pct_servico` do
   projeto ou da loja depois do contrato assinado?
2. Se for alcançável, qual o efeito em número num caso concreto?
3. O `Aditivo.dados_json` — o snapshot que o passo 6 passou a usar — já
   carrega a segmentação, ou precisaria carregar?

**Não implemente o congelamento.** Reporte, e a decisão volta para você.

Note que a regra 3 do plano (*o que já virou fato contábil se lê de onde foi
congelado*) aponta para uma resposta, mas apontar não é decidir: aqui há
efeito fiscal na face do documento, e isso é do dono do negócio.

## Aceites

O `xfail(strict=True)` do ACHADO-12 — e os cenários `tem_aditivo=True` da
bateria — saem no mesmo commit do conserto.

Antes disso, escreva o aceite que fecha o ciclo inteiro: **projeto com
aditivo termina com 2.1.06 zerado.** É a invariante que a
`TAREFA_BATERIA_CICLO` já declara e que o aditivo quebrava — receita
constituída que nunca virava receita faturada.

## O que NÃO fazer

- Não escrever um segundo predicado de "quais orçamentos contam".
- Não congelar a segmentação sem a decisão.
- Não mexer na Conciliação Final — é o passo 8.
