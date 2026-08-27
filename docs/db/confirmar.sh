#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
set -a; . ./.env; set +a
PRINC="${PGURL:?PGURL nao definido no .env}"
TESTE="${PRINC%/*}/orizon_baseline_teste"
TMP=$(mktemp -d); NOVA=""
trap '[ -n "$NOVA" ] && rm -f "$NOVA"; rm -rf "$TMP"' EXIT
ok=0; falha=0
titulo() { printf '\n\033[1m%s\033[0m\n' "$1"; }
aprova() { ok=$((ok+1));       printf '  \033[32mOK\033[0m     %s\n' "$1"; }
reprova(){ falha=$((falha+1)); printf '  \033[31mFALHA\033[0m  %s\n' "$1"; }

Q_FK="SELECT c.conrelid::regclass || ' | ' || c.conname || ' | ' || pg_get_constraintdef(c.oid)
      FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
      WHERE c.contype = 'f' AND n.nspname = 'public' ORDER BY 1;"
Q_CONS="SELECT c.conrelid::regclass || ' | ' || c.conname || ' | ' || pg_get_constraintdef(c.oid)
        FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE c.contype IN ('p','u','c') AND n.nspname = 'public'
          AND c.conrelid::regclass::text <> 'alembic_version' ORDER BY 1;"
Q_IDX="SELECT tablename || ' | ' || indexname || ' | ' || indexdef
       FROM pg_indexes WHERE schemaname = 'public'
         AND tablename <> 'alembic_version' ORDER BY 1;"
Q_COL="SELECT c.table_name || '.' || c.column_name || ' | ' || c.data_type
              || ' | null=' || c.is_nullable
              || ' | default=' || coalesce(c.column_default, '-')
       FROM information_schema.columns c
       JOIN information_schema.tables t
         ON t.table_schema = c.table_schema AND t.table_name = c.table_name
       WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
         AND c.table_name <> 'alembic_version' ORDER BY 1;"
colher() { psql "$1" -At -c "$2" 2>"$TMP/erro"; }

echo; echo "  CONFERENCIA DA ETAPA DE BASELINE — $(date '+%d/%m/%Y %H:%M')"
echo "  principal: ${PRINC##*/}    teste: ${TESTE##*/}"

titulo "1. Cadeia de migrations"
heads=$(alembic heads 2>/dev/null | grep -c '(head)')
atual=$(alembic current 2>/dev/null | head -1)
[ "$heads" = "1" ] && aprova "head unico" || reprova "$heads heads — cadeia bifurcada"
pend=$(alembic history -r current:head 2>/dev/null | grep -c '^Rev:')
if echo "$atual" | grep -q '(head)'; then
  aprova "banco principal esta no head: $atual"
elif [ "$pend" -le 2 ]; then
  aprova "estado intermediario esperado: banco na ultima migration real, head e o candidato de baseline"
  echo "       atual: $atual"
  echo "       pendente: $(alembic heads 2>/dev/null | head -1)"
else
  reprova "banco atras do head em $pend revisoes"; echo "       atual: $atual"
fi
echo "     historico:"; alembic history 2>/dev/null | sed 's/^/       /'

titulo "2. Modelos x banco principal (autogenerate)"
saida=$(alembic revision --autogenerate -m sonda_conferencia 2>&1)
NOVA=$(echo "$saida" | sed -n 's/.*Generating \(.*\.py\).*/\1/p' | tr -d ' ')
if [ -z "$NOVA" ] || [ ! -f "$NOVA" ]; then
  reprova "autogenerate nao produziu arquivo"; echo "$saida" | sed 's/^/       /'
else
  ops=$(grep -cE '^\s+op\.' "$NOVA")
  if [ "$ops" = "0" ]; then aprova "autogenerate vazio — modelos e banco identicos"
  else reprova "autogenerate gerou $ops operacoes"; grep -nE '^\s+op\.' "$NOVA" | head -40 | sed 's/^/       /'; fi
  rm -f "$NOVA"; NOVA=""
fi

titulo "3. Banco construido apenas pelas migrations (B2)"
if ! psql "$TESTE" -q -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' 2>"$TMP/erro"; then
  reprova "nao consegui limpar $TESTE"; sed 's/^/       /' "$TMP/erro"
else
  if DATABASE_URL="$TESTE" alembic upgrade head >"$TMP/up" 2>&1; then
    aprova "upgrade head do zero completou sem erro"
    nt=$(psql "$TESTE" -At -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
    if [ "${nt:-0}" -gt 50 ]; then aprova "banco construido tem $nt tabelas"
    else reprova "banco construido tem so $nt tabelas — a baseline nao criou nada"; fi
  else
    reprova "upgrade head do zero falhou"; tail -20 "$TMP/up" | sed 's/^/       /'
  fi
fi

titulo "4. Diferencas entre o principal e o construido"
compara() {
  local nome="$1" q="$2"
  colher "$PRINC" "$q" | sort > "$TMP/a"
  colher "$TESTE" "$q" | sort > "$TMP/b"
  if diff -q "$TMP/a" "$TMP/b" >/dev/null; then
    aprova "$nome identicos ($(wc -l < "$TMP/a"))"
  else
    reprova "$nome divergem  (principal $(wc -l < "$TMP/a") / construido $(wc -l < "$TMP/b"))"
    diff "$TMP/a" "$TMP/b" | head -40 | sed 's/^/       /'
  fi
}
compara "chaves estrangeiras" "$Q_FK"
compara "PK / unique / check"  "$Q_CONS"
compara "indices"              "$Q_IDX"
compara "colunas e defaults"   "$Q_COL"

titulo "5. As tres FKs dos ciclos"
for fkname in funcionarios_usuario_id_fkey redes_emitente_central_id_fkey fk_orcamentos_parcela_id; do
  achou=$(psql "$TESTE" -At -c "SELECT 1 FROM pg_constraint WHERE conname = '$fkname';")
  [ "$achou" = "1" ] && aprova "$fkname presente no banco construido" \
                     || reprova "$fkname AUSENTE no banco construido"
done

titulo "6. Testes de integridade de schema"
if git grep -lI 'pg_constraint\|inspect(' -- tests >/dev/null 2>&1; then
  aprova "existem testes de schema: $(git grep -lI 'pg_constraint\|inspect(' -- tests | tr '\n' ' ')"
else
  reprova "nenhum teste em tests/ compara metadata com o banco"
fi

titulo "7. Versionamento"
sujo=$(git status --porcelain -- migrations docs/db tests | head -20)
[ -z "$sujo" ] && aprova "migrations/, docs/db/ e tests/ commitados" \
               || { reprova "ha mudancas nao commitadas"; echo "$sujo" | sed 's/^/       /'; }
echo "     ultimos commits:"; git log --oneline -6 | sed 's/^/       /'

echo; printf "  %d OK / %d FALHA\n" "$ok" "$falha"
[ "$falha" -eq 0 ] && echo "  Etapa confirmada. Pode seguir para o B3." \
                   || echo "  NAO seguir para o B3 enquanto houver FALHA acima."
echo
