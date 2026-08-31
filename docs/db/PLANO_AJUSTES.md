# Plano de ajustes — consolidado

> **A ordem de execução está em `docs/db/ROTEIRO.md`.** Este arquivo é o
> porquê e o agrupamento; o roteiro é a fila.

Reescrito em 29/08/2026, depois do teste de ciclo das DREs. Substitui as
versões anteriores. Reúne os 23 achados contábeis, as pendências da
TAREFA_PROVISOES, o desenho das visões de DRE e a dívida de banco.

**Situação:** nenhum cliente real no sistema; os quatro ambientes estão
limpos e implantados. Todo conserto aqui custa código, não migração de dado
— a janela mais barata que vai existir.

---

## As quatro regras que organizam quase tudo

**1. Quem fica com o deságio decide se ele é receita ou custo.**
Terceiro financiou (banco, financeira, cartão): o deságio saiu da loja, é
custo financeiro. A loja financiou (Parcelamento Loja): o deságio ficou na
loja, é receita financeira. Os achados 01, 02 e 03 são violações disso.

**Terceiro caso, acrescentado em 30/08:** quem **nunca teve** o dinheiro não
tem nem receita nem custo. No ramo financeira/cartão a financeira recebe do
cliente e retém a própria taxa — o deságio não passa pelo caixa da loja, e
por isso não é despesa dela. O que a loja precisa ali não é lançar custo: é
**conferir** se a retenção real bateu com a esperada.

**A tabela por ramo (decidida em 30/08).** `cust_fin = Val_Cont − VAVO` é o
preço do crédito cobrado do cliente. `4.1.01` recebe **o VAVO em todos os
ramos** — o preço do móvel não muda conforme a forma de pagamento.

| ramo | o que acontece | `cust_fin` |
|---|---|---|
| à vista | cliente paga o preço à vista | não existe |
| loja | loja financia com capital próprio | **receita financeira** |
| loja_antecipacao | loja financia; depois antecipa no banco | **receita financeira**; o deságio do banco é custo separado, no evento da antecipação |
| financeira / cartão | a financeira recebe do cliente e retém a taxa | **nada no resultado** — vira retenção esperada, posição de balanço |

**2. Um livro, várias lentes.**
Todo evento lança uma vez. As visões de resultado são CONSULTAS sobre o
mesmo livro, nunca contabilidades paralelas. Duas visões que divergem por
terem lógica própria produzem divergência indistinguível de bug.

**3. O que já virou fato contábil se lê de onde foi congelado — não se
recalcula.**
Acrescentada em 30/08 depois de a mesma doença aparecer três vezes, por
caminhos independentes: o orçamento assinado que era sobrescrito pela
revisão seguinte (ACHADO-21); a Antecipada que leria o saldo da conta em vez
do constituído, fazendo a safra de janeiro encolher sozinha; e o aditivo
assinado que, ao ser recalculado ao vivo, se subtraía de si mesmo e zerava o
próprio valor (achado no passo 6). Recalcular um valor já escriturado faz o
passado mudar quando o presente muda. Snapshot congelado (`Aditivo.dados_json`),
lançamento com data, posição constituída — essas são as fontes; o motor não é.

**4. Nome tem que descrever comportamento.**
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

**0-a. ACHADO-13 — `faturar_segmento` não é delta-aware na receita.**
Mecanismo confirmado com números em 29/08: a receita é creditada pelo valor
cheio a cada chamada. **Vem antes do ACHADO-12** — somar contrato+aditivos
sem isto transforma um defeito raro em defeito de todo projeto com aditivo.

**0-b. ACHADO-21 — aditivo cobrado duas vezes quando há revisão de PE depois
da assinatura.** Medido: R$ 15.555,55 cobrados onde o correto era
R$ 11.111,11, e o valor pelo qual o cliente assinou o primeiro aditivo deixa
de existir no sistema. Único achado da auditoria que tira dinheiro a mais de
quem comprou. Conserto: orçamento de complemento vira imutável depois da
assinatura; revisão seguinte gera orçamento novo, calculado contra contrato +
aditivos já assinados.

**0-d. Três pontas soltas da medição do aditivo**, medidas mas ainda sem
dono:
- **Predicado do aditivo**: `POST /api/projetos/<n>/aditivo` filtra por
  `parcela_id` só se a requisição enviar a chave; sem ela pega o
  `complemento_pe=1` de **maior id** do projeto. Nada impede as duas rotas de
  complemento coexistirem no mesmo projeto — então o aditivo pode amarrar no
  orçamento errado por ordem de criação. Vai junto com a soma do ACHADO-12:
  o conjunto de orçamentos precisa ser explícito, não inferido.
