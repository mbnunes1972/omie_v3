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

---

## Fechados — não são adiamento, e por isso não estão na lista acima

- **Aditivo criado manualmente entre a assinatura e o PE.** DECIDIDO em
  31/08: **não entra**. O aditivo continua nascendo só do PE. Motivo e
  consequências em `DESENVOLVIMENTOS.md`. Reabre-se com número se o caso
  real aparecer com frequência.
- **ACHADO-15.** Aposentado em 31/08: a divergência de meio de ciclo é o
  modelo, não defeito.
