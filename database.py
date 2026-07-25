"""
database.py — Conexão SQLAlchemy + modelos de dados
Orizon Manager | Dalmóbile
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship, validates
from datetime import datetime
import hashlib
import os
from auth import perfis

def _hash_senha(senha: str) -> str:
    """SHA-256 hex de uma senha. Fonte única de hashing (Usuario + bootstrap/seed)."""
    return hashlib.sha256(senha.encode()).hexdigest()


# ── Conexão ──────────────────────────────────────────────────────────────────
# Postgres OBRIGATÓRIO (faxina 2026-07-23 — SQLite removido por inteiro; antes disso o runtime
# já o recusava desde a S85). DATABASE_URL ex.: postgresql+psycopg2://orizon:<senha>@localhost/orizon
# Sem DATABASE_URL o engine aponta para um placeholder que NUNCA conecta — main() explica e sai;
# a suíte de testes rebinda ENGINE/Session no conftest (banco dedicado orizon_test).
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = os.environ.get("DATABASE_URL")
_URL_PLACEHOLDER = "postgresql+psycopg2://nao_configurado@localhost:1/nao_configurado"
# pool_pre_ping (2026-07-25): o Postgres pode reciclar conexões ociosas (reinício por
# unattended-upgrades, timeout de rede) — sem o ping, o app usa a conexão MORTA do pool e
# a primeira requisição de cada conexão explode ("SSL connection has been closed
# unexpectedly"; foi o login da equipe falhando na instância A). pre_ping testa e refaz.
# pool_recycle recicla proativamente conexões com mais de 30min (higiene do mesmo risco).
ENGINE       = create_engine(DATABASE_URL or _URL_PLACEHOLDER, echo=False,
                             pool_pre_ping=True, pool_recycle=1800)
Session      = sessionmaker(bind=ENGINE)

# ── Base ─────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass

# ── Modelos ──────────────────────────────────────────────────────────────────
class Usuario(Base):
    __tablename__ = "usuarios"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    nome          = Column(String(120), nullable=False)
    login         = Column(String(60),  nullable=False, unique=True)
    senha_hash    = Column(String(64),  nullable=False)
    nivel         = Column(String(20),  nullable=False)   # diretor | gerente | consultor
    telefone      = Column(String(20),  nullable=True)
    email         = Column(String(120), nullable=True)
    cpf           = Column(String(20),  nullable=True)
    whatsapp      = Column(String(20),  nullable=True)
    ativo         = Column(Integer,     default=1)
    senha_provisoria = Column(Integer,  default=0)   # 1 = precisa trocar a senha no 1º login
    funcionario_id = Column(Integer,    ForeignKey("funcionarios.id"), nullable=True)  # RH (Cadastro) que esta conta representa
    # Função (cargo) da CONTA quando não há Funcionário vinculado (Perfil-4 rev2 §2): a coluna Função
    # de Usuários da Loja usa Funcionario.funcao_id se houver vínculo, senão este funcao_id.
    funcao_id     = Column(Integer,     ForeignKey("funcoes.id"), nullable=True)
    tema          = Column(String(10),  default="escuro")   # 'claro' | 'escuro'
    criado_em     = Column(DateTime,    default=datetime.utcnow)
    loja_id       = Column(Integer,     ForeignKey("lojas.id"), nullable=True)  # usuário de loja
    rede_id       = Column(Integer,     ForeignKey("redes.id"), nullable=True)  # admin de rede (loja_id NULL)

    sessoes       = relationship("Sessao",          back_populates="usuario", cascade="all, delete-orphan")
    autorizacoes  = relationship("LogAutorizacao",  back_populates="autorizador", foreign_keys="LogAutorizacao.autorizador_id")

    def set_senha(self, senha: str):
        self.senha_hash = _hash_senha(senha)

    def check_senha(self, senha: str) -> bool:
        return self.senha_hash == _hash_senha(senha)

    @property
    def limite_desconto(self) -> float:
        return perfis.desconto_max(self.nivel)

    @property
    def pode_ver_parametros(self) -> bool:
        return perfis.pode(self.nivel, "ver_parametros")


class Sessao(Base):
    __tablename__ = "sessoes"

    id          = Column(Integer,  primary_key=True, autoincrement=True)
    token       = Column(String(64), nullable=False, unique=True)
    usuario_id  = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    criada_em   = Column(DateTime, default=datetime.utcnow)
    expira_em   = Column(DateTime, nullable=False)
    ativa       = Column(Integer,  default=1)

    usuario     = relationship("Usuario", back_populates="sessoes")


class LogAutorizacao(Base):
    __tablename__ = "log_autorizacoes"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    solicitante_id   = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    autorizador_id   = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    desconto_solicit = Column(Float,    nullable=False)
    desconto_limite  = Column(Float,    nullable=False)
    autorizado       = Column(Integer,  default=0)   # 0=negado/cancelado 1=autorizado
    contexto         = Column(Text,     nullable=True)  # JSON com detalhes da negociação
    criado_em        = Column(DateTime, default=datetime.utcnow)

    solicitante  = relationship("Usuario", foreign_keys=[solicitante_id])
    autorizador  = relationship("Usuario", back_populates="autorizacoes", foreign_keys=[autorizador_id])


class LogAcaoGerencial(Base):
    """Auditoria de ações destrutivas autorizadas por gerente (ex.: reabrir cascata)."""
    __tablename__ = "log_acoes_gerenciais"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    solicitante_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    autorizador_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    acao           = Column(Text,     nullable=False)   # ex.: "reabrir_cascata"
    projeto_nome   = Column(Text,     nullable=True)
    etapa_alvo     = Column(Text,     nullable=True)
    contexto       = Column(Text,     nullable=True)    # JSON
    criado_em      = Column(DateTime, default=datetime.utcnow)

    solicitante = relationship("Usuario", foreign_keys=[solicitante_id])
    autorizador = relationship("Usuario", foreign_keys=[autorizador_id])


class LogAcessoDelegado(Base):
    """Auditoria do step-up por senha: fulano acessou um módulo/painel fora do perfil com a
    autorização (senha) de alguém que tinha o perfil. Molde do LogAcaoGerencial."""
    __tablename__ = "log_acesso_delegado"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    solicitante_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    autorizador_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    recurso        = Column(String(40), nullable=False)   # id do módulo ou 'admin'/'config'
    contexto       = Column(Text,     nullable=True)      # JSON opcional
    criado_em      = Column(DateTime, default=datetime.utcnow)


class Medicao(Base):
    """Dados de medição por projeto (etapas 9 e 10 do ciclo)."""
    __tablename__ = "medicoes"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    projeto_nome        = Column(String(200), nullable=False, unique=True)
    # Etapa 9 — solicitação
    solicitacao_arquivo = Column(String(255), nullable=True)
    solicitacao_por     = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    solicitacao_em      = Column(DateTime, nullable=True)
    # Etapa 10 — parecer + planta
    parecer             = Column(String(20), nullable=True)   # aprovado|reprovado|parcial
    ambientes_aprovados = Column(Text, nullable=True)
    planta_arquivo      = Column(String(255), nullable=True)
    medidor_id          = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    medicao_em          = Column(DateTime, nullable=True)
    # Reprovado — decisão comercial
    doc_cliente_arquivo = Column(String(255), nullable=True)
    excecao_por         = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    excecao_em          = Column(DateTime, nullable=True)


class Cliente(Base):
    __tablename__ = "clientes"

    id            = Column(Integer,     primary_key=True, autoincrement=True)
    nome          = Column(String(150), nullable=False)
    cpf           = Column(String(14),  nullable=True, unique=True)
    tipo_dest          = Column(Text, default="nao_contribuinte")  # contribuinte|isento|nao_contribuinte
    cnpj               = Column(String(18), nullable=True)
    inscricao_estadual = Column(Text, nullable=True)
    email         = Column(String(120), nullable=True)
    telefone      = Column(String(20),  nullable=True)
    whatsapp      = Column(String(20),  nullable=True)
    cep           = Column(String(9),   nullable=True)
    logradouro    = Column(String(200), nullable=True)
    numero        = Column(String(20),  nullable=True)
    complemento   = Column(String(100), nullable=True)
    bairro        = Column(String(100), nullable=True)
    cidade        = Column(String(80),  nullable=True)
    estado        = Column(String(2),   nullable=True)
    municipio_ibge = Column(String(7),  nullable=True)   # código IBGE do município (tomador NFS-e; via ViaCEP)
    observacoes   = Column(Text,        nullable=True)
    inst_mesmo_residencial = Column(Integer,     default=1)   # 1=True, 0=False
    inst_logradouro        = Column(String(200), nullable=True)
    inst_numero            = Column(String(20),  nullable=True)
    inst_complemento       = Column(String(100), nullable=True)
    inst_bairro            = Column(String(100), nullable=True)
    inst_cidade            = Column(String(80),  nullable=True)
    inst_cep               = Column(String(9),   nullable=True)
    inst_uf                = Column(String(2),   nullable=True)
    criado_em     = Column(DateTime,    default=datetime.utcnow)
    atualizado_em = Column(DateTime,    onupdate=datetime.utcnow)
    loja_id       = Column(Integer,     ForeignKey("lojas.id"), nullable=True)


class Parceiro(Base):
    __tablename__ = "parceiros"

    id                  = Column(Integer,     primary_key=True, autoincrement=True)
    nome                = Column(String(150), nullable=False)
    cpf_cnpj            = Column(String(18),  nullable=True)
    tipo                = Column(String(30),   nullable=True)   # arquiteto/designer/decorador/corretor/engenheiro/indicador
    email               = Column(String(120),  nullable=True)
    telefone            = Column(String(20),   nullable=True)
    whatsapp            = Column(String(20),   nullable=True)
    comissao_padrao_pct = Column(Float,        default=0.0)
    observacoes         = Column(Text,         nullable=True)
    criado_em           = Column(DateTime,     default=datetime.utcnow)
    rede_id             = Column(Integer,      ForeignKey("redes.id"), nullable=True)
    abrangencia         = Column(String(10),   default="loja")   # loja | rede
    pix                 = Column(String(140),  nullable=True)    # chave PIX p/ pagamento de comissão (v10)


class Funcao(Base):
    """Tabela de Funções (Modulos_Orizon_v10, Config): catálogo único de funções/cargos referenciado
    por Funcionário.funcao_id e Terceiro.funcao_id — substitui texto livre / listas separadas."""
    __tablename__ = "funcoes"

    id        = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id   = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    nome      = Column(String(80),  nullable=False)
    status    = Column(String(10),  nullable=False, default="ativo")   # ativo | inativo
    perfil_padrao = Column(String(40), nullable=True)   # slug do perfil_acesso default da função
    atribuicoes_json   = Column(Text,        nullable=True)   # JSON: papéis (mod_escopo.PAPEIS)
    remuneracao_padrao = Column(String(20),  nullable=True)   # fixa | variavel | fixa_variavel
    regime_trabalho    = Column(String(20),  nullable=True)   # presencial | remoto | misto
    regime_contratacao = Column(String(20),  nullable=True)   # registrado | terceirizacao
    descricao          = Column(Text,        nullable=True)   # descrição livre do que a função faz
    salario_fixo        = Column(Float,   nullable=True)   # parte fixa mensal da função
    beneficios_json     = Column(Text,    nullable=True)   # {"at":{"on","valor"},"va":..,"ps":..}
    comissao_json       = Column(Text,    nullable=True)   # {"por_meta","base","pct"|"faixas"} (não-consultor)
    usa_comissao_vendas = Column(Integer, default=0)       # 1 = comissão vem do comissao_vendas da loja (Consultor)
    comissao_fixa       = Column(Float,   nullable=True)   # comissão FIXA mensal isenta de encargos (férias/13º/INSS) — planejamento
    criado_em = Column(DateTime,    default=datetime.utcnow)


class PerfilAcesso(Base):
    """Perfil de acesso configurável POR LOJA (Regras_Funcoes_Perfis_Atribuicoes rev3 §2).
    Acesso a módulo/painel vem de `modulos_json`; capacidades finas = base perfis.PERFIS[`base`]
    com overrides opcionais em `capacidades_json`."""
    __tablename__ = "perfil_acesso"

    id           = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id      = Column(Integer,     ForeignKey("lojas.id"), nullable=False)  # perfis são por loja
    slug         = Column(String(40),  nullable=False)   # único globalmente (system: master/gerencial/operador)
    nome         = Column(String(80),  nullable=False)
    base         = Column(String(20),  nullable=False)   # master | gerencial | operador (preset das caps finas)
    modulos_json = Column(Text,        nullable=False, default="[]")  # JSON: ids de módulo/painel acessíveis
    capacidades_json = Column(Text,    nullable=False, default="{}")  # JSON {cap: bool} — overrides sobre a base
    sistema      = Column(Integer,     nullable=False, default=0)     # 1 = padrão, não apagável
    criado_em    = Column(DateTime,    default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("loja_id", "slug", name="uq_perfil_loja_slug"),)


class FolhaPagamento(Base):
    """Folha de Pagamento (Modulos_Orizon_v10, §2.1): um registro por Funcionário/competência.
    Parte fixa vem do cadastro; parte variável = vendas do período × % da faixa de meta (auto-cálculo).
    Despesa lançada nas contas existentes do Plano de Contas (5.3) — motor, não digitação."""
    __tablename__ = "folha_pagamento"

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    funcionario_id = Column(Integer,     ForeignKey("funcionarios.id"), nullable=False)
    competencia    = Column(String(7),   nullable=False)          # 'AAAA-MM'
    parte_fixa     = Column(Float,       nullable=True, default=0.0)
    vendas_liq     = Column(Float,       nullable=True, default=0.0)   # base da variável (valor líquido do período)
    faixa_pct      = Column(Float,       nullable=True, default=0.0)   # % da faixa de meta atingida
    parte_variavel = Column(Float,       nullable=True, default=0.0)
    base_comissao  = Column(Float,       nullable=True, default=0.0)   # base editável da comissão (recalcula variável)
    beneficios     = Column(Float,       nullable=True, default=0.0)   # Σ AT/VA/PS ativos da Função
    comissao_fixa  = Column(Float,       nullable=True, default=0.0)   # comissão fixa da Função (isenta de encargos)
    total          = Column(Float,       nullable=True, default=0.0)
    status         = Column(String(10),  nullable=False, default="aberta")   # aberta | paga
    ref_lancamento = Column(String(60),  nullable=True)           # ref idempotente do lançamento contábil
    gerado_em      = Column(DateTime,    default=datetime.utcnow)
    pago_em        = Column(DateTime,    nullable=True)


class ComissaoFolha(Base):
    """Item de comissão de um funcionário numa competência (Fase 4). Um funcionário pode ter vários
    (por etapa/projeto). origem='papel' vem da conclusão de etapa (Mapa); origem='venda' é a comissão
    do Consultor. A parte variável da Folha = Σ valor dos itens (status != 'cancelado')."""
    __tablename__ = "comissao_folha"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    funcionario_id = Column(Integer,  ForeignKey("funcionarios.id"), nullable=False)
    competencia    = Column(String(7), nullable=False)          # 'AAAA-MM' = mês de concluido_em
    origem         = Column(String(10), nullable=False, default="papel")  # papel | venda
    papel          = Column(String(30), nullable=True)          # projeto_executivo|medicao|montagem|assistencia|venda
    projeto_nome   = Column(Text,     nullable=True)            # nome_safe (rastreabilidade)
    etapa_codigo   = Column(String(8), nullable=True)           # etapa que disparou (papel); NULL p/ venda
    base           = Column(Float,    nullable=True, default=0.0)   # Σ order_total dos ambientes (ou vendas líq.)
    base_ajustada  = Column(Float,    nullable=True)            # override manual da base
    pct            = Column(Float,    nullable=True, default=0.0)
    valor          = Column(Float,    nullable=True, default=0.0)   # base_efetiva × pct/100
    status         = Column(String(12), nullable=False, default="previsto")  # previsto|confirmado|cancelado
    ref_etapa      = Column(String(120), nullable=True)        # idempotência: '<projeto>:<etapa>:<func>' ou 'venda:<func>:<comp>'
    criado_em      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("ref_etapa", name="uq_comissao_ref_etapa"),)


class AdiantamentoFuncionario(Base):
    """Adiantamento/empréstimo a funcionário (Fase 5). 'oficial' = 40% do salário fixo (auto, carteira);
    'adiantamento' = adiantamento avulso; 'emprestimo' = empréstimo (pode atravessar meses). abater/
    competencia_abate controlam a dedução do líquido; quitado marca a baixa quando a folha é paga."""
    __tablename__ = "adiantamento_funcionario"
    id                = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id           = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    funcionario_id    = Column(Integer,  ForeignKey("funcionarios.id"), nullable=False)
    tipo              = Column(String(14), nullable=False, default="adiantamento")  # oficial|adiantamento|emprestimo
    competencia       = Column(String(7), nullable=False)          # 'AAAA-MM' concedido
    valor             = Column(Float,    nullable=True, default=0.0)
    abater            = Column(Integer,  nullable=False, default=1)  # 1 = deduz do líquido (editável)
    competencia_abate = Column(String(7), nullable=True)           # folha que deduz
    quitado           = Column(Integer,  nullable=False, default=0)  # 1 = baixado (folha paga)
    observacao        = Column(Text,     nullable=True)
    ref               = Column(String(120), nullable=True)         # idempotência do oficial: 'oficial:<func>:<comp>'
    criado_em         = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("ref", name="uq_adiantamento_ref"),)


class Funcionario(Base):
    """Cadastro de RH (Modulos_Orizon_v9, módulo 2). NÃO é conta de login — o Usuário (Admin/Núcleo)
    referencia o Funcionário via usuario_id/funcionario_id, sem duplicar dado pessoal."""
    __tablename__ = "funcionarios"

    id                 = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id            = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    nome               = Column(String(150), nullable=False)
    cpf                = Column(String(20),  nullable=True)
    telefone           = Column(String(20),  nullable=True)
    email              = Column(String(120), nullable=True)
    cargo              = Column(String(80),  nullable=True)   # legado (texto) — ver funcao_id
    funcao_id          = Column(Integer,     ForeignKey("funcoes.id"), nullable=True)  # → Tabela de Funções (v10)
    remuneracao_tipo   = Column(String(20),  nullable=True)   # fixa | fixa_variavel
    remuneracao_fixa   = Column(Float,       nullable=True)
    remuneracao_var    = Column(Float,       nullable=True)   # parte variável (se fixa_variavel)
    # Endereço (mesmo bloco de Clientes) + Dados Bancários completos (v10)
    cep          = Column(String(9),   nullable=True)
    logradouro   = Column(String(200), nullable=True)
    numero       = Column(String(20),  nullable=True)
    complemento  = Column(String(100), nullable=True)
    bairro       = Column(String(100), nullable=True)
    cidade       = Column(String(80),  nullable=True)
    uf           = Column(String(2),   nullable=True)
    banco_nome   = Column(String(80),  nullable=True)
    banco_codigo = Column(String(6),   nullable=True)
    agencia      = Column(String(12),  nullable=True)
    conta        = Column(String(20),  nullable=True)
    pix          = Column(String(140), nullable=True)
    status             = Column(String(10),  nullable=False, default="ativo")   # ativo | inativo
    usuario_id         = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)  # conta de login (se houver)
    criado_em          = Column(DateTime,    default=datetime.utcnow)


class Fornecedor(Base):
    """Fornecedor PJ/PF (Modulos_Orizon_v9). Referenciado por 'Fornecedores a Pagar' (Financeiro 2.1)."""
    __tablename__ = "fornecedores"

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id         = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    tipo_pessoa     = Column(String(2),   nullable=False, default="pj")   # pj | pf
    nome            = Column(String(180), nullable=False)                 # razão social / nome
    cnpj_cpf        = Column(String(18),  nullable=True)
    telefone        = Column(String(20),  nullable=True)
    email           = Column(String(120), nullable=True)
    categoria       = Column(String(20),  nullable=True)   # materia_prima | transportadora | servicos | outro
    prazo_pagamento = Column(Integer,     nullable=True)   # dias
    dados_bancarios = Column(Text,        nullable=True)   # legado (texto livre)
    # Endereço + Dados Bancários estruturados (v10)
    cep          = Column(String(9),   nullable=True)
    logradouro   = Column(String(200), nullable=True)
    numero       = Column(String(20),  nullable=True)
    complemento  = Column(String(100), nullable=True)
    bairro       = Column(String(100), nullable=True)
    cidade       = Column(String(80),  nullable=True)
    uf           = Column(String(2),   nullable=True)
    banco_nome   = Column(String(80),  nullable=True)
    banco_codigo = Column(String(6),   nullable=True)
    agencia      = Column(String(12),  nullable=True)
    conta        = Column(String(20),  nullable=True)
    pix          = Column(String(140), nullable=True)
    status          = Column(String(10),  nullable=False, default="ativo")
    criado_em       = Column(DateTime,    default=datetime.utcnow)


class Terceiro(Base):
    """Prestador Pessoa Física (Modulos_Orizon_v9): sempre PF (PJ vira Fornecedor). O Montador é a mesma
    pessoa da 'Execução da Montagem' (Financeiro) — referência, nunca cadastro duplicado."""
    __tablename__ = "terceiros"

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id         = Column(Integer,     ForeignKey("lojas.id"), nullable=True)
    nome            = Column(String(150), nullable=False)
    cpf             = Column(String(20),  nullable=True)
    telefone        = Column(String(20),  nullable=True)
    tipo_servico    = Column(String(20),  nullable=True)   # legado — ver funcao_id
    funcao_id       = Column(Integer,     ForeignKey("funcoes.id"), nullable=True)  # → Tabela de Funções (v10)
    pix             = Column(String(140), nullable=True)
    dados_bancarios = Column(Text,        nullable=True)   # legado (texto livre)
    condicao        = Column(String(12),  nullable=True)   # mei | autonomo
    # Endereço + Dados Bancários completos (v10)
    cep          = Column(String(9),   nullable=True)
    logradouro   = Column(String(200), nullable=True)
    numero       = Column(String(20),  nullable=True)
    complemento  = Column(String(100), nullable=True)
    bairro       = Column(String(100), nullable=True)
    cidade       = Column(String(80),  nullable=True)
    uf           = Column(String(2),   nullable=True)
    banco_nome   = Column(String(80),  nullable=True)
    banco_codigo = Column(String(6),   nullable=True)
    agencia      = Column(String(12),  nullable=True)
    conta        = Column(String(20),  nullable=True)
    # Conta de login OPCIONAL restrita (Regras_Funcoes_Perfis_Atribuicoes §10): com conta, o Terceiro
    # ganha visão de Montagem/Assistência dos ambientes atribuídos. Coluna só; fluxo em passe seguinte.
    usuario_id      = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    status          = Column(String(10),  nullable=False, default="ativo")
    criado_em       = Column(DateTime,    default=datetime.utcnow)


class Rede(Base):
    """Rede (franquia) que agrupa lojas. Loja avulsa tem rede_id NULL."""
    __tablename__ = "redes"

    id        = Column(Integer,     primary_key=True, autoincrement=True)
    nome      = Column(String(150), nullable=False)
    cnpj      = Column(String(18),  nullable=True)
    emitente_central_id = Column(Integer, ForeignKey("emitente.id"), nullable=True)
    ativo     = Column(Integer,     default=1)
    criado_em = Column(DateTime,    default=datetime.utcnow)


class Loja(Base):
    """Loja (tenant). Pertence a uma rede ou é avulsa (rede_id NULL)."""
    __tablename__ = "lojas"

    id          = Column(Integer,     primary_key=True, autoincrement=True)
    rede_id     = Column(Integer,     ForeignKey("redes.id"), nullable=True)  # NULL = avulsa
    nome        = Column(String(150), nullable=False)
    cnpj        = Column(String(18),  nullable=True)
    codigo      = Column(String(8),   nullable=True, unique=True)   # 3 letras p/ num contrato
    telefone    = Column(String(20),  nullable=True)
    email       = Column(String(120), nullable=True)
    responsavel = Column(String(120), nullable=True)
    cep         = Column(String(9),   nullable=True)
    logradouro  = Column(String(200), nullable=True)
    numero      = Column(String(20),  nullable=True)
    complemento = Column(String(100), nullable=True)
    bairro      = Column(String(100), nullable=True)
    cidade      = Column(String(80),  nullable=True)
    estado      = Column(String(2),   nullable=True)
    testemunha1_nome = Column(String(120), nullable=True)
    testemunha1_cpf  = Column(String(14),  nullable=True)
    testemunha2_nome = Column(String(120), nullable=True)
    testemunha2_cpf  = Column(String(14),  nullable=True)
    emitente_id = Column(Integer, ForeignKey("emitente.id"), nullable=True)
    ativo       = Column(Integer,  default=1)
    criado_em   = Column(DateTime, default=datetime.utcnow)
    config_financeira_json = Column(Text, nullable=True)   # config financeira da loja (JSON)
    modulos_ativos = Column(Text, nullable=True)   # JSON: domínios ativos; NULL/"" = todos ligados (topologia)
    # Segmentação de receita Mercadoria × Serviço (default da loja; seed 65/35). Val_Cont divide-se
    # em Mercadoria (NF-e produto) + Serviço (NFS-e); override por projeto vive em parametros_json.
    pct_mercadoria = Column(Float, nullable=True, default=65.0)
    pct_servico    = Column(Float, nullable=True, default=35.0)
    # PDV (Ponto de Venda avançado — spec _geral/2026-07-22-ponto-de-venda-design.md): PDV é uma
    # Loja com mãe. loja_mae_id NULL = loja plena (comportamento idêntico ao anterior). O PDV
    # herda da mãe: rede_id (não editável), emissão fiscal (fallback do emitente) e modelos de
    # documento; razão contábil e tenancy são PRÓPRIOS (owner_id = pdv.id).
    loja_mae_id = Column(Integer, ForeignKey("lojas.id"), nullable=True)
    tipo        = Column(String(12), nullable=False, default="loja")   # loja | ponto_venda


class ParceiroLoja(Base):
    """Vínculo M:N parceiro × loja, com comissão própria por loja."""
    __tablename__ = "parceiro_lojas"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    parceiro_id         = Column(Integer, ForeignKey("parceiros.id"), nullable=False)
    loja_id             = Column(Integer, ForeignKey("lojas.id"),     nullable=False)
    comissao_padrao_pct = Column(Float,   default=0.0)
    ativo               = Column(Integer, default=1)


class UsuarioLoja(Base):
    """Vínculo M:N usuário × loja (lojas acessíveis). loja_id em usuarios = loja primária/default."""
    __tablename__ = "usuario_lojas"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    loja_id    = Column(Integer, ForeignKey("lojas.id"),    nullable=False)

    __table_args__ = (UniqueConstraint("usuario_id", "loja_id", name="uq_usuario_loja"),)


class Projeto(Base):
    """Metadados de pipeline por projeto. nome_safe é a chave natural (nome da pasta)."""
    __tablename__ = "projetos_meta"

    nome_safe  = Column(String,   primary_key=True)
    cliente_id = Column(Integer,  ForeignKey("clientes.id"), nullable=True)
    status     = Column(String(20), nullable=True)   # quente | morno | frio | convertido | perdido
    status_at  = Column(DateTime,   nullable=True)
    perdido_em     = Column(DateTime,   nullable=True)
    parametros_json = Column(Text, nullable=True)   # parâmetros estruturais da negociação (JSON, projeto-wide)
    loja_id        = Column(Integer,    ForeignKey("lojas.id"), nullable=True)
    criado_por_id  = Column(Integer,    ForeignKey("usuarios.id"), nullable=True)   # usuário que criou o projeto (escopo por projetista)
    data_entrega   = Column(DateTime,   nullable=True)   # âncora do cronograma REGRESSIVO (entrega ao cliente, def. na assinatura)
    data_inicio    = Column(DateTime,   nullable=True)   # âncora do cronograma PROGRESSIVO (início; def. assinatura + carência)
    equipe_json    = Column(Text,       nullable=True)   # Equipe do Projeto: seleções dos papéis SELETORES (medidor/finalizador/montagem[N])
    previsao_medicao = Column(DateTime, nullable=True)   # marco de medição (venda programada / obra do cliente)
    venda_programada = Column(Integer,  default=0)        # 1 = obra do cliente controla a medição (classificação + marcador no contrato, Fatia 3)
    folga_autorizada = Column(Integer,  default=0)        # 1 = data de entrega gravada apesar de folga NEGATIVA, sob autorização gerencial (Fatia 2)
    data_limite_contratual = Column(DateTime, nullable=True)  # D0 (assinatura) + prazo contratual em DIAS ÚTEIS — registrada na assinatura (Fatia 3)


class Briefing(Base):
    __tablename__ = "briefings"

    id                    = Column(Integer,  primary_key=True, autoincrement=True)
    cliente_id            = Column(Integer,  ForeignKey("clientes.id"), nullable=False)
    projeto_nome          = Column(Text,     nullable=True)
    criado_em             = Column(DateTime, default=datetime.utcnow)
    atualizado_em         = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Obrigatórios (gate etapa 2)
    data_atendimento      = Column(DateTime, nullable=False)
    consultor_id          = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    tipo_imovel           = Column(Text,     nullable=False)
    budget_declarado      = Column(Float,    nullable=False)
    categoria_proposta    = Column(Text,     nullable=False)
    data_entrega_desejada = Column(Text,     nullable=False)
    flexibilidade_prazo   = Column(Text,     nullable=False)

    # Opcionais
    condicao_imovel       = Column(Text,     nullable=True)
    metragem_m2           = Column(Float,    nullable=True)
    num_ambientes         = Column(Integer,  nullable=True)
    ambientes_prioritarios = Column(Text,    nullable=True)
    tem_arquiteto         = Column(Text,     nullable=True)
    nome_arquiteto        = Column(Text,     nullable=True)
    tem_gerente_obra      = Column(Integer,  nullable=True)
    end_empreendimento    = Column(Text,     nullable=True)
    estilo_decisao        = Column(Text,     nullable=True)
    estilo_vida           = Column(Text,     nullable=True)
    relacao_projeto       = Column(Text,     nullable=True)
    decisor               = Column(Text,     nullable=True)
    referencias_visuais   = Column(Text,     nullable=True)
    obs_referencias       = Column(Text,     nullable=True)
    experiencia_anterior  = Column(Text,     nullable=True)
    obs_experiencia       = Column(Text,     nullable=True)
    tem_budget            = Column(Text,     nullable=True)
    forma_pagamento_pref  = Column(Text,     nullable=True)
    data_entrega_limite   = Column(Text,     nullable=True)
    motivo_prazo          = Column(Text,     nullable=True)
    nao_abre_mao          = Column(Text,     nullable=True)
    restricoes            = Column(Text,     nullable=True)
    obs_livres            = Column(Text,     nullable=True)

    cliente   = relationship("Cliente", foreign_keys=[cliente_id])
    consultor = relationship("Usuario", foreign_keys=[consultor_id])


# ── EP-07: Versionamento de Orçamentos ───────────────────────────────────────

class PoolAmbiente(Base):
    """Pool permanente de XMLs por projeto. Registros nunca são deletados."""
    __tablename__ = "pool_ambientes"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_id     = Column(String,   nullable=False)          # nome da pasta do projeto
    nome           = Column(String,   nullable=False)          # nome base sem extensão
    versao         = Column(Integer,  default=1)
    nome_exibicao  = Column(String,   nullable=False)          # "Cozinha", "Cozinha_v1" etc.
    xml_path       = Column(String,   nullable=False)
    ambientes_json = Column(Text,     nullable=False)
    budget_total   = Column(Float,    nullable=False, default=0.0)
    order_total    = Column(Float,    nullable=False, default=0.0)
    # ── qualidade do XML (spec §8) ──
    qa_selo               = Column(String,  nullable=True)
    qa_pct_sem_acrescimo  = Column(Float,   nullable=True)
    qa_markup_xml         = Column(Float,   nullable=True)
    qa_custo_sem_venda    = Column(Integer, nullable=True)
    qa_override_por_id    = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    qa_override_motivo    = Column(String,  nullable=True)
    renegociar_pe         = Column(Integer, default=0)   # Revisão de PE (11c): ambiente marcado p/ renegociar (Fatia venda 2026-07-21)
    created_by     = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    criador           = relationship("Usuario", foreign_keys=[created_by])
    orcamento_links   = relationship("OrcamentoAmbiente", back_populates="pool_ambiente",
                                     cascade="all, delete-orphan")


class Orcamento(Base):
    """Versão de negociação dentro de um projeto. Nunca deletado."""
    __tablename__ = "orcamentos"

    id              = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_id      = Column(String,   nullable=False)
    nome            = Column(String,   nullable=False, default="Orçamento 1")
    ordem           = Column(Integer,  nullable=False, default=1)
    desconto_pct    = Column(Float,    default=0.0)
    forma_pagamento = Column(String,   nullable=True)
    negociacao_json = Column(Text,     nullable=True)   # snapshot das entradas da negociação (JSON)
    valor_total     = Column(Float,    default=0.0)
    valor_liquido   = Column(Float,    default=0.0)
    num_proposta    = Column(String,   nullable=True)   # nº da proposta comercial 'PV<AAAAMMDD><SEQ>' (gerado 1x)
    # ── derivados do motor de negociação (modo sombra — spec §5) ──
    vbvo         = Column(Float, default=0.0)
    cfo          = Column(Float, default=0.0)
    vbno         = Column(Float, default=0.0)
    vavo         = Column(Float, default=0.0)
    cust_ad      = Column(Float, default=0.0)
    com_arq_orc  = Column(Float, default=0.0)
    pro_fid_orc  = Column(Float, default=0.0)
    val_liq      = Column(Float, default=0.0)
    desc_tot_pct = Column(Float, default=0.0)
    markup       = Column(Float, default=0.0)
    cust_fin     = Column(Float, default=0.0)
    val_cont     = Column(Float, default=0.0)
    prov_imp     = Column(Float, default=0.0)
    out_forn     = Column(Float, default=0.0)   # Outros Fornecedores (editável Gerente Adm/Fin)
    # Fatia B (resultado financeiro): ramo do custo financeiro confirmado na AF (box).
    ramo_financeiro     = Column(String,  nullable=True)   # loja|loja_antecipacao|financeira (NULL = auto pela forma de pagamento)
    ramo_financeiro_seq = Column(Integer, default=0)       # contador p/ ref idempotente de troca de ramo
    # Fatia 3 da Revisão de PE (2026-07-21): orçamento de AJUSTE pós-assinatura — só os ambientes
    # marcados "Renegociar" na 11c, base de valores = PE (arquivo_pe). Isento das travas de contrato
    # assinado nos endpoints de negociação (margens/descontos/valor); NUNCA vira o contratado.
    complemento_pe           = Column(Integer, default=0)
    created_by      = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, nullable=True)
    loja_id         = Column(Integer,  ForeignKey("lojas.id"), nullable=True)

    criador   = relationship("Usuario", foreign_keys=[created_by])
    ambientes = relationship("OrcamentoAmbiente", back_populates="orcamento",
                             cascade="all, delete-orphan")


class OrcamentoAmbiente(Base):
    """Relação N:N entre orçamento e ambiente do pool."""
    __tablename__ = "orcamento_ambientes"

    orcamento_id     = Column(Integer, ForeignKey("orcamentos.id"),     primary_key=True)
    pool_ambiente_id = Column(Integer, ForeignKey("pool_ambientes.id"), primary_key=True)
    ordem            = Column(Integer, default=1)
    added_at         = Column(DateTime, default=datetime.utcnow)
    desconto_individual_pct = Column(Float, nullable=False, default=0.0, server_default="0")

    orcamento     = relationship("Orcamento",     back_populates="ambientes")
    pool_ambiente = relationship("PoolAmbiente",  back_populates="orcamento_links")


# ── Ciclo do Projeto ──────────────────────────────────────────────────────────

class CicloEtapa(Base):
    """Estado de cada etapa do pipeline por projeto."""
    __tablename__ = "ciclo_etapas"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome   = Column(Text,     nullable=False)   # nome_safe
    etapa_codigo   = Column(Text,     nullable=False)   # "7", "11b", "17a" etc.
    status         = Column(Text,     nullable=False, default="pendente")
    responsavel_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    iniciado_em    = Column(DateTime, nullable=True)
    concluido_em   = Column(DateTime, nullable=True)   # = data_conclusao (Modulos_Orizon_v11)
    # Cronograma do Ciclo (Modulos_Orizon_v11): data prevista de conclusão (D0 + prazo padrão),
    # constituída na assinatura do contrato; editável só por reautenticação Gerente+ (auditada).
    data_prevista_conclusao = Column(DateTime, nullable=True)
    # Responsável por função (Modulos_Orizon_v12): funcao_responsavel_id é herdada do Cronograma de
    # Projeto Padrão no D0 (a FUNÇÃO que executa a fase); responsavel_funcionario_id nasce vazio e é
    # escolhido depois, restrito aos funcionários que têm essa função.
    funcao_responsavel_id       = Column(Integer, ForeignKey("funcoes.id"), nullable=True)
    responsavel_funcionario_id  = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)
    observacoes    = Column(Text,     nullable=True)

    __table_args__ = (UniqueConstraint("projeto_nome", "etapa_codigo", name="uq_ciclo_etapa"),)

    responsavel = relationship("Usuario", foreign_keys=[responsavel_id])


class AtribuicaoAmbiente(Base):
    """Mapa de Atribuições (Regras_Funcoes_Perfis_Atribuicoes §4/§5): quem executa cada papel
    operacional (PE/Medição/Montagem/Assistência) por ambiente do projeto. A atribuição CONCEDE
    visibilidade escopada ao Usuário vinculado ao profissional. pool_ambiente_id NULL = 'projeto
    inteiro' (default que vale para os ambientes sem atribuição própria). Um profissional por
    papel/ambiente (UniqueConstraint). Trocas ficam em LogAcaoGerencial (sem versionar a tabela)."""
    __tablename__ = "atribuicoes_ambiente"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id          = Column(Integer,  ForeignKey("lojas.id"), nullable=False)   # isolamento F4
    projeto_nome     = Column(Text,     nullable=False)                            # nome_safe
    pool_ambiente_id = Column(Integer,  ForeignKey("pool_ambientes.id"), nullable=True)  # NULL = projeto inteiro
    papel            = Column(Text,     nullable=False)   # projeto_executivo|medicao|montagem|assistencia
    funcionario_id   = Column(Integer,  ForeignKey("funcionarios.id"), nullable=True)
    terceiro_id      = Column(Integer,  ForeignKey("terceiros.id"), nullable=True)
    atribuido_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    criado_em        = Column(DateTime, default=datetime.utcnow)
    atualizado_em    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("projeto_nome", "pool_ambiente_id", "papel",
                                       name="uq_atribuicao_papel_ambiente"),)


class CicloLogistico(Base):
    """Expedição (Modulos_Orizon_v5, módulo 7): pedido produzido -> cliente com o produto.
    Estado AGREGADO + referências por ID a Projetos/Estoque/Fiscal — NUNCA duplica dado.
    Prazos (planejado) entram uma vez na criação; datas (realizado) são capturadas ao mover o card."""
    __tablename__ = "ciclo_logistico"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    projeto_nome   = Column(Text,     nullable=False)                 # ref: nome_safe do projeto
    numero_pedido  = Column(Text,     nullable=True)                  # nº do pedido na fábrica
    status_atual   = Column(Text,     nullable=False, default="Pedido Enviado")
    # Prazos (planejado — informados pela fábrica na criação)
    prazo_producao    = Column(Date, nullable=True)
    prazo_saida       = Column(Date, nullable=True)
    prazo_recebimento = Column(Date, nullable=True)
    prazo_entrega     = Column(Date, nullable=True)
    # Realizado (capturado ao mover o card, editável)
    data_producao     = Column(Date, nullable=True)
    data_saida        = Column(Date, nullable=True)
    data_recebimento  = Column(Date, nullable=True)
    data_entrega      = Column(Date, nullable=True)
    # Transporte
    transportadora = Column(Text, nullable=True)
    cte            = Column(Text, nullable=True)                      # conhecimento de transporte
    rastreio       = Column(Text, nullable=True)
    # Referências (nunca duplica): NF-e é dado do Fiscal
    nfe_id         = Column(Integer, ForeignKey("documento_fiscal.id"), nullable=True)
    criado_em      = Column(DateTime, nullable=True)
    criado_por_id  = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    # Desmembramento parcial (spec 2026-07-13, Fatia 2): 1 linha por parcela; NULL = projeto-wide legado.
    parcela_id     = Column(Integer,  ForeignKey("parcela_projeto.id"), nullable=True)


class CicloLogisticoTransicao(Base):
    """Histórico auditável de mudanças de status_atual do CicloLogistico (quem/quando)."""
    __tablename__ = "ciclo_logistico_transicao"

    id                 = Column(Integer,  primary_key=True, autoincrement=True)
    ciclo_logistico_id = Column(Integer,  ForeignKey("ciclo_logistico.id"), nullable=False)
    de_status          = Column(Text,     nullable=True)
    para_status        = Column(Text,     nullable=False)
    usuario_id         = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    quando             = Column(DateTime, nullable=True)


# ── Desmembramento parcial na Revisão de PE (spec docs/superpowers/specs/2026-07-13-...) ────────

class ParcelaProjeto(Base):
    """Parcela = grupo de ambientes que percorre o ciclo (aprovação→entrega→NF-e) de forma
    independente (decisão #1). Congela a fração do Val_Cont na criação (#5). Usada a partir da Fatia 2.
    `saldo_margem_estimado` é DERIVADO (#9), recalculável de pool_ambientes + arquivo_pe — a coluna
    existe só como cache opcional, nunca como fonte de verdade."""
    __tablename__ = "parcela_projeto"
    id                    = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome          = Column(Text,     nullable=False, index=True)   # nome_safe
    ordem                 = Column(Integer,  nullable=False, default=1)     # maior ordem = "última" (#5)
    status                = Column(String(16), nullable=False, default="aguardando")  # aguardando|em_aprovacao|liquidada
    fracao_val_cont       = Column(Float,    nullable=False, default=0.0)   # congelada (#5)
    val_cont_congelado    = Column(Float,    nullable=False, default=0.0)   # congelado (#5)
    orcamento_id          = Column(Integer,  ForeignKey("orcamentos.id"), nullable=True)
    saldo_margem_estimado = Column(Float,    nullable=True)   # cache opcional do derivado (#9)
    criado_em             = Column(DateTime, default=datetime.utcnow)
    criado_por_id         = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    prazo_conclusao       = Column(DateTime, nullable=True)   # Fase A: prazo da fase (validado × cronograma)


class ParcelaAmbiente(Base):
    """Membership N:N parcela ↔ ambiente do pool (#1)."""
    __tablename__ = "parcela_ambiente"
    parcela_id       = Column(Integer, ForeignKey("parcela_projeto.id"), primary_key=True)
    pool_ambiente_id = Column(Integer, ForeignKey("pool_ambientes.id"),  primary_key=True)


class ArquivoPE(Base):
    """XML/Promob do Projeto Executivo — FORA do pool do orçamento (decisão #2). Documento de
    comparação/liquidação: NÃO cria PoolAmbiente, NÃO vincula a orçamento, NÃO alimenta o motor →
    não esbarra na trava `_contrato_assinado`. `valor_atualizado` = CFO/custo de fábrica extraído do
    XML (Σ order_total), NÃO valor de venda (#4)."""
    __tablename__ = "arquivo_pe"
    id               = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome     = Column(Text,     nullable=False, index=True)   # nome_safe
    pool_ambiente_id = Column(Integer,  ForeignKey("pool_ambientes.id"), nullable=False)  # a qual ambiente o PE se refere
    formato          = Column(String(10), nullable=False)   # 'xml_pe' | 'promob_pe'
    arquivo_path     = Column(Text,     nullable=True)
    valor_atualizado = Column(Float,    nullable=True)       # CFO do PE (só p/ 'xml_pe'); null = não carregado
    valor_venda      = Column(Float,    nullable=True)       # VENDA bruta do PE (`total` do XML = VBVA) — Fatia venda 2026-07-21
    carregado_em     = Column(DateTime, default=datetime.utcnow)
    carregado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    __table_args__ = (UniqueConstraint("projeto_nome", "pool_ambiente_id", "formato", name="uq_arquivo_pe"),)


class AssistenciaCaso(Base):
    """Módulo Assistências (Modulos_Orizon_v5, módulo 10 / Financeiro v7 §6): atendimento pós-execução.
    Duas dimensões independentes: sub_tipo (montagem × pós-conclusão) e tipo_custo (paga/loja/fabrica),
    este DERIVADO do motivo. Realizar o caso dispara o lançamento contábil conforme o tipo de custo."""
    __tablename__ = "assistencia_caso"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    projeto_nome   = Column(Text,     nullable=True)                 # ref: nome_safe (opcional)
    sub_tipo       = Column(Text,     nullable=False)                # "montagem" | "pos_conclusao"
    motivo         = Column(Text,     nullable=False)                # chave de mod_assistencias.MOTIVOS
    tipo_custo     = Column(Text,     nullable=False)                # "paga" | "loja" | "fabrica" (derivado)
    descricao      = Column(Text,     nullable=True)
    valor          = Column(Float,    nullable=True)                 # custo do reparo / valor da venda
    status         = Column(Text,     nullable=False, default="aberto")   # aberto | realizado
    reembolsado_fabrica = Column(Integer, nullable=True)             # fase 2: fábrica reembolsou de fato
    ref_lancamento = Column(Text,     nullable=True)                 # ref idempotente do lançamento
    criado_em      = Column(DateTime, nullable=True)
    realizado_em   = Column(DateTime, nullable=True)
    criado_por_id  = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)


class ProvisaoRegistro(Base):
    """Provisões registradas por versão (venda/rev1/rev2) de um orçamento.
    venda = snapshot na geração do contrato; rev1/rev2 = aprovação financeira I/II."""
    __tablename__ = "provisao_registro"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=False)
    versao       = Column(String(8), nullable=False)   # 'venda' | 'rev1' | 'rev2'
    itens_json   = Column(Text,      nullable=False)    # {rubrica: valor_R$}
    cfo          = Column(Float, default=0.0)           # base congelada p/ recalcular margem
    val_liq      = Column(Float, default=0.0)
    cust_var     = Column(Float, default=0.0)
    marg_cont    = Column(Float, default=0.0)
    decisao      = Column(String(10), nullable=True)    # 'concorda' | 'revisa' | None (venda)
    por_id       = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    criado_em    = Column(DateTime, default=datetime.utcnow)
    travada_em   = Column(DateTime, nullable=True)      # Fatia C (#10): versão aprovada e travada (não reedita sem Diretor)

    __table_args__ = (UniqueConstraint("orcamento_id", "versao", name="uq_provisao_orc_versao"),)


class Conta(Base):
    """Conta do Plano de Contas (árvore hierárquica), por owner (rede|loja).
    Módulo Financeiro sub-projeto #1. Fonte: Especificacao_Financeiro_Orizon_v2.docx §2/§2.1."""
    __tablename__ = "conta"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo = Column(String(10), nullable=False)   # 'rede' | 'loja'
    owner_id   = Column(Integer,    nullable=False)
    codigo     = Column(String(20), nullable=False)   # hierárquico: '5', '5.4', '5.4.01'
    nome       = Column(Text,       nullable=False)
    grupo      = Column(Integer,    nullable=False)    # 1..5 (Ativo/Passivo/PL/Receita/Despesa)
    tipo       = Column(String(10), nullable=False)    # 'sintetica' (agrupa) | 'analitica' (folha)
    natureza   = Column(String(8),  nullable=False)    # 'devedora' | 'credora'
    pai_id     = Column(Integer, ForeignKey("conta.id"), nullable=True)
    ativa      = Column(Integer, default=1)
    ordem      = Column(Integer, default=0)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("owner_tipo", "owner_id", "codigo", name="uq_conta_owner_codigo"),)


