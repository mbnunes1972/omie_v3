# Conciliação de Custo de Fábrica do PE na AF2 + Complemento de Projeto por Fase + Crédito a Clientes (2026-08-14)

## Demanda
O Projeto Executivo (PE) pode revelar que o Custo de Fábrica (CFO) saiu diferente do vendido —
por ambiente, e o projeto pode estar desmembrado em várias fases (`ParcelaProjeto`), cada uma
com seu próprio conjunto de ambientes, liberadas independentemente. Hoje isso não tem decisão
formal: a AF2 (11d) só **mostra** a divergência (read-only) e a Conferência (etapa 12) ajusta a
provisão sozinha, sem repasse ao cliente e sem trilha de decisão. Demanda do usuário (Marcelo):
dar à AF2 um mecanismo de decisão explícito — **Manter / Estornar / Absorver / Cobrar** — por
diferença, com lançamento contábil real para os casos que envolvem o cliente, granularidade por
fase (o desmembramento existe justamente para liberar fases independentemente, a decisão
financeira precisa acompanhar), e trilha auditável.

## Como se chegou a este desenho (contexto da discussão)
Levantamento do estado atual (ver achados abaixo) mudou o escopo do pedido original:
- "AF2" já é o nome oficial da etapa **11d** (`mod_ciclo.py:166`, `ETAPAS_APROVACAO_FINANCEIRA`) —
  a tela "Comparar Valores" já existe, hoje read-only. Não cria tela nova; **estende essa**.
- Dos 4 tratamentos, só 2 precisavam de mecanismo novo: **Manter/Absorver** já são o comportamento
  padrão de hoje (a Conferência ajusta a provisão de Custo de Fábrica pro valor real,
  `ajustar_provisao_delta`, `mod_contabil.py:1253-1295`, independente do sinal) — só ganham um
  clique que registra a decisão, sem lançamento próprio.
- O mesmo XML de PE alimenta a comparação de **venda** (11c, `mod_pe_comparacao.montar_comparacao_venda`)
  e a de **custo de fábrica** (11d/AF2, `mod_pe_comparacao.montar_comparacao_pe`) — é o mesmo
  parser do pool, extraindo campos diferentes (spec `docs/superpowers/specs/ciclo/
  2026-07-21-revisao-pe-venda-renegociacao-design.md:20-21`). Isso permite tratar **ambiente que
  mudou de valor** (a comparação de venda já resolve isso, via o fator proporcional de
  `_complemento_diferencas`, `main.py:14625-14686`) e **ambiente/peça novo sem contratado
  correspondente** (entra pelo valor cheio) **no mesmo mecanismo** — o "Complemento de Projeto".
- O mecanismo de Complemento PE (`Orcamento.complemento_pe=1`, hoje ligado à 11e) existe, mas é
  **1 por projeto inteiro** (não por fase) e **deliberadamente sem lançamento contábil** (decisão
  de 21/07 — "acerto na liquidação/NF-e"). Este desenho **generaliza** esse mecanismo: passa a
  ser por fase e **ganha lançamento contábil real**, seguindo a mesma dinâmica do contrato
  principal (provisiona na assinatura do aditivo, efetiva no matching pleno da NF-e do
  complemento) — decisão do usuário: "este é um sistema gerencial cuja maior importância é
  registrar o fluxo financeiro".
