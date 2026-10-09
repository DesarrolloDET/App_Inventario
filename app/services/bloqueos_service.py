"""
Service del maestro BLOQUEOS HORARIOS.

Contiene las reglas de negocio:
- Listar con paginacion y filtro de activo.
- Listar por fecha (endpoint especial).
- Obtener uno.
- Crear (validando solapamiento con otros bloqueos activos).
- Actualizar (validando solapamiento si cambian fecha/horas).
- Desactivar (soft delete).
- Reactivar (verificando que no genere solapamiento con bloqueos activos).

Reglas aplicadas:
- Seccion 8:  los bloqueos son operativos de Mejia.
- Seccion 31: validacion de intervalos y duplicados.
- Seccion 40: reglas de negocio en services.

Concurrencia:
- La validacion de solapamiento se hace en el service (Nivel 1).
- NO hay constraint a nivel BD que impida solapamiento.
- Se documenta la ventana de concurrencia: dos transacciones
  simultaneas podrian pasar la validacion e insertar ambas. En un
  sistema interno con baja concurrencia, esto es aceptable.
- Si en produccion se detecta, se puede migrar a un EXCLUDE constraint
  de PostgreSQL.

En la Fase 6 se agregara un decorador @auditar(...).
"""

from __future__ import annotations

from datetime import date, time
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.programming import BloqueoHorario
from app.schemas.bloqueos import BloqueoCreate, BloqueoUpdate, TipoBloqueo



# ---------------------------------------------------------------------------
# Excepciones propias del service
# ---------------------------------------------------------------------------

class BloqueoError(Exception):
    """Error base del service de bloqueos."""


class BloqueoNoEncontradoError(BloqueoError):
    """El bloqueo solicitado no existe."""


class BloqueoSolapadoError(BloqueoError):
    """El bloqueo se solapa con otro bloqueo activo en la misma fecha."""


class RangoInvalidoError(BloqueoError):
    """El rango horario es invalido (hora_fin <= hora_inicio)."""

class BloqueoProtegidoError(BloqueoError):
    """El bloqueo es obligatorio (ALMUERZO) y no se puede modificar ni desactivar."""    


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _rangos_solapan(
    h1_inicio: time, h1_fin: time,
    h2_inicio: time, h2_fin: time,
) -> bool:
    """
    Devuelve True si dos rangos [inicio, fin) se solapan.

    Intervalos semiabiertos:
        12:00-13:00 NO se solapa con 13:00-14:00.
        12:00-13:00 SI se solapa con 12:30-13:30.
    """
    return h1_inicio < h2_fin and h2_inicio < h1_fin


def _buscar_solapamiento(
    db: Session,
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
    excluir_id: int | None = None,
) -> BloqueoHorario | None:
    """
    Busca un bloqueo activo que se solape con el rango indicado.

    Solo considera bloqueos en la misma fecha y activos.
    Si 'excluir_id' se especifica, ignora ese bloqueo (para updates).
    """
    stmt = (
        select(BloqueoHorario)
        .where(BloqueoHorario.fecha == fecha)
        .where(BloqueoHorario.activo.is_(True))
        .where(BloqueoHorario.hora_inicio < hora_fin)
        .where(hora_inicio < BloqueoHorario.hora_fin)
    )
    if excluir_id is not None:
        stmt = stmt.where(BloqueoHorario.bloqueo_id != excluir_id)

    return db.execute(stmt).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def listar_bloqueos(
    db: Session,
    *,
    offset: int,
    limit: int,
    solo_activos: bool = True,
) -> tuple[list[BloqueoHorario], int]:
    """
    Lista bloqueos con paginacion.

    Returns:
        (items, total): items de la pagina y total del universo.
    """
    base = select(BloqueoHorario)

    if solo_activos:
        base = base.where(BloqueoHorario.activo.is_(True))

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    items = list(
        db.execute(
            base.order_by(
                BloqueoHorario.fecha.asc(),
                BloqueoHorario.hora_inicio.asc(),
            )
            .offset(offset)
            .limit(limit)
        ).scalars().all()
    )

    return items, total


def listar_bloqueos_por_fecha(
    db: Session,
    fecha: date,
    *,
    solo_activos: bool = True,
) -> list[BloqueoHorario]:
    """
    Lista TODOS los bloqueos de una fecha especifica (sin paginar).

    Uso tipico: el frontend consulta los bloqueos de un dia antes de
    mostrar las franjas disponibles al cliente.
    """
    stmt = (
        select(BloqueoHorario)
        .where(BloqueoHorario.fecha == fecha)
        .order_by(BloqueoHorario.hora_inicio.asc())
    )
    if solo_activos:
        stmt = stmt.where(BloqueoHorario.activo.is_(True))

    return list(db.execute(stmt).scalars().all())