class Lancamento(Base):
    """Lançamento contábil (partida dobrada) do Livro. Módulo Financeiro sub-projeto #2.
    Carrega projeto_id (dimensão gerencial, = nome_safe). `data` = competência."""
    __tablename__ = "lancamento"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo       = Column(String(10), nullable=False)
    owner_id         = Column(Integer,    nullable=False)
    data             = Column(DateTime,   nullable=False, default=datetime.utcnow)
    conta_debito_id  = Column(Integer, ForeignKey("conta.id"), nullable=False)
    conta_credito_id = Column(Integer, ForeignKey("conta.id"), nullable=False)
    valor            = Column(Float,      nullable=False)
    projeto_id       = Column(String,     nullable=True)    # nome_safe (dimensão gerencial)
    origem           = Column(String(64), nullable=False, default="manual")   # 'manual' | tipo de evento
    # 2026-07-15: alargado de String(30) — SQLite nunca validou o limite, mas vários EVENTOS de
    # mod_contabil.py passam de 30 chars (ex.: 'reconhecimento_despesa_retencao_com_vendas', 42
    # chars); achado ao validar a suíte contra Postgres de verdade (Etapa 4 da migração).
    historico        = Column(Text,       nullable=True)
    ref              = Column(String(80), nullable=True)   # idempotência do wiring (ex.: 'fat:NFE-<proj>-<id>')
    motivo           = Column(String(30), nullable=True)   # dimensão do reparo em garantia: 'defeito_fabrica'|'outro' (§6.2)
    ia_sugestao      = Column(Text,       nullable=True)    # snapshot da sugestão da IA de classificação (§6.3)
    criado_em        = Column(DateTime,   default=datetime.utcnow)


