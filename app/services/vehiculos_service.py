"""
Service del maestro VEHICULOS.

Contiene las reglas de negocio:
- Listar con paginacion y filtro de activo.
- Obtener uno.
- Crear (validando placa unica + transportadora existente y activa).
- Actualizar (validando placa unica si cambia + transportadora activa si cambia).
- Desactivar (soft delete).
- Reactivar (verificando que la transportadora siga activa).

NO contiene:
- Logica HTTP (eso va en app.routers.vehiculos).
- Manejo de permisos (eso va en las dependencias de los routers).

Reglas aplicadas:
- Seccion 31: validacion de duplicados y de relaciones.
- Seccion 40: reglas de negocio en services.

Dependencia en transportadoras:
- Reutiliza obtener_transportadora() del service de transportadoras
  para no duplicar la logica de busqueda.
- Si la transportadora no existe -> TransportadoraInvalidaError.
- Si la transportadora esta inactiva -> TransportadoraInvalidaError.

En la Fase 6 se agregara un decorador @auditar(...).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.masters import Vehiculo
from app.schemas.vehiculos import VehiculoCreate, VehiculoUpdate
from app.services import transportadoras_service as transportadoras_svc


# ---------------------------------------------------------------------------
# Excepciones propias del service
# ---------------------------------------------------------------------------

class VehiculoError(Exception):
    """Error base del service de vehiculos."""


class VehiculoNoEncontradoError(VehiculoError):
    """El vehiculo solicitado no existe."""


class VehiculoDuplicadoError(VehiculoError):
    """Ya existe un vehiculo con esa placa."""


class TransportadoraInvalidaError(VehiculoError):
    """La transportadora referenciada no existe o no esta activa."""


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def listar_vehiculos(
    db: Session,
    *,
    offset: int,
    limit: int,
    solo_activos: bool = True,
    transportadora_id: int | None = None,
) -> tuple[list[Vehiculo], int]:
    """
    Lista vehiculos con paginacion.

    Args:
        db: sesion SQLAlchemy.
        offset: registros a saltar.
        limit: cantidad maxima a devolver.
        solo_activos: si True, solo vehiculos activos.
        transportadora_id: si se especifica, filtra por transportadora.

    Returns:
        (items, total): items de la pagina actual y total del universo.
    """
    base = select(Vehiculo)

    if solo_activos:
        base = base.where(Vehiculo.activo.is_(True))

    if transportadora_id is not None:
        base = base.where(Vehiculo.transportadora_id == transportadora_id)

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    items = list(
        db.execute(
            base.order_by(Vehiculo.vehiculo_id.asc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
    )

    return items, total


def obtener_vehiculo(db: Session, vehiculo_id: int) -> Vehiculo:
    """
    Obtiene un vehiculo por ID.

    Raises:
        VehiculoNoEncontradoError: si no existe.
    """
    v = db.get(Vehiculo, vehiculo_id)
    if v is None:
        raise VehiculoNoEncontradoError(
            f"Vehiculo {vehiculo_id} no encontrado."
        )
    return v


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _existe_placa(
    db: Session,
    placa: str,
    excluir_id: int | None = None,
) -> bool:
    """Devuelve True si existe un vehiculo con esa placa."""
    stmt = select(Vehiculo).where(Vehiculo.placa == placa)
    if excluir_id is not None:
        stmt = stmt.where(Vehiculo.vehiculo_id != excluir_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def _validar_transportadora_activa(db: Session, transportadora_id: int) -> None:
    """
    Verifica que la transportadora exista y este activa.

    Raises:
        TransportadoraInvalidaError: si no existe o esta inactiva.
    """
    try:
        t = transportadoras_svc.obtener_transportadora(db, transportadora_id)
    except transportadoras_svc.TransportadoraNoEncontradaError:
        raise TransportadoraInvalidaError(
            f"Transportadora {transportadora_id} no existe."
        )

    if not t.activo:
        raise TransportadoraInvalidaError(
            f"Transportadora {transportadora_id} esta inactiva."
        )


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def crear_vehiculo(db: Session, datos: VehiculoCreate) -> Vehiculo:
    """
    Crea un vehiculo.

    Raises:
        VehiculoDuplicadoError: si ya existe uno con esa placa.
        TransportadoraInvalidaError: si la transportadora no existe
                                     o esta inactiva.
    """
    if _existe_placa(db, datos.placa):
        raise VehiculoDuplicadoError(
            f"Ya existe un vehiculo con la placa '{datos.placa}'."
        )

    _validar_transportadora_activa(db, datos.transportadora_id)

    v = Vehiculo(
        placa=datos.placa,
        transportadora_id=datos.transportadora_id,
        activo=True,
    )
    db.add(v)
    db.flush()
    return v


def actualizar_vehiculo(
    db: Session,
    vehiculo_id: int,
    datos: VehiculoUpdate,
) -> Vehiculo:
    """
    Actualiza un vehiculo.

    Solo actualiza los campos que llegan (no None).

    Raises:
        VehiculoNoEncontradoError: si no existe.
        VehiculoDuplicadoError: si la nueva placa ya esta en uso.
        TransportadoraInvalidaError: si la nueva transportadora no
                                     existe o esta inactiva.
    """
    v = obtener_vehiculo(db, vehiculo_id)

    if datos.placa is not None and datos.placa != v.placa:
        if _existe_placa(db, datos.placa, excluir_id=vehiculo_id):
            raise VehiculoDuplicadoError(
                f"Ya existe un vehiculo con la placa '{datos.placa}'."
            )
        v.placa = datos.placa

    if (
        datos.transportadora_id is not None
        and datos.transportadora_id != v.transportadora_id
    ):
        _validar_transportadora_activa(db, datos.transportadora_id)
        v.transportadora_id = datos.transportadora_id

    db.flush()
    return v


def desactivar_vehiculo(db: Session, vehiculo_id: int) -> Vehiculo:
    """
    Desactiva un vehiculo (soft delete). Idempotente.

    Raises:
        VehiculoNoEncontradoError: si no existe.
    """
    v = obtener_vehiculo(db, vehiculo_id)
    v.activo = False
    db.flush()
    return v


def reactivar_vehiculo(db: Session, vehiculo_id: int) -> Vehiculo:
    """
    Reactiva un vehiculo. Verifica que su transportadora siga activa.

    Raises:
        VehiculoNoEncontradoError: si no existe.
        TransportadoraInvalidaError: si la transportadora del vehiculo
                                     esta inactiva o ya no existe.
    """
    v = obtener_vehiculo(db, vehiculo_id)

    # Regla: no reactivar un vehiculo cuya transportadora esta inactiva.
    _validar_transportadora_activa(db, v.transportadora_id)

    v.activo = True
    db.flush()
    return v