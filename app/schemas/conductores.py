"""
Schemas Pydantic para el maestro CONDUCTORES.

Contiene:
- ConductorCreate: entrada para POST /api/v1/conductores.
- ConductorUpdate: entrada para PUT /api/v1/conductores/{id}.
- ConductorResponse: salida de un conductor individual.

Reglas aplicadas:
- Seccion 31: validacion de tipos, longitud, formatos.

Decisiones:
- 'documento' es unico a nivel de BD. La validacion de duplicados se
  hace en el service, no en el schema.
- 'nombre_completo' NO es unico: pueden existir dos conductores con el
  mismo nombre pero distinto documento (caso real: homonimos).
- 'activo' no se expone en Create/Update. Se maneja con endpoints
  dedicados (DELETE para desactivar, POST /reactivar para reactivar).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Entrada: POST /api/v1/conductores
# ---------------------------------------------------------------------------

class ConductorCreate(BaseModel):
    """Cuerpo de la peticion para crear un conductor."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    documento: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Numero de documento unico del conductor.",
        examples=["1234567890"],
    )

    nombre_completo: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Nombre completo del conductor.",
        examples=["Juan Perez Gomez"],
    )


# ---------------------------------------------------------------------------
# Entrada: PUT /api/v1/conductores/{id}
# ---------------------------------------------------------------------------

class ConductorUpdate(BaseModel):
    """
    Cuerpo de la peticion para actualizar un conductor.

    Todos los campos son opcionales: se actualiza solo lo que llega.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    documento: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
        description="Nuevo numero de documento unico.",
    )

    nombre_completo: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Nuevo nombre completo.",
    )


# ---------------------------------------------------------------------------
# Salida: un conductor individual
# ---------------------------------------------------------------------------

class ConductorResponse(BaseModel):
    """Representacion publica de un conductor."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    conductor_id: int = Field(..., description="ID del conductor.")
    documento: str = Field(..., description="Documento unico.")
    nombre_completo: str = Field(..., description="Nombre completo.")
    activo: bool = Field(..., description="Si el conductor esta activo.")