class PeriodoContabil(Base):
    """Snapshot de Auditoria/Reconciliação de um período (Módulo Financeiro sub-projeto #6).
    Rateia a despesa fixa aos projetos (margem plena) e registra a divergência vs. o resultado societário."""
    __tablename__ = "periodo_contabil"
    id                   = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo           = Column(String(10), nullable=False)
    owner_id             = Column(Integer,    nullable=False)
    inicio               = Column(DateTime, nullable=True)
    fim                  = Column(DateTime, nullable=True)
    status               = Column(String(10), default="fechado")   # 'aberto' | 'fechado'
    metodologia          = Column(String(30), nullable=False)      # base de rateio (vigência)
    resultado_societario = Column(Float, default=0.0)
    soma_margem_plena    = Column(Float, default=0.0)
    divergencia_residual = Column(Float, default=0.0)
    dados_json           = Column(Text, nullable=True)             # alocacao_por_projeto serializada
    criado_em            = Column(DateTime, default=datetime.utcnow)


class Contrato(Base):
    """Contrato gerado a partir do orçamento aprovado."""
    __tablename__ = "contratos"

    id                   = Column(Integer,  primary_key=True, autoincrement=True)
    num_contrato         = Column(Text,     nullable=True)   # LOJA-AAAA-MM-DD-SEQ
    projeto_nome         = Column(Text,     nullable=False)
    orcamento_id         = Column(Integer,  ForeignKey("orcamentos.id"), nullable=False)
    template_path        = Column(Text,     nullable=False, default="config/contrato_template.docx")
    pdf_path             = Column(Text,     nullable=True)
    endereco_instalacao  = Column(Text,     nullable=True)
    pagamento_json       = Column(Text,     nullable=True)   # JSON com cronograma de parcelas
    status               = Column(Text,     nullable=False, default="rascunho")
    # status: rascunho | gerado | assinado_loja | assinado_cliente | vigente
    adendo               = Column(Text,     nullable=True)
    gerado_em            = Column(DateTime, nullable=True)
    gerado_por_id        = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    d4sign_uuid          = Column(Text,     nullable=True)   # fase futura D4Sign
    loja_id              = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    loja_snapshot_json   = Column(Text,     nullable=True)   # snapshot dos dados da loja (F3)
    modelo_versao_id     = Column(Integer, ForeignKey("documento_modelos.id"), nullable=True)
    # NULL = contrato legado -> cai no contrato_template/contrato.md global.
    # Preenchido = reproduz as cláusulas daquela versão, mesmo que a loja já
    # tenha trocado o modelo. Ver docs/superpowers/specs/2026-07-15-modelos-documentos-loja-design.md D6.

    gerado_por   = relationship("Usuario",  foreign_keys=[gerado_por_id])
    orcamento    = relationship("Orcamento", foreign_keys=[orcamento_id])
    assinaturas  = relationship("ContratoAssinatura", back_populates="contrato",
                                cascade="all, delete-orphan")


