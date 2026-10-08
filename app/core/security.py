"""
Utilidades de seguridad para MEJIA TURNOS.

"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)


# ---------------------------------------------------------------------------
# Configuracion del PasswordHasher
# ---------------------------------------------------------------------------
# Parametros basados en las recomendaciones OWASP 2024 para Argon2id:
#   - time_cost: 3 iteraciones
#   - memory_cost: 64 MiB (65536 KiB)
#   - parallelism: 4 hilos
#   - hash_len: 32 bytes (256 bits)
#   - salt_len: 16 bytes (128 bits)
#
# Balance: ~50-100ms por hash en hardware moderno.
# ---------------------------------------------------------------------------

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,       # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


# ---------------------------------------------------------------------------
# Funciones publicas
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Hashea una contraseña con Argon2id.

    
    """
    if not isinstance(password, str):
        raise ValueError("password debe ser un string")

    if not password:
        raise ValueError("password no puede estar vacio")

    # Argon2id con los parametros configurados arriba.
    # password.encode('utf-8') porque argon2-cffi trabaja con bytes.
    return _hasher.hash(password.encode("utf-8"))


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifica si una contraseña coincide con un hash Argon2id.

   
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password debe ser un string no vacio")

    if not isinstance(password_hash, str) or not password_hash:
        raise ValueError("password_hash debe ser un string no vacio")

    try:
        _hasher.verify(password_hash, password.encode("utf-8"))
        return True

    except VerifyMismatchError:
        # Contraseña incorrecta. NO es un error, es un resultado valido.
        return False

    except VerificationError:
        # Error durante la verificacion (hash corrupto o malformado).
        # No es un fallo de login; propagamos para que quede en logs.
        raise

    except InvalidHashError:
        # El hash no tiene formato Argon2id valido. Corrupcion en BD.
        # Propagamos para que quede en logs.
        raise


def needs_rehash(password_hash: str) -> bool:
    """
    Indica si un hash fue generado con parametros distintos a los actuales.

    Uso tipico (futuro, en el flujo de login):
        if verify_password(password, user.password_hash):
            if needs_rehash(user.password_hash):
                user.password_hash = hash_password(password)
                db.commit()
            # login exitoso

    Esto permite rotar parametros de hashing sin invalidar passwords
    existentes. Si subimos time_cost de 3 a 4 en el futuro, los hashes
    antiguos se re-hashean silenciosamente en el proximo login.

    Args:
        password_hash: Hash almacenado en BD.

    Returns:
        True si el hash deberia ser regenerado con los parametros actuales.
    """
    return _hasher.check_needs_rehash(password_hash)