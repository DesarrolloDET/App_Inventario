"""
Schemas comunes reutilizables por todos los modulos.

"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Tipo generico
# ---------------------------------------------------------------------------

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Parametros de paginacion
# ---------------------------------------------------------------------------

class PaginationParams(BaseModel):
    """
    Parametros de paginacion tipados.

    Uso en routers:
        from fastapi import Query
        from app.schemas.common import PaginationParams

        def listar(
            pag: PaginationParams = Depends(),
            ...
        ):
            ...

    O bien, mas explicito:
        def listar(
            page: int = Query(1, ge=1),
            page_size: int = Query(20, ge=1, le=100),
        ):
            ...
    """

    model_config = ConfigDict(extra="forbid")

    page: int = Field(
        default=1,
        ge=1,
        description="Numero de pagina (1-indexed).",
    )

    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Cantidad de elementos por pagina (1-100).",
    )

    @property
    def offset(self) -> int:
        """Calcula el offset SQL equivalente a la pagina actual."""
        return (self.page - 1) * self.page_size


# ---------------------------------------------------------------------------
# Envoltorio generico de paginacion
# ---------------------------------------------------------------------------

class Page(BaseModel, Generic[T]):
    """
    Respuesta paginada generica.

    Ejemplo de uso:
        @router.get("/puertos", response_model=Page[PuertoResponse])
        def listar(...):
            items, total = listar_puertos(...)
            return Page[PuertoResponse](
                items=items,
                total=total,
                page=pag.page,
                page_size=pag.page_size,
                pages=(total + pag.page_size - 1) // pag.page_size,
            )
    """

    model_config = ConfigDict(extra="forbid")

    items: list[T] = Field(
        description="Elementos de la pagina actual.",
    )

    total: int = Field(
        ge=0,
        description="Total de elementos en el universo completo.",
    )

    page: int = Field(
        ge=1,
        description="Pagina actual (1-indexed).",
    )

    page_size: int = Field(
        ge=1,
        le=100,
        description="Cantidad de elementos por pagina.",
    )

    pages: int = Field(
        ge=0,
        description="Total de paginas (ceil(total / page_size)).",
    )
