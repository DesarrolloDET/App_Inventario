"""
Schemas Pydantic para PROGRAMACION_DETALLE.

Contiene:
- ProgramacionDetalleCreate: entrada para POST
  /api/v1/programaciones/{programacion_id}/detalles.
- ProgramacionDetalleUpdate: entrada para PUT
  /api/v1/programaciones/{programacion_id}/detalles/{detalle_id}.
- ProgramacionDetalleResponse: salida.

Reglas aplicadas:
- Seccion 6:  cada detalle representa una operacion
              (fecha + transportadora + materia prima + puerto + cantidad).
- Seccion 31: validacion de tipos.

Decisiones:
- 'cantidad_vehiculos' > 0.
- El puerto es obligatorio.
- La transportadora, materia prima y puerto deben existir y estar
  activos. La validacion la hace el service.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Entrada: POST
# ---------------------------------------------------------------------------

class ProgramacionDetalleCreate(BaseModel):
    """Cuerpo de la peticion para crear un detalle de programacion."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fecha_operacion: date = Field(
        ...,
        description="Fecha de la operacion (debe estar dentro del rango de la programacion).",
    )
    transportadora_id: int = Field(
        ..., ge=1, description="ID de la transportadora (debe estar activa)."
    )
    materia_prima_id: int = Field(
        ..., ge=1, description="ID de la materia prima (debe estar activa)."
    )
    puerto_id: int = Field(
        ..., ge=1, description="ID del puerto de origen (debe estar activo)."
    )
    cantidad_vehiculos: int = Field(
        ...,
        ge=1,
        le=100,
        description="Cantidad de vehiculos a programar. Maximo 100 por operacion.",
    )


# ---------------------------------------------------------------------------
# Entrada: PUT
# ---------------------------------------------------------------------------

class ProgramacionDetalleUpdate(BaseModel):
    """
    Cuerpo de la peticion para actualizar un detalle.

    Nota: si cambia 'cantidad_vehiculos' o 'fecha_operacion', el service
    debe regenerar los cupos (eliminar los antiguos y crear los nuevos).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fecha_operacion: date | None = Field(default=None)
    transportadora_id: int | None = Field(default=None, ge=1)
    materia_prima_id: int | None = Field(default=None, ge=1)
    puerto_id: int | None = Field(default=None, ge=1)
    cantidad_vehiculos: int | None = Field(default=None, ge=1, le=100)


# ---------------------------------------------------------------------------
# Salida
# ---------------------------------------------------------------------------

class ProgramacionDetalleResponse(BaseModel):
    """Representacion publica de un detalle de programacion."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    programacion_detalle_id: int = Field(..., description="ID del detalle.")
    programacion_id: int = Field(..., description="ID de la programacion padre.")
    fecha_operacion: date = Field(..., description="Fecha de la operacion.")
    transportadora_id: int = Field(..., description="ID de la transportadora.")
    materia_prima_id: int = Field(..., description="ID de la materia prima.")
    puerto_id: int = Field(..., description="ID del puerto de origen.")
    cantidad_vehiculos: int = Field(
        ..., description="Cantidad de vehiculos programados."
    )
    cupos_generados: int = Field(
        0,
        description="Cantidad de cupos efectivamente generados (puede ser "
                    "menor que cantidad_vehiculos si hubo bloqueos).",
    )