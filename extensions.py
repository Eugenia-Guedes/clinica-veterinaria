
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
jwt = JWTManager()


@event.listens_for(Engine, "connect")
def ativar_chaves_estrangeiras_sqlite(
    dbapi_connection,
    connection_record
):
    """Ativa as chaves estrangeiras em cada conexão SQLite."""

    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
