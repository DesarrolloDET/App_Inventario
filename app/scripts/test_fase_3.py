"""
Script de pruebas de integracion de la FASE 3 - Programacion.

Crea datos de prueba, ejecuta el flujo completo de negocio, verifica
los resultados y limpia todo al final. NO se conecta por HTTP: usa
los services directamente.

Uso:
    python -m app.scripts.test_fase_3

Resultado:
    - Imprime un reporte con [OK]/[FALLO] por prueba.
    - Retorna exit code 0 si todo pasa, 1 si algo falla.
    - Limpia los datos de prueba incluso si hay excepciones.

Datos de prueba:
    - Se usa la fecha 2099-01-15 para no chocar con datos reales.
    - Se crean maestros con codigos/nombres que empiezan con 'ZZTEST-'.
    - Todo se limpia al final, incluso si falla.
"""

from __future__ import annotations

import sys
from datetime import date, time
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.horario_operativo import (
    ALMUERZO_FIN,
    ALMUERZO_INICIO,
    generar_franjas_dia,
)
from app.database.connection import SessionLocal
from app.models.masters import (
    MateriaPrima,
    Puerto,
    Transportadora,
)
from app.models.programming import (
    BloqueoHorario,
    Cupo,
    Programacion,
    ProgramacionDetalle,
)
from app.models.security import Usuario
from app.schemas.bloqueos import BloqueoCreate, TipoBloqueo
from app.schemas.programacion_detalle import (
    ProgramacionDetalleCreate,
    ProgramacionDetalleUpdate,
)
from app.schemas.programaciones import (
    EstadoProgramacion,
    ProgramacionCreate,
    ProgramacionUpdate,
)
from app.services import bloqueos_service as bl_svc
from app.services import programacion_detalle_service as det_svc
from app.services import programaciones_service as prog_svc


# ---------------------------------------------------------------------------
# Fecha y prefijos de prueba
# ---------------------------------------------------------------------------

FECHA_TEST = date(2099, 1, 15)
PREFIJO_TEST = "ZZTEST-"


# ---------------------------------------------------------------------------
# Runner de pruebas
# ---------------------------------------------------------------------------

class Runner:
    """Acumula resultados de pruebas."""

    def __init__(self) -> None:
        self.resultados: list[tuple[str, bool, str]] = []

    def probar(self, nombre: str, fn: Callable[[], None]) -> None:
        """
        Ejecuta una prueba.

        Args:
            nombre: descripcion legible.
            fn: funcion sin argumentos. Debe lanzar AssertionError si falla.
        """
        try:
            fn()
        except AssertionError as exc:
            self.resultados.append((nombre, False, str(exc)))
        except Exception as exc:
            self.resultados.append((nombre, False, f"{type(exc).__name__}: {exc}"))
        else:
            self.resultados.append((nombre, True, ""))

    def imprimir(self) -> None:
        print()
        print("=" * 70)
        print("  PRUEBAS DE INTEGRACION - FASE 3")
        print("=" * 70)

        ok_count = 0
        for nombre, ok, detalle in self.resultados:
            marca = "[OK]" if ok else "[FALLO]"
            print(f"  {marca:8s} {nombre}")
            if not ok:
                print(f"           {detalle}")
            else:
                ok_count += 1

        total = len(self.resultados)
        print("-" * 70)
        print(f"  {ok_count}/{total} pruebas pasaron.")
        print("=" * 70)
        print()


# ---------------------------------------------------------------------------
# Helpers de setup
# ---------------------------------------------------------------------------

def _obtener_o_crear_transportadora(db: Session) -> Transportadora:
    """Obtiene o crea una transportadora de prueba."""
    t = db.execute(
        select(Transportadora).where(
            Transportadora.nit == f"{PREFIJO_TEST}TRANSP"
        )
    ).scalar_one_or_none()
    if t is None:
        t = Transportadora(
            nit=f"{PREFIJO_TEST}TRANSP",
            razon_social="Transportadora de Prueba",
            activo=True,
        )
        db.add(t)
        db.flush()
    return t


def _obtener_o_crear_materia(db: Session) -> MateriaPrima:
    """Obtiene o crea una materia prima de prueba."""
    m = db.execute(
        select(MateriaPrima).where(
            MateriaPrima.codigo == f"{PREFIJO_TEST}MP"
        )
    ).scalar_one_or_none()
    if m is None:
        m = MateriaPrima(
            codigo=f"{PREFIJO_TEST}MP",
            nombre="Materia Prima de Prueba",
            activo=True,
        )
        db.add(m)
        db.flush()
    return m


