"""
Service del maestro MATERIAS PRIMAS.

Contiene las reglas de negocio:
- Listar con paginacion y filtro de activo.
- Obtener una.
- Crear (validando duplicado por codigo).
- Actualizar (validando duplicado por codigo si cambia).
- Desactivar (soft delete).
- Reactivar.

NO contiene:
- Logica HTTP (eso va en app.routers.materias_primas).
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

from app.models.masters import MateriaPrima
from app.schemas.materias_primas import MateriaPrimaCreate, MateriaPrimaUpdate


# ---------------------------------------------------------------------------
# Excepciones propias del service
# ---------------------------------------------------------------------------

class MateriaPrimaError(Exception):
    """Error base del service de materias primas."""


class MateriaPrimaNoEncontradaError(MateriaPrimaError):
    """La materia prima solicitada no existe."""


class MateriaPrimaDuplicadaError(MateriaPrimaError):
    """Ya existe una materia prima con ese codigo."""


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def listar_materias_primas(
    db: Session,
    *,
    offset: int,
    limit: int,
    solo_activos: bool = True,
) -> tuple[list[MateriaPrima], int]:
    """
    Lista materias primas con paginacion.

    Returns:
        (items, total): items de la pagina actual y total del universo.
    """
    base = select(MateriaPrima)

    if solo_activos:
        base = base.where(MateriaPrima.activo.is_(True))

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    items = list(
        db.execute(
            base.order_by(MateriaPrima.materia_prima_id.asc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
    )

    return items, total


def obtener_materia_prima(db: Session, materia_prima_id: int) -> MateriaPrima:
    """
    Obtiene una materia prima por ID.

    Raises:
        MateriaPrimaNoEncontradaError: si no existe.
    """
    mp = db.get(MateriaPrima, materia_prima_id)
    if mp is None:
        raise MateriaPrimaNoEncontradaError(
            f"Materia prima {materia_prima_id} no encontrada."
        )
    return mp


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def _existe_codigo(
    db: Session,
    codigo: str,
    excluir_id: int | None = None,
) -> bool:
    """Devuelve True si existe una materia prima con ese codigo."""
    stmt = select(MateriaPrima).where(MateriaPrima.codigo == codigo)
    if excluir_id is not None:
        stmt = stmt.where(MateriaPrima.materia_prima_id != excluir_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def crear_materia_prima(
    db: Session,
    datos: MateriaPrimaCreate,
) -> MateriaPrima:
    """
    Crea una materia prima.

    Raises:
        MateriaPrimaDuplicadaError: si ya existe una con ese codigo.
    """
    if _existe_codigo(db, datos.codigo):
        raise MateriaPrimaDuplicadaError(
            f"Ya existe una materia prima con el codigo '{datos.codigo}'."
        )

    mp = MateriaPrima(
        codigo=datos.codigo,
        nombre=datos.nombre,
        activo=True,
    )
    db.add(mp)
    db.flush()
    return mp


def actualizar_materia_prima(
    db: Session,
    materia_prima_id: int,
    datos: MateriaPrimaUpdate,
) -> MateriaPrima:
    """
    Actualiza una materia prima.

    Solo actualiza los campos que llegan (no None).

    Raises:
        MateriaPrimaNoEncontradaError: si no existe.
        MateriaPrimaDuplicadaError: si el nuevo codigo ya esta en uso.
    """
    mp = obtener_materia_prima(db, materia_prima_id)

    if datos.codigo is not None and datos.codigo != mp.codigo:
        if _existe_codigo(db, datos.codigo, excluir_id=materia_prima_id):
            raise MateriaPrimaDuplicadaError(
                f"Ya existe una materia prima con el codigo '{datos.codigo}'."
            )
        mp.codigo = datos.codigo

    if datos.nombre is not None:
        mp.nombre = datos.nombre

    db.flush()
    return mp


def desactivar_materia_prima(db: Session, materia_prima_id: int) -> MateriaPrima:
    """
    Desactiva una materia prima (soft delete). Idempotente.

    Raises:
        MateriaPrimaNoEncontradaError: si no existe.
    """
    mp = obtener_materia_prima(db, materia_prima_id)
    mp.activo = False
    db.flush()
    return mp


def reactivar_materia_prima(db: Session, materia_prima_id: int) -> MateriaPrima:
    """
    Reactiva una materia prima. Idempotente.

    Raises:
        MateriaPrimaNoEncontradaError: si no existe.
    """
    mp = obtener_materia_prima(db, materia_prima_id)
    mp.activo = True
    db.flush()
    return mp