- **Segmentação herdada**: a segmentação vem de `Projeto.parametros_json`
  ao vivo. Um aditivo assinado depois de uma mudança de parâmetro é faturado
  com a segmentação ATUAL, não com a que valia quando foi negociado. Mesma
  classe do ACHADO-19; muda o número entre Mercadoria e Serviço.
- **Resolvido sem medir (29/08):** a dependência do mecanismo legado é
  **zero** — os quatro ambientes foram limpos e não há projeto nenhum com
  `ArquivoPE` gravado. Aposentar o legado custa zero agora, e este é o
  momento mais barato que vai existir.

**1. ACHADO-12 — aditivo não vira receita E não é cobrado.**
Escalado em 29/08: o `Recebivel` nasce do contrato original, antes do
aditivo existir. Aditivo vendido, executado, nunca faturado nem cobrado.
É caixa que não entra.

**Cobrança decidida em 29/08: recebíveis próprios.** A assinatura do aditivo
passa a coletar forma de pagamento e chama
`_materializar_recebiveis_venda_seguro` para o orçamento do complemento — a
guarda de idempotência já é por `orcamento_id`, então nada toca nos
recebíveis do contrato. Dois efeitos que vêm de graça e um cuidado:

- O aditivo passa a ter **custo financeiro próprio**: `_ramo_financeiro_efetivo`
  lê `orc.forma_pagamento`, então a regra do deságio (quem fica com ele decide
  se é receita ou custo) se aplica ao aditivo sem código novo.
- O aditivo passa a aparecer na carteira e no relatório de endividamento pelo
  que de fato é.
- **Cuidado:** o recálculo do complemento zera `forma_pagamento`
  (main.py:7885-7891, "calculada em cima do VBVO antigo"). Com a forma de
  pagamento coletada na assinatura, um recálculo posterior a apagaria — o que
  a imutabilidade pós-assinatura do ACHADO-21 já impede. **Os dois consertos
  dependem um do outro; não implemente este sem aquele.**

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

**4. ACHADO-02 + ACHADO-03, juntos — o que cada ramo faz com o `cust_fin`.**
Medido: R$ 3.800 em R$ 46.300 contados duas vezes no ramo loja. Decidido em
30/08 a tabela por ramo acima. `4.1.01` recebe **o VAVO sempre**.

**A tabela `_RAMO_CFIN_EVENTO` também está errada** — não é a resposta
canônica que o ACHADO-03 supunha. Ela manda `financeira` e
`loja_antecipacao` para o mesmo evento de custo provisionado, quando o
primeiro não gera custo nenhum e o segundo gera receita financeira no
contrato. O `if` de main.py:749 e o dicionário divergiam **e nenhum dos dois
estava certo**.

**A retenção esperada fica**, nos ramos financeira e loja_antecipacao, e
serve ao que o usuário pediu: conferência automática do assistente
financeiro. Contrato de R$ 200.000 com retenção prevista de 10%; o banco
retém 9%; sobram R$ 2.000 que precisam aparecer. Mas ela **não é despesa** —
a receita já nasce líquida dela, e lançá-la como custo subtrai duas vezes.
É posição de balanço que abate o recebível, e a **variância vai para uma
conta só, nos dois sentidos**, exatamente como já foi decidido para os
impostos (`2.1.04.13 → 4.3.01`).

**5. ACHADO-13 — guarda do refaturamento.** Decidido: um segmento é faturado
uma vez, sempre. `estornar_faturamento_nfe` já existe; a guarda reaproveita.
Teste dos dois lados: segunda chamada recusada; depois do estorno, aceita.

**6. ACHADO-01 — a perna que faltava tem nome: o evento de conferência.**
A pergunta mais antiga desta auditoria (*o que liquida a provisão de custo
financeiro?*) foi respondida em 30/08 pela tabela por ramo: **a retenção
real chegando**. No `financeira`, a liquidação do cartão; no
`loja_antecipacao`, a antecipação bancária. A provisão não é dívida com
ninguém — é previsão de retenção, e se encerra quando a retenção acontece,
com a diferença indo para a conta única de variância.

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