def _obtener_o_crear_puerto(db: Session) -> Puerto:
    """Obtiene o crea un puerto de prueba."""
    p = db.execute(
        select(Puerto).where(
            Puerto.nombre == f"{PREFIJO_TEST}PUERTO"
        )
    ).scalar_one_or_none()
    if p is None:
        p = Puerto(
            nombre=f"{PREFIJO_TEST}PUERTO",
            activo=True,
        )
        db.add(p)
        db.flush()
    return p


def _obtener_admin(db: Session) -> Usuario:
    """Obtiene el usuario admin (debe existir por el seed)."""
    admin = db.execute(
        select(Usuario).where(Usuario.username == "admin")
    ).scalar_one_or_none()
    if admin is None:
        raise RuntimeError(
            "Usuario 'admin' no encontrado. "
            "Ejecute 'python -m app.scripts.seed_security' primero."
        )
    return admin


# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------

def limpiar_datos_test(db: Session) -> None:
    """
    Elimina todos los datos de prueba.

    Se ejecuta en finally para garantizar la limpieza incluso si una
    prueba falla.
    """
    # Cupos
    cupos = db.execute(
        select(Cupo).where(Cupo.fecha == FECHA_TEST)
    ).scalars().all()
    for c in cupos:
        db.delete(c)

    # Bloqueos
    bls = db.execute(
        select(BloqueoHorario).where(BloqueoHorario.fecha == FECHA_TEST)
    ).scalars().all()
    for b in bls:
        db.delete(b)

    # Detalles y programaciones
    progs = db.execute(
        select(Programacion).where(
            Programacion.fecha_inicio == FECHA_TEST
        )
    ).scalars().all()
    for p in progs:
        # Detalles y cupos se borran por cascade.
        db.delete(p)

    db.flush()


# ---------------------------------------------------------------------------
# Pruebas individuales
# ---------------------------------------------------------------------------

