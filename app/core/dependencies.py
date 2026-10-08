"""
Dependencias reutilizables de FastAPI para MEJIA TURNOS.

Contiene:
- get_current_user: extrae y valida al usuario desde el JWT.
- require_roles: factory de dependencias que exigen ciertos roles.
- CurrentUser / RequiredRoles: alias de tipo para endpoints.

NO contiene:
- Logica de login (eso va en app.services.auth_service).
- Generacion/decodificacion de JWT (eso va en app.core.jwt).
- Reglas de negocio (eso va en app.services.<modulo>).

Reglas aplicadas:
- Seccion 23: seguridad desde el backend.
- Seccion 25: cada endpoint verifica usuario, rol, recurso, estado.
- Seccion 27: minimo privilegio.

Estrategia de autorizacion:
- El JWT identifica al usuario (claim 'sub' = usuario_id).
- El token NO es la fuente de verdad de los roles: en cada request se
  consultan los roles ACTUALES en la base de datos.
- Si un rol fue revocado, el token ya no sirve (aunque no haya expirado).
- Esto es un balance entre seguridad y performance (~5ms por request).
"""

from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.jwt import (
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    TokenNotYetValidError,
    decode_access_token,
)
from app.database.connection import get_db
from app.models.security import Usuario


# ---------------------------------------------------------------------------
# Esquema de seguridad HTTP
# ---------------------------------------------------------------------------
# HTTPBearer extrae el token de la cabecera "Authorization: Bearer <token>".
# auto_error=True hace que FastAPI devuelva 401 automaticamente si no
# hay cabecera, sin que tengamos que comprobarlo manualmente.
#
# En el futuro, si queremos soportar tambien el flujo OAuth2PasswordBearer
# (para el boton "Authorize" de Swagger), agregaremos un segundo esquema.
# ---------------------------------------------------------------------------

bearer_scheme = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    """
    Extrae y valida al usuario autenticado desde el JWT.

    Pasos:
      1. Extrae el token de la cabecera Authorization.
      2. Decodifica y valida el JWT (firma, exp, nbf, claims, tipo).
      3. Convierte el payload crudo a TokenPayload tipado.
      4. Busca al usuario en BD por usuario_id.
      5. Verifica que el usuario exista y este activo.
      6. Verifica que los roles del token coincidan con los roles
         ACTUALES del usuario en BD (revocacion inmediata de roles).

    Errores:
      - 401 si el token es invalido, expirado o de tipo incorrecto.
      - 401 si el usuario no existe o esta inactivo.
      - 401 si los roles del token ya no coinciden con los de BD.

    Returns:
        La instancia Usuario (con roles cargados via selectinload).
    """
    token = credentials.credentials

    # Paso 2: decodificar. Mapear excepciones de jwt.py a HTTPException 401.
    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token expiro. Inicie sesion nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenNotYetValidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token aun no es valido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenInvalidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenError:
        # Cualquier otra excepcion de la jerarquia.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Paso 3: convertir a modelo tipado.
    # (En este punto confiamos en jwt.py que ya valido los claims).
    try:
        usuario_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido: sub malformado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Paso 4: buscar al usuario con sus roles.
    usuario = db.execute(
        select(Usuario)
        .options(selectinload(Usuario.roles))
        .where(Usuario.usuario_id == usuario_id)
    ).scalar_one_or_none()

    # Paso 5: verificar existencia y estado.
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Paso 6: verificar que los roles del token coincidan con BD.
    # Si un rol fue revocado, invalidamos el token.
    roles_token = set(payload.get("roles", []))
    roles_bd = {rol.nombre for rol in usuario.roles}

    if roles_token != roles_bd:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Los permisos del token ya no son validos. Inicie sesion nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return usuario


# ---------------------------------------------------------------------------
# require_roles
# ---------------------------------------------------------------------------

def require_roles(*roles_requeridos: str) -> Callable[..., Usuario]:
    """
    Factory de dependencias que exige que el usuario tenga al menos uno
    de los roles indicados.

    Uso:
        @router.post("/programacion")
        def crear_programacion(
            user: Usuario = Depends(require_roles("ADMINISTRADOR", "SUPERVISOR")),
        ):
            ...

    El usuario debe tener AL MENOS UNO de los roles. Para exigir TODOS,
    habria que agregar otra factory (no es necesario en el MVP).

    Args:
        *roles_requeridos: nombres de roles permitidos.

    Returns:
        Una dependencia que, al ejecutarse, valida el rol y devuelve
        el Usuario. Si el rol no coincide, lanza 403.

    Notas:
        - Si se llama sin argumentos, se trata como error de programacion.
        - Los nombres de roles se comparan en mayusculas exactas.
    """
    if not roles_requeridos:
        raise ValueError("require_roles debe recibir al menos un rol")

    roles_set = set(roles_requeridos)

    def _verificar(
        current_user: Annotated[Usuario, Depends(get_current_user)],
    ) -> Usuario:
        roles_usuario = {rol.nombre for rol in current_user.roles}

        if not roles_usuario.intersection(roles_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "No tiene permisos suficientes para esta operacion. "
                    f"Roles requeridos: {sorted(roles_set)}. "
                    f"Roles actuales: {sorted(roles_usuario)}."
                ),
            )
        return current_user

    return _verificar


# ---------------------------------------------------------------------------
# Alias de tipo para endpoints
# ---------------------------------------------------------------------------
# Annotated permite escribir endpoints mas limpios:
#
#   from app.core.dependencies import CurrentUser, AdminUser
#
#   @router.get("/me")
#   def me(user: CurrentUser):
#       ...
#
#   @router.post("/admin/solo")
#   def solo_admin(user: AdminUser):
#       ...

CurrentUser = Annotated[Usuario, Depends(get_current_user)]
AdminUser = Annotated[Usuario, Depends(require_roles("ADMINISTRADOR"))]