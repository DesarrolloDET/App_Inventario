"""
Conexión a la base de datos PostgreSQL.

Usa la configuración central (app.core.config.settings) en lugar de
leer variables de entorno directamente. Esto garantiza:
- Una sola fuente de verdad para la URL de conexión.
- Validación temprana si faltan variables.
- Facilidad para testear (se puede sobreescribir settings).

Reglas aplicadas:
- Sección 29: variables de entorno.
- Sección 30: uso exclusivo de SQLAlchemy/ORM (nada de SQL por concatenación).
- Sección 39: la capa de base de datos no lee config por su cuenta.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings


# Engine global. Se crea una sola vez al importar el módulo.
# pool_pre_ping evita conexiones muertas tras cortes de red.
engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,  # cambiar a True solo para depurar SQL en local
)


def probar_conexion() -> str:
    """
    Verifica que la base de datos responde y devuelve su nombre.
    Se usa desde /health/database.
    """
    with engine.connect() as connection:
        resultado = connection.execute(text("SELECT current_database()"))
        return resultado.scalar_one()