- Estorno **não** entra nesse mecanismo (decisão explícita do usuário: "cobrança entra junto,
  estorno mantém separado") — fica num lançamento manual e imediato, numa conta nova.

## Decisões

### 1. UI — estende a AF2 existente, não cria tela nova
A tela "Comparar Valores" (11d, `static/index.html:19852`) ganha os 4 botões de decisão por
ambiente/diferença, dentro da fase selecionada. Evita colisão de nome com a AF2 já estabelecida
em código/specs/DEV_LOG.

### 2. Granularidade — por FASE, decisão por ambiente dentro dela
A decisão é tomada **por ambiente**, mas a AF2 (11d) só é considerada concluída quando **toda
fase conhecida do projeto** (via `ParcelaAmbiente`, `database.py:855-862`) tem decisão registrada
para todo ambiente com PE carregado. Projeto não desmembrado = uma fase implícita (o projeto
inteiro). Fases podem já existir antes da 11d rodar — o desmembramento é liberado desde a etapa
9/10 e reforçado na 11c (`static/index.html:18032-18034,19520-19528`), então não há problema de
ordem.

### 3. Os 4 tratamentos

| Tratamento | Lançamento | Quando |
|---|---|---|
| **Manter** (economia, loja fica) | Nenhum — só grava decisão | Diferença favorável, loja decide não repassar |
| **Absorver** (prejuízo, loja assume) | Nenhum — só grava decisão | Diferença desfavorável, loja decide não cobrar |
| **Cobrar** (repassa ao cliente, positivo) | Via **Complemento de Projeto** (§4) | Diferença desfavorável que a loja decide repassar, **ou** ambiente/peça novo |
| **Estornar** (crédito ao cliente, negativo) | Via **Crédito a Clientes** (§5) — **separado do Complemento** | Diferença favorável que a loja decide devolver |

Em **Manter/Absorver**, a Conferência (etapa 12, `conferencia_pedido`, `mod_contabil.py:1425-1454`)
continua fazendo o ajuste técnico da provisão exatamente como hoje — a diferença é que ela deixa
de ser quem **decide**, só **executa** o que já foi decidido na fase (a etapa 12 vira
confirmação, não decisão).

**Regra explícita: diferença negativa nunca entra no Complemento.** Só pode ser Manter (fica com
a loja) ou Estornar (crédito separado) — evita duas rotas concorrentes pra devolver dinheiro ao
cliente. O Complemento de Projeto só recebe itens com decisão **Cobrar**.

### 4. Complemento de Projeto (generalização do Complemento PE)
- **Ambiente já contratado que mudou de valor:** reaproveita `_complemento_diferencas`
  (`main.py:14625-14686`) — fator proporcional `VAVA_contratado/VBVA_contratado` sobre o valor do
  XML novo. Esse fator já embute o desconto (global + individual) do ambiente contratado sem
  duplicar — **não copia** `desconto_pct`/`desconto_individual_pct`, mantém a lógica atual.
- **Ambiente/peça nova (sem contratado correspondente):** sem fator — entra pelo valor cheio do
  XML como item novo do complemento (é uma venda nova, não uma diferença).
- **Agregação por FASE:** ao contrário de hoje (1 complemento por projeto, gatilho manual
  `PoolAmbiente.renegociar_pe`), o complemento passa a ser **1 por fase**, populado
  automaticamente pelos ambientes daquela fase com decisão **Cobrar**. Implica em schema novo:
  `Orcamento` (quando `complemento_pe=1`) ganha amarração à fase — hoje a busca é só
  `filter_by(projeto_id, complemento_pe=1)` (`main.py:6780-6781`), sem dimensão de parcela.
- **Provisiona só na assinatura do Termo Aditivo** — não no clique "Cobrar" da AF2. Mesma
  dinâmica do contrato principal (que só provisiona na assinatura, não na proposta). O clique
  "Cobrar" só inclui o item no complemento da fase (rascunho); o lançamento contábil (as 10
  rubricas, ativo diferido) nasce quando o cliente assina o aditivo daquele complemento.
- **Efetiva por matching pleno na NF-e do complemento**, igual ao contrato principal.
- **Consequência prática:** possivelmente **vários complementos/aditivos por projeto** ao longo
  do tempo (um por fase que gerar cobrança) — o numerador `TA<data><seq>` já suporta isso.

**Decisão derivada (a confirmar com o usuário antes de implementar):** com a decisão movendo pra
AF2 por ambiente, a 11c deixa de ser ponto de decisão (`renegociar_pe` manual) e vira só
upload/comparação — a decisão única acontece na AF2. Estou assumindo essa leitura por
consistência com tudo que foi decidido; sinalizar se for diferente.

### 5. Crédito a Clientes (Estorno) — mecanismo separado, manual

**Lançamento A — no clique "Aprovar" o Estorno (imediato):**
- DÉBITO `4.3.02` Devolução de Vendas (já existe, dormente)
- CRÉDITO `2.1.11` Créditos a Clientes (conta **nova**, passivo)

**Lançamento B — na baixa (evento futuro, manual, admin/fin decide quando):**
- DÉBITO `2.1.11` Créditos a Clientes
- CRÉDITO `1.1.02` Contas a Receber (se abatido contra parcela/complemento futuro que o cliente
  ainda deve — **inclusive um Complemento de Projeto gerado depois**, por tratamento manual e
  paralelo) **ou** `1.1.01` Caixa/Bancos (se devolvido em dinheiro)

Cobrar e Estornar **nunca se compensam automaticamente**, mesmo ocorrendo na mesma fase (ex.:
ambiente novo comprado + outro ambiente mais barato na mesma fase geram **dois eventos
distintos**: entra no Complemento e cria um crédito em `2.1.11` separadamente). Se o gerente
quiser usar o crédito para abater o complemento, é o Lançamento B feito manualmente contra o
`1.1.02` gerado pelo complemento — nunca automático.

### 6. Conta nova no plano de contas
`2.1.11` **"Créditos a Clientes"** (passivo), **fora** do grupo Provisões (`2.1.04`) — por
não estar sob o prefixo `2.1.04.%`, fica automaticamente fora da varredura de
`conciliar_final` (`mod_contabil.py:1798-1824`, que itera só contas desse grupo) sem precisar de
exceção especial no código de fechamento.

### 7. Conciliação Final (etapa 21) — permite fechar com saldo pendente
Projeto pode ser dado como `concluido` mesmo com saldo em aberto em `2.1.11` — o crédito é
"evento futuro", não bloqueia o fechamento do projeto.

### 8. Decisão por fase — tabela nova e isolada
Tabela nova (ex.: `conciliacao_pe_fase`) — **não mexe** em `CicloEtapa` (`database.py:751`,
`UniqueConstraint(projeto_nome, etapa_codigo)`) nem em `ProvisaoRegistro`
(`database.py:1031-1049`, `UniqueConstraint(orcamento_id, versao)`), que são compartilhados com a
AF1 (etapa 8). Campos sugeridos: `id, projeto_nome, parcela_id, pool_ambiente_id, tipo_decisao
(manter|absorver|cobrar|estornar), diferenca_cfo, diferenca_valor_contrato, valor_aprovado,
aprovador_id, aprovado_em`. A conclusão de "11d" ganha uma checagem **derivada** (função pura,
não coluna nova em `CicloEtapa`): "toda fase do projeto tem decisão registrada para todo ambiente
com PE carregado".

### 9. Auditoria — banco E arquivo
Toda decisão/lançamento grava nos dois lugares, na mesma ação:
- `LogAcaoGerencial` (já existe, mesmo padrão usado nas outras aprovações financeiras).
- **Arquivo JSONL por projeto** (novo — pedido explícito do usuário, "arquivo separado mesmo"),
  caminho seguindo a convenção já usada para artefatos de projeto (`PROJETOS/<nome_safe>/...`,
  mesmo padrão da pasta de medição). Escrita segura sob concorrência: abrir em modo append (`'a'`) e
  escrever a linha inteira (JSON + `\n`) numa única chamada `write()` — no Linux, escrita
  `O_APPEND` de até `PIPE_BUF` bytes é atômica por chamada, então múltiplos processos/threads
  escrevendo linhas completas não se intercalam nem corrompem, sem precisar de lock de arquivo.
  Formato JSONL: `{"quando": ISO8601, "quem": usuario_id, "etapa": "11d", "parcela_id":...,
  "pool_ambiente_id":..., "tipo_decisao":..., "valor":...}`.

## Ambiente/peça nova — decisão (2026-08-14, pós-implementação da Fatia 2)
Avaliado incluir ambiente/peça nova (sem contratado correspondente) no mesmo fluxo do Complemento
de Projeto. **Decisão: fica de fora desta frente — trata-se como nova venda separada** (opção que
"sempre será uma possibilidade", nas palavras do usuário). Motivo concreto encontrado no código: o
endpoint de upload de XML pro pool (`POST` que cria `PoolAmbiente`, `main.py:10444`) tem uma trava
de contrato assinado **incondicional** (`if _contrato_assinado(nome_safe, db): ... 403`, sem
exceção — diferente dos endpoints de negociação, que já têm a exceção `complemento_pe` em vários
pontos, ex. `main.py:13802`). É um endpoint fundamental, usado por **todo** projeto pra montar o
pool inicial, com lógica delicada de detecção de duplicata (nome/hash) e prompts de
sobrescrever/renomear — abrir uma exceção ali pra permitir upload pós-assinatura é mexer numa
trava de integridade que protege o escopo vendido de adulteração, num endpoint de alto uso. Um
endpoint **novo e dedicado** seria mais seguro, mas é escopo considerável por si só (upload
próprio, amarração à fase, ainda sem desenho completo) — não compensa o risco/esforço frente à
alternativa já aceita (nova venda). Reavaliar como frente própria se a demanda aparecer forte na
prática.

## Fora de escopo desta frente
- **Fatia 2 do desmembramento** (etapas 12-16 correndo por parcela dentro de `CicloEtapa`/
  `CicloLogistico`, ainda não implementada — `docs/superpowers/specs/ciclo/
  2026-07-13-desmembramento-pe-parcial-design.md:123-140,237-243`) — a tabela nova de decisão por
  fase não depende disso e continua válida mesmo se a Fatia 2 for implementada depois (são
  problemas diferentes: essa é financeira, a Fatia 2 é operacional).
- Retrofit de juros/atualização monetária no crédito ao cliente (nominal, sem correção).
- Reconferência com PE recarregado após decisão já tomada numa fase (precisa de tratamento de
  rebase, análogo ao que já existe pros ajustes excepcionais de fábrica — não desenhado aqui).

## Riscos e casos de borda a testar
- **Ambiente em múltiplas fases:** `ParcelaAmbiente` não impede hoje (chave composta
  `parcela_id+pool_ambiente_id`) — precisa decidir/validar que um ambiente pertence a **no
  máximo uma fase ativa** antes de rodar a agregação por fase, senão a diferença conta duas vezes.
- **Idempotência dos lançamentos** — seguir o padrão do projeto (`ref` único), ex.:
  `estorno:<projeto>:<parcela_id>:<pool_ambiente_id>` e `complemento:<projeto>:<parcela_id>`.
- **Complemento de fases diferentes do mesmo projeto** — múltiplos aditivos/Termos por projeto,
  cada um com seu próprio ciclo de assinatura; garantir que o `Contrato.modelo_versao_id`/
  numeração não colidam entre eles.
- **Projeto não desmembrado** (sem `ParcelaProjeto`) — tratar como fase única (todo o pool), pra
  não quebrar o fluxo de projetos que nunca usam desmembramento.

## Testes (esboço)
- `mod_conciliacao_pe.py` (puro): cálculo de diferença por ambiente (reaproveitando
  `mod_pe_comparacao`), agregação por fase, validação de decisão, regra "negativo nunca entra no
  complemento".
- `test_contabil_credito_cliente.py`: lançamento A (débito 4.3.02/crédito 2.1.11), baixa manual
  B (crédito 1.1.02 ou 1.1.01), idempotência por `ref`, `conciliar_final` não varre `2.1.11`,
  projeto fecha com saldo pendente.
- `test_complemento_por_fase.py`: agregação de ambiente-existente-diferença + ambiente-novo numa
  mesma fase, provisiona só na assinatura do aditivo (não no clique Cobrar), efetiva na NF-e do
  complemento.
- `test_af2_decisao_por_fase.py`: gate de conclusão de 11d exige decisão em toda fase; tabela
  nova não interfere em `CicloEtapa`/`ProvisaoRegistro` nem na AF1 (regressão).
- `test_auditoria_pe_jsonl.py`: escrita concorrente segura (múltiplas threads), presença em
  paralelo no `LogAcaoGerencial`, formato JSONL parseável linha a linha.

## Decisões já tomadas (recap desta discussão, 2026-08-13/14)
- AF2 estende a tela existente (11d), sem tela nova.
- Manter/Absorver: sem lançamento próprio, Conferência (12) vira confirmação.
- Cobrar: Complemento de Projeto por fase, generaliza o Complemento PE existente, provisiona na
  assinatura do aditivo, mesma dinâmica do contrato.
- Estorno: mecanismo separado e manual, conta nova `2.1.11 Créditos a Clientes` fora do grupo
  Provisões, contrapartida `4.3.02 Devolução de Vendas`.
- Cobrar e Estornar nunca se compensam automaticamente, mesmo na mesma fase — uso do crédito pra
  abater complemento é sempre tratamento manual e paralelo.
- Conciliação Final permite fechar com saldo de crédito pendente.
- Decisão por fase em tabela nova isolada — não mexe em `CicloEtapa`/`ProvisaoRegistro`/AF1.
- Auditoria dupla: `LogAcaoGerencial` + arquivo JSONL por projeto (append atômico, sem lock).

**Confirmado (2026-08-14):** a 11c deixa de ser ponto de decisão manual (`renegociar_pe`) e vira
só upload/comparação, com a decisão única centralizada na AF2 (§4). Ambiente/peça nova fica de
fora desta frente — trata-se como nova venda separada (ver seção própria acima).

**Progresso (TDD por fatias):**
- ✅ Fatia 1 — schema (`ConciliacaoPeFase`, conta `2.1.11`) + motor puro (`mod_conciliacao_pe.py`).
- ✅ Fatia 2 — Estorno (lançamentos `registrar_credito_cliente`/`baixar_credito_cliente`) +
  Complemento por fase (`Orcamento.parcela_id`, fórmula `valor_complemento_por_fator`).
- ⏳ Fatia 3 — endpoints (decisão por ambiente/fase na AF2, complemento por fase, gancho na
  assinatura do aditivo — reaproveita `registro_venda_contrato`+`constituir_provisoes_fechamento`
  já existentes).
- ⏳ Fatia 4 — UI (tela "Comparar Valores" da AF2 ganha seletor de fase + botões de decisão).
