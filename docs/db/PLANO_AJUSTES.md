# Plano de ajustes — tudo que a auditoria identificou

Consolida os 13 achados contábeis, as pendências da TAREFA_PROVISOES e a
dívida de banco. Ordenado por consequência no número, não por facilidade.

Situação em 29/08/2026. Nenhum cliente real no sistema; os quatro ambientes
estão limpos. Isso significa que todo conserto aqui custa código, não
migração de dado — a janela mais barata que vai existir.

---

## O enquadramento

**O sistema é gerencial, não fiscal.** O objetivo é que os números permitam
controlar o negócio. Formalismo fiscal fica para depois, e não será
retrabalho se os conceitos estiverem certos agora.

Consequência prática: "faturar" é evento de gestão, não emissão de nota. O
que precisa estar certo é o valor, o momento e a conta.

## A regra que organiza os achados 01, 02 e 03

**Quem fica com o deságio decide se ele é receita ou custo.**

- Financiou um terceiro (banco, financeira, cartão) — o deságio saiu da
  loja: é **custo financeiro**.
- Financiou a própria loja (Parcelamento Loja) — o deságio ficou na loja:
  é **receita financeira**. A loja está fazendo o papel da financeira e
  ganha por isso.

Os três primeiros achados são violações dessa regra em pontos diferentes.

---

## FASE 1 — a receita
Bloqueia usar o sistema para decidir preço, margem ou comissão. Os dois
erram a receita em direções opostas: um omite, o outro infla. Enquanto não
fecharem, não dá para dizer se a receita apurada está para mais ou para
menos.

### ACHADO-12 — aditivo nunca vira receita
100% do valor de todo aditivo fica preso em 2.1.06.

Desenho decidido:
- O **Aditivo continua entidade própria**. Não vira linha de Contrato — isso
  destruiria a rastreabilidade de quanto foi vendido originalmente e por quê
  o valor mudou.
- Uma **função única** passa a responder "valor do projeto" = contrato +
  aditivos. `_valores_segmentados_do_projeto` consulta essa função em vez de
  ler o Contrato direto. Valor derivado num lugar só não é terceira fonte de
  verdade — é a eliminação da ambiguidade.
- O acréscimo percorre o **mesmo caminho** do contrato original: constitui em
  2.1.06 e é reconhecido no faturamento. Um caminho, não dois.
- O lado do custo vem pela máquina de rubricas que já existe: as despesas a
  maior geram suas contrapartidas em Fornecedores a Pagar.

Pronto quando: o xfail do aditivo vira verde e o ciclo com aditivo fecha as
sete invariantes.

### ACHADO-02 — receita financeira contada duas vezes no ramo "loja"
Medido: venda de R$ 46.300 apura R$ 50.100. Distorção de R$ 3.800, o custo
financeiro contado duas vezes.

Desenho decidido, direto da regra do deságio:
- `Val_Cont = VAVO + cust_fin`.
- **4.1.01 recebe o VAVO** — o que a mercadoria vale à vista.
- **4.4.03 recebe o cust_fin** como receita financeira.
- Somados dão o Val_Cont, contado uma vez.

Ganho gerencial além da correção: passa a dar para ver separado quanto a
loja ganha vendendo móvel e quanto ganha financiando. Hoje os dois estão
misturados dentro de 4.1.01, e inflados.

Pronto quando: `test_ramo_loja_receita_total_deveria_contar_o_custo_
financeiro_uma_vez_so` vira verde sozinho.

---

## FASE 2 — o custo e o fechamento

### ACHADO-01 — a provisão de custo financeiro nunca é liquidada
Causa raiz de vários outros. O ativo diferido drena, a provisão não, porque
falta o lançamento de liquidação.

Desenho decidido:
- O assistente informa o **valor líquido recebido**. Venda de R$ 100.000,
  entrou R$ 90.000: o sistema deriva os R$ 10.000 de deságio e baixa a
  provisão contra o recebível.
- Sem obrigação fiscal, não há motivo para exigir conciliação de face e
  líquido — o líquido é o fato, o resto é derivado.
- O lançamento continua valendo mesmo "sumindo": é ele que informa o volume
  que passou por cada financeira, que é insumo de negociação com o banco.

Destrava o item 2 da TAREFA_PROVISOES.

### Item 5 — projeto fechando com provisão em aberto
`conciliar_final` exclui 2.1.04.13 e 2.1.04.19 da resolução automática, então
um projeto pode ser encerrado com saldo em aberto, em silêncio.

