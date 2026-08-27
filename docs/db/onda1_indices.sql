-- ============================================================================
-- Orizon One — Onda 1 / indices nas colunas filhas das FKs
--
-- Diagnostico: 147 das 171 FKs (86%) nao tinham indice na coluna filha,
-- em 75 das 83 tabelas. Postgres indexa o lado do pai automaticamente,
-- nunca o do filho.
--
-- SEGURO PARA A VERSAO ATUAL EM PRODUCAO: criar indice nao altera nome,
-- tipo nem comportamento de nenhuma coluna. O codigo em execucao nao percebe.
--
-- CONCURRENTLY nao roda dentro de transacao. No psql, rode direto.
-- No Alembic, envolva em:  with op.get_context().autocommit_block():
--
-- ANTES DE RODAR — ordene por impacto real:
--
--   SELECT relname, n_live_tup, pg_size_pretty(pg_total_relation_size(relid))
--   FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 25;
--
-- Tabela vazia nao ganha nada com indice hoje. Comece pelas maiores.
-- ============================================================================


-- ==========================================================================
-- NIVEL 1 — MULTI-TENANT E HIERARQUIA CONTABIL  (43 indices)
-- loja_id/rede_id filtram praticamente toda consulta do sistema.
-- conta.pai_id e centro_custo.pai_id sustentam a recursao do plano de contas
-- (DRE e Balanco). conta_debito_id/conta_credito_id sao o join quente do razao.
-- Estes valem sozinhos a maior parte do ganho.
-- ==========================================================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_acordo_fabrica_loja_titular_id
    ON acordo_fabrica (loja_titular_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_adiantamento_funcionario_loja_id
    ON adiantamento_funcionario (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aditivos_loja_id
    ON aditivos (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ajuste_fabrica_loja_id
    ON ajuste_fabrica (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aprovacoes_pe_loja_id
    ON aprovacoes_pe (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assistencia_caso_loja_id
    ON assistencia_caso (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_atribuicoes_ambiente_loja_id
    ON atribuicoes_ambiente (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_centro_custo_pai_id
    ON centro_custo (pai_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_logistico_loja_id
    ON ciclo_logistico (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_clientes_loja_id
    ON clientes (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_comissao_folha_loja_id
    ON comissao_folha (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conta_pai_id
    ON conta (pai_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contratos_loja_id
    ON contratos (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_documento_fiscal_emitente_id
    ON documento_fiscal (emitente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_documento_fiscal_loja_id
    ON documento_fiscal (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_emitente_rede_id
    ON emitente (rede_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_folha_pagamento_loja_id
    ON folha_pagamento (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_fornecedores_loja_id
    ON fornecedores (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_funcionarios_loja_id
    ON funcionarios (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_funcoes_loja_id
    ON funcoes (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_integracoes_clicksign_loja_id
    ON integracoes_clicksign (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_integracoes_clicksign_rede_id
    ON integracoes_clicksign (rede_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_integracoes_d4sign_loja_id
    ON integracoes_d4sign (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_integracoes_d4sign_rede_id
    ON integracoes_d4sign (rede_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lancamento_conta_credito_id
    ON lancamento (conta_credito_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lancamento_conta_debito_id
    ON lancamento (conta_debito_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lojas_emitente_id
    ON lojas (emitente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lojas_rede_id
    ON lojas (rede_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_orcamentos_loja_id
    ON orcamentos (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_parceiro_lojas_loja_id
    ON parceiro_lojas (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_parceiros_rede_id
    ON parceiros (rede_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_perfil_emissao_emitente_id
    ON perfil_emissao (emitente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_projetos_meta_loja_id
    ON projetos_meta (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_provisao_data_prevista_loja_id
    ON provisao_data_prevista (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_recebivel_loja_id
    ON recebivel (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_redes_emitente_central_id
    ON redes (emitente_central_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_simulador_autorizacoes_loja_id
    ON simulador_autorizacoes (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_simulador_log_acessos_loja_id
    ON simulador_log_acessos (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_solicitacoes_medicao_loja_id
    ON solicitacoes_medicao (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_terceiros_loja_id
    ON terceiros (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usuario_lojas_loja_id
    ON usuario_lojas (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usuarios_loja_id
    ON usuarios (loja_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usuarios_rede_id
    ON usuarios (rede_id);

-- ==========================================================================
-- NIVEL 2 — RELACIONAIS DE NEGOCIO  (51 indices)
-- Joins de dominio: orcamento, contrato, ambiente, caso, parcela,
-- assinaturas e anexos. Segundo maior ganho.
-- ==========================================================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_adiantamento_funcionario_funcionario_id
    ON adiantamento_funcionario (funcionario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aditivos_contrato_id
    ON aditivos (contrato_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aditivos_modelo_versao_id
    ON aditivos (modelo_versao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aditivos_orcamento_complemento_id
    ON aditivos (orcamento_complemento_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aditivos_assinaturas_aditivo_id
    ON aditivos_assinaturas (aditivo_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ajuste_fabrica_acordo_id
    ON ajuste_fabrica (acordo_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ajuste_fabrica_aplicacao_ajuste_id
    ON ajuste_fabrica_aplicacao (ajuste_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aprovacoes_pe_contrato_id
    ON aprovacoes_pe (contrato_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aprovacoes_pe_modelo_versao_id
    ON aprovacoes_pe (modelo_versao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aprovacoes_pe_assinaturas_aprovacao_id
    ON aprovacoes_pe_assinaturas (aprovacao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_arquivo_pe_pool_ambiente_id
    ON arquivo_pe (pool_ambiente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assistencia_anexos_caso_id
    ON assistencia_anexos (caso_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assistencia_executores_caso_id
    ON assistencia_executores (caso_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assistencia_executores_funcionario_id
    ON assistencia_executores (funcionario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assistencia_executores_terceiro_id
    ON assistencia_executores (terceiro_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_atribuicoes_ambiente_funcionario_id
    ON atribuicoes_ambiente (funcionario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_atribuicoes_ambiente_pool_ambiente_id
    ON atribuicoes_ambiente (pool_ambiente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_atribuicoes_ambiente_terceiro_id
    ON atribuicoes_ambiente (terceiro_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_briefings_cliente_id
    ON briefings (cliente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_logistico_nfe_id
    ON ciclo_logistico (nfe_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_logistico_parcela_id
    ON ciclo_logistico (parcela_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_logistico_transicao_ciclo_logistico_id
    ON ciclo_logistico_transicao (ciclo_logistico_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_revisoes_relatorio_doc_id
    ON ciclo_revisoes (relatorio_doc_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_comissao_folha_funcionario_id
    ON comissao_folha (funcionario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conciliacao_pe_fase_parcela_id
    ON conciliacao_pe_fase (parcela_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conciliacao_pe_fase_pool_ambiente_id
    ON conciliacao_pe_fase (pool_ambiente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contratos_modelo_versao_id
    ON contratos (modelo_versao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contratos_orcamento_id
    ON contratos (orcamento_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contratos_assinaturas_contrato_id
    ON contratos_assinaturas (contrato_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversa_mensagens_documento_ref_id
    ON conversa_mensagens (documento_ref_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversas_cliente_id
    ON conversas (cliente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_documento_fiscal_danfe_doc_id
    ON documento_fiscal (danfe_doc_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_documento_fiscal_fabrica_doc_id
    ON documento_fiscal (fabrica_doc_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_documento_fiscal_xml_doc_id
    ON documento_fiscal (xml_doc_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_folha_pagamento_funcionario_id
    ON folha_pagamento (funcionario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_funcionarios_funcao_id
    ON funcionarios (funcao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_orcamento_ambientes_pool_ambiente_id
    ON orcamento_ambientes (pool_ambiente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_parceiro_lojas_parceiro_id
    ON parceiro_lojas (parceiro_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_parcela_ambiente_pool_ambiente_id
    ON parcela_ambiente (pool_ambiente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_parcela_projeto_orcamento_id
    ON parcela_projeto (orcamento_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_projetos_meta_cliente_id
    ON projetos_meta (cliente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_provisao_registro_por_id
    ON provisao_registro (por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_recebivel_orcamento_id
    ON recebivel (orcamento_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_segmento_config_template_padrao_id
    ON segmento_config (template_padrao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sinal_retido_pool_ambiente_id
    ON sinal_retido (pool_ambiente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_solicitacoes_medicao_modelo_versao_id
    ON solicitacoes_medicao (modelo_versao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_solicitacoes_medicao_assinaturas_solicitacao_id
    ON solicitacoes_medicao_assinaturas (solicitacao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_terceiros_funcao_id
    ON terceiros (funcao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_triagem_entradas_conversa_id
    ON triagem_entradas (conversa_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usuarios_funcao_id
    ON usuarios (funcao_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usuarios_funcionario_id
    ON usuarios (funcionario_id);

-- ==========================================================================
-- NIVEL 3 — AUTORIA E AUDITORIA  (53 indices)
-- Colunas *_por_id / usuario_id. Raramente filtradas em consulta,
-- mas cada uma transforma a exclusao de um usuario em varredura completa
-- da tabela. Prioridade menor; ainda assim entram.
-- ==========================================================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_acordo_fabrica_criado_por_id
    ON acordo_fabrica (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_acordo_movimento_criado_por_id
    ON acordo_movimento (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aditivos_gerado_por_id
    ON aditivos (gerado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ajuste_fabrica_criado_por_id
    ON ajuste_fabrica (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_aprovacoes_pe_gerado_por_id
    ON aprovacoes_pe (gerado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_arquivo_pe_carregado_por_id
    ON arquivo_pe (carregado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assistencia_anexos_enviado_por_id
    ON assistencia_anexos (enviado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assistencia_caso_criado_por_id
    ON assistencia_caso (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assuntos_criado_por_id
    ON assuntos (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_atribuicoes_ambiente_atribuido_por_id
    ON atribuicoes_ambiente (atribuido_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_briefings_consultor_id
    ON briefings (consultor_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_documentos_enviado_por_id
    ON ciclo_documentos (enviado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_etapas_funcao_responsavel_id
    ON ciclo_etapas (funcao_responsavel_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_etapas_responsavel_id
    ON ciclo_etapas (responsavel_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_logistico_criado_por_id
    ON ciclo_logistico (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_logistico_transicao_usuario_id
    ON ciclo_logistico_transicao (usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ciclo_revisoes_aberta_por_id
    ON ciclo_revisoes (aberta_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conciliacao_pe_fase_aprovador_id
    ON conciliacao_pe_fase (aprovador_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contato_confirmacoes_confirmado_por_id
    ON contato_confirmacoes (confirmado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contraparte_financeira_criado_por_id
    ON contraparte_financeira (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contratos_gerado_por_id
    ON contratos (gerado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversa_mensagens_autor_usuario_id
    ON conversa_mensagens (autor_usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversa_participantes_externos_criado_por_id
    ON conversa_participantes_externos (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_documento_modelos_criado_por_id
    ON documento_modelos (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_documento_tipos_criado_por_id
    ON documento_tipos (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_funcionarios_usuario_id
    ON funcionarios (usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_log_acesso_delegado_autorizador_id
    ON log_acesso_delegado (autorizador_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_log_acesso_delegado_solicitante_id
    ON log_acesso_delegado (solicitante_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_log_acoes_gerenciais_autorizador_id
    ON log_acoes_gerenciais (autorizador_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_log_acoes_gerenciais_solicitante_id
    ON log_acoes_gerenciais (solicitante_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_log_autorizacoes_autorizador_id
    ON log_autorizacoes (autorizador_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_log_autorizacoes_solicitante_id
    ON log_autorizacoes (solicitante_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_medicoes_excecao_por
    ON medicoes (excecao_por);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_medicoes_medidor_id
    ON medicoes (medidor_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_medicoes_solicitacao_por
    ON medicoes (solicitacao_por);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_orcamentos_created_by
    ON orcamentos (created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_parcela_projeto_criado_por_id
    ON parcela_projeto (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pool_ambientes_created_by
    ON pool_ambientes (created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pool_ambientes_qa_override_por_id
    ON pool_ambientes (qa_override_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_projetos_meta_criado_por_id
    ON projetos_meta (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_provisao_data_prevista_atualizado_por_id
    ON provisao_data_prevista (atualizado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_recebivel_confirmado_por_id
    ON recebivel (confirmado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_retencao_obra_criado_por_id
    ON retencao_obra (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_retencao_obra_liberado_por_id
    ON retencao_obra (liberado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sessoes_usuario_id
    ON sessoes (usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_simulador_autorizacoes_concedido_por_usuario_id
    ON simulador_autorizacoes (concedido_por_usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_simulador_autorizacoes_solicitado_por_usuario_id
    ON simulador_autorizacoes (solicitado_por_usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_simulador_log_acessos_usuario_id
    ON simulador_log_acessos (usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sinal_retido_sinalizado_por_id
    ON sinal_retido (sinalizado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_solicitacoes_medicao_gerado_por_id
    ON solicitacoes_medicao (gerado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_template_mensagem_criado_por_id
    ON template_mensagem (criado_por_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_terceiros_usuario_id
    ON terceiros (usuario_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_triagem_entradas_resolvido_por_id
    ON triagem_entradas (resolvido_por_id);

-- ============================================================================
-- DEPOIS DE RODAR — confirme que a lista zerou:
--
--   Reexecute a query de "FKs sem indice na coluna filha".
--   Resultado esperado: nenhuma linha.
--
-- E atualize as estatisticas do planejador:
--
--   ANALYZE;
-- ============================================================================