class ContratoAssinatura(Base):
    """Registro de assinatura interna (MVP) ou confirmação D4Sign (futuro)."""
    __tablename__ = "contratos_assinaturas"

    id           = Column(Integer,  primary_key=True, autoincrement=True)
    contrato_id  = Column(Integer,  ForeignKey("contratos.id"), nullable=False)
    parte        = Column(Text,     nullable=False)   # loja | cliente
    nome         = Column(Text,     nullable=False)
    cpf          = Column(Text,     nullable=False)
    assinado_em  = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_origem    = Column(Text,     nullable=True)
    hash_sha256  = Column(Text,     nullable=False)

    contrato = relationship("Contrato", back_populates="assinaturas")


class Aditivo(Base):
    """Termo Aditivo do contrato (Fatia 3 da Revisão de PE, 2026-07-21): documenta a DIFERENÇA dos
    ambientes renegociados (orçamento de ajuste × contrato original), com modelo versionado por loja
    (documento_modelos tipo 'termo_aditivo') e assinatura loja+cliente. TABELA PRÓPRIA de propósito:
    uma linha em `contratos` viraria "o último contrato" e quebraria a trava `_contrato_assinado`.
    Sem efeito contábil (decisão do usuário: gerencial; acerto na liquidação/NF-e)."""
    __tablename__ = "aditivos"

    id                 = Column(Integer,  primary_key=True, autoincrement=True)
    num_aditivo        = Column(Text,     nullable=True)    # TA<AAAAMMDD><SEQ> (gerado 1x)
    projeto_nome       = Column(Text,     nullable=False, index=True)
    contrato_id        = Column(Integer,  ForeignKey("contratos.id"), nullable=False)
    orcamento_complemento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=False)
    pdf_path           = Column(Text,     nullable=True)
    dados_json         = Column(Text,     nullable=True)    # snapshot da diferença (ambientes, valores)
    status             = Column(Text,     nullable=False, default="rascunho")
    # status: rascunho | para_assinatura | assinado_loja | assinado_cliente | assinado
    gerado_em          = Column(DateTime, nullable=True)
    gerado_por_id      = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    loja_id            = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    modelo_versao_id   = Column(Integer,  ForeignKey("documento_modelos.id"), nullable=True)

    assinaturas = relationship("AditivoAssinatura", back_populates="aditivo",
                               cascade="all, delete-orphan")


