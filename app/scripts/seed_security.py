"""
Script de inicializacion de seguridad para MEJIA TURNOS.

Crea:
- Los 6 roles base del sistema.
- Un usuario administrador inicial con contrasena aleatoria.

Idempotente: si los recursos ya existen, no los vuelve a crear.
Esto permite correr el script multiples veces sin errores.

Uso:
    python -m app.scripts.seed_security

Reglas aplicadas:
- Seccion 26: roles iniciales.
- Seccion 28: NUNCA guardar contrasenas en codigo.
- Seccion 51: no modificar produccion manualmente.

IMPORTANTE:
- La contrasena del admin se imprime UNA SOLA VEZ.
- Guardarla en un gestor de secretos INMEDIATAMENTE.
- Si se pierde, hay que borrar el usuario en BD y volver a correr.
"""

from __future__ import annotations

import secrets
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database.connection import SessionLocal
from app.models.security import Rol, Usuario


# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

# Roles iniciales del sistema. Orden = jerarquia logica (no tecnica).
ROLES_INICIALES: list[str] = [
    "ADMINISTRADOR",
    "SUPERVISOR",
    "PORTERIA",
    "CALIDAD",
    "BASCULA",
    "DESCARGUE",
]

# Datos del usuario admin inicial.
ADMIN_USERNAME = "admin"
ADMIN_NOMBRE = "Administrador del Sistema"
ADMIN_CORREO = "sistemas@concentradospollorico.com"

# Longitud en bytes de la contrasena generada.
# 24 bytes -> ~32 caracteres url-safe -> ~192 bits de entropia.
_ADMIN_PASSWORD_BYTES = 24


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generar_password() -> str:
    """Genera una contrasena aleatoria, segura y url-safe."""
    return secrets.token_urlsafe(_ADMIN_PASSWORD_BYTES)


def _existe_rol(db: Session, nombre: str) -> bool:
    """Devuelve True si el rol con ese nombre ya existe en BD."""
    return (
        db.execute(select(Rol).where(Rol.nombre == nombre)).scalar_one_or_none()
        is not None
    )


def _existe_usuario(db: Session, username: str) -> bool:
    """Devuelve True si el usuario con ese username ya existe en BD."""
    return (
        db.execute(
            select(Usuario).where(Usuario.username == username)
        ).scalar_one_or_none()
        is not None
    )


# ---------------------------------------------------------------------------
# Paso 1: crear roles
# ---------------------------------------------------------------------------

def crear_roles(db: Session) -> list[str]:
    """
    Crea los roles base si no existen.

    Returns:
        Lista de nombres de roles que fueron CREADOS en esta ejecucion.
        Los que ya existian no se incluyen.
    """
    creados: list[str] = []

    for nombre in ROLES_INICIALES:
        if _existe_rol(db, nombre):
            continue

        rol = Rol(nombre=nombre)
        db.add(rol)
        creados.append(nombre)

    return creados


# ---------------------------------------------------------------------------
# Paso 2: crear usuario admin
# ---------------------------------------------------------------------------

def crear_admin_si_no_existe(db: Session) -> tuple[Usuario, str | None]:
    """
    Crea el usuario admin si no existe.

    Returns:
        (usuario, password_plana_o_None)
        - Si el admin fue creado: (Usuario, "contrasena_en_texto_plano")
        - Si ya existia:          (Usuario, None)

    Notas:
        - La contrasena se genera con secrets.token_urlsafe.
        - NUNCA se loggea, solo se retorna para que el main() la imprima
          una unica vez.
    """
    existente = db.execute(
        select(Usuario).where(Usuario.username == ADMIN_USERNAME)
    ).scalar_one_or_none()

    if existente is not None:
        return existente, None

    password_plana = generar_password()

    admin = Usuario(
        username=ADMIN_USERNAME,
        nombre=ADMIN_NOMBRE,
        correo=ADMIN_CORREO,
        password_hash=hash_password(password_plana),
        activo=True,
    )
    db.add(admin)
    db.flush()  # para que admin.usuario_id este disponible

    return admin, password_plana


# ---------------------------------------------------------------------------
# Paso 3: asignar rol ADMINISTRADOR
# ---------------------------------------------------------------------------

def asignar_rol_a_usuario(
    db: Session,
    usuario: Usuario,
    nombre_rol: str,
) -> bool:
    """
    Asigna un rol a un usuario si no lo tiene ya.

    Returns:
        True si se hizo la asignacion, False si ya la tenia.
    """
    rol = db.execute(
        select(Rol).where(Rol.nombre == nombre_rol)
    ).scalar_one_or_none()

    if rol is None:
        raise RuntimeError(
            f"Rol '{nombre_rol}' no existe en BD. "
            "Corra primero crear_roles()."
        )

    # Cargar roles actuales del usuario.
    # usuario.roles se carga perezosamente; forzamos la carga.
    _ = list(usuario.roles)

    if rol in usuario.roles:
        return False

    usuario.roles.append(rol)
    return True


# ---------------------------------------------------------------------------
# Paso 4: imprimir credenciales
# ---------------------------------------------------------------------------

def imprimir_credenciales(username: str, password_plana: str) -> None:
    """
    Imprime las credenciales del admin UNA SOLA VEZ.

    El formato es claro para que el usuario lo note.
    NO se loggea en ningun otro lado.
    """
    linea = "=" * 70
    print()
    print(linea)
    print("  USUARIO ADMINISTRADOR CREADO — GUARDE ESTA CONTRASENA AHORA")
    print(linea)
    print(f"  Username: {username}")
    print(f"  Password: {password_plana}")
    print()
    print("  Esta contrasena NO se volvera a mostrar.")
    print("  Guardela en un gestor de secretos AHORA.")
    print("  Si la pierde, tendra que borrar el usuario y volver a correr.")
    print(linea)
    print()


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------

def main() -> int:
    """
    Ejecuta el seed completo.

    Returns:
        0 si todo fue bien, 1 si hubo error.
    """
    print("Iniciando seed de seguridad de MEJIA TURNOS...")
    print()

    try:
        with SessionLocal() as db:
            # 1. Roles
            print("[1/3] Creando roles base...")
            roles_creados = crear_roles(db)
            if roles_creados:
                print(f"      Creados: {', '.join(roles_creados)}")
            else:
                print("      Todos los roles ya existian.")

            # 2. Admin
            print("[2/3] Verificando usuario admin...")
            admin, password_plana = crear_admin_si_no_existe(db)
            if password_plana:
                print(f"      Admin '{admin.username}' creado.")
            else:
                print(f"      Admin '{admin.username}' ya existia.")

            # 3. Asignar rol
            print("[3/3] Asignando rol ADMINISTRADOR al admin...")
            asignado = asignar_rol_a_usuario(db, admin, "ADMINISTRADOR")
            if asignado:
                print("      Rol asignado.")
            else:
                print("      El admin ya tenia el rol.")

            # Commit: si algo fallo antes, esta linea no se alcanza
            # y el contexto de sesion hara rollback automatico.
            db.commit()

        # Imprimir credenciales SOLO si el admin fue creado.
        if password_plana:
            imprimir_credenciales(admin.username, password_plana)

        print("Seed completado exitosamente.")
        return 0

    except Exception as exc:
        # No exponer trazas sensibles al usuario.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())