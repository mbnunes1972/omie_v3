# Agenda da Loja — design (v1)

**Data:** 2026-08-03 · **Status:** aprovado em debate (usuário + Fable 5), pré-implementação
**Escopo:** visão agregada, POR LOJA, dos volumes e datas de todos os cronogramas de projeto.
**Princípio central:** a Agenda é **DERIVADA** — lê os cronogramas/fases que já existem e nunca
vira segunda fonte de verdade de datas. Data errada na Agenda se corrige no cronograma do
projeto, jamais na Agenda. Única gravação nova: config de capacidade + um congelado por fase
(`val_liq_congelado`, §4).

---

## 1. Modelo mental: três naturezas de dado

| Conceito | O que é | Visão onde aparece |
|---|---|---|
| **Marco** | evento com DATA (pontual) | Calendário |
| **Carga** | VOLUME (R$ Val_Liq) distribuído num período | Semana · Mês |
| **Capacidade** | recurso necessário × disponível (duplas de montagem) | Painel Capacidade |

Um mesmo fato alimenta os três: fase com montagem 10–12/09 → marco (12/09), carga (Val_Liq da
fase espalhado em 3 dias úteis), necessidade (⌈carga/produtividade⌉ duplas/dia).

## 2. Nomenclatura (fechada)

- Módulo: **"Agenda da Loja"** (menu: "Agenda").
- Agrupamento por área: **"Setor"** (refinamento DE EXIBIÇÃO do `mod_ciclo.FAIXA_POR_ETAPA`;
  a governança interna por faixa não muda).
- Visões: **Calendário** (grade do mês, dias) · **Semana** (7 colunas) · **Mês** (consolidado).
  Navegação ‹ hoje ›. Periodicidade = a própria visão.
- Painel de dimensionamento: **"Capacidade"**. O nome "Gantt" fica reservado à v2 (alocação
  nominal por dupla).

## 3. Setores da v1 (Comercial fica FORA da v1)

| Setor | Etapas | Marcos (fonte de dado) |
|---|---|---|
| **Medição** | 9, 10 | `Projeto.previsao_medicao`; `CicloEtapa.data_prevista_conclusao` (9/10) |
| **Projeto Executivo** | 11a–11e | `data_prevista_conclusao` das subfases: 11a Planta de pontos, 11b Reunião de alinhamento, 11c Revisão de PE (entrega p/ assinatura), 11e Aprovação do PE pelo cliente (assinatura). **Gap conhecido:** o cronograma padrão hoje NÃO data as subfases — v1 aplica offsets default como frações da janela da etapa 11 (proposta: 11a 20% · 11b 40% · 11c 70% · 11d 85% · 11e 100%), editáveis pelo modal de cronograma existente |
| **Expedição** | 12–16 | `data_prevista_conclusao` (12–15); entrega da fase = `CicloLogistico.prazo_entrega` > `ParcelaProjeto.entrega_prevista` > `Projeto.data_entrega` (MESMA regra da faixa de entrega, Sessão 136) |
| **Montagem** | 17–20 | janela derivada (§6); marcos 18–20 pela `data_prevista_conclusao` |
| **Financeiro** | 8, 11d, 21 | `data_prevista_conclusao` — só marcos, sem carga |

Executado substitui previsto: etapa concluída usa `concluido_em`/datas realizadas (marco vira
"realizado", sai da carga futura).

## 4. Unidade de volume: **Val_Liq congelado por fase** (decisão do usuário)

- Unidade primária de TODA a Agenda (marcos com valor, cargas e capacidade):
  **Valor Líquido da loja** = `VAVO − Cust_Ad`. É a mesma base das comissões (venda, medição,
  PE, montagem — `mod_comissao`). `Cust_Ad` fica fora porque não carrega markup — não faz
  sentido dimensionar volume/duplas sobre ele. **Não usar `val_cont_congelado`** (contém
  `Cust_Fin`, grandeza de financiamento, não de operação).
