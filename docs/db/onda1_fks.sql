-- ============================================================================
-- Orizon One — Onda 1 / parte 2: as FKs faltantes da categoria E
--
-- 19 constraints diretas + 2 de chave natural (condicionais) + 2 adiadas.
-- Triagem: 43 colunas *_id sem FK -> A:4 externas  B:6 polimorficas
--          C:10 codigos de negocio  D:0 legado  E:23 divida real
--
-- METODO — NOT VALID em duas etapas:
--   ADD CONSTRAINT ... NOT VALID  toma ACCESS EXCLUSIVE por instantes e NAO
--   varre a tabela; ja passa a valer para toda gravacao nova.
--   VALIDATE CONSTRAINT           varre a tabela existente sob SHARE UPDATE
--   EXCLUSIVE, que NAO bloqueia leitura nem escrita.
--   Em uma etapa so, a tabela inteira fica travada durante a varredura.
--
-- REGRA DE EXCLUSAO — escolhida, nao herdada. As 171 FKs atuais estao todas
-- em NO ACTION por default; estas nao repetem o erro:
--   RESTRICT  relacao de negocio: impede apagar o pai que ainda tem filhos
--   SET NULL  autoria/atribuicao: apagar o usuario nao apaga o historico,
--             so desamarra o nome. Exige a coluna NULLABLE — confira abaixo.
--
-- SEGURO PARA A VERSAO ATUAL EM PRODUCAO, com uma ressalva: a partir daqui
-- o banco passa a rejeitar gravacao com referencia invalida. Ensaiar na VPS A
-- sobre clone real antes de subir.
-- ============================================================================


-- ============================================================================
-- ETAPA 0 — VERIFICACOES. Rode e leia ANTES de qualquer ALTER.
-- ============================================================================

-- 0.1  As colunas que vao receber SET NULL precisam aceitar NULL.
--      Qualquer linha aqui = trocar a regra para RESTRICT ou tornar a coluna
--      nullable antes.
SELECT table_name, column_name, is_nullable
FROM information_schema.columns
WHERE table_schema='public' AND is_nullable='NO'
  AND (table_name, column_name) IN (
    ('ciclo_etapas','responsavel_terceiro_id'),
    ('ciclo_etapas','transferencia_destino_funcionario_id'),
    ('ciclo_etapas','transferencia_destino_terceiro_id'),
    ('ciclo_etapas','transferencia_solicitada_por_usuario_id'),
    ('conversa_mensagens','destinatario_usuario_id'),
    ('conversa_mensagens','transferido_para_funcionario_id'),
    ('conversas','concluido_por_id'),
    ('conversas','criado_por_id'),
    ('conversas','responsavel_usuario_id'),
    ('segmento_config','responsavel_funcionario_id')
  );

-- 0.2  Tipos compativeis entre filho e pai (int x bigint x text quebram a FK).
SELECT c.table_name, c.column_name, c.data_type
FROM information_schema.columns c
WHERE c.table_schema='public' AND (c.table_name, c.column_name) IN (
    ('acordo_fabrica','contraparte_id'),
    ('assistencia_caso','pool_ambiente_id'),
    ('conta','centro_custo_id'),
    ('conversas','assunto_id'),
    ('conversas','rede_id'),
    ('envios_externos','template_id'),
    ('envios_externos','triagem_id'),
    ('lojas','loja_mae_id'),
    ('orcamentos','parcela_id'),
    ('ciclo_etapas','responsavel_terceiro_id'),
    ('ciclo_etapas','transferencia_destino_funcionario_id'),
    ('ciclo_etapas','transferencia_destino_terceiro_id'),
    ('ciclo_etapas','transferencia_solicitada_por_usuario_id'),
    ('conversa_mensagens','destinatario_usuario_id'),
    ('conversa_mensagens','transferido_para_funcionario_id'),
    ('conversas','concluido_por_id'),
    ('conversas','criado_por_id'),
    ('conversas','responsavel_usuario_id'),
    ('segmento_config','responsavel_funcionario_id')
  )
ORDER BY 1,2;

-- 0.3  CHAVE NATURAL: as FKs para projetos_meta.nome_safe so existem se
--      houver UNIQUE nessa coluna. Se voltar vazio, veja a ETAPA 3.
SELECT tc.constraint_name, tc.constraint_type
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage k
  ON k.constraint_name = tc.constraint_name AND k.table_schema = tc.table_schema
WHERE tc.table_schema='public' AND tc.table_name='projetos_meta'
  AND k.column_name='nome_safe'
  AND tc.constraint_type IN ('PRIMARY KEY','UNIQUE');


