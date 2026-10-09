"""agregar puerto_id a programacion_detalle y llegadas previas a citas

Revision ID: 5213103761c7
Revises: b3f25b90d0e2
Create Date: 2026-10-09 12:06:40.423363

Notas de ajuste manual:
- El FK 'fk_programacion_detalle_puerto_id' se nombra explicitamente para
  que el downgrade pueda eliminarlo sin ambiguedad. Alembic autogenero
  un create_foreign_key(None, ...) que funcionaria en upgrade pero
  romperia el downgrade.
- Se asume que programacion_detalle esta vacia (0 filas), por lo que
  agregar puerto_id NOT NULL directamente es seguro. Si hubiera filas,
  habria que hacer: add_column nullable -> UPDATE -> alter_column NOT NULL.
- El ondelete='RESTRICT' del FK significa que no se puede eliminar un
  puerto mientras tenga detalles de programacion apuntandole.
  Coherente con la politica de no borrar historia.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5213103761c7'
down_revision: Union[str, Sequence[str], None] = 'b3f25b90d0e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- citas: nuevas columnas para eventos previos ---
    op.add_column(
        'citas',
        sa.Column(
            'fecha_hora_llegada_parqueadero',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        'citas',
        sa.Column(
            'fecha_hora_inicio_previos',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        'idx_citas_llegada_parqueadero',
        'citas',
        ['fecha_hora_llegada_parqueadero'],
        unique=False,
    )

    # --- programacion_detalle: FK a puertos ---
    # Como la tabla esta vacia, se puede agregar NOT NULL directo.
    op.add_column(
        'programacion_detalle',
        sa.Column('puerto_id', sa.Integer(), nullable=False),
    )
    op.create_index(
        'idx_prog_det_puerto',
        'programacion_detalle',
        ['puerto_id'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_programacion_detalle_puerto_id',   # <-- nombre explicito
        'programacion_detalle',
        'puertos',
        ['puerto_id'],
        ['puerto_id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    """Downgrade schema."""
    # --- programacion_detalle: revertir FK ---
    op.drop_constraint(
        'fk_programacion_detalle_puerto_id',
        'programacion_detalle',
        type_='foreignkey',
    )
    op.drop_index(
        'idx_prog_det_puerto',
        table_name='programacion_detalle',
    )
    op.drop_column('programacion_detalle', 'puerto_id')

    # --- citas: revertir columnas previas ---
    op.drop_index(
        'idx_citas_llegada_parqueadero',
        table_name='citas',
    )
    op.drop_column('citas', 'fecha_hora_inicio_previos')
    op.drop_column('citas', 'fecha_hora_llegada_parqueadero')