Decisão: **avisar e listar**, com a lista sendo o mecanismo de verdade.
Aviso depende de alguém estar olhando na hora; fila sobrevive ao momento e
vira trabalho do assistente administrativo. Só faz sentido depois do
ACHADO-01 — hoje a fila nasceria com todos os projetos dentro.

### ACHADO-03 — o ramo roteado por `if` num lugar e por tabela em outro
`_fin_provisoes_venda_seguro` trata `loja_antecipacao` como se fosse `loja`,
divergindo de `_RAMO_CFIN_EVENTO`.

Pela regra do deságio, é o erro mais grave possível de classificação:
registra como receita da loja um deságio que foi para o banco.

Conserto: a tabela é a fonte única. **Quando existe tabela de decisão,
ninguém decide de novo com um `if`** — regra para o CLAUDE.md. Quarta
ocorrência da mesma doença.

---

## FASE 3 — risco condicional e superfície de erro
Não erram número hoje, mas erram quando a condição acontecer.

- **ACHADO-06** — reclassificação de Outros Fornecedores pode deixar ativo e
  provisão com saldos diferentes. Depende da conferência do pedido.
- **ACHADO-13** — `faturar_segmento` pode duplicar receita se chamado duas
  vezes para o mesmo segmento. Não confirmado. **Primeiro medir**: o fluxo
  permite? Se permitir, sobe para a Fase 1.
- **ACHADO-07** — dois escape hatches manuais sem validação de regra de
  negócio. Um deles já ganhou guarda (item 1 da TAREFA_PROVISOES); o outro
  precisa do mesmo.
- **P5** — `parcela_ambiente.valor_ambiente` entra como zero silencioso no
  cálculo de retenção. "Ambiente sem valor informado" e "ambiente que vale
  zero" são coisas diferentes, e o `or 0.0` do código já desconfia disso.

---

## FASE 4 — limpeza
Nenhum muda número. Reduzem confusão e superfície.

- **ACHADO-04** — 2.1.05 "Financiamento Total Flex a Pagar" nunca tocada.
- **ACHADO-05** — 2.1.04.01 e o evento `pagamento_comissao` são mecanismo
  morto.
- **ACHADO-08** — contas do PLANO_PADRAO que nenhum evento toca.
- **ACHADO-09** — 5.3.01 usada por dois mecanismos com nomes conceitualmente
  diferentes. Renomear ou separar.
- **ACHADO-10** — `_fin_evento_seguro` é código morto.
- **ACHADO-11** — docstring de `conciliar_final` desatualizada.

Para 04, 05, 08 e 10 a pergunta é a mesma: **remover ou implementar?** Conta
que nunca é tocada é funcionalidade que não existe ou vestígio de decisão
revogada. Decidir uma vez, para os quatro.

---

## FASE 5 — higiene de banco e operação
Não muda número; evita susto.

- As quatro entradas de UPDATE/DELETE do `_migrar_colunas_pg` — medição deu
  zero nos quatro ambientes, então saem sem migration. Mais o teste de que
  **nenhum boot altera dado**, que fecha a classe (o irmão do
  `test_schema_boot_estavel`, que já cobre o schema).
- Dívida de Onda 2: os três ciclos de FK (usuarios↔funcionarios,
  redes↔emitente, orcamentos↔parcela_projeto) e os 53 pares FK-sem-índice de
  nível 3.
- Produção: mover o DATABASE_URL de `Environment=` na unidade systemd para
  um `/root/orizon.env`, como A e B. Hoje qualquer um que rode
  `systemctl cat` lê a senha.
- Rotacionar o `sad2026` no localhost, Integração e Homologação.

---

## Decisões tomadas em 29/08/2026

**ACHADO-13 — refaturar não é permitido.** Um segmento é faturado uma vez,
sempre. `faturar_segmento` deve recusar a segunda chamada para o mesmo
segmento, com erro explícito. Correção exige **cancelar o faturamento
anterior primeiro**, num ato explícito que estorna a receita e fica no
histórico. Isso transforma o ACHADO-13 de "talvez duplique" em "não pode
duplicar, por construção" — e sobe para a Fase 1, porque a guarda é barata
e o risco é receita dobrada.

Verificar se já existe cancelamento de faturamento no sistema. Se não
existir, ele é parte deste conserto — sem ele, não há caminho de correção.

