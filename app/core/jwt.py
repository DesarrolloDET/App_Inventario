"""
Modulo de generacion y validacion de tokens JWT para MEJIA TURNOS.

Claims incluidos en el token:
    sub   -> usuario_id (como string; requerido por la spec JWT)
    roles -> lista de nombres de rol del usuario
    type  -> "access" (permite distinguir de refresh tokens futuros)
    exp   -> timestamp de expiracion
    iat   -> timestamp de emision
    nbf   -> "not before"; el token es valido desde iat
    jti   -> UUID unico del token (para revocacion futura)

NUNCA incluir en el token:
    password, password_hash, email, nombre, datos personales.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAlgorithmError,
    InvalidTokenError,
)

from app.core.config import settings


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Tipo de token. En el futuro habra tambien "refresh".
_TOKEN_TYPE_ACCESS = "access"

# Claims que SIEMPRE deben estar presentes en un token valido.
_REQUIRED_CLAIMS = ("sub", "exp", "iat", "nbf", "jti", "type", "roles")


# ---------------------------------------------------------------------------
# Excepciones propias
# ---------------------------------------------------------------------------
# Envolvemos las excepciones de PyJWT en nuestras propias excepciones para
# desacoplar el resto del sistema de la libreria concreta. Si algun dia
# cambiamos de PyJWT a otra libreria, solo este modulo cambia.

class TokenError(Exception):
    """Error base de manejo de tokens."""


class TokenExpiredError(TokenError):
    """El token expiro (claim exp < ahora)."""


class TokenNotYetValidError(TokenError):
    """El token aun no es valido (claim nbf > ahora)."""


class TokenInvalidError(TokenError):
    """El token es invalido: firma incorrecta, formato corrupto, claim faltante, etc."""


# ---------------------------------------------------------------------------
# Generacion
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str | int,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Genera un access token JWT firmado con HS256.

    Args:
        subject: Identificador del usuario. Normalmente el usuario_id
                 como string o int. Se convierte a string por la spec JWT
                 (claim 'sub' debe ser string).
        roles: Lista de nombres de roles del usuario (ej: ["ADMINISTRADOR"]).
               Se incluye dentro del token para evitar consultar la BD en
               cada request.
        expires_delta: Duracion del token. Si es None, usa el valor de
                       settings.ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Token JWT como string (formato header.payload.signature).

    Notas:
        - El token incluye un 'jti' (UUID) unico, util para revocacion futura.
        - El token NO contiene informacion personal ni sensible.
        - La firma usa settings.SECRET_KEY y settings.JWT_ALGORITHM.
    """
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),                    # usuario_id como string
        "roles": list(roles),                   # copia defensiva
        "type": _TOKEN_TYPE_ACCESS,
        "iat": now,                             # issued at
        "nbf": now,                             # not before (mismo que iat)
        "exp": now + expires_delta,             # expiration
        "jti": str(uuid.uuid4()),               # JWT ID unico
    }

    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    # PyJWT >= 2.0 devuelve str directamente. Por si acaso, normalizamos.
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token


# ---------------------------------------------------------------------------
# Validacion y decodificacion
# ---------------------------------------------------------------------------

def decode_access_token(token: str) -> dict[str, Any]:
    """
    Verifica y decodifica un access token JWT.

    Verifica:
        - Firma valida con settings.SECRET_KEY y settings.JWT_ALGORITHM.
        - Claim 'exp' no vencido.
        - Claim 'nbf' cumplido.
        - Claim 'type' == 'access'.
        - Claims obligatorios presentes (sub, exp, iat, nbf, jti, roles).

    Args:
        token: JWT como string.

    Returns:
        Diccionario con el payload del token.

    Raises:
        TokenExpiredError:      Si el token expiro.
        TokenNotYetValidError:  Si el token aun no es valido.
        TokenInvalidError:      Si el token es invalido por cualquier otra razon
                                (firma incorrecta, formato corrupto, claims
                                faltantes, tipo incorrecto, etc.).
    """
    if not isinstance(token, str) or not token:
        raise TokenInvalidError("token debe ser un string no vacio")

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],   # lista explicita: evita 'alg: none'
            options={
                "require": list(_REQUIRED_CLAIMS),  # todos los claims deben estar
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
            },
        )

    except ExpiredSignatureError as exc:
        raise TokenExpiredError("el token expiro") from exc

    except ImmatureSignatureError as exc:
        raise TokenNotYetValidError("el token aun no es valido") from exc

    except InvalidAlgorithmError as exc:
        raise TokenInvalidError("algoritmo de firma no permitido") from exc

    except (DecodeError, InvalidTokenError) as exc:
        # Incluye firma invalida, formato corrupto, claims faltantes, etc.
        raise TokenInvalidError("token invalido") from exc

    # Validacion adicional de negocio: el tipo debe ser "access".
    if payload.get("type") != _TOKEN_TYPE_ACCESS:
        raise TokenInvalidError(
            f"tipo de token invalido: se esperaba '{_TOKEN_TYPE_ACCESS}'"
        )

    # Validacion defensiva: roles debe ser una lista de strings.
    roles = payload.get("roles")
    if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
        raise TokenInvalidError("claim 'roles' debe ser una lista de strings")

    return payload