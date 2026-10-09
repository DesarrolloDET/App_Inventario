"""
Schemas Pydantic para el maestro MATERIAS PRIMAS.

Contiene:
- MateriaPrimaCreate: entrada para POST /api/v1/materias-primas.
- MateriaPrimaUpdate: entrada para PUT /api/v1/materias-primas/{id}.
- MateriaPrimaResponse: salida de una materia prima individual.

Reglas aplicadas:
- Seccion 31: validacion de tipos, longitud, formatos.

Decisiones:
- 'codigo' es unico a nivel de BD. La validacion de duplicados se hace
  en el service, no en el schema (el schema no tiene acceso a la BD).
- 'nombre' NO es unico: dos materias primas pueden tener el mismo nombre
  con codigos distintos. Caso de uso: "Maiz amarillo" y "Maiz blanco"
  comparten parcialmente el nombre pero son codigos distintos.
- 'activo' no se expone en Create/Update. Se maneja con endpoints
  dedicados (DELETE para desactivar, POST /reactivar para reactivar).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Entrada: POST /api/v1/materias-primas
# ---------------------------------------------------------------------------

class MateriaPrimaCreate(BaseModel):
    """Cuerpo de la peticion para crear una materia prima."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    codigo: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Codigo unico de la materia prima.",
        examples=["MAIZ-001"],
    )

    nombre: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Nombre descriptivo de la materia prima.",
        examples=["Maiz amarillo"],
    )


# ---------------------------------------------------------------------------
# Entrada: PUT /api/v1/materias-primas/{id}
# ---------------------------------------------------------------------------

class MateriaPrimaUpdate(BaseModel):
    """
    Cuerpo de la peticion para actualizar una materia prima.

    Todos los campos son opcionales: se actualiza solo lo que llega.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    codigo: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Nuevo codigo unico.",
    )

    nombre: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
        description="Nuevo nombre descriptivo.",
    )


# ---------------------------------------------------------------------------
# Salida: una materia prima individual
# ---------------------------------------------------------------------------

class MateriaPrimaResponse(BaseModel):
    """Representacion publica de una materia prima."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    materia_prima_id: int = Field(..., description="ID de la materia prima.")
    codigo: str = Field(..., description="Codigo unico.")
    nombre: str = Field(..., description="Nombre descriptivo.")
    activo: bool = Field(..., description="Si la materia prima esta activa.")