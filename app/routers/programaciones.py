"""
Router de PROGRAMACIONES y PROGRAMACION_DETALLE.

Endpoints de programaciones (cabecera):
- POST   /api/v1/programaciones                     -> Crear (ADMINISTRADOR)
- GET    /api/v1/programaciones                     -> Listar (autenticado)
- GET    /api/v1/programaciones/{id}                -> Obtener con detalles
- PUT    /api/v1/programaciones/{id}                -> Actualizar (ADMINISTRADOR, BORRADOR)
- POST   /api/v1/programaciones/{id}/publicar       -> Publicar (ADMINISTRADOR)
- POST   /api/v1/programaciones/{id}/cerrar         -> Cerrar (ADMINISTRADOR)
- POST   /api/v1/programaciones/{id}/cancelar       -> Cancelar (ADMINISTRADOR)

Endpoints de detalles:
- POST   /api/v1/programaciones/{id}/detalles       -> Crear detalle (ADMINISTRADOR)
- GET    /api/v1/programaciones/{id}/detalles       -> Listar detalles
- GET    /api/v1/programaciones/detalles/{det_id}   -> Obtener detalle
- PUT    /api/v1/programaciones/detalles/{det_id}   -> Actualizar detalle (ADMINISTRADOR, BORRADOR)
- DELETE /api/v1/programaciones/detalles/{det_id}   -> Eliminar detalle (ADMINISTRADOR, BORRADOR)

Reglas aplicadas:
- Seccion 6:  la programacion define la operacion.
- Seccion 25: autorizacion en backend.
- Seccion 40: routers delgados.

Codigos de error:
- 400: datos invalidos (rango de fechas, maestro inactivo, sin detalles).
- 401: token ausente/invalido.
- 403: rol insuficiente.
- 404: recurso no encontrado.
- 409: conflicto de estado, capacidad insuficiente, dependencia operativa.
- 422: validacion Pydantic.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, require_roles
from app.database.connection import get_db
from app.models.security import Usuario
from app.schemas.common import Page
from app.schemas.cupos import CupoResponse
from app.schemas.programacion_detalle import (
    ProgramacionDetalleCreate,
    ProgramacionDetalleResponse,
    ProgramacionDetalleUpdate,
)
from app.schemas.programaciones import (
    EstadoProgramacion,
    ProgramacionConDetallesResponse,
    ProgramacionCreate,
    ProgramacionResponse,
    ProgramacionUpdate,
)
from app.services import programacion_detalle_service as det_svc
from app.services import programaciones_service as svc


router = APIRouter(prefix="/programaciones", tags=["programaciones"])


# ---------------------------------------------------------------------------
# Helper para evitar duplicacion de mapeo de excepciones
# ---------------------------------------------------------------------------

def _map_err_comun(exc: Exception) -> HTTPException:
    """Traduce excepciones comunes del service a HTTPException."""
    if isinstance(exc, svc.ProgramacionNoEncontradaError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programacion no encontrada.",
        )
    if isinstance(exc, det_svc.DetalleNoEncontradoError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detalle no encontrado.",
        )
    if isinstance(exc, svc.ProgramacionNoModificableError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, det_svc.ProgramacionNoModificableError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, svc.TransicionEstadoInvalidaError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, svc.ProgramacionSinDetallesError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if isinstance(exc, det_svc.FechaFueraDeRangoError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if isinstance(exc, det_svc.MaestroInactivoError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if isinstance(exc, det_svc.CapacidadInsuficienteError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, det_svc.DependenciaOperativaError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    # Fallback: 500 (nunca deberia pasar si mapeamos todo).
    raise exc


# ===========================================================================
# PROGRAMACIONES (cabecera)
# ===========================================================================

# ---------------------------------------------------------------------------
# Listar
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=Page[ProgramacionResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar programaciones con paginacion y filtros",
)
def listar_programaciones(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1, description="Numero de pagina (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por pagina."),
    estado: EstadoProgramacion | None = Query(
        None, description="Filtra por estado de la programacion."
    ),
    fecha_desde: date | None = Query(
        None, description="Filtra programaciones con fecha_inicio >= fecha_desde."
    ),
    fecha_hasta: date | None = Query(
        None, description="Filtra programaciones con fecha_fin <= fecha_hasta."
    ),
) -> Page[ProgramacionResponse]:
    """Lista programaciones con paginacion y filtros opcionales."""
    # Validacion de coherencia de fechas.
    if fecha_desde is not None and fecha_hasta is not None:
        if fecha_desde > fecha_hasta:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="fecha_desde no puede ser posterior a fecha_hasta.",
            )

    offset = (page - 1) * page_size
    items, total = svc.listar_programaciones(
        db,
        offset=offset,
        limit=page_size,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    pages = (total + page_size - 1) // page_size

    return Page[ProgramacionResponse](
        items=[ProgramacionResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Obtener con detalles
# ---------------------------------------------------------------------------

@router.get(
    "/{programacion_id}",
    response_model=ProgramacionConDetallesResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener una programacion con sus detalles",
)
def obtener_programacion(
    programacion_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ProgramacionConDetallesResponse:
    """Obtiene una programacion con sus detalles."""
    try:
        prog = svc.obtener_programacion(db, programacion_id)
    except svc.ProgramacionNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programacion no encontrada.",
        )

    # Cargar cupos por detalle para el conteo.
    detalles_resp: list[ProgramacionDetalleResponse] = []
    for det in prog.detalles:
        cupos = det_svc.listar_cupos_de_detalle(db, det.programacion_detalle_id)
        resp = ProgramacionDetalleResponse.model_validate(det)
        resp.cupos_generados = len(cupos)
        detalles_resp.append(resp)

    return ProgramacionConDetallesResponse(
        programacion_id=prog.programacion_id,
        fecha_inicio=prog.fecha_inicio,
        fecha_fin=prog.fecha_fin,
        estado=prog.estado,
        usuario_creador_id=prog.usuario_creador_id,
        fecha_creacion=prog.fecha_creacion,
        detalles=detalles_resp,
    )


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ProgramacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una programacion en BORRADOR (solo ADMINISTRADOR)",
)
def crear_programacion(
    datos: ProgramacionCreate,
    usuario: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProgramacionResponse:
    """Crea una programacion en BORRADOR. El usuario creador se toma del token."""
    prog = svc.crear_programacion(db, datos, usuario_creador=usuario)
    return ProgramacionResponse.model_validate(prog)


# ---------------------------------------------------------------------------
# Actualizar
# ---------------------------------------------------------------------------

@router.put(
    "/{programacion_id}",
    response_model=ProgramacionResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar una programacion (solo ADMINISTRADOR, BORRADOR)",
)
def actualizar_programacion(
    programacion_id: int,
    datos: ProgramacionUpdate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProgramacionResponse:
    """Actualiza la cabecera de una programacion en BORRADOR."""
    try:
        prog = svc.actualizar_programacion(db, programacion_id, datos)
    except (
        svc.ProgramacionNoEncontradaError,
        svc.ProgramacionNoModificableError,
    ) as exc:
        raise _map_err_comun(exc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return ProgramacionResponse.model_validate(prog)


# ---------------------------------------------------------------------------
# Publicar
# ---------------------------------------------------------------------------

@router.post(
    "/{programacion_id}/publicar",
    response_model=ProgramacionResponse,
    status_code=status.HTTP_200_OK,
    summary="Publicar una programacion (solo ADMINISTRADOR)",
)
def publicar_programacion(
    programacion_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProgramacionResponse:
    """Publica una programacion en BORRADOR."""
    try:
        prog = svc.publicar_programacion(db, programacion_id)
    except (
        svc.ProgramacionNoEncontradaError,
        svc.TransicionEstadoInvalidaError,
        svc.ProgramacionSinDetallesError,
    ) as exc:
        raise _map_err_comun(exc)
    return ProgramacionResponse.model_validate(prog)


# ---------------------------------------------------------------------------
# Cerrar
# ---------------------------------------------------------------------------

@router.post(
    "/{programacion_id}/cerrar",
    response_model=ProgramacionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cerrar una programacion (solo ADMINISTRADOR)",
)
def cerrar_programacion(
    programacion_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProgramacionResponse:
    """Cierra una programacion en PUBLICADA."""
    try:
        prog = svc.cerrar_programacion(db, programacion_id)
    except (
        svc.ProgramacionNoEncontradaError,
        svc.TransicionEstadoInvalidaError,
    ) as exc:
        raise _map_err_comun(exc)
    return ProgramacionResponse.model_validate(prog)


# ---------------------------------------------------------------------------
# Cancelar
# ---------------------------------------------------------------------------

@router.post(
    "/{programacion_id}/cancelar",
    response_model=ProgramacionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar una programacion (solo ADMINISTRADOR)",
)
def cancelar_programacion(
    programacion_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProgramacionResponse:
    """Cancela una programacion en BORRADOR o PUBLICADA."""
    try:
        prog = svc.cancelar_programacion(db, programacion_id)
    except (
        svc.ProgramacionNoEncontradaError,
        svc.TransicionEstadoInvalidaError,
    ) as exc:
        raise _map_err_comun(exc)
    return ProgramacionResponse.model_validate(prog)


# ===========================================================================
# DETALLES (sub-recursos)
# ===========================================================================
# IMPORTANTE: las rutas /{programacion_id}/detalles y /detalles/{detalle_id}
# deben declararse DESPUES de las de programaciones individuales para que
# FastAPI no interprete "detalles" como un programacion_id. Se usa un
# router anidado para separar la logica.

detalles_router = APIRouter(prefix="/programaciones", tags=["programaciones - detalles"])


# ---------------------------------------------------------------------------
# Listar detalles de una programacion
# ---------------------------------------------------------------------------

@detalles_router.get(
    "/{programacion_id}/detalles",
    response_model=list[ProgramacionDetalleResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar los detalles de una programacion",
)
def listar_detalles(
    programacion_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[ProgramacionDetalleResponse]:
    """Lista los detalles de una programacion con el conteo de cupos."""
    try:
        detalles = det_svc.listar_detalles_de_programacion(db, programacion_id)
    except det_svc.ProgramacionNoModificableError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programacion no encontrada.",
        )

    respuestas = []
    for det in detalles:
        resp = ProgramacionDetalleResponse.model_validate(det)
        resp.cupos_generados = len(det.cupos)
        respuestas.append(resp)
    return respuestas


# ---------------------------------------------------------------------------
# Crear detalle
# ---------------------------------------------------------------------------

@detalles_router.post(
    "/{programacion_id}/detalles",
    response_model=ProgramacionDetalleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un detalle (solo ADMINISTRADOR, BORRADOR)",
)
def crear_detalle(
    programacion_id: int,
    datos: ProgramacionDetalleCreate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProgramacionDetalleResponse:
    """Crea un detalle y genera automaticamente sus cupos."""
    try:
        det = det_svc.crear_detalle(db, programacion_id, datos)
    except (
        det_svc.ProgramacionNoModificableError,
        det_svc.FechaFueraDeRangoError,
        det_svc.MaestroInactivoError,
        det_svc.CapacidadInsuficienteError,
    ) as exc:
        raise _map_err_comun(exc)

    cupos = det_svc.listar_cupos_de_detalle(db, det.programacion_detalle_id)
    resp = ProgramacionDetalleResponse.model_validate(det)
    resp.cupos_generados = len(cupos)
    return resp


# ---------------------------------------------------------------------------
# Obtener detalle
# ---------------------------------------------------------------------------

@detalles_router.get(
    "/detalles/{detalle_id}",
    response_model=ProgramacionDetalleResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener un detalle por ID",
)
def obtener_detalle(
    detalle_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ProgramacionDetalleResponse:
    """Obtiene un detalle por ID."""
    try:
        det = det_svc.obtener_detalle(db, detalle_id)
    except det_svc.DetalleNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detalle no encontrado.",
        )

    cupos = det_svc.listar_cupos_de_detalle(db, detalle_id)
    resp = ProgramacionDetalleResponse.model_validate(det)
    resp.cupos_generados = len(cupos)
    return resp


# ---------------------------------------------------------------------------
# Actualizar detalle
# ---------------------------------------------------------------------------

@detalles_router.put(
    "/detalles/{detalle_id}",
    response_model=ProgramacionDetalleResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un detalle (solo ADMINISTRADOR, BORRADOR)",
)
def actualizar_detalle(
    detalle_id: int,
    datos: ProgramacionDetalleUpdate,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProgramacionDetalleResponse:
    """Actualiza un detalle. Si cambian cantidad o fecha, regenera cupos."""
    try:
        det = det_svc.actualizar_detalle(db, detalle_id, datos)
    except (
        det_svc.DetalleNoEncontradoError,
        det_svc.ProgramacionNoModificableError,
        det_svc.FechaFueraDeRangoError,
        det_svc.MaestroInactivoError,
        det_svc.CapacidadInsuficienteError,
        det_svc.DependenciaOperativaError,
    ) as exc:
        raise _map_err_comun(exc)

    cupos = det_svc.listar_cupos_de_detalle(db, detalle_id)
    resp = ProgramacionDetalleResponse.model_validate(det)
    resp.cupos_generados = len(cupos)
    return resp


# ---------------------------------------------------------------------------
# Eliminar detalle
# ---------------------------------------------------------------------------

@detalles_router.delete(
    "/detalles/{detalle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un detalle (solo ADMINISTRADOR, BORRADOR)",
)
def eliminar_detalle(
    detalle_id: int,
    _: Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Elimina un detalle y sus cupos (hard delete en BORRADOR)."""
    try:
        det_svc.eliminar_detalle(db, detalle_id)
    except (
        det_svc.DetalleNoEncontradoError,
        det_svc.ProgramacionNoModificableError,
        det_svc.DependenciaOperativaError,
    ) as exc:
        raise _map_err_comun(exc)


# ---------------------------------------------------------------------------
# Cupos de un detalle
# ---------------------------------------------------------------------------

@detalles_router.get(
    "/detalles/{detalle_id}/cupos",
    response_model=list[CupoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar los cupos de un detalle",
)
def listar_cupos_de_detalle(
    detalle_id: int,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[CupoResponse]:
    """Lista los cupos generados para un detalle."""
    try:
        det_svc.obtener_detalle(db, detalle_id)
    except det_svc.DetalleNoEncontradoError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detalle no encontrado.",
        )

    cupos = det_svc.listar_cupos_de_detalle(db, detalle_id)
    return [CupoResponse.model_validate(c) for c in cupos]