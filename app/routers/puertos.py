"""
Router del maestro PUERTOS.

Endpoints:
- POST   /api/v1/puertos                    -> Crear (ADMINISTRADOR)
- GET    /api/v1/puertos                    -> Listar (autenticado)
- GET    /api/v1/puertos/{id}               -> Obtener (autenticado)
- PUT    /api/v1/puertos/{id}               -> Actualizar (ADMINISTRADOR)
- DELETE /api/v1/puertos/{id}               -> Desactivar (ADMINISTRADOR)
- POST   /api/v1/puertos/{id}/reactivar     -> Reactivar (ADMINISTRADOR)

Reglas aplicadas:
- Seccion 25: autorizacion en backend.
- Seccion 32: mensajes de error seguros.
- Seccion 40: routers delgados; la logica esta en el service.

Convencion de errores:
- 400 Bad Request   -> datos invalidos (Pydantic ya cubre la mayoria).
- 401 Unauthorized  -> token ausente/invalido (dependencias).
- 403 Forbidden     -> rol insuficiente (require_roles).
- 404 Not Found     -> recurso no existe.
- 409 Conflict      -> duplicado (nombre ya en uso).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, require_roles
from app.database.connection import get_db
from app.models.security import Usuario
from app.schemas.common import Page
from app.schemas.puertos import PuertoCreate, PuertoResponse, PuertoUpdate
from app.services import puertos_service as svc


router = APIRouter(prefix="/puertos", tags=["puertos"])


# ---------------------------------------------------------------------------
# Listar
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=Page[PuertoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar puertos con paginacion",
)
def listar_puertos(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1, description="Numero de pagina (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por pagina."),
    solo_activos: bool = Query(True, description="Si True, solo puertos activos."),
) -> Page[PuertoResponse]:
    """Lista puertos con paginacion."""
    offset = (page - 1) * page_size
    items, total = svc.listar_puertos(
        db,
        offset=offset,
        limit=page_size,
        solo_activos=solo_activos,
    )

    pages = (total + page_size - 1) // page_size  # ceil

    return Page[PuertoResponse](
        items=[PuertoResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Obtener
# ---------------------------------------------------------------------------

@router.get(
    "/{puerto_id}",
    response_model=PuertoResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener un puerto por ID",
)
def obtener_puerto(
    puerto_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> PuertoResponse:
    """Obtiene un puerto por ID."""
    try:
        puerto = svc.obtener_puerto(db, puerto_id)
    except svc.PuertoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Puerto no encontrado.",
        )
    return PuertoResponse.model_validate(puerto)


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=PuertoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un puerto (solo ADMINISTRADOR)",
)
def crear_puerto(
    datos: PuertoCreate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> PuertoResponse:
    """Crea un puerto."""
    try:
        puerto = svc.crear_puerto(db, datos)
    except svc.PuertoDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return PuertoResponse.model_validate(puerto)


# ---------------------------------------------------------------------------
# Actualizar
# ---------------------------------------------------------------------------

@router.put(
    "/{puerto_id}",
    response_model=PuertoResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un puerto (solo ADMINISTRADOR)",
)
def actualizar_puerto(
    puerto_id: int,
    datos: PuertoUpdate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> PuertoResponse:
    """Actualiza un puerto existente."""
    try:
        puerto = svc.actualizar_puerto(db, puerto_id, datos)
    except svc.PuertoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Puerto no encontrado.",
        )
    except svc.PuertoDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return PuertoResponse.model_validate(puerto)


# ---------------------------------------------------------------------------
# Desactivar
# ---------------------------------------------------------------------------

@router.delete(
    "/{puerto_id}",
    response_model=PuertoResponse,
    status_code=status.HTTP_200_OK,
    summary="Desactivar un puerto (solo ADMINISTRADOR)",
)
def desactivar_puerto(
    puerto_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> PuertoResponse:
    """Desactiva un puerto (soft delete)."""
    try:
        puerto = svc.desactivar_puerto(db, puerto_id)
    except svc.PuertoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Puerto no encontrado.",
        )
    return PuertoResponse.model_validate(puerto)


# ---------------------------------------------------------------------------
# Reactivar
# ---------------------------------------------------------------------------

@router.post(
    "/{puerto_id}/reactivar",
    response_model=PuertoResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivar un puerto (solo ADMINISTRADOR)",
)
def reactivar_puerto(
    puerto_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> PuertoResponse:
    """Reactiva un puerto previamente desactivado."""
    try:
        puerto = svc.reactivar_puerto(db, puerto_id)
    except svc.PuertoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Puerto no encontrado.",
        )
    return PuertoResponse.model_validate(puerto)