class AditivoAssinatura(Base):
    """Assinatura interna do Termo Aditivo — espelho de ContratoAssinatura."""
    __tablename__ = "aditivos_assinaturas"

    id          = Column(Integer,  primary_key=True, autoincrement=True)
    aditivo_id  = Column(Integer,  ForeignKey("aditivos.id"), nullable=False)
    parte       = Column(Text,     nullable=False)   # loja | cliente
    nome        = Column(Text,     nullable=False)
    cpf         = Column(Text,     nullable=False)
    assinado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_origem   = Column(Text,     nullable=True)
    hash_sha256 = Column(Text,     nullable=False)

    aditivo = relationship("Aditivo", back_populates="assinaturas")


class AprovacaoPE(Base):
    """Aprovação do Projeto Executivo (correção da Fatia 3, 2026-07-21): substitui o upload de
    "PE Assinado" na 11e — documento GERADO pelo sistema (modelo por loja tipo 'aprovacao_pe'),
    registrando os AMBIENTES APROVADOS (dados_json — importa quando há desmembramento), imprimível
    e assinável internamente (loja+cliente, mecanismo do contrato/aditivo; integração de assinatura
    digital fica como fase futura, mesmo placeholder do contrato)."""
    __tablename__ = "aprovacoes_pe"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    num_aprovacao    = Column(Text,     nullable=True)    # AP<AAAAMMDD><SEQ> (gerado 1x)
    projeto_nome     = Column(Text,     nullable=False, index=True)
    contrato_id      = Column(Integer,  ForeignKey("contratos.id"), nullable=False)
    pdf_path         = Column(Text,     nullable=True)
    dados_json       = Column(Text,     nullable=True)    # {"ambientes": [{id, nome}]} aprovados
    status           = Column(Text,     nullable=False, default="rascunho")
    # status: rascunho | para_assinatura | assinado_loja | assinado_cliente | assinado
    gerado_em        = Column(DateTime, nullable=True)
    gerado_por_id    = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    loja_id          = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    modelo_versao_id = Column(Integer,  ForeignKey("documento_modelos.id"), nullable=True)

    assinaturas = relationship("AprovacaoPEAssinatura", back_populates="aprovacao",
                               cascade="all, delete-orphan")


