-- ============================================================================
-- Orizon One — limpeza para nova fase de testes
-- Lista de preservacao conferida contra as 81 tabelas em 28/08/2026.
--
-- Mantem estrutura, configuracao de rede/loja, plano de contas, integracoes,
-- modelos de documento e usuarios. Apaga TODO o movimento e os cadastros
-- operacionais — funcionarios incluido, por decisao de 28/08/2026: os
-- usuarios master perdem o vinculo (usuarios.funcionario_id vira NULL) e o
-- RH sera recadastrado na fase nova.
--
-- Tambem esvazia 'sessoes': todos caem da sessao ao final.
--
-- EXIGE SUPERUSUARIO: usa session_replication_role.
--
-- POR QUE DELETE E NAO TRUNCATE:
--   TRUNCATE ... CASCADE esvazia toda tabela que REFERENCIA a truncada, por
--   estrutura e nao por dado. Como usuarios.funcionario_id aponta para
--   funcionarios, o CASCADE levaria usuarios junto — e usuarios e' para ficar.
--   E TRUNCATE sem CASCADE mantem uma checagem estrutural que o
--   session_replication_role nao desliga.
--
-- conta e centro_custo FICAM na lista mesmo nascendo de migration: as
-- migrations ja foram aplicadas e nao rodam de novo. Tira-las daqui trocaria
-- a limpeza por um plano de contas vazio.
--
-- Uso:  sudo -u postgres psql -d BANCO -v ON_ERROR_STOP=1 -f docs/db/limpar_base.sql
-- ============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ---------------------------------------------------------------- FASE 1
SET session_replication_role = replica;

DO $$
DECLARE
  manter text[] := ARRAY[
    'alembic_version',
    'redes','lojas','emitente','perfil_emissao',
    'usuarios','perfil_acesso','funcoes','usuario_lojas',
    'conta','centro_custo','periodo_contabil',
    'documento_tipos','documento_modelos',
    'integracoes_clicksign','numero_conectado',
    'template_mensagem','triagem_config','segmento_config','assuntos'
  ];
  r record;
  seq text;
  quantas int := 0;
  apagadas bigint := 0;
  n bigint;
BEGIN
  FOR r IN
    SELECT table_name AS t
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
      AND table_name <> ALL(manter)
    ORDER BY table_name
  LOOP
    EXECUTE format('DELETE FROM %I', r.t);
    GET DIAGNOSTICS n = ROW_COUNT;
    quantas := quantas + 1;
    apagadas := apagadas + n;

    seq := pg_get_serial_sequence('public.' || quote_ident(r.t), 'id');
    IF seq IS NOT NULL THEN
      PERFORM setval(seq, 1, false);
    END IF;
  END LOOP;

  RAISE NOTICE '% tabelas esvaziadas, % linhas apagadas', quantas, apagadas;
END $$;

SET session_replication_role = DEFAULT;

-- ---------------------------------------------------------------- FASE 2
-- Anula, nas tabelas mantidas, as colunas que apontavam para tabelas
-- esvaziadas. Sem isso ficam referencias penduradas que violam as FKs.
DO $$
DECLARE
  manter text[] := ARRAY[
    'alembic_version',
    'redes','lojas','emitente','perfil_emissao',
    'usuarios','perfil_acesso','funcoes','usuario_lojas',
    'conta','centro_custo','periodo_contabil',
    'documento_tipos','documento_modelos',
    'integracoes_clicksign','numero_conectado',
    'template_mensagem','triagem_config','segmento_config','assuntos'
  ];
  r record;
  bloqueadas text := '';
BEGIN
  FOR r IN
    SELECT tc.table_name AS filho, kcu.column_name AS coluna,
           ccu.table_name AS pai, c.is_nullable
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
    JOIN information_schema.constraint_column_usage ccu
      ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
    JOIN information_schema.columns c
      ON c.table_schema = tc.table_schema AND c.table_name = tc.table_name
     AND c.column_name = kcu.column_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND tc.table_name  =  ANY(manter)
      AND ccu.table_name <> ALL(manter)
  LOOP
    IF r.is_nullable = 'YES' THEN
      EXECUTE format('UPDATE %I SET %I = NULL WHERE %I IS NOT NULL',
                     r.filho, r.coluna, r.coluna);
      RAISE NOTICE 'anulado %.% (apontava para %)', r.filho, r.coluna, r.pai;
    ELSE
      bloqueadas := bloqueadas || format('%s.%s -> %s; ', r.filho, r.coluna, r.pai);
    END IF;
  END LOOP;

  IF bloqueadas <> '' THEN
    RAISE EXCEPTION 'Colunas NOT NULL apontando para tabelas esvaziadas: %'
                    '  Decida caso a caso antes de rodar.', bloqueadas;
  END IF;
END $$;

COMMIT;

-- ---------------------------------------------------------------- CONFERE
\echo ''
\echo '=== o que sobrou (contagem real) ==='
SELECT table_name AS tabela,
       (xpath('/row/c/text()', query_to_xml(
          format('SELECT count(*) AS c FROM %I.%I', table_schema, table_name),
          false, true, '')))[1]::text::bigint AS linhas
FROM information_schema.tables
WHERE table_schema='public' AND table_type='BASE TABLE'
ORDER BY 2 DESC, 1;
