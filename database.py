"""
database.py — Conexão SQLAlchemy + modelos de dados
Orizon Manager | Dalmóbile
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, ForeignKey, Text, UniqueConstraint, Index, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship, validates
from datetime import datetime
import hashlib
import hmac
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
# pool_size/max_overflow (2026-08-08): o server virou ThreadingHTTPServer (era single-thread,
# uma requisição de cada vez bastava o pool default de 5+10). Sob concorrência real, várias
# requisições pedem sessão ao mesmo tempo — sem folga aqui, a N+1-ésima trava esperando conexão
# livre em vez de dar erro claro.
ENGINE       = create_engine(DATABASE_URL or _URL_PLACEHOLDER, echo=False,
                             pool_pre_ping=True, pool_recycle=1800,
                             pool_size=15, max_overflow=25)
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
    # T-D (27/08/2026, alinhamento de modelos): server_default alinhado ao que
    # _migrar_colunas_pg já grava no banco (ALTER TABLE ... DEFAULT 0) — precisa existir
    # de verdade no Postgres pra backfillar linha antiga direto no ADD COLUMN, não só no
    # INSERT feito pelo ORM (que é tudo que `default=` sozinho garante).
    senha_provisoria = Column(Integer,  default=0, server_default="0")   # 1 = precisa trocar a senha no 1º login
    funcionario_id = Column(Integer,    ForeignKey("funcionarios.id"), nullable=True, index=True)  # RH (Cadastro) que esta conta representa
    # Função (cargo) da CONTA quando não há Funcionário vinculado (Perfil-4 rev2 §2): a coluna Função
    # de Usuários da Loja usa Funcionario.funcao_id se houver vínculo, senão este funcao_id.
    funcao_id     = Column(Integer,     ForeignKey("funcoes.id"), nullable=True, index=True)
    tema          = Column(String(10),  default="escuro")   # 'claro' | 'escuro'
    # Orizon Chat Fatia 6 (ponte WhatsApp): quando notificar o usuário no WhatsApp da empresa.
    # T-D (27/08/2026): mesmo motivo do server_default de senha_provisoria, acima.
    notificar_whatsapp = Column(String(16), default="quando_offline", server_default="quando_offline")  # sempre|quando_offline|nunca
    criado_em     = Column(DateTime,    default=datetime.utcnow)
    loja_id       = Column(Integer,     ForeignKey("lojas.id"), nullable=True, index=True)  # usuário de loja
    rede_id       = Column(Integer,     ForeignKey("redes.id"), nullable=True, index=True)  # admin de rede (loja_id NULL)
    # Permissões por CONTA (2026-08-08) — só admin_rede: PerfilAcesso é por LOJA (loja_id
    # nullable=False), então não serve pra Gestor de Rede (sem loja própria). NULL = usa os
    # padrões do nível (auth.perfis.PERFIS["admin_rede"]); {} ou dict parcial = overrides,
    # só nas capacidades da allowlist (auth.perfis.CAPACIDADES_OVERRIDAVEIS_REDE — não inclui
    # gerir_redes/gerir_lojas, que definem a IDENTIDADE de admin_rede pra mod_tenancy). Master
    # usa o mecanismo que já existe (slug próprio em PerfilAcesso, por loja); super_admin é
    # sempre pleno (god-mode, perfis.pode() nunca olha override pra esse nível).
    capacidades_override_json = Column(Text, nullable=True)

    sessoes       = relationship("Sessao",          back_populates="usuario", cascade="all, delete-orphan")
    autorizacoes  = relationship("LogAutorizacao",  back_populates="autorizador", foreign_keys="LogAutorizacao.autorizador_id")

    def set_senha(self, senha: str):
        self.senha_hash = _hash_senha(senha)

    def check_senha(self, senha: str) -> bool:
        # hmac.compare_digest (tempo constante) em vez de == — achado de auditoria 2026-08-13,
        # defesa em profundidade (timing attack remoto sobre SHA-256 de 32 bytes é impraticável
        # dado o jitter de rede, mas a troca é grátis e correta).
        return hmac.compare_digest(self.senha_hash or "", _hash_senha(senha))

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


class SimuladorAutorizacao(Base):
    """Autorização por loja (LGPD) pro Simulador de Modelo de Negócios acessar dados sigilosos da
    loja (folha, salários, margens, dívida) — Sessão 185/187. Fluxo REMOTO (rev2, achado do
    usuário: a concessão original pedia a senha do Master DENTRO da tela do solicitante — só
    funcionava com os dois juntos): o super_admin SOLICITA (`status='pendente'`, sem senha
    nenhuma); o Master vê o pedido na PRÓPRIA sessão (aba Privacidade/Config) e aprova reautenticando
    a PRÓPRIA senha (padrão step-up de auto-confirmação, não a de terceiro) — pode acontecer em
    qualquer lugar, em qualquer momento, sem os dois precisarem estar juntos. No máximo UMA linha
    `status IN ('pendente','ativa')` por loja (invariante de aplicação, checado em
    mod_simulador_autorizacao — reconceder após revogação cria uma linha NOVA, preservando o
    histórico da revogada). Revogável a qualquer momento pelo Master, efeito imediato."""
    __tablename__ = "simulador_autorizacoes"

    id                       = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id                  = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)
    status                   = Column(String(10), nullable=False, default="ativa")   # pendente | ativa | revogada
    solicitado_por_usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)  # quem pediu (super_admin)
    solicitado_em            = Column(DateTime, nullable=True)
    concedido_por_usuario_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)   # Master (NULL = seed)
    beneficiario             = Column(String(40), nullable=False, default="orizon_assessoria")
    escopo                   = Column(String(40), nullable=False, default="simulacao_leitura")
    base_legal               = Column(Text,     nullable=True)   # texto do termo aceito
    concedido_em             = Column(DateTime, nullable=True)
    revogado_em              = Column(DateTime, nullable=True)
    ip                       = Column(String(64), nullable=True)
    criado_em                = Column(DateTime, default=datetime.utcnow)


class SimuladorLogAcesso(Base):
    """Trilha de auditoria PRÓPRIA do Simulador (RF-04) — fora do log operacional: concessão,
    revogação e cada abertura/levantamento de dados de uma loja pelo Simulador."""
    __tablename__ = "simulador_log_acessos"

    id         = Column(Integer,  primary_key=True, autoincrement=True)
    evento     = Column(String(20), nullable=False)   # concessao | revogacao | abertura | levantamento
    usuario_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    loja_id    = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
    contexto   = Column(Text,     nullable=True)
    ip         = Column(String(64), nullable=True)
    criado_em  = Column(DateTime, default=datetime.utcnow)


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
    loja_id       = Column(Integer,     ForeignKey("lojas.id"), nullable=True, index=True)


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
    rede_id             = Column(Integer,      ForeignKey("redes.id"), nullable=True, index=True)
    abrangencia         = Column(String(10),   default="loja")   # loja | rede
    pix                 = Column(String(140),  nullable=True)    # chave PIX p/ pagamento de comissão (v10)


class Funcao(Base):
    """Tabela de Funções (Modulos_Orizon_v10, Config): catálogo único de funções/cargos referenciado
    por Funcionário.funcao_id e Terceiro.funcao_id — substitui texto livre / listas separadas."""
    __tablename__ = "funcoes"

    id        = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id   = Column(Integer,     ForeignKey("lojas.id"), nullable=True, index=True)
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
    usa_comissao_vendas = Column(Integer, default=0, server_default="0")       # 1 = comissão vem do comissao_vendas da loja (Consultor)
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
    loja_id        = Column(Integer,     ForeignKey("lojas.id"), nullable=True, index=True)
    funcionario_id = Column(Integer,     ForeignKey("funcionarios.id"), nullable=False, index=True)
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
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
    funcionario_id = Column(Integer,  ForeignKey("funcionarios.id"), nullable=False, index=True)
    competencia    = Column(String(7), nullable=False)          # 'AAAA-MM' = mês de concluido_em
    origem         = Column(String(10), nullable=False, default="papel")  # papel | venda
    papel          = Column(String(30), nullable=True)          # projeto_executivo|medicao|montagem|assistencia|venda
    projeto_nome   = Column(Text,     nullable=True)            # nome_safe (rastreabilidade)
    etapa_codigo   = Column(String(8), nullable=True)           # etapa que disparou (papel); NULL p/ venda
    base           = Column(Float,    nullable=True, default=0.0)   # Σ order_total dos ambientes (ou vendas líq.)
    base_ajustada  = Column(Float,    nullable=True)            # override manual da base (venda: valor líquido ajustado)
    pct            = Column(Float,    nullable=True, default=0.0)
    pct_ajustado   = Column(Float,    nullable=True)            # override manual do % (gerente, no ato do pagamento)
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
    loja_id           = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
    funcionario_id    = Column(Integer,  ForeignKey("funcionarios.id"), nullable=False, index=True)
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
    loja_id            = Column(Integer,     ForeignKey("lojas.id"), nullable=True, index=True)
    nome               = Column(String(150), nullable=False)
    cpf                = Column(String(20),  nullable=True)
    telefone           = Column(String(20),  nullable=True)
    email              = Column(String(120), nullable=True)
    cargo              = Column(String(80),  nullable=True)   # legado (texto) — ver funcao_id
    funcao_id          = Column(Integer,     ForeignKey("funcoes.id"), nullable=True, index=True)  # → Tabela de Funções (v10)
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
    # use_alter: fecha ciclo com Usuario.funcionario_id (1:1 modelado nos dois lados — ver
    # nota "divida de Onda 2" em CLAUDE.md). Sem use_alter, um schema do zero (baseline
    # Alembic) nao consegue decidir se funcionarios ou usuarios entra primeiro.
    usuario_id         = Column(Integer,     ForeignKey("usuarios.id", use_alter=True), nullable=True)  # conta de login (se houver)
    criado_em          = Column(DateTime,    default=datetime.utcnow)


class Fornecedor(Base):
    """Fornecedor PJ/PF (Modulos_Orizon_v9). Referenciado por 'Fornecedores a Pagar' (Financeiro 2.1)."""
    __tablename__ = "fornecedores"

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id         = Column(Integer,     ForeignKey("lojas.id"), nullable=True, index=True)
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
    loja_id         = Column(Integer,     ForeignKey("lojas.id"), nullable=True, index=True)
    nome            = Column(String(150), nullable=False)
    cpf             = Column(String(20),  nullable=True)
    cnpj            = Column(String(18),  nullable=True)   # contratação via MEI (achado do usuário 2026-08-17)
    telefone        = Column(String(20),  nullable=True)
    tipo_servico    = Column(String(20),  nullable=True)   # legado — ver funcao_id
    funcao_id       = Column(Integer,     ForeignKey("funcoes.id"), nullable=True, index=True)  # → Tabela de Funções (v10)
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
    # use_alter: fecha ciclo com Emitente.rede_id. Esta coluna esta 100% nula no banco
    # (auditoria Dia 0) — e' a metade nao usada do ciclo (ver "divida de Onda 2" em
    # CLAUDE.md). Sem use_alter, um schema do zero nao consegue ordenar redes x emitente.
    emitente_central_id = Column(Integer, ForeignKey("emitente.id", use_alter=True), nullable=True, index=True)
    ativo     = Column(Integer,     default=1)
    criado_em = Column(DateTime,    default=datetime.utcnow)


class Loja(Base):
    """Loja (tenant). Pertence a uma rede ou é avulsa (rede_id NULL)."""
    __tablename__ = "lojas"

    id          = Column(Integer,     primary_key=True, autoincrement=True)
    rede_id     = Column(Integer,     ForeignKey("redes.id"), nullable=True, index=True)  # NULL = avulsa
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
    # E-mail das testemunhas (achado do usuário 2026-08-17): só existiam nome+CPF, pro contrato
    # impresso — a assinatura digital (ClickSign) precisa de e-mail pra cadastrar a testemunha
    # como signatária. Opcional: sem e-mail, a testemunha simplesmente não entra no envelope.
    testemunha1_email = Column(String(150), nullable=True)
    testemunha2_email = Column(String(150), nullable=True)
    emitente_id = Column(Integer, ForeignKey("emitente.id"), nullable=True, index=True)
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
    loja_mae_id = Column(Integer, ForeignKey("lojas.id", ondelete="RESTRICT", onupdate="CASCADE", name="fk_lojas_loja_mae_id"), nullable=True, index=True)
    tipo        = Column(String(12), nullable=False, default="loja", server_default="loja")   # loja | ponto_venda
    # Logo própria da loja (2026-08-20): só o NOME do arquivo em logos_loja/<id>/ — mesmo
    # esquema de nome de mod_documentos.guardar_staging (sha256[:16] + extensão). NULL/"" =
    # sem logo própria, cai no logo_dalmobile.png padrão (mod_contrato._resolver_logo_src).
    logo_arquivo = Column(String(80), nullable=True)


class ParceiroLoja(Base):
    """Vínculo M:N parceiro × loja, com comissão própria por loja."""
    __tablename__ = "parceiro_lojas"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    parceiro_id         = Column(Integer, ForeignKey("parceiros.id"), nullable=False, index=True)
    loja_id             = Column(Integer, ForeignKey("lojas.id"),     nullable=False, index=True)
    comissao_padrao_pct = Column(Float,   default=0.0)
    ativo               = Column(Integer, default=1)


class UsuarioLoja(Base):
    """Vínculo M:N usuário × loja (lojas acessíveis). loja_id em usuarios = loja primária/default."""
    __tablename__ = "usuario_lojas"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    loja_id    = Column(Integer, ForeignKey("lojas.id"),    nullable=False, index=True)

    __table_args__ = (UniqueConstraint("usuario_id", "loja_id", name="uq_usuario_loja"),)


class Projeto(Base):
    """Metadados de pipeline por projeto. nome_safe é a chave natural (nome da pasta)."""
    __tablename__ = "projetos_meta"

    nome_safe  = Column(String,   primary_key=True)
    cliente_id = Column(Integer,  ForeignKey("clientes.id"), nullable=True, index=True)
    # quente | morno | frio | convertido | perdido | cancelado | em_revisao (revisado 2026-08-17:
    # cancelamento leve, pré-2ª-assinatura, tem 2 desfechos escolhidos pelo gerente — "cancelado"
    # trava tudo (ver _contrato_assinado); "em_revisao" reabre a negociação, comportamento antigo
    # com rótulo honesto — não é mais rotulado "cancelado" por engano).
    status     = Column(String(20), nullable=True)
    status_at  = Column(DateTime,   nullable=True)
    perdido_em     = Column(DateTime,   nullable=True)
    # Trava PERMANENTE: só é setada quando o contrato já tinha as 2 assinaturas (provisões já
    # constituídas) e foi cancelado depois disso — "revender" exige projeto novo, nunca reabre.
    # status="cancelado" sozinho também trava (ver `_projeto_cancelado`/`_contrato_assinado` em
    # main.py), mas não é permanente como este flag; "Reabrir Orçamentos" é frente futura. Uma vez
    # 1, nunca volta a 0 — nem um novo contrato no mesmo projeto reabre a edição.
    cancelado_definitivo = Column(Integer, default=0, server_default="0")
    parametros_json = Column(Text, nullable=True)   # parâmetros estruturais da negociação (JSON, projeto-wide)
    loja_id        = Column(Integer,    ForeignKey("lojas.id"), nullable=True, index=True)
    criado_por_id  = Column(Integer,    ForeignKey("usuarios.id"), nullable=True)   # usuário que criou o projeto (escopo por projetista)
    data_entrega   = Column(DateTime,   nullable=True)   # âncora do cronograma REGRESSIVO (entrega ao cliente, def. na assinatura)
    data_inicio    = Column(DateTime,   nullable=True)   # âncora do cronograma PROGRESSIVO (início; def. assinatura + carência)
    equipe_json    = Column(Text,       nullable=True)   # Equipe do Projeto: seleções dos papéis SELETORES (medidor/finalizador/montagem[N])
    previsao_medicao = Column(DateTime, nullable=True)   # marco de medição (venda programada / obra do cliente)
    venda_programada = Column(Integer,  default=0, server_default="0")        # 1 = obra do cliente controla a medição (classificação + marcador no contrato, Fatia 3)
    folga_autorizada = Column(Integer,  default=0, server_default="0")        # 1 = data de entrega gravada apesar de folga NEGATIVA, sob autorização gerencial (Fatia 2)
    data_limite_contratual = Column(DateTime, nullable=True)  # D0 (assinatura) + prazo contratual em DIAS ÚTEIS — registrada na assinatura (Fatia 3)


class Briefing(Base):
    __tablename__ = "briefings"

    id                    = Column(Integer,  primary_key=True, autoincrement=True)
    cliente_id            = Column(Integer,  ForeignKey("clientes.id"), nullable=False, index=True)
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
    renegociar_pe         = Column(Integer, default=0, server_default="0")   # Revisão de PE (11c): ambiente marcado p/ renegociar (Fatia venda 2026-07-21)
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
    complemento_pe           = Column(Integer, default=0, server_default="0")
    # Conciliação de PE/AF2 (spec 2026-08-14): generaliza o Complemento de "1 por projeto inteiro"
    # pra "1 por FASE" — o desmembramento libera fases independentemente, a cobrança acompanha.
    # NULL = projeto não desmembrado (fase única implícita, todo o pool).
    # use_alter: fecha ciclo com ParcelaProjeto.orcamento_id, que ja existia antes desta
    # coluna (criada pela migration 0002 — o ciclo se fechou aqui, nao do outro lado; ver
    # "divida de Onda 2" em CLAUDE.md). Sem use_alter, um schema do zero nao consegue
    # ordenar orcamentos x parcela_projeto.
    parcela_id      = Column(Integer,  ForeignKey("parcela_projeto.id", ondelete="RESTRICT", onupdate="CASCADE", use_alter=True, name="fk_orcamentos_parcela_id"), nullable=True, index=True)
    created_by      = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, nullable=True)
    loja_id         = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)

    criador   = relationship("Usuario", foreign_keys=[created_by])
    ambientes = relationship("OrcamentoAmbiente", back_populates="orcamento",
                             cascade="all, delete-orphan")


class OrcamentoAmbiente(Base):
    """Relação N:N entre orçamento e ambiente do pool."""
    __tablename__ = "orcamento_ambientes"

    orcamento_id     = Column(Integer, ForeignKey("orcamentos.id"),     primary_key=True)
    pool_ambiente_id = Column(Integer, ForeignKey("pool_ambientes.id"), primary_key=True, index=True)
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
    # Fonte única da equipe (2026-07-27): o responsável da etapa pode ser um TERCEIRO (montador/
    # medidor/PE terceirizados). Exatamente um dos dois responsáveis fica preenchido.
    responsavel_terceiro_id     = Column(Integer, ForeignKey("terceiros.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_ciclo_etapas_responsavel_terceiro_id"), nullable=True, index=True)
    observacoes    = Column(Text,     nullable=True)
    # Transferência de responsabilidade (2026-08-23): ciclo de vida 'nenhuma' → 'pendente'
    # (destino tem login, aguarda aceite via "Receber Projeto") ou direto 'nenhuma' de novo
    # (destino sem login — aceite automático, ninguém pra confirmar). Exatamente um dos dois
    # campos de destino fica preenchido, igual ao par responsavel_funcionario_id/_terceiro_id.
    transferencia_status                    = Column(Text, nullable=False, default="nenhuma", server_default="nenhuma")
    transferencia_destino_funcionario_id    = Column(Integer, ForeignKey("funcionarios.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_ciclo_etapas_transferencia_destino_funcionario_id"), nullable=True, index=True)
    transferencia_destino_terceiro_id       = Column(Integer, ForeignKey("terceiros.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_ciclo_etapas_transferencia_destino_terceiro_id"), nullable=True, index=True)
    transferencia_solicitada_por_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_ciclo_etapas_transferencia_solicitada_por_usuario_id"), nullable=True, index=True)
    transferencia_solicitada_em             = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("projeto_nome", "etapa_codigo", name="uq_ciclo_etapa"),
        # C3 (27/08/2026, alinhamento de modelos): índice antigo, nome fora da convenção
        # ix_<tabela>_<coluna> (falta o "_id") — a 0003 nunca recriou porque
        # responsavel_funcionario_id não estava na lista das 147 FKs sem índice do Dia 0.
        Index("ix_ciclo_etapas_responsavel_funcionario", "responsavel_funcionario_id"),
        # Parciais (WHERE transferencia_status='pendente') — servem à consulta de transferências
        # pendentes; não substituem os índices completos das FKs (ix_ciclo_etapas_transferencia_
        # destino_funcionario_id/_terceiro_id, criados pela 0002 ao lado destes).
        Index("ix_ciclo_etapas_transf_dest_func", "transferencia_destino_funcionario_id",
              postgresql_where=text("transferencia_status = 'pendente'")),
        Index("ix_ciclo_etapas_transf_dest_terc", "transferencia_destino_terceiro_id",
              postgresql_where=text("transferencia_status = 'pendente'")),
    )

    responsavel = relationship("Usuario", foreign_keys=[responsavel_id])


class AtribuicaoAmbiente(Base):
    """Mapa de Atribuições (Regras_Funcoes_Perfis_Atribuicoes §4/§5): quem executa cada papel
    operacional (PE/Medição/Montagem/Assistência) por ambiente do projeto. A atribuição CONCEDE
    visibilidade escopada ao Usuário vinculado ao profissional. pool_ambiente_id NULL = 'projeto
    inteiro' (default que vale para os ambientes sem atribuição própria). PE/Medição/Assistência
    seguem 1 profissional por papel/ambiente; **Montagem aceita VÁRIOS** (2026-08-06, pedido do
    usuário — times de montagem podem ter 2+ pessoas) — por isso a unicidade não é uma
    UniqueConstraint comum: é um ÍNDICE ÚNICO PARCIAL só sobre `papel <> 'montagem'`
    (`uq_atribuicao_papel_ambiente`, em __table_args__ abaixo — C3, 27/08/2026: SQLAlchemy EXPRESSA
    isso sim, via Index(unique=True, postgresql_where=...); a nota anterior aqui dizia o contrário
    e a constraint viveu anos só em _migrar_colunas_pg, invisível pro autogenerate). Trocas ficam
    em LogAcaoGerencial (sem versionar a tabela)."""
    __tablename__ = "atribuicoes_ambiente"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id          = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)   # isolamento F4
    projeto_nome     = Column(Text,     nullable=False)                            # nome_safe
    pool_ambiente_id = Column(Integer,  ForeignKey("pool_ambientes.id"), nullable=True, index=True)  # NULL = projeto inteiro
    papel            = Column(Text,     nullable=False)   # projeto_executivo|medicao|montagem|assistencia
    funcionario_id   = Column(Integer,  ForeignKey("funcionarios.id"), nullable=True, index=True)
    terceiro_id      = Column(Integer,  ForeignKey("terceiros.id"), nullable=True, index=True)
    atribuido_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    criado_em        = Column(DateTime, default=datetime.utcnow)
    atualizado_em    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("uq_atribuicao_papel_ambiente", "projeto_nome", "pool_ambiente_id", "papel",
              unique=True, postgresql_where=text("papel <> 'montagem'")),
    )


class CicloLogistico(Base):
    """Expedição (Modulos_Orizon_v5, módulo 7): pedido produzido -> cliente com o produto.
    Estado AGREGADO + referências por ID a Projetos/Estoque/Fiscal — NUNCA duplica dado.
    Prazos (planejado) entram uma vez na criação; datas (realizado) são capturadas ao mover o card."""
    __tablename__ = "ciclo_logistico"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
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
    nfe_id         = Column(Integer, ForeignKey("documento_fiscal.id"), nullable=True, index=True)
    criado_em      = Column(DateTime, nullable=True)
    criado_por_id  = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    # Desmembramento parcial (spec 2026-07-13, Fatia 2): 1 linha por parcela; NULL = projeto-wide legado.
    parcela_id     = Column(Integer,  ForeignKey("parcela_projeto.id"), nullable=True, index=True)


class CicloLogisticoTransicao(Base):
    """Histórico auditável de mudanças de status_atual do CicloLogistico (quem/quando)."""
    __tablename__ = "ciclo_logistico_transicao"

    id                 = Column(Integer,  primary_key=True, autoincrement=True)
    ciclo_logistico_id = Column(Integer,  ForeignKey("ciclo_logistico.id"), nullable=False, index=True)
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
    orcamento_id          = Column(Integer,  ForeignKey("orcamentos.id"), nullable=True, index=True)
    saldo_margem_estimado = Column(Float,    nullable=True)   # cache opcional do derivado (#9)
    criado_em             = Column(DateTime, default=datetime.utcnow)
    criado_por_id         = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    prazo_conclusao       = Column(DateTime, nullable=True)   # Fase A: prazo da fase (validado × cronograma)
    # Previsões pedidas no desmembramento/retenção (2026-08-02): quando a fase pode PROSSEGUIR
    # (obra libera) e a NOVA previsão de entrega da fase (antes do card de expedição existir).
    liberacao_prevista    = Column(Date, nullable=True)
    entrega_prevista      = Column(Date, nullable=True)
    # Agenda Fatia 1 (spec 2026-08-03 §4): Val_Liq da fase (VAVO−Cust_Ad rateado por ambiente,
    # base das comissões e da Agenda) CONGELADO na criação — como o Val_Cont, não se recalcula
    # (a proporção VAVO/Cust_Ad do projeto pode mudar depois). NULL = legado pendente de
    # backfill (main._backfill_val_liq_fases roda no start, idempotente).
    val_liq_congelado     = Column(Float, nullable=True)


class ParcelaAmbiente(Base):
    """Membership N:N parcela ↔ ambiente do pool (#1)."""
    __tablename__ = "parcela_ambiente"
    parcela_id       = Column(Integer, ForeignKey("parcela_projeto.id"), primary_key=True)
    pool_ambiente_id = Column(Integer, ForeignKey("pool_ambientes.id"),  primary_key=True, index=True)
    # Valor de contrato BRUTO do ambiente (Val_Cont rateado, não o CFO — #4/#5). Guardado na
    # confirmação p/ permitir SPLIT exato na liberação em ondas (Fatia 3) sem reler o contrato.
    valor_ambiente   = Column(Float, nullable=False, default=0.0, server_default="0.0")


class ConciliacaoPeFase(Base):
    """Decisão de conciliação de Custo de Fábrica do PE na AF2 (11d), por ambiente dentro de uma
    fase (spec 2026-08-14). Tabela ISOLADA — não mexe em CicloEtapa/ProvisaoRegistro (usados
    também pela AF1); a conclusão de "11d" faz uma checagem DERIVADA sobre esta tabela, não uma
    coluna nova nelas. `parcela_id` NULL = projeto não desmembrado (fase única implícita)."""
    __tablename__ = "conciliacao_pe_fase"
    id                     = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome           = Column(Text,     nullable=False, index=True)   # nome_safe
    parcela_id             = Column(Integer,  ForeignKey("parcela_projeto.id"), nullable=True, index=True)
    pool_ambiente_id       = Column(Integer,  ForeignKey("pool_ambientes.id"), nullable=False, index=True)
    tipo_decisao           = Column(String(16), nullable=False)   # manter|absorver|cobrar|estornar
    diferenca_cfo          = Column(Float,    nullable=False, default=0.0)
    diferenca_valor_contrato = Column(Float,  nullable=False, default=0.0)
    valor_aprovado         = Column(Float,    nullable=False, default=0.0)   # editável (Estornar)
    aprovador_id           = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    aprovado_em            = Column(DateTime, default=datetime.utcnow)
    criado_em              = Column(DateTime, default=datetime.utcnow)


class SinalRetido(Base):
    """Desmembramento OPERACIONAL (Fatia 1, spec 2026-07-27): o MEDIDOR sinaliza que um ambiente está
    RETIDO pela obra. Por AMBIENTE. A gerência CONFIRMA → vira parcela retida (`confirmado=1`)."""
    __tablename__ = "sinal_retido"
    id                = Column(Integer, primary_key=True, autoincrement=True)
    projeto_nome      = Column(Text,    nullable=False, index=True)
    pool_ambiente_id  = Column(Integer, ForeignKey("pool_ambientes.id"), nullable=False, index=True)
    sinalizado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    motivo            = Column(Text,    nullable=True)
    confirmado        = Column(Integer, nullable=False, default=0)
    criado_em         = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("projeto_nome", "pool_ambiente_id", name="uq_sinal_retido"),)


