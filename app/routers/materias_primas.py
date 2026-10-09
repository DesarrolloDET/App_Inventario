"""
Router del maestro MATERIAS PRIMAS.

Endpoints:
- POST   /api/v1/materias-primas                 -> Crear (ADMINISTRADOR)
- GET    /api/v1/materias-primas                 -> Listar (autenticado)
- GET    /api/v1/materias-primas/{id}            -> Obtener (autenticado)
- PUT    /api/v1/materias-primas/{id}            -> Actualizar (ADMINISTRADOR)
- DELETE /api/v1/materias-primas/{id}            -> Desactivar (ADMINISTRADOR)
- POST   /api/v1/materias-primas/{id}/reactivar  -> Reactivar (ADMINISTRADOR)

Reglas aplicadas:
- Seccion 25: autorizacion en backend.
- Seccion 32: mensajes de error seguros.
- Seccion 40: routers delgados; la logica esta en el service.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, require_roles
from app.database.connection import get_db
from app.models.security import Usuario
from app.schemas.common import Page
from app.schemas.materias_primas import (
    MateriaPrimaCreate,
    MateriaPrimaResponse,
    MateriaPrimaUpdate,
)
from app.services import materias_primas_service as svc


router = APIRouter(prefix="/materias-primas", tags=["materias primas"])


# ---------------------------------------------------------------------------
# Listar
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=Page[MateriaPrimaResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar materias primas con paginacion",
)
def listar_materias_primas(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1, description="Numero de pagina (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por pagina."),
    solo_activos: bool = Query(True, description="Si True, solo materias primas activas."),
) -> Page[MateriaPrimaResponse]:
    """Lista materias primas con paginacion."""
    offset = (page - 1) * page_size
    items, total = svc.listar_materias_primas(
        db,
        offset=offset,
        limit=page_size,
        solo_activos=solo_activos,
    )

    pages = (total + page_size - 1) // page_size

    return Page[MateriaPrimaResponse](
        items=[MateriaPrimaResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Obtener
# ---------------------------------------------------------------------------

@router.get(
    "/{materia_prima_id}",
    response_model=MateriaPrimaResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener una materia prima por ID",
)
def obtener_materia_prima(
    materia_prima_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> MateriaPrimaResponse:
    """Obtiene una materia prima por ID."""
    try:
        mp = svc.obtener_materia_prima(db, materia_prima_id)
    except svc.MateriaPrimaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Materia prima no encontrada.",
        )
    return MateriaPrimaResponse.model_validate(mp)


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=MateriaPrimaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una materia prima (solo ADMINISTRADOR)",
)
def crear_materia_prima(
    datos: MateriaPrimaCreate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> MateriaPrimaResponse:
    """Crea una materia prima."""
    try:
        mp = svc.crear_materia_prima(db, datos)
    except svc.MateriaPrimaDuplicadaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return MateriaPrimaResponse.model_validate(mp)


# ---------------------------------------------------------------------------
# Actualizar
# ---------------------------------------------------------------------------

@router.put(
    "/{materia_prima_id}",
    response_model=MateriaPrimaResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar una materia prima (solo ADMINISTRADOR)",
)
def actualizar_materia_prima(
    materia_prima_id: int,
    datos: MateriaPrimaUpdate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> MateriaPrimaResponse:
    """Actualiza una materia prima existente."""
    try:
        mp = svc.actualizar_materia_prima(db, materia_prima_id, datos)
    except svc.MateriaPrimaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Materia prima no encontrada.",
        )
    except svc.MateriaPrimaDuplicadaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return MateriaPrimaResponse.model_validate(mp)


# ---------------------------------------------------------------------------
# Desactivar
# ---------------------------------------------------------------------------

@router.delete(
    "/{materia_prima_id}",
    response_model=MateriaPrimaResponse,
    status_code=status.HTTP_200_OK,
    summary="Desactivar una materia prima (solo ADMINISTRADOR)",
)
def desactivar_materia_prima(
    materia_prima_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> MateriaPrimaResponse:
    """Desactiva una materia prima (soft delete)."""
    try:
        mp = svc.desactivar_materia_prima(db, materia_prima_id)
    except svc.MateriaPrimaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Materia prima no encontrada.",
        )
    return MateriaPrimaResponse.model_validate(mp)


# ---------------------------------------------------------------------------
# Reactivar
# ---------------------------------------------------------------------------

@router.post(
    "/{materia_prima_id}/reactivar",
    response_model=MateriaPrimaResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivar una materia prima (solo ADMINISTRADOR)",
)
def reactivar_materia_prima(
    materia_prima_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> MateriaPrimaResponse:
    """Reactiva una materia prima previamente desactivada."""
    try:
        mp = svc.reactivar_materia_prima(db, materia_prima_id)
    except svc.MateriaPrimaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Materia prima no encontrada.",
        )
    return MateriaPrimaResponse.model_validate(mp)