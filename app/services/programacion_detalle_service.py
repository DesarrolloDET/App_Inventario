"""
Service de PROGRAMACION_DETALLE + generacion de CUPOS.

Contiene:
- CRUD de detalles (crear, actualizar, eliminar) con validaciones.
- Generacion automatica de cupos al crear/actualizar un detalle.
- Aseguramiento idempotente del bloqueo obligatorio de almuerzo.
- Calculo de franjas disponibles (franjas del dia - bloqueos - cupos usados).

NO contiene:
- Logica HTTP (eso va en app.routers.programaciones y programacion_detalle).
- Reglas de la cabecera de programacion (eso va en programaciones_service).

Reglas aplicadas:
- Seccion 7:  cupos, franjas y capacidad.
- Seccion 8:  bloqueos horarios.
- Seccion 40: reglas de negocio en services.

Reglas de negocio implementadas:
- Solo se puede crear/editar/eliminar un detalle si la programacion esta
  en estado BORRADOR. Una vez PUBLICADA, es inmutable.
- Un detalle requiere: fecha_operacion dentro del rango de la programacion,
  transportadora activa, materia prima activa, puerto activo.
- La cantidad de vehiculos no puede exceder las franjas disponibles.
- El almuerzo (12:00-13:00) SIEMPRE esta bloqueado, ademas de los
  bloqueos ordinarios de la fecha.
- Al crear/actualizar un detalle, se generan cupos automaticamente.
- La generacion de cupos y la creacion del detalle son atomicas.
- Si una operacion falla, no quedan cupos parciales.

Concurrencia:
- La validacion de franjas disponibles se hace en el service (Nivel 1).
- NO hay constraint a nivel BD que impida crear dos cupos para la misma
  franja en distintos detalles. Se confia en:
    a) El UniqueConstraint de cupos (mismo detalle + fecha + horas).
    b) La logica del service que excluye franjas ya usadas.
- En el MVP con baja concurrencia, esto es aceptable.

En la Fase 6 se agregara un decorador @auditar(...).
"""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.horario_operativo import (
    ALMUERZO_FIN,
    ALMUERZO_INICIO,
    generar_franjas_dia,
)
from app.models.masters import (
    MateriaPrima,
    Puerto,
    Transportadora,
)
from app.models.programming import (
    BloqueoHorario,
    Cupo,
    Programacion,
    ProgramacionDetalle,
)
from app.schemas.bloqueos import TipoBloqueo
from app.schemas.programacion_detalle import (
    ProgramacionDetalleCreate,
    ProgramacionDetalleUpdate,
)
from app.schemas.programaciones import EstadoProgramacion


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class ProgramacionDetalleError(Exception):
    """Error base del service de detalles de programacion."""


class DetalleNoEncontradoError(ProgramacionDetalleError):
    """El detalle solicitado no existe."""


class FechaFueraDeRangoError(ProgramacionDetalleError):
    """La fecha de operacion esta fuera del rango de la programacion."""


class MaestroInactivoError(ProgramacionDetalleError):
    """Un maestro referenciado (transportadora/materia/puerto) no existe o esta inactivo."""


class CapacidadInsuficienteError(ProgramacionDetalleError):
    """No hay suficientes franjas disponibles para la cantidad solicitada."""


class ProgramacionNoModificableError(ProgramacionDetalleError):
    """La programacion no esta en BORRADOR y no admite cambios en sus detalles."""


