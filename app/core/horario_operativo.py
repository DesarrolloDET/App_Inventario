"""
Reglas del horario operativo de MEJIA TURNOS.

Fuente unica de verdad para:
- Horario de operacion diaria.
- Franjas de 60 minutos.
- Bloqueo obligatorio de almuerzo.
- Generacion de franjas disponibles.

Reglas aplicadas:
- Seccion 5  (flujo operativo): franjas horarias.
- Seccion 7  (cupos): horarios y capacidad.
- Seccion 8  (bloqueos): almuerzo y otros.

Parametros del MVP:
- Hora de inicio de operacion: 07:00.
- Hora de fin de operacion:   16:00.
- Duracion de cada franja:    60 minutos.
- Franja de almuerzo:         12:00-13:00 (SIEMPRE bloqueada).

Franjas generadas (8):
    07:00-08:00
    08:00-09:00
    09:00-10:00
    10:00-11:00
    11:00-12:00
    13:00-14:00
    14:00-15:00
    15:00-16:00

Nota sobre el almuerzo:
- La franja 12:00-13:00 NO se genera.
- La regla es DURA: no depende de que exista un BloqueoHorario.
- Ademas, se crea un BloqueoHorario con tipo='ALMUERZO' para que sea
  visible en el CRUD de bloqueos. Ese bloqueo esta protegido: no se puede
  desactivar ni modificar.
"""

from __future__ import annotations

from datetime import time


# ---------------------------------------------------------------------------
# Constantes del MVP
# ---------------------------------------------------------------------------
# Estos valores son los del MVP. Si en el futuro se necesita parametrizar
# por dia, transportadora o tipo de operacion, se migraran a configuracion
# externa (BD o .env) sin cambiar la estructura de este modulo.
# ---------------------------------------------------------------------------

HORA_INICIO: time = time(7, 0)
HORA_FIN: time = time(16, 0)

DURACION_FRANJA_MIN: int = 60

ALMUERZO_INICIO: time = time(12, 0)
ALMUERZO_FIN: time = time(13, 0)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def es_hora_de_almuerzo(hora: time) -> bool:
    """
    Devuelve True si la hora cae dentro de la franja de almuerzo [12:00, 13:00).
    """
    return ALMUERZO_INICIO <= hora < ALMUERZO_FIN


def franja_es_de_almuerzo(hora_inicio: time, hora_fin: time) -> bool:
    """
    Devuelve True si la franja (hora_inicio, hora_fin) coincide exactamente
    con la franja de almuerzo.

    Se compara con igualdad exacta: la unica franja de almuerzo valida en
    el MVP es 12:00-13:00. Cualquier otro rango que la contenga parcialmente
    no se considera "la franja de almuerzo" y sera tratada por la logica
    de bloqueos ordinarios.
    """
    return hora_inicio == ALMUERZO_INICIO and hora_fin == ALMUERZO_FIN


def generar_franjas_dia(
    incluir_almuerzo: bool = False,
) -> list[tuple[time, time]]:
    """
    Genera las franjas horarias del dia de operacion.

    Args:
        incluir_almuerzo: si True, incluye la franja 12:00-13:00 en el
                          resultado. Por defecto False (el almuerzo esta
                          bloqueado y no se ofrece).

    Returns:
        Lista de tuplas (hora_inicio, hora_fin).

    Ejemplo (incluir_almuerzo=False):
        [
            (07:00, 08:00),
            (08:00, 09:00),
            (09:00, 10:00),
            (10:00, 11:00),
            (11:00, 12:00),
            (13:00, 14:00),
            (14:00, 15:00),
            (15:00, 16:00),
        ]
    """
    franjas: list[tuple[time, time]] = []

    actual = HORA_INICIO
    while actual < HORA_FIN:
        # Calcular hora_fin de esta franja.
        minutos_actual = actual.hour * 60 + actual.minute
        minutos_fin = minutos_actual + DURACION_FRANJA_MIN

        hora_fin_h = minutos_fin // 60
        hora_fin_m = minutos_fin % 60
        hora_fin = time(hora_fin_h, hora_fin_m)

        # Si la franja es la de almuerzo, saltarla (salvo que se pida incluir).
        if franja_es_de_almuerzo(actual, hora_fin) and not incluir_almuerzo:
            actual = hora_fin
            continue

        franjas.append((actual, hora_fin))
        actual = hora_fin

    return franjas


def capacidad_maxima_dia() -> int:
    """
    Devuelve la capacidad teorica maxima del dia (sin contar bloqueos).

    En el MVP: 8 franjas disponibles (9 franjas de 60min entre 07:00 y 16:00,
    menos la franja de almuerzo = 8).
    """
    return len(generar_franjas_dia(incluir_almuerzo=False))