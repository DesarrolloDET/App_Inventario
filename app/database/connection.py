"""
Conexion a la base de datos PostgreSQL.


"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,     # verifica conexiones vivas antes de usarlas
    echo=False,             # cambiar a True solo para depurar SQL en local
)


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,       # control manual de transacciones
    autoflush=False,        # evita flushes implicitos antes de queries
    expire_on_commit=False, # objetos siguen usables despues de commit
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def probar_conexion() -> str:
    """
    Verifica que la base de datos responde y devuelve su nombre.
    Se usa desde /health/database.
    """
    with engine.connect() as connection:
        resultado = connection.execute(text("SELECT current_database()"))
        return resultado.scalar_one()


# ---------------------------------------------------------------------------
# Dependencia FastAPI
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    Provee una sesion de base de datos por request.

    Uso en endpoints FastAPI:
        from fastapi import Depends
        from sqlalchemy.orm import Session
        from app.database.connection import get_db

        @router.get("/algo")
        def endpoint(db: Session = Depends(get_db)):
            ...

    Comportamiento transaccional:
      - Si el endpoint retorna sin excepcion -> commit.
      - Si el endpoint lanza cualquier excepcion -> rollback y la
        excepcion se propaga (FastAPI la maneja y responde 500).
      - En cualquier caso, la sesion se cierra.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()