- **Novo congelado:** `ParcelaProjeto.val_liq_congelado`, gravado NO MESMO instante em que a
  fase é criada, pela mesma lógica por ambiente de `mod_comissao._liquidos_por_ambiente`
  (`Val_Liq_Amb = VAVA × Val_Liq/VAVO`), com a última fase absorvendo o resíduo →
  `Σ val_liq_congelado == Val_Liq` exato ao centavo (mesmo invariante #5 do Val_Cont).
  Congela-se pelo mesmo motivo do Val_Cont: recalcular on-the-fly divergiria da comissão
  efetivamente paga se a proporção VAVO/Cust_Ad do projeto mudar depois.
- **Todos os caminhos que criam/dividem fase congelam também o líquido:** POST /parcelas,
  desmembramento sucessivo, `mod_retido.reter` (split), `mod_retido.liberar` (split em ondas),
  `mod_retido.confirmar` (legado). Splits repartem o `val_liq_congelado` da mãe na MESMA
  proporção usada para o Val_Cont (última absorve resíduo).
- Projeto NÃO desmembrado: usa `Val_Liq` do orçamento contratado (motor).
- **Backfill (migração única):** fases existentes sem o campo recebem o valor calculado pelo
  motor atual na migração (melhor aproximação disponível); log da migração anota os projetos
  afetados.
- Unidade secundária alternável na UI: nº de fases/projetos e nº de ambientes.

## 5. Valores na Agenda — catálogo de ITENS COM VALOR (rev 2 · 2026-08-03, feedback do usuário)

**Onde valor NÃO aparece: no Calendário.** A visão Calendário é de DATAS e STATUS (mostrar R$
no marco sem rótulo confundia — "valor de quê?"). Todo valor exibido na Agenda tem NOME DE
ITEM explícito, e vive nas visões Semana/Mês e no painel Capacidade (Fatia 3/4).

**Catálogo (proposta acordada na conversa, base da Fatia 3):**

| Item (rótulo na tela) | Natureza | Período/Data (fonte: CRONOGRAMA do projeto) | Valor |
|---|---|---|---|
| **Projeto Executivo** | carga distribuída | janela: conclusão da 10 → prevista da 11 (por fase do desmembramento) | Val_Liq da fase espalhado em dias úteis |
| **Conferência e Implantação** | carga distribuída | janela: prevista da 11 → prevista da 12 | idem |
| **Produção (saída da fábrica)** | marco valorado | data prevista de conclusão da 13 (saída) | Val_Liq da fase no dia |
| **Montagem** | carga distribuída | janela: entrega da fase → prevista da 17 | Val_Liq da fase espalhado em dias úteis |
| **Entrega ao cliente** | marco valorado | data de entrega da fase (regra da faixa) | Val_Liq da fase no dia |

- **Semana/Mês:** uma LINHA por item do catálogo (o rótulo resolve a nomenclatura — "Montagem
  R$ 42k na semana" é inequívoco), célula = Σ do item no dia/período.
- **Capacidade:** DUAS faixas — **Montagem** (duplas necessárias × disponíveis) e **Projeto
  Executivo** (ocupação diária × produtividade R$ 20k/dia) — o PE não fica órfão do "Gantt".
  Conferência/Produção não têm produtividade configurada na v1 → só volume na Semana/Mês.

## 6. Capacidade (v1 = dimensionamento; v2 = alocação nominal) — rev 2026-08-03

**Princípio (correção do usuário):** a janela de trabalho NÃO é derivada da produtividade nem
tem teto artificial — **ela vem do cronograma de entrega do projeto** (cada etapa tem sua data
prevista). O cronograma dá a necessidade de produção diária; a produtividade converte essa
necessidade em recurso necessário no período.

- **Montagem:** janela da fase = do 1º dia útil após a entrega da fase (§3-Expedição) até a
  `data_prevista_conclusao` da etapa 17 (fase com `entrega_prevista` própria desloca a janela
  junto). Carga diária = `val_liq` espalhado nos dias úteis da janela
  (`mod_calendario.espalhar`). **Duplas necessárias no dia = ⌈Σ cargas do dia ÷
  produtividade_montagem⌉**, comparadas às `duplas_disponiveis`.
- **Projeto Executivo (análogo):** janela = da conclusão da etapa 10 até a
  `data_prevista_conclusao` da 11 (subfases refinam depois). Carga diária = `val_liq`
  espalhado na janela. **Ocupação do PE no dia = Σ cargas ÷ produtividade_pe_rs_dia**
  (default R$ 20.000/dia) — mostrada como % da capacidade diária de PE.
- Painel: barras por dia (horizonte configurável, default 6 semanas) — duplas de montagem
  (linha das disponíveis, destaque nos estouros) e ocupação do PE. Resumos: rodapé do dia no
  Calendário; linha própria na Semana; no Mês, `dias-dupla` e `dias-PE` necessários vs
  disponíveis.
- **v2 (fora desta spec):** cadastro de montadores/duplas, atribuição fase→dupla→dias, Gantt
  nominal com arrastar. O desenho da v1 (carga diária POR FASE) é exatamente o insumo da v2.

## 7. Calendário útil — `mod_calendario.py` (utilitário GENÉRICO novo)

Confirmado pelo usuário: não existe hoje cálculo de dias úteis no codebase
(`prazo_contratual_dias_uteis` é só um número, sem calendário por trás). Nasce como módulo puro
e genérico — a Agenda é o primeiro consumidor; o prazo contratual e prazos de etapa podem
migrar depois (fora desta v1):

- `eh_dia_util(data, cfg)` · `proximo_dia_util(data, cfg)` ·
  `dias_uteis_entre(a, b, cfg)` · `adicionar_dias_uteis(data, n, cfg)` ·
  `espalhar(valor, inicio, n_dias_uteis, cfg) -> {data: fatia}`.
- `cfg`: dias da semana úteis (default seg–sex; sábado opcional) + **feriados** (lista de
  datas na config da loja — ENTRA na v1, é barato: uma lista editável no painel Config).

## 8. Parâmetros (config da loja, nova seção "Agenda e Capacidade")

Painel Config → aba "Agenda", separado por títulos **Projeto Executivo**, **Montagem** e
**Calendário útil** (decisão do usuário, rev 2026-08-03):

| Parâmetro | Seção | Default | Uso |
|---|---|---|---|
| `produtividade_pe_rs_dia` | Projeto Executivo | 20.000,00 | conversão carga→ocupação do PE |
| `produtividade_montagem_rs_dupla_dia` | Montagem | 7.000,00 | conversão carga→duplas |
| `duplas_disponiveis` | Montagem | 2 | linha de capacidade |
| `sabado_util` | Calendário útil | false | calendário útil |
| `feriados` | Calendário útil | [] | calendário útil |
| `horizonte_capacidade_semanas` | Calendário útil | 6 | painel Capacidade |

(`teto_dias_montagem` foi REMOVIDO na rev 2026-08-03 — a janela vem do cronograma, §6.)
Estrutura preparada para produtividades de outros setores no futuro (ex.: medições/dia).

## 9. Acesso por perfil (verificado no código)

O mecanismo existente é `main._bloqueio_comercial(ator)` (main.py) →
`mod_escopo.visao_do_papel(ator)`: quem tem escopo por ATRIBUIÇÃO (PE/Medidor/Montagem) é
visão **"operacional"** e nunca vê valores comerciais; os demais são "comercial" (admins de
tenancy, "nenhuma"). Não está em `mod_tenancy.py` — tenancy resolve LOJA; papel/visão é
`mod_escopo`. A Agenda REUSA esse mecanismo:

- **Visão comercial** (gerência, consultor…): tudo — marcos com R$, cargas, Capacidade.
  Consultor: agenda filtrada aos SEUS projetos (mesma regra de posse do restante do sistema).
- **Visão operacional** (medidor, projetista, montador): Calendário com marcos e CONTAGENS,
  **sem R$, sem Semana/Mês e sem o painel Capacidade** (duplas derivam de R$ — vazariam
  volume). Útil para o montador ver a própria semana sem expor o comercial.

> ⚠️ **DORMENTE (auditoria da Vera, 2026-08-03):** o gate `mod_escopo.escopo_por_atribuicao`
> compara `nivel` contra valores APOSENTADOS na migração Perfil-4 (`medidor`,
> `projetista_executivo`, `supervisor_montagem`) — nenhuma conta real cai em "operacional"
> hoje (débito documentado no DEV_LOG desde 2026-07-10, anterior à Agenda). O branch da
> Agenda está implementado e testado no código, mas só passa a valer quando a frente de
> re-chaveamento (nivel → Função/Mapa de Atribuições) for executada. Até lá, a proteção
> efetiva é o escopo por posse (consultor) e a tenancy por loja.

## 10. Backend (forma)

- **`mod_agenda.py` puro** (TDD): monta marcos/cargas/capacidade a partir de estruturas já
  carregadas; zero I/O.
- **1 endpoint agregador:** `GET /api/agenda?de=AAAA-MM-DD&ate=AAAA-MM-DD&setor=<opc>` →
  `{marcos: [{data, setor, etapa, projeto, cliente, fase, valor?, realizado}], cargas_dia:
  [{data, setor, valor}], capacidade: [{data, duplas_necessarias}], unidades…}` — granular por
  DIA; as três visões e as consolidações semana/mês são montadas no front a partir do mesmo
  payload. Tenancy por loja como em todo endpoint (`escopo_operacional`); valores omitidos na
  visão operacional.
- Sem tabela nova além da config (+ a coluna congelada do §4).

## 11. Parecer — bases VAVO × Val_Liq em `provisoes_orcamento` (achado do usuário, FORA do escopo da Agenda)

Verificado: **há motivo documentado** para `frete_loc/assist/ins_loc/prov_mont/prov_gar`
usarem VAVO — `docs/referencia/NOMENCLATURA.md §3b "Bases das provisões (convenção CANÔNICA)"`:
provisão de % sobre a VENDA usa VAVO; e o motor DEVE espelhar a constituição contábil
(`mod_contabil.constituir_provisoes_venda`, também VAVO — houve bug corrigido na assistência
por divergência de base). Ou seja: não é acidente, é convenção com espelho contábil e teste.

Dito isso, o argumento econômico do usuário procede (Cust_Ad não carrega markup — % sobre VAVO
provisiona sobre brinde/viagem/custo especial repassados). Migrar VAVO→Val_Liq é uma
**recalibração de negócio**, não um fix: os percentuais configurados hoje foram calibrados
sobre VAVO (mudar a base encolhe as provisões pelo fator Val_Liq/VAVO — ~88% no projeto
Norberto) e exige mexer em `mod_provisoes` + `mod_contabil.constituir_provisoes_venda` +
NOMENCLATURA §3b + testes anti-drift, com decisão sobre projetos em andamento (os snapshots de
`ProvisaoRegistro` preservam o passado; só novos registros mudariam). **Recomendação:** frente
própria, validada com o contador (e recalibrando os % junto), ANTES ou DEPOIS da Agenda —
a Agenda não depende disso: usa Val_Liq por definição própria (§4), qualquer que seja a base
das provisões.

## 12. Fora do escopo da v1 (registrado)

Comercial na Agenda; agenda consolidada da REDE; Gantt nominal por dupla (v2); produtividade
de outros setores; migração do prazo contratual para o calendário útil; recalibração das
bases de provisão (§11).
