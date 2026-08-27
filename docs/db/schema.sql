--
-- PostgreSQL database dump
--

\restrict SUG595tYhf5PKMiU1gE3e7k3GwTdjZzPVx1n9djW8FAwVVIUOHebThFzbcrDDOE

-- Dumped from database version 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)
-- Dumped by pg_dump version 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA public;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: acordo_fabrica; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acordo_fabrica (
    id integer NOT NULL,
    descricao text NOT NULL,
    tipo character varying(10) NOT NULL,
    loja_titular_id integer NOT NULL,
    conta_saldo character varying(10) NOT NULL,
    valor_implantado double precision NOT NULL,
    status character varying(12) NOT NULL,
    criado_por_id integer,
    criado_em timestamp without time zone,
    contraparte_tipo character varying(10) DEFAULT 'fabrica'::character varying,
    contraparte_nome text,
    contraparte_id integer
);


--
-- Name: acordo_fabrica_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acordo_fabrica_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acordo_fabrica_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acordo_fabrica_id_seq OWNED BY public.acordo_fabrica.id;


--
-- Name: acordo_movimento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acordo_movimento (
    id integer NOT NULL,
    acordo_id integer NOT NULL,
    tipo character varying(20) NOT NULL,
    valor double precision NOT NULL,
    lancamento_ref text,
    criado_por_id integer,
    criado_em timestamp without time zone
);


--
-- Name: acordo_movimento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acordo_movimento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acordo_movimento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acordo_movimento_id_seq OWNED BY public.acordo_movimento.id;


--
-- Name: adiantamento_funcionario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.adiantamento_funcionario (
    id integer NOT NULL,
    loja_id integer,
    funcionario_id integer NOT NULL,
    tipo character varying(14) NOT NULL,
    competencia character varying(7) NOT NULL,
    valor double precision,
    abater integer NOT NULL,
    competencia_abate character varying(7),
    quitado integer NOT NULL,
    observacao text,
    ref character varying(120),
    criado_em timestamp without time zone
);


--
-- Name: adiantamento_funcionario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.adiantamento_funcionario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: adiantamento_funcionario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.adiantamento_funcionario_id_seq OWNED BY public.adiantamento_funcionario.id;


--
-- Name: aditivos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.aditivos (
    id integer NOT NULL,
    num_aditivo text,
    projeto_nome text NOT NULL,
    contrato_id integer NOT NULL,
    orcamento_complemento_id integer NOT NULL,
    pdf_path text,
    dados_json text,
    status text NOT NULL,
    gerado_em timestamp without time zone,
    gerado_por_id integer,
    loja_id integer,
    modelo_versao_id integer
);


--
-- Name: aditivos_assinaturas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.aditivos_assinaturas (
    id integer NOT NULL,
    aditivo_id integer NOT NULL,
    parte text NOT NULL,
    nome text NOT NULL,
    cpf text NOT NULL,
    assinado_em timestamp without time zone NOT NULL,
    ip_origem text,
    hash_sha256 text NOT NULL
);


--
-- Name: aditivos_assinaturas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.aditivos_assinaturas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: aditivos_assinaturas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.aditivos_assinaturas_id_seq OWNED BY public.aditivos_assinaturas.id;


--
-- Name: aditivos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.aditivos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: aditivos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.aditivos_id_seq OWNED BY public.aditivos.id;


--
-- Name: ajuste_fabrica; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ajuste_fabrica (
    id integer NOT NULL,
    acordo_id integer,
    loja_id integer NOT NULL,
    descricao text,
    tipo character varying(10) NOT NULL,
    natureza character varying(10) NOT NULL,
    pct double precision NOT NULL,
    base character varying(16) NOT NULL,
    tratamento character varying(14) NOT NULL,
    vigencia_de timestamp without time zone,
    vigencia_ate timestamp without time zone,
    projetos_json text,
    ativo integer NOT NULL,
    criado_por_id integer,
    criado_em timestamp without time zone
);


--
-- Name: ajuste_fabrica_aplicacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ajuste_fabrica_aplicacao (
    id integer NOT NULL,
    ajuste_id integer NOT NULL,
    projeto_nome text NOT NULL,
    base_calculo double precision,
    pct_snapshot double precision,
    valor double precision NOT NULL,
    status character varying(16) NOT NULL,
    lancamento_ref text,
    acerto_ref text,
    criado_em timestamp without time zone
);


--
-- Name: ajuste_fabrica_aplicacao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ajuste_fabrica_aplicacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ajuste_fabrica_aplicacao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ajuste_fabrica_aplicacao_id_seq OWNED BY public.ajuste_fabrica_aplicacao.id;


--
-- Name: ajuste_fabrica_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ajuste_fabrica_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ajuste_fabrica_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ajuste_fabrica_id_seq OWNED BY public.ajuste_fabrica.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: aprovacoes_pe; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.aprovacoes_pe (
    id integer NOT NULL,
    num_aprovacao text,
    projeto_nome text NOT NULL,
    contrato_id integer NOT NULL,
    pdf_path text,
    dados_json text,
    status text NOT NULL,
    gerado_em timestamp without time zone,
    gerado_por_id integer,
    loja_id integer,
    modelo_versao_id integer,
    assinatura_canal character varying(16) DEFAULT 'interno'::character varying,
    clicksign_envelope_id text,
    clicksign_enviado_em timestamp without time zone,
    clicksign_signatarios_json text
);


--
-- Name: aprovacoes_pe_assinaturas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.aprovacoes_pe_assinaturas (
    id integer NOT NULL,
    aprovacao_id integer NOT NULL,
    parte text NOT NULL,
    nome text NOT NULL,
    cpf text NOT NULL,
    assinado_em timestamp without time zone NOT NULL,
    ip_origem text,
    hash_sha256 text NOT NULL
);


--
-- Name: aprovacoes_pe_assinaturas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.aprovacoes_pe_assinaturas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: aprovacoes_pe_assinaturas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.aprovacoes_pe_assinaturas_id_seq OWNED BY public.aprovacoes_pe_assinaturas.id;


--
-- Name: aprovacoes_pe_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.aprovacoes_pe_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: aprovacoes_pe_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.aprovacoes_pe_id_seq OWNED BY public.aprovacoes_pe.id;


--
-- Name: arquivo_pe; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.arquivo_pe (
    id integer NOT NULL,
    projeto_nome text NOT NULL,
    pool_ambiente_id integer NOT NULL,
    formato character varying(10) NOT NULL,
    arquivo_path text,
    valor_atualizado double precision,
    carregado_em timestamp without time zone,
    carregado_por_id integer,
    valor_venda double precision
);


--
-- Name: arquivo_pe_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.arquivo_pe_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: arquivo_pe_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.arquivo_pe_id_seq OWNED BY public.arquivo_pe.id;


--
-- Name: assistencia_anexos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistencia_anexos (
    id integer NOT NULL,
    caso_id integer NOT NULL,
    arquivo_path text NOT NULL,
    nome_original text NOT NULL,
    enviado_por_id integer,
    enviado_em timestamp without time zone NOT NULL
);


--
-- Name: assistencia_anexos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assistencia_anexos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assistencia_anexos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assistencia_anexos_id_seq OWNED BY public.assistencia_anexos.id;


--
-- Name: assistencia_caso; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistencia_caso (
    id integer NOT NULL,
    loja_id integer,
    projeto_nome text,
    sub_tipo text NOT NULL,
    motivo text NOT NULL,
    tipo_custo text NOT NULL,
    descricao text,
    valor double precision,
    status text NOT NULL,
    reembolsado_fabrica integer,
    ref_lancamento text,
    criado_em timestamp without time zone,
    realizado_em timestamp without time zone,
    criado_por_id integer,
    pool_ambiente_id integer,
    data_inicio date,
    data_fim date,
    forma_pagamento character varying DEFAULT 'direto'::character varying,
    classificacao_avulsa character varying
);


--
-- Name: assistencia_caso_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assistencia_caso_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assistencia_caso_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assistencia_caso_id_seq OWNED BY public.assistencia_caso.id;


--
-- Name: assistencia_executores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistencia_executores (
    id integer NOT NULL,
    caso_id integer NOT NULL,
    funcionario_id integer,
    terceiro_id integer
);


--
-- Name: assistencia_executores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assistencia_executores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assistencia_executores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assistencia_executores_id_seq OWNED BY public.assistencia_executores.id;


--
-- Name: assuntos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assuntos (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    nome text NOT NULL,
    criado_por_id integer,
    ativo integer NOT NULL,
    criado_em timestamp without time zone
);


--
-- Name: assuntos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assuntos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assuntos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assuntos_id_seq OWNED BY public.assuntos.id;


