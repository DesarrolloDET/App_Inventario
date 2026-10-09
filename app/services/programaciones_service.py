"""
Service de PROGRAMACIONES (cabecera).

Contiene las reglas de negocio de la cabecera:
- Listar con paginacion y filtro de estado.
- Obtener una con sus detalles.
- Crear (estado inicial BORRADOR).
- Actualizar (solo en BORRADOR).
- Publicar (BORRADOR -> PUBLICADA).
- Cerrar (PUBLICADA -> CERRADA).
- Cancelar (BORRADOR/PUBLICADA -> CANCELADA).

NO contiene:
- Generacion de cupos (eso vive en programacion_detalle_service).
- Logica HTTP (eso va en app.routers.programaciones).

Reglas aplicadas:
- Seccion 6:  la programacion define la operacion de un rango de fechas.
- Seccion 40: reglas de negocio en services.
- Seccion 51: no eliminar historia; los cambios de estado son definitivos.

Maquina de estados:
    BORRADOR -> PUBLICADA -> CERRADA
        \\         /
         \\       /
          v     v
         CANCELADA

Transiciones permitidas:
- BORRADOR -> PUBLICADA (requiere al menos 1 detalle).
- BORRADOR -> CANCELADA.
- PUBLICADA -> CERRADA.
- PUBLICADA -> CANCELADA.
- Cualquier otra -> TransicionEstadoInvalidaError.

Notas:
- 'actualizar' solo funciona en BORRADOR. En PUBLICADA/CERRADA/CANCELADA,
  se rechaza con ProgramacionNoModificableError.
- En la Fase 6 se agregara un decorador @auditar(...).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from datetime import date

from app.models.programming import Programacion, ProgramacionDetalle
from app.models.security import Usuario
from app.schemas.programaciones import (
    EstadoProgramacion,
    ProgramacionCreate,
    ProgramacionUpdate,
)


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class ProgramacionError(Exception):
    """Error base del service de programaciones."""


class ProgramacionNoEncontradaError(ProgramacionError):
    """La programacion solicitada no existe."""


class TransicionEstadoInvalidaError(ProgramacionError):
    """La transicion de estado solicitada no es valida."""


class ProgramacionNoModificableError(ProgramacionError):
    """La programacion no se puede modificar en su estado actual."""


class ProgramacionSinDetallesError(ProgramacionError):
    """La programacion no tiene detalles y no se puede publicar."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cargar_con_detalles(db: Session, programacion_id: int) -> Programacion:
    """
    Carga una programacion con sus detalles ansiosamente.

    Uso interno para evitar lazy loading despues de cerrar la sesion.
    """
    programacion = db.execute(
        select(Programacion)
        .options(selectinload(Programacion.detalles))
        .where(Programacion.programacion_id == programacion_id)
    ).scalar_one_or_none()

    if programacion is None:
        raise ProgramacionNoEncontradaError(
            f"Programacion {programacion_id} no encontrada."
        )
    return programacion


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def listar_programaciones(
    db: Session,
    *,
    offset: int,
    limit: int,
    estado: EstadoProgramacion | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> tuple[list[Programacion], int]:
    """
    Lista programaciones con paginacion y filtros opcionales.

    Args:
        db: sesion SQLAlchemy.
        offset: registros a saltar.
        limit: cantidad maxima a devolver.
        estado: si se especifica, filtra por estado.
        fecha_desde: si se especifica, incluye programaciones cuya
                     fecha_inicio >= fecha_desde.
        fecha_hasta: si se especifica, incluye programaciones cuya
                     fecha_fin <= fecha_hasta.

    Returns:
        (items, total): items de la pagina actual y total del universo.
    """
    base = select(Programacion)

    if estado is not None:
        base = base.where(Programacion.estado == estado.value)

    if fecha_desde is not None:
        base = base.where(Programacion.fecha_inicio >= fecha_desde)

    if fecha_hasta is not None:
        base = base.where(Programacion.fecha_fin <= fecha_hasta)

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    items = list(
        db.execute(
            base.order_by(Programacion.programacion_id.desc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
    )

    return items, total


def obtener_programacion(db: Session, programacion_id: int) -> Programacion:
    """
    Obtiene una programacion con sus detalles.

    Raises:
        ProgramacionNoEncontradaError: si no existe.
    """
    return _cargar_con_detalles(db, programacion_id)


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def crear_programacion(
    db: Session,
    datos: ProgramacionCreate,
    usuario_creador: Usuario,
) -> Programacion:
    """
    Crea una programacion en estado BORRADOR.

    Args:
        db: sesion.
        datos: ProgramacionCreate validado.
        usuario_creador: usuario autenticado que crea la programacion.

    Returns:
        La Programacion creada.

    Notas:
        - El estado inicial es BORRADOR.
        - La programacion NO tiene detalles al crear. Se agregan despues
          via el service de detalles.
    """
    programacion = Programacion(
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        estado=EstadoProgramacion.BORRADOR.value,
        usuario_creador_id=usuario_creador.usuario_id,
    )
    db.add(programacion)
    db.flush()
    return programacion


def actualizar_programacion(
    db: Session,
    programacion_id: int,
    datos: ProgramacionUpdate,
) -> Programacion:
    """
    Actualiza la cabecera de una programacion.

    Solo permitido en estado BORRADOR.

    Raises:
        ProgramacionNoEncontradaError: si no existe.
        ProgramacionNoModificableError: si no esta en BORRADOR.
        ValueError: si el nuevo rango es invalido.
    """
    programacion = _cargar_con_detalles(db, programacion_id)

    if programacion.estado != EstadoProgramacion.BORRADOR.value:
        raise ProgramacionNoModificableError(
            f"La programacion esta en estado {programacion.estado} "
            f"y no se puede modificar."
        )

    # Merge de campos.
    nueva_inicio = (
        datos.fecha_inicio
        if datos.fecha_inicio is not None
        else programacion.fecha_inicio
    )
    nueva_fin = (
        datos.fecha_fin
        if datos.fecha_fin is not None
        else programacion.fecha_fin
    )

    if nueva_fin < nueva_inicio:
        raise ValueError(
            "fecha_fin debe ser mayor o igual a fecha_inicio."
        )

    # Validacion adicional: si hay detalles, sus fechas deben seguir
    # dentro del nuevo rango.
    for detalle in programacion.detalles:
        if not (nueva_inicio <= detalle.fecha_operacion <= nueva_fin):
            raise ValueError(
                f"La fecha del detalle {detalle.programacion_detalle_id} "
                f"({detalle.fecha_operacion}) queda fuera del nuevo rango "
                f"[{nueva_inicio}, {nueva_fin}]."
            )

    programacion.fecha_inicio = nueva_inicio
    programacion.fecha_fin = nueva_fin

    db.flush()
    return programacion


# ---------------------------------------------------------------------------
# Transiciones de estado
# ---------------------------------------------------------------------------

def publicar_programacion(db: Session, programacion_id: int) -> Programacion:
    """
    Publica una programacion (BORRADOR -> PUBLICADA).

    Reglas:
        - La programacion debe estar en BORRADOR.
        - Debe tener al menos un detalle.

    Raises:
        ProgramacionNoEncontradaError: si no existe.
        TransicionEstadoInvalidaError: si no esta en BORRADOR.
        ProgramacionSinDetallesError: si no tiene detalles.
    """
    programacion = _cargar_con_detalles(db, programacion_id)

    if programacion.estado != EstadoProgramacion.BORRADOR.value:
        raise TransicionEstadoInvalidaError(
            f"Solo se puede publicar una programacion en BORRADOR "
            f"(actual: {programacion.estado})."
        )

    if not programacion.detalles:
        raise ProgramacionSinDetallesError(
            "La programacion no tiene detalles y no se puede publicar."
        )

    programacion.estado = EstadoProgramacion.PUBLICADA.value
    db.flush()
    return programacion


def cerrar_programacion(db: Session, programacion_id: int) -> Programacion:
    """
    Cierra una programacion (PUBLICADA -> CERRADA).

    En el MVP, se cierra sin mas validaciones porque aun no existen
    citas. En la Fase 4 se agregara la validacion de que todas las citas
    asociadas esten FINALIZADA, CANCELADA o NO_SHOW.

    Raises:
        ProgramacionNoEncontradaError: si no existe.
        TransicionEstadoInvalidaError: si no esta en PUBLICADA.
    """
    programacion = _cargar_con_detalles(db, programacion_id)

    if programacion.estado != EstadoProgramacion.PUBLICADA.value:
        raise TransicionEstadoInvalidaError(
            f"Solo se puede cerrar una programacion en PUBLICADA "
            f"(actual: {programacion.estado})."
        )

    programacion.estado = EstadoProgramacion.CERRADA.value
    db.flush()
    return programacion


def cancelar_programacion(db: Session, programacion_id: int) -> Programacion:
    """
    Cancela una programacion (BORRADOR/PUBLICADA -> CANCELADA).

    En el MVP, se cancela sin mas validaciones porque aun no existen
    citas. En la Fase 4 se agregara la validacion de que no haya citas
    CONFIRMADA o EN_PROCESO.

    Raises:
        ProgramacionNoEncontradaError: si no existe.
        TransicionEstadoInvalidaError: si esta CERRADA o ya CANCELADA.
    """
    programacion = _cargar_con_detalles(db, programacion_id)

    estados_que_se_pueden_cancelar = {
        EstadoProgramacion.BORRADOR.value,
        EstadoProgramacion.PUBLICADA.value,
    }
    if programacion.estado not in estados_que_se_pueden_cancelar:
        raise TransicionEstadoInvalidaError(
            f"No se puede cancelar una programacion en estado "
            f"{programacion.estado}."
        )

    programacion.estado = EstadoProgramacion.CANCELADA.value
    db.flush()
    return programacion