def run_pruebas() -> int:
    """Ejecuta todas las pruebas. Retorna exit code."""
    runner = Runner()

    with SessionLocal() as db:
        try:
            # --- Setup ---
            admin = _obtener_admin(db)
            t = _obtener_o_crear_transportadora(db)
            m = _obtener_o_crear_materia(db)
            p = _obtener_o_crear_puerto(db)
            db.commit()

            # ============================================================
            # SECCION 1: Flujo completo
            # ============================================================

            # Contenedores compartidos entre pruebas.
            ctx: dict = {}

            def prueba_1_crear_programacion() -> None:
                prog = prog_svc.crear_programacion(
                    db,
                    ProgramacionCreate(
                        fecha_inicio=FECHA_TEST,
                        fecha_fin=FECHA_TEST,
                    ),
                    usuario_creador=admin,
                )
                db.commit()
                assert prog.estado == "BORRADOR", f"estado={prog.estado}"
                assert prog.fecha_inicio == FECHA_TEST
                ctx["prog_id"] = prog.programacion_id

            runner.probar("1. Crear programacion en BORRADOR", prueba_1_crear_programacion)

            def prueba_2_detalle_max_capacidad() -> None:
                det = det_svc.crear_detalle(
                    db, ctx["prog_id"],
                    ProgramacionDetalleCreate(
                        fecha_operacion=FECHA_TEST,
                        transportadora_id=t.transportadora_id,
                        materia_prima_id=m.materia_prima_id,
                        puerto_id=p.puerto_id,
                        cantidad_vehiculos=8,
                    ),
                )
                db.commit()
                ctx["det_id"] = det.programacion_detalle_id

            runner.probar("2. Crear detalle con 8 cupos (capacidad max)", prueba_2_detalle_max_capacidad)

            def prueba_3_verificar_cupos() -> None:
                cupos = det_svc.listar_cupos_de_detalle(db, ctx["det_id"])
                assert len(cupos) == 8, f"esperados 8, hay {len(cupos)}"

                # Verificar que NO existe franja de almuerzo.
                for c in cupos:
                    assert not (
                        c.hora_inicio == ALMUERZO_INICIO
                        and c.hora_fin == ALMUERZO_FIN
                    ), "hay un cupo en la franja de almuerzo"

                # Verificar que las 8 franjas coinciden con las esperadas.
                franjas_esperadas = set(generar_franjas_dia(incluir_almuerzo=False))
                franjas_obtenidas = {(c.hora_inicio, c.hora_fin) for c in cupos}
                assert franjas_obtenidas == franjas_esperadas, (
                    f"franjas no coinciden\n"
                    f"  esperadas: {sorted(franjas_esperadas)}\n"
                    f"  obtenidas: {sorted(franjas_obtenidas)}"
                )

            runner.probar("3. Verificar 8 cupos y ausencia de almuerzo", prueba_3_verificar_cupos)

            def prueba_4_capacidad_excedida() -> None:
                try:
                    det_svc.crear_detalle(
                        db, ctx["prog_id"],
                        ProgramacionDetalleCreate(
                            fecha_operacion=FECHA_TEST,
                            transportadora_id=t.transportadora_id,
                            materia_prima_id=m.materia_prima_id,
                            puerto_id=p.puerto_id,
                            cantidad_vehiculos=1,
                        ),
                    )
                except det_svc.CapacidadInsuficienteError:
                    db.rollback()
                    return
                raise AssertionError("no rechazo capacidad excedida")

            runner.probar("4. Rechazar capacidad excedida (409 esperado)", prueba_4_capacidad_excedida)

            def prueba_5_publicar() -> None:
                prog = prog_svc.publicar_programacion(db, ctx["prog_id"])
                db.commit()
                assert prog.estado == "PUBLICADA", f"estado={prog.estado}"

            runner.probar("5. Publicar programacion", prueba_5_publicar)

            def prueba_6_inmutable_publicada() -> None:
                # Intentar crear detalle.
                try:
                    det_svc.crear_detalle(
                        db, ctx["prog_id"],
                        ProgramacionDetalleCreate(
                            fecha_operacion=FECHA_TEST,
                            transportadora_id=t.transportadora_id,
                            materia_prima_id=m.materia_prima_id,
                            puerto_id=p.puerto_id,
                            cantidad_vehiculos=1,
                        ),
                    )
                    db.rollback()
                    raise AssertionError("permitio crear detalle en PUBLICADA")
                except det_svc.ProgramacionNoModificableError:
                    db.rollback()

                # Intentar actualizar detalle.
                try:
                    det_svc.actualizar_detalle(
                        db, ctx["det_id"],
                        ProgramacionDetalleUpdate(cantidad_vehiculos=1),
                    )
                    db.rollback()
                    raise AssertionError("permitio actualizar detalle en PUBLICADA")
                except det_svc.ProgramacionNoModificableError:
                    db.rollback()

                # Intentar eliminar detalle.
                try:
                    det_svc.eliminar_detalle(db, ctx["det_id"])
                    db.rollback()
                    raise AssertionError("permitio eliminar detalle en PUBLICADA")
                except det_svc.ProgramacionNoModificableError:
                    db.rollback()

            runner.probar("6. Rechazar modificaciones en PUBLICADA", prueba_6_inmutable_publicada)

            def prueba_7_cancelar() -> None:
                prog = prog_svc.cancelar_programacion(db, ctx["prog_id"])
                db.commit()
                assert prog.estado == "CANCELADA", f"estado={prog.estado}"

                # Cerrar desde CANCELADA debe fallar.
                try:
                    prog_svc.cerrar_programacion(db, ctx["prog_id"])
                    db.rollback()
                    raise AssertionError("permitio cerrar desde CANCELADA")
                except prog_svc.TransicionEstadoInvalidaError:
                    db.rollback()

            runner.probar("7. Cancelar y rechazar cierre desde CANCELADA", prueba_7_cancelar)

            # ============================================================
            # SECCION 2: Casos limite
            # ============================================================

            def prueba_8_fecha_fuera_rango() -> None:
                # Crear nueva programacion para no chocar con la cancelada.
                prog2 = prog_svc.crear_programacion(
                    db,
                    ProgramacionCreate(
                        fecha_inicio=FECHA_TEST,
                        fecha_fin=FECHA_TEST,
                    ),
                    usuario_creador=admin,
                )
                db.commit()

                try:
                    det_svc.crear_detalle(
                        db, prog2.programacion_id,
                        ProgramacionDetalleCreate(
                            fecha_operacion=date(2099, 2, 1),  # fuera de rango
                            transportadora_id=t.transportadora_id,
                            materia_prima_id=m.materia_prima_id,
                            puerto_id=p.puerto_id,
                            cantidad_vehiculos=1,
                        ),
                    )
                    db.rollback()
                    raise AssertionError("permitio fecha fuera de rango")
                except det_svc.FechaFueraDeRangoError:
                    db.rollback()

                # Limpiar prog2.
                prog2_obj = db.get(Programacion, prog2.programacion_id)
                if prog2_obj is not None:
                    db.delete(prog2_obj)
                    db.commit()

            runner.probar("8. Rechazar fecha fuera del rango", prueba_8_fecha_fuera_rango)

            def prueba_9_maestro_inactivo() -> None:
                # Crear transportadora inactiva temporal.
                t_inactiva = Transportadora(
                    nit=f"{PREFIJO_TEST}INACTIVA",
                    razon_social="Inactiva",
                    activo=False,
                )
                db.add(t_inactiva)
                db.flush()

                prog3 = prog_svc.crear_programacion(
                    db,
                    ProgramacionCreate(
                        fecha_inicio=FECHA_TEST,
                        fecha_fin=FECHA_TEST,
                    ),
                    usuario_creador=admin,
                )
                db.commit()

                try:
                    det_svc.crear_detalle(
                        db, prog3.programacion_id,
                        ProgramacionDetalleCreate(
                            fecha_operacion=FECHA_TEST,
                            transportadora_id=t_inactiva.transportadora_id,
                            materia_prima_id=m.materia_prima_id,
                            puerto_id=p.puerto_id,
                            cantidad_vehiculos=1,
                        ),
                    )
                    db.rollback()
                    raise AssertionError("permitio maestro inactivo")
                except det_svc.MaestroInactivoError:
                    db.rollback()

                # Limpiar.
                db.delete(t_inactiva)
                prog3_obj = db.get(Programacion, prog3.programacion_id)
                if prog3_obj is not None:
                    db.delete(prog3_obj)
                db.commit()

            runner.probar("9. Rechazar maestro inactivo", prueba_9_maestro_inactivo)

            # ============================================================
            # SECCION 3: Bloqueos e idempotencia
            # ============================================================

            def prueba_10_almuerzo_idempotente() -> None:
                # Contar bloqueos ALMUERZO de la fecha.
                bls = db.execute(
                    select(BloqueoHorario).where(
                        BloqueoHorario.fecha == FECHA_TEST,
                        BloqueoHorario.tipo_bloqueo == TipoBloqueo.ALMUERZO.value,
                    )
                ).scalars().all()
                assert len(bls) <= 1, (
                    f"hay {len(bls)} bloqueos de ALMUERZO (max 1)"
                )

            runner.probar("10. Bloqueo de almuerzo es unico", prueba_10_almuerzo_idempotente)

            def prueba_11_bloqueo_parcial() -> None:
                # Crear programacion nueva para fecha distinta.
                fecha_b = date(2099, 1, 16)
                prog_b = prog_svc.crear_programacion(
                    db,
                    ProgramacionCreate(
                        fecha_inicio=fecha_b,
                        fecha_fin=fecha_b,
                    ),
                    usuario_creador=admin,
                )
                db.commit()

                # Crear un detalle que use las primeras 4 franjas.
                det_b = det_svc.crear_detalle(
                    db, prog_b.programacion_id,
                    ProgramacionDetalleCreate(
                        fecha_operacion=fecha_b,
                        transportadora_id=t.transportadora_id,
                        materia_prima_id=m.materia_prima_id,
                        puerto_id=p.puerto_id,
                        cantidad_vehiculos=4,
                    ),
                )
                db.commit()

                # Crear un bloqueo manual que cubra parcialmente las
                # franjas 04 y 05 (08:30-09:30).
                bl = bl_svc.crear_bloqueo(
                    db,
                    BloqueoCreate(
                        fecha=fecha_b,
                        hora_inicio=time(8, 30),
                        hora_fin=time(9, 30),
                        tipo_bloqueo=TipoBloqueo.LIMPIEZA,
                        descripcion="Bloqueo parcial de prueba",
                    ),
                )
                db.commit()
                assert bl.bloqueo_id > 0

                # Crear otro detalle. Debe excluir las franjas que se
                # solapan con el bloqueo (08:00-09:00 y 09:00-10:00)
                # ademas de las ya usadas por det_b.
                det_c = det_svc.crear_detalle(
                    db, prog_b.programacion_id,
                    ProgramacionDetalleCreate(
                        fecha_operacion=fecha_b,
                        transportadora_id=t.transportadora_id,
                        materia_prima_id=m.materia_prima_id,
                        puerto_id=p.puerto_id,
                        cantidad_vehiculos=3,
                    ),
                )
                db.commit()

                cupos_c = det_svc.listar_cupos_de_detalle(db, det_c.programacion_detalle_id)
                assert len(cupos_c) == 3

                # Las franjas usadas por det_b (07:00-08:00, 08:00-09:00, 09:00-10:00, 10:00-11:00)
                # estan ocupadas. El bloqueo cubre 08:00-09:00 y 09:00-10:00 (ya ocupadas por det_b).
                # Las franjas disponibles para det_c son: 11:00-12:00, 13:00-14:00, 14:00-15:00, 15:00-16:00.
                franjas_c = {(c.hora_inicio, c.hora_fin) for c in cupos_c}
                assert time(11, 0) in {c[0] for c in franjas_c}, (
                    f"det_c no uso 11:00, uso {sorted(franjas_c)}"
                )

                # Limpieza de la fecha_b.
                prog_b_obj = db.get(Programacion, prog_b.programacion_id)
                if prog_b_obj is not None:
                    db.delete(prog_b_obj)
                bls_b = db.execute(
                    select(BloqueoHorario).where(BloqueoHorario.fecha == fecha_b)
                ).scalars().all()
                for b in bls_b:
                    db.delete(b)
                db.commit()

            runner.probar("11. Bloqueo parcial excluye franjas solapadas", prueba_11_bloqueo_parcial)

            # ============================================================
            # SECCION 4: No duplicacion
            # ============================================================

            def prueba_12_no_duplicacion() -> None:
                fecha_c = date(2099, 1, 17)
                prog_c = prog_svc.crear_programacion(
                    db,
                    ProgramacionCreate(
                        fecha_inicio=fecha_c,
                        fecha_fin=fecha_c,
                    ),
                    usuario_creador=admin,
                )
                db.commit()

                # Detalle A con 3 cupos.
                det_a = det_svc.crear_detalle(
                    db, prog_c.programacion_id,
                    ProgramacionDetalleCreate(
                        fecha_operacion=fecha_c,
                        transportadora_id=t.transportadora_id,
                        materia_prima_id=m.materia_prima_id,
                        puerto_id=p.puerto_id,
                        cantidad_vehiculos=3,
                    ),
                )
                db.commit()

                # Detalle B con 3 cupos (mismo dia, distinta operacion).
                det_b = det_svc.crear_detalle(
                    db, prog_c.programacion_id,
                    ProgramacionDetalleCreate(
                        fecha_operacion=fecha_c,
                        transportadora_id=t.transportadora_id,
                        materia_prima_id=m.materia_prima_id,
                        puerto_id=p.puerto_id,
                        cantidad_vehiculos=3,
                    ),
                )
                db.commit()

                cupos_a = det_svc.listar_cupos_de_detalle(db, det_a.programacion_detalle_id)
                cupos_b = det_svc.listar_cupos_de_detalle(db, det_b.programacion_detalle_id)

                franjas_a = {(c.hora_inicio, c.hora_fin) for c in cupos_a}
                franjas_b = {(c.hora_inicio, c.hora_fin) for c in cupos_b}

                interseccion = franjas_a & franjas_b
                assert not interseccion, (
                    f"hay franjas duplicadas: {sorted(interseccion)}"
                )

                # Limpieza.
                prog_c_obj = db.get(Programacion, prog_c.programacion_id)
                if prog_c_obj is not None:
                    db.delete(prog_c_obj)
                bls_c = db.execute(
                    select(BloqueoHorario).where(BloqueoHorario.fecha == fecha_c)
                ).scalars().all()
                for b in bls_c:
                    db.delete(b)
                db.commit()

            runner.probar("12. No duplicacion de cupos entre detalles", prueba_12_no_duplicacion)

        finally:
            # Limpieza garantizada.
            try:
                limpiar_datos_test(db)
                db.commit()
            except Exception as exc:
                db.rollback()
                print(f"ERROR en limpieza: {exc}", file=sys.stderr)

    runner.imprimir()

    # Exit code.
    fallos = sum(1 for _, ok, _ in runner.resultados if not ok)
    return 0 if fallos == 0 else 1


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(run_pruebas())