**19-a. A Antecipada lê o CONSTITUÍDO, não o saldo. DECIDIDO 29/08.**
A pergunta da Antecipada é sobre o passado ("qual foi o custo da safra de
janeiro?"), e saldo de conta é fotografia do presente. Lendo saldo, o ativo
diferido drena conforme as provisões são efetivadas e o custo da safra de
janeiro **encolhe sozinho** nos meses seguintes — margem de janeiro subindo
sem ninguém lançar nada em janeiro. A Antecipada soma os **débitos que
entraram** no ativo diferido para os projetos daquela safra; esse número é
estável para sempre. Não exige coluna nova: o lançamento já carrega
`projeto_id` e `data`.

Vale para todas as rubricas, não só o CMV. **Escrever isto no código que
montar a Antecipada, não só aqui** — é invisível até os relatórios de três
meses atrás começarem a mudar sozinhos.

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
31-a. ACHADO-22 — apagar do docstring de `_fin_faturamento_segmentado_seguro`
    a promessa do "matching pleno" extinto em 07/08, e apontar para
    `reconhecer_despesa_efetivacao`. É onde alguém vai procurar como o CMV é
    reconhecido, e a promessa velha já induziu um erro de análise.
31-b. **Varredura por `logging.warning`/`print` em caminho de dinheiro**
    (achado ao consertar o ACHADO-24, F2-1, 31/08/2026). Quarto lugar onde
    alguém previu a falha e escolheu seguir com um aviso em vez de recusar —
    os outros três são o ACHADO-19 (seis rotas), o ACHADO-23 (congelamento
    da segmentação) e o ACHADO-18. Cada aviso desses é um lugar onde alguém
    viu o problema e não teve tempo; vale uma varredura dedicada, não mais
    um achado por vez.

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
- Antecipada lê o constituído (débitos do período), nunca o saldo da conta.
- `4.1.01` recebe o **VAVO em todos os ramos**.
- Quem nunca teve o dinheiro não tem receita nem custo (financeira/cartão).
- Retenção esperada é posição de balanço, não despesa; variância numa conta
  só, nos dois sentidos, como nos impostos.
- Segmentação não congelada trava a **AF1**, não a assinatura nem a NF-e
  (ACHADO-23), e a AF1 consegue congelar ali mesmo.
- Aditivo tem **recebíveis próprios**: a assinatura coleta forma de pagamento
  e materializa `Recebivel` com a mesma mecânica do contrato.

## Como impedir que mudança de contrato de API vire cegueira de UI (F2-2)

docs/db/TAREFA_CONTRATOS_UI.md pediu uma recomendação, não código. Três
direções, do mais barato ao mais caro:

1. **Varredura estática de `static/index.html`** — um teste que faz parse
   dos `fetch(...)` para rotas conhecidas e confere se o corpo enviado
   contém as chaves que aquela rota hoje exige (uma tabela pequena,
   mantida à mão, espelhando as guardas já escritas em `main.py`). Custo:
   baixo — um arquivo, sem infraestrutura nova. Cobertura: pega
   **ausência** de campo (teria pego o ACHADO-25 e o ACHADO-26 no mesmo
   commit que os introduziu — `peAditivoAssinar` nunca cita
   `forma_pagamento`; `conciliarFinal()` nunca cita `vereditos`). Não pega
   **qualidade** do valor (manda a chave, mas vazia) — não pegaria sozinho
   o ACHADO-24 original.
2. **Contrato declarado por endpoint, lido pelos dois lados** — um schema
   (JSON/dict) por rota, associado à guarda no backend E consultado por um
   teste (ou por validação no próprio JS antes do `fetch`). Custo: médio —
   exige reescrever as guardas ad-hoc de hoje numa forma declarativa,
   endpoint por endpoint, à medida que cada um for tocado (não como
   reescrita única). Cobertura: pega ausência E qualidade (um schema pode
   exigir "pelo menos uma parcela ou entrada_valor > 0", não só "a chave
   existe") — e dá erro de UX melhor, avisando antes do round-trip.
3. **E2E de navegador nos fluxos críticos** (aditivo, contrato, Conciliação
   Final) — Playwright/Selenium dirigindo a tela real. Custo: alto — infra
   nova, testes lentos e mais frágeis a mudança visual. Cobertura: total —
   é o único que pegaria o ACHADO-26 por inteiro (o campo nem existe pra
   descrever num schema; só rodar a tela mostra que "Concluir" nunca
   oferece veredito nenhum).

**Recomendação:** fazer a **1** agora — é barata, teria pego os dois
achados que já mordemos, e serve de rede permanente contra o próximo. Não
esperar a 2 ou a 3 para isso. Migrar pra **2** endpoint por endpoint,
como parte do próprio conserto de cada achado de UI (ACHADO-25, ACHADO-26)
— o schema nasce junto com a correção, não depois. Reservar a **3** para
só os 2-3 fluxos mais caros de errar (Conciliação Final é um deles) —
não para a suíte inteira, o custo não compensa fora dos fluxos terminais/
irreversíveis.

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
oito achados dele afetam diretamente o valor da venda, a cobrança e a margem.