class AprovacaoPEAssinatura(Base):
    """Assinatura interna da Aprovação do PE — espelho de ContratoAssinatura."""
    __tablename__ = "aprovacoes_pe_assinaturas"

    id           = Column(Integer,  primary_key=True, autoincrement=True)
    aprovacao_id = Column(Integer,  ForeignKey("aprovacoes_pe.id"), nullable=False)
    parte        = Column(Text,     nullable=False)   # loja | cliente
    nome         = Column(Text,     nullable=False)
    cpf          = Column(Text,     nullable=False)
    assinado_em  = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_origem    = Column(Text,     nullable=True)
    hash_sha256  = Column(Text,     nullable=False)

    aprovacao = relationship("AprovacaoPE", back_populates="assinaturas")


class Conversa(Base):
    """Chat do Orizon — Fatia 1/Fundação (spec _geral/2026-07-25-chat-projeto-…): âncora
    FLEXÍVEL, decisão da seção 2 — `projeto_nome` e `cliente_id` são AMBOS opcionais (projeto
    em andamento; cliente sem projeto; ou os dois em branco = reclamação institucional sem
    vínculo). `loja_id` é sempre presente: mesmo a reclamação institucional pertence à loja
    que a registrou (tenancy). Natureza/transferência, bloqueador, modo privado e EnvioExterno
    são FATIAS FUTURAS (2-7) — não adicionar campos aqui fora da spec."""
    __tablename__ = "conversas"

    id           = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id      = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)
    projeto_nome = Column(Text,     nullable=True, index=True)
    cliente_id   = Column(Integer,  ForeignKey("clientes.id"), nullable=True)
    criado_em    = Column(DateTime, default=datetime.utcnow)


class ConversaMensagem(Base):
    """Mensagem da Conversa (Fatia 1: só interna). `canal` já nasce na coluna porque é do
    modelo consolidado da spec, mas na Fatia 1 apenas 'interno' circula (mod_chat valida).
    `autor_usuario_id` NULL fica RESERVADO para resposta vinda de fora (fatias 6-7,
    e-mail/WhatsApp) — nenhum caminho interno cria mensagem sem autor hoje."""
    __tablename__ = "conversa_mensagens"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    conversa_id      = Column(Integer,  ForeignKey("conversas.id"), nullable=False, index=True)
    autor_usuario_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    corpo            = Column(Text,     nullable=False)
    canal            = Column(String(20), nullable=False, default="interno")
    # Fatia 2 (Responsabilidade + transferência — spec seção 6): 'transferencia' oficializa a
    # troca de responsabilidade gravando em CicloEtapa.responsavel_funcionario_id (o campo do
    # v12; NADA de estado paralelo). `bloqueador` nesta fatia é SÓ flag — o gate real em
    # pode_avancar() é a Fatia 3. `resolvido_em` fecha o bloqueador (Fatia 3 também).
    natureza         = Column(String(20), nullable=False, default="interacao")   # interacao | transferencia
    etapa_codigo     = Column(String(10), nullable=True)
    transferido_para_funcionario_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)
    documento_ref_id = Column(Integer,  nullable=True)   # Fatia 5 (documento compartilhável)
    bloqueador       = Column(Integer,  nullable=False, default=0)
    resolvido_em     = Column(DateTime, nullable=True)
    # Fatia 4 (modo privado, decisão 8): privada=1 → o corpo em claro NUNCA persiste (fica
    # ""), só `corpo_cifrado` (Fernet, chave ORIZON_CHAT_ENC_KEY do ambiente). Metadados
    # continuam visíveis a todos; o texto só decripta p/ quem tem `ver_mensagem_privada`.
    privada          = Column(Integer,  nullable=False, default=0)
    corpo_cifrado    = Column(Text,     nullable=True)
    criado_em        = Column(DateTime, default=datetime.utcnow)


class ContatoConfirmacao(Base):
    """Confirmação dos contatos de comunicação na fase de contrato (decisão 13 da spec de chat,
    mini-frente 2026-07-25): o operador VÊ os contatos (cliente e arquiteto, se houver) e
    escolhe explicitamente — 'confirmado' (canal validado) ou 'sem_whatsapp' ("seguir sem
    WhatsApp"). Gate bloqueante-suave: o POST do contrato exige uma confirmação registrada;
    nunca passa sem ver, mas sempre há saída explícita. Append-only (a mais recente vale);
    `contatos_json` guarda o snapshot do que foi mostrado na hora da escolha (auditoria —
    decisão 12: o dado vivo é o cadastro, aqui é só o retrato do momento)."""
    __tablename__ = "contato_confirmacoes"

    id                = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id           = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)
    projeto_nome      = Column(Text,     nullable=False, index=True)
    modo              = Column(String(20), nullable=False)   # confirmado | sem_whatsapp
    contatos_json     = Column(Text,     nullable=True)
    confirmado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    confirmado_em     = Column(DateTime, default=datetime.utcnow)


class ContraparteFinanceira(Base):
    """Cadastro de Credores/Devedores (revisão 2026-07-22): entidade contra a qual acordos são
    lançados — fábrica, empresa (do grupo ou não) ou banco. O papel (credor|devedor) é dado pelo
    TIPO de cada acordo (crédito nosso ⇒ contraparte devedora; dívida nossa ⇒ contraparte credora)."""
    __tablename__ = "contraparte_financeira"

    id            = Column(Integer,  primary_key=True, autoincrement=True)
    nome          = Column(Text,     nullable=False)
    tipo          = Column(String(10), nullable=False)   # fabrica | empresa | banco
    # cadastro completo (pedido 2026-07-22): CNPJ, contato financeiro e endereço
    cnpj          = Column(String(18), nullable=True)
    telefone      = Column(String(20), nullable=True)
    email         = Column(Text,     nullable=True)
    cep           = Column(String(9),  nullable=True)
    logradouro    = Column(Text,     nullable=True)
    numero        = Column(String(20), nullable=True)
    complemento   = Column(Text,     nullable=True)
    bairro        = Column(Text,     nullable=True)
    cidade        = Column(Text,     nullable=True)
    uf            = Column(String(2),  nullable=True)
    criado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    criado_em     = Column(DateTime, default=datetime.utcnow)


class AcordoFabrica(Base):
    """Acordo com a fábrica (spec 2026-07-21): crédito (fábrica deve à titular) ou dívida (titular
    deve à fábrica), com saldo CONTROLADO NO RAZÃO da loja titular (1.1.08 / 2.1.08). O cadastro
    dispara a implantação pelo PL (× 3.5, CPC 23). Consumido pelos ajustes vinculados até esgotar."""
    __tablename__ = "acordo_fabrica"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    descricao        = Column(Text,     nullable=False)
    tipo             = Column(String(10), nullable=False)   # credito | divida
    # Revisão "Acordos Financeiros" (2026-07-21, feedback de teste): contraparte generalizada —
    # fábrica, EMPRESA (do grupo ou não; cada loja registra só o SEU lado, sem acerto automático)
    # ou BANCO (empréstimos). O nome é livre (ex.: "Verano", "Banco Itaú").
    contraparte_tipo = Column(String(10), nullable=False, default="fabrica")  # fabrica|empresa|banco
    contraparte_nome = Column(Text,     nullable=True)
    contraparte_id   = Column(Integer,  ForeignKey("contraparte_financeira.id"), nullable=True)
    loja_titular_id  = Column(Integer,  ForeignKey("lojas.id"), nullable=False)
    conta_saldo      = Column(String(10), nullable=False)   # 1.1.08|2.1.08|1.1.09|2.1.09|2.1.10
    valor_implantado = Column(Float,    nullable=False, default=0.0)
    status           = Column(String(12), nullable=False, default="ativo")   # ativo|esgotado|encerrado
    criado_por_id    = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    criado_em        = Column(DateTime, default=datetime.utcnow)

    ajustes = relationship("AjusteFabrica", back_populates="acordo")


class AjusteFabrica(Base):
    """Regra de consumo por loja (spec 2026-07-21): % de desconto/acréscimo aplicado na
    Conferência do Pedido sobre o valor de fábrica. `tratamento='custo'` (sem acordo) muda o
    custo econômico via ajustar_provisao_delta; `'consumir_saldo'` amortiza o acordo vinculado.
    `loja_id ≠ loja_titular` do acordo ⇒ fluxo intercompany (conta corrente + acerto)."""
    __tablename__ = "ajuste_fabrica"

    id            = Column(Integer,  primary_key=True, autoincrement=True)
    acordo_id     = Column(Integer,  ForeignKey("acordo_fabrica.id"), nullable=True)
    loja_id       = Column(Integer,  ForeignKey("lojas.id"), nullable=False)   # quem consome
    descricao     = Column(Text,     nullable=True)
    tipo          = Column(String(10), nullable=False)    # desconto | acrescimo
    natureza      = Column(String(10), nullable=False, default="recorrente")   # recorrente|pontual
    pct           = Column(Float,    nullable=False)
    base          = Column(String(16), nullable=False, default="pos_descontos")  # |valor_conferido
    tratamento    = Column(String(14), nullable=False)    # custo (consumir_saldo: legado, recusado na criação desde 2026-07-22)
    vigencia_de   = Column(DateTime, nullable=True)
    vigencia_ate  = Column(DateTime, nullable=True)
    projetos_json = Column(Text,     nullable=True)       # pontual: lista de nome_safe vinculados
    ativo         = Column(Integer,  nullable=False, default=1)
    criado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    criado_em     = Column(DateTime, default=datetime.utcnow)

    acordo = relationship("AcordoFabrica", back_populates="ajustes")


class AcordoMovimento(Base):
    """Movimento MANUAL de um acordo financeiro (revisão 2026-07-21): pagamento, recebimento,
    atualização (juros), transferência entre acordos da MESMA loja, captação (empréstimo novo) e
    baixa de encerramento. `valor` sempre positivo; o efeito no saldo vem do `tipo`."""
    __tablename__ = "acordo_movimento"

    id            = Column(Integer,  primary_key=True, autoincrement=True)
    acordo_id     = Column(Integer,  ForeignKey("acordo_fabrica.id"), nullable=False, index=True)
    tipo          = Column(String(20), nullable=False)
    # pagamento|recebimento|atualizacao|transferencia_in|transferencia_out|baixa_encerramento
    valor         = Column(Float,    nullable=False)
    lancamento_ref = Column(Text,    nullable=True)
    criado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    criado_em     = Column(DateTime, default=datetime.utcnow)


class AjusteFabricaAplicacao(Base):
    """Aplicação de um ajuste numa venda (trilha de auditoria — fonte do saldo por acordo).
    Revisão 2026-07-21: `status` é sempre 'n/a' (o fluxo de acerto foi eliminado; a coluna e
    `acerto_ref` ficam vestigiais). Aplicações NEGATIVAS registram reversões (devolução)."""
    __tablename__ = "ajuste_fabrica_aplicacao"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    ajuste_id      = Column(Integer,  ForeignKey("ajuste_fabrica.id"), nullable=False)
    projeto_nome   = Column(Text,     nullable=False, index=True)
    base_calculo   = Column(Float,    nullable=True)
    pct_snapshot   = Column(Float,    nullable=True)
    valor          = Column(Float,    nullable=False)
    status         = Column(String(16), nullable=False, default="n/a")   # pendente_acerto|acertada|n/a
    lancamento_ref = Column(Text,     nullable=True)
    acerto_ref     = Column(Text,     nullable=True)
    criado_em      = Column(DateTime, default=datetime.utcnow)


