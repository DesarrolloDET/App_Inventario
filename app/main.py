"""
Punto de entrada de la aplicacion FastAPI MEJIA TURNOS.


"""

from fastapi import FastAPI

from app.database.connection import probar_conexion
from app.routers.auth import router as auth_router
from app.routers.puertos import router as puertos_router
from app.routers.materias_primas import router as materias_primas_router
from app.routers.conductores import router as conductores_router
from app.routers.transportadoras import router as transportadoras_router
from app.routers.vehiculos import router as vehiculos_router
from app.routers.bloqueos import router as bloqueos_router


# ---------------------------------------------------------------------------
# Prefijo global de la API
# ---------------------------------------------------------------------------
# Cambiar aqui cuando se cree /api/v2 para no tocar los routers.
# ---------------------------------------------------------------------------

API_V1_PREFIX = "/api/v1"


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

app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(puertos_router, prefix=API_V1_PREFIX)
app.include_router(materias_primas_router, prefix=API_V1_PREFIX)
app.include_router(conductores_router, prefix=API_V1_PREFIX)
app.include_router(transportadoras_router, prefix=API_V1_PREFIX)
app.include_router(vehiculos_router, prefix=API_V1_PREFIX)
app.include_router(bloqueos_router, prefix=API_V1_PREFIX)

# ---------------------------------------------------------------------------
# Health checks (sin prefijo: son infraestructura)
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