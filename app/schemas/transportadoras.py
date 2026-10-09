"""
Schemas Pydantic para el maestro TRANSPORTADORAS.

Contiene:
- TransportadoraCreate: entrada para POST /api/v1/transportadoras.
- TransportadoraUpdate: entrada para PUT /api/v1/transportadoras/{id}.
- TransportadoraResponse: salida de una transportadora individual.

Reglas aplicadas:
- Seccion 31: validacion de tipos, longitud, formatos.

Decisiones:
- 'nit' es unico a nivel de BD. La validacion de duplicados se hace
  en el service, no en el schema.
- 'razon_social' NO es unico: pueden existir dos razones sociales
  iguales con NITs distintos (caso real: empresas con nombres
  comerciales similares pero personas juridicas distintas).
- 'activo' no se expone en Create/Update. Se maneja con endpoints
  dedicados (DELETE para desactivar, POST /reactivar para reactivar).

NO se expone la lista de vehiculos en el response.
Razon: eficiencia (evitar N+1) y simplicidad. Si se requiere, se puede
agregar un parametro include_vehiculos=true en el futuro.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Entrada: POST /api/v1/transportadoras
# ---------------------------------------------------------------------------

class TransportadoraCreate(BaseModel):
    """Cuerpo de la peticion para crear una transportadora."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    nit: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="NIT unico de la transportadora.",
        examples=["900123456-7"],
    )

    razon_social: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Razon social de la transportadora.",
        examples=["ABC Transportes S.A.S."],
    )


# ---------------------------------------------------------------------------
# Entrada: PUT /api/v1/transportadoras/{id}
# ---------------------------------------------------------------------------

class TransportadoraUpdate(BaseModel):
    """
    Cuerpo de la peticion para actualizar una transportadora.

    Todos los campos son opcionales: se actualiza solo lo que llega.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    nit: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
        description="Nuevo NIT unico.",
    )

    razon_social: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Nueva razon social.",
    )


# ---------------------------------------------------------------------------
# Salida: una transportadora individual
# ---------------------------------------------------------------------------

class TransportadoraResponse(BaseModel):
    """Representacion publica de una transportadora."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    transportadora_id: int = Field(..., description="ID de la transportadora.")
    nit: str = Field(..., description="NIT unico.")
    razon_social: str = Field(..., description="Razon social.")
    activo: bool = Field(..., description="Si la transportadora esta activa.")