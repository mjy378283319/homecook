import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "homecook.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _column_ddl(col) -> str:
    ddl = f'"{col.name}" {col.type.compile(engine.dialect)}'
    default = getattr(col.default, "arg", None)
    if default is not None and not callable(default):
        if isinstance(default, str):
            ddl += " DEFAULT '" + default.replace("'", "''") + "'"
        elif isinstance(default, bool):
            ddl += f" DEFAULT {1 if default else 0}"
        elif isinstance(default, (int, float)):
            ddl += f" DEFAULT {default}"
    return ddl


def _ensure_columns() -> None:
    """轻量迁移：给已存在的表补齐模型里新增的列（SQLite ADD COLUMN）。

    老版本数据库升级时不丢数据，也不需要手工执行 SQL。
    """
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in tables:
                continue  # create_all 已经建好
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing or col.primary_key:
                    continue
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {_column_ddl(col)}'))


def init_db():
    import app.models  # noqa: F401  (ensure models registered)
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
