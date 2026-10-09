"""
Schemas Pydantic para CUPOS.

Contiene:
- CupoResponse: salida de un cupo.

Reglas aplicadas:
- Seccion 7: un cupo = una franja horaria.

Decisiones:
- Un cupo no se expone con Create/Update directos. Se genera
  automaticamente desde el detalle de programacion.
- El campo 'activo' es de solo lectura.
"""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field


class CupoResponse(BaseModel):
    """Representacion publica de un cupo."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    cupo_id: int = Field(..., description="ID del cupo.")
    programacion_detalle_id: int = Field(
        ..., description="ID del detalle al que pertenece."
    )
    fecha: date = Field(..., description="Fecha del cupo.")
    hora_inicio: time = Field(..., description="Hora de inicio de la franja.")
    hora_fin: time = Field(..., description="Hora de fin de la franja.")
    activo: bool = Field(..., description="Si el cupo esta activo.")