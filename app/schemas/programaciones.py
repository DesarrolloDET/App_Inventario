"""
Schemas Pydantic para PROGRAMACIONES (cabecera).

Contiene:
- ProgramacionCreate: entrada para POST /api/v1/programaciones.
- ProgramacionUpdate: entrada para PUT /api/v1/programaciones/{id}.
- ProgramacionResponse: salida de una programacion (cabecera).
- ProgramacionEstadoUpdate: entrada para POST /api/v1/programaciones/{id}/publicar,
                            /cerrar, /cancelar.
- ProgramacionConDetallesResponse: cabecera + lista de detalles.

Reglas aplicadas:
- Seccion 6:  la programacion define la operacion de un rango de fechas.
- Seccion 31: validacion de tipos y fechas.

Decisiones:
- Los estados son un enum cerrado: BORRADOR, PUBLICADA, CERRADA, CANCELADA.
- No se expone 'usuario_creador_id' en Create; lo asigna el backend
  desde el usuario autenticado.
- El rango de fechas se valida: fecha_fin >= fecha_inicio.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enum de estados
# ---------------------------------------------------------------------------

class EstadoProgramacion(str, Enum):
    """Estados posibles de una programacion."""

    BORRADOR = "BORRADOR"
    PUBLICADA = "PUBLICADA"
    CERRADA = "CERRADA"
    CANCELADA = "CANCELADA"


# ---------------------------------------------------------------------------
# Entrada: POST /api/v1/programaciones
# ---------------------------------------------------------------------------

class ProgramacionCreate(BaseModel):
    """
    Cuerpo de la peticion para crear una programacion.

    La programacion se crea en estado BORRADOR. El usuario creador se
    toma del contexto autenticado (no se pasa en el body).
    """

    model_config = ConfigDict(extra="forbid")

    fecha_inicio: date = Field(
        ...,
        description="Fecha de inicio del rango de operacion.",
        examples=["2026-10-15"],
    )

    fecha_fin: date = Field(
        ...,
        description="Fecha de fin del rango de operacion (inclusive).",
        examples=["2026-10-15"],
    )

    @model_validator(mode="after")
    def _validar_rango(self) -> "ProgramacionCreate":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError(
                "fecha_fin debe ser mayor o igual a fecha_inicio."
            )
        return self


# ---------------------------------------------------------------------------
# Entrada: PUT /api/v1/programaciones/{id}
# ---------------------------------------------------------------------------

class ProgramacionUpdate(BaseModel):
    """
    Cuerpo de la peticion para actualizar una programacion.

    Solo permitido en estado BORRADOR. Todos los campos opcionales.
    """

    model_config = ConfigDict(extra="forbid")

    fecha_inicio: date | None = Field(default=None)
    fecha_fin: date | None = Field(default=None)


# ---------------------------------------------------------------------------
# Salida: cabecera
# ---------------------------------------------------------------------------

class ProgramacionResponse(BaseModel):
    """Representacion publica de una programacion (sin detalles)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    programacion_id: int = Field(..., description="ID de la programacion.")
    fecha_inicio: date = Field(..., description="Fecha de inicio del rango.")
    fecha_fin: date = Field(..., description="Fecha de fin del rango.")
    estado: EstadoProgramacion = Field(..., description="Estado actual.")
    usuario_creador_id: int | None = Field(
        ..., description="ID del usuario que creo la programacion."
    )
    fecha_creacion: datetime = Field(..., description="Fecha y hora de creacion.")


# ---------------------------------------------------------------------------
# Salida: cabecera + detalles
# ---------------------------------------------------------------------------

class ProgramacionConDetallesResponse(ProgramacionResponse):
    """
    Representacion publica de una programacion con sus detalles.

    Los detalles se cargan bajo demanda (lazy loading) para no afectar
    el rendimiento de listados.
    """

    detalles: list["ProgramacionDetalleResponse"] = Field(
        default_factory=list,
        description="Lista de detalles de la programacion.",
    )


# ---------------------------------------------------------------------------
# Entrada: cambio de estado
# ---------------------------------------------------------------------------

class ProgramacionEstadoUpdate(BaseModel):
    """
    Cuerpo de la peticion para cambiar el estado de una programacion.

    Normalmente vacio; se define para permitir un 'motivo' futuro.
    """

    model_config = ConfigDict(extra="forbid")

    motivo: str | None = Field(
        default=None,
        max_length=500,
        description="Motivo del cambio de estado (opcional, para auditoria).",
    )


# ---------------------------------------------------------------------------
# Import diferido (evita import circular con programacion_detalle.py)
# ---------------------------------------------------------------------------
# Se importa al final y se llama model_rebuild() para resolver la referencia.

from app.schemas.programacion_detalle import ProgramacionDetalleResponse  # noqa: E402

ProgramacionConDetallesResponse.model_rebuild()