class CicloDocumento(Base):
    """Documento carregado numa subfase do ciclo. Append-only: nunca sobrescreve."""
    __tablename__ = "ciclo_documentos"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome   = Column(Text,     nullable=False)   # nome_safe
    etapa_codigo   = Column(Text,     nullable=False)   # "11a","11b","11c","11e"
    tipo           = Column(Text,     nullable=False)   # pe_planta_pontos, ...
    arquivo_path   = Column(Text,     nullable=False)   # relativo a PROJETOS/<nome>/
    nome_original  = Column(Text,     nullable=False)
    enviado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    enviado_em     = Column(DateTime, nullable=False, default=datetime.utcnow)

    enviado_por = relationship("Usuario", foreign_keys=[enviado_por_id])


class CicloRevisao(Base):
    """Revisão aberta numa subfase (reabertura em cascata)."""
    __tablename__ = "ciclo_revisoes"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome     = Column(Text,     nullable=False)
    etapa_codigo     = Column(Text,     nullable=False)
    aberta_por_id    = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    aberta_em        = Column(DateTime, nullable=False, default=datetime.utcnow)
    relatorio_doc_id = Column(Integer,  ForeignKey("ciclo_documentos.id"), nullable=True)
    motivo           = Column(Text,     nullable=True)

    aberta_por = relationship("Usuario", foreign_keys=[aberta_por_id])


class DocumentoModelo(Base):
    """Modelo de documento de uma loja (contrato/proposta), versionado.

    IMUTÁVEL: uma versão nunca muda de corpo_md depois de criada. Editar é criar
    a versão seguinte. É o que dá sentido a Contrato.modelo_versao_id — se a linha
    fosse mutável, o ponteiro não garantiria a reprodução do contrato assinado.
    """
    __tablename__ = "documento_modelos"

    # @validates é o ÚNICO do database.py — deliberado, não desleixo: nenhuma outra
    # tabela carrega uma garantia jurídica. Aqui a imutabilidade não é preferência de
    # estilo, é o que sustenta reproduzir as cláusulas de um contrato já assinado.
    # Docstring não impede `m.corpo_md = "outra"; db.commit()`; isto impede.

    id            = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id       = Column(Integer,  ForeignKey("lojas.id"), nullable=False)
    tipo          = Column(Text,     nullable=False)   # contrato | proposta
    versao        = Column(Integer,  nullable=False)   # sequencial por (loja_id, tipo)
    nome          = Column(Text,     nullable=True)
    corpo_md      = Column(Text,     nullable=False)
    origem_nome   = Column(Text,     nullable=True)
    origem_path   = Column(Text,     nullable=True)
    origem_sha256 = Column(Text,     nullable=True)
    ativo         = Column(Integer,  nullable=False, default=0)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    criado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("loja_id", "tipo", "versao", name="uq_doc_modelo_versao"),
    )

    @validates("corpo_md")
    def _corpo_e_imutavel(self, key, value):
        """Barra a edição de corpo_md depois que a linha existe.

        Dispara no setattr. `self.id is not None` só vale depois do flush, então o
        construtor (id ainda None) passa e a carga do banco nem chega aqui — o loader
        do SQLAlchemy não passa pelo setattr instrumentado. Verificado por experimento.
        """
        if self.id is not None:
            raise ValueError(
                "corpo_md é imutável: um contrato pode apontar para esta versão e "
                "regerá-lo tem que reproduzir as cláusulas originais. "
                "Para mudar o modelo, crie a próxima versão (mod_documentos.criar_versao)."
            )
        return value


class DocumentoTipo(Base):
    """Tipo de documento CUSTOMIZADO por loja ("Novo Documento" do painel Config →
    Documentos, spec 2026-07-22): nome dado pelo usuário + etapa do ciclo associada.
    Os 4 tipos nativos (contrato/proposta/termo_aditivo/aprovacao_pe) NÃO viram linha
    aqui. O slug (`doc_<nome-slugificado>`) é a chave usada em documento_modelos.tipo
    e é path-safe por construção — vira componente de diretório em documentos_loja/.
    A geração do documento DENTRO do ciclo é frente futura; o vínculo já fica gravado."""
    __tablename__ = "documento_tipos"

    id            = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id       = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)
    slug          = Column(Text,     nullable=False)
    nome          = Column(Text,     nullable=False)
    etapa_ciclo   = Column(Text,     nullable=True)   # código da etapa (ETAPAS_CICLO); opcional
    criado_em     = Column(DateTime, default=datetime.utcnow)
    criado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("loja_id", "slug", name="uq_documento_tipos_loja_slug"),
    )