class RetencaoObra(Base):
    """Registro HISTÓRICO de cada EVENTO de retenção por obra (decisão 2026-08-02): a retenção
    pode ser acionada em qualquer etapa entre a Solicitação de Medição e a Montagem, e VÁRIAS
    vezes. Cada evento grava quando foi, em qual fase do ciclo (etapa_codigo), quais ambientes,
    o motivo e a data prevista de liberação. `liberado_em` é estampado quando TODOS os ambientes
    do evento saem de fase retida (liberação em ondas conta pela última)."""
    __tablename__ = "retencao_obra"
    id                  = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome        = Column(Text,     nullable=False, index=True)
    etapa_codigo        = Column(Text,     nullable=True)    # fase do CICLO onde foi acionada (9/10/11…/17)
    # rev 2026-08-03 (auditoria): motivo_tipo = catálogo (mod_retido.MOTIVOS_RETENCAO);
    # motivo = descrição livre do fato. A retenção é POR AMBIENTE (ambientes_json) — decisão
    # do usuário: fase NÃO entra no registro (desmembramentos posteriores mudariam o retrato).
    motivo_tipo         = Column(Text,     nullable=True)
    motivo              = Column(Text,     nullable=True)
    liberacao_prevista  = Column(Date,     nullable=True)
    ambientes_json      = Column(Text,     nullable=False, default="[]")   # [pool_ambiente_id, ...]
    criado_em           = Column(DateTime, default=datetime.utcnow)
    criado_por_id       = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    liberado_em         = Column(DateTime, nullable=True)
    liberado_por_id     = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)


class ArquivoPE(Base):
    """XML/Promob do Projeto Executivo — FORA do pool do orçamento (decisão #2). Documento de
    comparação/liquidação: NÃO cria PoolAmbiente, NÃO vincula a orçamento, NÃO alimenta o motor →
    não esbarra na trava `_contrato_assinado`. `valor_atualizado` = CFO/custo de fábrica extraído do
    XML (Σ order_total), NÃO valor de venda (#4)."""
    __tablename__ = "arquivo_pe"
    id               = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome     = Column(Text,     nullable=False, index=True)   # nome_safe
    pool_ambiente_id = Column(Integer,  ForeignKey("pool_ambientes.id"), nullable=False, index=True)  # a qual ambiente o PE se refere
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
    este DERIVADO do motivo. Realizar o caso dispara o lançamento contábil conforme o tipo de custo.
    **Agendamento (2026-08-06):** `pool_ambiente_id`+`data_inicio`+`data_fim` tiram a Assistência do
    Mapa de Atribuições (papel `assistencia` foi removido de `mod_escopo.PAPEIS`) — cada CASO agora
    carrega sua própria janela e ambiente, com Gantt próprio (ver `mod_agenda.itens_assistencia`).
    Um mesmo ambiente pode ter vários casos ao longo do tempo, cada um com equipe/janela distintas —
    por isso não reaproveita `AtribuicaoAmbiente` (que é por ambiente+papel, não por caso)."""
    __tablename__ = "assistencia_caso"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
    projeto_nome   = Column(Text,     nullable=True)                 # ref: nome_safe (opcional)
    pool_ambiente_id = Column(Integer, ForeignKey("pool_ambientes.id", ondelete="RESTRICT", onupdate="CASCADE", name="fk_assistencia_caso_pool_ambiente_id"), nullable=True, index=True)
    data_inicio    = Column(Date,     nullable=True)
    data_fim       = Column(Date,     nullable=True)
    sub_tipo       = Column(Text,     nullable=False)                # "montagem" | "pos_conclusao"
    motivo         = Column(Text,     nullable=False)                # chave de mod_assistencias.MOTIVOS
    tipo_custo     = Column(Text,     nullable=False)                # "paga" | "loja" | "fabrica" (derivado)
    descricao      = Column(Text,     nullable=True)
    valor          = Column(Float,    nullable=True)                 # custo do reparo / valor da venda
    status         = Column(Text,     nullable=False, default="aberto")   # aberto | realizado
    reembolsado_fabrica = Column(Integer, nullable=True)             # fase 2: fábrica reembolsou de fato
    ref_lancamento = Column(Text,     nullable=True)                 # ref idempotente do lançamento
    # 2026-08-07 (achado da Vera + revisão do usuário): "direto" = paga na hora (Caixa); "a_prazo" =
    # faturado por terceiro, cria Fornecedores a Pagar. Substitui o "Efetivar" genérico da
    # Reconciliação pra Assistência/Garantia (que arriscava duplo-lançamento do mesmo evento real).
    forma_pagamento = Column(Text,    nullable=False, default="direto", server_default="direto")   # "direto" | "a_prazo"
    # só relevante pra caso AVULSO (sem projeto) e NÃO cobrado (tipo_custo loja/fabrica): a provisão
    # é uma média estatística por projeto — sem projeto não tem o que debitar. "garantia" = despesa
    # normal (5.2.12/5.2.13); "concessao" = fora da cobertura, cortesia (5.3.21).
    classificacao_avulsa = Column(Text, nullable=True)                # "garantia" | "concessao"
    criado_em      = Column(DateTime, nullable=True)
    realizado_em   = Column(DateTime, nullable=True)
    criado_por_id  = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)


class AssistenciaExecutor(Base):
    """Equipe de UM caso de assistência (0..N — mesmo padrão do Montagem multi-executor, mas por
    CASO, não por ambiente: dois casos no mesmo ambiente podem ter equipes diferentes)."""
    __tablename__ = "assistencia_executores"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    caso_id        = Column(Integer, ForeignKey("assistencia_caso.id"), nullable=False, index=True)
    funcionario_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True, index=True)
    terceiro_id    = Column(Integer, ForeignKey("terceiros.id"), nullable=True, index=True)


class AssistenciaAnexo(Base):
    """Arquivo anexado a um caso de assistência. Append-only (mesmo padrão de CicloDocumento)."""
    __tablename__ = "assistencia_anexos"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    caso_id        = Column(Integer,  ForeignKey("assistencia_caso.id"), nullable=False, index=True)
    arquivo_path   = Column(Text,     nullable=False)   # relativo a PROJETOS/<nome>/
    nome_original  = Column(Text,     nullable=False)
    enviado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    enviado_em     = Column(DateTime, nullable=False, default=datetime.utcnow)


class Recebivel(Base):
    """Recebível de venda (2026-08-07, achado da Vera): `1.1.02 Contas a Receber` nasce cheia no
    contrato (`registro_venda_contrato`) mas nunca era baixada — nada disparava o evento
    `recebimento_venda`. Cada linha aqui é uma entrada de caixa PREVISTA (entrada, parcela ou o lote
    financiado por Cartão/Aymoré) — materializada uma vez na geração do contrato
    (`mod_recebiveis.materializar`), confirmada manualmente (mesmo padrão de `efetivar_provisao`) via
    `mod_contabil.registrar_recebimento_venda`, que capa ao saldo real em aberto de `1.1.02` — protege
    o razão mesmo quando `valor_previsto` é só uma estimativa de face (caso do Parcelamento Loja, antigo Total Flex, que mistura
    capital+juros na parcela; a apropriação do juros em si é separada, `apropriar_juros_loja`)."""
    __tablename__ = "recebivel"

    id                = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id           = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)
    projeto_nome      = Column(Text,     nullable=False)
    orcamento_id      = Column(Integer,  ForeignKey("orcamentos.id"), nullable=False, index=True)
    tipo              = Column(Text,     nullable=False)   # "entrada" | "parcela" | "financiado"
    numero            = Column(Integer,  nullable=True)     # nº da parcela, quando aplicável
    forma             = Column(Text,     nullable=True)     # instrumento informativo (pix/boleto/cartao/aymore/...)
    valor_previsto    = Column(Float,    nullable=False)
    data_prevista     = Column(Date,     nullable=False)
    status            = Column(Text,     nullable=False, default="previsto")   # "previsto" | "confirmado" | "duvidoso"
    valor_confirmado  = Column(Float,    nullable=True)
    confirmado_em     = Column(Date,     nullable=True)
    confirmado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    # Não-recebimento (2026-08-07): reclassificado pra "Recebíveis Duvidosos" (1.1.10) — ainda pode
    # ser confirmado depois (o dinheiro pode chegar), só sai de Contas a Receber "normal".
    duvidoso_em       = Column(Date,     nullable=True)
    ref               = Column(Text,     nullable=False, unique=True)   # idempotência do lançamento
    criado_em         = Column(DateTime, nullable=False, default=datetime.utcnow)


class ProvisaoDataPrevista(Base):
    """Data prevista de efetivação de uma provisão (2026-08-07, pedido do usuário — mesma ideia do
    Recebível, aplicada às provisões). NÃO é lançamento contábil — é só agenda/lembrete: uma provisão
    (`mod_contabil.reconciliacao`) é computada NA HORA a partir do razão, não é uma linha persistida,
    então essa data não tem onde morar dentro do motor contábil. Só faz sentido POR PROJETO (agregar
    a data entre vários projetos não tem sentido) — upsert por (projeto_nome, codigo_conta)."""
    __tablename__ = "provisao_data_prevista"

    id                = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id           = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)
    projeto_nome      = Column(Text,     nullable=False)
    codigo_conta      = Column(Text,     nullable=False)
    data_prevista     = Column(Date,     nullable=False)
    atualizado_em     = Column(DateTime, nullable=False, default=datetime.utcnow)
    atualizado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)

    __table_args__ = (UniqueConstraint("projeto_nome", "codigo_conta", name="uq_provisao_data_prevista"),)


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
    por_id       = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
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
    pai_id     = Column(Integer, ForeignKey("conta.id"), nullable=True, index=True)
    ativa      = Column(Integer, default=1)
    ordem      = Column(Integer, default=0)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Centro de Custo/Natureza (2026-08-08): duas etiquetas independentes, só usadas nas contas do
    # grupo 5 (Despesas/Custos). centro_custo_id aponta pra CentroCusto (árvore própria, mesmo
    # owner). natureza_custo é um slug fixo (ver NATUREZA_CUSTO em mod_contabil.py) — não precisa
    # de tabela, é lista fechada de 3. Nome deliberadamente diferente de `natureza` (devedora/
    # credora) — conceito totalmente diferente.
    centro_custo_id = Column(Integer, ForeignKey("centro_custo.id", ondelete="RESTRICT", onupdate="CASCADE", name="fk_conta_centro_custo_id"), nullable=True, index=True)
    natureza_custo  = Column(String(16), nullable=True)
    __table_args__ = (UniqueConstraint("owner_tipo", "owner_id", "codigo", name="uq_conta_owner_codigo"),)


class CentroCusto(Base):
    """Árvore de Centro de Custo ("quem gastou"), por owner (rede|loja) — mesmo molde de Conta,
    mas sem partida dobrada própria: só é referenciada por Conta.centro_custo_id. Módulo
    Financeiro — Centro de Custo/Natureza (2026-08-08)."""
    __tablename__ = "centro_custo"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo = Column(String(10), nullable=False)   # 'rede' | 'loja'
    owner_id   = Column(Integer,    nullable=False)
    codigo     = Column(String(20), nullable=False)   # hierárquico: '1', '1.1'
    nome       = Column(Text,       nullable=False)
    pai_id     = Column(Integer, ForeignKey("centro_custo.id"), nullable=True, index=True)
    ativo      = Column(Integer, default=1)
    ordem      = Column(Integer, default=0)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("owner_tipo", "owner_id", "codigo", name="uq_centro_custo_owner_codigo"),)


class Lancamento(Base):
    """Lançamento contábil (partida dobrada) do Livro. Módulo Financeiro sub-projeto #2.
    Carrega projeto_id (dimensão gerencial, = nome_safe). `data` = competência."""
    __tablename__ = "lancamento"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo       = Column(String(10), nullable=False)
    owner_id         = Column(Integer,    nullable=False)
    data             = Column(DateTime,   nullable=False, default=datetime.utcnow)
    conta_debito_id  = Column(Integer, ForeignKey("conta.id"), nullable=False, index=True)
    conta_credito_id = Column(Integer, ForeignKey("conta.id"), nullable=False, index=True)
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

    __table_args__ = (Index("ix_lancamento_owner", "owner_tipo", "owner_id"),)


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
    # Frente 2 (spec 2026-08-25, Centro de Custo/Natureza): snapshot de relatorio_natureza +
    # relatorio_centro_custo do intervalo, gravado no fechamento — coluna PRÓPRIA de propósito
    # (não entra em dados_json, que já tem um conteúdo diferente e específico — alocação por
    # projeto, uma lista, não um dict; misturar os dois exigiria reestruturar o formato existente
    # pra quem já lê dados_json). Período FECHADO devolve o snapshot; aberto calcula ao vivo.
    classificacao_snapshot_json = Column(Text, nullable=True)
    criado_em            = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_periodo_contabil_owner", "owner_tipo", "owner_id"),)


class VeredictoProvisao(Base):
    """Veredito NOMEADO sobre o saldo aberto de uma provisão na Conciliação Final (ACHADO-16,
    docs/db/TAREFA_ACHADO16.md, passo 8) — substitui o cancelamento silencioso que
    `resolver_saldo_provisao` fazia sozinho. Toda rubrica que chega à Conciliação Final com
    saldo aberto exige um destes quatro, escolhido por uma pessoa: 'efetivada' (FALTA — a
    despesa real já foi reconhecida a cada efetivação, só falta o residual mecânico),
    'encerrada_valor_menor' (SOBRA — efetiva pelo valor real e reverte o resíduo, DUAS pernas),
    'nao_se_aplica' (SOBRA — reverte o saldo inteiro; exige `motivo`) ou 'ainda_vai_chegar' (não
    resolve nada — o projeto não fecha). Fica registrado quem decidiu e quando: é o rastro que
    sustenta o relatório de "projetos encerrados por reversão" (o contra-controle de que
    `nao_se_aplica`/`encerrada_valor_menor` não viram só um jeito de encerrar sem olhar)."""
    __tablename__ = "veredictos_provisao"

    id                 = Column(Integer,  primary_key=True, autoincrement=True)
    owner_tipo         = Column(String(10), nullable=False)
    owner_id           = Column(Integer,  nullable=False)
    projeto_nome       = Column(Text,     nullable=False)
    codigo_provisao    = Column(Text,     nullable=False)
    veredito           = Column(Text,     nullable=False)
    valor_provisionado = Column(Float,    nullable=False)
    valor_efetivado    = Column(Float,    nullable=True)
    valor_revertido    = Column(Float,    nullable=True)
    motivo             = Column(Text,     nullable=True)
    decidido_por_id    = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    decidido_em        = Column(DateTime, default=datetime.utcnow)
    ref                = Column(String(80), nullable=True)   # idempotência, mesmo padrão de Lancamento.ref

    decidido_por = relationship("Usuario", foreign_keys=[decidido_por_id])

    __table_args__ = (Index("ix_veredictos_provisao_owner_projeto", "owner_tipo", "owner_id", "projeto_nome"),)


class Contrato(Base):
    """Contrato gerado a partir do orçamento aprovado."""
    __tablename__ = "contratos"

    id                   = Column(Integer,  primary_key=True, autoincrement=True)
    num_contrato         = Column(Text,     nullable=True)   # LOJA-AAAA-MM-DD-SEQ
    projeto_nome         = Column(Text,     nullable=False)
    orcamento_id         = Column(Integer,  ForeignKey("orcamentos.id"), nullable=False, index=True)
    template_path        = Column(Text,     nullable=False, default="config/contrato_template.docx")
    pdf_path             = Column(Text,     nullable=True)
    endereco_instalacao  = Column(Text,     nullable=True)
    pagamento_json       = Column(Text,     nullable=True)   # JSON com cronograma de parcelas
    # Retrato IMUTÁVEL da negociação, gravado só na 2ª assinatura (junto da constituição das
    # provisões): desconto_pct, forma_pagamento, negociacao_json (parcelas/entrada/juros de
    # retenção) do Orçamento + parametros_json (custos adicionais) do Projeto — tudo num dict só.
    # Diferente de pagamento_json (que é só texto pra detectar obsolescência, não trava nada).
    snapshot_negociacao_json = Column(Text, nullable=True)
    status               = Column(Text,     nullable=False, default="rascunho")
    # status: rascunho | gerado | assinado_loja | assinado_cliente | vigente
    adendo               = Column(Text,     nullable=True)
    gerado_em            = Column(DateTime, nullable=True)
    gerado_por_id        = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    loja_id              = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
    loja_snapshot_json   = Column(Text,     nullable=True)   # snapshot dos dados da loja (F3)
    modelo_versao_id     = Column(Integer, ForeignKey("documento_modelos.id"), nullable=True, index=True)
    # NULL = contrato legado -> cai no contrato_template/contrato.md global.
    # Preenchido = reproduz as cláusulas daquela versão, mesmo que a loja já
    # tenha trocado o modelo. Ver docs/superpowers/specs/2026-07-15-modelos-documentos-loja-design.md D6.
    # Assinatura eletrônica ClickSign (2026-08-11): canal escolhido na tela de assinatura —
    # NULL/'interno' é o mecanismo de sempre (loja+cliente clicam na tela); 'clicksign' empurra
    # o PDF pra um envelope na ClickSign e a tela interna recusa assinar aquele documento (uma
    # fonte de verdade só, ver _registrar_assinatura_contrato/_reconciliar_contrato_clicksign).
    # C1 (27/08/2026, alinhamento de modelos): server_default="interno" casa com o banco (aqui e
    # em AprovacaoPE.assinatura_canal, abaixo) — mas a origem dele NÃO é rastreável em código:
    # _migrar_colunas_pg faz só `ADD COLUMN ... VARCHAR(16)`, sem DEFAULT nenhum. Alguém rodou um
    # ALTER COLUMN direto no banco em algum momento (fora de migration, achado da revisão de
    # 27/08). O valor em si bate com o comentário acima (NULL/'interno' já eram equivalentes), e
    # SolicitacaoMedicao.assinatura_canal (mesmo campo, 3ª classe) NÃO tem esse default no banco —
    # inconsistência entre as três, não uma regra deliberada. Registrado, não corrigido aqui.
    assinatura_canal              = Column(String(16), nullable=True, server_default="interno")
    clicksign_envelope_id         = Column(Text,     nullable=True)
    clicksign_enviado_em          = Column(DateTime, nullable=True)
    clicksign_signatarios_json    = Column(Text,     nullable=True)
    # Frente 3 (achado do usuário 2026-08-17): signatário do CLIENTE confirmado na aprovação do
    # orçamento (override do modal ou o Cliente cadastrado, já resolvido) — sobrevive além do
    # `signatario_override` transiente do request, pra pré-preencher a confirmação de assinatura
    # manual (interna) sem pedir nome+CPF em branco de novo.
    cliente_nome_confirmado       = Column(Text,     nullable=True)
    cliente_cpf_confirmado        = Column(Text,     nullable=True)

    gerado_por   = relationship("Usuario",  foreign_keys=[gerado_por_id])
    orcamento    = relationship("Orcamento", foreign_keys=[orcamento_id])
    assinaturas  = relationship("ContratoAssinatura", back_populates="contrato",
                                cascade="all, delete-orphan")


class ContratoAssinatura(Base):
    """Registro de assinatura — interna (loja/cliente clicam na tela) ou confirmação vinda da
    ClickSign (reconciliação/webhook), ver Contrato.assinatura_canal."""
    __tablename__ = "contratos_assinaturas"

    id           = Column(Integer,  primary_key=True, autoincrement=True)
    contrato_id  = Column(Integer,  ForeignKey("contratos.id"), nullable=False, index=True)
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
    A assinatura completa (loja+cliente) constitui as provisões contábeis da diferença negociada
    (mesmo mecanismo do fechamento da venda original, achado Vera 2026-08-12 — a decisão anterior
    de "sem efeito contábil, acerto na liquidação" nunca teve o "acerto" implementado em lugar
    nenhum, e o valor assinado ficava sem rastro no razão)."""
    __tablename__ = "aditivos"

    id                 = Column(Integer,  primary_key=True, autoincrement=True)
    num_aditivo        = Column(Text,     nullable=True)    # TA<AAAAMMDD><SEQ> (gerado 1x)
    projeto_nome       = Column(Text,     nullable=False, index=True)
    contrato_id        = Column(Integer,  ForeignKey("contratos.id"), nullable=False, index=True)
    orcamento_complemento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=False, index=True)
    pdf_path           = Column(Text,     nullable=True)
    dados_json         = Column(Text,     nullable=True)    # snapshot da diferença (ambientes, valores)
    status             = Column(Text,     nullable=False, default="rascunho")
    # status: rascunho | para_assinatura | assinado_loja | assinado_cliente | assinado
    gerado_em          = Column(DateTime, nullable=True)
    gerado_por_id      = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    loja_id            = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
    modelo_versao_id   = Column(Integer,  ForeignKey("documento_modelos.id"), nullable=True, index=True)

    assinaturas = relationship("AditivoAssinatura", back_populates="aditivo",
                               cascade="all, delete-orphan")


class AditivoAssinatura(Base):
    """Assinatura interna do Termo Aditivo — espelho de ContratoAssinatura."""
    __tablename__ = "aditivos_assinaturas"

    id          = Column(Integer,  primary_key=True, autoincrement=True)
    aditivo_id  = Column(Integer,  ForeignKey("aditivos.id"), nullable=False, index=True)
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
    contrato_id      = Column(Integer,  ForeignKey("contratos.id"), nullable=False, index=True)
    pdf_path         = Column(Text,     nullable=True)
    dados_json       = Column(Text,     nullable=True)    # {"ambientes": [{id, nome}]} aprovados
    status           = Column(Text,     nullable=False, default="rascunho")
    # status: rascunho | para_assinatura | assinado_loja | assinado_cliente | assinado
    gerado_em        = Column(DateTime, nullable=True)
    gerado_por_id    = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    loja_id          = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
    modelo_versao_id = Column(Integer,  ForeignKey("documento_modelos.id"), nullable=True, index=True)
    # Assinatura eletrônica ClickSign (2026-08-11) — mesmo mecanismo do Contrato, ver lá.
    # server_default: ver a nota C1 em Contrato.assinatura_canal (origem não rastreável em código).
    assinatura_canal              = Column(String(16), nullable=True, server_default="interno")
    clicksign_envelope_id         = Column(Text,     nullable=True)
    clicksign_enviado_em          = Column(DateTime, nullable=True)
    clicksign_signatarios_json    = Column(Text,     nullable=True)

    assinaturas = relationship("AprovacaoPEAssinatura", back_populates="aprovacao",
                               cascade="all, delete-orphan")


class AprovacaoPEAssinatura(Base):
    """Assinatura interna da Aprovação do PE — espelho de ContratoAssinatura."""
    __tablename__ = "aprovacoes_pe_assinaturas"

    id           = Column(Integer,  primary_key=True, autoincrement=True)
    aprovacao_id = Column(Integer,  ForeignKey("aprovacoes_pe.id"), nullable=False, index=True)
    parte        = Column(Text,     nullable=False)   # loja | cliente
    nome         = Column(Text,     nullable=False)
    cpf          = Column(Text,     nullable=False)
    assinado_em  = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_origem    = Column(Text,     nullable=True)
    hash_sha256  = Column(Text,     nullable=False)

    aprovacao = relationship("AprovacaoPE", back_populates="assinaturas")


class SolicitacaoMedicao(Base):
    """Termo de Responsabilidade e Solicitação de Medição (achado do usuário 2026-08-17): a
    etapa 9 do ciclo deixou de ser um upload simples e virou um documento GERADO pelo sistema
    (modelo por loja tipo 'solicitacao_medicao'), assinável interno (loja+cliente, sem
    testemunhas) OU por ClickSign — mesmo mecanismo do Contrato/Aprovação do PE. Tabela PRÓPRIA
    (não reaproveita `Medicao`, que guarda o parecer/planta da etapa 10 — dado não-relacionado a
    assinatura) espelhando `AprovacaoPE`."""
    __tablename__ = "solicitacoes_medicao"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome     = Column(Text,     nullable=False, index=True)
    pdf_path         = Column(Text,     nullable=True)
    status           = Column(Text,     nullable=False, default="rascunho")
    # status: rascunho | para_assinatura | assinado_loja | assinado_cliente | assinado
    gerado_em        = Column(DateTime, nullable=True)
    gerado_por_id    = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    loja_id          = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
    modelo_versao_id = Column(Integer,  ForeignKey("documento_modelos.id"), nullable=True, index=True)
    # Assinatura eletrônica ClickSign — mesmo mecanismo do Contrato/Aprovação do PE.
    # server_default: ver a nota C1 em Contrato.assinatura_canal — esta 3ª classe NÃO tinha o
    # default no banco (alinhado na migration 0006, revisão de 27/08/2026, item 3 do relatório de
    # alinhamento); campo igual às outras duas agora, sem comportamento divergente por classe.
    assinatura_canal              = Column(String(16), nullable=True, server_default="interno")
    clicksign_envelope_id         = Column(Text,     nullable=True)
    clicksign_enviado_em          = Column(DateTime, nullable=True)
    clicksign_signatarios_json    = Column(Text,     nullable=True)

    assinaturas = relationship("SolicitacaoMedicaoAssinatura", back_populates="solicitacao",
                               cascade="all, delete-orphan")


class SolicitacaoMedicaoAssinatura(Base):
    """Assinatura interna da Solicitação de Medição — espelho de ContratoAssinatura/
    AprovacaoPEAssinatura. Só loja/cliente (sem testemunha, decisão do usuário 2026-08-17)."""
    __tablename__ = "solicitacoes_medicao_assinaturas"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    solicitacao_id = Column(Integer,  ForeignKey("solicitacoes_medicao.id"), nullable=False, index=True)
    parte          = Column(Text,     nullable=False)   # loja | cliente
    nome           = Column(Text,     nullable=False)
    cpf            = Column(Text,     nullable=False)
    assinado_em    = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_origem      = Column(Text,     nullable=True)
    hash_sha256    = Column(Text,     nullable=False)

    solicitacao = relationship("SolicitacaoMedicao", back_populates="assinaturas")


class IntegracaoClickSign(Base):
    """Credencial ClickSign por loja OU por rede (2026-08-11) — espelha fiscal/mod_fiscal.py
    (resolver_emitente/focus_client_para_emitente), mas mais simples: 1 linha por loja OU por
    rede (sem tabela de override tipo PerfilEmissao), já que não existe "tipo de documento" pra
    distinguir na credencial. Tokens gravados cifrados (integracoes.cripto_segredos); nunca em
    texto puro no banco. Resolução (mod_clicksign.resolver_config): override da loja -> default
    da rede -> None (nenhum configurado = dormente, fluxo interno de assinatura continua)."""
    __tablename__ = "integracoes_clicksign"

    id                  = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id             = Column(Integer,  ForeignKey("lojas.id"), nullable=True, index=True)
    rede_id             = Column(Integer,  ForeignKey("redes.id"), nullable=True, index=True)
    token_sandbox_enc   = Column(Text,     nullable=True)
    token_producao_enc  = Column(Text,     nullable=True)
    webhook_secret_enc  = Column(Text,     nullable=True)
    ambiente_ativo      = Column(Text,     nullable=False, default="sandbox")   # sandbox | producao
    criado_em           = Column(DateTime, nullable=True, default=datetime.utcnow)
    atualizado_em       = Column(DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    cliente_id   = Column(Integer,  ForeignKey("clientes.id"), nullable=True, index=True)
    # Central de Comunicação (spec 2026-07-27, Fatia 1): a Conversa deixa de ser só "do projeto".
    # tipo: projeto (a de sempre) | direct (1:1) | grupo (N) | publico (mural da loja, Fatia 2).
    # `titulo` é o nome do grupo. `criado_por_id` = quem abriu. Registros antigos = 'projeto'
    # (default preenche as linhas existentes na migração).
    # tipo: projeto | direct | grupo | mural | forum_loja | forum_orizon (Fatia 4). mural =
    # canal de avisos por loja (gerência posta); forum_loja/forum_orizon = DEBATES (cada conversa
    # é um tópico com título+assunto). forum_orizon é CROSS-LOJA (escopo rede_id).
    tipo          = Column(String(20), nullable=False, default="projeto", server_default="projeto")
    titulo        = Column(Text,       nullable=True)
    rede_id       = Column(Integer,    ForeignKey("redes.id", ondelete="RESTRICT", onupdate="CASCADE", name="fk_conversas_rede_id"), nullable=True, index=True)   # só forum_orizon
    criado_por_id = Column(Integer,    ForeignKey("usuarios.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_conversas_criado_por_id"), nullable=True, index=True)
    # Assunto da conversa (Orizon Chat, Fatia 2): livre (Conversa Livre) | projeto (usa
    # `projeto_nome`) | custom (usa `assunto_id`). Ortogonal ao `tipo` (direct/grupo): categoriza
    # sobre O QUE se fala. Registros antigos = 'livre' (mas os do projeto herdam via projeto_nome).
    assunto_tipo  = Column(String(12), nullable=False, default="livre", server_default="livre")
    assunto_id    = Column(Integer,    ForeignKey("assuntos.id", ondelete="RESTRICT", onupdate="CASCADE", name="fk_conversas_assunto_id"), nullable=True, index=True)
    # Segmento MANUAL do atendimento (revisão UX 2026-07-31 r3): a triagem INDICA
    # (segmento_sugerido) e a gerência pode tratar/trocar pelo seletor do thread. NULL = derivar
    # do tráfego externo (_atendimento_meta); preenchido = override que vence o derivado.
    segmento      = Column(String(20), nullable=True)
    # Atendimentos UI (spec 2026-08-04): responsável ATUAL da conversa (§7.1-A — triagem/criação
    # atribuem, Transferir muda, a transferência automática de etapa também atualiza); urgência
    # MANUAL (§6.1, sem regra automática); origem de entrada (§5 — decide a tag de fallback
    # Triagem×Avulsa quando não há segmento); status do ATENDIMENTO (§8 — concluir/reabrir,
    # global à conversa, ≠ do arquivamento pessoal em ConversaParticipante.arquivada).
    responsavel_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_conversas_responsavel_usuario_id"), nullable=True, index=True)
    urgente        = Column(Integer,    nullable=False, default=0, server_default="0")
    origem_entrada = Column(String(12), nullable=True)    # triagem | avulsa | NULL (legado/interna)
    status         = Column(String(12), nullable=False, default="aberta", server_default="aberta")   # aberta | concluida
    concluido_por_id = Column(Integer,  ForeignKey("usuarios.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_conversas_concluido_por_id"), nullable=True, index=True)
    concluido_em   = Column(DateTime,   nullable=True)
    conclusao_obs  = Column(Text,       nullable=True)
    criado_em    = Column(DateTime, default=datetime.utcnow)


class Assunto(Base):
    """Assunto CUSTOM do Orizon Chat (Fatia 2), criado pelo usuário via "criar assunto". Os
    assuntos-projeto NÃO vivem aqui (são a lista viva de projetos) e "Conversa Livre" é o default
    (assunto_tipo='livre', sem linha). Um assunto por loja (isolado)."""
    __tablename__ = "assuntos"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    loja_id       = Column(Integer, ForeignKey("lojas.id"), nullable=False, index=True)
    nome          = Column(Text,    nullable=False)
    criado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    ativo         = Column(Integer, nullable=False, default=1)
    criado_em     = Column(DateTime, default=datetime.utcnow)


class UsuarioPresenca(Base):
    """Presença do usuário (Orizon Chat, Fatia 6): heartbeat da web. Offline há > N min → a ponte
    WhatsApp pode espelhar/notificar (dentro das regras da Meta)."""
    __tablename__ = "usuario_presenca"

    usuario_id = Column(Integer, ForeignKey("usuarios.id"), primary_key=True)
    visto_em   = Column(DateTime, default=datetime.utcnow)


class MensagemAnexo(Base):
    """Anexo (foto/arquivo) de uma mensagem do Orizon Chat (Fatia 5). O binário vive no storage
    (dir de comunicação, fora do git); aqui ficam os metadados + caminho relativo."""
    __tablename__ = "mensagem_anexos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    mensagem_id = Column(Integer, ForeignKey("conversa_mensagens.id"), nullable=False, index=True)
    tipo        = Column(String(12), nullable=False, default="arquivo")   # imagem | arquivo
    nome        = Column(Text,    nullable=False)
    mime        = Column(String(120), nullable=True)
    tamanho     = Column(Integer, nullable=True)
    caminho     = Column(Text,    nullable=False)   # relativo ao dir de comunicação
    criado_em   = Column(DateTime, default=datetime.utcnow)


class ConversaParticipante(Base):
    """Membro de uma Conversa direct/grupo (Central de Comunicação, Fatia 1). Público NÃO lista
    participantes (audiência = a loja); projeto tampouco (audiência = o time do projeto). direct
    tem exatamente 2 linhas. `lido_ate_mensagem_id` é a base do "não lido" (Fatia 2)."""
    __tablename__ = "conversa_participantes"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    conversa_id   = Column(Integer, ForeignKey("conversas.id"), nullable=False, index=True)
    usuario_id    = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    papel         = Column(String(12), nullable=False, default="membro")   # membro | admin
    arquivada     = Column(Integer, nullable=False, default=0)
    lido_ate_mensagem_id = Column(Integer, nullable=True)
    # Membership da CONVERSA DO PROJETO (Orizon Chat, unificação 2026-07-27): a origem distingue o
    # membro DERIVADO da equipe (auto) do adicionado à mão (manual); `removido` é o tombstone da
    # remoção manual de um auto — o sync respeita ("override vence"): não readiciona.
    origem        = Column(String(8),  nullable=False, default="manual", server_default="manual")   # auto | manual
    removido      = Column(Integer,    nullable=False, default=0, server_default="0")
    adicionado_em = Column(DateTime, default=datetime.utcnow)


class ConversaParticipanteExterno(Base):
    """Participante EXTERNO de uma conversa (contato por WhatsApp/e-mail, SEM Usuario) — Orizon Chat
    2026-07-28. As mensagens da conversa ESPELHAM para o telefone/e-mail dele via mod_chat_externo
    (Meta Cloud API / SMTP), sempre CONFIG-GATED: sem credencial nasce 'pendente_config'. Destacado
    na UI (melhora a organização — pedido do lojista). `removido` = tombstone (mesma lógica do interno)."""
    __tablename__ = "conversa_participantes_externos"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    conversa_id   = Column(Integer, ForeignKey("conversas.id"), nullable=False, index=True)
    nome          = Column(Text,    nullable=False)
    telefone      = Column(Text,    nullable=True)     # WhatsApp (Meta)
    email         = Column(Text,    nullable=True)
    meio          = Column(String(16), nullable=False, default="whatsapp")   # whatsapp | email
    removido      = Column(Integer, nullable=False, default=0)
    criado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    criado_em     = Column(DateTime, default=datetime.utcnow)


class TemplateMensagem(Base):
    """Template de mensagem aprovado pela Meta (RF-07, Orizon Chat/Meta 2026-07-28). Por LOJA. Cada
    `slot_obrigatorio` (1..9 da tabela 4.1 da spec) tem no máximo UM template ativo por loja — é o
    checklist de configuração inicial (RF-16). `assinatura_var` = posição da variável do responsável
    real (RF-17a). Status espelha o painel: rascunho/pendente · em_analise ('Em análise na Meta') ·
    aprovado · rejeitado."""
    __tablename__ = "template_mensagem"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    loja_id          = Column(Integer, ForeignKey("lojas.id"), nullable=False, index=True)
    segmento         = Column(String(20), nullable=True)    # comercial/.../sac/compras/parceiros (NULL=geral)
    slot_obrigatorio = Column(Integer, nullable=True)       # 1..9 (tabela 4.1) ou NULL (extra)
    nome_meta        = Column(Text,     nullable=False)     # nome do template na Meta
    categoria        = Column(String(12), nullable=False, default="utility")   # utility | marketing
    idioma           = Column(String(12), nullable=False, default="pt_BR")
    corpo            = Column(Text,     nullable=True)      # texto com {{1}}…
    variaveis_json   = Column(Text,     nullable=True)      # JSON: descrição das variáveis
    assinatura_var   = Column(Integer,  nullable=True)      # posição da var de assinatura (RF-17a)
    status           = Column(String(12), nullable=False, default="rascunho")  # rascunho|em_analise|aprovado|rejeitado
    meta_template_id = Column(Text,     nullable=True)
    ativo            = Column(Integer,  nullable=False, default=1)
    criado_por_id    = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    criado_em        = Column(DateTime, default=datetime.utcnow)


class TriagemConfig(Base):
    """Configuração da pergunta de triagem por LOJA (RF-08, Orizon Chat/Meta). Uma linha por loja.
    `formato` = lista (opções numeradas) | livre (texto, atendente roteia). `itens_json` = lista
    ordenada de {segmento, rotulo, ativo} da lista de opções mostrada ao cliente."""
    __tablename__ = "triagem_config"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    loja_id        = Column(Integer, ForeignKey("lojas.id"), nullable=False, unique=True, index=True)
    formato        = Column(String(8), nullable=False, default="lista")   # lista | livre
    mensagem_livre = Column(Text, nullable=True)
    itens_json     = Column(Text, nullable=True)   # [{segmento, rotulo, ativo}] ordenado
    atualizado_em  = Column(DateTime, default=datetime.utcnow)


class SegmentoConfig(Base):
    """Configuração de um segmento (canal) por LOJA (RF-02, Orizon Chat/Meta): ativar/desativar,
    rótulo de exibição e template padrão. Uma linha por (loja, segmento) — o padrão (7 segmentos,
    todos ativos) é derivado em código quando não há linha."""
    __tablename__ = "segmento_config"
    __table_args__ = (UniqueConstraint("loja_id", "segmento", name="uq_segmento_config"),)

    id                = Column(Integer, primary_key=True, autoincrement=True)
    loja_id           = Column(Integer, ForeignKey("lojas.id"), nullable=False, index=True)
    segmento          = Column(String(20), nullable=False)
    ativo             = Column(Integer, nullable=False, default=1)
    rotulo            = Column(Text, nullable=True)
    template_padrao_id = Column(Integer, ForeignKey("template_mensagem.id"), nullable=True, index=True)
    # r4 (2026-07-31): segmento = CANAL DE ENTRADA da triagem, com RESPONSÁVEL (Funcionario —
    # decisão 16: responsabilidade é por funcionário). Linhas com `segmento` fora do catálogo
    # base são segmentos CUSTOM da loja (criados/apagados na tela Segmentos).
    responsavel_funcionario_id = Column(Integer, ForeignKey("funcionarios.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_segmento_config_responsavel_funcionario_id"), nullable=True, index=True)
    atualizado_em     = Column(DateTime, default=datetime.utcnow)


class NumeroConectado(Base):
    """Número de WhatsApp Business conectado por LOJA (RF-01, Orizon Chat/Meta): UM número cobre
    toda a comunicação externa da loja. Guarda só o número EXIBÍVEL (E.164) + rótulo — o transporte
    real (token/Phone Number ID) vive em variável de ambiente (config-gated), NUNCA no banco."""
    __tablename__ = "numero_conectado"

    id            = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id       = Column(Integer,  ForeignKey("lojas.id"), nullable=False, unique=True, index=True)
    numero        = Column(String(24), nullable=True)   # E.164 exibível, ex.: +55 12 99604-9888
    rotulo        = Column(Text,     nullable=True)
    atualizado_em = Column(DateTime, default=datetime.utcnow)


class ConversaMensagem(Base):
    """Mensagem da Conversa (Fatia 1: só interna). `canal` já nasce na coluna porque é do
    modelo consolidado da spec, mas na Fatia 1 apenas 'interno' circula (mod_chat valida).
    `autor_usuario_id` NULL fica RESERVADO para resposta vinda de fora (fatias 6-7,
    e-mail/WhatsApp) — nenhum caminho interno cria mensagem sem autor hoje."""
    __tablename__ = "conversa_mensagens"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    conversa_id      = Column(Integer,  ForeignKey("conversas.id"), nullable=False, index=True)
    autor_usuario_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    # Destinatário DIRIGIDO da mensagem (F2, 2026-07-28): um membro específico. NULL = todos.
    # Marcação VISUAL — todos os membros leem; o render exibe "para <nome>".
    destinatario_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_conversa_mensagens_destinatario_usuario_id"), nullable=True, index=True)
    corpo            = Column(Text,     nullable=False)
    canal            = Column(String(20), nullable=False, default="interno")
    # Central de Comunicação (spec 2026-07-27): segmento derivado da FUNÇÃO do autor no envio
    # (comercial|financeiro|logistica|...). Rótulo automático, não seleção manual.
    canal_segmento   = Column(String(20), nullable=True)
    # Fatia 2 (Responsabilidade + transferência — spec seção 6): 'transferencia' oficializa a
    # troca de responsabilidade gravando em CicloEtapa.responsavel_funcionario_id (o campo do
    # v12; NADA de estado paralelo). `bloqueador` nesta fatia é SÓ flag — o gate real em
    # pode_avancar() é a Fatia 3. `resolvido_em` fecha o bloqueador (Fatia 3 também).
    natureza         = Column(String(20), nullable=False, default="interacao", server_default="interacao")   # interacao | transferencia
    etapa_codigo     = Column(String(10), nullable=True)
    transferido_para_funcionario_id = Column(Integer, ForeignKey("funcionarios.id", ondelete="SET NULL", onupdate="CASCADE", name="fk_conversa_mensagens_transferido_para_funcionario_id"), nullable=True, index=True)
    # Fatia 5: FK real — o documento tramitado é um CicloDocumento do MESMO projeto
    # (validado no endpoint; a FK segura o vínculo órfão). Só vale em transferência.
    documento_ref_id = Column(Integer,  ForeignKey("ciclo_documentos.id"), nullable=True, index=True)
    bloqueador       = Column(Integer,  nullable=False, default=0, server_default="0")
    resolvido_em     = Column(DateTime, nullable=True)
    # Fatia 4 (modo privado, decisão 8): privada=1 → o corpo em claro NUNCA persiste (fica
    # ""), só `corpo_cifrado` (Fernet, chave ORIZON_CHAT_ENC_KEY do ambiente). Metadados
    # continuam visíveis a todos; o texto só decripta p/ quem tem `ver_mensagem_privada`.
    privada          = Column(Integer,  nullable=False, default=0, server_default="0")
    corpo_cifrado    = Column(Text,     nullable=True)
    # Evento inline na timeline (spec chat 2026-07-31): mensagem de SISTEMA que o render mostra
    # como faixa, não balão — triagem_vinculo | membro_entrou | membro_saiu | fase_transicao |
    # documento_registrado | documento_encaminhado | etapa_concluida | transferencia_pendente |
    # transferencia_aceita (os 3 últimos: Concluir/Transferir do Ciclo, 2026-08-23). NULL =
    # mensagem comum.
    evento           = Column(String(24), nullable=True)
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


class EnvioExterno(Base):
    """Porta de saída/entrada externa de uma Mensagem do chat (Fatias 6-7, spec seção 6d):
    e-mail/WhatsApp. Uma Mensagem pode ter 0..N (saída para o destinatário + entradas de
    resposta). O transporte ao vivo é gated por configuração (mod_chat_externo): sem
    credencial, o envio nasce 'pendente_config' — nunca um 'enviado' fantasma."""
    __tablename__ = "envios_externos"

    id                = Column(Integer,  primary_key=True, autoincrement=True)
    # RF-08 (2026-08-04): NULLABLE — a pergunta automática de TRIAGEM sai ANTES de existir
    # conversa/mensagem; nesse caso o vínculo é triagem_id.
    mensagem_id       = Column(Integer,  ForeignKey("conversa_mensagens.id"), nullable=True, index=True)
    triagem_id        = Column(Integer,  ForeignKey("triagem_entradas.id", ondelete="RESTRICT", onupdate="CASCADE", name="fk_envios_externos_triagem_id"), nullable=True, index=True)
    meio              = Column(String(16), nullable=False)   # email | whatsapp
    direcao           = Column(String(10), nullable=False, default="saida")   # saida | entrada
    canal             = Column(String(20), nullable=True)    # segmento comercial|financeiro|...
    destinatario_tipo = Column(String(16), nullable=True)    # interno|parceiro|cliente|avulso
    destinatario_id   = Column(Integer,  nullable=True)
    destino           = Column(Text,     nullable=True)      # e-mail ou telefone resolvido
    status            = Column(String(20), nullable=False, default="pendente_config")
    id_externo        = Column(Text,     nullable=True, index=True)   # id do provedor (threading)
    id_externo_ref    = Column(Text,     nullable=True)      # id citado numa resposta (decisão 14)
    # Envio por TEMPLATE aprovado (spec 2026-08-04 §11 — ex-F3 de 28/07): aponta o template usado
    # no payload "type":"template"; NULL = texto livre/documento.
    template_id       = Column(Integer,  ForeignKey("template_mensagem.id", ondelete="RESTRICT", onupdate="CASCADE", name="fk_envios_externos_template_id"), nullable=True, index=True)
    erro              = Column(Text,     nullable=True)
    criado_em         = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_envios_externos_destinatario", "destinatario_tipo", "destinatario_id"),)


class TriagemEntrada(Base):
    """Buffer de TRIAGEM automática (revisão 2026-08-05 — substitui a fila humana da spec
    _geral/2026-07-31-triagem-pipeline-entrada-design.md): entrada externa que a automação
    ainda NÃO roteou — primeiro contato de número desconhecido, número ambíguo (2+ conversas
    candidatas) ou projeto concluído. Regra de ouro: mensagem nenhuma é descartada em silêncio.
    Idempotente por `id_externo` (wamid — a Meta reentrega o mesmo webhook 5-6x até o 200).
    Resolução é SEMPRE automática (chat.triagem.triagem_materializar): resposta reconhecida no
    menu → materializa na hora com o segmento escolhido; sem resposta reconhecida em 2min →
    materializa com segmento='triagem' (selo próprio, tratamento cai pro SAC distribuir)."""
    __tablename__ = "triagem_entradas"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id          = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)
    meio             = Column(String(16), nullable=False, default="whatsapp")   # whatsapp | email
    remetente        = Column(Text,     nullable=False)    # número/e-mail normalizado
    texto            = Column(Text,     nullable=True)
    id_externo       = Column(Text,     nullable=True, unique=True, index=True)  # wamid (idempotência)
    id_externo_ref   = Column(Text,     nullable=True)     # id citado (reply), se houver
    status           = Column(String(12), nullable=False, default="pendente")   # pendente|resolvido
    candidatos_json  = Column(Text,     nullable=True)     # [conversa_id, …] quando ambíguo
    segmento_sugerido = Column(String(20), nullable=True)  # resposta do menu de triagem automática
    nome_whatsapp    = Column(String(150), nullable=True)  # nome de perfil da Meta (fallback do lead)
    conversa_id      = Column(Integer,  ForeignKey("conversas.id"), nullable=True, index=True)
    resolvido_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    resolvido_em     = Column(DateTime, nullable=True)
    criado_em        = Column(DateTime, default=datetime.utcnow)


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
    contraparte_tipo = Column(String(10), nullable=False, default="fabrica", server_default="fabrica")  # fabrica|empresa|banco
    contraparte_nome = Column(Text,     nullable=True)
    contraparte_id   = Column(Integer,  ForeignKey("contraparte_financeira.id", ondelete="RESTRICT", onupdate="CASCADE", name="fk_acordo_fabrica_contraparte_id"), nullable=True, index=True)
    loja_titular_id  = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)
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
    acordo_id     = Column(Integer,  ForeignKey("acordo_fabrica.id"), nullable=True, index=True)
    loja_id       = Column(Integer,  ForeignKey("lojas.id"), nullable=False, index=True)   # quem consome
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
    ajuste_id      = Column(Integer,  ForeignKey("ajuste_fabrica.id"), nullable=False, index=True)
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
    relatorio_doc_id = Column(Integer,  ForeignKey("ciclo_documentos.id"), nullable=True, index=True)
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
    rede_id = Column(Integer, ForeignKey("redes.id"), nullable=True, index=True)
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
    emitente_id = Column(Integer, ForeignKey("emitente.id"), nullable=False, index=True)
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
    loja_id        = Column(Integer, ForeignKey("lojas.id"), nullable=True, index=True)
    emitente_id    = Column(Integer, ForeignKey("emitente.id"), nullable=True, index=True)
    status         = Column(Text, nullable=True)
    chave_nfe      = Column(Text, nullable=True)
    numero         = Column(Text, nullable=True)
    serie          = Column(Text, nullable=True)
    mensagem_sefaz = Column(Text, nullable=True)
    erros_json     = Column(Text, nullable=True)
    xml_doc_id     = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True, index=True)
    danfe_doc_id   = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True, index=True)
    fabrica_doc_id = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True, index=True)
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
    _backfill_emitente_cnpj() # copia Loja.cnpj p/ Emitente.cnpj quando ainda vazio (idempotente)
    _sess = get_session()
    try:
        backfill_funcoes_todas_lojas(_sess)   # funções novas do catálogo em todas as lojas (idempotente)
    finally:
        _sess.close()
    _simulador_autorizacao_seed_v1()   # lojas existentes já nascem autorizadas (idempotente, Sessão 185)
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


def _backfill_emitente_cnpj():
    """O painel Fiscal não tinha campo de CNPJ (achado 2026-08-08): todo Emitente criado por ele
    ficou com cnpj vazio, e a Focus recusa a emissão ('CNPJ do emitente não autorizado'). Copia
    Loja.cnpj pro Emitente vinculado quando o Emitente ainda não tem CNPJ próprio. Idempotente;
    não mexe em Emitente que já tem cnpj preenchido (pode ser ≠ da loja, ex. distribuidora)."""
    db = Session()
    try:
        for loja in db.query(Loja).filter(Loja.emitente_id.isnot(None), Loja.cnpj.isnot(None)).all():
            em = db.get(Emitente, loja.emitente_id)
            if em and not (em.cnpj or "").strip():
                em.cnpj = loja.cnpj
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
# loja_id/rede_id NULL = plataforma. Login/senha NÃO ficam aqui — achado real (28/08/2026):
# o login+senha hardcoded que viviam nestas 2 constantes ("sad2026"/"trocar123") acabaram
# como super_admin de verdade na Integração e na Homologação (chegaram pelo dump de
# `usuarios`, não por alguém rodando seed.py nos servidores), com senha_provisoria=0 — uma
# credencial de bootstrap conhecida, versionada no git, ativa em produção-adjacente sem
# forçar troca. seed.py agora lê ORIZON_ADMIN_LOGIN/ORIZON_ADMIN_SENHA do ambiente e se
# recusa a criar o super_admin sem as duas — nada de valor default.
_SEED_SA_NOME  = "Administrador da Plataforma"

# Catálogo padrão de Funções (cargos) — semeado por loja via seed.py (Regras §7/§8).
FUNCOES_PADRAO = [
    "Consultor de Vendas", "Gerente de Vendas", "Gerente Administrativo/Financeiro", "Diretor",
    "Assistente Logístico", "Conferente", "Supervisor de Montagem", "Assistente Administrativo",
    "Projetista Executivo", "Medidor", "Montador", "Ajudante de Montagem", "SAC",
]


def _simulador_autorizacao_seed_v1():
    """Seed idempotente (Sessão 185, decisão do usuário): lojas EXISTENTES nascem autorizadas pro
    Simulador — sem isso, toda loja de produção viraria 🔒 da noite pro dia na entrada em vigor da
    autorização por loja. Loja sem NENHUMA linha `simulador_autorizacoes` (nova ou já semeada)
    ganha uma `ativa` com concedido_por_usuario_id=NULL (marca "seed", não uma concessão real de
    Master) — idempotente: loja que já tem qualquer linha (ativa OU revogada) não é tocada, porque
    revogar deliberadamente depois do seed não pode ser desfeito por um restart do servidor."""
    db = Session()
    try:
        ja_tem = {lid for (lid,) in db.query(SimuladorAutorizacao.loja_id).distinct().all()}
        criadas = 0
        for (lid,) in db.query(Loja.id).all():
            if lid in ja_tem:
                continue
            db.add(SimuladorAutorizacao(
                loja_id=lid, status="ativa", concedido_por_usuario_id=None,
                beneficiario="orizon_assessoria", escopo="simulacao_leitura",
                base_legal="Seed inicial — lojas existentes migradas já autorizadas (decisão do "
                           "usuário, Sessão 185).",
                concedido_em=datetime.utcnow()))
            criadas += 1
        if criadas:
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def backfill_funcoes_todas_lojas(db):
    """Semeia funções NOVAS do catálogo em TODAS as lojas existentes (idempotente por
    loja+nome). Roda no start — sem isso, uma função acrescentada a FUNCOES_PADRAO (ex.:
    'Ajudante de Montagem', 2026-07-26) só apareceria em loja criada depois. Retorna nº criadas."""
    criadas = 0
    for (lid,) in db.query(Loja.id).all():
        existentes = {f.nome for f in db.query(Funcao).filter_by(loja_id=lid).all()}
        for nome in FUNCOES_PADRAO:
            if nome not in existentes:
                usa = 1 if nome == "Consultor de Vendas" else 0
                db.add(Funcao(loja_id=lid, nome=nome, status="ativo", usa_comissao_vendas=usa))
                criadas += 1
    if criadas:
        db.commit()
    return criadas



