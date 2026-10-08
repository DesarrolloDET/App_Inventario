"""
Schemas Pydantic para autenticacion en MEJIA TURNOS.

"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Entrada: POST /auth/login
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """
    Cuerpo de la peticion POST /auth/login.

    El cliente envia username + password. El backend:
      1. Busca al usuario por username.
      2. Verifica el password contra password_hash (argon2).
      3. Si coincide y el usuario esta activo, devuelve un JWT.
    """

    model_config = ConfigDict(
        extra="forbid",           # rechaza campos desconocidos
        str_strip_whitespace=True, # limpia espacios al inicio/final
    )

    username: str = Field(
        ...,
        min_length=1,
        max_length=80,
        description="Nombre de usuario. No distingue mayusculas/minusculas.",
        examples=["admin"],
    )

    password: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Contrasena en texto plano. NUNCA se almacena ni se loguea.",
        examples=["MiClaveSegura123!"],
    )


# ---------------------------------------------------------------------------
# Salida: POST /auth/login
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """
    Respuesta de POST /auth/login cuando las credenciales son validas.

    Contiene SOLO el token de acceso y metadatos publicos.
    NUNCA incluye el password_hash ni datos sensibles del usuario.
    """

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(
        ...,
        description="Token JWT de acceso. Usar en cabecera 'Authorization: Bearer <token>'.",
    )

    token_type: str = Field(
        default="bearer",
        description="Tipo de token. Siempre 'bearer' (RFC 6750).",
    )

    expires_in: int = Field(
        ...,
        ge=1,
        description="Segundos hasta que el access_token expire.",
        examples=[1800],
    )


# ---------------------------------------------------------------------------
# Payload tipado del JWT (interno)
# ---------------------------------------------------------------------------

class TokenPayload(BaseModel):
    """
    Estructura tipada del payload de un JWT de MEJIA TURNOS.

    Se usa internamente en app.core.dependencies.get_current_user para
    validar de forma explicita que el token contiene lo que esperamos.

    Refleja exactamente lo que app.core.jwt.create_access_token produce.
    Si cambia el formato del token, este schema debe cambiar tambien.
    """

    model_config = ConfigDict(extra="allow")  # permite claims futuros

    sub: str = Field(
        ...,
        description="usuario_id como string (requerido por la spec JWT).",
    )

    roles: list[str] = Field(
        default_factory=list,
        description="Nombres de los roles asignados al usuario.",
    )

    type: str = Field(
        ...,
        description="Tipo de token: 'access' o 'refresh'.",
    )

    jti: str = Field(
        ...,
        description="Identificador unico del token (UUID).",
    )

    iat: datetime = Field(..., description="Momento de emision del token.")
    nbf: datetime = Field(..., description="Momento desde el cual el token es valido.")
    exp: datetime = Field(..., description="Momento de expiracion del token.")

    @property
    def usuario_id(self) -> int:
        """
        Convierte 'sub' (string) al usuario_id (int).

        Se define como propiedad para que el resto del codigo no tenga
        que acordarse de convertir manualmente.
        """
        return int(self.sub)


# ---------------------------------------------------------------------------
# Salida: GET /auth/me
# ---------------------------------------------------------------------------

class UsuarioActualResponse(BaseModel):
    """
    Respuesta de GET /auth/me.

    Devuelve SOLO la informacion publica del usuario autenticado.
    NUNCA incluye password_hash, correo (si no es necesario) ni otros
    datos sensibles.
    """

    model_config = ConfigDict(extra="forbid")

    usuario_id: int = Field(..., description="ID del usuario.")
    username: str = Field(..., description="Nombre de usuario.")
    nombre: str = Field(..., description="Nombre completo del usuario.")
    roles: list[str] = Field(
        default_factory=list,
        description="Nombres de los roles del usuario.",
    )
    activo: bool = Field(..., description="Si el usuario esta activo.")