class Emitente(Base):
    """Identidade fiscal de 1 CNPJ. Emite documentos; NÃO é a loja vendedora."""
    __tablename__ = "emitente"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj = Column(String(18), nullable=True)
    razao_social = Column(Text, nullable=True)
    nome_fantasia = Column(Text, nullable=True)
    inscricao_estadual = Column(Text, nullable=True)
    inscricao_municipal = Column(Text, nullable=True)
    regime_tributario = Column(Text, nullable=True)
    csosn_padrao = Column(Text, nullable=True)
    csosn_contribuinte = Column(Text, nullable=True)
    cfop_dentro_uf = Column(Text, nullable=True)
    cfop_fora_uf = Column(Text, nullable=True)
    serie_nfe = Column(Text, nullable=True)
    discrimina_impostos = Column(Integer, default=1)
    cnae_servico = Column(Text, nullable=True)
    cod_servico_municipio = Column(Text, nullable=True)
    aliquota_iss = Column(Float, nullable=True)
    retencao_json = Column(Text, nullable=True)
    municipio_ibge = Column(Text, nullable=True)
    logradouro = Column(Text, nullable=True)
    numero = Column(Text, nullable=True)
    bairro = Column(Text, nullable=True)
    cidade = Column(Text, nullable=True)
    uf = Column(Text, nullable=True)
    cep = Column(Text, nullable=True)
    cert_validade = Column(DateTime, nullable=True)
    cert_cnpj = Column(Text, nullable=True)
    papel_cnpj = Column(Text, nullable=True)
    focus_token_homolog_enc = Column(Text, nullable=True)
    focus_token_prod_enc = Column(Text, nullable=True)
    ambiente_ativo = Column(Text, default="homologacao")
    placeholders_json = Column(Text, nullable=True)
    rede_id = Column(Integer, ForeignKey("redes.id"), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PerfilEmissao(Base):
    """Política: qual Emitente assina cada tipo de documento, por owner (loja|rede).
    Unicidade (owner_tipo, owner_id, tipo_doc) — um único emitente por política (auditoria A12).
    Para DBs existentes, o índice único é criado em `_migrar_colunas`."""
    __tablename__ = "perfil_emissao"
    __table_args__ = (UniqueConstraint("owner_tipo", "owner_id", "tipo_doc", name="uq_perfil_emissao"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo = Column(Text, nullable=False)   # "loja" | "rede"
    owner_id = Column(Integer, nullable=False)
    tipo_doc = Column(Text, nullable=False)      # "produto" | "servico"
    emitente_id = Column(Integer, ForeignKey("emitente.id"), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class DocumentoFiscal(Base):
    """Rastreio de um documento fiscal emitido (NF-e produto / NFS-e serviço via Focus).
    `ref` = idempotência. XML/DANFE ficam em CicloDocumento (etapa 15) referenciados por
    xml_doc_id/danfe_doc_id. `loja_id` = escopo da venda; `emitente_id` = emitente resolvido."""
    __tablename__ = "documento_fiscal"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    ref            = Column(Text, nullable=False, unique=True)
    projeto_nome   = Column(Text, nullable=True)
    tipo_documento = Column(Text, default="produto")   # "produto" | "servico"
    etapa_codigo   = Column(Text, default="15")
    loja_id        = Column(Integer, ForeignKey("lojas.id"), nullable=True)
    emitente_id    = Column(Integer, ForeignKey("emitente.id"), nullable=True)
    status         = Column(Text, nullable=True)
    chave_nfe      = Column(Text, nullable=True)
    numero         = Column(Text, nullable=True)
    serie          = Column(Text, nullable=True)
    mensagem_sefaz = Column(Text, nullable=True)
    erros_json     = Column(Text, nullable=True)
    xml_doc_id     = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    danfe_doc_id   = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    fabrica_doc_id = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    emitido_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Inicialização ─────────────────────────────────────────────────────────────
def init_db():
    """Bootstrap do schema em Postgres: create_all + ADD/DROP COLUMN idempotentes
    (_migrar_colunas_pg) + seed da loja padrão. O caminho SQLite (migrações raw sqlite3
    sobre orizon.db) foi REMOVIDO na faxina 2026-07-23 — banco legado não sobe mais aqui."""
    if ENGINE.dialect.name == "sqlite":
        raise RuntimeError(
            "SQLite foi removido do Orizon (faxina 2026-07-23). Configure DATABASE_URL "
            "para um Postgres (ex.: postgresql+psycopg2://orizon:SENHA@localhost/orizon).")
    Base.metadata.create_all(ENGINE)
    _migrar_colunas_pg()      # ADD COLUMN das colunas novas (create_all não altera existentes)
    _seed_loja_padrao()       # loja seed + backfill de loja_id (idempotente)
    _backfill_funcao_flags()  # liga usa_comissao_vendas na função Consultor de Vendas (idempotente)
    try:
        from auth import perfis
        perfis.recarregar()   # invalida o cache do registro de perfis (perfil_acesso pode ter mudado)
    except Exception:
        pass


def _backfill_funcao_flags():
    """Garante que a função 'Consultor de Vendas' tenha usa_comissao_vendas=1 (motor da Folha e
    identificação do consultor). Idempotente; funções antigas nascidas antes do flag são corrigidas."""
    db = Session()
    try:
        for fn in db.query(Funcao).filter(Funcao.nome.ilike("consultor de vendas")).all():
            if not fn.usa_comissao_vendas:
                fn.usa_comissao_vendas = 1
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()



# ── Loja seed (F1 multi-tenant) ───────────────────────────────────────────────
# Espelha as constantes de mod_contrato.py (evita import circular database<->mod_contrato).
# Os CPFs das testemunhas são placeholders — corrigidos no configurador de lojas (F2).
_SEED_LOJA_NOME   = "INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA"
_SEED_LOJA_CNPJ   = "19.152.134/0001-56"
_SEED_LOJA_CODIGO = "INS"
_SEED_LOJA_TEL    = "(12) 3341-8777"
_SEED_LOJA_EMAIL  = "sac@dalmobilesjc.com.br"
_SEED_TEST1_NOME  = "Jaime Perinazzo"
_SEED_TEST1_CPF   = "xxx.xxx.xxx-xx"
_SEED_TEST2_NOME  = "Felipe Guizalberte"
_SEED_TEST2_CPF   = "yyy.yyy.yyy-yy"

# ── super_admin de bootstrap (F2 multi-tenant) ────────────────────────────────
# Hash SHA-256 igual ao Usuario.set_senha. Senha de exemplo ("trocar123") —
# TROCAR antes de produção. loja_id/rede_id NULL = plataforma.
_SEED_SA_NOME  = "Administrador da Plataforma"
_SEED_SA_LOGIN = "sad2026"
_SEED_SA_SENHA = "trocar123"

# Catálogo padrão de Funções (cargos) — semeado por loja via seed.py (Regras §7/§8).
FUNCOES_PADRAO = [
    "Consultor de Vendas", "Gerente de Vendas", "Gerente Administrativo/Financeiro", "Diretor",
    "Assistente Logístico", "Conferente", "Supervisor de Montagem", "Assistente Administrativo",
    "Projetista Executivo", "Medidor", "Montador", "SAC",
]



def _migrar_colunas_pg():
    """Postgres: ADD/DROP COLUMN idempotentes — `create_all()` não altera tabelas já
    existentes, então toda coluna nova do modelo precisa de uma linha aqui para chegar
    aos bancos já povoados (local, VPS A/B, produção)."""
    stmts = [
        "ALTER TABLE lojas ADD COLUMN IF NOT EXISTS responsavel VARCHAR(120)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS senha_provisoria INTEGER DEFAULT 0",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS atribuicoes_json TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS remuneracao_padrao VARCHAR(20)",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS regime_trabalho VARCHAR(20)",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS regime_contratacao VARCHAR(20)",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS descricao TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS salario_fixo DOUBLE PRECISION",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS beneficios_json TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS comissao_json TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS usa_comissao_vendas INTEGER DEFAULT 0",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS comissao_fixa DOUBLE PRECISION",
        "ALTER TABLE folha_pagamento ADD COLUMN IF NOT EXISTS comissao_fixa DOUBLE PRECISION",
        "ALTER TABLE folha_pagamento ADD COLUMN IF NOT EXISTS base_comissao DOUBLE PRECISION",
        "ALTER TABLE folha_pagamento ADD COLUMN IF NOT EXISTS beneficios DOUBLE PRECISION",
        # projetos_meta: âncoras do cronograma (v11) + equipe + Fatia 2 (medição / venda programada).
        # Um Postgres criado antes destas colunas não as ganha por create_all() — precisa deste ADD.
        "ALTER TABLE projetos_meta ADD COLUMN IF NOT EXISTS data_entrega TIMESTAMP",
        "ALTER TABLE projetos_meta ADD COLUMN IF NOT EXISTS data_inicio TIMESTAMP",
        "ALTER TABLE projetos_meta ADD COLUMN IF NOT EXISTS equipe_json TEXT",
        "ALTER TABLE projetos_meta ADD COLUMN IF NOT EXISTS previsao_medicao TIMESTAMP",
        "ALTER TABLE projetos_meta ADD COLUMN IF NOT EXISTS venda_programada INTEGER DEFAULT 0",
        "ALTER TABLE projetos_meta ADD COLUMN IF NOT EXISTS folga_autorizada INTEGER DEFAULT 0",
        "ALTER TABLE projetos_meta ADD COLUMN IF NOT EXISTS data_limite_contratual TIMESTAMP",
        # ciclo_etapas: data prevista + responsável por função (v11/v12).
        "ALTER TABLE ciclo_etapas ADD COLUMN IF NOT EXISTS data_prevista_conclusao TIMESTAMP",
        "ALTER TABLE ciclo_etapas ADD COLUMN IF NOT EXISTS funcao_responsavel_id INTEGER",
        "ALTER TABLE ciclo_etapas ADD COLUMN IF NOT EXISTS responsavel_funcionario_id INTEGER",
        # Fatia venda da Revisão de PE (2026-07-21): venda do PE + flag Renegociar por ambiente.
        "ALTER TABLE arquivo_pe ADD COLUMN IF NOT EXISTS valor_venda DOUBLE PRECISION",
        "ALTER TABLE pool_ambientes ADD COLUMN IF NOT EXISTS renegociar_pe INTEGER DEFAULT 0",
        # Fatia 3 PE: orçamento de ajuste pós-assinatura.
        "ALTER TABLE orcamentos ADD COLUMN IF NOT EXISTS complemento_pe INTEGER DEFAULT 0",
        # Acordos Financeiros (revisão 2026-07-21): contraparte generalizada.
        "ALTER TABLE acordo_fabrica ADD COLUMN IF NOT EXISTS contraparte_tipo VARCHAR(10) DEFAULT 'fabrica'",
        "ALTER TABLE acordo_fabrica ADD COLUMN IF NOT EXISTS contraparte_nome TEXT",
        "ALTER TABLE acordo_fabrica ADD COLUMN IF NOT EXISTS contraparte_id INTEGER",
        # cadastro completo da contraparte (2026-07-22)
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS cnpj VARCHAR(18)",
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS telefone VARCHAR(20)",
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS email TEXT",
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS cep VARCHAR(9)",
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS logradouro TEXT",
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS numero VARCHAR(20)",
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS complemento TEXT",
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS bairro TEXT",
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS cidade TEXT",
        "ALTER TABLE contraparte_financeira ADD COLUMN IF NOT EXISTS uf VARCHAR(2)",
        # PDV (2026-07-22): loja com mãe. DEFAULT 'loja' backfila as linhas existentes no ADD.
        "ALTER TABLE lojas ADD COLUMN IF NOT EXISTS loja_mae_id INTEGER",
        "ALTER TABLE lojas ADD COLUMN IF NOT EXISTS tipo VARCHAR(12) DEFAULT 'loja'",
        # Faxina Omie (2026-07-23): integração removida do produto — colunas de sync dropadas
        # (decisão do Diretor; o dado era só estado da integração morta).
        # Chat Fatia 2 (2026-07-25): natureza/transferência na mensagem — bases que já têm a
        # tabela da Fatia 1 ganham as colunas novas (create_all não altera tabela existente).
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS natureza VARCHAR(20) DEFAULT 'interacao'",
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS etapa_codigo VARCHAR(10)",
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS transferido_para_funcionario_id INTEGER",
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS documento_ref_id INTEGER",
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS bloqueador INTEGER DEFAULT 0",
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS resolvido_em TIMESTAMP",
        # Chat Fatia 4 (modo privado, 2026-07-25)
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS privada INTEGER DEFAULT 0",
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS corpo_cifrado TEXT",
        "ALTER TABLE clientes DROP COLUMN IF EXISTS omie_codigo",
        "ALTER TABLE clientes DROP COLUMN IF EXISTS omie_sync_status",
        "ALTER TABLE clientes DROP COLUMN IF EXISTS omie_sync_erro",
        "ALTER TABLE clientes DROP COLUMN IF EXISTS omie_sync_at",
    ]
    with ENGINE.begin() as conn:
        for s in stmts:
            conn.exec_driver_sql(s)


def _seed_loja_padrao():
    """Loja seed (dados reais da INSPIRIUM/Dalmóbile) + backfill de loja_id. Idempotente:
    só cria a loja se ainda não existir nenhuma. Chamada pelo init_db()."""
    db = Session()
    try:
        loja = db.query(Loja).order_by(Loja.id).first()
        if loja is None:
            loja = Loja(nome=_SEED_LOJA_NOME, cnpj=_SEED_LOJA_CNPJ, codigo=_SEED_LOJA_CODIGO,
                        telefone=_SEED_LOJA_TEL, email=_SEED_LOJA_EMAIL,
                        testemunha1_nome=_SEED_TEST1_NOME, testemunha1_cpf=_SEED_TEST1_CPF,
                        testemunha2_nome=_SEED_TEST2_NOME, testemunha2_cpf=_SEED_TEST2_CPF,
                        ativo=1)
            db.add(loja)
            db.commit()
        loja_id = loja.id

        # Usuario à parte: super_admin/admin_rede são papéis de plataforma/rede, SEM loja própria
        # por desenho (loja_id NULL de propósito) — não entram no backfill.
        (db.query(Usuario)
           .filter(Usuario.loja_id.is_(None))
           .filter(Usuario.nivel.notin_(("super_admin", "admin_rede")))
           .update({"loja_id": loja_id}, synchronize_session=False))
        for modelo in (Cliente, Projeto, Orcamento, Contrato):
            db.query(modelo).filter(modelo.loja_id.is_(None)).update({"loja_id": loja_id})
        db.commit()

        for p in db.query(Parceiro).all():
            if p.abrangencia is None:
                p.abrangencia = "loja"
            vinculo = db.query(ParceiroLoja).filter_by(parceiro_id=p.id, loja_id=loja_id).first()
            if vinculo is None:
                db.add(ParceiroLoja(parceiro_id=p.id, loja_id=loja_id,
                                    comissao_padrao_pct=p.comissao_padrao_pct or 0.0, ativo=1))
        db.commit()
    finally:
        db.close()


def get_session():
    return Session()


def loja_seed_id(db):
    """Id da loja seed (a 1ª loja por id), ou None se ainda não houver loja."""
    loja = db.query(Loja).order_by(Loja.id).first()
    return loja.id if loja else None


def upsert_projeto_status(nome_safe: str, status: str, perdido_em=None):
    """Cria ou atualiza o registro de status do projeto. Thread-safe via sessão própria."""
    db = get_session()
    try:
        p = db.get(Projeto, nome_safe)
        if not p:
            p = Projeto(nome_safe=nome_safe)
            p.loja_id = loja_seed_id(db)   # F4: nunca criar projeto sem loja (evita 404 fantasma)
            db.add(p)
        antigo_status = p.status
        p.status    = status
        p.status_at = datetime.utcnow()
        if status == "perdido":
            p.perdido_em = perdido_em or datetime.utcnow()
        elif antigo_status == "perdido" and status != "perdido":
            p.perdido_em = None
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def membership_loja_ids(db, usuario_id):
    """IDs das lojas acessíveis do usuário (via usuario_lojas)."""
    rows = (db.query(UsuarioLoja.loja_id)
              .filter(UsuarioLoja.usuario_id == usuario_id).all())
    return [r[0] for r in rows]


def lojas_acessiveis_ids(db, usuario_id, nivel=None, loja_id=None):
    """Memberships do usuário + PDVs da(s) loja(s) dele quando é Diretor (base master).

    Pedido 2026-07-24: o Diretor de uma loja-MÃE acessa o Ponto de Venda como acessa a
    própria loja (seletor multi-loja + X-Loja-Ativa). O acesso é DERIVADO — nada é gravado
    em usuario_lojas, então PDVs novos e diretores novos entram/saem sozinhos. Direção
    ÚNICA: usuário do PDV não ganha a mãe. Demais perfis (gerencial/operador) inalterados."""
    ids = membership_loja_ids(db, usuario_id)
    try:
        from auth import perfis as _perfis   # import local: evita ciclo auth<->database
        eh_diretor = _perfis.base(nivel) == "master"
    except Exception:
        eh_diretor = False
    if eh_diretor:
        proprias = set(ids) | ({loja_id} if loja_id else set())
        if proprias:
            vistos = set(ids)
            pdvs = (db.query(Loja.id)
                      .filter(Loja.loja_mae_id.in_(proprias), Loja.ativo == 1)
                      .order_by(Loja.id).all())
            ids = ids + [p[0] for p in pdvs if p[0] not in vistos]
    return ids


def _backfill_usuario_lojas(cur):
    """Idempotente: cria 1 membership para cada usuário com loja_id e sem vínculo ainda."""
    cur.execute("""
        INSERT INTO usuario_lojas (usuario_id, loja_id)
        SELECT u.id, u.loja_id FROM usuarios u
        WHERE u.loja_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM usuario_lojas ul
                          WHERE ul.usuario_id = u.id AND ul.loja_id = u.loja_id)
    """)
