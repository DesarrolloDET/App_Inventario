"""
Router del maestro CONDUCTORES.

Endpoints:
- POST   /api/v1/conductores                 -> Crear (ADMINISTRADOR)
- GET    /api/v1/conductores                 -> Listar (autenticado)
- GET    /api/v1/conductores/{id}            -> Obtener (autenticado)
- PUT    /api/v1/conductores/{id}            -> Actualizar (ADMINISTRADOR)
- DELETE /api/v1/conductores/{id}            -> Desactivar (ADMINISTRADOR)
- POST   /api/v1/conductores/{id}/reactivar  -> Reactivar (ADMINISTRADOR)

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
from app.schemas.conductores import (
    ConductorCreate,
    ConductorResponse,
    ConductorUpdate,
)
from app.services import conductores_service as svc


router = APIRouter(prefix="/conductores", tags=["conductores"])


# ---------------------------------------------------------------------------
# Listar
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=Page[ConductorResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar conductores con paginacion",
)
def listar_conductores(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1, description="Numero de pagina (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por pagina."),
    solo_activos: bool = Query(True, description="Si True, solo conductores activos."),
) -> Page[ConductorResponse]:
    """Lista conductores con paginacion."""
    offset = (page - 1) * page_size
    items, total = svc.listar_conductores(
        db,
        offset=offset,
        limit=page_size,
        solo_activos=solo_activos,
    )

    pages = (total + page_size - 1) // page_size

    return Page[ConductorResponse](
        items=[ConductorResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Obtener
# ---------------------------------------------------------------------------

@router.get(
    "/{conductor_id}",
    response_model=ConductorResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener un conductor por ID",
)
def obtener_conductor(
    conductor_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ConductorResponse:
    """Obtiene un conductor por ID."""
    try:
        conductor = svc.obtener_conductor(db, conductor_id)
    except svc.ConductorNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conductor no encontrado.",
        )
    return ConductorResponse.model_validate(conductor)


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ConductorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un conductor (solo ADMINISTRADOR)",
)
def crear_conductor(
    datos: ConductorCreate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ConductorResponse:
    """Crea un conductor."""
    try:
        conductor = svc.crear_conductor(db, datos)
    except svc.ConductorDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return ConductorResponse.model_validate(conductor)


# ---------------------------------------------------------------------------
# Actualizar
# ---------------------------------------------------------------------------

@router.put(
    "/{conductor_id}",
    response_model=ConductorResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un conductor (solo ADMINISTRADOR)",
)
def actualizar_conductor(
    conductor_id: int,
    datos: ConductorUpdate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ConductorResponse:
    """Actualiza un conductor existente."""
    try:
        conductor = svc.actualizar_conductor(db, conductor_id, datos)
    except svc.ConductorNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conductor no encontrado.",
        )
    except svc.ConductorDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return ConductorResponse.model_validate(conductor)


# ---------------------------------------------------------------------------
# Desactivar
# ---------------------------------------------------------------------------

@router.delete(
    "/{conductor_id}",
    response_model=ConductorResponse,
    status_code=status.HTTP_200_OK,
    summary="Desactivar un conductor (solo ADMINISTRADOR)",
)
def desactivar_conductor(
    conductor_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ConductorResponse:
    """Desactiva un conductor (soft delete)."""
    try:
        conductor = svc.desactivar_conductor(db, conductor_id)
    except svc.ConductorNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conductor no encontrado.",
        )
    return ConductorResponse.model_validate(conductor)


# ---------------------------------------------------------------------------
# Reactivar
# ---------------------------------------------------------------------------

@router.post(
    "/{conductor_id}/reactivar",
    response_model=ConductorResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivar un conductor (solo ADMINISTRADOR)",
)
def reactivar_conductor(
    conductor_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ConductorResponse:
    """Reactiva un conductor previamente desactivado."""
    try:
        conductor = svc.reactivar_conductor(db, conductor_id)
    except svc.ConductorNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conductor no encontrado.",
        )
    return ConductorResponse.model_validate(conductor)