class DependenciaOperativaError(ProgramacionDetalleError):
    """El detalle tiene citas o dependencias operativas que impiden su eliminacion."""


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _asegurar_bloqueo_almuerzo(db: Session, fecha: date) -> None:
    """
    Garantiza que exista un BloqueoHorario activo de tipo ALMUERZO para
    la fecha indicada, con el rango [12:00, 13:00).

    Idempotente: si ya existe, no hace nada.
    """
    existente = db.execute(
        select(BloqueoHorario).where(
            BloqueoHorario.fecha == fecha,
            BloqueoHorario.tipo_bloqueo == TipoBloqueo.ALMUERZO.value,
            BloqueoHorario.activo.is_(True),
        )
    ).scalar_one_or_none()

    if existente is not None:
        return

    bloqueo = BloqueoHorario(
        fecha=fecha,
        hora_inicio=ALMUERZO_INICIO,
        hora_fin=ALMUERZO_FIN,
        tipo_bloqueo=TipoBloqueo.ALMUERZO.value,
        descripcion="Bloqueo obligatorio de almuerzo",
        activo=True,
    )
    db.add(bloqueo)


def _franja_solapa_con_alguno(
    inicio: time,
    fin: time,
    bloqueos: list[BloqueoHorario],
) -> bool:
    """
    Devuelve True si la franja (inicio, fin) se solapa con algun bloqueo.

    Regla: un bloqueo invalida cualquier franja con la que se solape
    parcial o totalmente. Se usa la condicion de intervalos semiabiertos.
    """
    for b in bloqueos:
        if inicio < b.hora_fin and b.hora_inicio < fin:
            return True
    return False


def _obtener_franjas_disponibles(
    db: Session,
    fecha: date,
    excluir_detalle_id: int | None = None,
) -> list[tuple[time, time]]:
    """
    Calcula las franjas del dia que estan disponibles para asignar.

    Franja disponible = franja base del horario operativo
                        - bloqueada por un BloqueoHorario activo
                        - ya usada por un Cupo de otro detalle

    Args:
        db: sesion.
        fecha: fecha de operacion.
        excluir_detalle_id: si se especifica, los cupos de ESE detalle
                            no cuentan como "usados" (util para
                            regenerar cupos del mismo detalle).

    Returns:
        Lista de tuplas (hora_inicio, hora_fin) disponibles.
    """
    # 1. Franjas base (sin almuerzo).
    franjas_base = generar_franjas_dia(incluir_almuerzo=False)

    # 2. Bloqueos activos de esa fecha.
    bloqueos = list(
        db.execute(
            select(BloqueoHorario).where(
                BloqueoHorario.fecha == fecha,
                BloqueoHorario.activo.is_(True),
            )
        ).scalars().all()
    )

    # 3. Cupos activos de esa fecha.
    stmt_cupos = (
        select(Cupo)
        .where(Cupo.fecha == fecha, Cupo.activo.is_(True))
    )
    if excluir_detalle_id is not None:
        stmt_cupos = stmt_cupos.where(
            Cupo.programacion_detalle_id != excluir_detalle_id
        )
    cupos_existentes = list(db.execute(stmt_cupos).scalars().all())

    franjas_usadas = {(c.hora_inicio, c.hora_fin) for c in cupos_existentes}

    # 4. Filtrar.
    disponibles: list[tuple[time, time]] = []
    for (ini, fin) in franjas_base:
        if (ini, fin) in franjas_usadas:
            continue
        if _franja_solapa_con_alguno(ini, fin, bloqueos):
            continue
        disponibles.append((ini, fin))

    return disponibles


def _crear_cupos(
    db: Session,
    detalle: ProgramacionDetalle,
    franjas: list[tuple[time, time]],
) -> list[Cupo]:
    """
    Crea los cupos para un detalle, usando las franjas indicadas.

    NO hace commit; el caller decide cuando.
    """
    cupos: list[Cupo] = []
    for (ini, fin) in franjas:
        cupo = Cupo(
            programacion_detalle_id=detalle.programacion_detalle_id,
            fecha=detalle.fecha_operacion,
            hora_inicio=ini,
            hora_fin=fin,
            activo=True,
        )
        db.add(cupo)
        cupos.append(cupo)
    db.flush()
    return cupos


