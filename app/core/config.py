"""
Configuracion central del sistema MEJIA TURNOS.

Lee variables de entorno desde .env (desarrollo) o variables del sistema
(produccion). Valida tipos y reglas de negocio desde el arranque.

Reglas aplicadas:
- Seccion 23: secretos fuera del codigo.
- Seccion 29: variables de entorno.
- Seccion 31: validacion de tipos y obligatorios.
- Seccion 66: configuracion segura antes de cualquier otra cosa.

Decisiones de diseno:
- En produccion NO se confia en el archivo .env: los secretos vienen
  exclusivamente de variables de entorno del contenedor / Secret Manager.
- Las variables de entorno del sistema SIEMPRE ganan sobre .env.
- SECRET_KEY y DB_PASSWORD se limpian de espacios y saltos de linea
  al cargarse, para evitar el bug silencioso de .env con \\n al final.
"""

from __future__ import annotations

from enum import Enum
import os
from pathlib import Path
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


# ---------------------------------------------------------------------------
# Constantes internas
# ---------------------------------------------------------------------------

# Valor centinela que aparece en .env.example.
# NO es una clave real. Sirve para que el sistema detecte si alguien
# olvido reemplazar el placeholder en produccion y falle al arrancar.
# NO cambiar este valor.
_INVALID_PRODUCTION_SECRET = "CAMBIAR_ESTA_CLAVE_POR_UNA_ALEATORIA_DE_64_BYTES"

# Longitud minima aceptable de SECRET_KEY en produccion.
# 32 bytes (256 bits) es el minimo recomendado para HS256.
_MIN_SECRET_LENGTH = 32


class Environment(str, Enum):
    """Entornos soportados por la aplicacion."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

_APP_ENV_RAW = os.getenv("APP_ENV", "development").strip().lower()
_IS_PRODUCTION = _APP_ENV_RAW == "production"

_ENV_FILE: Path | None = None if _IS_PRODUCTION else Path(".env")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """
    Configuracion tipada y validada de MEJIA TURNOS.

    Comportamiento segun entorno:
      - development / staging: lee .env + variables de entorno.
        Las variables de entorno del sistema GANAN sobre .env.
      - production: NO lee .env. Solo lee variables de entorno del
        sistema (Secret Manager, env vars del contenedor, etc.).

    Reglas de validacion:
      - SECRET_KEY y DB_PASSWORD se limpian de espacios y saltos de linea.
      - En produccion, SECRET_KEY no puede ser el placeholder ni tener
        menos de 32 caracteres.
      - En produccion, DB_PASSWORD es obligatoria.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Entorno ---
    APP_ENV: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Entorno de ejecucion: development | staging | production",
    )

    # --- Base de datos ---
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432, ge=1, le=65535)
    DB_NAME: str = Field(default="mejia_turnos")
    DB_USER: str = Field(default="postgres")
    DB_PASSWORD: str = Field(default="")

    # --- Seguridad ---
    SECRET_KEY: str = Field(
        default=_INVALID_PRODUCTION_SECRET,
        description=(
            "Clave simetrica para firmar JWT. En produccion debe tener al "
            "menos 32 caracteres y no ser el placeholder."
        ),
    )
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = Field(
        default="HS256",
        description="Algoritmo de firma JWT. Solo HMAC permitido por ahora.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Duracion del access token en minutos (1 min a 24 h).",
    )

    # -----------------------------------------------------------------------
    # Precedencia explicita de fuentes
    # -----------------------------------------------------------------------

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        Orden de precedencia de fuentes.

        En pydantic-settings v2, el ULTIMO de la tupla es el que GANA.

        Orden final:
          1. init_settings        (argumentos al constructor)
          2. dotenv_settings      (archivo .env)
          3. env_settings         (variables de entorno del sistema)  <- GANA
          4. file_secret_settings (secretos montados como archivos)

        Garantiza que en produccion las variables de entorno del
        contenedor SIEMPRE sobreescriban el .env.
        """
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    # -----------------------------------------------------------------------
    # Propiedades derivadas
    # -----------------------------------------------------------------------

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == Environment.DEVELOPMENT

    @property
    def database_url(self) -> str:
        """Construye la URL de conexion a PostgreSQL."""
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASSWORD)
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # -----------------------------------------------------------------------
    # Validadores
    # -----------------------------------------------------------------------

    @field_validator("SECRET_KEY", "DB_PASSWORD", mode="before")
    @classmethod
    def _strip_whitespace(cls, value: Any) -> Any:
        """
        Elimina espacios y saltos de linea al inicio/final.

        Previene el bug silencioso de .env cuando el valor termina en \\n.
        Si SECRET_KEY tuviera un \\n, los JWT firmados en un arranque no
        serian validos en otro arranque sin \\n, tumbando sesiones.
        """
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _validate_production_requirements(self) -> "Settings":
        """Reglas adicionales cuando APP_ENV == production."""
        if self.APP_ENV == Environment.PRODUCTION:
            if not self.SECRET_KEY or self.SECRET_KEY == _INVALID_PRODUCTION_SECRET:
                raise ValueError(
                    "SECRET_KEY no configurada para produccion. "
                    "Defina una clave aleatoria de al menos 32 caracteres."
                )
            if len(self.SECRET_KEY) < _MIN_SECRET_LENGTH:
                raise ValueError(
                    f"SECRET_KEY demasiado corta para produccion "
                    f"(minimo {_MIN_SECRET_LENGTH} caracteres)."
                )
            if not self.DB_PASSWORD:
                raise ValueError("DB_PASSWORD no configurada para produccion.")
        return self


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Devuelve la instancia unica de Settings.

    lru_cache garantiza que el archivo .env se lea una sola vez por
    proceso y que todos los modulos compartan la misma configuracion.
    """
    return Settings()


settings = get_settings()