-- ============================================================================
-- ETAPA 1 — AS 19 CONSTRAINTS DIRETAS  (todas com 0 orfaos confirmados)
-- ============================================================================

-- negocio
ALTER TABLE acordo_fabrica
  ADD CONSTRAINT fk_acordo_fabrica_contraparte_id
  FOREIGN KEY (contraparte_id) REFERENCES contraparte_financeira (id)
  ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

-- negocio
ALTER TABLE assistencia_caso
  ADD CONSTRAINT fk_assistencia_caso_pool_ambiente_id
  FOREIGN KEY (pool_ambiente_id) REFERENCES pool_ambientes (id)
  ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

-- negocio
ALTER TABLE conta
  ADD CONSTRAINT fk_conta_centro_custo_id
  FOREIGN KEY (centro_custo_id) REFERENCES centro_custo (id)
  ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

-- negocio
ALTER TABLE conversas
  ADD CONSTRAINT fk_conversas_assunto_id
  FOREIGN KEY (assunto_id) REFERENCES assuntos (id)
  ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

-- negocio
ALTER TABLE conversas
  ADD CONSTRAINT fk_conversas_rede_id
  FOREIGN KEY (rede_id) REFERENCES redes (id)
  ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

-- negocio
ALTER TABLE envios_externos
  ADD CONSTRAINT fk_envios_externos_template_id
  FOREIGN KEY (template_id) REFERENCES template_mensagem (id)
  ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

-- negocio
ALTER TABLE envios_externos
  ADD CONSTRAINT fk_envios_externos_triagem_id
  FOREIGN KEY (triagem_id) REFERENCES triagem_entradas (id)
  ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

-- negocio (auto-FK)
ALTER TABLE lojas
  ADD CONSTRAINT fk_lojas_loja_mae_id
  FOREIGN KEY (loja_mae_id) REFERENCES lojas (id)
  ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

-- negocio
ALTER TABLE orcamentos
  ADD CONSTRAINT fk_orcamentos_parcela_id
  FOREIGN KEY (parcela_id) REFERENCES parcela_projeto (id)
  ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

