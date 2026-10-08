from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Auditoria(Base):
    __tablename__ = "auditoria"

    auditoria_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    usuario_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("usuarios.usuario_id"),
        nullable=True
    )

    entidad: Mapped[str] = mapped_column(
        String(80),
        nullable=False
    )

    entidad_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    accion: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    valor_anterior: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    valor_nuevo: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    motivo: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    usuario: Mapped["Usuario | None"] = relationship()

    __table_args__ = (
    Index(
        "idx_auditoria_entidad",
        "entidad",
        "entidad_id"
    ),
    Index(
        "idx_auditoria_fecha",
        "fecha_hora"
    ),
    Index(
        "idx_auditoria_usuario",
        "usuario_id"
    ),
)