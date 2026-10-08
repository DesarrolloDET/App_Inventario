from fastapi import FastAPI

from app.database.connection import probar_conexion


app = FastAPI(
    title="MEJIA TURNOS",
    version="1.0.0"
)


@app.get("/")
def inicio():
    return {
        "sistema": "MEJIA TURNOS",
        "estado": "OK"
    }


@app.get("/health/database")
def health_database():
    try:
        database = probar_conexion()

        return {
            "status": "connected",
            "database": database
        }

    except Exception as e:
        return {
            "status": "error",
            "detail": str(e)
        }