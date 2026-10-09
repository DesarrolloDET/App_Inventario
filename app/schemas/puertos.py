"""
Schemas Pydantic para el maestro PUERTOS.

"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Entrada: POST /api/v1/puertos
# ---------------------------------------------------------------------------

class PuertoCreate(BaseModel):
    """Cuerpo de la peticion para crear un puerto."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    nombre: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Nombre del puerto. Debe ser unico.",
        examples=["Buenaventura"],
    )


# ---------------------------------------------------------------------------
# Entrada: PUT /api/v1/puertos/{id}
# ---------------------------------------------------------------------------

class PuertoUpdate(BaseModel):
    """
    Cuerpo de la peticion para actualizar un puerto.

    Todos los campos son opcionales: se actualiza solo lo que llega.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    nombre: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
        description="Nuevo nombre del puerto.",
    )


# ---------------------------------------------------------------------------
# Salida: un puerto individual
# ---------------------------------------------------------------------------

class PuertoResponse(BaseModel):
    """Representacion publica de un puerto."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,   # permite construir desde un modelo SQLAlchemy
    )

    puerto_id: int = Field(..., description="ID del puerto.")
    nombre: str = Field(..., description="Nombre del puerto.")
    activo: bool = Field(..., description="Si el puerto esta activo.")
