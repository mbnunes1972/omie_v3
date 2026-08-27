\echo '=============================================================='
\echo '1) TAMANHO E USO DAS TABELAS'
\echo '   seq_tup_read alto = varredura completa acontecendo de verdade.'
\echo '=============================================================='
SELECT relname                             AS tabela,
       n_live_tup                          AS linhas,
       pg_size_pretty(pg_total_relation_size(relid)) AS tamanho,
       seq_scan                            AS varreduras,
       seq_tup_read                        AS linhas_varridas,
       idx_scan                            AS usos_de_indice
FROM pg_stat_user_tables
ORDER BY seq_tup_read DESC NULLS LAST
LIMIT 30;

\echo ''
\echo '=============================================================='
\echo '2) TABELAS VAZIAS  (candidatas a eliminacao)'
\echo '=============================================================='
SELECT relname AS tabela, seq_scan AS leituras_historicas,
       n_tup_ins AS insercoes_historicas
FROM pg_stat_user_tables
WHERE n_live_tup = 0
ORDER BY 1;

\echo ''
\echo '=============================================================='
\echo '3) INDICES NUNCA USADOS'
\echo '=============================================================='
SELECT relname AS tabela, indexrelname AS indice,
       pg_size_pretty(pg_relation_size(indexrelid)) AS tamanho
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

\echo ''
\echo '=============================================================='
\echo '4) INDICES DUPLICADOS'
\echo '=============================================================='
SELECT pg_size_pretty(sum(pg_relation_size(idx))::bigint) AS desperdicio,
       array_agg(idx::regclass) AS indices_identicos
FROM (
  SELECT indexrelid AS idx,
         indrelid::text||E'\n'||indclass::text||E'\n'||indkey::text||E'\n'||
         coalesce(indexprs::text,'')||E'\n'||coalesce(indpred::text,'') AS chave
  FROM pg_index
) s
GROUP BY chave HAVING count(*) > 1
ORDER BY sum(pg_relation_size(idx)) DESC;

\echo ''
\echo '=============================================================='
\echo '5) COLUNAS VAZIAS EM 100% DAS LINHAS  (o enxugamento)'
\echo '=============================================================='
DROP TABLE IF EXISTS colunas_vazias;
CREATE TEMP TABLE colunas_vazias(tabela text, coluna text, linhas_na_tabela bigint);
DO $$
DECLARE r record; preenchidos bigint; total bigint;
BEGIN
  FOR r IN
    SELECT c.table_name AS t, c.column_name AS col
    FROM information_schema.columns c
    JOIN information_schema.tables tb
      ON tb.table_name = c.table_name AND tb.table_schema = c.table_schema
    WHERE c.table_schema='public' AND tb.table_type='BASE TABLE'
      AND c.is_nullable='YES'
  LOOP
    EXECUTE format('SELECT count(*) FROM %I', r.t) INTO total;
    CONTINUE WHEN total = 0;
    EXECUTE format('SELECT count(%I) FROM %I', r.col, r.t) INTO preenchidos;
    IF preenchidos = 0 THEN
      INSERT INTO colunas_vazias VALUES (r.t, r.col, total);
    END IF;
  END LOOP;
END $$;
SELECT * FROM colunas_vazias ORDER BY 1, 2;
DROP TABLE colunas_vazias;

\echo ''
\echo '=============================================================='
\echo '6) AS 10 MAIORES TABELAS'
\echo '=============================================================='
SELECT relname AS tabela, n_live_tup AS linhas,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       pg_size_pretty(pg_indexes_size(relid))        AS so_indices
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;

\echo ''
\echo '=============================================================='
\echo '7) CONSULTAS MAIS CARAS  (so se pg_stat_statements estiver ativo)'
\echo '=============================================================='
SELECT round(total_exec_time)::bigint AS ms_total,
       calls AS chamadas,
       round(mean_exec_time::numeric, 1) AS ms_media,
       left(query, 110) AS consulta
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 15;
