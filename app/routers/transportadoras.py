"""
Router del maestro TRANSPORTADORAS.

Endpoints:
- POST   /api/v1/transportadoras                 -> Crear (ADMINISTRADOR)
- GET    /api/v1/transportadoras                 -> Listar (autenticado)
- GET    /api/v1/transportadoras/{id}            -> Obtener (autenticado)
- PUT    /api/v1/transportadoras/{id}            -> Actualizar (ADMINISTRADOR)
- DELETE /api/v1/transportadoras/{id}            -> Desactivar (ADMINISTRADOR)
- POST   /api/v1/transportadoras/{id}/reactivar  -> Reactivar (ADMINISTRADOR)

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
from app.schemas.transportadoras import (
    TransportadoraCreate,
    TransportadoraResponse,
    TransportadoraUpdate,
)
from app.services import transportadoras_service as svc


router = APIRouter(prefix="/transportadoras", tags=["transportadoras"])


# ---------------------------------------------------------------------------
# Listar
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=Page[TransportadoraResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar transportadoras con paginacion",
)
def listar_transportadoras(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1, description="Numero de pagina (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por pagina."),
    solo_activos: bool = Query(True, description="Si True, solo transportadoras activas."),
) -> Page[TransportadoraResponse]:
    """Lista transportadoras con paginacion."""
    offset = (page - 1) * page_size
    items, total = svc.listar_transportadoras(
        db,
        offset=offset,
        limit=page_size,
        solo_activos=solo_activos,
    )

    pages = (total + page_size - 1) // page_size

    return Page[TransportadoraResponse](
        items=[TransportadoraResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Obtener
# ---------------------------------------------------------------------------

@router.get(
    "/{transportadora_id}",
    response_model=TransportadoraResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener una transportadora por ID",
)
def obtener_transportadora(
    transportadora_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TransportadoraResponse:
    """Obtiene una transportadora por ID."""
    try:
        t = svc.obtener_transportadora(db, transportadora_id)
    except svc.TransportadoraNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transportadora no encontrada.",
        )
    return TransportadoraResponse.model_validate(t)


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=TransportadoraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una transportadora (solo ADMINISTRADOR)",
)
def crear_transportadora(
    datos: TransportadoraCreate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> TransportadoraResponse:
    """Crea una transportadora."""
    try:
        t = svc.crear_transportadora(db, datos)
    except svc.TransportadoraDuplicadaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return TransportadoraResponse.model_validate(t)


# ---------------------------------------------------------------------------
# Actualizar
# ---------------------------------------------------------------------------

@router.put(
    "/{transportadora_id}",
    response_model=TransportadoraResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar una transportadora (solo ADMINISTRADOR)",
)
def actualizar_transportadora(
    transportadora_id: int,
    datos: TransportadoraUpdate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> TransportadoraResponse:
    """Actualiza una transportadora existente."""
    try:
        t = svc.actualizar_transportadora(db, transportadora_id, datos)
    except svc.TransportadoraNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transportadora no encontrada.",
        )
    except svc.TransportadoraDuplicadaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return TransportadoraResponse.model_validate(t)


# ---------------------------------------------------------------------------
# Desactivar
# ---------------------------------------------------------------------------

@router.delete(
    "/{transportadora_id}",
    response_model=TransportadoraResponse,
    status_code=status.HTTP_200_OK,
    summary="Desactivar una transportadora (solo ADMINISTRADOR)",
)
def desactivar_transportadora(
    transportadora_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> TransportadoraResponse:
    """Desactiva una transportadora (soft delete)."""
    try:
        t = svc.desactivar_transportadora(db, transportadora_id)
    except svc.TransportadoraNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transportadora no encontrada.",
        )
    return TransportadoraResponse.model_validate(t)


# ---------------------------------------------------------------------------
# Reactivar
# ---------------------------------------------------------------------------

@router.post(
    "/{transportadora_id}/reactivar",
    response_model=TransportadoraResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivar una transportadora (solo ADMINISTRADOR)",
)
def reactivar_transportadora(
    transportadora_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> TransportadoraResponse:
    """Reactiva una transportadora previamente desactivada."""
    try:
        t = svc.reactivar_transportadora(db, transportadora_id)
    except svc.TransportadoraNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transportadora no encontrada.",
        )
    return TransportadoraResponse.model_validate(t)