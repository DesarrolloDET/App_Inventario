"""
Schemas Pydantic para el maestro BLOQUEOS HORARIOS.

Contiene:
- TipoBloqueo: enum cerrado de tipos de bloqueo.
- BloqueoCreate: entrada para POST /api/v1/bloqueos.
- BloqueoUpdate: entrada para PUT /api/v1/bloqueos/{id}.
- BloqueoResponse: salida de un bloqueo individual.

Reglas aplicadas:
- Seccion 31: validacion de tipos, longitud, formatos.
- Seccion 8:  los bloqueos son operativos de Mejia (no de transportadoras).

Decisiones:
- TipoBloqueo es un ENUM cerrado. Si se requiere un tipo nuevo, se
  agrega al enum y se hace un cambio controlado.
- 'hora_fin' > 'hora_inicio' (validado aqui Y en la BD).
- 'fecha', 'hora_inicio', 'hora_fin', 'tipo_bloqueo' son obligatorios.
- 'descripcion' es opcional.
- Los intervalos se interpretan como [hora_inicio, hora_fin).
- 'activo' no se expone en Create/Update.
"""

from __future__ import annotations

from datetime import date, time
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enum de tipos de bloqueo
# ---------------------------------------------------------------------------

class TipoBloqueo(str, Enum):
    """
    Tipos de bloqueo operativo soportados en el MVP.

    Fuente unica de verdad: si se requiere un tipo nuevo, se agrega aqui.
    El modelo SQLAlchemy, el servicio y el router usan este enum.

    Notas:
    - ALMUERZO: bloqueo obligatorio de 12:00 a 13:00 en el MVP.
    - LIMPIEZA: aseo de areas o equipos.
    - MANTENIMIENTO: reparaciones programadas.
    - CAMBIO_PRODUCTO: transicion entre materias primas.
    - RESTRICCION_OPERATIVA: restriccion puntual (clima, seguridad, etc.).
    - CIERRE_TEMPORAL: cierre total de operacion (festivos, eventos).
    """

    ALMUERZO = "ALMUERZO"
    LIMPIEZA = "LIMPIEZA"
    MANTENIMIENTO = "MANTENIMIENTO"
    CAMBIO_PRODUCTO = "CAMBIO_PRODUCTO"
    RESTRICCION_OPERATIVA = "RESTRICCION_OPERATIVA"
    CIERRE_TEMPORAL = "CIERRE_TEMPORAL"


# ---------------------------------------------------------------------------
# Entrada: POST /api/v1/bloqueos
# ---------------------------------------------------------------------------

class BloqueoCreate(BaseModel):
    """Cuerpo de la peticion para crear un bloqueo horario."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    fecha: date = Field(
        ...,
        description="Fecha del bloqueo.",
        examples=["2026-10-15"],
    )

    hora_inicio: time = Field(
        ...,
        description="Hora de inicio del bloqueo (inclusive).",
        examples=["12:00:00"],
    )

    hora_fin: time = Field(
        ...,
        description="Hora de fin del bloqueo (exclusive).",
        examples=["13:00:00"],
    )

    tipo_bloqueo: TipoBloqueo = Field(
        ...,
        description="Tipo de bloqueo operativo.",
    )

    descripcion: str | None = Field(
        default=None,
        max_length=500,
        description="Descripcion opcional del bloqueo.",
    )

    @model_validator(mode="after")
    def _validar_horas(self) -> "BloqueoCreate":
        """Verifica que hora_fin > hora_inicio."""
        if self.hora_fin <= self.hora_inicio:
            raise ValueError(
                "hora_fin debe ser estrictamente mayor que hora_inicio."
            )
        return self


# ---------------------------------------------------------------------------
# Entrada: PUT /api/v1/bloqueos/{id}
# ---------------------------------------------------------------------------

class BloqueoUpdate(BaseModel):
    """
    Cuerpo de la peticion para actualizar un bloqueo.

    Todos los campos son opcionales: se actualiza solo lo que llega.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    fecha: date | None = Field(default=None)
    hora_inicio: time | None = Field(default=None)
    hora_fin: time | None = Field(default=None)
    tipo_bloqueo: TipoBloqueo | None = Field(default=None)
    descripcion: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Salida: un bloqueo individual
# ---------------------------------------------------------------------------

class BloqueoResponse(BaseModel):
    """Representacion publica de un bloqueo horario."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    bloqueo_id: int = Field(..., description="ID del bloqueo.")
    fecha: date = Field(..., description="Fecha del bloqueo.")
    hora_inicio: time = Field(..., description="Hora de inicio.")
    hora_fin: time = Field(..., description="Hora de fin.")
    tipo_bloqueo: TipoBloqueo = Field(..., description="Tipo de bloqueo.")
    descripcion: str | None = Field(..., description="Descripcion.")
    activo: bool = Field(..., description="Si el bloqueo esta activo.")