# Lista Paralela de Achados — o que foi postergado

Criada em 31/08/2026. **Duas filas, uma ativa.**

- **Lista de Achados** (`ACHADOS_CONTABEIS.md` + `ROTEIRO.md`): o que está
  sendo corrigido agora.
- **Lista Paralela** (este arquivo): o que apareceu, vale, e foi
  **deliberadamente adiado** para o ciclo seguinte.

## As três regras

**1. Nem tudo que sai da fila ativa vem para cá.** Item **decidido contra**
está **fechado**, não adiado — fica registrado onde nasceu, com a decisão e
o motivo. Misturar "não agora" com "não" transforma a lista paralela em
cemitério, e cemitério ninguém revisa.

**2. Achado correlacionado entra na fila ativa, não aqui.** Se o que apareceu
é da mesma família do que está sendo consertado, tratar junto custa menos —
foi o que aconteceu com os ACHADOS 24, 26 e 27, que nasceram no meio da Fase
2 e foram resolvidos ali mesmo. Adiar o correlacionado é pagar duas vezes
pelo mesmo contexto.

**3. Todo item leva o motivo do adiamento.** Sem ele, o próximo a ler
rediscute a decisão do zero. "Adiado" sem porquê é o mesmo que não
registrado.

## A rotação

Ao fim de cada etapa de estabilização: revisa-se esta lista, ela **vira a
lista de achados em correção**, e o que for adiado dela começa a **nova
lista paralela**. A fila nunca cresce sem alguém decidir que cresce.

---

## Itens

**LP-01 · Data acordada da medição.**
`SolicitacaoMedicao` não tem campo de data; a única data é
`Contrato.previsao_medicao`, que é previsão dada no fechamento da venda. O
modal de "Solicitar Medição" deve capturar a **data acordada**, e ela entra
no documento que o cliente assina. Decidir se substitui, corrige ou
complementa a previsão — guardar as duas dá variância previsto × acordado.
*Adiado:* é coluna nova, migration, tela e decisão de desenho — não cabe num
ciclo de estabilização. (Marcelo, 31/08, clicando em Homologação.)
*Pedido de novo em 02/09*, com dois requisitos que o item ainda não tinha:
**uma data por fase** quando o projeto está desmembrado (liga no LP-12), e o
registro **alterando a programação automática** que o cronograma padrão
montou na assinatura — não é campo, é entrada que substitui previsão do
sistema. Medir onde essa programação vive e quem mais a lê antes de escrever
nela. Dois pedidos independentes do mesmo usuário: o adiamento estava certo,
a necessidade está confirmada.

**LP-02 · CPF do signatário conferido contra o cadastro.**
O ACHADO-28 entra no beta2 só com validação de dígito. Conferir se o CPF
**bate com a pessoa** que deveria assinar (o cliente do projeto, o gerente da
loja) é guarda diferente e mais forte.
*Adiado:* é política de negócio, decisão do Marcelo, e não travar o beta
esperando por ela.

**LP-03 · Varredura de `logging.warning`/`print` em caminho de dinheiro.**
Quatro achados desta auditoria nasceram de alguém prever a falha e seguir
com um aviso no log: ACHADO-18, 19, 23, 24. Cada aviso desses é um lugar
onde alguém viu o problema e não teve tempo.
*Adiado:* é varredura ampla, melhor feita de uma vez com a fila vazia.

**LP-04 · Varredura das fixtures que montam estado direto no banco.**
O passo 9 revelou vários testes com `valor_total` zero por acidente, porque
construíam o vínculo de ambiente no banco sem passar pelo recálculo do
caminho HTTP. Todo teste assim prova menos do que promete.
*Adiado:* não afeta produção, e mexer em fixture no meio de um ciclo
mascara regressão.

**LP-05 · E2E dos demais fluxos terminais.**
A recomendação do F2-2 era dois ou três; existe um (Conciliação Final).
Candidatos: emissão de NF-e, e o ciclo do aditivo ponta a ponta.
*Adiado:* o primeiro precisa rodar algumas semanas antes de sabermos se o
padrão se sustenta.

**LP-06 · PostgreSQL 16 na bancada.**
Hoje PG18 contra PG16 dos servidores. Já custou uma armadilha documentada
(`SET transaction_timeout` no dump). Ver `ESTEIRA.md`.
*Adiado:* mexer no banco da bancada no meio de um ciclo para a suíte por um
tempo indeterminado.

**LP-07 · Acesso remoto à bancada por rede privada.**
Tailscale ou WireGuard, sem abrir porta. Objetivo do Marcelo: liberdade de
trabalhar de qualquer lugar sem expor a máquina que tem repositório, chaves
e histórico.
*Adiado:* é infraestrutura, não bloqueia nada hoje.

**LP-08 · Servidor de desenvolvimento remoto.**
A `ESTEIRA.md` já comporta: entra como estágio 1 e a bancada volta a ser só
oficina.
*Adiado:* o Marcelo registrou como intenção, sem prazo.

**LP-09 · Alternativas de revisão de PE.**
Hoje existe só painel de comparação. O cliente às vezes faz várias
alternativas — inclusão, remoção, mudança de item — e aquilo vira uma
negociação nova. O paralelo natural é o que já existe na venda: vários
orçamentos, um vence.
*Adiado:* funcionalidade grande, e o Marcelo registrou insegurança sobre a
escolha atual sem ter decidido mudá-la. **Não confundir com o ACHADO-21**,
que trata de revisão *depois* da assinatura e é defeito, não ausência.

