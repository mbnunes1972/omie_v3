# Estado da revisão do banco — Orizon One

Última atualização: 27/08/2026
Decisões de custos: https://claude.ai/code/artifact/36d8b3ec-541a-4266-908e-bb15f2b83b4b
Plano completo: https://claude.ai/code/artifact/d66ad57d-b877-4ab7-a9b0-1cdf5a18bdfc

## Onde estamos

**Dia 0 (medir) — CONCLUÍDO.** Nada foi alterado no banco até agora.
Todas as operações feitas foram leituras.

## O que a auditoria encontrou

| Medida | Valor | Leitura |
|---|---|---|
| Tabelas | 83 | — |
| FKs declaradas | 171 | schema bem normalizado, melhor que o esperado |
| Tabelas sem nenhuma FK | 1 (`periodo_contabil`) | usa padrão polimórfico `owner_id`/`owner_tipo`; correto assim |
| FKs sem índice na coluna filha | 147 de 171 | investimento no crescimento, **não** lentidão medida |
| Colunas `*_id` sem FK | 43 | triadas: 4 externas, 6 polimórficas, 10 códigos, 0 legado, **23 dívida real** |
| Índices duplicados | 0 | nada a fazer |
| Colunas 100% nulas | 132 | campos de domínio nunca preenchidos — **mapa de cobertura de testes**, não lixo |
| Maior tabela | 667 linhas (`ciclo_etapas`) | banco pequeno; índice não muda desempenho hoje |

## Ressalvas importantes

- As estatísticas do PostgreSQL estão zeradas (`n_live_tup = 0` em tabelas
  que têm dados). Consultas sobre `pg_stat_user_tables` **não são confiáveis**
  até rodar `ANALYZE` e acumular uso. Não apagar nada com base nelas.
- `pg_stat_statements` não está instalado. Sem ele não há como medir
  desempenho. Ativar antes do lançamento.
- 6 das 19 FKs propostas guardam colunas 100% nulas: estão corretas, mas
  não foram testadas contra dado real.

## Arquivos prontos, ainda não executados

| Arquivo | Conteúdo | Quando |
|---|---|---|
| `dia0_medicao.sql` | 7 leituras de diagnóstico | já rodou |
| `onda1_fks.sql` | 19 constraints + 25 índices + casos especiais | Dia 2 |
| `onda1_indices.sql` | 147 índices em 3 níveis (usar só 1 e 2) | Dia 3 |

## Os seis dias

- [x] **Dia 0** — Medir, sem alterar nada
- [x] **Dia 1** — Adotar Alembic — baseline `0001` carimbada no LOCALHOST; VPS A e B pendentes (conferir schema com diff antes de carimbar)
- [x] **Dia 2** — As 19 FKs (`onda1_fks.sql`)
- [x] **Dia 3** — Índices, níveis 1 e 2 (`onda1_indices.sql`)
- [x] **Dia 4** — Higiene: linha órfã `orcamentos.id=53`, `VACUUM ANALYZE`, `pg_stat_statements`  <-- PRÓXIMO
- [x] **Dia 5** — Congelar: regerar ERD, `schema.sql`, escrever as regras no `CLAUDE.md`

## Onda 2 — só com a versão modular, quebra o código atual

- `projetos_meta_id` inteiro no lugar das 3 referências por `nome_safe`
- Revisar as regras de exclusão das 171 FKs herdadas em `NO ACTION`
- Tabela `etapas_ciclo` para o catálogo hardcoded em `mod_ciclo.py`
- Sentinela `0` de `lido_ate_mensagem_id`: código → dado → constraint
- Aposentar o `_migrar_colunas_pg` do `database.py`

## Ambientes

| ambiente | onde | banco | papel |
|---|---|---|---|
| localhost | WSL, no Legion |  `orizon` · **PostgreSQL 18** | desenvolvimento |
| VPS A | 167.88.33.121:8765 · `orizon-a.service` |  `orizon_integracao` · PostgreSQL 16 | **Integração** |
| VPS B | 167.88.33.121:8766 · `orizon-b.service` | `orizon_homologacao` · PostgreSQL 16 | **Homologação** |
| Produção | 179.197.77.9 · Hostinger srv1832321 | `orizon_producao` · PostgreSQL 16.15 | produção, sem cliente |

Fluxo: localhost -> Integração -> Homologação -> Produção.

**Armadilhas:**
- A e B sao duas instancias na MESMA maquina, com o mesmo PostgreSQL 16.
  A maquina hospeda tambem o ArchDecorPoints.
- Nesse servidor, o banco chamado `orizon` e' o da **Integracao**, nao o de
  producao. A producao e' outra maquina.
- localhost roda PostgreSQL 18 e os servidores rodam 16. Dump do 18 NAO
  restaura no 16 — clonar o desenvolvimento para os demais e' impossivel.
  Cada banco precisa ser construido pelas migrations.

**Estado em 27/08/2026:**

| | Alembic | FKs | `integracoes_d4sign` |
|---|---|---|---|
| localhost | `0004` | 190 | sim |
| VPS A | nenhum | 169 | nao |
| VPS B | nenhum | 170 | nao |
| Producao | ? | ? | ? |

**Bloqueio atual:** a baseline `0001` e' vazia, entao `alembic upgrade head`
num banco novo nao cria nada. Substitui-la por uma migration inicial gerada
dos modelos e' a peca que falta.