**Item 5 — a fila é do assistente administrativo da loja.** Quem já faz o
lançamento do ajuste no dia a dia é quem vê a pendência. A fila aparece na
tela dele, filtrada por loja. O gerente não precisa dela para trabalhar,
mas o saldo em aberto deve ser visível no fechamento do projeto.

## Fase 4 — resolvida em 29/08/2026, depois da investigação de origem

A investigação mostrou que **três dos quatro não são defeitos**. As contas
vieram todas juntas do seed inicial (0b86514, 09/07/2026), derivado de um
plano de contas genérico importado de uma vez — nenhuma nasceu de
funcionalidade sendo construída.

**ACHADO-04 — remover o evento, manter a conta.** O evento `custo_financeiro`
(5.5.03 × 2.1.05) nasceu marcado [CONFIRMAR CONTADOR] e nunca foi
confirmado. Ele modela o Parcelamento Loja como se o dinheiro viesse de
fora — um passivo a pagar. Pela regra do deságio, quem financia é a própria
loja, e o deságio é receita financeira dela. O mecanismo que roda hoje
(1.1.07 / 2.1.07 / 4.4.03) está certo; o evento adormecido está errado.

Evento errado que ninguém chama é arma carregada: basta alguém achar que
"faltava wirar". Remover. A conta 2.1.05 fica no catálogo — volta a fazer
sentido se o Parcelamento Loja algum dia for fundeado por terceiro.

**ACHADO-05 — remover o evento, medir a conta.** `pagamento_comissao` foi
legitimamente superado: comissão hoje é paga pela Folha, com caminho
próprio. Remover.

Mas a comissão passou a usar `2.1.04.12 "Retenção de Comissão de Vendas"`,
e **retenção e provisão são conceitos diferentes** — provisão reconhece a
obrigação, retenção segura parte do pagamento até uma condição. Se a mesma
conta faz as duas coisas, é a doença do ACHADO-09 outra vez. MEDIR ANTES DE
FECHAR o 05.

**ACHADO-08 — artefato da medição, não defeito.** Duas categorias estavam na
mesma lista:

- Despesa administrativa (Aluguel, Água, Energia, Salários): **são usadas**,
  por lançamento manual. "Nunca tocada por evento" nunca foi sintoma nelas.
- Contas de módulo (Estoques, Imobilizado, Intangível, Financiamentos de
  Longo Prazo, Aluguéis): são plano, não sobra. Plano de contas é mapa do
  que a empresa pretende ser. Ficam.

A ação é **refinar o relatório**, não mexer nas contas: distinguir conta de
evento de conta de lançamento manual, e marcar as de módulo como futuro
declarado. Senão a lista acusa as mesmas quinze em toda auditoria futura.

**ACHADO-10 — remover.** Mecanismo completo e funcional, substituído por
versões mais específicas em cada fluxo. A intenção de plugar outros eventos
nele nunca se concretizou. Deixar ali é oferecer o caminho errado a quem
chegar depois.

## ACHADO-14 — "Total Flex" virou "Parcelamento Loja" e o rename não chegou

O produto mudou de nome. O código não: `mod_fin/total_flex.py`,
`config/total_flex.json`, `tabelas_financeiras/total_flex.json`, e o nome da
conta `2.1.05 "Financiamento Total Flex a Pagar"` — que está **no banco**,
onde rename em código nunca chega (`seed_plano()` cria o que falta e não
corrige o que existe).

Mesmo padrão de 1.1.09/2.1.09. Conserto: rename no código, mais migration de
dado para o nome da conta nos ambientes existentes, no mesmo commit.

Consequência: nenhuma no número. Custo de não fazer: quem entra no projeto
procura por "Parcelamento Loja" e não encontra o código que implementa.

## Recalibração do tamanho

Depois da investigação, a lista real de defeitos que erram número é:
**01, 02, 03, 12, 13, 06 e o P5** — sete, dos quais dois já estão
completamente especificados e com teste esperando virar verde.

O resto é catálogo, código superado, nomenclatura e um critério de medição
largo demais. E os defeitos reais estão concentrados em dois lugares — o
tratamento do deságio e o caminho do aditivo — não espalhados.

## Decisões ainda abertas

**`2.1.04.12` acumula provisão e retenção de comissão ao mesmo tempo?**
Medir. Se sim, vira achado novo e o ACHADO-05 só fecha junto com ele.

## O que NÃO fazer

Não emitir nota nem apurar margem para cliente real antes da Fase 1 fechar.
Os dois achados dela afetam diretamente o valor da venda.
