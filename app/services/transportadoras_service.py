"""
Service del maestro TRANSPORTADORAS.

Contiene las reglas de negocio:
- Listar con paginacion y filtro de activo.
- Obtener una.
- Crear (validando duplicado por nit).
- Actualizar (validando duplicado por nit si cambia).
- Desactivar (soft delete).
- Reactivar.

NO contiene:
- Logica HTTP (eso va en app.routers.transportadoras).
- Manejo de permisos (eso va en las dependencias de los routers).

Reglas aplicadas:
- Seccion 31: validacion de duplicados.
- Seccion 40: reglas de negocio en services.

Notas de diseño:
- Desactivar una transportadora NO afecta a sus vehiculos. La regla
  de "no usar transportadora inactiva" se aplicara al crear viajes o
  programaciones (Fase 3+).
- En la Fase 6 se agregara un decorador @auditar(...) que envuelva
  estas funciones sin tener que reescribirlas.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.masters import Transportadora
from app.schemas.transportadoras import (
    TransportadoraCreate,
    TransportadoraUpdate,
)


# ---------------------------------------------------------------------------
# Excepciones propias del service
# ---------------------------------------------------------------------------

class TransportadoraError(Exception):
    """Error base del service de transportadoras."""


class TransportadoraNoEncontradaError(TransportadoraError):
    """La transportadora solicitada no existe."""


class TransportadoraDuplicadaError(TransportadoraError):
    """Ya existe una transportadora con ese NIT."""


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def listar_transportadoras(
    db: Session,
    *,
    offset: int,
    limit: int,
    solo_activos: bool = True,
) -> tuple[list[Transportadora], int]:
    """
    Lista transportadoras con paginacion.

    Returns:
        (items, total): items de la pagina actual y total del universo.
    """
    base = select(Transportadora)

    if solo_activos:
        base = base.where(Transportadora.activo.is_(True))

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    items = list(
        db.execute(
            base.order_by(Transportadora.transportadora_id.asc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
    )

    return items, total


def obtener_transportadora(
    db: Session,
    transportadora_id: int,
) -> Transportadora:
    """
    Obtiene una transportadora por ID.

    Raises:
        TransportadoraNoEncontradaError: si no existe.
    """
    t = db.get(Transportadora, transportadora_id)
    if t is None:
        raise TransportadoraNoEncontradaError(
            f"Transportadora {transportadora_id} no encontrada."
        )
    return t


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def _existe_nit(
    db: Session,
    nit: str,
    excluir_id: int | None = None,
) -> bool:
    """Devuelve True si existe una transportadora con ese NIT."""
    stmt = select(Transportadora).where(Transportadora.nit == nit)
    if excluir_id is not None:
        stmt = stmt.where(Transportadora.transportadora_id != excluir_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def crear_transportadora(
    db: Session,
    datos: TransportadoraCreate,
) -> Transportadora:
    """
    Crea una transportadora.

    Raises:
        TransportadoraDuplicadaError: si ya existe una con ese NIT.
    """
    if _existe_nit(db, datos.nit):
        raise TransportadoraDuplicadaError(
            f"Ya existe una transportadora con el NIT '{datos.nit}'."
        )

    t = Transportadora(
        nit=datos.nit,
        razon_social=datos.razon_social,
        activo=True,
    )
    db.add(t)
    db.flush()
    return t


def actualizar_transportadora(
    db: Session,
    transportadora_id: int,
    datos: TransportadoraUpdate,
) -> Transportadora:
    """
    Actualiza una transportadora.

    Solo actualiza los campos que llegan (no None).

    Raises:
        TransportadoraNoEncontradaError: si no existe.
        TransportadoraDuplicadaError: si el nuevo NIT ya esta en uso.
    """
    t = obtener_transportadora(db, transportadora_id)

    if datos.nit is not None and datos.nit != t.nit:
        if _existe_nit(db, datos.nit, excluir_id=transportadora_id):
            raise TransportadoraDuplicadaError(
                f"Ya existe una transportadora con el NIT '{datos.nit}'."
            )
        t.nit = datos.nit

    if datos.razon_social is not None:
        t.razon_social = datos.razon_social

    db.flush()
    return t


def desactivar_transportadora(
    db: Session,
    transportadora_id: int,
) -> Transportadora:
    """
    Desactiva una transportadora (soft delete). Idempotente.

    No afecta a los vehiculos asociados: la validacion de "transportadora
    activa" se aplica al crear viajes o programaciones, no aqui.

    Raises:
        TransportadoraNoEncontradaError: si no existe.
    """
    t = obtener_transportadora(db, transportadora_id)
    t.activo = False
    db.flush()
    return t


def reactivar_transportadora(
    db: Session,
    transportadora_id: int,
) -> Transportadora:
    """
    Reactiva una transportadora. Idempotente.

    Raises:
        TransportadoraNoEncontradaError: si no existe.
    """
    t = obtener_transportadora(db, transportadora_id)
    t.activo = True
    db.flush()
    return t