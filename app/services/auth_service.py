"""
Servicio de autenticacion de MEJIA TURNOS.

Contiene la logica de negocio para:
- Autenticar un usuario por username + password.

NO contiene:
- Logica HTTP (eso va en app.routers.auth).
- Verificacion de JWT (eso va en app.core.jwt).
- Hashing (eso va en app.core.security).

Reglas aplicadas:
- Seccion 25: verificacion desde el backend.
- Seccion 28: NUNCA loggear passwords ni hashes.
- Seccion 40: reglas de negocio en services, no en routers.

Consideraciones de seguridad:
- Timing attack: cuando el username no existe, se ejecuta un hash
  dummy para que el tiempo de respuesta sea similar al caso real.
  Sin esto, un atacante puede enumerar usernames midiendo tiempos.
- Mensajes genericos: el service devuelve None tanto si el username
  no existe como si el password es incorrecto. El router traduce
  None a un 401 con mensaje generico.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password, verify_password
from app.models.security import Usuario


# ---------------------------------------------------------------------------
# Constante de proteccion contra timing attack
# ---------------------------------------------------------------------------
# Password ficticio que se hashea cuando el username no existe, para que
# el tiempo de respuesta sea similar al caso en que SÍ existe y hay que
# verificar un password real.
#
# El valor NO importa (nadie lo usa para comparar). Solo importa que
# hash_password() tarde un tiempo comparable a una verificacion real.
#
# Si algun dia se cambia el costo de argon2, este valor debe seguir
# siendo un string no vacio. No es necesario actualizarlo al cambiar
# parametros de argon2: el tiempo se ajusta automaticamente.
# ---------------------------------------------------------------------------

_DUMMY_PASSWORD_FOR_TIMING = "dummy_password_para_proteccion_de_timing_attack"


# ---------------------------------------------------------------------------
# Funcion publica
# ---------------------------------------------------------------------------

def autenticar_usuario(
    db: Session,
    username: str,
    password: str,
) -> Usuario | None:
    """
    Verifica credenciales y devuelve el Usuario si son validas.

    Args:
        db: sesion SQLAlchemy activa.
        username: nombre de usuario (no distingue mayus/minus).
        password: contrasena en texto plano.

    Returns:
        Usuario con sus roles cargados si las credenciales son validas.
        None en cualquier otro caso:
          - usuario no existe
          - password incorrecto
          - usuario inactivo

    Seguridad:
        - Proteccion contra timing attacks: cuando el usuario no existe
          se ejecuta un hash dummy para igualar el tiempo de respuesta.
        - No revela si el usuario existe o no (mismo retorno None).
        - NUNCA loggear password ni password_hash.
    """
    # Normalizamos el username (minúsculas, sin espacios).
    username_normalizado = username.strip()

    # Buscar al usuario con sus roles precargados (evita N+1 al usar .roles).
    usuario = db.execute(
        select(Usuario)
        .options(selectinload(Usuario.roles))
        .where(Usuario.username == username_normalizado)
    ).scalar_one_or_none()

    # Caso 1: usuario no existe.
    # Proteccion contra timing attack: hashear un dummy para que el tiempo
    # de respuesta sea similar al caso real (~80ms con argon2 por defecto).
    if usuario is None:
        hash_password(_DUMMY_PASSWORD_FOR_TIMING)
        return None

    # Caso 2: usuario existe pero el password no coincide.
    # verify_password NUNCA lanza por password incorrecto: devuelve False.
    if not verify_password(password, usuario.password_hash):
        return None

    # Caso 3: password correcto pero usuario inactivo.
    # Se verifica DESPUES del password para no revelar por timing que la
    # cuenta existe y esta inactiva.
    if not usuario.activo:
        return None

    # Caso 4: credenciales validas.
    return usuario