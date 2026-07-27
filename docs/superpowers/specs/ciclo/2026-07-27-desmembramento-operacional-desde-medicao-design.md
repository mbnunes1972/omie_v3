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

## 2. Princípio central (decisão do lojista 2026-07-27)

**O ciclo OPERACIONAL depende da obra; o FINANCEIRO é DESACOPLADO.**
- Operacional: ambientes retidos pela obra seguram só a si; os prontos avançam
  medição→PE→produção→entrega→montagem de forma independente.
- Financeiro: os **pagamentos correm no cronograma acordado** — o atraso da obra do cliente **não
  interrompe os pagamentos devidos** (é comum o cliente quitar antes do fim da obra). Ajustes
  financeiros podem ocorrer, mas são **exceção e explícitos**, nunca disparados automaticamente pelo
  retido operacional. Logo, o desmembramento OPERACIONAL **não** reparticiona nem congela parcelas
  financeiras.

## 3. Onde nasce: a partir da SOLICITAÇÃO DE MEDIÇÃO (etapa 9)

O desmembramento operacional deve ser possível **desde a etapa 9** (não só no PE). É na medição que a
obra revela quais ambientes estão prontos. Ganchos que já existem e casam com isso:
- `projetos_meta.venda_programada` (= "obra do cliente controla a medição") e `previsao_medicao` — hoje
  no nível do PROJETO; a extensão é torná-los **por ambiente/grupo**.
- Medição **parcial** (`mod_medicao`, `ambientes_aprovados`) — já registra ambientes aprovados; passa a
  ser a porta de entrada do "grupo pronto vs grupo retido".

## 4. Modelo (reuso + o que falta)

- **Grupo operacional = reusar `ParcelaProjeto`/`ParcelaAmbiente`** como a unidade que percorre o ciclo,
  MAS sem os campos financeiros dirigindo (fração/val_cont congelados continuam sendo do desmembramento
  FINANCEIRO, opcional e separado). Alternativa: um agrupamento operacional próprio se misturar com o
  financeiro poluir — decisão de implementação (ver §7).
- **`CicloEtapa.parcela_id` passa a ser USADO no operacional:** as etapas 9–17 ganham linha por
  grupo/parcela, com status próprio. `parcela_id` NULL = projeto inteiro (legado intacto).
- **Estado novo `retido` (aguardando obra)** para o ambiente/grupo: sai do fluxo (não bloqueia os
  demais) até ser **liberado**, quando reentra na fila da sua etapa.
- **Gate de execução por grupo:** o "bloqueador invertido" (`etapa_executavel`) e o gate de execução
  passam a valer **por parcela/grupo**, não pelo projeto.

## 5. Fluxo alvo

1. Na **solicitação de medição (9)**, o operador pode **desmembrar** os ambientes em: prontos (seguem) e
   **retidos pela obra** (ficam em `retido`). Pode-se desmembrar depois também (a obra libera aos poucos).
2. Cada grupo pronto percorre medição→PE→produção→entrega→montagem com **status por grupo**.
3. Ambiente **liberado** pela obra reentra na etapa correspondente (nova medição/continuação).
4. **Financeiro segue seu cronograma** — pagamentos devidos não são interrompidos; sem repartição
   automática. Ajuste financeiro (se necessário) é ação explícita à parte.

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

1. **Reusar `ParcelaProjeto` para o operacional** (com os campos financeiros nulos/ignorados) **ou**
   criar um agrupamento operacional próprio (`grupo_operacional`)? (Menos acoplamento vs mais tabelas.)
2. O "retido pela obra" é por **ambiente** ou por **grupo** (parcela)?
3. Desmembrar exige gerência, ou o operador da medição pode? (Provável: gerência define; medidor sinaliza.)
4. Quando a obra libera, é **nova medição** do ambiente ou **continuação** do ponto onde parou?

## 8. Próximo passo

Fechar as decisões da §7 com o lojista → então fatiar (backend/TDD): (1) grupo operacional + estado
retido desde a etapa 9; (2) etapas 9–17 por grupo + gate por grupo; (3) liberação/reentrada; (4) UI.