**LP-10 · Botões cobrar / manter / absorver / estornar em colunas.**
Hoje ficam desalinhados na tela de conciliação de PE. Ergonomia pura.
*Adiado:* não muda número nem trava fluxo. (Marcelo, 31/08.)

**LP-11 · `execucao_montagem`/`pagamento_fabrica` — ligar ou remover
(ACHADO-33, item 7 de `TAREFA_CONCILIACAO_UI.md`).**
Medido em 01/09, sem mexer: os dois estão em `EVENTOS` e só são disparados
por teste. Se ligados hoje, do jeito que estão definidos, cada um faria
**um lançamento só** — provisão (2.1.04.02/2.1.04.06) × Caixa/Bancos
(1.1.01), sem a perna de despesa formal que `efetivar_provisao` já faz
(`reconhecer_despesa_efetivacao`, débito na despesa × crédito no ativo
diferido). Ligar assim, sem essa perna, moveria dinheiro da provisão pro
caixa sem NUNCA reconhecer a despesa real na DRE — o oposto do que a
auditoria inteira defendeu. Gatilho natural, se ligados: `execucao_montagem`
na conclusão da etapa "17" (Montagem) — hoje sem NENHUM campo de valor
nesse ponto, precisaria de um novo, tipo o "informe o valor efetivamente
gasto" do Efetivar; `pagamento_fabrica` não tem gatilho natural nenhum na
aplicação — o pagamento a fornecedor que existe (`/api/financeiro/
pagar-fornecedor`, evento `pagamento_fornecedor`, DIFERENTE deste) baixa a
conta genérica 2.1.01 (Fornecedores a Pagar), não a provisão 2.1.04.06
diretamente. Como o item 6 (ACHADO-33) restaurou o Efetivar genérico pra
Montagem e pra Fábrica — que já faz as duas pernas certas, com
`forma_pagamento` à escolha (direto ou a_prazo) — os dois eventos mortos
podem já ser puramente redundantes com o mecanismo genérico.
*Adiado:* decisão do Marcelo — ligar (com a perna de despesa corrigida) ou
remover da tabela `EVENTOS` os dois.

**LP-12 · Desmembramento em fases nas etapas futuras.**
O desmembramento abre dois braços na venda e para por ali: as etapas
seguintes continuam tratando o projeto como um só. A aprovação financeira
passa a ser por fase, e as liberações também, com valor **proporcional à
fase**.
*Delimitação já dada pelo Marcelo, e é ela que torna o item viável:* **as
contas de provisão NÃO se desmembram** — a contabilidade continua
consolidada por projeto. O que ganha fase é a camada de acionamento. Sem
migration de plano de contas, sem rateio contábil.
*Falta decidir:* proporcional a quê — valor de contrato da fase, CFO da
fase, ou número de ambientes.
*Adiado:* é produto, não defeito; toca todas as etapas pós-venda.
(Marcelo, 02/09, percurso do `v2026.09.02-beta1`.)

**LP-13 · Tela única de Provisões por projeto.**
Hoje há quatro caminhos para o mesmo estado — Financeiro em leitura, modal
de Reconciliação do projeto, tabela da Conciliação Final, e a Fila. Essa
multiplicidade produziu, sozinha, o **ACHADO-26, 32, 33 e 41**. O alvo: uma
tela por projeto onde tudo acontece — ver, efetivar, revisar, resolver, dar
veredito — e link para ela onde hoje há modal ou tabela editável. O botão
"Resolver" volta e leva até lá, com a rubrica em foco.
Resolve o **ACHADO-37** (a fila empilhando todos os projetos) de graça.
*Adiado:* é redesenho, não conserto — e mexeria justamente na tela que
acabou de ser estabilizada. Desenho completo na Parte A do
`TAREFA_CONCILIACAO_UI.md`. (Marcelo, 01/09, e reafirmado em 02/09.)


**LP-14 · Evento de término por etapa, com oferta de transferência.**
Pedido do Marcelo (02/09): *toda etapa precisa ter um evento que caracterize
seu término, e sempre que terminar deve aparecer um popup informando o
término e oferecendo a transferência de responsabilidade.*
Hoje a transferência é um ato avulso, procurado pelo usuário quando ele
lembra — foi tentando fazê-la fora de hora que o ACHADO-46 apareceu.
*O que o item exige antes de existir:* um levantamento de quais das 21
etapas têm hoje um evento de término identificável e quais terminam por
inferência (status mudou, alguém clicou). Sem esse mapa, "toda etapa" não
tem alcance definido.
*Adiado:* é fluxo novo em todas as etapas do ciclo, não conserto. Depende do
ACHADO-46/47 estarem prontos — sem papéis declarados, a oferta de
transferência não teria a quem oferecer.
(Marcelo, 02/09, testando o Ciclo.)


---

## Fechados — não são adiamento, e por isso não estão na lista acima

- **Aditivo criado manualmente entre a assinatura e o PE.** DECIDIDO em
  31/08: **não entra**. O aditivo continua nascendo só do PE. Motivo e
  consequências em `DESENVOLVIMENTOS.md`. Reabre-se com número se o caso
  real aparecer com frequência.
- **ACHADO-15.** Aposentado em 31/08: a divergência de meio de ciclo é o
  modelo, não defeito.
