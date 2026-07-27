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

## 5. Fluxo alvo (com as decisões fechadas 2026-07-27)

1. Na **solicitação de medição (9)**, o **MEDIDOR SINALIZA** os ambientes retidos pela obra (o sinal é
   **por ambiente** — granularidade fina, decisão #2/#3). Pode sinalizar mais adiante também (a obra
   libera/segura aos poucos).
2. A **GERÊNCIA CONFIRMA** o desmembramento (decisão #3): os ambientes prontos vão para a parcela que
   **segue** e os retidos ficam numa parcela **retida** (`particionar_por_selecao` já faz a partição
   selecionados×restantes). A retido pode conter 1..N ambientes.
3. Cada parcela pronta percorre medição→PE→produção→entrega→montagem com **status por parcela**.
4. **Reconhecimento contábil acompanha:** a parcela retida tem suas provisões **diferidas** (não
   reconhece / não emite NF-e) até executar; ao executar a etapa que reconhece, o matching roda para
   aquela parcela. **Só o recebimento do cliente** corre por fora (cronograma de pagamento).
5. Obra **libera** um ambiente → **CONTINUAÇÃO de onde parou** (decisão #4): o ambiente retoma a etapa
   em que foi retido (não refaz medição do zero). A parcela dele volta a **seguir** a partir daquele
   ponto (seu `parcela_id`/status de etapa é preservado).

### 5.1 Reconciliação "retido por ambiente" × parcela (unidade)
O **sinal de retido é por AMBIENTE** (o medidor marca cada ambiente). A **parcela é o veículo** que
percorre o ciclo e carrega o reconhecimento financeiro. A gerência, ao confirmar, **materializa** os
ambientes retidos numa parcela retida e os prontos noutra — o retido "efetivo" acaba sendo a parcela,
mas a **origem do estado é o ambiente**. Ambientes retidos em momentos/etapas diferentes podem formar
parcelas distintas (a obra libera em ondas). `parcela_id` NULL segue sendo o projeto inteiro (legado).

## 6. Impactos a mapear (antes de implementar)

- **Cronograma/prazos** por grupo (o `data_prevista_conclusao` da etapa vira por parcela).
- **NF-e/entrega/produção** já têm noção de parcela no financeiro — alinhar para o operacional não
  duplicar/contradizer o financeiro.
- **Equipe/gate** (frente recém-feita): o gate de execução por etapa vira por grupo; os responsáveis
  (Mapa por ambiente) já são por ambiente — encaixam.
- **Conciliação final (21)** e o encerramento: como fecham com grupos em tempos diferentes.
- **Migração:** opt-in; projeto sem grupo roda o fluxo atual (legado intacto, como o desmembramento
  financeiro já faz).

## 7. Decisões FECHADAS (2026-07-27)

1. **Parcela UNIFICADA** — reusa `ParcelaProjeto` (operacional + reconhecimento financeiro na mesma
   unidade, §2/§4). Só os recebimentos do cliente ficam por fora.
2. **Retido por AMBIENTE** — o sinal é por ambiente (granularidade fina); a parcela materializa o grupo.
3. **Medidor SINALIZA, gerência CONFIRMA** o desmembramento.
4. **CONTINUAÇÃO de onde parou** — ambiente liberado retoma a etapa em que foi retido (não refaz).

## 8. Fatiamento (backend/TDD)

1. **Retido por ambiente + desmembrar na medição** — ✅ FEITA 2026-07-27. `SinalRetido` (por ambiente,
   medidor sinaliza) + `mod_retido.sinalizar`/`limpar_sinal`/`listar_sinais`/`confirmar` (gerência).
   `confirmar` reusa `particionar_por_selecao` + `congelar_parcelas` → parcela `aguardando` (pronta) ×
   `retido` (aguarda obra); `Σ val_cont_congelado` exato. Endpoints `POST .../retido/{sinalizar,limpar,
   confirmar}` (sinalizar/limpar = `registrar_medicao`; confirmar = `autorizar`) + sinais na GET
   `/parcelas`. **NÃO toca no razão.** Testes: `test_retido.py` (6). Primeiro split apenas (progressivo
   fica p/ a Fatia 3).
2. **Ciclo operacional por parcela** — ✅ FEITA 2026-07-27 (núcleo: o GATE). O status operacional
   segue por PARCELA (`ParcelaProjeto.status`); uma parcela `retido` fica FORA do fluxo de execução.
   `mod_retido.parcela_do_ambiente`/`ambiente_retido`/`ambientes_retidos`/`gate_operacao_ambiente`
   (legado/não desmembrado/parcela que segue ⇒ passa). Gate plugado no **upload de PE por ambiente**
   (`POST .../pe/upload`) → **409** se o ambiente está em parcela retida. Testes: `test_retido.py`
   (+2: gate unitário + endpoint 409). **Adiado p/ fatias seguintes:** linha de `CicloEtapa` por
   parcela (mudar o `UniqueConstraint` de `(projeto,etapa)` p/ incluir `parcela_id` é mudança grande
   que rippla todo o ciclo — só quando a visibilidade status-por-parcela na tela exigir) e estender o
   gate a montagem/produção (mesmo helper, outros pontos). **NÃO toca no razão.**
3. **Liberação/continuação** — ✅ FEITA 2026-07-27. A obra LIBERA ambientes retidos → a parcela
   retoma (`retido`→`aguardando`, continuação de onde parou — decisão #4). `mod_retido.liberar`:
   liberação TOTAL da parcela = flip de status; liberação PARCIAL (ondas) = **SPLIT** — os liberados
   viram parcela `aguardando`, o resto fica `retido`, reusando `congelar_parcelas` p/ manter
   `Σ val_cont_congelado` exato. Habilitado por `ParcelaAmbiente.valor_ambiente` (valor bruto por
   ambiente, gravado na confirmação → split exato sem reler o contrato). Endpoint `POST
   .../retido/liberar` (`autorizar` = gerência). Testes: `test_retido.py` (+3 = 10). **NÃO toca no
   razão.**
4. **Reconhecimento contábil por parcela (área sensível — razão)** — ✅ FEITA 2026-07-27.
   `reconhecer_despesas_nfe` ganhou `fracao` (default `None` = projeto inteiro, **byte-idêntico** ao
   legado): quando informado, limita o reconhecido de cada rubrica a `fracao × constituído`, deixando
   o resto DIFERIDO no ativo `1.1.06` — **a parcela retida fica diferida**. A fração entra no `ref`
   (`match:<proj>:fNNNN:<rubrica>`) → ao LIBERAR (fração maior), a re-emissão da NF-e reconhece só o
   **DELTA**; mesma fração é idempotente. O wiring vivo (`_fin_faturamento_segmentado_seguro`) passa
   `mod_retido.fracao_reconhecivel(db, projeto)` = `Σ val_cont_congelado(não-retidas)/Σ(todas)`
   (exato por #5; `None` se não desmembrado). **Não duplica** o fluxo financeiro de 2026-07-13 (mesma
   função de matching, agora com teto por fração). Testes: `test_fase_d2_nfe.py` (defer+delta+idemp.)
   + `test_retido.py` (`fracao_reconhecivel`). _Simplificação consciente:_ a granularidade é a fração
   ELEGÍVEL (não-retida) do projeto — NF-e verdadeiramente por-parcela (uma emissão por parcela) vem
   com a etapa-15-por-parcela da Fatia 5. **Impostos e recebimento do cliente seguem por fora (§2).**
   **Auditoria da Vera (2026-07-27) → 2 correções aplicadas:** (🔴) a **Conciliação Final (etapa 21)**
   `resolve à força` todo saldo de provisão — reconheceria a provisão de ambiente **retido** como sobra
   (receita `4.4.02`) antes da execução e deixaria o ativo `1.1.06` órfão; o endpoint `POST
   .../ciclo/21/conciliar` agora **bloqueia (409)** enquanto `mod_retido.ambientes_retidos` não estiver
   vazio (mesmo padrão do gate de PE). (🟠) o `ref` do matching fracionado passou de bucket de fração
   truncada (`f%04d`, colidível) para o **ALVO acumulado em centavos** (`:a<cents>:<rubrica>`) —
   colisão-livre por construção (frações próximas reconhecem cada delta). +`order_by(id)` em
   `fracao_reconhecivel` (soma float determinística). Testes: `test_retido.py`
   (conciliar 409), `test_fase_d2_nfe.py` (frações próximas não colidem).
5. **UI** — ✅ FEITA 2026-07-27. Modal **"Retenção por Obra"** (botão na barra do Ciclo, ao lado de
   Mapa/Equipe): (a) **não desmembrado** — lista o pool de ambientes com toggle "Marcar retido"
   (medidor → sinalizar/limpar) + botão "Confirmar desmembramento" (só gerência, `_podeAutorizarFront`);
   (b) **desmembrado** — cartões de parcela com status colorido (Segue/Retido/Em aprovação/Liquidada)
   + Val_Cont congelado + ambientes; parcela retida mostra checkboxes + "Liberar selecionados" (só
   gerência). Consome `GET /parcelas` (pool/sinais/parcelas). Sem step-up (a sessão do medidor/gerência
   já carrega a capacidade); backend enforça `registrar_medicao`/`autorizar`. `node --check` verde;
   tokens de design OK.

Cada fatia: suíte verde, DEV_LOG + spec, Vera antes de fechar (áreas sensíveis: ciclo + contábil).
