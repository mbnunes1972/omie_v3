# Agenda da Loja — plano de implementação em fatias

**Spec:** `docs/superpowers/specs/agenda/2026-08-03-agenda-da-loja-design.md`
**Regra geral:** cada fatia fecha sozinha (suíte verde, DEV_LOG, commit, push); TDD nos módulos
puros; frontend segue o padrão inline do fichário (sem modal, decisão do usuário).

## Fatia 0 — Calendário útil + config "Agenda e Capacidade"
- `mod_calendario.py` novo, puro: `eh_dia_util`, `proximo_dia_util`, `dias_uteis_entre`,
  `adicionar_dias_uteis`, `espalhar` (valor→{dia: fatia} em dias úteis). Config: seg–sex,
  `sabado_util`, `feriados[]`.
- Config da loja: seção `agenda` no `config_financeira_json`:
  `produtividade_pe_rs_dia=20000` (Projeto Executivo), `produtividade_montagem_rs_dupla_dia=7000`
  + `duplas_disponiveis=2` (Montagem), `sabado_util=false`, `feriados=[]`,
  `horizonte_capacidade_semanas=6` (Calendário útil). Painel Config → aba "Agenda" com as três
  seções tituladas (rev 2026-08-03: SEM `teto_dias_montagem` — janela vem do cronograma).
- Testes: `tests/test_calendario.py` (semana, sábado opcional, feriado, espalhamento com
  resíduo na última fatia).

## Fatia 1 — `val_liq_congelado` por fase
- `database.py`: coluna `parcela_projeto.val_liq_congelado` (Float) + migração idempotente
  (`ALTER TABLE ... IF NOT EXISTS`) + **backfill único** na migração (motor atual; logar
  projetos afetados).
- Helper em `main.py` (ou módulo): `_liquidos_contrato_por_ambiente(orcamento_id, db)` —
  espelho de `_valores_contrato_por_ambiente` com a lógica de
  `mod_comissao._liquidos_por_ambiente` (`VAVA × Val_Liq/VAVO`).
- Congelar em TODOS os caminhos de criação/split de fase (mesma proporção do Val_Cont, última
  absorve resíduo): POST /parcelas · POST /parcelas/<id>/desmembrar
  (`mod_parcelas.desmembrar_fase` ganha o segundo congelado) · `mod_retido.reter` ·
  `mod_retido.liberar` (split em ondas) · `mod_retido.confirmar`.
- Invariante testado: `Σ val_liq_congelado == Val_Liq` ao centavo, inclusive após split
  sucessivo + retenção + liberação parcial.
- Expor no GET /parcelas (perfil comercial).

## Fatia 2 — Motor de marcos + endpoint + visão Calendário
- Offsets default das subfases do PE no cronograma (frações da janela da 11: 20/40/70/85/100%),
  aplicados por `mod_cronograma.gerar_cronograma_projeto`/`garantir_cronograma` sem
  sobrescrever data já editada.
- `mod_agenda.py` puro: `marcos(projetos_data, cfg)` por setor (mapa do §3 da spec; executado
  substitui previsto).
- `GET /api/agenda?de&ate&setor`: agrega marcos por dia; tenancy por loja; consultor filtrado
  por posse; visão operacional sem R$ (via `mod_escopo.visao_do_papel`).
- Frontend: página/aba "Agenda" com seletor Calendário|Semana|Mês (Semana/Mês entram na Fatia
  3), grade do mês com badges por setor, drill-down inline do dia, chips de filtro por Setor.

## Fatia 3 — Cargas + visões Semana e Mês
- `mod_agenda.cargas_dia(...)`: entrega-no-período para os setores; Montagem E Projeto
  Executivo distribuídos pelas janelas do CRONOGRAMA (§6 da spec, rev 2026-08-03, via
  `mod_calendario.espalhar` — sem teto artificial).
- Visão Semana (linhas=setores × colunas=dias, célula com R$, drill-down inline) e visão Mês
  (cards por setor: total, nº fases, comparativo mês anterior).
- Unidade secundária (nº fases/ambientes) alternável.

## Fatia 4 — Painel Capacidade
- `mod_agenda.capacidade(...)`: duplas de montagem necessárias/dia (⌈Σ carga/produtividade⌉)
  + ocupação diária do PE (Σ carga ÷ `produtividade_pe_rs_dia`, em %), horizonte configurável.
- Painel com barras + linha de duplas disponíveis + estouros; rodapé de duplas no Calendário;
  linha de capacidade na Semana; dias-dupla e dias-PE no Mês.
- Vera antes de fechar (área sensível: valores + perfis).

## Frente separada (não bloqueia a Agenda)
- Recalibração das bases de provisão VAVO→Val_Liq (spec §11): decidir com o contador; se
  aprovada, mexer `mod_provisoes` + `mod_contabil.constituir_provisoes_venda` + NOMENCLATURA
  §3b + testes + recalibração dos % nas lojas.
