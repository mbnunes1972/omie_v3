"""Alembic env.py — Orizon One."""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# permite "import database" a partir da raiz do projeto
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------- conexao
url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit(
        "DATABASE_URL nao definido.\n"
        "Rode antes:  set -a; source .env; set +a"
    )
# o '%' e caractere de interpolacao do configparser — precisa ser escapado
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))

# ------------------------------------------------------- metadata dos modelos
import database as _db  # noqa: E402

target_metadata = None
for nome in ("Base", "BASE", "Model", "DeclarativeBase"):
    obj = getattr(_db, nome, None)
    if obj is not None and hasattr(obj, "metadata"):
        target_metadata = obj.metadata
        break
if target_metadata is None:
    for nome in ("metadata", "METADATA"):
        obj = getattr(_db, nome, None)
        if obj is not None and hasattr(obj, "tables"):
            target_metadata = obj
            break
if target_metadata is None:
    raise SystemExit(
        "Nao encontrei o metadata dos modelos em database.py.\n"
        "Procure a linha que cria o Base (declarative_base() ou "
        "class Base(DeclarativeBase)) e ajuste esta secao."
    )


# pg_stat_statements e' extensao de infra (CREATE EXTENSION), nao schema da aplicacao —
# nao e' modelada pelo SQLAlchemy e nao deve aparecer em nenhum autogenerate/diff futuro.
_TABELAS_DE_EXTENSAO = {"pg_stat_statements", "pg_stat_statements_info"}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in _TABELAS_DE_EXTENSAO:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
