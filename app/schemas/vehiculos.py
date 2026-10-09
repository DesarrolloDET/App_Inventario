"""
Schemas Pydantic para el maestro VEHICULOS.

Contiene:
- VehiculoCreate: entrada para POST /api/v1/vehiculos.
- VehiculoUpdate: entrada para PUT /api/v1/vehiculos/{id}.
- VehiculoResponse: salida de un vehiculo individual.

Reglas aplicadas:
- Seccion 31: validacion de tipos, longitud, formatos.

Decisiones:
- 'placa' es unico a nivel de BD. La validacion de duplicados se hace
  en el service.
- 'transportadora_id' es FK obligatoria. En CREATE debe apuntar a una
  transportadora existente y ACTIVA.
- En UPDATE, si cambia transportadora_id, se valida lo mismo. Si no
  cambia, no se revalida (evita fallos si la transportadora se
  desactivo despues de crear el vehiculo).
- La respuesta NO incluye los datos completos de la transportadora.
  Para eso, el cliente consulta /api/v1/transportadoras/{id} aparte.
- 'activo' no se expone en Create/Update. Se maneja con endpoints
  dedicados (DELETE para desactivar, POST /reactivar para reactivar).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Entrada: POST /api/v1/vehiculos
# ---------------------------------------------------------------------------

class VehiculoCreate(BaseModel):
    """Cuerpo de la peticion para crear un vehiculo."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    placa: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Placa unica del vehiculo.",
        examples=["ABC123"],
    )

    transportadora_id: int = Field(
        ...,
        ge=1,
        description="ID de la transportadora propietaria (debe estar activa).",
    )


# ---------------------------------------------------------------------------
# Entrada: PUT /api/v1/vehiculos/{id}
# ---------------------------------------------------------------------------

class VehiculoUpdate(BaseModel):
    """
    Cuerpo de la peticion para actualizar un vehiculo.

    Todos los campos son opcionales: se actualiza solo lo que llega.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    placa: str | None = Field(
        default=None,
        min_length=1,
        max_length=10,
        description="Nueva placa unica.",
    )

    transportadora_id: int | None = Field(
        default=None,
        ge=1,
        description="Nuevo ID de transportadora (debe estar activa).",
    )


# ---------------------------------------------------------------------------
# Salida: un vehiculo individual
# ---------------------------------------------------------------------------

class VehiculoResponse(BaseModel):
    """Representacion publica de un vehiculo."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    vehiculo_id: int = Field(..., description="ID del vehiculo.")
    placa: str = Field(..., description="Placa unica.")
    transportadora_id: int = Field(..., description="ID de la transportadora propietaria.")
    activo: bool = Field(..., description="Si el vehiculo esta activo.")