-- atribuicao
ALTER TABLE ciclo_etapas
  ADD CONSTRAINT fk_ciclo_etapas_responsavel_terceiro_id
  FOREIGN KEY (responsavel_terceiro_id) REFERENCES terceiros (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- atribuicao
ALTER TABLE ciclo_etapas
  ADD CONSTRAINT fk_ciclo_etapas_transferencia_destino_funcionario_id
  FOREIGN KEY (transferencia_destino_funcionario_id) REFERENCES funcionarios (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- atribuicao
ALTER TABLE ciclo_etapas
  ADD CONSTRAINT fk_ciclo_etapas_transferencia_destino_terceiro_id
  FOREIGN KEY (transferencia_destino_terceiro_id) REFERENCES terceiros (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- auditoria
ALTER TABLE ciclo_etapas
  ADD CONSTRAINT fk_ciclo_etapas_transferencia_solicitada_por_usuario_id
  FOREIGN KEY (transferencia_solicitada_por_usuario_id) REFERENCES usuarios (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- atribuicao
ALTER TABLE conversa_mensagens
  ADD CONSTRAINT fk_conversa_mensagens_destinatario_usuario_id
  FOREIGN KEY (destinatario_usuario_id) REFERENCES usuarios (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- atribuicao
ALTER TABLE conversa_mensagens
  ADD CONSTRAINT fk_conversa_mensagens_transferido_para_funcionario_id
  FOREIGN KEY (transferido_para_funcionario_id) REFERENCES funcionarios (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- auditoria
ALTER TABLE conversas
  ADD CONSTRAINT fk_conversas_concluido_por_id
  FOREIGN KEY (concluido_por_id) REFERENCES usuarios (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- auditoria
ALTER TABLE conversas
  ADD CONSTRAINT fk_conversas_criado_por_id
  FOREIGN KEY (criado_por_id) REFERENCES usuarios (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- atribuicao
ALTER TABLE conversas
  ADD CONSTRAINT fk_conversas_responsavel_usuario_id
  FOREIGN KEY (responsavel_usuario_id) REFERENCES usuarios (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- atribuicao
ALTER TABLE segmento_config
  ADD CONSTRAINT fk_segmento_config_responsavel_funcionario_id
  FOREIGN KEY (responsavel_funcionario_id) REFERENCES funcionarios (id)
  ON DELETE SET NULL ON UPDATE CASCADE NOT VALID;

-- --- validacao, uma a uma, sem travar leitura nem escrita ---
ALTER TABLE acordo_fabrica VALIDATE CONSTRAINT fk_acordo_fabrica_contraparte_id;
ALTER TABLE assistencia_caso VALIDATE CONSTRAINT fk_assistencia_caso_pool_ambiente_id;
ALTER TABLE conta VALIDATE CONSTRAINT fk_conta_centro_custo_id;
ALTER TABLE conversas VALIDATE CONSTRAINT fk_conversas_assunto_id;
ALTER TABLE conversas VALIDATE CONSTRAINT fk_conversas_rede_id;
ALTER TABLE envios_externos VALIDATE CONSTRAINT fk_envios_externos_template_id;
ALTER TABLE envios_externos VALIDATE CONSTRAINT fk_envios_externos_triagem_id;
ALTER TABLE lojas VALIDATE CONSTRAINT fk_lojas_loja_mae_id;
ALTER TABLE orcamentos VALIDATE CONSTRAINT fk_orcamentos_parcela_id;
ALTER TABLE ciclo_etapas VALIDATE CONSTRAINT fk_ciclo_etapas_responsavel_terceiro_id;
ALTER TABLE ciclo_etapas VALIDATE CONSTRAINT fk_ciclo_etapas_transferencia_destino_funcionario_id;
ALTER TABLE ciclo_etapas VALIDATE CONSTRAINT fk_ciclo_etapas_transferencia_destino_terceiro_id;
ALTER TABLE ciclo_etapas VALIDATE CONSTRAINT fk_ciclo_etapas_transferencia_solicitada_por_usuario_id;
ALTER TABLE conversa_mensagens VALIDATE CONSTRAINT fk_conversa_mensagens_destinatario_usuario_id;
ALTER TABLE conversa_mensagens VALIDATE CONSTRAINT fk_conversa_mensagens_transferido_para_funcionario_id;
ALTER TABLE conversas VALIDATE CONSTRAINT fk_conversas_concluido_por_id;
ALTER TABLE conversas VALIDATE CONSTRAINT fk_conversas_criado_por_id;
ALTER TABLE conversas VALIDATE CONSTRAINT fk_conversas_responsavel_usuario_id;
ALTER TABLE segmento_config VALIDATE CONSTRAINT fk_segmento_config_responsavel_funcionario_id;


-- ============================================================================
-- ETAPA 2 — INDICES DAS NOVAS FKs
-- Toda FK nova cria uma coluna filha que tambem precisa de indice. Estes NAO
-- estao em onda1_indices.sql, que cobria apenas as 171 FKs pre-existentes.
-- ============================================================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_acordo_fabrica_contraparte_id
    ON acordo_fabrica (contraparte_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assistencia_caso_pool_ambiente_id
    ON assistencia_caso (pool_ambiente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conta_centro_custo_id
    ON conta (centro_custo_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversas_assunto_id
    ON conversas (assunto_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversas_rede_id
    ON conversas (rede_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_envios_externos_template_id
    ON envios_externos (template_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_envios_externos_triagem_id
    ON envios_externos (triagem_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lojas_loja_mae_id
    ON lojas (loja_mae_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_orcamentos_parcela_id
    ON orcamentos (parcela_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_etapas_responsavel_terceiro_id
    ON ciclo_etapas (responsavel_terceiro_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_etapas_transferencia_destino_funcionario_id
    ON ciclo_etapas (transferencia_destino_funcionario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_etapas_transferencia_destino_terceiro_id
    ON ciclo_etapas (transferencia_destino_terceiro_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_etapas_transferencia_solicitada_por_usuario_id
    ON ciclo_etapas (transferencia_solicitada_por_usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversa_mensagens_destinatario_usuario_id
    ON conversa_mensagens (destinatario_usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversa_mensagens_transferido_para_funcionario_id
    ON conversa_mensagens (transferido_para_funcionario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversas_concluido_por_id
    ON conversas (concluido_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversas_criado_por_id
    ON conversas (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversas_responsavel_usuario_id
    ON conversas (responsavel_usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_segmento_config_responsavel_funcionario_id
    ON segmento_config (responsavel_funcionario_id);


-- ============================================================================
-- ETAPA 3 — CHAVE NATURAL: as 3 colunas projeto_id -> projetos_meta.nome_safe
--
-- Estas apontam para um NOME, nao para um id. Consequencias:
--   * so e possivel com UNIQUE em projetos_meta.nome_safe (etapa 0.3)
--   * ON UPDATE CASCADE deixa de ser opcional: sem ele, renomear um projeto
--     passa a ser proibido pelo banco
--   * o unico orfao encontrado na auditoria inteira esta justamente aqui
--     (orcamentos.id=53), o que e sintoma, nao coincidencia
--
-- Duas saidas legitimas:
--   (a) declarar agora como esta, aceitando a chave textual — abaixo
--   (b) ADIAR para a Onda 2 e introduzir projetos_meta_id inteiro no lugar
-- A (b) e a correcao de verdade. A (a) protege o dado enquanto ela nao vem.
-- ============================================================================

-- Pre-requisito da opcao (a), se a etapa 0.3 voltou vazia:
-- ALTER TABLE projetos_meta ADD CONSTRAINT uq_projetos_meta_nome_safe
--   UNIQUE (nome_safe);

-- ALTER TABLE lancamento
--   ADD CONSTRAINT fk_lancamento_projeto_id
--   FOREIGN KEY (projeto_id) REFERENCES projetos_meta (nome_safe)
--   ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;
-- ALTER TABLE lancamento VALIDATE CONSTRAINT fk_lancamento_projeto_id;
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lancamento_projeto_id ON lancamento (projeto_id);

-- ALTER TABLE pool_ambientes
--   ADD CONSTRAINT fk_pool_ambientes_projeto_id
--   FOREIGN KEY (projeto_id) REFERENCES projetos_meta (nome_safe)
--   ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;
-- ALTER TABLE pool_ambientes VALIDATE CONSTRAINT fk_pool_ambientes_projeto_id;
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pool_ambientes_projeto_id ON pool_ambientes (projeto_id);


-- ============================================================================
-- ETAPA 4 — AS DUAS ADIADAS. Nao entram nesta migracao.
-- ============================================================================
--
-- 4.1  orcamentos.projeto_id  — 1 orfao real (id=53, 'Vera_Debug_ListaRefresh',
--      resto de teste E2E de 2026-08-26). Resolver a linha primeiro. Apagar o
--      orcamento e mais limpo que religar a um placeholder: o placeholder vira
--      lixo permanente que ninguem lembra de remover. Confira antes que a
--      linha nao tem filhos (parcelas, contratos) presos a ela.
--      Depois: mesma constraint da ETAPA 3.
--
-- 4.2  conversa_participantes.lido_ate_mensagem_id — 10 linhas com o sentinela
--      0 que chat/core.py:_ultimo_id_mensagem grava quando a conversa nao tem
--      mensagem. Nenhuma aponta para registro inexistente de verdade, mas
--      todas quebram uma FK ingenua. E uma danca de tres passos, NESTA ordem:
--
--        1. deploy do codigo trocando o sentinela 0 por NULL
--        2. UPDATE conversa_participantes SET lido_ate_mensagem_id = NULL
--             WHERE lido_ate_mensagem_id = 0;
--        3. so entao ADD CONSTRAINT ... ON DELETE SET NULL
--
--      Invertida a ordem, o codigo antigo volta a gravar 0 entre o passo 2 e
--      o 3 e a constraint falha. Como o passo 1 e mudanca de aplicacao, esta
--      nao e uma migracao de Onda 1 pura — ela acompanha um deploy.
-- ============================================================================

-- Ao final de tudo:
--   ANALYZE;

-- ============================================================================
-- ETAPA 5 — INDICES DAS COLUNAS POLIMORFICAS (categoria B)
--
-- As 6 colunas owner_id/destinatario_id nunca poderao ter FK — o alvo varia
-- por linha. Mas sao filtradas em toda consulta multi-tenant do Financeiro,
-- sempre em par com a coluna de tipo. Indice composto, na ordem (tipo, id):
-- o tipo tem baixa cardinalidade e vem primeiro para o indice servir tambem
-- as consultas que filtram so por ele.
--
-- Isto tambem explica por que periodo_contabil aparecia isolada no mapa ER:
-- ela nao esta orfa, ela usa o padrao polimorfico. Nao ha FK a declarar ali.
-- ============================================================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conta_owner
    ON conta (owner_tipo, owner_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_centro_custo_owner
    ON centro_custo (owner_tipo, owner_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lancamento_owner
    ON lancamento (owner_tipo, owner_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_perfil_emissao_owner
    ON perfil_emissao (owner_tipo, owner_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_periodo_contabil_owner
    ON periodo_contabil (owner_tipo, owner_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_envios_externos_destinatario
    ON envios_externos (destinatario_tipo, destinatario_id);
