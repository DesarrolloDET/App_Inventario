from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class EtapaViaje(Base):
    __tablename__ = "etapas_viaje"

    etapa_viaje_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    cita_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("citas.cita_id", ondelete="CASCADE"),
        nullable=False
    )

    orden_etapa: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False
    )

    tipo_etapa: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="BLOQUEADA"
    )

    fecha_habilitada: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    fecha_inicio: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    fecha_finalizacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    usuario_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("usuarios.usuario_id"),
        nullable=True
    )

    resultado: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    observacion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    cita: Mapped["Cita"] = relationship(
        back_populates="etapas"
    )

    usuario: Mapped["Usuario | None"] = relationship()

    __table_args__ = (
    UniqueConstraint(
        "cita_id",
        "orden_etapa",
        name="etapas_viaje_cita_id_orden_etapa_key"
    ),
    UniqueConstraint(
        "cita_id",
        "tipo_etapa",
        name="etapas_viaje_cita_id_tipo_etapa_key"
    ),
    Index(
        "idx_etapas_cita_estado",
        "cita_id",
        "estado"
    ),
    Index(
        "idx_etapas_tipo_estado",
        "tipo_etapa",
        "estado"
    ),
)