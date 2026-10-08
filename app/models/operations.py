from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Viaje(Base):
    __tablename__ = "viajes"

    viaje_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    vehiculo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vehiculos.vehiculo_id"),
        nullable=False
    )

    conductor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conductores.conductor_id"),
        nullable=False
    )

    materia_prima_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materias_primas.materia_prima_id"),
        nullable=False
    )

    puerto_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("puertos.puerto_id"),
        nullable=False
    )

    fecha_hora_cargue: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    validado_cargue: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PROGRAMADO"
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    vehiculo: Mapped["Vehiculo"] = relationship()

    conductor: Mapped["Conductor"] = relationship()

    materia_prima: Mapped["MateriaPrima"] = relationship()

    puerto: Mapped["Puerto"] = relationship()

    solicitud_cita: Mapped["SolicitudCita | None"] = relationship(
        back_populates="viaje",
        uselist=False
    )
    __table_args__ = (
    Index(
        "idx_viajes_vehiculo",
        "vehiculo_id"
    ),
    Index(
        "idx_viajes_estado",
        "estado"
    ),
)


class SolicitudCita(Base):
    __tablename__ = "solicitudes_cita"

    solicitud_cita_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    viaje_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("viajes.viaje_id"),
        nullable=False
    )

    fecha_solicitud: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDIENTE"
    )

    viaje: Mapped["Viaje"] = relationship(
        back_populates="solicitud_cita"
    )

    cita: Mapped["Cita | None"] = relationship(
        back_populates="solicitud_cita",
        uselist=False
    )
    __table_args__ = (
    Index(
        "idx_solicitudes_viaje",
        "viaje_id"
    ),
)


class Cita(Base):
    __tablename__ = "citas"

    cita_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    solicitud_cita_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("solicitudes_cita.solicitud_cita_id"),
        nullable=False,
        unique=True
    )

    cupo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cupos.cupo_id"),
        nullable=False
    )

    fecha_hora_programada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    fecha_hora_llegada: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CONFIRMADA"
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    solicitud_cita: Mapped["SolicitudCita"] = relationship(
        back_populates="cita"
    )

    cupo: Mapped["Cupo"] = relationship()

    etapas: Mapped[list["EtapaViaje"]] = relationship(
        back_populates="cita",
        cascade="all, delete-orphan"
    )
    __table_args__ = (
    Index(
        "idx_citas_estado",
        "estado"
    ),
    Index(
        "idx_citas_fecha_programada",
        "fecha_hora_programada"
    ),
    Index(
        "idx_citas_llegada",
        "fecha_hora_llegada"
    ),
    Index(
        "uq_cupo_cita_activa",
        "cupo_id",
        unique=True,
        postgresql_where=(
            "estado NOT IN ('CANCELADA','NO_SHOW')"
        )
    ),
)