def obtener_bloqueo(db: Session, bloqueo_id: int) -> BloqueoHorario:
    """
    Obtiene un bloqueo por ID.

    Raises:
        BloqueoNoEncontradoError: si no existe.
    """
    b = db.get(BloqueoHorario, bloqueo_id)
    if b is None:
        raise BloqueoNoEncontradoError(
            f"Bloqueo {bloqueo_id} no encontrado."
        )
    return b


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def crear_bloqueo(db: Session, datos: BloqueoCreate) -> BloqueoHorario:
    """
    Crea un bloqueo.

    Raises:
        RangoInvalidoError: si hora_fin <= hora_inicio.
        BloqueoSolapadoError: si se solapa con otro bloqueo activo.
    """
    if datos.hora_fin <= datos.hora_inicio:
        raise RangoInvalidoError(
            "hora_fin debe ser estrictamente mayor que hora_inicio."
        )

    solapado = _buscar_solapamiento(
        db,
        fecha=datos.fecha,
        hora_inicio=datos.hora_inicio,
        hora_fin=datos.hora_fin,
    )
    if solapado is not None:
        raise BloqueoSolapadoError(
            f"El bloqueo se solapa con el bloqueo {solapado.bloqueo_id} "
            f"({solapado.hora_inicio}-{solapado.hora_fin}, "
            f"tipo={solapado.tipo_bloqueo})."
        )

    b = BloqueoHorario(
        fecha=datos.fecha,
        hora_inicio=datos.hora_inicio,
        hora_fin=datos.hora_fin,
        tipo_bloqueo=datos.tipo_bloqueo.value,
        descripcion=datos.descripcion,
        activo=True,
    )
    db.add(b)
    db.flush()
    return b


def actualizar_bloqueo(
    db: Session,
    bloqueo_id: int,
    datos: BloqueoUpdate,
) -> BloqueoHorario:
    """
    Actualiza un bloqueo.

    Raises:
        BloqueoNoEncontradoError: si no existe.
        RangoInvalidoError: si hora_fin <= hora_inicio (tras merge).
        BloqueoSolapadoError: si el nuevo rango se solapa con otro activo.
    """
    b = obtener_bloqueo(db, bloqueo_id)

    if b.tipo_bloqueo == TipoBloqueo.ALMUERZO.value:
        raise BloqueoProtegidoError(
            "El bloqueo de almuerzo es obligatorio y no se puede modificar."
        )

    # Merge de campos.
    nueva_fecha = datos.fecha if datos.fecha is not None else b.fecha
    nueva_ini = datos.hora_inicio if datos.hora_inicio is not None else b.hora_inicio
    nueva_fin = datos.hora_fin if datos.hora_fin is not None else b.hora_fin

    if nueva_fin <= nueva_ini:
        raise RangoInvalidoError(
            "hora_fin debe ser estrictamente mayor que hora_inicio."
        )

    # Solo verificar solapamiento si cambia fecha u horas.
    cambio_rango = (
        nueva_fecha != b.fecha
        or nueva_ini != b.hora_inicio
        or nueva_fin != b.hora_fin
    )
    if cambio_rango:
        solapado = _buscar_solapamiento(
            db,
            fecha=nueva_fecha,
            hora_inicio=nueva_ini,
            hora_fin=nueva_fin,
            excluir_id=bloqueo_id,
        )
        if solapado is not None:
            raise BloqueoSolapadoError(
                f"El bloqueo se solapa con el bloqueo {solapado.bloqueo_id}."
            )

    b.fecha = nueva_fecha
    b.hora_inicio = nueva_ini
    b.hora_fin = nueva_fin

    if datos.tipo_bloqueo is not None:
        b.tipo_bloqueo = datos.tipo_bloqueo.value

    if datos.descripcion is not None:
        b.descripcion = datos.descripcion

    db.flush()
    return b


def desactivar_bloqueo(db: Session, bloqueo_id: int) -> BloqueoHorario:
    """
    Desactiva un bloqueo (soft delete). Idempotente.

    Nota: si hay citas confirmadas o procesos en curso dentro del rango
    afectado, esta operacion NO las toca. La validacion se hara en la
    Fase 4 (creacion de citas) al consultar bloqueos activos.

    Raises:
        BloqueoNoEncontradoError: si no existe.
    """
    b = obtener_bloqueo(db, bloqueo_id)

    if b.tipo_bloqueo == TipoBloqueo.ALMUERZO.value:
        raise BloqueoProtegidoError(
            "El bloqueo de almuerzo es obligatorio y no se puede desactivar."
    )

    b.activo = False
    db.flush()
    return b


def reactivar_bloqueo(db: Session, bloqueo_id: int) -> BloqueoHorario:
    """
    Reactiva un bloqueo. Verifica que no se solape con otros activos.

    Raises:
        BloqueoNoEncontradoError: si no existe.
        BloqueoSolapadoError: si al reactivar se produce solapamiento.
    """
    b = obtener_bloqueo(db, bloqueo_id)

    if b.tipo_bloqueo == TipoBloqueo.ALMUERZO.value:
        raise BloqueoProtegidoError(
            "El bloqueo de almuerzo es obligatorio y no se puede reactivar "
            "(nunca deberia estar inactivo)."
        )


    # Al reactivar, otros bloqueos activos podrian solaparse.
    solapado = _buscar_solapamiento(
        db,
        fecha=b.fecha,
        hora_inicio=b.hora_inicio,
        hora_fin=b.hora_fin,
        excluir_id=bloqueo_id,
    )
    if solapado is not None:
        raise BloqueoSolapadoError(
            f"No se puede reactivar: se solapa con el bloqueo "
            f"{solapado.bloqueo_id}."
        )

    b.activo = True
    db.flush()
    return b