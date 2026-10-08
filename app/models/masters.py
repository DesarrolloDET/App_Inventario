from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Transportadora(Base):
    __tablename__ = "transportadoras"

    transportadora_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    nit: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False
    )

    razon_social: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    vehiculos: Mapped[list["Vehiculo"]] = relationship(
        back_populates="transportadora"
    )


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    vehiculo_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    placa: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False
    )

    transportadora_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("transportadoras.transportadora_id"),
        nullable=False
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    transportadora: Mapped["Transportadora"] = relationship(
        back_populates="vehiculos"
    )


class Conductor(Base):
    __tablename__ = "conductores"

    conductor_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    documento: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False
    )

    nombre_completo: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )


class MateriaPrima(Base):
    __tablename__ = "materias_primas"

    materia_prima_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    codigo: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    nombre: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )


class Puerto(Base):
    __tablename__ = "puertos"

    puerto_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    nombre: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )