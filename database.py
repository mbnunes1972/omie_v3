"""
database.py — Conexão SQLAlchemy + modelos de dados
Omie_V3 | Dalmóbile
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from datetime import datetime
import hashlib
import os

# ── Conexão ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "omie.db")
ENGINE   = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session  = sessionmaker(bind=ENGINE)

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
    ativo         = Column(Integer,     default=1)
    criado_em     = Column(DateTime,    default=datetime.utcnow)

    sessoes       = relationship("Sessao",          back_populates="usuario", cascade="all, delete-orphan")
    autorizacoes  = relationship("LogAutorizacao",  back_populates="autorizador", foreign_keys="LogAutorizacao.autorizador_id")

    def set_senha(self, senha: str):
        self.senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    def check_senha(self, senha: str) -> bool:
        return self.senha_hash == hashlib.sha256(senha.encode()).hexdigest()

    @property
    def limite_desconto(self) -> float:
        limites = {"consultor": 10.0, "gerente": 20.0, "diretor": 100.0}
        return limites.get(self.nivel, 0.0)

    @property
    def pode_ver_parametros(self) -> bool:
        return self.nivel in ("gerente", "diretor")


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


# ── Inicialização ─────────────────────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(ENGINE)

def get_session():
    return Session()
