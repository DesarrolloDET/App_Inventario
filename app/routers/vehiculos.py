"""
Router del maestro VEHICULOS.

Endpoints:
- POST   /api/v1/vehiculos                 -> Crear (ADMINISTRADOR)
- GET    /api/v1/vehiculos                 -> Listar (autenticado)
- GET    /api/v1/vehiculos/{id}            -> Obtener (autenticado)
- PUT    /api/v1/vehiculos/{id}            -> Actualizar (ADMINISTRADOR)
- DELETE /api/v1/vehiculos/{id}            -> Desactivar (ADMINISTRADOR)
- POST   /api/v1/vehiculos/{id}/reactivar  -> Reactivar (ADMINISTRADOR)

Reglas aplicadas:
- Seccion 25: autorizacion en backend.
- Seccion 32: mensajes de error seguros.
- Seccion 40: routers delgados; la logica esta en el service.

Codigos de error:
- 400 Bad Request: transportadora referenciada invalida.
- 401 Unauthorized: token ausente/invalido (dependencias).
- 403 Forbidden: rol insuficiente.
- 404 Not Found: vehiculo no existe.
- 409 Conflict: placa duplicada.
- 422 Unprocessable Entity: validacion Pydantic.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, require_roles
from app.database.connection import get_db
from app.models.security import Usuario
from app.schemas.common import Page
from app.schemas.vehiculos import (
    VehiculoCreate,
    VehiculoResponse,
    VehiculoUpdate,
)
from app.services import vehiculos_service as svc


router = APIRouter(prefix="/vehiculos", tags=["vehiculos"])


# ---------------------------------------------------------------------------
# Listar
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=Page[VehiculoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar vehiculos con paginacion",
)
def listar_vehiculos(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1, description="Numero de pagina (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por pagina."),
    solo_activos: bool = Query(True, description="Si True, solo vehiculos activos."),
    transportadora_id: int | None = Query(
        None,
        ge=1,
        description="Opcional: filtra por transportadora.",
    ),
) -> Page[VehiculoResponse]:
    """Lista vehiculos con paginacion, opcionalmente filtrados por transportadora."""
    offset = (page - 1) * page_size
    items, total = svc.listar_vehiculos(
        db,
        offset=offset,
        limit=page_size,
        solo_activos=solo_activos,
        transportadora_id=transportadora_id,
    )

    pages = (total + page_size - 1) // page_size

    return Page[VehiculoResponse](
        items=[VehiculoResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Obtener
# ---------------------------------------------------------------------------

@router.get(
    "/{vehiculo_id}",
    response_model=VehiculoResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener un vehiculo por ID",
)
def obtener_vehiculo(
    vehiculo_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> VehiculoResponse:
    """Obtiene un vehiculo por ID."""
    try:
        v = svc.obtener_vehiculo(db, vehiculo_id)
    except svc.VehiculoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehiculo no encontrado.",
        )
    return VehiculoResponse.model_validate(v)


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=VehiculoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un vehiculo (solo ADMINISTRADOR)",
)
def crear_vehiculo(
    datos: VehiculoCreate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> VehiculoResponse:
    """Crea un vehiculo."""
    try:
        v = svc.crear_vehiculo(db, datos)
    except svc.VehiculoDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except svc.TransportadoraInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return VehiculoResponse.model_validate(v)


# ---------------------------------------------------------------------------
# Actualizar
# ---------------------------------------------------------------------------

@router.put(
    "/{vehiculo_id}",
    response_model=VehiculoResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un vehiculo (solo ADMINISTRADOR)",
)
def actualizar_vehiculo(
    vehiculo_id: int,
    datos: VehiculoUpdate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> VehiculoResponse:
    """Actualiza un vehiculo existente."""
    try:
        v = svc.actualizar_vehiculo(db, vehiculo_id, datos)
    except svc.VehiculoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehiculo no encontrado.",
        )
    except svc.VehiculoDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except svc.TransportadoraInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return VehiculoResponse.model_validate(v)


# ---------------------------------------------------------------------------
# Desactivar
# ---------------------------------------------------------------------------

@router.delete(
    "/{vehiculo_id}",
    response_model=VehiculoResponse,
    status_code=status.HTTP_200_OK,
    summary="Desactivar un vehiculo (solo ADMINISTRADOR)",
)
def desactivar_vehiculo(
    vehiculo_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> VehiculoResponse:
    """Desactiva un vehiculo (soft delete)."""
    try:
        v = svc.desactivar_vehiculo(db, vehiculo_id)
    except svc.VehiculoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehiculo no encontrado.",
        )
    return VehiculoResponse.model_validate(v)


# ---------------------------------------------------------------------------
# Reactivar
# ---------------------------------------------------------------------------

@router.post(
    "/{vehiculo_id}/reactivar",
    response_model=VehiculoResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivar un vehiculo (solo ADMINISTRADOR)",
)
def reactivar_vehiculo(
    vehiculo_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> VehiculoResponse:
    """Reactiva un vehiculo. La transportadora asociada debe estar activa."""
    try:
        v = svc.reactivar_vehiculo(db, vehiculo_id)
    except svc.VehiculoNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehiculo no encontrado.",
        )
    except svc.TransportadoraInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return VehiculoResponse.model_validate(v)