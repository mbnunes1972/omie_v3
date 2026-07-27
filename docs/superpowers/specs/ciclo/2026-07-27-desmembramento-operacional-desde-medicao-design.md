# Desmembramento OPERACIONAL por ambiente desde a medição (design)

**Data:** 2026-07-27
**Status:** conceito em discussão (levantado pelo lojista 2026-07-27). Spec para revisão; implementação
NÃO iniciada.
**Relaciona-se com:** `ciclo/2026-07-13-desmembramento-pe-parcial-design.md` (desmembramento FINANCEIRO
na Revisão de PE) — este documento trata do lado **OPERACIONAL**, que ficou faltando.

---

## 1. Motivação (a dor)

Em móveis planejados, a **obra do cliente** frequentemente segura ALGUNS ambientes (o local ainda não
está pronto para medir/entregar/montar), enquanto outros já podem seguir. Hoje o ciclo é **do projeto
inteiro** (`CicloEtapa` = `(projeto, etapa)`), então um ambiente retido pela obra **trava todos**.

O desmembramento existente (spec 2026-07-13) resolveu o **financeiro** (parcelas = grupos de ambientes
com fração congelada do Val_Cont, aprovação/liquidação sucessivas) e é ancorado na **Revisão de PE
(11c)**. Mas: (a) começa tarde demais (PE), (b) não há estado "retido pela obra", (c) o `parcela_id` do
`CicloEtapa` quase não é usado no fluxo operacional — a **status operacional segue no nível do projeto**.

## 2. Princípio central (decisão do lojista 2026-07-27, CORRIGIDO)

Há DUAS coisas financeiras e elas se comportam diferente:

- **Reconhecimento contábil / confirmação das provisões por etapa ACOMPANHA o operacional.** A
  provisão de uma etapa só é **reconhecida quando o operacional reflete a execução** — não se
  aprova/confirma o financeiro do PE antes do PE existir. No modelo vigente (`CLAUDE.md`): no
  contrato as rubricas nascem **ativo diferido** (`1.1.06.0X × 2.1.04.0X`, sem tocar a DRE); o
  **reconhecimento pleno é na NF-e** (`reconhecer_despesas_nfe`). Logo, **etapa RETIDA ⇒ operacional
  retido + reconhecimento financeiro daquela etapa retido (diferido)**, juntos.
- **Só os RECEBIMENTOS do cliente são desacoplados.** Os pagamentos correm no cronograma acordado; o
  atraso da obra **não interrompe os pagamentos devidos** (`recebimento_venda` abate `1.1.02`,
  independente da execução).

**Consequência de modelo:** o grupo OPERACIONAL e a PARCELA financeira são a **MESMA unidade** (não
dois agrupamentos). O `status` da parcela (`aguardando → em_aprovacao → liquidada`) e a NF-e parcial
(`val_cont_congelado`) são **dirigidos pela execução operacional** daquele grupo. Só o recebimento
corre por fora.

## 3. Onde nasce: a partir da SOLICITAÇÃO DE MEDIÇÃO (etapa 9)

O desmembramento operacional deve ser possível **desde a etapa 9** (não só no PE). É na medição que a
obra revela quais ambientes estão prontos. Ganchos que já existem e casam com isso:
- `projetos_meta.venda_programada` (= "obra do cliente controla a medição") e `previsao_medicao` — hoje
  no nível do PROJETO; a extensão é torná-los **por ambiente/grupo**.
- Medição **parcial** (`mod_medicao`, `ambientes_aprovados`) — já registra ambientes aprovados; passa a
  ser a porta de entrada do "grupo pronto vs grupo retido".

## 4. Modelo — parcela UNIFICADA (operacional + reconhecimento financeiro)

Decisão de modelo (2026-07-27): a parcela é **uma unidade só** — reusa `ParcelaProjeto`/
`ParcelaAmbiente`, que já carrega o `val_cont_congelado` (base da NF-e parcial) e o `status`
(`aguardando|em_aprovacao|liquidada`). NÃO se cria um agrupamento operacional separado, porque o
reconhecimento contábil precisa ACOMPANHAR a execução operacional do grupo (§2).

