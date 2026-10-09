"""
Service del maestro PUERTOS.

"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.masters import Puerto
from app.schemas.puertos import PuertoCreate, PuertoUpdate


# ---------------------------------------------------------------------------
# Excepciones propias del service
# ---------------------------------------------------------------------------
# Envolvemos los errores de negocio en excepciones propias para que el
# router los traduzca a codigos HTTP sin depender de SQLAlchemy.

class PuertoError(Exception):
    """Error base del service de puertos."""


class PuertoNoEncontradoError(PuertoError):
    """El puerto solicitado no existe."""


class PuertoDuplicadoError(PuertoError):
    """Ya existe un puerto con ese nombre."""


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def listar_puertos(
    db: Session,
    *,
    offset: int,
    limit: int,
    solo_activos: bool = True,
) -> tuple[list[Puerto], int]:
    """
    Lista puertos con paginacion.

    Args:
        db: sesion SQLAlchemy.
        offset: numero de registros a saltar (page-1)*page_size.
        limit:  cantidad maxima de registros a devolver.
        solo_activos: si True, devuelve solo puertos activos.

    Returns:
        (items, total):
          - items: lista de Puerto en la pagina actual.
          - total: total de registros que cumplen el filtro.
    """
    base = select(Puerto)

    if solo_activos:
        base = base.where(Puerto.activo.is_(True))

    # Total (sin limit/offset)
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    # Pagina actual
    items = list(
        db.execute(
            base.order_by(Puerto.puerto_id.asc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
    )

    return items, total


def obtener_puerto(db: Session, puerto_id: int) -> Puerto:
    """
    Obtiene un puerto por ID.

    Args:
        db: sesion SQLAlchemy.
        puerto_id: id del puerto.

    Returns:
        La instancia Puerto.

    Raises:
        PuertoNoEncontradoError: si no existe.
    """
    puerto = db.get(Puerto, puerto_id)
    if puerto is None:
        raise PuertoNoEncontradoError(f"Puerto {puerto_id} no encontrado.")
    return puerto


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def _existe_nombre(
    db: Session,
    nombre: str,
    excluir_id: int | None = None,
) -> bool:
    """
    Devuelve True si existe un puerto con ese nombre.

    Args:
        db: sesion.
        nombre: nombre a buscar.
        excluir_id: si se especifica, ignora el registro con ese id
                    (util para actualizaciones).
    """
    stmt = select(Puerto).where(Puerto.nombre == nombre)
    if excluir_id is not None:
        stmt = stmt.where(Puerto.puerto_id != excluir_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def crear_puerto(db: Session, datos: PuertoCreate) -> Puerto:
    """
    Crea un puerto.

    Raises:
        PuertoDuplicadoError: si ya existe uno con ese nombre.
    """
    if _existe_nombre(db, datos.nombre):
        raise PuertoDuplicadoError(
            f"Ya existe un puerto con el nombre '{datos.nombre}'."
        )

    puerto = Puerto(nombre=datos.nombre, activo=True)
    db.add(puerto)
    db.flush()  # para obtener puerto_id
    return puerto


def actualizar_puerto(
    db: Session,
    puerto_id: int,
    datos: PuertoUpdate,
) -> Puerto:
    """
    Actualiza un puerto existente.

    Solo actualiza los campos que llegan en 'datos' (no None).

    Raises:
        PuertoNoEncontradoError: si el puerto no existe.
        PuertoDuplicadoError: si el nuevo nombre ya esta en uso.
    """
    puerto = obtener_puerto(db, puerto_id)

    if datos.nombre is not None and datos.nombre != puerto.nombre:
        if _existe_nombre(db, datos.nombre, excluir_id=puerto_id):
            raise PuertoDuplicadoError(
                f"Ya existe un puerto con el nombre '{datos.nombre}'."
            )
        puerto.nombre = datos.nombre

    db.flush()
    return puerto


def desactivar_puerto(db: Session, puerto_id: int) -> Puerto:
    """
    Desactiva un puerto (soft delete).

    Si ya estaba inactivo, no falla (idempotente).

    Raises:
        PuertoNoEncontradoError: si el puerto no existe.
    """
    puerto = obtener_puerto(db, puerto_id)
    puerto.activo = False
    db.flush()
    return puerto


def reactivar_puerto(db: Session, puerto_id: int) -> Puerto:
    """
    Reactiva un puerto previamente desactivado.

    Si ya estaba activo, no falla (idempotente).

    Raises:
        PuertoNoEncontradoError: si el puerto no existe.
    """
    puerto = obtener_puerto(db, puerto_id)
    puerto.activo = True
    db.flush()
    return puerto