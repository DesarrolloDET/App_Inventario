"""
Router de autenticacion de MEJIA TURNOS.

Endpoints:
- POST /auth/login  -> recibe credenciales, devuelve un JWT.
- GET  /auth/me     -> devuelve el usuario autenticado.

Reglas aplicadas:
- Seccion 24: autenticacion segura.
- Seccion 25: verificacion desde backend.
- Seccion 28: NUNCA loggear passwords.
- Seccion 32: manejo de errores seguro (mensajes genericos al cliente).

Diseno:
- Los endpoints son DELGADOS: solo orquestan service + jwt.
- La logica de negocio esta en app.services.auth_service.
- La validacion del token esta en app.core.dependencies.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.jwt import create_access_token
from app.database.connection import get_db
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UsuarioActualResponse,
)
from app.services.auth_service import autenticar_usuario


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
# prefix="/auth" agrupa todos los endpoints bajo /auth en la documentacion.
# tags=["auth"] los agrupa visualmente en Swagger.
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Autenticar usuario y obtener un token JWT",
    responses={
        200: {"description": "Credenciales validas. Devuelve el token."},
        401: {"description": "Credenciales invalidas."},
        422: {"description": "Cuerpo de la peticion malformado."},
    },
)
def login(
    credenciales: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """
    Autentica a un usuario con username + password.

    - Si las credenciales son validas, devuelve un JWT firmado.
    - Si son invalidas, devuelve 401 con un mensaje GENERICO.

    El mensaje es siempre el mismo ("Credenciales invalidas") tanto si
    el username no existe como si el password es incorrecto, para no
    revelar que usuarios existen.
    """
    usuario = autenticar_usuario(
        db=db,
        username=credenciales.username,
        password=credenciales.password,
    )

    # Credenciales invalidas: 401 con mensaje generico.
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Credenciales validas: generar token.
    roles = [rol.nombre for rol in usuario.roles]

    token = create_access_token(
        subject=usuario.usuario_id,
        roles=roles,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UsuarioActualResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener el usuario autenticado actual",
    responses={
        200: {"description": "Devuelve los datos publicos del usuario."},
        401: {"description": "Token ausente, invalido o expirado."},
    },
)
def me(usuario: CurrentUser) -> UsuarioActualResponse:
    """
    Devuelve los datos publicos del usuario autenticado.

    La dependencia CurrentUser valida el token, busca al usuario y
    verifica su estado antes de llegar aqui.

    NUNCA devuelve password_hash ni datos sensibles.
    """
    return UsuarioActualResponse(
        usuario_id=usuario.usuario_id,
        username=usuario.username,
        nombre=usuario.nombre,
        roles=[rol.nombre for rol in usuario.roles],
        activo=usuario.activo,
    )