def _eliminar_cupos_de_detalle(db: Session, detalle: ProgramacionDetalle) -> None:
    """
    Elimina TODOS los cupos de un detalle.

    En el MVP, sin citas, siempre es seguro. En la Fase 4, esta funcion
    puede fallar con IntegrityError si algun cupo tiene cita. En ese
    caso, se propaga DependenciaOperativaError.
    """
    from sqlalchemy.exc import IntegrityError

    try:
        for cupo in list(detalle.cupos):
            db.delete(cupo)
        db.flush()
    except IntegrityError as exc:
        raise DependenciaOperativaError(
            "No se pueden regenerar los cupos: algun cupo tiene citas asociadas."
        ) from exc


def _validar_maestros(
    db: Session,
    transportadora_id: int,
    materia_prima_id: int,
    puerto_id: int,
) -> None:
    """
    Valida que los maestros existen y estan activos.

    Raises:
        MaestroInactivoError: si alguno no existe o esta inactivo.
    """
    t = db.get(Transportadora, transportadora_id)
    if t is None or not t.activo:
        raise MaestroInactivoError(
            f"Transportadora {transportadora_id} no existe o esta inactiva."
        )

    m = db.get(MateriaPrima, materia_prima_id)
    if m is None or not m.activo:
        raise MaestroInactivoError(
            f"Materia prima {materia_prima_id} no existe o esta inactiva."
        )

    p = db.get(Puerto, puerto_id)
    if p is None or not p.activo:
        raise MaestroInactivoError(
            f"Puerto {puerto_id} no existe o esta inactivo."
        )


def _cargar_programacion_para_modificar(
    db: Session,
    programacion_id: int,
) -> Programacion:
    """
    Carga la programacion verificando que este en BORRADOR.

    Raises:
        ProgramacionNoModificableError: si no esta en BORRADOR.
    """
    from app.services.programaciones_service import (
        ProgramacionNoEncontradaError as ProgNoEncErr,
        _cargar_con_detalles,
    )

    try:
        prog = _cargar_con_detalles(db, programacion_id)
    except ProgNoEncErr as exc:
        raise ProgramacionNoModificableError(str(exc)) from exc

    if prog.estado != EstadoProgramacion.BORRADOR.value:
        raise ProgramacionNoModificableError(
            f"La programacion esta en estado {prog.estado}. "
            f"Solo se permite modificar detalles en BORRADOR."
        )
    return prog


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def listar_detalles_de_programacion(
    db: Session,
    programacion_id: int,
) -> list[ProgramacionDetalle]:
    """
    Lista los detalles de una programacion con sus cupos cargados.

    Raises:
        ProgramacionNoModificableError: si la programacion no existe.
    """
    from app.services.programaciones_service import (
        ProgramacionNoEncontradaError as ProgNoEncErr,
        _cargar_con_detalles,
    )

    try:
        prog = _cargar_con_detalles(db, programacion_id)
    except ProgNoEncErr as exc:
        raise ProgramacionNoModificableError(str(exc)) from exc

    # Cargar cupos ansiosamente.
    detalles = list(
        db.execute(
            select(ProgramacionDetalle)
            .options(selectinload(ProgramacionDetalle.cupos))
            .where(ProgramacionDetalle.programacion_id == programacion_id)
            .order_by(ProgramacionDetalle.programacion_detalle_id.asc())
        ).scalars().all()
    )
    return detalles


