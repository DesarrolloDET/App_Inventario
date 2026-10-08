"""
Punto de entrada de la aplicacion FastAPI MEJIA TURNOS.

"""

from fastapi import FastAPI

from app.database.connection import probar_conexion
from app.routers.auth import router as auth_router


# ---------------------------------------------------------------------------
# Aplicacion
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MEJIA TURNOS",
    version="1.0.0",
    description="Sistema de gestion de turnos y citas para Mejia y Cia.",
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
def inicio() -> dict:
    """Endpoint raiz de health check."""
    return {
        "sistema": "MEJIA TURNOS",
        "estado": "OK",
    }


@app.get("/health/database", tags=["health"])
def health_database() -> dict:
    """Verifica la conexion a la base de datos."""
    try:
        database = probar_conexion()
        return {
            "status": "connected",
            "database": database,
        }
    except Exception:
        # No exponer detalles del error al cliente (regla 32).
        return {
            "status": "error",
            "detail": "No se pudo conectar a la base de datos.",
        }