- **Nasce na MEDIÇÃO (9), não só no PE:** hoje `POST /parcelas` é ancorado no PE (11c); a extensão é
  permitir criar a parcela desde a etapa 9 (o congelamento do `val_cont_congelado` já é puro,
  `mod_parcelas.congelar_parcelas`, e independe de estar no PE).
- **`CicloEtapa.parcela_id` passa a ser USADO no operacional:** as etapas 9–17 ganham linha por
  parcela, com status próprio. `parcela_id` NULL = projeto inteiro (legado intacto).
- **Estado novo `retido` (aguardando obra)** na parcela: sai do fluxo operacional (não bloqueia as
  demais) até ser **liberada**; enquanto retida, o **reconhecimento contábil daquela parcela fica
  diferido** (não emite NF-e / não reconhece despesa — segue como ativo diferido `1.1.06`).
- **Gate de execução por parcela:** o "bloqueador invertido" (`etapa_executavel`) passa a valer por
  parcela.
- **Reconhecimento dirigido pela execução:** quando a parcela executa uma etapa que reconhece
  (NF-e/etapa 15), aí sim `reconhecer_despesas_nfe` roda **para aquela parcela** (o `val_cont_congelado`
  é a base). `aguardando → em_aprovacao → liquidada` segue o operacional do grupo.
- **Recebimento do cliente por fora:** `recebimento_venda` (abate `1.1.02`) segue o cronograma de
  pagamento, independentemente de a parcela estar retida (§2).

## 5. Fluxo alvo

1. Na **solicitação de medição (9)**, o operador pode **desmembrar** os ambientes em: prontos (seguem) e
   **retidos pela obra** (ficam em `retido`). Pode-se desmembrar depois também (a obra libera aos poucos).
2. Cada grupo pronto percorre medição→PE→produção→entrega→montagem com **status por grupo**.
3. Ambiente **liberado** pela obra reentra na etapa correspondente (nova medição/continuação).
4. **Reconhecimento contábil acompanha:** a parcela retida tem suas provisões **diferidas** (não
   reconhece / não emite NF-e) até executar; ao executar a etapa que reconhece, o matching roda para
   aquela parcela. **Só o recebimento do cliente** corre por fora (cronograma de pagamento).

## 6. Impactos a mapear (antes de implementar)

- **Cronograma/prazos** por grupo (o `data_prevista_conclusao` da etapa vira por parcela).
- **NF-e/entrega/produção** já têm noção de parcela no financeiro — alinhar para o operacional não
  duplicar/contradizer o financeiro.
- **Equipe/gate** (frente recém-feita): o gate de execução por etapa vira por grupo; os responsáveis
  (Mapa por ambiente) já são por ambiente — encaixam.
- **Conciliação final (21)** e o encerramento: como fecham com grupos em tempos diferentes.
- **Migração:** opt-in; projeto sem grupo roda o fluxo atual (legado intacto, como o desmembramento
  financeiro já faz).

## 7. Decisões abertas (para fechar antes de codar)

1. ~~Reusar `ParcelaProjeto` ou criar grupo próprio?~~ **RESOLVIDA (2026-07-27): parcela UNIFICADA** —
   reusa `ParcelaProjeto` (operacional + reconhecimento financeiro são a mesma unidade, §2/§4). Só os
   recebimentos do cliente ficam por fora.
2. O "retido pela obra" é por **ambiente** ou por **grupo** (parcela)?
3. Desmembrar exige gerência, ou o operador da medição pode? (Provável: gerência define; medidor sinaliza.)
4. Quando a obra libera, é **nova medição** do ambiente ou **continuação** do ponto onde parou?

## 8. Próximo passo

Fechar as decisões da §7 com o lojista → então fatiar (backend/TDD): (1) grupo operacional + estado
retido desde a etapa 9; (2) etapas 9–17 por grupo + gate por grupo; (3) liberação/reentrada; (4) UI.
