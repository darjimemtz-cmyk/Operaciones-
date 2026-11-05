"""
DOT Repository - FNG San Luis Potosí
7-day rolling window hours, fatigue alerts, available hours calculation.
Business rules: 70h max in 7 days, exclude instructors/movers.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from services.repositories import (
    db_cursor,
    cached_query,
    DEFAULT_TTL,
    LONG_TTL,
)

# Constantes de negocio
MAX_HORAS_7_DIAS = 70.0
UMBRAL_FATIGA = 52.0  # >= 52h = alerta amarilla/roja
VENTANA_DIAS = 7

@dataclass
class HorasDOT:
    """Horas DOT de un operador en ventana de 7 días."""
    operador_id: int
    nombre: str
    producto: str
    horas_7d: float
    horas_libres: float
    dias_trabajados: int
    estatus: str  # "OK", "ALERTA", "CRITICO", "SIN_DATOS"
    detalle_dias: List[Dict[str, Any]]  # [{fecha, horas, estatus}]

@dataclass
class CumplimientoDOT:
    """Resumen de cumplimiento DOT para la flota."""
    total_operadores: int
    cumpliendo: int
    alerta: int
    critico: int
    sin_datos: int
    porcentaje_cumplimiento: float

@dataclass
class FatigaRanking:
    """Operador en ranking de fatiga."""
    operador_id: int
    nombre: str
    producto: str
    horas_7d: float
    horas_libres: float
    nivel: str  # "VERDE", "AMARILLO", "ROJO"


def _es_instructor_o_movedor(esquema: Optional[str], tipo_unidad: Optional[str]) -> bool:
    """Check if operator is instructor or mover (excluded from DOT)."""
    if not esquema and not tipo_unidad:
        return False
    esc = (esquema or "").upper()
    tun = (tipo_unidad or "").upper()
    return ("INSTRUCTOR" in esc or "MOVEDOR" in esc or
            "INSTRUCTOR" in tun or "MOVEDOR" in tun)


def get_horas_dot_7dias(operador_id: int) -> Optional[HorasDOT]:
    """Get DOT hours for a specific operator in the last 7 days."""
    def _query() -> Optional[HorasDOT]:
        with db_cursor() as c:
            # Get operator info
            c.execute("""
                SELECT id, nombre, producto, esquema, tipo_unidad
                FROM operadores WHERE id = ? AND estatus_empleado = 'Activo'
            """, (operador_id,))
            op = c.fetchone()
            if not op:
                return None
            if _es_instructor_o_movedor(op["esquema"], op["tipo_unidad"]):
                return None

            # Get last 7 days from dot_diario (strict 7-day rolling window)
            hoy = date.today()
            fecha_inicio = (hoy - timedelta(days=VENTANA_DIAS - 1)).strftime("%Y-%m-%d")
            fecha_fin = hoy.strftime("%Y-%m-%d")

            # Use MAX per day to avoid duplicate records in dot_diario inflating hours
            c.execute("""
                SELECT fecha, MAX(COALESCE(horas, 0.0)) as horas, MAX(estatus_dia) as estatus_dia
                FROM dot_diario
                WHERE operador_id = ? AND fecha BETWEEN ? AND ?
                GROUP BY fecha
                ORDER BY fecha
            """, (operador_id, fecha_inicio, fecha_fin))
            rows = c.fetchall()

            if not rows:
                return HorasDOT(
                    operador_id=operador_id,
                    nombre=op["nombre"],
                    producto=op["producto"],
                    horas_7d=0.0,
                    horas_libres=MAX_HORAS_7_DIAS,
                    dias_trabajados=0,
                    estatus="SIN_DATOS",
                    detalle_dias=[],
                )

            total_horas = sum(r["horas"] or 0 for r in rows)
            dias_trab = sum(1 for r in rows if (r["horas"] or 0) > 0)
            horas_libres = MAX_HORAS_7_DIAS - total_horas

            if total_horas >= MAX_HORAS_7_DIAS:
                estatus = "CRITICO"
            elif total_horas >= UMBRAL_FATIGA:
                estatus = "ALERTA"
            else:
                estatus = "OK"

            detalle = [
                {"fecha": r["fecha"], "horas": r["horas"] or 0, "estatus": r["estatus_dia"]}
                for r in rows
            ]

            return HorasDOT(
                operador_id=operador_id,
                nombre=op["nombre"],
                producto=op["producto"],
                horas_7d=round(total_horas, 1),
                horas_libres=round(max(0, horas_libres), 1),
                dias_trabajados=dias_trab,
                estatus=estatus,
                detalle_dias=detalle,
            )

    cache_key = f"horas_dot_7d:{operador_id}"
    return cached_query(cache_key, _query, DEFAULT_TTL)


def get_horas_libres_dot(operador_id: int) -> float:
    """Get available DOT hours for an operator (70h - used in last 7 days)."""
    h = get_horas_dot_7dias(operador_id)
    return h.horas_libres if h else MAX_HORAS_7_DIAS


def get_todas_horas_dot_7dias() -> List[HorasDOT]:
    """Get DOT hours for all active operators (excl instructors/movers). Cached DEFAULT_TTL."""
    def _query() -> List[HorasDOT]:
        with db_cursor() as c:
            c.execute("""
                SELECT id, nombre, producto, esquema, tipo_unidad
                FROM operadores
                WHERE estatus_empleado = 'Activo'
            """)
            ops = c.fetchall()

            results = []
            for op in ops:
                if _es_instructor_o_movedor(op["esquema"], op["tipo_unidad"]):
                    continue
                h = get_horas_dot_7dias(op["id"])
                if h:
                    results.append(h)
            return results

    return cached_query("todas_horas_dot_7d", _query, DEFAULT_TTL)


def get_cumplimiento_dot() -> CumplimientoDOT:
    """Get overall DOT compliance summary. Cached DEFAULT_TTL."""
    def _query() -> CumplimientoDOT:
        todas = get_todas_horas_dot_7dias()
        total = len(todas)
        if total == 0:
            return CumplimientoDOT(0, 0, 0, 0, 0, 0.0)
        cumpliendo = sum(1 for h in todas if h.estatus == "OK")
        alerta = sum(1 for h in todas if h.estatus == "ALERTA")
        critico = sum(1 for h in todas if h.estatus == "CRITICO")
        sin_datos = sum(1 for h in todas if h.estatus == "SIN_DATOS")
        pct = round((cumpliendo / total) * 100, 1) if total > 0 else 0.0
        return CumplimientoDOT(total, cumpliendo, alerta, critico, sin_datos, pct)

    return cached_query("cumplimiento_dot", _query, DEFAULT_TTL)


def get_ranking_fatiga(producto: Optional[str] = None, top: int = 20) -> List[FatigaRanking]:
    """Get fatigue ranking (highest hours first). Cached DEFAULT_TTL."""
    def _query() -> List[FatigaRanking]:
        todas = get_todas_horas_dot_7dias()
        if producto:
            todas = [h for h in todas if h.producto == producto]
        todas.sort(key=lambda x: x.horas_7d, reverse=True)
        return [
            FatigaRanking(
                operador_id=h.operador_id,
                nombre=h.nombre,
                producto=h.producto,
                horas_7d=h.horas_7d,
                horas_libres=h.horas_libres,
                nivel="ROJO" if h.horas_7d >= MAX_HORAS_7_DIAS else
                      "AMARILLO" if h.horas_7d >= UMBRAL_FATIGA else "VERDE",
            )
            for h in todas[:top]
        ]

    cache_key = f"ranking_fatiga:{producto or 'all'}:{top}"
    return cached_query(cache_key, _query, DEFAULT_TTL)


def get_alertas_dot_criticas() -> List[HorasDOT]:
    """Get operators in CRITICAL status (>=70h). Cached DEFAULT_TTL."""
    todas = get_todas_horas_dot_7dias()
    return [h for h in todas if h.estatus == "CRITICO"]


def get_alertas_dot_amarillas() -> List[HorasDOT]:
    """Get operators in ALERT status (52-69h). Cached DEFAULT_TTL."""
    todas = get_todas_horas_dot_7dias()
    return [h for h in todas if h.estatus == "ALERTA"]


def get_operadores_sin_datos_dot() -> List[HorasDOT]:
    """Get operators with no DOT data in window. Cached DEFAULT_TTL."""
    todas = get_todas_horas_dot_7dias()
    return [h for h in todas if h.estatus == "SIN_DATOS"]


def get_disponibilidad_por_producto() -> Dict[str, List[Tuple[str, float]]]:
    """Get available hours grouped by product: {producto: [(nombre, hrs_libres), ...]}."""
    def _query() -> Dict[str, List[Tuple[str, float]]]:
        todas = get_todas_horas_dot_7dias()
        grouped: Dict[str, List[Tuple[str, float]]] = {}
        for h in todas:
            if h.estatus in ("OK", "ALERTA") and h.horas_libres > 0:
                grouped.setdefault(h.producto, []).append((h.nombre, h.horas_libres))
        for prod in grouped:
            grouped[prod].sort(key=lambda x: x[1], reverse=True)
        return grouped

    return cached_query("disponibilidad_por_producto", _query, DEFAULT_TTL)