def _migrar_colunas_pg():
    """Postgres: ADD/DROP COLUMN idempotentes — `create_all()` não altera tabelas já
    existentes, então toda coluna nova do modelo precisa de uma linha aqui para chegar
    aos bancos já povoados (local, VPS A/B, produção).

    CONGELADA em 27/08/2026 (revisão estrutural do banco, Alembic adotado — ver
    docs/db/ESTADO_REVISAO.md e CLAUDE.md §"Banco de dados — regras permanentes", R1).
    Mantém só o que já está aqui, para os bancos que ainda não rodaram as migrations.
    NENHUM ADD COLUMN novo entra nesta função — schema novo é sempre uma revisão em
    migrations/versions/, nunca DDL solto fora de migration."""
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
        # Conciliação de PE/AF2 (spec 2026-08-14): Complemento de Projeto por fase.
        "ALTER TABLE orcamentos ADD COLUMN IF NOT EXISTS parcela_id INTEGER",
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
        # Central de Comunicação (spec 2026-07-27, Fatia 1): tipo/titulo/criado_por na conversa
        # + segmento derivado da função na mensagem. tipo='projeto' preenche as linhas existentes.
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) DEFAULT 'projeto'",
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS titulo TEXT",
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS criado_por_id INTEGER",
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS canal_segmento VARCHAR(20)",
        # Orizon Chat Fatia 2: assunto da conversa (livre|projeto|custom). Linhas do projeto
        # herdam via projeto_nome; as demais nascem 'livre'.
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS assunto_tipo VARCHAR(12) DEFAULT 'livre'",
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS assunto_id INTEGER",
        "UPDATE conversas SET assunto_tipo='projeto' WHERE projeto_nome IS NOT NULL AND (assunto_tipo IS NULL OR assunto_tipo='livre')",
        # Fatia 4: canais públicos viram 3 (mural avisos + forum_loja + forum_orizon cross-loja).
        # O antigo 'publico' (canal aberto único) vira um debate 'forum_loja' "Geral".
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS rede_id INTEGER",
        "UPDATE conversas SET tipo='forum_loja', titulo=COALESCE(titulo,'Geral') WHERE tipo='publico'",
        # Fatia 6: ponte WhatsApp — preferência de notificação do usuário (presença é tabela nova).
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS notificar_whatsapp VARCHAR(16) DEFAULT 'quando_offline'",
        # — CHAT (frente 2026-07-31; tabela triagem_entradas nova nasce no create_all) —
        # Evento inline na timeline (faixa de sistema): triagem_vinculo/membro_entrou/…
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS evento VARCHAR(24)",
        # Segmento manual do atendimento (r3): NULL = derivado do tráfego; preenchido vence.
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS segmento VARCHAR(20)",
        # r4: segmento tem RESPONSÁVEL (funcionário) — canal de entrada da triagem.
        "ALTER TABLE segmento_config ADD COLUMN IF NOT EXISTS responsavel_funcionario_id INTEGER",
        # Unificação conversa-do-projeto (2026-07-27): origem/removido na membership.
        "ALTER TABLE conversa_participantes ADD COLUMN IF NOT EXISTS origem VARCHAR(8) DEFAULT 'manual'",
        "ALTER TABLE conversa_participantes ADD COLUMN IF NOT EXISTS removido INTEGER DEFAULT 0",
        # Fonte única da equipe (2026-07-27): responsável TERCEIRO por etapa.
        "ALTER TABLE ciclo_etapas ADD COLUMN IF NOT EXISTS responsavel_terceiro_id INTEGER",
        # Desmembramento operacional Fatia 3: valor bruto por ambiente (split exato na liberação).
        "ALTER TABLE parcela_ambiente ADD COLUMN IF NOT EXISTS valor_ambiente DOUBLE PRECISION DEFAULT 0.0",
        # Retenção recorrente + previsões por fase (2026-08-02)
        "ALTER TABLE parcela_projeto ADD COLUMN IF NOT EXISTS liberacao_prevista DATE",
        "ALTER TABLE parcela_projeto ADD COLUMN IF NOT EXISTS entrega_prevista DATE",
        # Agenda Fatia 1 (2026-08-03): Val_Liq congelado por fase
        "ALTER TABLE parcela_projeto ADD COLUMN IF NOT EXISTS val_liq_congelado DOUBLE PRECISION",
        # Retenção auditável (2026-08-03): catálogo de motivo (retenção é POR AMBIENTE)
        "ALTER TABLE retencao_obra ADD COLUMN IF NOT EXISTS motivo_tipo TEXT",
        # RF-08 triagem automática (2026-08-04): pergunta sai sem conversa → mensagem_id opcional
        "ALTER TABLE envios_externos ALTER COLUMN mensagem_id DROP NOT NULL",
        "ALTER TABLE envios_externos ADD COLUMN IF NOT EXISTS triagem_id INTEGER",
        # Atendimentos UI (spec 2026-08-04): responsável atual + urgência manual + origem de
        # entrada + status concluir/reabrir na conversa; template usado no envio externo.
        # O DEFAULT backfila as linhas existentes no próprio ADD.
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS responsavel_usuario_id INTEGER",
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS urgente INTEGER DEFAULT 0",
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS origem_entrada VARCHAR(12)",
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS status VARCHAR(12) DEFAULT 'aberta'",
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS concluido_por_id INTEGER",
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS concluido_em TIMESTAMP",
        "ALTER TABLE conversas ADD COLUMN IF NOT EXISTS conclusao_obs TEXT",
        "ALTER TABLE envios_externos ADD COLUMN IF NOT EXISTS template_id INTEGER",
        # Backfill (revisão visual 2026-08-04): conversas de PROJETO criadas antes do fix acima
        # nasceram sem responsável (get_or_create_conversa_projeto não recebia criado_por_id
        # ainda) — achado do Marcelo comparando Homolog com o mockup (cabeçalho sem nome).
        # Idempotente: só toca quem ainda está NULL; não sobrescreve transferência já feita.
        "UPDATE conversas SET responsavel_usuario_id = "
        "(SELECT criado_por_id FROM projetos_meta WHERE nome_safe = conversas.projeto_nome) "
        "WHERE tipo = 'projeto' AND responsavel_usuario_id IS NULL "
        "AND projeto_nome IN (SELECT nome_safe FROM projetos_meta WHERE criado_por_id IS NOT NULL)",
        # Orizon Chat 2026-07-28: participante EXTERNO (contato WhatsApp/e-mail) — create_all cria a
        # tabela nova; esta linha é só o marcador (sem ADD COLUMN — a tabela nasce completa).
        # F2 (destinatário dirigido por mensagem): marcação visual "para <nome>".
        "ALTER TABLE conversa_mensagens ADD COLUMN IF NOT EXISTS destinatario_usuario_id INTEGER",
        # Orizon Chat/Meta Fatia 2: biblioteca de templates (RF-07) — tabela nova via create_all (marcador).
        # Orizon Chat/Meta Fatia 6: config de triagem (RF-08) — tabela nova via create_all (marcador).
        # Orizon Chat/Meta: config de segmentos (RF-02) — tabela nova via create_all (marcador).
        # Orizon Chat/Meta: número conectado por loja (RF-01) — tabela nova via create_all (marcador).
        # Chat Fatia 5 (FK do documento tramitado, conversa_mensagens.documento_ref_id): a entrada
        # que criava fk_convmsg_documento_ref saiu daqui em 27/08/2026 — virou constraint órfã
        # (nome divergente do modelo, achada na comparação constraint-a-constraint da baseline
        # Alembic) e a migration 0008 já a renomeou pro nome padrão. Manter a entrada aqui
        # recriaria a FK antiga com o nome velho a cada boot (o EXCEPTION duplicate_object só
        # pega nome igual, não estrutura igual — resultado seria uma segunda FK duplicada na
        # mesma coluna). Ver CLAUDE.md.
        "ALTER TABLE clientes DROP COLUMN IF EXISTS omie_codigo",
        "ALTER TABLE clientes DROP COLUMN IF EXISTS omie_sync_status",
        "ALTER TABLE clientes DROP COLUMN IF EXISTS omie_sync_erro",
        "ALTER TABLE clientes DROP COLUMN IF EXISTS omie_sync_at",
        # Triagem automática (2026-08-05): nome do perfil do WhatsApp (Meta), usado como fallback
        # de nome do lead quando o telefone não bate com nenhum Cliente já cadastrado.
        "ALTER TABLE triagem_entradas ADD COLUMN IF NOT EXISTS nome_whatsapp VARCHAR(150)",
        # Mapa de Atribuições — Montagem aceita VÁRIOS executores por ambiente (2026-08-06,
        # pedido do usuário). A UniqueConstraint antiga (1 só por papel/ambiente) sai do modelo
        # e vira ÍNDICE ÚNICO PARCIAL, válido só pra papel<>'montagem' — SQLAlchemy não tem como
        # expressar "único, exceto quando X" via __table_args__. DROP tolera o nome não existir
        # (bases que nunca chegaram a criar a constraint, ex. squash de create_all novo).
        """DO $$ BEGIN
             ALTER TABLE atribuicoes_ambiente DROP CONSTRAINT uq_atribuicao_papel_ambiente;
           EXCEPTION WHEN undefined_object THEN NULL; END $$""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_atribuicao_papel_ambiente "
        "ON atribuicoes_ambiente (projeto_nome, pool_ambiente_id, papel) WHERE papel <> 'montagem'",
        # Assistência ganha agendamento próprio (2026-08-06): ambiente + janela — sai do Mapa de
        # Atribuições (papel 'assistencia' removido de mod_escopo.PAPEIS). assistencia_executores/
        # assistencia_anexos são tabelas NOVAS (create_all cria sozinho, sem entrada aqui).
        "ALTER TABLE assistencia_caso ADD COLUMN IF NOT EXISTS pool_ambiente_id INTEGER",
        "ALTER TABLE assistencia_caso ADD COLUMN IF NOT EXISTS data_inicio DATE",
        "ALTER TABLE assistencia_caso ADD COLUMN IF NOT EXISTS data_fim DATE",
        # forma de pagamento (direto/a_prazo) + classificação do avulso (garantia/concessão),
        # 2026-08-07 — ver docstring de AssistenciaCaso.
        "ALTER TABLE assistencia_caso ADD COLUMN IF NOT EXISTS forma_pagamento VARCHAR DEFAULT 'direto'",
        "ALTER TABLE assistencia_caso ADD COLUMN IF NOT EXISTS classificacao_avulsa VARCHAR",
        # limpeza única: linhas do Mapa com o papel aposentado (o mecanismo nunca chegou a ser
        # usado de verdade — achado ao investigar antes de tirar 'assistencia' do Mapa — mas
        # roda mesmo assim por segurança; idempotente, a 2ª vez apaga 0 linha).
        "DELETE FROM atribuicoes_ambiente WHERE papel = 'assistencia'",
        # Não-recebimento (2026-08-07): recebível reclassificado pra "Recebíveis Duvidosos" (1.1.10)
        # — ver docstring de Recebivel.
        "ALTER TABLE recebivel ADD COLUMN IF NOT EXISTS duvidoso_em DATE",
        # O model.origem alargou de String(30) pra String(64) em 2026-07-15 (comentário na classe
        # Lancamento) mas a migração de COLUMN TYPE nunca foi escrita — bases Postgres criadas antes
        # dessa data ficaram presas em varchar(30) e nunca mais deram erro até um evento novo passar
        # de 30 chars (achado ao vivo 2026-08-07, StringDataRightTruncation em
        # 'reconhecimento_despesa_retencao_com_vendas' e afins — a coluna larga só existia no papel).
        "ALTER TABLE lancamento ALTER COLUMN origem TYPE VARCHAR(64)",
        # Permissões por conta do Gestor de Rede (2026-08-08) — ver docstring de Usuario.
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS capacidades_override_json TEXT",
        # Centro de Custo/Natureza (2026-08-08): 2 etiquetas novas na conta — a tabela centro_custo
        # nasce completa via create_all (marcador); só as 2 colunas em `conta` precisam de ADD.
        "ALTER TABLE conta ADD COLUMN IF NOT EXISTS centro_custo_id INTEGER",
        "ALTER TABLE conta ADD COLUMN IF NOT EXISTS natureza_custo VARCHAR(16)",
        # Simulador — fluxo remoto de autorização (Sessão 187): a tabela simulador_autorizacoes já
        # nasceu na Sessão 185/186 sem essas 2 colunas — achado da Vera (2026-08-10): banco que já
        # tinha a tabela ficava com UndefinedColumn em toda rota do Simulador (create_all() não
        # altera tabela existente, só cria as que faltam).
        "ALTER TABLE simulador_autorizacoes ADD COLUMN IF NOT EXISTS solicitado_por_usuario_id INTEGER",
        "ALTER TABLE simulador_autorizacoes ADD COLUMN IF NOT EXISTS solicitado_em TIMESTAMP",
        # Cancelamento de contrato — timing correto de provisão + trava definitiva (2026-08-12):
        # provisões passam a nascer só na 2ª assinatura (não mais na geração do PDF); cancelar
        # depois disso trava o PROJETO pra sempre (cancelado_definitivo), e o contrato fechado
        # guarda um retrato imutável da negociação (snapshot_negociacao_json).
        "ALTER TABLE projetos_meta ADD COLUMN IF NOT EXISTS cancelado_definitivo INTEGER DEFAULT 0",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS snapshot_negociacao_json TEXT",
        # Assinatura eletrônica ClickSign (2026-08-11): canal escolhido na tela de assinatura do
        # Contrato/Aprovação do PE — tabela integracoes_clicksign nasce via create_all (marcador).
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS assinatura_canal VARCHAR(16)",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS clicksign_envelope_id TEXT",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS clicksign_enviado_em TIMESTAMP",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS clicksign_signatarios_json TEXT",
        "ALTER TABLE aprovacoes_pe ADD COLUMN IF NOT EXISTS assinatura_canal VARCHAR(16)",
        "ALTER TABLE aprovacoes_pe ADD COLUMN IF NOT EXISTS clicksign_envelope_id TEXT",
        "ALTER TABLE aprovacoes_pe ADD COLUMN IF NOT EXISTS clicksign_enviado_em TIMESTAMP",
        "ALTER TABLE aprovacoes_pe ADD COLUMN IF NOT EXISTS clicksign_signatarios_json TEXT",
        # Faxina D4Sign (2026-08-12): integração nunca chegou a ter código — só colunas de uma
        # migração antiga (commit c0f256f). Substituída pela ClickSign; dropa o schema morto.
        "ALTER TABLE contratos DROP COLUMN IF EXISTS d4sign_uuid",
        "ALTER TABLE contratos DROP COLUMN IF EXISTS d4sign_enviado_em",
        "ALTER TABLE contratos DROP COLUMN IF EXISTS d4sign_signatarios_json",
        "ALTER TABLE aprovacoes_pe DROP COLUMN IF EXISTS d4sign_uuid",
        "ALTER TABLE aprovacoes_pe DROP COLUMN IF EXISTS d4sign_enviado_em",
        "ALTER TABLE aprovacoes_pe DROP COLUMN IF EXISTS d4sign_signatarios_json",
        # Achado do usuário 2026-08-17: Terceiro (MEI) precisa de CNPJ; Folha de Pagamento ganha
        # % de comissão ajustável pelo gerente no ato do pagamento (comissão de venda).
        "ALTER TABLE terceiros ADD COLUMN IF NOT EXISTS cnpj VARCHAR(18)",
        "ALTER TABLE comissao_folha ADD COLUMN IF NOT EXISTS pct_ajustado DOUBLE PRECISION",
        # Achado do usuário 2026-08-17: e-mail de testemunha, pra assinatura digital (ClickSign)
        # poder cadastrá-la como signatária — nome/CPF já existiam, só pro contrato impresso.
        "ALTER TABLE lojas ADD COLUMN IF NOT EXISTS testemunha1_email VARCHAR(150)",
        "ALTER TABLE lojas ADD COLUMN IF NOT EXISTS testemunha2_email VARCHAR(150)",
        # Frente 3 (achado do usuário 2026-08-17): signatário confirmado na aprovação do
        # orçamento, reaproveitado na confirmação de assinatura manual.
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS cliente_nome_confirmado TEXT",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS cliente_cpf_confirmado TEXT",
        # Logo por loja (2026-08-20): nome do arquivo em logos_loja/<id>/, NULL = padrão do sistema.
        "ALTER TABLE lojas ADD COLUMN IF NOT EXISTS logo_arquivo VARCHAR(80)",
        # Transferência de responsabilidade da etapa (2026-08-23): "Concluir" pergunta se
        # transfere; pendente até quem recebeu clicar "Receber Projeto" (ou aceite automático
        # se o destino não tem login). Índices parciais — sem eles a agregação cross-projeto de
        # "Pendências"/"Responsabilidades" (GET /api/me/ciclo/...) faz full scan da tabela toda.
        "ALTER TABLE ciclo_etapas ADD COLUMN IF NOT EXISTS transferencia_status VARCHAR(10) DEFAULT 'nenhuma'",
        "ALTER TABLE ciclo_etapas ADD COLUMN IF NOT EXISTS transferencia_destino_funcionario_id INTEGER",
        "ALTER TABLE ciclo_etapas ADD COLUMN IF NOT EXISTS transferencia_destino_terceiro_id INTEGER",
        "ALTER TABLE ciclo_etapas ADD COLUMN IF NOT EXISTS transferencia_solicitada_por_usuario_id INTEGER",
        "ALTER TABLE ciclo_etapas ADD COLUMN IF NOT EXISTS transferencia_solicitada_em TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS ix_ciclo_etapas_transf_dest_func ON ciclo_etapas (transferencia_destino_funcionario_id) WHERE transferencia_status = 'pendente'",
        "CREATE INDEX IF NOT EXISTS ix_ciclo_etapas_transf_dest_terc ON ciclo_etapas (transferencia_destino_terceiro_id) WHERE transferencia_status = 'pendente'",
        "CREATE INDEX IF NOT EXISTS ix_ciclo_etapas_responsavel_funcionario ON ciclo_etapas (responsavel_funcionario_id)",
        # A entrada que criava ix_ciclo_etapas_responsavel_terceiro saiu daqui em 27/08/2026 —
        # duplicata de ix_ciclo_etapas_responsavel_terceiro_id (mesma coluna, nome sem o sufixo
        # "_id", confirmado via pg_index). A migration 0009 dropa a duplicata nos bancos que já
        # a tinham; manter a entrada aqui a recriaria a cada boot. Ver CLAUDE.md.
        # Frente 2 (spec 2026-08-25, Centro de Custo/Natureza): snapshot dos relatórios no fechamento.
        "ALTER TABLE periodo_contabil ADD COLUMN IF NOT EXISTS classificacao_snapshot_json TEXT",
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
    # A própria loja do usuário é SEMPRE acessível, mesmo sem linha em usuario_lojas (o
    # backfill pode não ter rodado neste banco). Antes, quem não tinha o vínculo ficava com
    # a própria loja de FORA da lista — no Diretor da mãe sobrava só o PDV, e a loja ativa
    # podia cair no PDV, quebrando toda operação nos projetos da mãe (chat 403/404). Direção
    # única preservada: isto só adiciona a loja NATIVA — PDV não ganha a mãe por aqui.
    if loja_id and loja_id not in ids:
        ids = ids + [loja_id]
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
