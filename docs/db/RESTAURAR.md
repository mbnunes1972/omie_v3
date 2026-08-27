# Reconstruir um ambiente do zero

Ensaiado e verificado em 27/08/2026 contra orizon_baseline_teste.
Duas metades: a ESTRUTURA vem das migrations, a CONFIGURACAO vem do dump.

## 1. Estrutura
    createdb <banco>                      # como superusuario
    DATABASE_URL="postgresql://.../<banco>" alembic upgrade head

Resultado: 83 tabelas, 188 FKs, 251 indices. Nenhum dado.

## 2. Configuracao
    sudo -u postgres psql -d <banco> -v ON_ERROR_STOP=1 -f docs/db/config_AAAAMMDD.sql

O dump usa --disable-triggers: PRECISA de superusuario, e as FKs nao sao
checadas durante a insercao. Por isso o passo 3 nao e opcional.

## 3. Conferir
Comparar contagens contra a origem. Se baterem, a integridade se sustenta
porque na origem as FKs sao verificadas.

## Gerar um dump novo
    pg_dump "$PGURL" --data-only --column-inserts --disable-triggers \
      -t redes -t lojas -t emitente -t perfil_emissao \
      -t usuarios -t perfil_acesso -t funcoes -t usuario_lojas \
      -t conta -t centro_custo -t periodo_contabil \
      -t documento_tipos -t documento_modelos \
      -t integracoes_clicksign -t numero_conectado \
      -t template_mensagem -t triagem_config -t segmento_config -t assuntos \
      > docs/db/config_$(date +%Y%m%d).sql

Os avisos de FK circular (redes<->emitente, conta, centro_custo, lojas) sao
esperados: sao os 3 ciclos + auto-referencias registrados como divida de
Onda 2. Nao impedem a restauracao com --disable-triggers.

O arquivo config_*.sql NAO vai para o git: contem credenciais de integracao.

## Quando o plano de contas virar migration
A parte "conta" e "centro_custo" sai do dump e passa a nascer da migration
de dado. O dump fica so com dado de instancia: redes, lojas, emitente,
usuarios, perfis, credenciais.
