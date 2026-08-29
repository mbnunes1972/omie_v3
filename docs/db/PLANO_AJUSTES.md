# Plano de ajustes — consolidado

Reescrito em 29/08/2026, depois do teste de ciclo das DREs. Substitui as
versões anteriores. Reúne os 20 achados contábeis, as pendências da
TAREFA_PROVISOES, o desenho das visões de DRE e a dívida de banco.

**Situação:** nenhum cliente real no sistema; os quatro ambientes estão
limpos e implantados. Todo conserto aqui custa código, não migração de dado
— a janela mais barata que vai existir.

---

## As três regras que organizam quase tudo

**1. Quem fica com o deságio decide se ele é receita ou custo.**
Terceiro financiou (banco, financeira, cartão): o deságio saiu da loja, é
custo financeiro. A loja financiou (Parcelamento Loja): o deságio ficou na
loja, é receita financeira. Os achados 01, 02 e 03 são violações disso.

**2. Um livro, várias lentes.**
Todo evento lança uma vez. As visões de resultado são CONSULTAS sobre o
mesmo livro, nunca contabilidades paralelas. Duas visões que divergem por
terem lógica própria produzem divergência indistinguível de bug.

**3. Nome tem que descrever comportamento.**
Cinco achados desta auditoria são a mesma doença: conta ou mecanismo cujo
nome promete o que o código não faz (Total Flex, Retenção de Comissão,
DRE "Real", 5.3.01, 2.1.05). Renomear sem medir só troca a confusão de
lugar.

---

## A ordem obrigatória

**Não construa relatório em cima de número errado.** Se as visões de DRE
forem montadas antes do Grupo 1, os primeiros relatórios do sistema vão
estar errados — e as pessoas vão confiar neles. Relatório errado em que
ninguém confia é inofensivo; relatório errado que todo mundo usa é o pior
resultado possível.

---

## GRUPO 1 — receita e margem · bloqueia usar o sistema para decidir

**1. ACHADO-12 — aditivo não vira receita E não é cobrado.**
Escalado em 29/08: o `Recebivel` nasce do contrato original, antes do
aditivo existir. Aditivo vendido, executado, nunca faturado nem cobrado.
É caixa que não entra.

Desenho decidido: o Aditivo continua entidade própria (rastreabilidade);
uma função única responde "valor do projeto" = contrato + aditivos; o
acréscimo percorre o mesmo caminho do contrato (2.1.06 → faturamento); e o
`Recebivel` passa a contemplar os aditivos.

**2. ACHADO-16 — provisão cancelada em silêncio torna a margem fictícia.**
Medido: projeto com receita de 90.000 e custo zero. A Conciliação Final
descarta a estimativa em vez de questioná-la. Basta esquecer uma nota da
fábrica para o projeto fechar com margem inventada.

**DECIDIDO em 29/08: recusa o fechamento.** Toda provisão aberta precisa de
um veredito nomeado antes de o projeto fechar — *efetivada* / *encerrada com
valor menor* / *não se aplica* / *ainda vai chegar*. O quarto não resolve: o
projeto fica aberto, e é isso que impede a decisão de virar pressão para
chutar valor. Resíduo de provisão superestimada **reverte custo** (correção
de estimativa) — regra que **não** vale para o custo financeiro, ver
ACHADO-01.

Vem junto, senão a decisão vira formalidade: **relatório de projetos
encerrados por reversão**, ordenado pelo valor revertido, com o motivo
escrito ao lado. A reversão melhora a margem — logo é exatamente o que se
quer olhar.

**3. ACHADO-18 — guarda de `valor_total > 0`. DECIDIDO em 29/08: entra.**
Medido: o ponto de entrada examinado não alcança o fail-soft, mas por
coincidência de desenho, não por validação. E o ACHADO-19 mostrou seis
outras rotas que alcançam. A guarda entra na geração de contrato e na
emissão de NF-e, recusando com mensagem. É a segunda linha; a primeira é o
item 0. Proteção acidental não é proteção.

**4. ACHADO-02 — receita financeira contada duas vezes no ramo loja.**
Medido: R$ 3.800 em R$ 46.300. Decidido: `4.1.01` recebe o VAVO, `4.4.03`
recebe o `cust_fin` como receita financeira. Somados dão o Val_Cont, uma vez.

**5. ACHADO-13 — guarda do refaturamento.** Decidido: um segmento é faturado
uma vez, sempre. `estornar_faturamento_nfe` já existe; a guarda reaproveita.
Teste dos dois lados: segunda chamada recusada; depois do estorno, aceita.

**6. ACHADO-03 — ramo roteado por `if` num lugar e por tabela em outro.**
Pela regra do deságio, é o erro mais grave de classificação possível:
registra como receita da loja um deságio que foi ao banco.

## GRUPO 2 — custo e fechamento

**7. ACHADO-01 — provisão de custo financeiro nunca liquidada.**
Decidido: o assistente informa o **líquido recebido**; o sistema deriva o
deságio e baixa a provisão contra o recebível. Sem obrigação fiscal, não há
motivo para conciliar face e líquido.