--
-- Name: atribuicoes_ambiente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.atribuicoes_ambiente (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    projeto_nome text NOT NULL,
    pool_ambiente_id integer,
    papel text NOT NULL,
    funcionario_id integer,
    terceiro_id integer,
    atribuido_por_id integer,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


--
-- Name: atribuicoes_ambiente_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.atribuicoes_ambiente_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: atribuicoes_ambiente_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.atribuicoes_ambiente_id_seq OWNED BY public.atribuicoes_ambiente.id;


--
-- Name: briefings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.briefings (
    id integer NOT NULL,
    cliente_id integer NOT NULL,
    projeto_nome text,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone,
    data_atendimento timestamp without time zone NOT NULL,
    consultor_id integer,
    tipo_imovel text NOT NULL,
    budget_declarado double precision NOT NULL,
    categoria_proposta text NOT NULL,
    data_entrega_desejada text NOT NULL,
    flexibilidade_prazo text NOT NULL,
    condicao_imovel text,
    metragem_m2 double precision,
    num_ambientes integer,
    ambientes_prioritarios text,
    tem_arquiteto text,
    nome_arquiteto text,
    tem_gerente_obra integer,
    end_empreendimento text,
    estilo_decisao text,
    estilo_vida text,
    relacao_projeto text,
    decisor text,
    referencias_visuais text,
    obs_referencias text,
    experiencia_anterior text,
    obs_experiencia text,
    tem_budget text,
    forma_pagamento_pref text,
    data_entrega_limite text,
    motivo_prazo text,
    nao_abre_mao text,
    restricoes text,
    obs_livres text
);


--
-- Name: briefings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.briefings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: briefings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.briefings_id_seq OWNED BY public.briefings.id;


--
-- Name: centro_custo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.centro_custo (
    id integer NOT NULL,
    owner_tipo character varying(10) NOT NULL,
    owner_id integer NOT NULL,
    codigo character varying(20) NOT NULL,
    nome text NOT NULL,
    pai_id integer,
    ativo integer,
    ordem integer,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


--
-- Name: centro_custo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.centro_custo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: centro_custo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.centro_custo_id_seq OWNED BY public.centro_custo.id;


--
-- Name: ciclo_documentos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ciclo_documentos (
    id integer NOT NULL,
    projeto_nome text NOT NULL,
    etapa_codigo text NOT NULL,
    tipo text NOT NULL,
    arquivo_path text NOT NULL,
    nome_original text NOT NULL,
    enviado_por_id integer,
    enviado_em timestamp without time zone NOT NULL
);


--
-- Name: ciclo_documentos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ciclo_documentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ciclo_documentos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ciclo_documentos_id_seq OWNED BY public.ciclo_documentos.id;


--
-- Name: ciclo_etapas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ciclo_etapas (
    id integer NOT NULL,
    projeto_nome text NOT NULL,
    etapa_codigo text NOT NULL,
    status text NOT NULL,
    responsavel_id integer,
    iniciado_em timestamp without time zone,
    concluido_em timestamp without time zone,
    data_prevista_conclusao timestamp without time zone,
    funcao_responsavel_id integer,
    responsavel_funcionario_id integer,
    observacoes text,
    responsavel_terceiro_id integer,
    transferencia_status character varying(10) DEFAULT 'nenhuma'::character varying,
    transferencia_destino_funcionario_id integer,
    transferencia_destino_terceiro_id integer,
    transferencia_solicitada_por_usuario_id integer,
    transferencia_solicitada_em timestamp without time zone
);


--
-- Name: ciclo_etapas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ciclo_etapas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ciclo_etapas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ciclo_etapas_id_seq OWNED BY public.ciclo_etapas.id;


--
-- Name: ciclo_logistico; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ciclo_logistico (
    id integer NOT NULL,
    loja_id integer,
    projeto_nome text NOT NULL,
    numero_pedido text,
    status_atual text NOT NULL,
    prazo_producao date,
    prazo_saida date,
    prazo_recebimento date,
    prazo_entrega date,
    data_producao date,
    data_saida date,
    data_recebimento date,
    data_entrega date,
    transportadora text,
    cte text,
    rastreio text,
    nfe_id integer,
    criado_em timestamp without time zone,
    criado_por_id integer,
    parcela_id integer
);


--
-- Name: ciclo_logistico_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ciclo_logistico_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ciclo_logistico_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ciclo_logistico_id_seq OWNED BY public.ciclo_logistico.id;


--
-- Name: ciclo_logistico_transicao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ciclo_logistico_transicao (
    id integer NOT NULL,
    ciclo_logistico_id integer NOT NULL,
    de_status text,
    para_status text NOT NULL,
    usuario_id integer,
    quando timestamp without time zone
);


--
-- Name: ciclo_logistico_transicao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ciclo_logistico_transicao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ciclo_logistico_transicao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ciclo_logistico_transicao_id_seq OWNED BY public.ciclo_logistico_transicao.id;


--
-- Name: ciclo_revisoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ciclo_revisoes (
    id integer NOT NULL,
    projeto_nome text NOT NULL,
    etapa_codigo text NOT NULL,
    aberta_por_id integer,
    aberta_em timestamp without time zone NOT NULL,
    relatorio_doc_id integer,
    motivo text
);


--
-- Name: ciclo_revisoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ciclo_revisoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ciclo_revisoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ciclo_revisoes_id_seq OWNED BY public.ciclo_revisoes.id;


--
-- Name: clientes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clientes (
    id integer NOT NULL,
    nome character varying(150) NOT NULL,
    cpf character varying(14),
    tipo_dest text,
    cnpj character varying(18),
    inscricao_estadual text,
    email character varying(120),
    telefone character varying(20),
    whatsapp character varying(20),
    cep character varying(9),
    logradouro character varying(200),
    numero character varying(20),
    complemento character varying(100),
    bairro character varying(100),
    cidade character varying(80),
    estado character varying(2),
    municipio_ibge character varying(7),
    observacoes text,
    inst_mesmo_residencial integer,
    inst_logradouro character varying(200),
    inst_numero character varying(20),
    inst_complemento character varying(100),
    inst_bairro character varying(100),
    inst_cidade character varying(80),
    inst_cep character varying(9),
    inst_uf character varying(2),
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone,
    loja_id integer
);


--
-- Name: clientes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clientes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clientes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clientes_id_seq OWNED BY public.clientes.id;


--
-- Name: comissao_folha; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comissao_folha (
    id integer NOT NULL,
    loja_id integer,
    funcionario_id integer NOT NULL,
    competencia character varying(7) NOT NULL,
    origem character varying(10) NOT NULL,
    papel character varying(30),
    projeto_nome text,
    etapa_codigo character varying(8),
    base double precision,
    base_ajustada double precision,
    pct double precision,
    valor double precision,
    status character varying(12) NOT NULL,
    ref_etapa character varying(120),
    criado_em timestamp without time zone,
    pct_ajustado double precision
);


--
-- Name: comissao_folha_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comissao_folha_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comissao_folha_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comissao_folha_id_seq OWNED BY public.comissao_folha.id;


--
-- Name: conciliacao_pe_fase; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conciliacao_pe_fase (
    id integer NOT NULL,
    projeto_nome text NOT NULL,
    parcela_id integer,
    pool_ambiente_id integer NOT NULL,
    tipo_decisao character varying(16) NOT NULL,
    diferenca_cfo double precision NOT NULL,
    diferenca_valor_contrato double precision NOT NULL,
    valor_aprovado double precision NOT NULL,
    aprovador_id integer,
    aprovado_em timestamp without time zone,
    criado_em timestamp without time zone
);


--
-- Name: conciliacao_pe_fase_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conciliacao_pe_fase_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conciliacao_pe_fase_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conciliacao_pe_fase_id_seq OWNED BY public.conciliacao_pe_fase.id;


--
-- Name: conta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conta (
    id integer NOT NULL,
    owner_tipo character varying(10) NOT NULL,
    owner_id integer NOT NULL,
    codigo character varying(20) NOT NULL,
    nome text NOT NULL,
    grupo integer NOT NULL,
    tipo character varying(10) NOT NULL,
    natureza character varying(8) NOT NULL,
    pai_id integer,
    ativa integer,
    ordem integer,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone,
    centro_custo_id integer,
    natureza_custo character varying(16)
);


--
-- Name: conta_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conta_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conta_id_seq OWNED BY public.conta.id;


--
-- Name: contato_confirmacoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contato_confirmacoes (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    projeto_nome text NOT NULL,
    modo character varying(20) NOT NULL,
    contatos_json text,
    confirmado_por_id integer,
    confirmado_em timestamp without time zone
);


--
-- Name: contato_confirmacoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contato_confirmacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contato_confirmacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contato_confirmacoes_id_seq OWNED BY public.contato_confirmacoes.id;


--
-- Name: contraparte_financeira; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contraparte_financeira (
    id integer NOT NULL,
    nome text NOT NULL,
    tipo character varying(10) NOT NULL,
    criado_por_id integer,
    criado_em timestamp without time zone,
    cnpj character varying(18),
    telefone character varying(20),
    email text,
    cep character varying(9),
    logradouro text,
    numero character varying(20),
    complemento text,
    bairro text,
    cidade text,
    uf character varying(2)
);


--
-- Name: contraparte_financeira_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contraparte_financeira_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contraparte_financeira_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contraparte_financeira_id_seq OWNED BY public.contraparte_financeira.id;


--
-- Name: contratos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contratos (
    id integer NOT NULL,
    num_contrato text,
    projeto_nome text NOT NULL,
    orcamento_id integer NOT NULL,
    template_path text NOT NULL,
    pdf_path text,
    endereco_instalacao text,
    pagamento_json text,
    status text NOT NULL,
    adendo text,
    gerado_em timestamp without time zone,
    gerado_por_id integer,
    loja_id integer,
    loja_snapshot_json text,
    modelo_versao_id integer,
    assinatura_canal character varying(16) DEFAULT 'interno'::character varying,
    clicksign_envelope_id text,
    clicksign_enviado_em timestamp without time zone,
    clicksign_signatarios_json text,
    snapshot_negociacao_json text,
    cliente_nome_confirmado text,
    cliente_cpf_confirmado text
);


--
-- Name: contratos_assinaturas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contratos_assinaturas (
    id integer NOT NULL,
    contrato_id integer NOT NULL,
    parte text NOT NULL,
    nome text NOT NULL,
    cpf text NOT NULL,
    assinado_em timestamp without time zone NOT NULL,
    ip_origem text,
    hash_sha256 text NOT NULL
);


--
-- Name: contratos_assinaturas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contratos_assinaturas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contratos_assinaturas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contratos_assinaturas_id_seq OWNED BY public.contratos_assinaturas.id;


--
-- Name: contratos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contratos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contratos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contratos_id_seq OWNED BY public.contratos.id;


--
-- Name: conversa_mensagens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversa_mensagens (
    id integer NOT NULL,
    conversa_id integer NOT NULL,
    autor_usuario_id integer,
    corpo text NOT NULL,
    canal character varying(20) NOT NULL,
    criado_em timestamp without time zone,
    natureza character varying(20) DEFAULT 'interacao'::character varying,
    etapa_codigo character varying(10),
    transferido_para_funcionario_id integer,
    documento_ref_id integer,
    bloqueador integer DEFAULT 0,
    resolvido_em timestamp without time zone,
    privada integer DEFAULT 0,
    corpo_cifrado text,
    canal_segmento character varying(20),
    destinatario_usuario_id integer,
    evento character varying(24)
);


--
-- Name: conversa_mensagens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conversa_mensagens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conversa_mensagens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conversa_mensagens_id_seq OWNED BY public.conversa_mensagens.id;


--
-- Name: conversa_participantes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversa_participantes (
    id integer NOT NULL,
    conversa_id integer NOT NULL,
    usuario_id integer NOT NULL,
    papel character varying(12) NOT NULL,
    arquivada integer NOT NULL,
    lido_ate_mensagem_id integer,
    adicionado_em timestamp without time zone,
    origem character varying(8) DEFAULT 'manual'::character varying,
    removido integer DEFAULT 0
);


--
-- Name: conversa_participantes_externos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversa_participantes_externos (
    id integer NOT NULL,
    conversa_id integer NOT NULL,
    nome text NOT NULL,
    telefone text,
    email text,
    meio character varying(16) NOT NULL,
    removido integer NOT NULL,
    criado_por_id integer,
    criado_em timestamp without time zone
);


--
-- Name: conversa_participantes_externos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conversa_participantes_externos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conversa_participantes_externos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conversa_participantes_externos_id_seq OWNED BY public.conversa_participantes_externos.id;


--
-- Name: conversa_participantes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conversa_participantes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conversa_participantes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conversa_participantes_id_seq OWNED BY public.conversa_participantes.id;


--
-- Name: conversas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversas (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    projeto_nome text,
    cliente_id integer,
    criado_em timestamp without time zone,
    tipo character varying(20) DEFAULT 'projeto'::character varying,
    titulo text,
    criado_por_id integer,
    assunto_tipo character varying(12) DEFAULT 'livre'::character varying,
    assunto_id integer,
    rede_id integer,
    segmento character varying(20),
    responsavel_usuario_id integer,
    urgente integer DEFAULT 0,
    origem_entrada character varying(12),
    status character varying(12) DEFAULT 'aberta'::character varying,
    concluido_por_id integer,
    concluido_em timestamp without time zone,
    conclusao_obs text
);


--
-- Name: conversas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conversas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conversas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conversas_id_seq OWNED BY public.conversas.id;


--
-- Name: documento_fiscal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documento_fiscal (
    id integer NOT NULL,
    ref text NOT NULL,
    projeto_nome text,
    tipo_documento text,
    etapa_codigo text,
    loja_id integer,
    emitente_id integer,
    status text,
    chave_nfe text,
    numero text,
    serie text,
    mensagem_sefaz text,
    erros_json text,
    xml_doc_id integer,
    danfe_doc_id integer,
    fabrica_doc_id integer,
    emitido_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


--
-- Name: documento_fiscal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documento_fiscal_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documento_fiscal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documento_fiscal_id_seq OWNED BY public.documento_fiscal.id;


--
-- Name: documento_modelos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documento_modelos (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    tipo text NOT NULL,
    versao integer NOT NULL,
    nome text,
    corpo_md text NOT NULL,
    origem_nome text,
    origem_path text,
    origem_sha256 text,
    ativo integer NOT NULL,
    criado_em timestamp without time zone,
    criado_por_id integer
);


--
-- Name: documento_modelos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documento_modelos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documento_modelos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documento_modelos_id_seq OWNED BY public.documento_modelos.id;


--
-- Name: documento_tipos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documento_tipos (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    slug text NOT NULL,
    nome text NOT NULL,
    etapa_ciclo text,
    criado_em timestamp without time zone,
    criado_por_id integer
);


--
-- Name: documento_tipos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documento_tipos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documento_tipos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documento_tipos_id_seq OWNED BY public.documento_tipos.id;


--
-- Name: emitente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emitente (
    id integer NOT NULL,
    cnpj character varying(18),
    razao_social text,
    nome_fantasia text,
    inscricao_estadual text,
    inscricao_municipal text,
    regime_tributario text,
    csosn_padrao text,
    csosn_contribuinte text,
    cfop_dentro_uf text,
    cfop_fora_uf text,
    serie_nfe text,
    discrimina_impostos integer,
    cnae_servico text,
    cod_servico_municipio text,
    aliquota_iss double precision,
    retencao_json text,
    municipio_ibge text,
    logradouro text,
    numero text,
    bairro text,
    cidade text,
    uf text,
    cep text,
    cert_validade timestamp without time zone,
    cert_cnpj text,
    papel_cnpj text,
    focus_token_homolog_enc text,
    focus_token_prod_enc text,
    ambiente_ativo text,
    placeholders_json text,
    rede_id integer,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


--
-- Name: emitente_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emitente_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emitente_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emitente_id_seq OWNED BY public.emitente.id;


--
-- Name: envios_externos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.envios_externos (
    id integer NOT NULL,
    mensagem_id integer,
    meio character varying(16) NOT NULL,
    direcao character varying(10) NOT NULL,
    canal character varying(20),
    destinatario_tipo character varying(16),
    destinatario_id integer,
    destino text,
    status character varying(20) NOT NULL,
    id_externo text,
    id_externo_ref text,
    erro text,
    criado_em timestamp without time zone,
    triagem_id integer,
    template_id integer
);


--
-- Name: envios_externos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.envios_externos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: envios_externos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.envios_externos_id_seq OWNED BY public.envios_externos.id;


--
-- Name: folha_pagamento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.folha_pagamento (
    id integer NOT NULL,
    loja_id integer,
    funcionario_id integer NOT NULL,
    competencia character varying(7) NOT NULL,
    parte_fixa double precision,
    vendas_liq double precision,
    faixa_pct double precision,
    parte_variavel double precision,
    total double precision,
    status character varying(10) NOT NULL,
    ref_lancamento character varying(60),
    gerado_em timestamp without time zone,
    pago_em timestamp without time zone,
    base_comissao double precision,
    beneficios double precision,
    comissao_fixa double precision
);


--
-- Name: folha_pagamento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.folha_pagamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: folha_pagamento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.folha_pagamento_id_seq OWNED BY public.folha_pagamento.id;


--
-- Name: fornecedores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fornecedores (
    id integer NOT NULL,
    loja_id integer,
    tipo_pessoa character varying(2) NOT NULL,
    nome character varying(180) NOT NULL,
    cnpj_cpf character varying(18),
    telefone character varying(20),
    email character varying(120),
    categoria character varying(20),
    prazo_pagamento integer,
    dados_bancarios text,
    cep character varying(9),
    logradouro character varying(200),
    numero character varying(20),
    complemento character varying(100),
    bairro character varying(100),
    cidade character varying(80),
    uf character varying(2),
    banco_nome character varying(80),
    banco_codigo character varying(6),
    agencia character varying(12),
    conta character varying(20),
    pix character varying(140),
    status character varying(10) NOT NULL,
    criado_em timestamp without time zone
);


--
-- Name: fornecedores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fornecedores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fornecedores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fornecedores_id_seq OWNED BY public.fornecedores.id;


--
-- Name: funcionarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.funcionarios (
    id integer NOT NULL,
    loja_id integer,
    nome character varying(150) NOT NULL,
    cpf character varying(20),
    telefone character varying(20),
    email character varying(120),
    cargo character varying(80),
    funcao_id integer,
    remuneracao_tipo character varying(20),
    remuneracao_fixa double precision,
    remuneracao_var double precision,
    cep character varying(9),
    logradouro character varying(200),
    numero character varying(20),
    complemento character varying(100),
    bairro character varying(100),
    cidade character varying(80),
    uf character varying(2),
    banco_nome character varying(80),
    banco_codigo character varying(6),
    agencia character varying(12),
    conta character varying(20),
    pix character varying(140),
    status character varying(10) NOT NULL,
    usuario_id integer,
    criado_em timestamp without time zone
);


--
-- Name: funcionarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.funcionarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: funcionarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.funcionarios_id_seq OWNED BY public.funcionarios.id;


--
-- Name: funcoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.funcoes (
    id integer NOT NULL,
    loja_id integer,
    nome character varying(80) NOT NULL,
    status character varying(10) NOT NULL,
    perfil_padrao character varying(40),
    criado_em timestamp without time zone,
    atribuicoes_json text,
    remuneracao_padrao character varying(20),
    regime_trabalho character varying(20),
    regime_contratacao character varying(20),
    descricao text,
    salario_fixo double precision,
    beneficios_json text,
    comissao_json text,
    usa_comissao_vendas integer DEFAULT 0,
    comissao_fixa double precision
);


--
-- Name: funcoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.funcoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: funcoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.funcoes_id_seq OWNED BY public.funcoes.id;


--
-- Name: integracoes_clicksign; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.integracoes_clicksign (
    id integer NOT NULL,
    loja_id integer,
    rede_id integer,
    token_sandbox_enc text,
    token_producao_enc text,
    webhook_secret_enc text,
    ambiente_ativo text NOT NULL,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


--
-- Name: integracoes_clicksign_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.integracoes_clicksign_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: integracoes_clicksign_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.integracoes_clicksign_id_seq OWNED BY public.integracoes_clicksign.id;


--
-- Name: integracoes_d4sign; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.integracoes_d4sign (
    id integer NOT NULL,
    loja_id integer,
    rede_id integer,
    token_sandbox_enc text,
    token_producao_enc text,
    cryptkey_sandbox_enc text,
    cryptkey_producao_enc text,
    safe_uuid_sandbox text,
    safe_uuid_producao text,
    webhook_secret_enc text,
    ambiente_ativo text NOT NULL,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


--
-- Name: integracoes_d4sign_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.integracoes_d4sign_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: integracoes_d4sign_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.integracoes_d4sign_id_seq OWNED BY public.integracoes_d4sign.id;


--
-- Name: lancamento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lancamento (
    id integer NOT NULL,
    owner_tipo character varying(10) NOT NULL,
    owner_id integer NOT NULL,
    data timestamp without time zone NOT NULL,
    conta_debito_id integer NOT NULL,
    conta_credito_id integer NOT NULL,
    valor double precision NOT NULL,
    projeto_id character varying,
    origem character varying(64) NOT NULL,
    historico text,
    ref character varying(80),
    motivo character varying(30),
    ia_sugestao text,
    criado_em timestamp without time zone
);


--
-- Name: lancamento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lancamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lancamento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lancamento_id_seq OWNED BY public.lancamento.id;


--
-- Name: log_acesso_delegado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.log_acesso_delegado (
    id integer NOT NULL,
    solicitante_id integer NOT NULL,
    autorizador_id integer,
    recurso character varying(40) NOT NULL,
    contexto text,
    criado_em timestamp without time zone
);


--
-- Name: log_acesso_delegado_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.log_acesso_delegado_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_acesso_delegado_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.log_acesso_delegado_id_seq OWNED BY public.log_acesso_delegado.id;


--
-- Name: log_acoes_gerenciais; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.log_acoes_gerenciais (
    id integer NOT NULL,
    solicitante_id integer,
    autorizador_id integer NOT NULL,
    acao text NOT NULL,
    projeto_nome text,
    etapa_alvo text,
    contexto text,
    criado_em timestamp without time zone
);


--
-- Name: log_acoes_gerenciais_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.log_acoes_gerenciais_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_acoes_gerenciais_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.log_acoes_gerenciais_id_seq OWNED BY public.log_acoes_gerenciais.id;


--
-- Name: log_autorizacoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.log_autorizacoes (
    id integer NOT NULL,
    solicitante_id integer NOT NULL,
    autorizador_id integer,
    desconto_solicit double precision NOT NULL,
    desconto_limite double precision NOT NULL,
    autorizado integer,
    contexto text,
    criado_em timestamp without time zone
);


--
-- Name: log_autorizacoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.log_autorizacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_autorizacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.log_autorizacoes_id_seq OWNED BY public.log_autorizacoes.id;


--
-- Name: lojas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lojas (
    id integer NOT NULL,
    rede_id integer,
    nome character varying(150) NOT NULL,
    cnpj character varying(18),
    codigo character varying(8),
    telefone character varying(20),
    email character varying(120),
    cep character varying(9),
    logradouro character varying(200),
    numero character varying(20),
    complemento character varying(100),
    bairro character varying(100),
    cidade character varying(80),
    estado character varying(2),
    testemunha1_nome character varying(120),
    testemunha1_cpf character varying(14),
    testemunha2_nome character varying(120),
    testemunha2_cpf character varying(14),
    emitente_id integer,
    ativo integer,
    criado_em timestamp without time zone,
    config_financeira_json text,
    modulos_ativos text,
    pct_mercadoria double precision,
    pct_servico double precision,
    responsavel character varying(120),
    loja_mae_id integer,
    tipo character varying(12) DEFAULT 'loja'::character varying,
    testemunha1_email character varying(150),
    testemunha2_email character varying(150),
    logo_arquivo character varying(80)
);


--
-- Name: lojas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lojas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lojas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lojas_id_seq OWNED BY public.lojas.id;


--
-- Name: medicoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.medicoes (
    id integer NOT NULL,
    projeto_nome character varying(200) NOT NULL,
    solicitacao_arquivo character varying(255),
    solicitacao_por integer,
    solicitacao_em timestamp without time zone,
    parecer character varying(20),
    ambientes_aprovados text,
    planta_arquivo character varying(255),
    medidor_id integer,
    medicao_em timestamp without time zone,
    doc_cliente_arquivo character varying(255),
    excecao_por integer,
    excecao_em timestamp without time zone
);


--
-- Name: medicoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.medicoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: medicoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.medicoes_id_seq OWNED BY public.medicoes.id;


--
-- Name: mensagem_anexos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mensagem_anexos (
    id integer NOT NULL,
    mensagem_id integer NOT NULL,
    tipo character varying(12) NOT NULL,
    nome text NOT NULL,
    mime character varying(120),
    tamanho integer,
    caminho text NOT NULL,
    criado_em timestamp without time zone
);


--
-- Name: mensagem_anexos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mensagem_anexos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mensagem_anexos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mensagem_anexos_id_seq OWNED BY public.mensagem_anexos.id;


--
-- Name: numero_conectado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.numero_conectado (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    numero character varying(24),
    rotulo text,
    atualizado_em timestamp without time zone
);


--
-- Name: numero_conectado_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.numero_conectado_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: numero_conectado_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.numero_conectado_id_seq OWNED BY public.numero_conectado.id;


--
-- Name: orcamento_ambientes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orcamento_ambientes (
    orcamento_id integer NOT NULL,
    pool_ambiente_id integer NOT NULL,
    ordem integer,
    added_at timestamp without time zone,
    desconto_individual_pct double precision DEFAULT '0'::double precision NOT NULL
);


--
-- Name: orcamentos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orcamentos (
    id integer NOT NULL,
    projeto_id character varying NOT NULL,
    nome character varying NOT NULL,
    ordem integer NOT NULL,
    desconto_pct double precision,
    forma_pagamento character varying,
    negociacao_json text,
    valor_total double precision,
    valor_liquido double precision,
    num_proposta character varying,
    vbvo double precision,
    cfo double precision,
    vbno double precision,
    vavo double precision,
    cust_ad double precision,
    com_arq_orc double precision,
    pro_fid_orc double precision,
    val_liq double precision,
    desc_tot_pct double precision,
    markup double precision,
    cust_fin double precision,
    val_cont double precision,
    prov_imp double precision,
    out_forn double precision,
    ramo_financeiro character varying,
    ramo_financeiro_seq integer,
    created_by integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    loja_id integer,
    complemento_pe integer DEFAULT 0,
    parcela_id integer
);


--
-- Name: orcamentos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.orcamentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: orcamentos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.orcamentos_id_seq OWNED BY public.orcamentos.id;


--
-- Name: parceiro_lojas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parceiro_lojas (
    id integer NOT NULL,
    parceiro_id integer NOT NULL,
    loja_id integer NOT NULL,
    comissao_padrao_pct double precision,
    ativo integer
);


--
-- Name: parceiro_lojas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.parceiro_lojas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: parceiro_lojas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.parceiro_lojas_id_seq OWNED BY public.parceiro_lojas.id;


--
-- Name: parceiros; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parceiros (
    id integer NOT NULL,
    nome character varying(150) NOT NULL,
    cpf_cnpj character varying(18),
    tipo character varying(30),
    email character varying(120),
    telefone character varying(20),
    whatsapp character varying(20),
    comissao_padrao_pct double precision,
    observacoes text,
    criado_em timestamp without time zone,
    rede_id integer,
    abrangencia character varying(10),
    pix character varying(140)
);


--
-- Name: parceiros_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.parceiros_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: parceiros_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.parceiros_id_seq OWNED BY public.parceiros.id;


--
-- Name: parcela_ambiente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parcela_ambiente (
    parcela_id integer NOT NULL,
    pool_ambiente_id integer NOT NULL,
    valor_ambiente double precision DEFAULT 0.0
);


--
-- Name: parcela_projeto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parcela_projeto (
    id integer NOT NULL,
    projeto_nome text NOT NULL,
    ordem integer NOT NULL,
    status character varying(16) NOT NULL,
    fracao_val_cont double precision NOT NULL,
    val_cont_congelado double precision NOT NULL,
    orcamento_id integer,
    saldo_margem_estimado double precision,
    criado_em timestamp without time zone,
    criado_por_id integer,
    prazo_conclusao timestamp without time zone,
    liberacao_prevista date,
    entrega_prevista date,
    val_liq_congelado double precision
);


--
-- Name: parcela_projeto_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.parcela_projeto_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: parcela_projeto_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.parcela_projeto_id_seq OWNED BY public.parcela_projeto.id;


--
-- Name: perfil_acesso; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perfil_acesso (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    slug character varying(40) NOT NULL,
    nome character varying(80) NOT NULL,
    base character varying(20) NOT NULL,
    modulos_json text NOT NULL,
    capacidades_json text NOT NULL,
    sistema integer NOT NULL,
    criado_em timestamp without time zone
);


--
-- Name: perfil_acesso_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.perfil_acesso_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perfil_acesso_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.perfil_acesso_id_seq OWNED BY public.perfil_acesso.id;


--
-- Name: perfil_emissao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perfil_emissao (
    id integer NOT NULL,
    owner_tipo text NOT NULL,
    owner_id integer NOT NULL,
    tipo_doc text NOT NULL,
    emitente_id integer NOT NULL,
    criado_em timestamp without time zone
);


--
-- Name: perfil_emissao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.perfil_emissao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perfil_emissao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.perfil_emissao_id_seq OWNED BY public.perfil_emissao.id;


--
-- Name: periodo_contabil; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.periodo_contabil (
    id integer NOT NULL,
    owner_tipo character varying(10) NOT NULL,
    owner_id integer NOT NULL,
    inicio timestamp without time zone,
    fim timestamp without time zone,
    status character varying(10),
    metodologia character varying(30) NOT NULL,
    resultado_societario double precision,
    soma_margem_plena double precision,
    divergencia_residual double precision,
    dados_json text,
    criado_em timestamp without time zone,
    classificacao_snapshot_json text
);


--
-- Name: periodo_contabil_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.periodo_contabil_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: periodo_contabil_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.periodo_contabil_id_seq OWNED BY public.periodo_contabil.id;


--
-- Name: pool_ambientes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pool_ambientes (
    id integer NOT NULL,
    projeto_id character varying NOT NULL,
    nome character varying NOT NULL,
    versao integer,
    nome_exibicao character varying NOT NULL,
    xml_path character varying NOT NULL,
    ambientes_json text NOT NULL,
    budget_total double precision NOT NULL,
    order_total double precision NOT NULL,
    qa_selo character varying,
    qa_pct_sem_acrescimo double precision,
    qa_markup_xml double precision,
    qa_custo_sem_venda integer,
    qa_override_por_id integer,
    qa_override_motivo character varying,
    created_by integer,
    created_at timestamp without time zone,
    renegociar_pe integer DEFAULT 0
);


--
-- Name: pool_ambientes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pool_ambientes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pool_ambientes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pool_ambientes_id_seq OWNED BY public.pool_ambientes.id;


--
-- Name: projetos_meta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.projetos_meta (
    nome_safe character varying NOT NULL,
    cliente_id integer,
    status character varying(20),
    status_at timestamp without time zone,
    perdido_em timestamp without time zone,
    parametros_json text,
    loja_id integer,
    criado_por_id integer,
    data_entrega timestamp without time zone,
    data_inicio timestamp without time zone,
    equipe_json text,
    previsao_medicao timestamp without time zone,
    venda_programada integer DEFAULT 0,
    folga_autorizada integer DEFAULT 0,
    data_limite_contratual timestamp without time zone,
    cancelado_definitivo integer DEFAULT 0
);


--
-- Name: provisao_data_prevista; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.provisao_data_prevista (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    projeto_nome text NOT NULL,
    codigo_conta text NOT NULL,
    data_prevista date NOT NULL,
    atualizado_em timestamp without time zone NOT NULL,
    atualizado_por_id integer
);


--
-- Name: provisao_data_prevista_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.provisao_data_prevista_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: provisao_data_prevista_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.provisao_data_prevista_id_seq OWNED BY public.provisao_data_prevista.id;


--
-- Name: provisao_registro; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.provisao_registro (
    id integer NOT NULL,
    orcamento_id integer NOT NULL,
    versao character varying(8) NOT NULL,
    itens_json text NOT NULL,
    cfo double precision,
    val_liq double precision,
    cust_var double precision,
    marg_cont double precision,
    decisao character varying(10),
    por_id integer,
    criado_em timestamp without time zone,
    travada_em timestamp without time zone
);


--
-- Name: provisao_registro_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.provisao_registro_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: provisao_registro_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.provisao_registro_id_seq OWNED BY public.provisao_registro.id;


--
-- Name: recebivel; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recebivel (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    projeto_nome text NOT NULL,
    orcamento_id integer NOT NULL,
    tipo text NOT NULL,
    numero integer,
    forma text,
    valor_previsto double precision NOT NULL,
    data_prevista date NOT NULL,
    status text NOT NULL,
    valor_confirmado double precision,
    confirmado_em date,
    confirmado_por_id integer,
    ref text NOT NULL,
    criado_em timestamp without time zone NOT NULL,
    duvidoso_em date
);


--
-- Name: recebivel_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recebivel_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recebivel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recebivel_id_seq OWNED BY public.recebivel.id;


--
-- Name: redes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.redes (
    id integer NOT NULL,
    nome character varying(150) NOT NULL,
    cnpj character varying(18),
    emitente_central_id integer,
    ativo integer,
    criado_em timestamp without time zone
);


--
-- Name: redes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.redes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: redes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.redes_id_seq OWNED BY public.redes.id;


--
-- Name: retencao_obra; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.retencao_obra (
    id integer NOT NULL,
    projeto_nome text NOT NULL,
    etapa_codigo text,
    motivo text,
    liberacao_prevista date,
    ambientes_json text NOT NULL,
    criado_em timestamp without time zone,
    criado_por_id integer,
    liberado_em timestamp without time zone,
    liberado_por_id integer,
    motivo_tipo text
);


--
-- Name: retencao_obra_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.retencao_obra_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: retencao_obra_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.retencao_obra_id_seq OWNED BY public.retencao_obra.id;


--
-- Name: segmento_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.segmento_config (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    segmento character varying(20) NOT NULL,
    ativo integer NOT NULL,
    rotulo text,
    template_padrao_id integer,
    atualizado_em timestamp without time zone,
    responsavel_funcionario_id integer
);


--
-- Name: segmento_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.segmento_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: segmento_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.segmento_config_id_seq OWNED BY public.segmento_config.id;


--
-- Name: sessoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sessoes (
    id integer NOT NULL,
    token character varying(64) NOT NULL,
    usuario_id integer NOT NULL,
    criada_em timestamp without time zone,
    expira_em timestamp without time zone NOT NULL,
    ativa integer
);


--
-- Name: sessoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sessoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sessoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sessoes_id_seq OWNED BY public.sessoes.id;


--
-- Name: simulador_autorizacoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.simulador_autorizacoes (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    status character varying(10) NOT NULL,
    concedido_por_usuario_id integer,
    beneficiario character varying(40) NOT NULL,
    escopo character varying(40) NOT NULL,
    base_legal text,
    concedido_em timestamp without time zone,
    revogado_em timestamp without time zone,
    ip character varying(64),
    criado_em timestamp without time zone,
    solicitado_por_usuario_id integer,
    solicitado_em timestamp without time zone
);


--
-- Name: simulador_autorizacoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.simulador_autorizacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: simulador_autorizacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.simulador_autorizacoes_id_seq OWNED BY public.simulador_autorizacoes.id;


--
-- Name: simulador_log_acessos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.simulador_log_acessos (
    id integer NOT NULL,
    evento character varying(20) NOT NULL,
    usuario_id integer,
    loja_id integer,
    contexto text,
    ip character varying(64),
    criado_em timestamp without time zone
);


--
-- Name: simulador_log_acessos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.simulador_log_acessos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: simulador_log_acessos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.simulador_log_acessos_id_seq OWNED BY public.simulador_log_acessos.id;


--
-- Name: sinal_retido; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sinal_retido (
    id integer NOT NULL,
    projeto_nome text NOT NULL,
    pool_ambiente_id integer NOT NULL,
    sinalizado_por_id integer,
    motivo text,
    confirmado integer NOT NULL,
    criado_em timestamp without time zone
);


--
-- Name: sinal_retido_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sinal_retido_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sinal_retido_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sinal_retido_id_seq OWNED BY public.sinal_retido.id;


--
-- Name: solicitacoes_medicao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solicitacoes_medicao (
    id integer NOT NULL,
    projeto_nome text NOT NULL,
    pdf_path text,
    status text NOT NULL,
    gerado_em timestamp without time zone,
    gerado_por_id integer,
    loja_id integer,
    modelo_versao_id integer,
    assinatura_canal character varying(16),
    clicksign_envelope_id text,
    clicksign_enviado_em timestamp without time zone,
    clicksign_signatarios_json text
);


--
-- Name: solicitacoes_medicao_assinaturas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solicitacoes_medicao_assinaturas (
    id integer NOT NULL,
    solicitacao_id integer NOT NULL,
    parte text NOT NULL,
    nome text NOT NULL,
    cpf text NOT NULL,
    assinado_em timestamp without time zone NOT NULL,
    ip_origem text,
    hash_sha256 text NOT NULL
);


--
-- Name: solicitacoes_medicao_assinaturas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solicitacoes_medicao_assinaturas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitacoes_medicao_assinaturas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solicitacoes_medicao_assinaturas_id_seq OWNED BY public.solicitacoes_medicao_assinaturas.id;


--
-- Name: solicitacoes_medicao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solicitacoes_medicao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitacoes_medicao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solicitacoes_medicao_id_seq OWNED BY public.solicitacoes_medicao.id;


--
-- Name: template_mensagem; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.template_mensagem (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    segmento character varying(20),
    slot_obrigatorio integer,
    nome_meta text NOT NULL,
    categoria character varying(12) NOT NULL,
    idioma character varying(12) NOT NULL,
    corpo text,
    variaveis_json text,
    assinatura_var integer,
    status character varying(12) NOT NULL,
    meta_template_id text,
    ativo integer NOT NULL,
    criado_por_id integer,
    criado_em timestamp without time zone
);


--
-- Name: template_mensagem_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.template_mensagem_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: template_mensagem_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.template_mensagem_id_seq OWNED BY public.template_mensagem.id;


--
-- Name: terceiros; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.terceiros (
    id integer NOT NULL,
    loja_id integer,
    nome character varying(150) NOT NULL,
    cpf character varying(20),
    telefone character varying(20),
    tipo_servico character varying(20),
    funcao_id integer,
    pix character varying(140),
    dados_bancarios text,
    condicao character varying(12),
    cep character varying(9),
    logradouro character varying(200),
    numero character varying(20),
    complemento character varying(100),
    bairro character varying(100),
    cidade character varying(80),
    uf character varying(2),
    banco_nome character varying(80),
    banco_codigo character varying(6),
    agencia character varying(12),
    conta character varying(20),
    usuario_id integer,
    status character varying(10) NOT NULL,
    criado_em timestamp without time zone,
    cnpj character varying(18)
);


--
-- Name: terceiros_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.terceiros_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: terceiros_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.terceiros_id_seq OWNED BY public.terceiros.id;


--
-- Name: triagem_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.triagem_config (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    formato character varying(8) NOT NULL,
    mensagem_livre text,
    itens_json text,
    atualizado_em timestamp without time zone
);


--
-- Name: triagem_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.triagem_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: triagem_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.triagem_config_id_seq OWNED BY public.triagem_config.id;


--
-- Name: triagem_entradas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.triagem_entradas (
    id integer NOT NULL,
    loja_id integer NOT NULL,
    meio character varying(16) NOT NULL,
    remetente text NOT NULL,
    texto text,
    id_externo text,
    id_externo_ref text,
    status character varying(12) NOT NULL,
    candidatos_json text,
    segmento_sugerido character varying(20),
    conversa_id integer,
    resolvido_por_id integer,
    resolvido_em timestamp without time zone,
    criado_em timestamp without time zone,
    nome_whatsapp character varying(150)
);


--
-- Name: triagem_entradas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.triagem_entradas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: triagem_entradas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.triagem_entradas_id_seq OWNED BY public.triagem_entradas.id;


--
-- Name: usuario_lojas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_lojas (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    loja_id integer NOT NULL
);


--
-- Name: usuario_lojas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuario_lojas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_lojas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuario_lojas_id_seq OWNED BY public.usuario_lojas.id;


--
-- Name: usuario_presenca; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_presenca (
    usuario_id integer NOT NULL,
    visto_em timestamp without time zone
);


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    nome character varying(120) NOT NULL,
    login character varying(60) NOT NULL,
    senha_hash character varying(64) NOT NULL,
    nivel character varying(20) NOT NULL,
    telefone character varying(20),
    email character varying(120),
    cpf character varying(20),
    whatsapp character varying(20),
    ativo integer,
    funcionario_id integer,
    funcao_id integer,
    tema character varying(10),
    criado_em timestamp without time zone,
    loja_id integer,
    rede_id integer,
    senha_provisoria integer DEFAULT 0,
    notificar_whatsapp character varying(16) DEFAULT 'quando_offline'::character varying,
    capacidades_override_json text
);


--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: acordo_fabrica id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acordo_fabrica ALTER COLUMN id SET DEFAULT nextval('public.acordo_fabrica_id_seq'::regclass);


--
-- Name: acordo_movimento id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acordo_movimento ALTER COLUMN id SET DEFAULT nextval('public.acordo_movimento_id_seq'::regclass);


--
-- Name: adiantamento_funcionario id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adiantamento_funcionario ALTER COLUMN id SET DEFAULT nextval('public.adiantamento_funcionario_id_seq'::regclass);


--
-- Name: aditivos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos ALTER COLUMN id SET DEFAULT nextval('public.aditivos_id_seq'::regclass);


--
-- Name: aditivos_assinaturas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos_assinaturas ALTER COLUMN id SET DEFAULT nextval('public.aditivos_assinaturas_id_seq'::regclass);


--
-- Name: ajuste_fabrica id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ajuste_fabrica ALTER COLUMN id SET DEFAULT nextval('public.ajuste_fabrica_id_seq'::regclass);


--
-- Name: ajuste_fabrica_aplicacao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ajuste_fabrica_aplicacao ALTER COLUMN id SET DEFAULT nextval('public.ajuste_fabrica_aplicacao_id_seq'::regclass);


--
-- Name: aprovacoes_pe id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aprovacoes_pe ALTER COLUMN id SET DEFAULT nextval('public.aprovacoes_pe_id_seq'::regclass);


--
-- Name: aprovacoes_pe_assinaturas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aprovacoes_pe_assinaturas ALTER COLUMN id SET DEFAULT nextval('public.aprovacoes_pe_assinaturas_id_seq'::regclass);


--
-- Name: arquivo_pe id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.arquivo_pe ALTER COLUMN id SET DEFAULT nextval('public.arquivo_pe_id_seq'::regclass);


--
-- Name: assistencia_anexos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_anexos ALTER COLUMN id SET DEFAULT nextval('public.assistencia_anexos_id_seq'::regclass);


--
-- Name: assistencia_caso id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_caso ALTER COLUMN id SET DEFAULT nextval('public.assistencia_caso_id_seq'::regclass);


--
-- Name: assistencia_executores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_executores ALTER COLUMN id SET DEFAULT nextval('public.assistencia_executores_id_seq'::regclass);


--
-- Name: assuntos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assuntos ALTER COLUMN id SET DEFAULT nextval('public.assuntos_id_seq'::regclass);


--
-- Name: atribuicoes_ambiente id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atribuicoes_ambiente ALTER COLUMN id SET DEFAULT nextval('public.atribuicoes_ambiente_id_seq'::regclass);


--
-- Name: briefings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.briefings ALTER COLUMN id SET DEFAULT nextval('public.briefings_id_seq'::regclass);


--
-- Name: centro_custo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.centro_custo ALTER COLUMN id SET DEFAULT nextval('public.centro_custo_id_seq'::regclass);


--
-- Name: ciclo_documentos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_documentos ALTER COLUMN id SET DEFAULT nextval('public.ciclo_documentos_id_seq'::regclass);


--
-- Name: ciclo_etapas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas ALTER COLUMN id SET DEFAULT nextval('public.ciclo_etapas_id_seq'::regclass);


--
-- Name: ciclo_logistico id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico ALTER COLUMN id SET DEFAULT nextval('public.ciclo_logistico_id_seq'::regclass);


--
-- Name: ciclo_logistico_transicao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico_transicao ALTER COLUMN id SET DEFAULT nextval('public.ciclo_logistico_transicao_id_seq'::regclass);


--
-- Name: ciclo_revisoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_revisoes ALTER COLUMN id SET DEFAULT nextval('public.ciclo_revisoes_id_seq'::regclass);


--
-- Name: clientes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes ALTER COLUMN id SET DEFAULT nextval('public.clientes_id_seq'::regclass);


--
-- Name: comissao_folha id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comissao_folha ALTER COLUMN id SET DEFAULT nextval('public.comissao_folha_id_seq'::regclass);


--
-- Name: conciliacao_pe_fase id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conciliacao_pe_fase ALTER COLUMN id SET DEFAULT nextval('public.conciliacao_pe_fase_id_seq'::regclass);


--
-- Name: conta id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conta ALTER COLUMN id SET DEFAULT nextval('public.conta_id_seq'::regclass);


--
-- Name: contato_confirmacoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contato_confirmacoes ALTER COLUMN id SET DEFAULT nextval('public.contato_confirmacoes_id_seq'::regclass);


--
-- Name: contraparte_financeira id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contraparte_financeira ALTER COLUMN id SET DEFAULT nextval('public.contraparte_financeira_id_seq'::regclass);


--
-- Name: contratos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contratos ALTER COLUMN id SET DEFAULT nextval('public.contratos_id_seq'::regclass);


--
-- Name: contratos_assinaturas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contratos_assinaturas ALTER COLUMN id SET DEFAULT nextval('public.contratos_assinaturas_id_seq'::regclass);


--
-- Name: conversa_mensagens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_mensagens ALTER COLUMN id SET DEFAULT nextval('public.conversa_mensagens_id_seq'::regclass);


--
-- Name: conversa_participantes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_participantes ALTER COLUMN id SET DEFAULT nextval('public.conversa_participantes_id_seq'::regclass);


--
-- Name: conversa_participantes_externos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_participantes_externos ALTER COLUMN id SET DEFAULT nextval('public.conversa_participantes_externos_id_seq'::regclass);


--
-- Name: conversas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversas ALTER COLUMN id SET DEFAULT nextval('public.conversas_id_seq'::regclass);


--
-- Name: documento_fiscal id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_fiscal ALTER COLUMN id SET DEFAULT nextval('public.documento_fiscal_id_seq'::regclass);


--
-- Name: documento_modelos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_modelos ALTER COLUMN id SET DEFAULT nextval('public.documento_modelos_id_seq'::regclass);


--
-- Name: documento_tipos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_tipos ALTER COLUMN id SET DEFAULT nextval('public.documento_tipos_id_seq'::regclass);


--
-- Name: emitente id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emitente ALTER COLUMN id SET DEFAULT nextval('public.emitente_id_seq'::regclass);


--
-- Name: envios_externos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.envios_externos ALTER COLUMN id SET DEFAULT nextval('public.envios_externos_id_seq'::regclass);


--
-- Name: folha_pagamento id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folha_pagamento ALTER COLUMN id SET DEFAULT nextval('public.folha_pagamento_id_seq'::regclass);


--
-- Name: fornecedores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fornecedores ALTER COLUMN id SET DEFAULT nextval('public.fornecedores_id_seq'::regclass);


--
-- Name: funcionarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcionarios ALTER COLUMN id SET DEFAULT nextval('public.funcionarios_id_seq'::regclass);


--
-- Name: funcoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcoes ALTER COLUMN id SET DEFAULT nextval('public.funcoes_id_seq'::regclass);


--
-- Name: integracoes_clicksign id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integracoes_clicksign ALTER COLUMN id SET DEFAULT nextval('public.integracoes_clicksign_id_seq'::regclass);


--
-- Name: integracoes_d4sign id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integracoes_d4sign ALTER COLUMN id SET DEFAULT nextval('public.integracoes_d4sign_id_seq'::regclass);


--
-- Name: lancamento id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lancamento ALTER COLUMN id SET DEFAULT nextval('public.lancamento_id_seq'::regclass);


--
-- Name: log_acesso_delegado id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acesso_delegado ALTER COLUMN id SET DEFAULT nextval('public.log_acesso_delegado_id_seq'::regclass);


--
-- Name: log_acoes_gerenciais id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acoes_gerenciais ALTER COLUMN id SET DEFAULT nextval('public.log_acoes_gerenciais_id_seq'::regclass);


--
-- Name: log_autorizacoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_autorizacoes ALTER COLUMN id SET DEFAULT nextval('public.log_autorizacoes_id_seq'::regclass);


--
-- Name: lojas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lojas ALTER COLUMN id SET DEFAULT nextval('public.lojas_id_seq'::regclass);


--
-- Name: medicoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicoes ALTER COLUMN id SET DEFAULT nextval('public.medicoes_id_seq'::regclass);


--
-- Name: mensagem_anexos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensagem_anexos ALTER COLUMN id SET DEFAULT nextval('public.mensagem_anexos_id_seq'::regclass);


--
-- Name: numero_conectado id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.numero_conectado ALTER COLUMN id SET DEFAULT nextval('public.numero_conectado_id_seq'::regclass);


--
-- Name: orcamentos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orcamentos ALTER COLUMN id SET DEFAULT nextval('public.orcamentos_id_seq'::regclass);


--
-- Name: parceiro_lojas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parceiro_lojas ALTER COLUMN id SET DEFAULT nextval('public.parceiro_lojas_id_seq'::regclass);


--
-- Name: parceiros id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parceiros ALTER COLUMN id SET DEFAULT nextval('public.parceiros_id_seq'::regclass);


--
-- Name: parcela_projeto id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parcela_projeto ALTER COLUMN id SET DEFAULT nextval('public.parcela_projeto_id_seq'::regclass);


--
-- Name: perfil_acesso id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_acesso ALTER COLUMN id SET DEFAULT nextval('public.perfil_acesso_id_seq'::regclass);


--
-- Name: perfil_emissao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_emissao ALTER COLUMN id SET DEFAULT nextval('public.perfil_emissao_id_seq'::regclass);


--
-- Name: periodo_contabil id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodo_contabil ALTER COLUMN id SET DEFAULT nextval('public.periodo_contabil_id_seq'::regclass);


--
-- Name: pool_ambientes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pool_ambientes ALTER COLUMN id SET DEFAULT nextval('public.pool_ambientes_id_seq'::regclass);


--
-- Name: provisao_data_prevista id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_data_prevista ALTER COLUMN id SET DEFAULT nextval('public.provisao_data_prevista_id_seq'::regclass);


--
-- Name: provisao_registro id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_registro ALTER COLUMN id SET DEFAULT nextval('public.provisao_registro_id_seq'::regclass);


--
-- Name: recebivel id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebivel ALTER COLUMN id SET DEFAULT nextval('public.recebivel_id_seq'::regclass);


--
-- Name: redes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.redes ALTER COLUMN id SET DEFAULT nextval('public.redes_id_seq'::regclass);


--
-- Name: retencao_obra id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retencao_obra ALTER COLUMN id SET DEFAULT nextval('public.retencao_obra_id_seq'::regclass);


--
-- Name: segmento_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segmento_config ALTER COLUMN id SET DEFAULT nextval('public.segmento_config_id_seq'::regclass);


--
-- Name: sessoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes ALTER COLUMN id SET DEFAULT nextval('public.sessoes_id_seq'::regclass);


--
-- Name: simulador_autorizacoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulador_autorizacoes ALTER COLUMN id SET DEFAULT nextval('public.simulador_autorizacoes_id_seq'::regclass);


--
-- Name: simulador_log_acessos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulador_log_acessos ALTER COLUMN id SET DEFAULT nextval('public.simulador_log_acessos_id_seq'::regclass);


--
-- Name: sinal_retido id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sinal_retido ALTER COLUMN id SET DEFAULT nextval('public.sinal_retido_id_seq'::regclass);


--
-- Name: solicitacoes_medicao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes_medicao ALTER COLUMN id SET DEFAULT nextval('public.solicitacoes_medicao_id_seq'::regclass);


--
-- Name: solicitacoes_medicao_assinaturas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes_medicao_assinaturas ALTER COLUMN id SET DEFAULT nextval('public.solicitacoes_medicao_assinaturas_id_seq'::regclass);


--
-- Name: template_mensagem id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.template_mensagem ALTER COLUMN id SET DEFAULT nextval('public.template_mensagem_id_seq'::regclass);


--
-- Name: terceiros id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.terceiros ALTER COLUMN id SET DEFAULT nextval('public.terceiros_id_seq'::regclass);


--
-- Name: triagem_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triagem_config ALTER COLUMN id SET DEFAULT nextval('public.triagem_config_id_seq'::regclass);


--
-- Name: triagem_entradas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triagem_entradas ALTER COLUMN id SET DEFAULT nextval('public.triagem_entradas_id_seq'::regclass);


--
-- Name: usuario_lojas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_lojas ALTER COLUMN id SET DEFAULT nextval('public.usuario_lojas_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Name: acordo_fabrica acordo_fabrica_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acordo_fabrica
    ADD CONSTRAINT acordo_fabrica_pkey PRIMARY KEY (id);


--
-- Name: acordo_movimento acordo_movimento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acordo_movimento
    ADD CONSTRAINT acordo_movimento_pkey PRIMARY KEY (id);


--
-- Name: adiantamento_funcionario adiantamento_funcionario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adiantamento_funcionario
    ADD CONSTRAINT adiantamento_funcionario_pkey PRIMARY KEY (id);


--
-- Name: aditivos_assinaturas aditivos_assinaturas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos_assinaturas
    ADD CONSTRAINT aditivos_assinaturas_pkey PRIMARY KEY (id);


--
-- Name: aditivos aditivos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos
    ADD CONSTRAINT aditivos_pkey PRIMARY KEY (id);


--
-- Name: ajuste_fabrica_aplicacao ajuste_fabrica_aplicacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ajuste_fabrica_aplicacao
    ADD CONSTRAINT ajuste_fabrica_aplicacao_pkey PRIMARY KEY (id);


--
-- Name: ajuste_fabrica ajuste_fabrica_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ajuste_fabrica
    ADD CONSTRAINT ajuste_fabrica_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: aprovacoes_pe_assinaturas aprovacoes_pe_assinaturas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aprovacoes_pe_assinaturas
    ADD CONSTRAINT aprovacoes_pe_assinaturas_pkey PRIMARY KEY (id);


--
-- Name: aprovacoes_pe aprovacoes_pe_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aprovacoes_pe
    ADD CONSTRAINT aprovacoes_pe_pkey PRIMARY KEY (id);


--
-- Name: arquivo_pe arquivo_pe_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.arquivo_pe
    ADD CONSTRAINT arquivo_pe_pkey PRIMARY KEY (id);


--
-- Name: assistencia_anexos assistencia_anexos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_anexos
    ADD CONSTRAINT assistencia_anexos_pkey PRIMARY KEY (id);


--
-- Name: assistencia_caso assistencia_caso_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_caso
    ADD CONSTRAINT assistencia_caso_pkey PRIMARY KEY (id);


--
-- Name: assistencia_executores assistencia_executores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_executores
    ADD CONSTRAINT assistencia_executores_pkey PRIMARY KEY (id);


--
-- Name: assuntos assuntos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assuntos
    ADD CONSTRAINT assuntos_pkey PRIMARY KEY (id);


--
-- Name: atribuicoes_ambiente atribuicoes_ambiente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atribuicoes_ambiente
    ADD CONSTRAINT atribuicoes_ambiente_pkey PRIMARY KEY (id);


--
-- Name: briefings briefings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.briefings
    ADD CONSTRAINT briefings_pkey PRIMARY KEY (id);


--
-- Name: centro_custo centro_custo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.centro_custo
    ADD CONSTRAINT centro_custo_pkey PRIMARY KEY (id);


--
-- Name: ciclo_documentos ciclo_documentos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_documentos
    ADD CONSTRAINT ciclo_documentos_pkey PRIMARY KEY (id);


--
-- Name: ciclo_etapas ciclo_etapas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas
    ADD CONSTRAINT ciclo_etapas_pkey PRIMARY KEY (id);


--
-- Name: ciclo_logistico ciclo_logistico_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico
    ADD CONSTRAINT ciclo_logistico_pkey PRIMARY KEY (id);


--
-- Name: ciclo_logistico_transicao ciclo_logistico_transicao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico_transicao
    ADD CONSTRAINT ciclo_logistico_transicao_pkey PRIMARY KEY (id);


--
-- Name: ciclo_revisoes ciclo_revisoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_revisoes
    ADD CONSTRAINT ciclo_revisoes_pkey PRIMARY KEY (id);


--
-- Name: clientes clientes_cpf_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_cpf_key UNIQUE (cpf);


--
-- Name: clientes clientes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_pkey PRIMARY KEY (id);


--
-- Name: comissao_folha comissao_folha_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comissao_folha
    ADD CONSTRAINT comissao_folha_pkey PRIMARY KEY (id);


--
-- Name: conciliacao_pe_fase conciliacao_pe_fase_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conciliacao_pe_fase
    ADD CONSTRAINT conciliacao_pe_fase_pkey PRIMARY KEY (id);


--
-- Name: conta conta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conta
    ADD CONSTRAINT conta_pkey PRIMARY KEY (id);


--
-- Name: contato_confirmacoes contato_confirmacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contato_confirmacoes
    ADD CONSTRAINT contato_confirmacoes_pkey PRIMARY KEY (id);


--
-- Name: contraparte_financeira contraparte_financeira_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contraparte_financeira
    ADD CONSTRAINT contraparte_financeira_pkey PRIMARY KEY (id);


--
-- Name: contratos_assinaturas contratos_assinaturas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contratos_assinaturas
    ADD CONSTRAINT contratos_assinaturas_pkey PRIMARY KEY (id);


--
-- Name: contratos contratos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contratos
    ADD CONSTRAINT contratos_pkey PRIMARY KEY (id);


--
-- Name: conversa_mensagens conversa_mensagens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_mensagens
    ADD CONSTRAINT conversa_mensagens_pkey PRIMARY KEY (id);


--
-- Name: conversa_participantes_externos conversa_participantes_externos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_participantes_externos
    ADD CONSTRAINT conversa_participantes_externos_pkey PRIMARY KEY (id);


--
-- Name: conversa_participantes conversa_participantes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_participantes
    ADD CONSTRAINT conversa_participantes_pkey PRIMARY KEY (id);


--
-- Name: conversas conversas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversas
    ADD CONSTRAINT conversas_pkey PRIMARY KEY (id);


--
-- Name: documento_fiscal documento_fiscal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_fiscal
    ADD CONSTRAINT documento_fiscal_pkey PRIMARY KEY (id);


--
-- Name: documento_fiscal documento_fiscal_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_fiscal
    ADD CONSTRAINT documento_fiscal_ref_key UNIQUE (ref);


--
-- Name: documento_modelos documento_modelos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_modelos
    ADD CONSTRAINT documento_modelos_pkey PRIMARY KEY (id);


--
-- Name: documento_tipos documento_tipos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_tipos
    ADD CONSTRAINT documento_tipos_pkey PRIMARY KEY (id);


--
-- Name: emitente emitente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emitente
    ADD CONSTRAINT emitente_pkey PRIMARY KEY (id);


--
-- Name: envios_externos envios_externos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.envios_externos
    ADD CONSTRAINT envios_externos_pkey PRIMARY KEY (id);


--
-- Name: folha_pagamento folha_pagamento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folha_pagamento
    ADD CONSTRAINT folha_pagamento_pkey PRIMARY KEY (id);


--
-- Name: fornecedores fornecedores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fornecedores
    ADD CONSTRAINT fornecedores_pkey PRIMARY KEY (id);


--
-- Name: funcionarios funcionarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_pkey PRIMARY KEY (id);


--
-- Name: funcoes funcoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcoes
    ADD CONSTRAINT funcoes_pkey PRIMARY KEY (id);


--
-- Name: integracoes_clicksign integracoes_clicksign_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integracoes_clicksign
    ADD CONSTRAINT integracoes_clicksign_pkey PRIMARY KEY (id);


--
-- Name: integracoes_d4sign integracoes_d4sign_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integracoes_d4sign
    ADD CONSTRAINT integracoes_d4sign_pkey PRIMARY KEY (id);


--
-- Name: lancamento lancamento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lancamento
    ADD CONSTRAINT lancamento_pkey PRIMARY KEY (id);


--
-- Name: log_acesso_delegado log_acesso_delegado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acesso_delegado
    ADD CONSTRAINT log_acesso_delegado_pkey PRIMARY KEY (id);


--
-- Name: log_acoes_gerenciais log_acoes_gerenciais_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acoes_gerenciais
    ADD CONSTRAINT log_acoes_gerenciais_pkey PRIMARY KEY (id);


--
-- Name: log_autorizacoes log_autorizacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_autorizacoes
    ADD CONSTRAINT log_autorizacoes_pkey PRIMARY KEY (id);


--
-- Name: lojas lojas_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lojas
    ADD CONSTRAINT lojas_codigo_key UNIQUE (codigo);


--
-- Name: lojas lojas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lojas
    ADD CONSTRAINT lojas_pkey PRIMARY KEY (id);


--
-- Name: medicoes medicoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicoes
    ADD CONSTRAINT medicoes_pkey PRIMARY KEY (id);


--
-- Name: medicoes medicoes_projeto_nome_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicoes
    ADD CONSTRAINT medicoes_projeto_nome_key UNIQUE (projeto_nome);


--
-- Name: mensagem_anexos mensagem_anexos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensagem_anexos
    ADD CONSTRAINT mensagem_anexos_pkey PRIMARY KEY (id);


--
-- Name: numero_conectado numero_conectado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.numero_conectado
    ADD CONSTRAINT numero_conectado_pkey PRIMARY KEY (id);


--
-- Name: orcamento_ambientes orcamento_ambientes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orcamento_ambientes
    ADD CONSTRAINT orcamento_ambientes_pkey PRIMARY KEY (orcamento_id, pool_ambiente_id);


--
-- Name: orcamentos orcamentos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orcamentos
    ADD CONSTRAINT orcamentos_pkey PRIMARY KEY (id);


--
-- Name: parceiro_lojas parceiro_lojas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parceiro_lojas
    ADD CONSTRAINT parceiro_lojas_pkey PRIMARY KEY (id);


--
-- Name: parceiros parceiros_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parceiros
    ADD CONSTRAINT parceiros_pkey PRIMARY KEY (id);


--
-- Name: parcela_ambiente parcela_ambiente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parcela_ambiente
    ADD CONSTRAINT parcela_ambiente_pkey PRIMARY KEY (parcela_id, pool_ambiente_id);


--
-- Name: parcela_projeto parcela_projeto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parcela_projeto
    ADD CONSTRAINT parcela_projeto_pkey PRIMARY KEY (id);


--
-- Name: perfil_acesso perfil_acesso_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_acesso
    ADD CONSTRAINT perfil_acesso_pkey PRIMARY KEY (id);


--
-- Name: perfil_emissao perfil_emissao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_emissao
    ADD CONSTRAINT perfil_emissao_pkey PRIMARY KEY (id);


--
-- Name: periodo_contabil periodo_contabil_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodo_contabil
    ADD CONSTRAINT periodo_contabil_pkey PRIMARY KEY (id);


--
-- Name: pool_ambientes pool_ambientes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pool_ambientes
    ADD CONSTRAINT pool_ambientes_pkey PRIMARY KEY (id);


--
-- Name: projetos_meta projetos_meta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projetos_meta
    ADD CONSTRAINT projetos_meta_pkey PRIMARY KEY (nome_safe);


--
-- Name: provisao_data_prevista provisao_data_prevista_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_data_prevista
    ADD CONSTRAINT provisao_data_prevista_pkey PRIMARY KEY (id);


--
-- Name: provisao_registro provisao_registro_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_registro
    ADD CONSTRAINT provisao_registro_pkey PRIMARY KEY (id);


--
-- Name: recebivel recebivel_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebivel
    ADD CONSTRAINT recebivel_pkey PRIMARY KEY (id);


--
-- Name: recebivel recebivel_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebivel
    ADD CONSTRAINT recebivel_ref_key UNIQUE (ref);


--
-- Name: redes redes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.redes
    ADD CONSTRAINT redes_pkey PRIMARY KEY (id);


--
-- Name: retencao_obra retencao_obra_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retencao_obra
    ADD CONSTRAINT retencao_obra_pkey PRIMARY KEY (id);


--
-- Name: segmento_config segmento_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segmento_config
    ADD CONSTRAINT segmento_config_pkey PRIMARY KEY (id);


--
-- Name: sessoes sessoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes
    ADD CONSTRAINT sessoes_pkey PRIMARY KEY (id);


--
-- Name: sessoes sessoes_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes
    ADD CONSTRAINT sessoes_token_key UNIQUE (token);


--
-- Name: simulador_autorizacoes simulador_autorizacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulador_autorizacoes
    ADD CONSTRAINT simulador_autorizacoes_pkey PRIMARY KEY (id);


--
-- Name: simulador_log_acessos simulador_log_acessos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulador_log_acessos
    ADD CONSTRAINT simulador_log_acessos_pkey PRIMARY KEY (id);


--
-- Name: sinal_retido sinal_retido_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sinal_retido
    ADD CONSTRAINT sinal_retido_pkey PRIMARY KEY (id);


--
-- Name: solicitacoes_medicao_assinaturas solicitacoes_medicao_assinaturas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes_medicao_assinaturas
    ADD CONSTRAINT solicitacoes_medicao_assinaturas_pkey PRIMARY KEY (id);


--
-- Name: solicitacoes_medicao solicitacoes_medicao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes_medicao
    ADD CONSTRAINT solicitacoes_medicao_pkey PRIMARY KEY (id);


--
-- Name: template_mensagem template_mensagem_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.template_mensagem
    ADD CONSTRAINT template_mensagem_pkey PRIMARY KEY (id);


--
-- Name: terceiros terceiros_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.terceiros
    ADD CONSTRAINT terceiros_pkey PRIMARY KEY (id);


--
-- Name: triagem_config triagem_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triagem_config
    ADD CONSTRAINT triagem_config_pkey PRIMARY KEY (id);


--
-- Name: triagem_entradas triagem_entradas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triagem_entradas
    ADD CONSTRAINT triagem_entradas_pkey PRIMARY KEY (id);


--
-- Name: adiantamento_funcionario uq_adiantamento_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adiantamento_funcionario
    ADD CONSTRAINT uq_adiantamento_ref UNIQUE (ref);


--
-- Name: arquivo_pe uq_arquivo_pe; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.arquivo_pe
    ADD CONSTRAINT uq_arquivo_pe UNIQUE (projeto_nome, pool_ambiente_id, formato);


--
-- Name: centro_custo uq_centro_custo_owner_codigo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.centro_custo
    ADD CONSTRAINT uq_centro_custo_owner_codigo UNIQUE (owner_tipo, owner_id, codigo);


--
-- Name: ciclo_etapas uq_ciclo_etapa; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas
    ADD CONSTRAINT uq_ciclo_etapa UNIQUE (projeto_nome, etapa_codigo);


--
-- Name: comissao_folha uq_comissao_ref_etapa; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comissao_folha
    ADD CONSTRAINT uq_comissao_ref_etapa UNIQUE (ref_etapa);


--
-- Name: conta uq_conta_owner_codigo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conta
    ADD CONSTRAINT uq_conta_owner_codigo UNIQUE (owner_tipo, owner_id, codigo);


--
-- Name: documento_modelos uq_doc_modelo_versao; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_modelos
    ADD CONSTRAINT uq_doc_modelo_versao UNIQUE (loja_id, tipo, versao);


--
-- Name: documento_tipos uq_documento_tipos_loja_slug; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_tipos
    ADD CONSTRAINT uq_documento_tipos_loja_slug UNIQUE (loja_id, slug);


--
-- Name: perfil_emissao uq_perfil_emissao; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_emissao
    ADD CONSTRAINT uq_perfil_emissao UNIQUE (owner_tipo, owner_id, tipo_doc);


--
-- Name: perfil_acesso uq_perfil_loja_slug; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_acesso
    ADD CONSTRAINT uq_perfil_loja_slug UNIQUE (loja_id, slug);


--
-- Name: provisao_data_prevista uq_provisao_data_prevista; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_data_prevista
    ADD CONSTRAINT uq_provisao_data_prevista UNIQUE (projeto_nome, codigo_conta);


--
-- Name: provisao_registro uq_provisao_orc_versao; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_registro
    ADD CONSTRAINT uq_provisao_orc_versao UNIQUE (orcamento_id, versao);


--
-- Name: segmento_config uq_segmento_config; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segmento_config
    ADD CONSTRAINT uq_segmento_config UNIQUE (loja_id, segmento);


--
-- Name: sinal_retido uq_sinal_retido; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sinal_retido
    ADD CONSTRAINT uq_sinal_retido UNIQUE (projeto_nome, pool_ambiente_id);


--
-- Name: usuario_lojas uq_usuario_loja; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_lojas
    ADD CONSTRAINT uq_usuario_loja UNIQUE (usuario_id, loja_id);


--
-- Name: usuario_lojas usuario_lojas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_lojas
    ADD CONSTRAINT usuario_lojas_pkey PRIMARY KEY (id);


--
-- Name: usuario_presenca usuario_presenca_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_presenca
    ADD CONSTRAINT usuario_presenca_pkey PRIMARY KEY (usuario_id);


--
-- Name: usuarios usuarios_login_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_login_key UNIQUE (login);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: ix_acordo_fabrica_contraparte_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acordo_fabrica_contraparte_id ON public.acordo_fabrica USING btree (contraparte_id);


--
-- Name: ix_acordo_fabrica_loja_titular_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acordo_fabrica_loja_titular_id ON public.acordo_fabrica USING btree (loja_titular_id);


--
-- Name: ix_acordo_movimento_acordo_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acordo_movimento_acordo_id ON public.acordo_movimento USING btree (acordo_id);


--
-- Name: ix_adiantamento_funcionario_funcionario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_adiantamento_funcionario_funcionario_id ON public.adiantamento_funcionario USING btree (funcionario_id);


--
-- Name: ix_adiantamento_funcionario_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_adiantamento_funcionario_loja_id ON public.adiantamento_funcionario USING btree (loja_id);


--
-- Name: ix_aditivos_assinaturas_aditivo_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aditivos_assinaturas_aditivo_id ON public.aditivos_assinaturas USING btree (aditivo_id);


--
-- Name: ix_aditivos_contrato_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aditivos_contrato_id ON public.aditivos USING btree (contrato_id);


--
-- Name: ix_aditivos_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aditivos_loja_id ON public.aditivos USING btree (loja_id);


--
-- Name: ix_aditivos_modelo_versao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aditivos_modelo_versao_id ON public.aditivos USING btree (modelo_versao_id);


--
-- Name: ix_aditivos_orcamento_complemento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aditivos_orcamento_complemento_id ON public.aditivos USING btree (orcamento_complemento_id);


--
-- Name: ix_aditivos_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aditivos_projeto_nome ON public.aditivos USING btree (projeto_nome);


--
-- Name: ix_ajuste_fabrica_acordo_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ajuste_fabrica_acordo_id ON public.ajuste_fabrica USING btree (acordo_id);


--
-- Name: ix_ajuste_fabrica_aplicacao_ajuste_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ajuste_fabrica_aplicacao_ajuste_id ON public.ajuste_fabrica_aplicacao USING btree (ajuste_id);


--
-- Name: ix_ajuste_fabrica_aplicacao_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ajuste_fabrica_aplicacao_projeto_nome ON public.ajuste_fabrica_aplicacao USING btree (projeto_nome);


--
-- Name: ix_ajuste_fabrica_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ajuste_fabrica_loja_id ON public.ajuste_fabrica USING btree (loja_id);


--
-- Name: ix_aprovacoes_pe_assinaturas_aprovacao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aprovacoes_pe_assinaturas_aprovacao_id ON public.aprovacoes_pe_assinaturas USING btree (aprovacao_id);


--
-- Name: ix_aprovacoes_pe_contrato_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aprovacoes_pe_contrato_id ON public.aprovacoes_pe USING btree (contrato_id);


--
-- Name: ix_aprovacoes_pe_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aprovacoes_pe_loja_id ON public.aprovacoes_pe USING btree (loja_id);


--
-- Name: ix_aprovacoes_pe_modelo_versao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aprovacoes_pe_modelo_versao_id ON public.aprovacoes_pe USING btree (modelo_versao_id);


--
-- Name: ix_aprovacoes_pe_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aprovacoes_pe_projeto_nome ON public.aprovacoes_pe USING btree (projeto_nome);


--
-- Name: ix_arquivo_pe_pool_ambiente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_arquivo_pe_pool_ambiente_id ON public.arquivo_pe USING btree (pool_ambiente_id);


--
-- Name: ix_arquivo_pe_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_arquivo_pe_projeto_nome ON public.arquivo_pe USING btree (projeto_nome);


--
-- Name: ix_assistencia_anexos_caso_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assistencia_anexos_caso_id ON public.assistencia_anexos USING btree (caso_id);


--
-- Name: ix_assistencia_caso_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assistencia_caso_loja_id ON public.assistencia_caso USING btree (loja_id);


--
-- Name: ix_assistencia_caso_pool_ambiente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assistencia_caso_pool_ambiente_id ON public.assistencia_caso USING btree (pool_ambiente_id);


--
-- Name: ix_assistencia_executores_caso_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assistencia_executores_caso_id ON public.assistencia_executores USING btree (caso_id);


--
-- Name: ix_assistencia_executores_funcionario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assistencia_executores_funcionario_id ON public.assistencia_executores USING btree (funcionario_id);


--
-- Name: ix_assistencia_executores_terceiro_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assistencia_executores_terceiro_id ON public.assistencia_executores USING btree (terceiro_id);


--
-- Name: ix_assuntos_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assuntos_loja_id ON public.assuntos USING btree (loja_id);


--
-- Name: ix_atribuicoes_ambiente_funcionario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_atribuicoes_ambiente_funcionario_id ON public.atribuicoes_ambiente USING btree (funcionario_id);


--
-- Name: ix_atribuicoes_ambiente_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_atribuicoes_ambiente_loja_id ON public.atribuicoes_ambiente USING btree (loja_id);


--
-- Name: ix_atribuicoes_ambiente_pool_ambiente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_atribuicoes_ambiente_pool_ambiente_id ON public.atribuicoes_ambiente USING btree (pool_ambiente_id);


--
-- Name: ix_atribuicoes_ambiente_terceiro_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_atribuicoes_ambiente_terceiro_id ON public.atribuicoes_ambiente USING btree (terceiro_id);


--
-- Name: ix_briefings_cliente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_briefings_cliente_id ON public.briefings USING btree (cliente_id);


--
-- Name: ix_centro_custo_pai_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_centro_custo_pai_id ON public.centro_custo USING btree (pai_id);


--
-- Name: ix_ciclo_etapas_responsavel_funcionario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_etapas_responsavel_funcionario ON public.ciclo_etapas USING btree (responsavel_funcionario_id);


--
-- Name: ix_ciclo_etapas_responsavel_terceiro_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_etapas_responsavel_terceiro_id ON public.ciclo_etapas USING btree (responsavel_terceiro_id);


--
-- Name: ix_ciclo_etapas_transf_dest_func; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_etapas_transf_dest_func ON public.ciclo_etapas USING btree (transferencia_destino_funcionario_id) WHERE ((transferencia_status)::text = 'pendente'::text);


--
-- Name: ix_ciclo_etapas_transf_dest_terc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_etapas_transf_dest_terc ON public.ciclo_etapas USING btree (transferencia_destino_terceiro_id) WHERE ((transferencia_status)::text = 'pendente'::text);


--
-- Name: ix_ciclo_etapas_transferencia_destino_funcionario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_etapas_transferencia_destino_funcionario_id ON public.ciclo_etapas USING btree (transferencia_destino_funcionario_id);


--
-- Name: ix_ciclo_etapas_transferencia_destino_terceiro_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_etapas_transferencia_destino_terceiro_id ON public.ciclo_etapas USING btree (transferencia_destino_terceiro_id);


--
-- Name: ix_ciclo_etapas_transferencia_solicitada_por_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_etapas_transferencia_solicitada_por_usuario_id ON public.ciclo_etapas USING btree (transferencia_solicitada_por_usuario_id);


--
-- Name: ix_ciclo_logistico_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_logistico_loja_id ON public.ciclo_logistico USING btree (loja_id);


--
-- Name: ix_ciclo_logistico_nfe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_logistico_nfe_id ON public.ciclo_logistico USING btree (nfe_id);


--
-- Name: ix_ciclo_logistico_parcela_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_logistico_parcela_id ON public.ciclo_logistico USING btree (parcela_id);


--
-- Name: ix_ciclo_logistico_transicao_ciclo_logistico_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_logistico_transicao_ciclo_logistico_id ON public.ciclo_logistico_transicao USING btree (ciclo_logistico_id);


--
-- Name: ix_ciclo_revisoes_relatorio_doc_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ciclo_revisoes_relatorio_doc_id ON public.ciclo_revisoes USING btree (relatorio_doc_id);


--
-- Name: ix_clientes_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clientes_loja_id ON public.clientes USING btree (loja_id);


--
-- Name: ix_comissao_folha_funcionario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comissao_folha_funcionario_id ON public.comissao_folha USING btree (funcionario_id);


--
-- Name: ix_comissao_folha_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comissao_folha_loja_id ON public.comissao_folha USING btree (loja_id);


--
-- Name: ix_conciliacao_pe_fase_parcela_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conciliacao_pe_fase_parcela_id ON public.conciliacao_pe_fase USING btree (parcela_id);


--
-- Name: ix_conciliacao_pe_fase_pool_ambiente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conciliacao_pe_fase_pool_ambiente_id ON public.conciliacao_pe_fase USING btree (pool_ambiente_id);


--
-- Name: ix_conciliacao_pe_fase_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conciliacao_pe_fase_projeto_nome ON public.conciliacao_pe_fase USING btree (projeto_nome);


--
-- Name: ix_conta_centro_custo_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conta_centro_custo_id ON public.conta USING btree (centro_custo_id);


--
-- Name: ix_conta_pai_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conta_pai_id ON public.conta USING btree (pai_id);


--
-- Name: ix_contato_confirmacoes_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contato_confirmacoes_loja_id ON public.contato_confirmacoes USING btree (loja_id);


--
-- Name: ix_contato_confirmacoes_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contato_confirmacoes_projeto_nome ON public.contato_confirmacoes USING btree (projeto_nome);


--
-- Name: ix_contratos_assinaturas_contrato_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contratos_assinaturas_contrato_id ON public.contratos_assinaturas USING btree (contrato_id);


--
-- Name: ix_contratos_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contratos_loja_id ON public.contratos USING btree (loja_id);


--
-- Name: ix_contratos_modelo_versao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contratos_modelo_versao_id ON public.contratos USING btree (modelo_versao_id);


--
-- Name: ix_contratos_orcamento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contratos_orcamento_id ON public.contratos USING btree (orcamento_id);


--
-- Name: ix_conversa_mensagens_conversa_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversa_mensagens_conversa_id ON public.conversa_mensagens USING btree (conversa_id);


--
-- Name: ix_conversa_mensagens_destinatario_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversa_mensagens_destinatario_usuario_id ON public.conversa_mensagens USING btree (destinatario_usuario_id);


--
-- Name: ix_conversa_mensagens_documento_ref_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversa_mensagens_documento_ref_id ON public.conversa_mensagens USING btree (documento_ref_id);


--
-- Name: ix_conversa_mensagens_transferido_para_funcionario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversa_mensagens_transferido_para_funcionario_id ON public.conversa_mensagens USING btree (transferido_para_funcionario_id);


--
-- Name: ix_conversa_participantes_conversa_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversa_participantes_conversa_id ON public.conversa_participantes USING btree (conversa_id);


--
-- Name: ix_conversa_participantes_externos_conversa_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversa_participantes_externos_conversa_id ON public.conversa_participantes_externos USING btree (conversa_id);


--
-- Name: ix_conversa_participantes_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversa_participantes_usuario_id ON public.conversa_participantes USING btree (usuario_id);


--
-- Name: ix_conversas_assunto_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversas_assunto_id ON public.conversas USING btree (assunto_id);


--
-- Name: ix_conversas_cliente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversas_cliente_id ON public.conversas USING btree (cliente_id);


--
-- Name: ix_conversas_concluido_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversas_concluido_por_id ON public.conversas USING btree (concluido_por_id);


--
-- Name: ix_conversas_criado_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversas_criado_por_id ON public.conversas USING btree (criado_por_id);


--
-- Name: ix_conversas_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversas_loja_id ON public.conversas USING btree (loja_id);


--
-- Name: ix_conversas_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversas_projeto_nome ON public.conversas USING btree (projeto_nome);


--
-- Name: ix_conversas_rede_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversas_rede_id ON public.conversas USING btree (rede_id);


--
-- Name: ix_conversas_responsavel_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversas_responsavel_usuario_id ON public.conversas USING btree (responsavel_usuario_id);


--
-- Name: ix_documento_fiscal_danfe_doc_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documento_fiscal_danfe_doc_id ON public.documento_fiscal USING btree (danfe_doc_id);


--
-- Name: ix_documento_fiscal_emitente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documento_fiscal_emitente_id ON public.documento_fiscal USING btree (emitente_id);


--
-- Name: ix_documento_fiscal_fabrica_doc_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documento_fiscal_fabrica_doc_id ON public.documento_fiscal USING btree (fabrica_doc_id);


--
-- Name: ix_documento_fiscal_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documento_fiscal_loja_id ON public.documento_fiscal USING btree (loja_id);


--
-- Name: ix_documento_fiscal_xml_doc_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documento_fiscal_xml_doc_id ON public.documento_fiscal USING btree (xml_doc_id);


--
-- Name: ix_documento_tipos_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documento_tipos_loja_id ON public.documento_tipos USING btree (loja_id);


--
-- Name: ix_emitente_rede_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emitente_rede_id ON public.emitente USING btree (rede_id);


--
-- Name: ix_envios_externos_destinatario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_envios_externos_destinatario ON public.envios_externos USING btree (destinatario_tipo, destinatario_id);


--
-- Name: ix_envios_externos_id_externo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_envios_externos_id_externo ON public.envios_externos USING btree (id_externo);


--
-- Name: ix_envios_externos_mensagem_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_envios_externos_mensagem_id ON public.envios_externos USING btree (mensagem_id);


--
-- Name: ix_envios_externos_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_envios_externos_template_id ON public.envios_externos USING btree (template_id);


--
-- Name: ix_envios_externos_triagem_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_envios_externos_triagem_id ON public.envios_externos USING btree (triagem_id);


--
-- Name: ix_folha_pagamento_funcionario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_folha_pagamento_funcionario_id ON public.folha_pagamento USING btree (funcionario_id);


--
-- Name: ix_folha_pagamento_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_folha_pagamento_loja_id ON public.folha_pagamento USING btree (loja_id);


--
-- Name: ix_fornecedores_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fornecedores_loja_id ON public.fornecedores USING btree (loja_id);


--
-- Name: ix_funcionarios_funcao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_funcionarios_funcao_id ON public.funcionarios USING btree (funcao_id);


--
-- Name: ix_funcionarios_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_funcionarios_loja_id ON public.funcionarios USING btree (loja_id);


--
-- Name: ix_funcoes_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_funcoes_loja_id ON public.funcoes USING btree (loja_id);


--
-- Name: ix_integracoes_clicksign_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integracoes_clicksign_loja_id ON public.integracoes_clicksign USING btree (loja_id);


--
-- Name: ix_integracoes_clicksign_rede_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integracoes_clicksign_rede_id ON public.integracoes_clicksign USING btree (rede_id);


--
-- Name: ix_integracoes_d4sign_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integracoes_d4sign_loja_id ON public.integracoes_d4sign USING btree (loja_id);


--
-- Name: ix_integracoes_d4sign_rede_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integracoes_d4sign_rede_id ON public.integracoes_d4sign USING btree (rede_id);


--
-- Name: ix_lancamento_conta_credito_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lancamento_conta_credito_id ON public.lancamento USING btree (conta_credito_id);


--
-- Name: ix_lancamento_conta_debito_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lancamento_conta_debito_id ON public.lancamento USING btree (conta_debito_id);


--
-- Name: ix_lancamento_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lancamento_owner ON public.lancamento USING btree (owner_tipo, owner_id);


--
-- Name: ix_lojas_emitente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lojas_emitente_id ON public.lojas USING btree (emitente_id);


--
-- Name: ix_lojas_loja_mae_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lojas_loja_mae_id ON public.lojas USING btree (loja_mae_id);


--
-- Name: ix_lojas_rede_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lojas_rede_id ON public.lojas USING btree (rede_id);


--
-- Name: ix_mensagem_anexos_mensagem_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensagem_anexos_mensagem_id ON public.mensagem_anexos USING btree (mensagem_id);


--
-- Name: ix_numero_conectado_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_numero_conectado_loja_id ON public.numero_conectado USING btree (loja_id);


--
-- Name: ix_orcamento_ambientes_pool_ambiente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_orcamento_ambientes_pool_ambiente_id ON public.orcamento_ambientes USING btree (pool_ambiente_id);


--
-- Name: ix_orcamentos_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_orcamentos_loja_id ON public.orcamentos USING btree (loja_id);


--
-- Name: ix_orcamentos_parcela_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_orcamentos_parcela_id ON public.orcamentos USING btree (parcela_id);


--
-- Name: ix_parceiro_lojas_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parceiro_lojas_loja_id ON public.parceiro_lojas USING btree (loja_id);


--
-- Name: ix_parceiro_lojas_parceiro_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parceiro_lojas_parceiro_id ON public.parceiro_lojas USING btree (parceiro_id);


--
-- Name: ix_parceiros_rede_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parceiros_rede_id ON public.parceiros USING btree (rede_id);


--
-- Name: ix_parcela_ambiente_pool_ambiente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parcela_ambiente_pool_ambiente_id ON public.parcela_ambiente USING btree (pool_ambiente_id);


--
-- Name: ix_parcela_projeto_orcamento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parcela_projeto_orcamento_id ON public.parcela_projeto USING btree (orcamento_id);


--
-- Name: ix_parcela_projeto_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parcela_projeto_projeto_nome ON public.parcela_projeto USING btree (projeto_nome);


--
-- Name: ix_perfil_emissao_emitente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_perfil_emissao_emitente_id ON public.perfil_emissao USING btree (emitente_id);


--
-- Name: ix_periodo_contabil_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_periodo_contabil_owner ON public.periodo_contabil USING btree (owner_tipo, owner_id);


--
-- Name: ix_projetos_meta_cliente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_projetos_meta_cliente_id ON public.projetos_meta USING btree (cliente_id);


--
-- Name: ix_projetos_meta_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_projetos_meta_loja_id ON public.projetos_meta USING btree (loja_id);


--
-- Name: ix_provisao_data_prevista_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_provisao_data_prevista_loja_id ON public.provisao_data_prevista USING btree (loja_id);


--
-- Name: ix_provisao_registro_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_provisao_registro_por_id ON public.provisao_registro USING btree (por_id);


--
-- Name: ix_recebivel_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recebivel_loja_id ON public.recebivel USING btree (loja_id);


--
-- Name: ix_recebivel_orcamento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recebivel_orcamento_id ON public.recebivel USING btree (orcamento_id);


--
-- Name: ix_redes_emitente_central_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_redes_emitente_central_id ON public.redes USING btree (emitente_central_id);


--
-- Name: ix_retencao_obra_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_retencao_obra_projeto_nome ON public.retencao_obra USING btree (projeto_nome);


--
-- Name: ix_segmento_config_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_segmento_config_loja_id ON public.segmento_config USING btree (loja_id);


--
-- Name: ix_segmento_config_responsavel_funcionario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_segmento_config_responsavel_funcionario_id ON public.segmento_config USING btree (responsavel_funcionario_id);


--
-- Name: ix_segmento_config_template_padrao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_segmento_config_template_padrao_id ON public.segmento_config USING btree (template_padrao_id);


--
-- Name: ix_simulador_autorizacoes_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_simulador_autorizacoes_loja_id ON public.simulador_autorizacoes USING btree (loja_id);


--
-- Name: ix_simulador_log_acessos_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_simulador_log_acessos_loja_id ON public.simulador_log_acessos USING btree (loja_id);


--
-- Name: ix_sinal_retido_pool_ambiente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sinal_retido_pool_ambiente_id ON public.sinal_retido USING btree (pool_ambiente_id);


--
-- Name: ix_sinal_retido_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sinal_retido_projeto_nome ON public.sinal_retido USING btree (projeto_nome);


--
-- Name: ix_solicitacoes_medicao_assinaturas_solicitacao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_medicao_assinaturas_solicitacao_id ON public.solicitacoes_medicao_assinaturas USING btree (solicitacao_id);


--
-- Name: ix_solicitacoes_medicao_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_medicao_loja_id ON public.solicitacoes_medicao USING btree (loja_id);


--
-- Name: ix_solicitacoes_medicao_modelo_versao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_medicao_modelo_versao_id ON public.solicitacoes_medicao USING btree (modelo_versao_id);


--
-- Name: ix_solicitacoes_medicao_projeto_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_medicao_projeto_nome ON public.solicitacoes_medicao USING btree (projeto_nome);


--
-- Name: ix_template_mensagem_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_template_mensagem_loja_id ON public.template_mensagem USING btree (loja_id);


--
-- Name: ix_terceiros_funcao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_terceiros_funcao_id ON public.terceiros USING btree (funcao_id);


--
-- Name: ix_terceiros_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_terceiros_loja_id ON public.terceiros USING btree (loja_id);


--
-- Name: ix_triagem_config_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_triagem_config_loja_id ON public.triagem_config USING btree (loja_id);


--
-- Name: ix_triagem_entradas_conversa_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_triagem_entradas_conversa_id ON public.triagem_entradas USING btree (conversa_id);


--
-- Name: ix_triagem_entradas_id_externo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_triagem_entradas_id_externo ON public.triagem_entradas USING btree (id_externo);


--
-- Name: ix_triagem_entradas_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_triagem_entradas_loja_id ON public.triagem_entradas USING btree (loja_id);


--
-- Name: ix_usuario_lojas_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuario_lojas_loja_id ON public.usuario_lojas USING btree (loja_id);


--
-- Name: ix_usuarios_funcao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_funcao_id ON public.usuarios USING btree (funcao_id);


--
-- Name: ix_usuarios_funcionario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_funcionario_id ON public.usuarios USING btree (funcionario_id);


--
-- Name: ix_usuarios_loja_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_loja_id ON public.usuarios USING btree (loja_id);


--
-- Name: ix_usuarios_rede_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_rede_id ON public.usuarios USING btree (rede_id);


--
-- Name: uq_atribuicao_papel_ambiente; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_atribuicao_papel_ambiente ON public.atribuicoes_ambiente USING btree (projeto_nome, pool_ambiente_id, papel) WHERE (papel <> 'montagem'::text);


--
-- Name: acordo_fabrica acordo_fabrica_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acordo_fabrica
    ADD CONSTRAINT acordo_fabrica_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: acordo_fabrica acordo_fabrica_loja_titular_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acordo_fabrica
    ADD CONSTRAINT acordo_fabrica_loja_titular_id_fkey FOREIGN KEY (loja_titular_id) REFERENCES public.lojas(id);


--
-- Name: acordo_movimento acordo_movimento_acordo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acordo_movimento
    ADD CONSTRAINT acordo_movimento_acordo_id_fkey FOREIGN KEY (acordo_id) REFERENCES public.acordo_fabrica(id);


--
-- Name: acordo_movimento acordo_movimento_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acordo_movimento
    ADD CONSTRAINT acordo_movimento_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: adiantamento_funcionario adiantamento_funcionario_funcionario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adiantamento_funcionario
    ADD CONSTRAINT adiantamento_funcionario_funcionario_id_fkey FOREIGN KEY (funcionario_id) REFERENCES public.funcionarios(id);


--
-- Name: adiantamento_funcionario adiantamento_funcionario_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adiantamento_funcionario
    ADD CONSTRAINT adiantamento_funcionario_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: aditivos_assinaturas aditivos_assinaturas_aditivo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos_assinaturas
    ADD CONSTRAINT aditivos_assinaturas_aditivo_id_fkey FOREIGN KEY (aditivo_id) REFERENCES public.aditivos(id);


--
-- Name: aditivos aditivos_contrato_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos
    ADD CONSTRAINT aditivos_contrato_id_fkey FOREIGN KEY (contrato_id) REFERENCES public.contratos(id);


--
-- Name: aditivos aditivos_gerado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos
    ADD CONSTRAINT aditivos_gerado_por_id_fkey FOREIGN KEY (gerado_por_id) REFERENCES public.usuarios(id);


--
-- Name: aditivos aditivos_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos
    ADD CONSTRAINT aditivos_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: aditivos aditivos_modelo_versao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos
    ADD CONSTRAINT aditivos_modelo_versao_id_fkey FOREIGN KEY (modelo_versao_id) REFERENCES public.documento_modelos(id);


--
-- Name: aditivos aditivos_orcamento_complemento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aditivos
    ADD CONSTRAINT aditivos_orcamento_complemento_id_fkey FOREIGN KEY (orcamento_complemento_id) REFERENCES public.orcamentos(id);


--
-- Name: ajuste_fabrica ajuste_fabrica_acordo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ajuste_fabrica
    ADD CONSTRAINT ajuste_fabrica_acordo_id_fkey FOREIGN KEY (acordo_id) REFERENCES public.acordo_fabrica(id);


--
-- Name: ajuste_fabrica_aplicacao ajuste_fabrica_aplicacao_ajuste_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ajuste_fabrica_aplicacao
    ADD CONSTRAINT ajuste_fabrica_aplicacao_ajuste_id_fkey FOREIGN KEY (ajuste_id) REFERENCES public.ajuste_fabrica(id);


--
-- Name: ajuste_fabrica ajuste_fabrica_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ajuste_fabrica
    ADD CONSTRAINT ajuste_fabrica_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: ajuste_fabrica ajuste_fabrica_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ajuste_fabrica
    ADD CONSTRAINT ajuste_fabrica_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: aprovacoes_pe_assinaturas aprovacoes_pe_assinaturas_aprovacao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aprovacoes_pe_assinaturas
    ADD CONSTRAINT aprovacoes_pe_assinaturas_aprovacao_id_fkey FOREIGN KEY (aprovacao_id) REFERENCES public.aprovacoes_pe(id);


--
-- Name: aprovacoes_pe aprovacoes_pe_contrato_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aprovacoes_pe
    ADD CONSTRAINT aprovacoes_pe_contrato_id_fkey FOREIGN KEY (contrato_id) REFERENCES public.contratos(id);


--
-- Name: aprovacoes_pe aprovacoes_pe_gerado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aprovacoes_pe
    ADD CONSTRAINT aprovacoes_pe_gerado_por_id_fkey FOREIGN KEY (gerado_por_id) REFERENCES public.usuarios(id);


--
-- Name: aprovacoes_pe aprovacoes_pe_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aprovacoes_pe
    ADD CONSTRAINT aprovacoes_pe_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: aprovacoes_pe aprovacoes_pe_modelo_versao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aprovacoes_pe
    ADD CONSTRAINT aprovacoes_pe_modelo_versao_id_fkey FOREIGN KEY (modelo_versao_id) REFERENCES public.documento_modelos(id);


--
-- Name: arquivo_pe arquivo_pe_carregado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.arquivo_pe
    ADD CONSTRAINT arquivo_pe_carregado_por_id_fkey FOREIGN KEY (carregado_por_id) REFERENCES public.usuarios(id);


--
-- Name: arquivo_pe arquivo_pe_pool_ambiente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.arquivo_pe
    ADD CONSTRAINT arquivo_pe_pool_ambiente_id_fkey FOREIGN KEY (pool_ambiente_id) REFERENCES public.pool_ambientes(id);


--
-- Name: assistencia_anexos assistencia_anexos_caso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_anexos
    ADD CONSTRAINT assistencia_anexos_caso_id_fkey FOREIGN KEY (caso_id) REFERENCES public.assistencia_caso(id);


--
-- Name: assistencia_anexos assistencia_anexos_enviado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_anexos
    ADD CONSTRAINT assistencia_anexos_enviado_por_id_fkey FOREIGN KEY (enviado_por_id) REFERENCES public.usuarios(id);


--
-- Name: assistencia_caso assistencia_caso_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_caso
    ADD CONSTRAINT assistencia_caso_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: assistencia_caso assistencia_caso_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_caso
    ADD CONSTRAINT assistencia_caso_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: assistencia_executores assistencia_executores_caso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_executores
    ADD CONSTRAINT assistencia_executores_caso_id_fkey FOREIGN KEY (caso_id) REFERENCES public.assistencia_caso(id);


--
-- Name: assistencia_executores assistencia_executores_funcionario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_executores
    ADD CONSTRAINT assistencia_executores_funcionario_id_fkey FOREIGN KEY (funcionario_id) REFERENCES public.funcionarios(id);


--
-- Name: assistencia_executores assistencia_executores_terceiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_executores
    ADD CONSTRAINT assistencia_executores_terceiro_id_fkey FOREIGN KEY (terceiro_id) REFERENCES public.terceiros(id);


--
-- Name: assuntos assuntos_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assuntos
    ADD CONSTRAINT assuntos_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: assuntos assuntos_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assuntos
    ADD CONSTRAINT assuntos_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: atribuicoes_ambiente atribuicoes_ambiente_atribuido_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atribuicoes_ambiente
    ADD CONSTRAINT atribuicoes_ambiente_atribuido_por_id_fkey FOREIGN KEY (atribuido_por_id) REFERENCES public.usuarios(id);


--
-- Name: atribuicoes_ambiente atribuicoes_ambiente_funcionario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atribuicoes_ambiente
    ADD CONSTRAINT atribuicoes_ambiente_funcionario_id_fkey FOREIGN KEY (funcionario_id) REFERENCES public.funcionarios(id);


--
-- Name: atribuicoes_ambiente atribuicoes_ambiente_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atribuicoes_ambiente
    ADD CONSTRAINT atribuicoes_ambiente_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: atribuicoes_ambiente atribuicoes_ambiente_pool_ambiente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atribuicoes_ambiente
    ADD CONSTRAINT atribuicoes_ambiente_pool_ambiente_id_fkey FOREIGN KEY (pool_ambiente_id) REFERENCES public.pool_ambientes(id);


--
-- Name: atribuicoes_ambiente atribuicoes_ambiente_terceiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atribuicoes_ambiente
    ADD CONSTRAINT atribuicoes_ambiente_terceiro_id_fkey FOREIGN KEY (terceiro_id) REFERENCES public.terceiros(id);


--
-- Name: briefings briefings_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.briefings
    ADD CONSTRAINT briefings_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: briefings briefings_consultor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.briefings
    ADD CONSTRAINT briefings_consultor_id_fkey FOREIGN KEY (consultor_id) REFERENCES public.usuarios(id);


--
-- Name: centro_custo centro_custo_pai_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.centro_custo
    ADD CONSTRAINT centro_custo_pai_id_fkey FOREIGN KEY (pai_id) REFERENCES public.centro_custo(id);


--
-- Name: ciclo_documentos ciclo_documentos_enviado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_documentos
    ADD CONSTRAINT ciclo_documentos_enviado_por_id_fkey FOREIGN KEY (enviado_por_id) REFERENCES public.usuarios(id);


--
-- Name: ciclo_etapas ciclo_etapas_funcao_responsavel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas
    ADD CONSTRAINT ciclo_etapas_funcao_responsavel_id_fkey FOREIGN KEY (funcao_responsavel_id) REFERENCES public.funcoes(id);


--
-- Name: ciclo_etapas ciclo_etapas_responsavel_funcionario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas
    ADD CONSTRAINT ciclo_etapas_responsavel_funcionario_id_fkey FOREIGN KEY (responsavel_funcionario_id) REFERENCES public.funcionarios(id);


--
-- Name: ciclo_etapas ciclo_etapas_responsavel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas
    ADD CONSTRAINT ciclo_etapas_responsavel_id_fkey FOREIGN KEY (responsavel_id) REFERENCES public.usuarios(id);


--
-- Name: ciclo_logistico ciclo_logistico_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico
    ADD CONSTRAINT ciclo_logistico_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: ciclo_logistico ciclo_logistico_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico
    ADD CONSTRAINT ciclo_logistico_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: ciclo_logistico ciclo_logistico_nfe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico
    ADD CONSTRAINT ciclo_logistico_nfe_id_fkey FOREIGN KEY (nfe_id) REFERENCES public.documento_fiscal(id);


--
-- Name: ciclo_logistico ciclo_logistico_parcela_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico
    ADD CONSTRAINT ciclo_logistico_parcela_id_fkey FOREIGN KEY (parcela_id) REFERENCES public.parcela_projeto(id);


--
-- Name: ciclo_logistico_transicao ciclo_logistico_transicao_ciclo_logistico_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico_transicao
    ADD CONSTRAINT ciclo_logistico_transicao_ciclo_logistico_id_fkey FOREIGN KEY (ciclo_logistico_id) REFERENCES public.ciclo_logistico(id);


--
-- Name: ciclo_logistico_transicao ciclo_logistico_transicao_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_logistico_transicao
    ADD CONSTRAINT ciclo_logistico_transicao_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: ciclo_revisoes ciclo_revisoes_aberta_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_revisoes
    ADD CONSTRAINT ciclo_revisoes_aberta_por_id_fkey FOREIGN KEY (aberta_por_id) REFERENCES public.usuarios(id);


--
-- Name: ciclo_revisoes ciclo_revisoes_relatorio_doc_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_revisoes
    ADD CONSTRAINT ciclo_revisoes_relatorio_doc_id_fkey FOREIGN KEY (relatorio_doc_id) REFERENCES public.ciclo_documentos(id);


--
-- Name: clientes clientes_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: comissao_folha comissao_folha_funcionario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comissao_folha
    ADD CONSTRAINT comissao_folha_funcionario_id_fkey FOREIGN KEY (funcionario_id) REFERENCES public.funcionarios(id);


--
-- Name: comissao_folha comissao_folha_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comissao_folha
    ADD CONSTRAINT comissao_folha_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: conciliacao_pe_fase conciliacao_pe_fase_aprovador_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conciliacao_pe_fase
    ADD CONSTRAINT conciliacao_pe_fase_aprovador_id_fkey FOREIGN KEY (aprovador_id) REFERENCES public.usuarios(id);


--
-- Name: conciliacao_pe_fase conciliacao_pe_fase_parcela_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conciliacao_pe_fase
    ADD CONSTRAINT conciliacao_pe_fase_parcela_id_fkey FOREIGN KEY (parcela_id) REFERENCES public.parcela_projeto(id);


--
-- Name: conciliacao_pe_fase conciliacao_pe_fase_pool_ambiente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conciliacao_pe_fase
    ADD CONSTRAINT conciliacao_pe_fase_pool_ambiente_id_fkey FOREIGN KEY (pool_ambiente_id) REFERENCES public.pool_ambientes(id);


--
-- Name: conta conta_pai_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conta
    ADD CONSTRAINT conta_pai_id_fkey FOREIGN KEY (pai_id) REFERENCES public.conta(id);


--
-- Name: contato_confirmacoes contato_confirmacoes_confirmado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contato_confirmacoes
    ADD CONSTRAINT contato_confirmacoes_confirmado_por_id_fkey FOREIGN KEY (confirmado_por_id) REFERENCES public.usuarios(id);


--
-- Name: contato_confirmacoes contato_confirmacoes_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contato_confirmacoes
    ADD CONSTRAINT contato_confirmacoes_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: contraparte_financeira contraparte_financeira_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contraparte_financeira
    ADD CONSTRAINT contraparte_financeira_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: contratos_assinaturas contratos_assinaturas_contrato_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contratos_assinaturas
    ADD CONSTRAINT contratos_assinaturas_contrato_id_fkey FOREIGN KEY (contrato_id) REFERENCES public.contratos(id);


--
-- Name: contratos contratos_gerado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contratos
    ADD CONSTRAINT contratos_gerado_por_id_fkey FOREIGN KEY (gerado_por_id) REFERENCES public.usuarios(id);


--
-- Name: contratos contratos_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contratos
    ADD CONSTRAINT contratos_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: contratos contratos_modelo_versao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contratos
    ADD CONSTRAINT contratos_modelo_versao_id_fkey FOREIGN KEY (modelo_versao_id) REFERENCES public.documento_modelos(id);


--
-- Name: contratos contratos_orcamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contratos
    ADD CONSTRAINT contratos_orcamento_id_fkey FOREIGN KEY (orcamento_id) REFERENCES public.orcamentos(id);


--
-- Name: conversa_mensagens conversa_mensagens_autor_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_mensagens
    ADD CONSTRAINT conversa_mensagens_autor_usuario_id_fkey FOREIGN KEY (autor_usuario_id) REFERENCES public.usuarios(id);


--
-- Name: conversa_mensagens conversa_mensagens_conversa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_mensagens
    ADD CONSTRAINT conversa_mensagens_conversa_id_fkey FOREIGN KEY (conversa_id) REFERENCES public.conversas(id);


--
-- Name: conversa_participantes conversa_participantes_conversa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_participantes
    ADD CONSTRAINT conversa_participantes_conversa_id_fkey FOREIGN KEY (conversa_id) REFERENCES public.conversas(id);


--
-- Name: conversa_participantes_externos conversa_participantes_externos_conversa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_participantes_externos
    ADD CONSTRAINT conversa_participantes_externos_conversa_id_fkey FOREIGN KEY (conversa_id) REFERENCES public.conversas(id);


--
-- Name: conversa_participantes_externos conversa_participantes_externos_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_participantes_externos
    ADD CONSTRAINT conversa_participantes_externos_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: conversa_participantes conversa_participantes_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_participantes
    ADD CONSTRAINT conversa_participantes_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: conversas conversas_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversas
    ADD CONSTRAINT conversas_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: conversas conversas_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversas
    ADD CONSTRAINT conversas_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: documento_fiscal documento_fiscal_danfe_doc_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_fiscal
    ADD CONSTRAINT documento_fiscal_danfe_doc_id_fkey FOREIGN KEY (danfe_doc_id) REFERENCES public.ciclo_documentos(id);


--
-- Name: documento_fiscal documento_fiscal_emitente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_fiscal
    ADD CONSTRAINT documento_fiscal_emitente_id_fkey FOREIGN KEY (emitente_id) REFERENCES public.emitente(id);


--
-- Name: documento_fiscal documento_fiscal_fabrica_doc_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_fiscal
    ADD CONSTRAINT documento_fiscal_fabrica_doc_id_fkey FOREIGN KEY (fabrica_doc_id) REFERENCES public.ciclo_documentos(id);


--
-- Name: documento_fiscal documento_fiscal_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_fiscal
    ADD CONSTRAINT documento_fiscal_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: documento_fiscal documento_fiscal_xml_doc_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_fiscal
    ADD CONSTRAINT documento_fiscal_xml_doc_id_fkey FOREIGN KEY (xml_doc_id) REFERENCES public.ciclo_documentos(id);


--
-- Name: documento_modelos documento_modelos_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_modelos
    ADD CONSTRAINT documento_modelos_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: documento_modelos documento_modelos_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_modelos
    ADD CONSTRAINT documento_modelos_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: documento_tipos documento_tipos_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_tipos
    ADD CONSTRAINT documento_tipos_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: documento_tipos documento_tipos_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento_tipos
    ADD CONSTRAINT documento_tipos_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: emitente emitente_rede_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emitente
    ADD CONSTRAINT emitente_rede_id_fkey FOREIGN KEY (rede_id) REFERENCES public.redes(id);


--
-- Name: envios_externos envios_externos_mensagem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.envios_externos
    ADD CONSTRAINT envios_externos_mensagem_id_fkey FOREIGN KEY (mensagem_id) REFERENCES public.conversa_mensagens(id);


--
-- Name: acordo_fabrica fk_acordo_fabrica_contraparte_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acordo_fabrica
    ADD CONSTRAINT fk_acordo_fabrica_contraparte_id FOREIGN KEY (contraparte_id) REFERENCES public.contraparte_financeira(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: assistencia_caso fk_assistencia_caso_pool_ambiente_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistencia_caso
    ADD CONSTRAINT fk_assistencia_caso_pool_ambiente_id FOREIGN KEY (pool_ambiente_id) REFERENCES public.pool_ambientes(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: ciclo_etapas fk_ciclo_etapas_responsavel_terceiro_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas
    ADD CONSTRAINT fk_ciclo_etapas_responsavel_terceiro_id FOREIGN KEY (responsavel_terceiro_id) REFERENCES public.terceiros(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: ciclo_etapas fk_ciclo_etapas_transferencia_destino_funcionario_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas
    ADD CONSTRAINT fk_ciclo_etapas_transferencia_destino_funcionario_id FOREIGN KEY (transferencia_destino_funcionario_id) REFERENCES public.funcionarios(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: ciclo_etapas fk_ciclo_etapas_transferencia_destino_terceiro_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas
    ADD CONSTRAINT fk_ciclo_etapas_transferencia_destino_terceiro_id FOREIGN KEY (transferencia_destino_terceiro_id) REFERENCES public.terceiros(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: ciclo_etapas fk_ciclo_etapas_transferencia_solicitada_por_usuario_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ciclo_etapas
    ADD CONSTRAINT fk_ciclo_etapas_transferencia_solicitada_por_usuario_id FOREIGN KEY (transferencia_solicitada_por_usuario_id) REFERENCES public.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: conta fk_conta_centro_custo_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conta
    ADD CONSTRAINT fk_conta_centro_custo_id FOREIGN KEY (centro_custo_id) REFERENCES public.centro_custo(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: conversa_mensagens fk_conversa_mensagens_destinatario_usuario_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_mensagens
    ADD CONSTRAINT fk_conversa_mensagens_destinatario_usuario_id FOREIGN KEY (destinatario_usuario_id) REFERENCES public.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: conversa_mensagens fk_conversa_mensagens_transferido_para_funcionario_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_mensagens
    ADD CONSTRAINT fk_conversa_mensagens_transferido_para_funcionario_id FOREIGN KEY (transferido_para_funcionario_id) REFERENCES public.funcionarios(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: conversas fk_conversas_assunto_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversas
    ADD CONSTRAINT fk_conversas_assunto_id FOREIGN KEY (assunto_id) REFERENCES public.assuntos(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: conversas fk_conversas_concluido_por_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversas
    ADD CONSTRAINT fk_conversas_concluido_por_id FOREIGN KEY (concluido_por_id) REFERENCES public.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: conversas fk_conversas_criado_por_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversas
    ADD CONSTRAINT fk_conversas_criado_por_id FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: conversas fk_conversas_rede_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversas
    ADD CONSTRAINT fk_conversas_rede_id FOREIGN KEY (rede_id) REFERENCES public.redes(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: conversas fk_conversas_responsavel_usuario_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversas
    ADD CONSTRAINT fk_conversas_responsavel_usuario_id FOREIGN KEY (responsavel_usuario_id) REFERENCES public.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: conversa_mensagens fk_convmsg_documento_ref; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversa_mensagens
    ADD CONSTRAINT fk_convmsg_documento_ref FOREIGN KEY (documento_ref_id) REFERENCES public.ciclo_documentos(id);


--
-- Name: envios_externos fk_envios_externos_template_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.envios_externos
    ADD CONSTRAINT fk_envios_externos_template_id FOREIGN KEY (template_id) REFERENCES public.template_mensagem(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: envios_externos fk_envios_externos_triagem_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.envios_externos
    ADD CONSTRAINT fk_envios_externos_triagem_id FOREIGN KEY (triagem_id) REFERENCES public.triagem_entradas(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: lojas fk_lojas_loja_mae_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lojas
    ADD CONSTRAINT fk_lojas_loja_mae_id FOREIGN KEY (loja_mae_id) REFERENCES public.lojas(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: orcamentos fk_orcamentos_parcela_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orcamentos
    ADD CONSTRAINT fk_orcamentos_parcela_id FOREIGN KEY (parcela_id) REFERENCES public.parcela_projeto(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: segmento_config fk_segmento_config_responsavel_funcionario_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segmento_config
    ADD CONSTRAINT fk_segmento_config_responsavel_funcionario_id FOREIGN KEY (responsavel_funcionario_id) REFERENCES public.funcionarios(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: folha_pagamento folha_pagamento_funcionario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folha_pagamento
    ADD CONSTRAINT folha_pagamento_funcionario_id_fkey FOREIGN KEY (funcionario_id) REFERENCES public.funcionarios(id);


--
-- Name: folha_pagamento folha_pagamento_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folha_pagamento
    ADD CONSTRAINT folha_pagamento_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: fornecedores fornecedores_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fornecedores
    ADD CONSTRAINT fornecedores_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: funcionarios funcionarios_funcao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_funcao_id_fkey FOREIGN KEY (funcao_id) REFERENCES public.funcoes(id);


--
-- Name: funcionarios funcionarios_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: funcionarios funcionarios_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: funcoes funcoes_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcoes
    ADD CONSTRAINT funcoes_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: integracoes_clicksign integracoes_clicksign_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integracoes_clicksign
    ADD CONSTRAINT integracoes_clicksign_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: integracoes_clicksign integracoes_clicksign_rede_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integracoes_clicksign
    ADD CONSTRAINT integracoes_clicksign_rede_id_fkey FOREIGN KEY (rede_id) REFERENCES public.redes(id);


--
-- Name: integracoes_d4sign integracoes_d4sign_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integracoes_d4sign
    ADD CONSTRAINT integracoes_d4sign_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: integracoes_d4sign integracoes_d4sign_rede_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integracoes_d4sign
    ADD CONSTRAINT integracoes_d4sign_rede_id_fkey FOREIGN KEY (rede_id) REFERENCES public.redes(id);


--
-- Name: lancamento lancamento_conta_credito_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lancamento
    ADD CONSTRAINT lancamento_conta_credito_id_fkey FOREIGN KEY (conta_credito_id) REFERENCES public.conta(id);


--
-- Name: lancamento lancamento_conta_debito_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lancamento
    ADD CONSTRAINT lancamento_conta_debito_id_fkey FOREIGN KEY (conta_debito_id) REFERENCES public.conta(id);


--
-- Name: log_acesso_delegado log_acesso_delegado_autorizador_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acesso_delegado
    ADD CONSTRAINT log_acesso_delegado_autorizador_id_fkey FOREIGN KEY (autorizador_id) REFERENCES public.usuarios(id);


--
-- Name: log_acesso_delegado log_acesso_delegado_solicitante_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acesso_delegado
    ADD CONSTRAINT log_acesso_delegado_solicitante_id_fkey FOREIGN KEY (solicitante_id) REFERENCES public.usuarios(id);


--
-- Name: log_acoes_gerenciais log_acoes_gerenciais_autorizador_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acoes_gerenciais
    ADD CONSTRAINT log_acoes_gerenciais_autorizador_id_fkey FOREIGN KEY (autorizador_id) REFERENCES public.usuarios(id);


--
-- Name: log_acoes_gerenciais log_acoes_gerenciais_solicitante_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acoes_gerenciais
    ADD CONSTRAINT log_acoes_gerenciais_solicitante_id_fkey FOREIGN KEY (solicitante_id) REFERENCES public.usuarios(id);


--
-- Name: log_autorizacoes log_autorizacoes_autorizador_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_autorizacoes
    ADD CONSTRAINT log_autorizacoes_autorizador_id_fkey FOREIGN KEY (autorizador_id) REFERENCES public.usuarios(id);


--
-- Name: log_autorizacoes log_autorizacoes_solicitante_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_autorizacoes
    ADD CONSTRAINT log_autorizacoes_solicitante_id_fkey FOREIGN KEY (solicitante_id) REFERENCES public.usuarios(id);


--
-- Name: lojas lojas_emitente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lojas
    ADD CONSTRAINT lojas_emitente_id_fkey FOREIGN KEY (emitente_id) REFERENCES public.emitente(id);


--
-- Name: lojas lojas_rede_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lojas
    ADD CONSTRAINT lojas_rede_id_fkey FOREIGN KEY (rede_id) REFERENCES public.redes(id);


--
-- Name: medicoes medicoes_excecao_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicoes
    ADD CONSTRAINT medicoes_excecao_por_fkey FOREIGN KEY (excecao_por) REFERENCES public.usuarios(id);


--
-- Name: medicoes medicoes_medidor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicoes
    ADD CONSTRAINT medicoes_medidor_id_fkey FOREIGN KEY (medidor_id) REFERENCES public.usuarios(id);


--
-- Name: medicoes medicoes_solicitacao_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicoes
    ADD CONSTRAINT medicoes_solicitacao_por_fkey FOREIGN KEY (solicitacao_por) REFERENCES public.usuarios(id);


--
-- Name: mensagem_anexos mensagem_anexos_mensagem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensagem_anexos
    ADD CONSTRAINT mensagem_anexos_mensagem_id_fkey FOREIGN KEY (mensagem_id) REFERENCES public.conversa_mensagens(id);


--
-- Name: numero_conectado numero_conectado_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.numero_conectado
    ADD CONSTRAINT numero_conectado_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: orcamento_ambientes orcamento_ambientes_orcamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orcamento_ambientes
    ADD CONSTRAINT orcamento_ambientes_orcamento_id_fkey FOREIGN KEY (orcamento_id) REFERENCES public.orcamentos(id);


--
-- Name: orcamento_ambientes orcamento_ambientes_pool_ambiente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orcamento_ambientes
    ADD CONSTRAINT orcamento_ambientes_pool_ambiente_id_fkey FOREIGN KEY (pool_ambiente_id) REFERENCES public.pool_ambientes(id);


--
-- Name: orcamentos orcamentos_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orcamentos
    ADD CONSTRAINT orcamentos_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: orcamentos orcamentos_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orcamentos
    ADD CONSTRAINT orcamentos_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: parceiro_lojas parceiro_lojas_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parceiro_lojas
    ADD CONSTRAINT parceiro_lojas_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: parceiro_lojas parceiro_lojas_parceiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parceiro_lojas
    ADD CONSTRAINT parceiro_lojas_parceiro_id_fkey FOREIGN KEY (parceiro_id) REFERENCES public.parceiros(id);


--
-- Name: parceiros parceiros_rede_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parceiros
    ADD CONSTRAINT parceiros_rede_id_fkey FOREIGN KEY (rede_id) REFERENCES public.redes(id);


--
-- Name: parcela_ambiente parcela_ambiente_parcela_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parcela_ambiente
    ADD CONSTRAINT parcela_ambiente_parcela_id_fkey FOREIGN KEY (parcela_id) REFERENCES public.parcela_projeto(id);


--
-- Name: parcela_ambiente parcela_ambiente_pool_ambiente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parcela_ambiente
    ADD CONSTRAINT parcela_ambiente_pool_ambiente_id_fkey FOREIGN KEY (pool_ambiente_id) REFERENCES public.pool_ambientes(id);


--
-- Name: parcela_projeto parcela_projeto_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parcela_projeto
    ADD CONSTRAINT parcela_projeto_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: parcela_projeto parcela_projeto_orcamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parcela_projeto
    ADD CONSTRAINT parcela_projeto_orcamento_id_fkey FOREIGN KEY (orcamento_id) REFERENCES public.orcamentos(id);


--
-- Name: perfil_acesso perfil_acesso_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_acesso
    ADD CONSTRAINT perfil_acesso_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: perfil_emissao perfil_emissao_emitente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_emissao
    ADD CONSTRAINT perfil_emissao_emitente_id_fkey FOREIGN KEY (emitente_id) REFERENCES public.emitente(id);


--
-- Name: pool_ambientes pool_ambientes_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pool_ambientes
    ADD CONSTRAINT pool_ambientes_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: pool_ambientes pool_ambientes_qa_override_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pool_ambientes
    ADD CONSTRAINT pool_ambientes_qa_override_por_id_fkey FOREIGN KEY (qa_override_por_id) REFERENCES public.usuarios(id);


--
-- Name: projetos_meta projetos_meta_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projetos_meta
    ADD CONSTRAINT projetos_meta_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: projetos_meta projetos_meta_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projetos_meta
    ADD CONSTRAINT projetos_meta_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: projetos_meta projetos_meta_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projetos_meta
    ADD CONSTRAINT projetos_meta_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: provisao_data_prevista provisao_data_prevista_atualizado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_data_prevista
    ADD CONSTRAINT provisao_data_prevista_atualizado_por_id_fkey FOREIGN KEY (atualizado_por_id) REFERENCES public.usuarios(id);


--
-- Name: provisao_data_prevista provisao_data_prevista_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_data_prevista
    ADD CONSTRAINT provisao_data_prevista_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: provisao_registro provisao_registro_orcamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_registro
    ADD CONSTRAINT provisao_registro_orcamento_id_fkey FOREIGN KEY (orcamento_id) REFERENCES public.orcamentos(id);


--
-- Name: provisao_registro provisao_registro_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provisao_registro
    ADD CONSTRAINT provisao_registro_por_id_fkey FOREIGN KEY (por_id) REFERENCES public.usuarios(id);


--
-- Name: recebivel recebivel_confirmado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebivel
    ADD CONSTRAINT recebivel_confirmado_por_id_fkey FOREIGN KEY (confirmado_por_id) REFERENCES public.usuarios(id);


--
-- Name: recebivel recebivel_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebivel
    ADD CONSTRAINT recebivel_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: recebivel recebivel_orcamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebivel
    ADD CONSTRAINT recebivel_orcamento_id_fkey FOREIGN KEY (orcamento_id) REFERENCES public.orcamentos(id);


--
-- Name: redes redes_emitente_central_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.redes
    ADD CONSTRAINT redes_emitente_central_id_fkey FOREIGN KEY (emitente_central_id) REFERENCES public.emitente(id);


--
-- Name: retencao_obra retencao_obra_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retencao_obra
    ADD CONSTRAINT retencao_obra_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: retencao_obra retencao_obra_liberado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retencao_obra
    ADD CONSTRAINT retencao_obra_liberado_por_id_fkey FOREIGN KEY (liberado_por_id) REFERENCES public.usuarios(id);


--
-- Name: segmento_config segmento_config_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segmento_config
    ADD CONSTRAINT segmento_config_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: segmento_config segmento_config_template_padrao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segmento_config
    ADD CONSTRAINT segmento_config_template_padrao_id_fkey FOREIGN KEY (template_padrao_id) REFERENCES public.template_mensagem(id);


--
-- Name: sessoes sessoes_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes
    ADD CONSTRAINT sessoes_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: simulador_autorizacoes simulador_autorizacoes_concedido_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulador_autorizacoes
    ADD CONSTRAINT simulador_autorizacoes_concedido_por_usuario_id_fkey FOREIGN KEY (concedido_por_usuario_id) REFERENCES public.usuarios(id);


--
-- Name: simulador_autorizacoes simulador_autorizacoes_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulador_autorizacoes
    ADD CONSTRAINT simulador_autorizacoes_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: simulador_autorizacoes simulador_autorizacoes_solicitado_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulador_autorizacoes
    ADD CONSTRAINT simulador_autorizacoes_solicitado_por_usuario_id_fkey FOREIGN KEY (solicitado_por_usuario_id) REFERENCES public.usuarios(id);


--
-- Name: simulador_log_acessos simulador_log_acessos_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulador_log_acessos
    ADD CONSTRAINT simulador_log_acessos_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: simulador_log_acessos simulador_log_acessos_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulador_log_acessos
    ADD CONSTRAINT simulador_log_acessos_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: sinal_retido sinal_retido_pool_ambiente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sinal_retido
    ADD CONSTRAINT sinal_retido_pool_ambiente_id_fkey FOREIGN KEY (pool_ambiente_id) REFERENCES public.pool_ambientes(id);


--
-- Name: sinal_retido sinal_retido_sinalizado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sinal_retido
    ADD CONSTRAINT sinal_retido_sinalizado_por_id_fkey FOREIGN KEY (sinalizado_por_id) REFERENCES public.usuarios(id);


--
-- Name: solicitacoes_medicao_assinaturas solicitacoes_medicao_assinaturas_solicitacao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes_medicao_assinaturas
    ADD CONSTRAINT solicitacoes_medicao_assinaturas_solicitacao_id_fkey FOREIGN KEY (solicitacao_id) REFERENCES public.solicitacoes_medicao(id);


--
-- Name: solicitacoes_medicao solicitacoes_medicao_gerado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes_medicao
    ADD CONSTRAINT solicitacoes_medicao_gerado_por_id_fkey FOREIGN KEY (gerado_por_id) REFERENCES public.usuarios(id);


--
-- Name: solicitacoes_medicao solicitacoes_medicao_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes_medicao
    ADD CONSTRAINT solicitacoes_medicao_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: solicitacoes_medicao solicitacoes_medicao_modelo_versao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes_medicao
    ADD CONSTRAINT solicitacoes_medicao_modelo_versao_id_fkey FOREIGN KEY (modelo_versao_id) REFERENCES public.documento_modelos(id);


--
-- Name: template_mensagem template_mensagem_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.template_mensagem
    ADD CONSTRAINT template_mensagem_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public.usuarios(id);


--
-- Name: template_mensagem template_mensagem_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.template_mensagem
    ADD CONSTRAINT template_mensagem_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: terceiros terceiros_funcao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.terceiros
    ADD CONSTRAINT terceiros_funcao_id_fkey FOREIGN KEY (funcao_id) REFERENCES public.funcoes(id);


--
-- Name: terceiros terceiros_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.terceiros
    ADD CONSTRAINT terceiros_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: terceiros terceiros_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.terceiros
    ADD CONSTRAINT terceiros_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: triagem_config triagem_config_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triagem_config
    ADD CONSTRAINT triagem_config_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: triagem_entradas triagem_entradas_conversa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triagem_entradas
    ADD CONSTRAINT triagem_entradas_conversa_id_fkey FOREIGN KEY (conversa_id) REFERENCES public.conversas(id);


--
-- Name: triagem_entradas triagem_entradas_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triagem_entradas
    ADD CONSTRAINT triagem_entradas_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: triagem_entradas triagem_entradas_resolvido_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triagem_entradas
    ADD CONSTRAINT triagem_entradas_resolvido_por_id_fkey FOREIGN KEY (resolvido_por_id) REFERENCES public.usuarios(id);


--
-- Name: usuario_lojas usuario_lojas_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_lojas
    ADD CONSTRAINT usuario_lojas_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: usuario_lojas usuario_lojas_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_lojas
    ADD CONSTRAINT usuario_lojas_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: usuario_presenca usuario_presenca_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_presenca
    ADD CONSTRAINT usuario_presenca_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: usuarios usuarios_funcao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_funcao_id_fkey FOREIGN KEY (funcao_id) REFERENCES public.funcoes(id);


--
-- Name: usuarios usuarios_funcionario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_funcionario_id_fkey FOREIGN KEY (funcionario_id) REFERENCES public.funcionarios(id);


--
-- Name: usuarios usuarios_loja_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES public.lojas(id);


--
-- Name: usuarios usuarios_rede_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_rede_id_fkey FOREIGN KEY (rede_id) REFERENCES public.redes(id);


--
-- PostgreSQL database dump complete
--

\unrestrict SUG595tYhf5PKMiU1gE3e7k3GwTdjZzPVx1n9djW8FAwVVIUOHebThFzbcrDDOE

