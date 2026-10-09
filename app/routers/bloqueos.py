"""
Router del maestro BLOQUEOS HORARIOS.

Endpoints:
- POST   /api/v1/bloqueos                    -> Crear (ADMINISTRADOR)
- GET    /api/v1/bloqueos                    -> Listar (autenticado)
- GET    /api/v1/bloqueos/por-fecha          -> Listar por fecha (autenticado)
- GET    /api/v1/bloqueos/{id}               -> Obtener (autenticado)
- PUT    /api/v1/bloqueos/{id}               -> Actualizar (ADMINISTRADOR)
- DELETE /api/v1/bloqueos/{id}               -> Desactivar (ADMINISTRADOR)
- POST   /api/v1/bloqueos/{id}/reactivar     -> Reactivar (ADMINISTRADOR)

Reglas aplicadas:
- Seccion 25: autorizacion en backend.
- Seccion 32: mensajes de error seguros.
- Seccion 40: routers delgados.

Codigos de error:
- 400 Bad Request: rango invalido (hora_fin <= hora_inicio).
- 401 Unauthorized: token ausente/invalido.
- 403 Forbidden: rol insuficiente.
- 404 Not Found: bloqueo no existe.
- 409 Conflict: solapamiento con otro bloqueo activo.
- 422 Unprocessable Entity: validacion Pydantic.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, require_roles
from app.database.connection import get_db
from app.models.security import Usuario
from app.schemas.bloqueos import (
    BloqueoCreate,
    BloqueoResponse,
    BloqueoUpdate,
)
from app.schemas.common import Page
from app.services import bloqueos_service as svc


router = APIRouter(prefix="/bloqueos", tags=["bloqueos"])


# ---------------------------------------------------------------------------
# Listar (paginado)
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=Page[BloqueoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar bloqueos con paginacion",
)
def listar_bloqueos(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1, description="Numero de pagina (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por pagina."),
    solo_activos: bool = Query(True, description="Si True, solo bloqueos activos."),
) -> Page[BloqueoResponse]:
    """Lista bloqueos con paginacion."""
    offset = (page - 1) * page_size
    items, total = svc.listar_bloqueos(
        db,
        offset=offset,
        limit=page_size,
        solo_activos=solo_activos,
    )

    pages = (total + page_size - 1) // page_size

    return Page[BloqueoResponse](
        items=[BloqueoResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Listar por fecha (sin paginar)
# ---------------------------------------------------------------------------
# IMPORTANTE: este endpoint va ANTES de /{bloqueo_id} para que FastAPI no
# interprete "por-fecha" como un bloqueo_id.
# ---------------------------------------------------------------------------

@router.get(
    "/por-fecha",
    response_model=list[BloqueoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar todos los bloqueos de una fecha",
)
def listar_bloqueos_por_fecha(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    fecha: date = Query(..., description="Fecha en formato YYYY-MM-DD."),
    solo_activos: bool = Query(True, description="Si True, solo bloqueos activos."),
) -> list[BloqueoResponse]:
    """Lista todos los bloqueos (sin paginar) de una fecha especifica."""
    items = svc.listar_bloqueos_por_fecha(db, fecha, solo_activos=solo_activos)
    return [BloqueoResponse.model_validate(i) for i in items]


# ---------------------------------------------------------------------------
# Obtener
# ---------------------------------------------------------------------------

@router.get(
    "/{bloqueo_id}",
    response_model=BloqueoResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener un bloqueo por ID",
)
def obtener_bloqueo(
    bloqueo_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> BloqueoResponse:
    """Obtiene un bloqueo por ID."""
    try:
        b = svc.obtener_bloqueo(db, bloqueo_id)
    except svc.BloqueoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bloqueo no encontrado.",
        )
    return BloqueoResponse.model_validate(b)


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=BloqueoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un bloqueo (solo ADMINISTRADOR)",
)
def crear_bloqueo(
    datos: BloqueoCreate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> BloqueoResponse:
    """Crea un bloqueo horario."""
    try:
        b = svc.crear_bloqueo(db, datos)
    except svc.RangoInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except svc.BloqueoSolapadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return BloqueoResponse.model_validate(b)


# ---------------------------------------------------------------------------
# Actualizar
# ---------------------------------------------------------------------------

@router.put(
    "/{bloqueo_id}",
    response_model=BloqueoResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un bloqueo (solo ADMINISTRADOR)",
)
def actualizar_bloqueo(
    bloqueo_id: int,
    datos: BloqueoUpdate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> BloqueoResponse:
    """Actualiza un bloqueo existente."""
    try:
        b = svc.actualizar_bloqueo(db, bloqueo_id, datos)
    except svc.BloqueoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bloqueo no encontrado.",
        )
    except svc.RangoInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except svc.BloqueoSolapadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return BloqueoResponse.model_validate(b)


# ---------------------------------------------------------------------------
# Desactivar
# ---------------------------------------------------------------------------

@router.delete(
    "/{bloqueo_id}",
    response_model=BloqueoResponse,
    status_code=status.HTTP_200_OK,
    summary="Desactivar un bloqueo (solo ADMINISTRADOR)",
)
def desactivar_bloqueo(
    bloqueo_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> BloqueoResponse:
    """Desactiva un bloqueo (soft delete)."""
    try:
        b = svc.desactivar_bloqueo(db, bloqueo_id)
    except svc.BloqueoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bloqueo no encontrado.",
        )
    return BloqueoResponse.model_validate(b)


# ---------------------------------------------------------------------------
# Reactivar
# ---------------------------------------------------------------------------

@router.post(
    "/{bloqueo_id}/reactivar",
    response_model=BloqueoResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivar un bloqueo (solo ADMINISTRADOR)",
)
def reactivar_bloqueo(
    bloqueo_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> BloqueoResponse:
    """Reactiva un bloqueo. Falla si se solapa con otro activo."""
    try:
        b = svc.reactivar_bloqueo(db, bloqueo_id)
    except svc.BloqueoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bloqueo no encontrado.",
        )
    except svc.BloqueoSolapadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return BloqueoResponse.model_validate(b)