**8. Item 5 — fila de provisões em aberto.** Dono: **assistente
administrativo da loja**. Ampliado pelo ACHADO-16: a fila é de toda provisão
que fecha sem efetivação, não só Impostos e Custo Financeiro.
Refinamento: provisão de imposto aberta = NF-e não emitida (falha
operacional). Imposto devido e não pago vive em **2.1.03** (decisão de
caixa). São dois relatórios.

**9. P5 — `parcela_ambiente.valor_ambiente`.** `NOT NULL default 0.0`: "não
informado" e "vale zero" são indistinguíveis por construção. Entra zerado na
base de retenção e distorce o rateio. Tornar anulável (custa nada com as
bases vazias) e fazer o cálculo recusar ou sinalizar quando NULL.

**10. ACHADO-06 — reclassificação de Outros Fornecedores.** Pode deixar
ativo e provisão divergentes. **Medir antes.**

**11. ACHADO-17 — Retenção de Comissão.** Decisão de produto: implementar a
retenção como concebida (parcial, condição de liberação, reversão para
receita) ou renomear a conta para o que ela é.

## GRUPO 3 — integridade estrutural · janela barata agora

**12. `projeto_id` → FK.** `Projeto.nome_safe` é a PK e `lancamento.projeto_id`
já guarda esse valor: declarar a FK com `ON UPDATE CASCADE` /
`ON DELETE RESTRICT` é quase só declarar.

**PRÉ-REQUISITO, medido e confirmado:** `upsert_projeto_status()` só é
chamado em mudança de status. Um projeto que existe como orçamento e ainda
não fechou **não tem linha em `Projeto`** — e a FK quebraria no primeiro
lançamento manual. Extrair `garantir_projeto(nome_safe)` de dentro dele e
chamá-lo **onde o projeto aparece pela primeira vez**. Só depois a FK.

Depois do `lancamento`, as outras ~28 colunas que guardam `nome_safe` podem
virar FK uma a uma, sem migração de dado.

**13. Dois testes do `projeto_id`:** todo lançamento cuja origem é evento de
projeto tem o campo; nenhum aponta para projeto inexistente.

**14. Impedir lançamento em período fechado.** Tabela nova e mínima:
`periodo_fechado(owner_tipo, owner_id, ano, mes, fechado_em, fechado_por)`,
única por `(owner, ano, mes)`. `lancar()` recusa `data` dentro de mês
fechado.

**Não reusar `PeriodoContabil`** — ele é snapshot de reconciliação com rateio
sobre intervalo livre, e intervalo livre é legítimo ali. Grade mensal não
admite sobreposição nem buraco: a pergunta "está em período fechado?" passa
a ter uma resposta só.

**15. Vocabulário controlado do `origem`**, com teste: as ~89 chaves de
`EVENTOS` mais `manual`.

**16. Campo novo de tipo de registro:** `normal` | `cancelamento` |
`estorno` | `ajuste`. Sem "outros" — categoria coringa enche e para de
discriminar.

**17. Campo de competência referida**, para lançamentos de ajuste. Só
leitura: permite mostrar "junho como publicado" e "junho com as correções
posteriores".

## GRUPO 4 — as visões de resultado · depende do Grupo 1

**18. Rename e remoção — DECIDIDO em 29/08 por medição:**

- `real` (= `dre()`, apurada do livro) → **DRE Diferida**. É a escriturada.
- `antecipacao_contrato` → **DRE Antecipada**. Leitura por safra, nunca
  escriturada.
- `competencia_estimada` → **REMOVER**. É um híbrido: receita realizada com
  custo estimado, misturando duas bases de medição na mesma coluna. E
  calcula errado — nunca subtrai a baixa da sobra.

A informação que ela tentava dar é o **relatório de variância**, que compara
as duas bases corretamente e por safra.

Cuidado do rename: rótulo muda livre; o **identificador do wire** só muda se
nada o persistir. Verificar antes, como no caso `total_flex`.

**19. DRE Antecipada como leitura**, nunca lançada. Lê as posições
constituídas na venda: provisões (despesa antecipada) e receita diferida
(receita antecipada). Nenhum lançamento novo.

**20. Exportação Excel da Antecipada.** Cabeçalho com: instante da geração,
escopo, **status de cada período (aberto/fechado)**, `max(lancamento.id)` e
contagem. O status responde "posso confiar?"; o id responde "de qual estado
do livro isso saiu?".

**21. Relatório de variância por safra** — provisionado × realizado, rubrica
a rubrica. A ponte entre as duas DREs, e o instrumento que responde "eu sei
orçar?".

**22. Relatório de endividamento e carteira** — provisões, receita diferida,
contas a receber, 2.1.03. Responde "até onde posso me alavancar".

**23. Decomposição do mês por safra** — "o resultado de junho: quanto veio de
vendas de junho, de março, de janeiro". Mostra o descasamento entre venda e
entrega em dinheiro. Sai de graça do que já está lançado.

