from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Rol(Base):
    __tablename__ = "roles"

    rol_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    nombre: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    usuarios: Mapped[list["Usuario"]] = relationship(
        secondary="usuario_rol",
        back_populates="roles"
    )


class Usuario(Base):
    __tablename__ = "usuarios"

    usuario_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    username: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False
    )

    nombre: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    correo: Mapped[str | None] = mapped_column(
        String(150),
        unique=True,
        nullable=True
    )

    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    roles: Mapped[list["Rol"]] = relationship(
        secondary="usuario_rol",
        back_populates="usuarios"
    )


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    usuario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.usuario_id"),
        primary_key=True
    )

    rol_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("roles.rol_id"),
        primary_key=True
    )