def obtener_detalle(db: Session, detalle_id: int) -> ProgramacionDetalle:
    """
    Obtiene un detalle con sus cupos cargados.

    Raises:
        DetalleNoEncontradoError: si no existe.
    """
    detalle = db.execute(
        select(ProgramacionDetalle)
        .options(selectinload(ProgramacionDetalle.cupos))
        .where(ProgramacionDetalle.programacion_detalle_id == detalle_id)
    ).scalar_one_or_none()

    if detalle is None:
        raise DetalleNoEncontradoError(
            f"Detalle {detalle_id} no encontrado."
        )
    return detalle


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def crear_detalle(
    db: Session,
    programacion_id: int,
    datos: ProgramacionDetalleCreate,
) -> ProgramacionDetalle:
    """
    Crea un detalle y genera sus cupos automaticamente.

    Raises:
        ProgramacionNoModificableError: si la programacion no esta en BORRADOR.
        FechaFueraDeRangoError: si la fecha no cae en el rango.
        MaestroInactivoError: si algun maestro esta inactivo.
        CapacidadInsuficienteError: si no hay suficientes franjas.
    """
    prog = _cargar_programacion_para_modificar(db, programacion_id)

    # 1. Validar rango de fechas.
    if not (prog.fecha_inicio <= datos.fecha_operacion <= prog.fecha_fin):
        raise FechaFueraDeRangoError(
            f"La fecha de operacion {datos.fecha_operacion} esta fuera del "
            f"rango de la programacion [{prog.fecha_inicio}, {prog.fecha_fin}]."
        )

    # 2. Validar maestros activos.
    _validar_maestros(
        db,
        transportadora_id=datos.transportadora_id,
        materia_prima_id=datos.materia_prima_id,
        puerto_id=datos.puerto_id,
    )

    # 3. Asegurar bloqueo de almuerzo.
    _asegurar_bloqueo_almuerzo(db, datos.fecha_operacion)

    # 4. Calcular franjas disponibles.
    disponibles = _obtener_franjas_disponibles(db, datos.fecha_operacion)

    # 5. Verificar capacidad.
    if datos.cantidad_vehiculos > len(disponibles):
        raise CapacidadInsuficienteError(
            f"Capacidad insuficiente para {datos.fecha_operacion}: "
            f"se solicitaron {datos.cantidad_vehiculos} cupos pero solo "
            f"hay {len(disponibles)} franjas disponibles."
        )

    # 6. Crear detalle.
    detalle = ProgramacionDetalle(
        programacion_id=programacion_id,
        fecha_operacion=datos.fecha_operacion,
        transportadora_id=datos.transportadora_id,
        materia_prima_id=datos.materia_prima_id,
        puerto_id=datos.puerto_id,
        cantidad_vehiculos=datos.cantidad_vehiculos,
    )
    db.add(detalle)
    db.flush()  # para obtener el detalle_id

    # 7. Crear cupos.
    franjas_a_usar = disponibles[: datos.cantidad_vehiculos]
    _crear_cupos(db, detalle, franjas_a_usar)

    return detalle


def actualizar_detalle(
    db: Session,
    detalle_id: int,
    datos: ProgramacionDetalleUpdate,
) -> ProgramacionDetalle:
    """
    Actualiza un detalle.

    Si cambia 'cantidad_vehiculos' o 'fecha_operacion', regenera los
    cupos del detalle (elimina los existentes y crea los nuevos).

    Raises:
        DetalleNoEncontradoError: si no existe.
        ProgramacionNoModificableError: si la programacion no esta en BORRADOR.
        FechaFueraDeRangoError: si la nueva fecha no cae en el rango.
        MaestroInactivoError: si cambia algun maestro y esta inactivo.
        CapacidadInsuficienteError: si no hay suficientes franjas.
    """
    detalle = obtener_detalle(db, detalle_id)
    prog = _cargar_programacion_para_modificar(db, detalle.programacion_id)

    # Merge de campos.
    nueva_fecha = (
        datos.fecha_operacion
        if datos.fecha_operacion is not None
        else detalle.fecha_operacion
    )
    nueva_transportadora_id = (
        datos.transportadora_id
        if datos.transportadora_id is not None
        else detalle.transportadora_id
    )
    nueva_materia_id = (
        datos.materia_prima_id
        if datos.materia_prima_id is not None
        else detalle.materia_prima_id
    )
    nuevo_puerto_id = (
        datos.puerto_id
        if datos.puerto_id is not None
        else detalle.puerto_id
    )
    nueva_cantidad = (
        datos.cantidad_vehiculos
        if datos.cantidad_vehiculos is not None
        else detalle.cantidad_vehiculos
    )

    # Validar rango.
    if not (prog.fecha_inicio <= nueva_fecha <= prog.fecha_fin):
        raise FechaFueraDeRangoError(
            f"La fecha de operacion {nueva_fecha} esta fuera del rango "
            f"de la programacion [{prog.fecha_inicio}, {prog.fecha_fin}]."
        )

    # Validar maestros activos (solo si cambian).
    if (
        datos.transportadora_id is not None
        or datos.materia_prima_id is not None
        or datos.puerto_id is not None
    ):
        _validar_maestros(
            db,
            transportadora_id=nueva_transportadora_id,
            materia_prima_id=nueva_materia_id,
            puerto_id=nuevo_puerto_id,
        )

    # Asegurar bloqueo de almuerzo si cambio la fecha.
    if nueva_fecha != detalle.fecha_operacion:
        _asegurar_bloqueo_almuerzo(db, nueva_fecha)

    # Determinar si hay que regenerar cupos.
    regenerar = (
        nueva_fecha != detalle.fecha_operacion
        or nueva_cantidad != detalle.cantidad_vehiculos
    )

    if regenerar:
        # Eliminar cupos actuales.
        _eliminar_cupos_de_detalle(db, detalle)

        # Recalcular disponibles (excluyendo el detalle actual para no
        # contar sus propios cupos, que acabamos de eliminar... aunque
        # ya no estan en BD, lo dejamos por seguridad).
        disponibles = _obtener_franjas_disponibles(
            db, nueva_fecha, excluir_detalle_id=detalle_id
        )

        if nueva_cantidad > len(disponibles):
            raise CapacidadInsuficienteError(
                f"Capacidad insuficiente para {nueva_fecha}: "
                f"se solicitaron {nueva_cantidad} cupos pero solo "
                f"hay {len(disponibles)} franjas disponibles."
            )

    # Aplicar cambios.
    detalle.fecha_operacion = nueva_fecha
    detalle.transportadora_id = nueva_transportadora_id
    detalle.materia_prima_id = nueva_materia_id
    detalle.puerto_id = nuevo_puerto_id
    detalle.cantidad_vehiculos = nueva_cantidad

    if regenerar:
        franjas_a_usar = disponibles[:nueva_cantidad]
        _crear_cupos(db, detalle, franjas_a_usar)

    db.flush()
    return detalle


def eliminar_detalle(db: Session, detalle_id: int) -> None:
    """
    Elimina un detalle (y sus cupos) SOLO si la programacion esta en BORRADOR.

    Raises:
        DetalleNoEncontradoError: si no existe.
        ProgramacionNoModificableError: si la programacion no esta en BORRADOR.
        DependenciaOperativaError: si algun cupo tiene citas asociadas.
    """
    from sqlalchemy.exc import IntegrityError

    detalle = obtener_detalle(db, detalle_id)
    _ = _cargar_programacion_para_modificar(db, detalle.programacion_id)

    # Eliminar el detalle directamente. El cascade "all, delete-orphan"
    # de la relacion ProgramacionDetalle.cupos se encarga de eliminar
    # los cupos asociados. Si algun cupo tiene cita, PostgreSQL lanzara
    # IntegrityError, que traducimos a DependenciaOperativaError.
    try:
        db.delete(detalle)
        db.flush()
    except IntegrityError as exc:
        raise DependenciaOperativaError(
            "No se puede eliminar el detalle: algun cupo tiene citas asociadas."
        ) from exc
    
def listar_cupos_de_detalle(
    db: Session,
    detalle_id: int,
) -> list[Cupo]:
    """
    Lista los cupos asociados a un detalle, ordenados por hora_inicio.

    Args:
        db: sesion.
        detalle_id: ID del detalle.

    Returns:
        Lista de Cupo ordenados por hora de inicio.
    """
    return list(
        db.execute(
            select(Cupo)
            .where(Cupo.programacion_detalle_id == detalle_id)
            .order_by(Cupo.hora_inicio.asc())
        ).scalars().all()
    )