**24-b. Tela de comparação de ambientes do PE × Projeto Vendido.**
Pedida pelo usuário em 29/08, reconhecendo que *"não foi tratado
anteriormente como deveria"*. Apresentar, numa tela de orçamento, os
ambientes com diferença de valor: **valor de venda do ambiente no Projeto
Executivo × valor do ambiente no Projeto Vendido**, calculados com **os
mesmos parâmetros usados na venda**.

É o instrumento que decide o valor do aditivo, e hoje esse valor sai de um
cálculo sem tela. **Não depende do Grupo 1** — o motor já calcula a
diferença por fator proporcional (`_complemento_diferencas_fase` →
`mod_conciliacao_pe.valor_complemento_por_fator`); medir primeiro o quanto
disso já está pronto, antes de desenhar tela nova.

Frente própria: é produto, não contabilidade. Não misturar com a
`TAREFA_ADITIVO`, que trata de faturar e cobrar o aditivo, seja qual for o
valor que esta tela produzir.

**Armadilha a evitar na tela:** as duas DREs **não são comparáveis período a
período** — uma venda de janeiro entregue em junho aparece na Antecipada de
janeiro e na Diferida de junho. A comparação que ensina é **por safra**.

## GRUPO 5 — higiene · nada muda número

24. `_migrar_colunas_pg` — remover as 4 entradas de UPDATE/DELETE (medição
    deu zero nos quatro ambientes).
25. Teste **"nenhum boot altera dado"** — o irmão do
    `test_schema_boot_estavel`, que já cobre schema.
26. ACHADO-07 — o segundo escape hatch manual sem validação.
27. Onda 2 — os três ciclos de FK (usuarios↔funcionarios, redes↔emitente,
    orcamentos↔parcela_projeto).
28. Onda 2 — os 53 pares FK-sem-índice de nível 3.
29. Produção: `Environment=` na unidade systemd → `/root/orizon.env`. Hoje
    qualquer um que rode `systemctl cat` lê a senha.
30. Rotacionar o `sad2026` no localhost, Integração e Homologação.

**ACHADO-19 e ACHADO-20 — medidos em 29/08 e rebaixados para cá.** As seis
rotas que respondem `ok` a um recálculo que falhou continuam sendo desenho
errado, mas a Medição 1 não achou exceção alcançável por usuário. Em vez de
blindar as seis rotas, fecham-se as duas causas, que são baratas:

31. `json.loads(proj.parametros_json)` ganha try/except (main.py:17258) —
    o `config_financeira_json`, seis linhas acima, já tem o dele.
32. Guarda de ciclo no complemento auto-referente (ACHADO-20).
33. `/parametros` (10893) deixa de devolver `sombra` recalculada ao vivo
    quando o recálculo do laço falhou. **É o único dos seis casos em que o
    sistema mostra um número que nunca existiu no banco** — faça este
    primeiro, é uma linha.

Dívida registrada, sem item: reescrever as seis rotas para insumo e
recálculo na mesma transação, quando alguma delas mudar por outro motivo.

Dívida com condição, não item: o alias `total_flex` no frontend sai quando
alguém tocar naquela tela.

---

## Decisões tomadas

- Sistema **gerencial**, não fiscal. Formalismo fica para depois.
- Deságio: quem fica com ele decide receita ou custo.
- Custo financeiro sempre descontado na origem — resíduo nunca é dívida.
- Variância de imposto → `4.3.01`, nos dois sentidos (falta e sobra).
- `5.6.10` nunca é destino implícito; sem destino definido, falha com nome.
- Refaturar: uma vez só, sempre. Correção passa por estorno.
- Fila de provisões: assistente administrativo da loja.
- DREs: Diferida escriturada, Antecipada lida, `competencia_estimada` sai.
- Exportação Excel como foto; nada persistido no banco.
- `projeto_id` vira FK.
- Guarda explícita de `valor_total > 0` antes de contrato e de NF-e.
- Conciliação Final não fecha com provisão em aberto; veredito nomeado por
  rubrica, e "ainda vai chegar" mantém o projeto aberto.

## Decisões ainda abertas

1. **ACHADO-17**: implementar a retenção de comissão, ou renomear a conta?
2. **Política de reconhecimento da Diferida** — confirmar que é na entrega
   (a venda é contrato, não resultado).

## Medições pendentes

- **ACHADO-19** — medições 1, 2 e 3 feitas em 29/08 (resultado no achado;
  rebaixado para o Grupo 5). Restam, agora sem urgência: **4** o contrato
  bate consigo mesmo; **5** quantos orçamentos já estão defasados nos quatro
  ambientes; **6** existe caminho até o contrato sem nunca ter persistido.
  A **6** vale por si — é a pergunta do ACHADO-18 pelo outro lado.
- **ACHADO-06** — a conferência do pedido pode deixar ativo e provisão
  divergentes?

## O que NÃO fazer

Não emitir nota nem apurar margem para cliente real antes do Grupo 1. Os
seis achados dele afetam diretamente o valor da venda, a cobrança e a margem.
