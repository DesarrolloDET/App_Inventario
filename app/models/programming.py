from datetime import date, time, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Programacion(Base):
    __tablename__ = "programaciones"

    programacion_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    fecha_inicio: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    fecha_fin: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="BORRADOR"
    )

    usuario_creador_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("usuarios.usuario_id"),
        nullable=True
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    usuario_creador: Mapped["Usuario | None"] = relationship()

    detalles: Mapped[list["ProgramacionDetalle"]] = relationship(
        back_populates="programacion",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "fecha_fin >= fecha_inicio",
            name="ck_programaciones_fechas"
        ),
        CheckConstraint(
            "estado IN ('BORRADOR','PUBLICADA','CERRADA','CANCELADA')",
            name="ck_programaciones_estado"
        ),
    )


class ProgramacionDetalle(Base):
    __tablename__ = "programacion_detalle"

    programacion_detalle_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    programacion_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "programaciones.programacion_id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    fecha_operacion: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    transportadora_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("transportadoras.transportadora_id"),
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

    cantidad_vehiculos: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    programacion: Mapped["Programacion"] = relationship(
        back_populates="detalles"
    )

    transportadora: Mapped["Transportadora"] = relationship()

    materia_prima: Mapped["MateriaPrima"] = relationship()

    puerto: Mapped["Puerto"] = relationship()

    cupos: Mapped[list["Cupo"]] = relationship(
        back_populates="programacion_detalle",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
    CheckConstraint(
        "cantidad_vehiculos > 0",
        name="ck_programacion_detalle_cantidad"
    ),
    Index(
        "idx_prog_det_fecha",
        "fecha_operacion"
    ),
    Index(
        "idx_prog_det_transportadora",
        "transportadora_id"
    ),
    Index(
        "idx_prog_det_materia",
        "materia_prima_id"
    ),
        Index(
        "idx_prog_det_puerto",
        "puerto_id"
    ),
)


class Cupo(Base):
    __tablename__ = "cupos"

    cupo_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    programacion_detalle_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "programacion_detalle.programacion_detalle_id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    fecha: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    hora_inicio: Mapped[time] = mapped_column(
        Time,
        nullable=False
    )

    hora_fin: Mapped[time] = mapped_column(
        Time,
        nullable=False
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    programacion_detalle: Mapped["ProgramacionDetalle"] = relationship(
        back_populates="cupos"
    )

    __table_args__ = (
    CheckConstraint(
        "hora_fin > hora_inicio",
        name="ck_cupos_horas"
    ),
    UniqueConstraint(
        "programacion_detalle_id",
        "fecha",
        "hora_inicio",
        "hora_fin",
        name="cupos_programacion_detalle_id_fecha_hora_inicio_hora_fin_key"
    ),
    Index(
        "idx_cupos_fecha_hora",
        "fecha",
        "hora_inicio",
        "hora_fin"
    ),
)


class BloqueoHorario(Base):
    __tablename__ = "bloqueos_horarios"

    bloqueo_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    fecha: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    hora_inicio: Mapped[time] = mapped_column(
        Time,
        nullable=False
    )

    hora_fin: Mapped[time] = mapped_column(
        Time,
        nullable=False
    )

    tipo_bloqueo: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    __table_args__ = (
        CheckConstraint(
            "hora_fin > hora_inicio",
            name="ck_bloqueos_horas"
        ),
        Index(
            "idx_bloqueos_fecha_hora",
            "fecha",
            "hora_inicio",
            "hora_fin"
        ),
    )