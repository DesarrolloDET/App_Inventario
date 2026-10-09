"""
Service del maestro CONDUCTORES.

Contiene las reglas de negocio:
- Listar con paginacion y filtro de activo.
- Obtener uno.
- Crear (validando duplicado por documento).
- Actualizar (validando duplicado por documento si cambia).
- Desactivar (soft delete).
- Reactivar.

NO contiene:
- Logica HTTP (eso va en app.routers.conductores).
- Manejo de permisos (eso va en las dependencias de los routers).

Reglas aplicadas:
- Seccion 31: validacion de duplicados.
- Seccion 40: reglas de negocio en services.

Preparado para auditoria futura:
- Cada funcion recibe solo lo necesario para operar.
- En la Fase 6 se agregara un decorador @auditar(...) que envuelva
  estas funciones sin tener que reescribirlas.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.masters import Conductor
from app.schemas.conductores import ConductorCreate, ConductorUpdate


# ---------------------------------------------------------------------------
# Excepciones propias del service
# ---------------------------------------------------------------------------

class ConductorError(Exception):
    """Error base del service de conductores."""


class ConductorNoEncontradoError(ConductorError):
    """El conductor solicitado no existe."""


class ConductorDuplicadoError(ConductorError):
    """Ya existe un conductor con ese documento."""


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def listar_conductores(
    db: Session,
    *,
    offset: int,
    limit: int,
    solo_activos: bool = True,
) -> tuple[list[Conductor], int]:
    """
    Lista conductores con paginacion.

    Returns:
        (items, total): items de la pagina actual y total del universo.
    """
    base = select(Conductor)

    if solo_activos:
        base = base.where(Conductor.activo.is_(True))

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    items = list(
        db.execute(
            base.order_by(Conductor.conductor_id.asc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
    )

    return items, total


def obtener_conductor(db: Session, conductor_id: int) -> Conductor:
    """
    Obtiene un conductor por ID.

    Raises:
        ConductorNoEncontradoError: si no existe.
    """
    conductor = db.get(Conductor, conductor_id)
    if conductor is None:
        raise ConductorNoEncontradoError(
            f"Conductor {conductor_id} no encontrado."
        )
    return conductor


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def _existe_documento(
    db: Session,
    documento: str,
    excluir_id: int | None = None,
) -> bool:
    """Devuelve True si existe un conductor con ese documento."""
    stmt = select(Conductor).where(Conductor.documento == documento)
    if excluir_id is not None:
        stmt = stmt.where(Conductor.conductor_id != excluir_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def crear_conductor(db: Session, datos: ConductorCreate) -> Conductor:
    """
    Crea un conductor.

    Raises:
        ConductorDuplicadoError: si ya existe uno con ese documento.
    """
    if _existe_documento(db, datos.documento):
        raise ConductorDuplicadoError(
            f"Ya existe un conductor con el documento '{datos.documento}'."
        )

    conductor = Conductor(
        documento=datos.documento,
        nombre_completo=datos.nombre_completo,
        activo=True,
    )
    db.add(conductor)
    db.flush()
    return conductor


def actualizar_conductor(
    db: Session,
    conductor_id: int,
    datos: ConductorUpdate,
) -> Conductor:
    """
    Actualiza un conductor.

    Solo actualiza los campos que llegan (no None).

    Raises:
        ConductorNoEncontradoError: si no existe.
        ConductorDuplicadoError: si el nuevo documento ya esta en uso.
    """
    conductor = obtener_conductor(db, conductor_id)

    if datos.documento is not None and datos.documento != conductor.documento:
        if _existe_documento(db, datos.documento, excluir_id=conductor_id):
            raise ConductorDuplicadoError(
                f"Ya existe un conductor con el documento '{datos.documento}'."
            )
        conductor.documento = datos.documento

    if datos.nombre_completo is not None:
        conductor.nombre_completo = datos.nombre_completo

    db.flush()
    return conductor


def desactivar_conductor(db: Session, conductor_id: int) -> Conductor:
    """
    Desactiva un conductor (soft delete). Idempotente.

    Raises:
        ConductorNoEncontradoError: si no existe.
    """
    conductor = obtener_conductor(db, conductor_id)
    conductor.activo = False
    db.flush()
    return conductor


def reactivar_conductor(db: Session, conductor_id: int) -> Conductor:
    """
    Reactiva un conductor. Idempotente.

    Raises:
        ConductorNoEncontradoError: si no existe.
    """
    conductor = obtener_conductor(db, conductor_id)
    conductor.activo = True
    db.flush()
    return conductor