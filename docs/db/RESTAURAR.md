# Reconstruir um ambiente do zero

Ensaiado e verificado em 28/08/2026 contra orizon_baseline_teste (docs/db/config_20260828_0206.sql).
Quatro passos: ESTRUTURA (migrations), CONFIGURACAO (dump), GABARITO (script), CONFERENCIA.

## 1. Estrutura
    createdb <banco>                      # como superusuario
    DATABASE_URL="postgresql://.../<banco>" alembic upgrade head

Resultado: 83 tabelas, 188 FKs, 251 indices. `conta`/`centro_custo` continuam VAZIOS aqui —
a migration de gabarito (`46a93cfd591b`) roda como parte deste passo, mas `redes`/`lojas`
ainda nao existem (passo 2 e' o proximo), entao ela nao encontra owner nenhum pra semear.
Isso e' esperado — nao e' o passo 2 que resolve isso, e' o 3.

## 2. Configuracao
    sudo -u postgres psql -d <banco> -v ON_ERROR_STOP=1 -f docs/db/config_AAAAMMDD.sql

O dump usa --disable-triggers: PRECISA de superusuario, e as FKs nao sao
checadas durante a insercao.

## 3. Gabarito
    DATABASE_URL="postgresql://.../<banco>" python3 scripts/aplicar_gabarito.py

Agora que `redes`/`lojas` existem (passo 2), este script aplica o MESMO gabarito que a
migration aplicaria (arvore de centro de custo + plano de contas + classificacao do grupo 5) —
so' que owner por owner, no banco de verdade, no momento certo. E' o 3º ponto de entrada de
`mod_contabil.aplicar_gabarito_completo` (docs/db/TAREFA_CENTRO_CUSTO_2.md item 6): migration
cobre banco ja povoado; criacao de loja (main.py) cobre a loja nova; este script cobre o banco
recem-restaurado, onde a migration rodou cedo demais pra ver os owners reais.

Idempotente — rodar de novo nao duplica nem sobrescreve reclassificacao manual.

## 4. Conferir
Comparar contagens contra a origem. Se baterem, a integridade se sustenta
porque na origem as FKs sao verificadas.

Ensaio de 28/08/2026 (orizon_baseline_teste, do zero + config_20260828_0206.sql + passo 3):
7 owners (1 rede + 6 lojas) — `conta` = 1120 (7 × 160), `centro_custo` = 112 (7 × 16).

## Gerar um dump novo
    pg_dump "$PGURL" --data-only --column-inserts --disable-triggers \
      -t redes -t lojas -t emitente -t perfil_emissao \
      -t usuarios -t perfil_acesso -t funcoes -t usuario_lojas \
      -t periodo_contabil \
      -t documento_tipos -t documento_modelos \
      -t integracoes_clicksign -t numero_conectado \
      -t template_mensagem -t triagem_config -t segmento_config -t assuntos \
      > docs/db/config_$(date +%Y%m%d_%H%M).sql

Os avisos de FK circular (redes<->emitente, lojas) sao esperados: sao os
ciclos + auto-referencias registrados como divida de Onda 2. Nao impedem a
restauracao com --disable-triggers.

O arquivo config_*.sql NAO vai para o git: contem credenciais de integracao.

## Plano de contas e centro de custo (migration + script, nao dump)
Desde a migration `c1ab3f8007c4` (docs/db/TAREFA_CENTRO_CUSTO.md), "conta" e
"centro_custo" SAiRAM da lista de -t acima. O dump fica so com dado de instancia:
redes, lojas, emitente, usuarios, perfis, credenciais. Se voce gerou um dump
ANTES desta mudanca (com -t conta -t centro_custo), NAO restaure-o por cima
de um banco ja migrado: os ids nao batem com o que a migration acabou de
criar e --disable-triggers deixaria o banco com FKs invalidas em silencio.

O gabarito em si nasce em DOIS momentos, nunca so' no passo 1: a migration
(`46a93cfd591b`) cobre owner que ja existia quando ela rodou; o passo 3
(`scripts/aplicar_gabarito.py`) cobre owner que so' passou a existir depois —
que num ambiente reconstruido do zero e' TODO MUNDO, porque a ordem dos
passos (Estrutura antes de Configuracao) faz a migration rodar antes de
`redes`/`lojas` existirem. Pular o passo 3 deixa o ambiente com plano de
contas vazio, sem erro nenhum avisando.
