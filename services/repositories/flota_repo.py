"""
Flota Repository - FNG San Luis Potosí
Unit status, product deficits, active fleet management.
Business rule: 31 unidades objetivo.
Derives fleet from operadores.eco + logistica_diaria (no separate unidades table).
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from services.repositories import (
    db_cursor,
    cached_query,
    DEFAULT_TTL,
    LONG_TTL,
)

# Unidades objetivo por producto (meta operativa)
OBJETIVO_POR_PRODUCTO = {
    "ARGON": 8,
    "NITROGENO": 2,
    "OXIGENO": 12,
    "CO2": 9,
}
TOTAL_OBJETIVO = 31

@dataclass
class Unidad:
    """Unidad de la flota (derivada de operadores.eco)."""
    eco: str
    producto: str
    estatus: str  # "ACTIVA", "MANTENIMIENTO", "BAJA", "SIN_ASIGNAR"
    operador_asignado: Optional[str]
    operador_id: Optional[int]
    kilometraje: Optional[int]
    ultima_revision: Optional[str]

@dataclass
class DeficitProducto:
    """Déficit de unidades por producto."""
    producto: str
    objetivo: int
    activas: int
    deficit: int
    porcentaje: float

@dataclass
class ResumenFlota:
    """Resumen ejecutivo de la flota."""
    total_unidades: int
    activas: int
    mantenimiento: int
    baja: int
    sin_asignar: int
    objetivo_total: int
    deficit_total: int
    por_producto: List[DeficitProducto]


def _get_unidades_desde_operadores() -> List[Unidad]:
    """Internal: derive units from operadores with eco assigned."""
    with db_cursor() as c:
        c.execute("""
            SELECT o.eco, o.producto, o.nombre, o.id,
                   ld.estatus as logistica_estatus
            FROM operadores o
            LEFT JOIN logistica_diaria ld ON ld.operador_id = o.id
                AND ld.fecha = date('now', 'localtime')
            WHERE o.estatus_empleado = 'Activo'
              AND o.eco IS NOT NULL
              AND o.eco != ''
              AND o.eco != 'N/A'
              AND UPPER(COALESCE(o.esquema, '')) NOT LIKE '%INSTRUCTOR%'
              AND UPPER(COALESCE(o.esquema, '')) NOT LIKE '%MOVEDOR%'
            ORDER BY o.producto, o.eco
        """)
        rows = c.fetchall()

    unidades: List[Unidad] = []
    for row in rows:
        eco = row["eco"]
        # Determine unit status from logistics status
        log_estatus = row["logistica_estatus"] or ""
        if log_estatus in ("DE", "D1", "D2", "V1", "V2") or log_estatus.startswith("D") or log_estatus.startswith("V"):
            estatus = "MANTENIMIENTO"  # operator resting = unit not available
        elif log_estatus:
            estatus = "ACTIVA"
        else:
            estatus = "SIN_ASIGNAR"

        unidades.append(Unidad(
            eco=eco,
            producto=row["producto"],
            estatus=estatus,
            operador_asignado=row["nombre"],
            operador_id=row["id"],
            kilometraje=None,  # not tracked in current schema
            ultima_revision=None,
        ))
    return unidades


def get_unidades_activas() -> List[Unidad]:
    """Get all units derived from active operators with eco. Cached LONG_TTL."""
    def _query() -> List[Unidad]:
        return [u for u in _get_unidades_desde_operadores() if u.estatus in ("ACTIVA", "MANTENIMIENTO")]
    return cached_query("unidades_activas", _query, LONG_TTL)


def get_unidad_by_eco(eco: str) -> Optional[Unidad]:
    """Get single unit by ECO number."""
    unidades = _get_unidades_desde_operadores()
    for u in unidades:
        if u.eco == eco:
            return u
    return None


def get_deficit_por_producto() -> List[DeficitProducto]:
    """Calculate deficit per product vs operational target. Cached DEFAULT_TTL."""
    def _query() -> List[DeficitProducto]:
        unidades = _get_unidades_desde_operadores()
        activas_por_prod: Dict[str, int] = {}
        for u in unidades:
            if u.estatus == "ACTIVA":
                activas_por_prod[u.producto] = activas_por_prod.get(u.producto, 0) + 1

        results = []
        for prod, objetivo in OBJETIVO_POR_PRODUCTO.items():
            activas = activas_por_prod.get(prod, 0)
            deficit = max(0, objetivo - activas)
            pct = round((activas / objetivo) * 100, 1) if objetivo > 0 else 0.0
            results.append(DeficitProducto(
                producto=prod,
                objetivo=objetivo,
                activas=activas,
                deficit=deficit,
                porcentaje=pct,
            ))
        return results

    return cached_query("deficit_por_producto", _query, DEFAULT_TTL)


def get_resumen_flota() -> ResumenFlota:
    """Get complete fleet summary. Cached DEFAULT_TTL."""
    def _query() -> ResumenFlota:
        unidades = _get_unidades_desde_operadores()
        counts = {"ACTIVA": 0, "MANTENIMIENTO": 0, "BAJA": 0, "SIN_ASIGNAR": 0}
        for u in unidades:
            if u.estatus in counts:
                counts[u.estatus] += 1

        total = sum(counts.values())
        por_prod = get_deficit_por_producto()
        deficit_total = sum(d.deficit for d in por_prod)

        return ResumenFlota(
            total_unidades=total,
            activas=counts["ACTIVA"],
            mantenimiento=counts["MANTENIMIENTO"],
            baja=counts["BAJA"],
            sin_asignar=counts["SIN_ASIGNAR"],
            objetivo_total=TOTAL_OBJETIVO,
            deficit_total=deficit_total,
            por_producto=por_prod,
        )

    return cached_query("resumen_flota", _query, DEFAULT_TTL)


def get_unidades_sin_operador() -> List[Unidad]:
    """Get units without operator (eco assigned but no active operator). Cached DEFAULT_TTL."""
    def _query() -> List[Unidad]:
        unidades = _get_unidades_desde_operadores()
        return [u for u in unidades if u.estatus == "SIN_ASIGNAR"]
    return cached_query("unidades_sin_operador", _query, DEFAULT_TTL)


def get_unidades_en_mantenimiento() -> List[Unidad]:
    """Get units in maintenance (operator resting). Cached DEFAULT_TTL."""
    def _query() -> List[Unidad]:
        unidades = _get_unidades_desde_operadores()
        return [u for u in unidades if u.estatus == "MANTENIMIENTO"]
    return cached_query("unidades_en_mantenimiento", _query, DEFAULT_TTL)


def get_cobertura_operativa() -> Dict[str, Any]:
    """Get operational coverage: units with/without operator per product."""
    def _query() -> Dict[str, Any]:
        unidades = _get_unidades_desde_operadores()
        cobertura: Dict[str, Dict[str, int]] = {}
        for u in unidades:
            if u.producto not in cobertura:
                cobertura[u.producto] = {"con_operador": 0, "sin_operador": 0, "total": 0}
            cobertura[u.producto]["total"] += 1
            if u.estatus in ("ACTIVA", "MANTENIMIENTO"):
                cobertura[u.producto]["con_operador"] += 1
            else:
                cobertura[u.producto]["sin_operador"] += 1
        return cobertura

    return cached_query("cobertura_operativa", _query, DEFAULT_TTL)


def validar_objetivo_31_unidades() -> Tuple[bool, str]:
    """Validate if fleet meets 31-unit target. Returns (ok, message)."""
    resumen = get_resumen_flota()
    if resumen.activas >= TOTAL_OBJETIVO:
        return True, f"Flota cumple objetivo: {resumen.activas}/{TOTAL_OBJETIVO} unidades activas"
    else:
        return False, f"DÉFICIT: {resumen.activas}/{TOTAL_OBJETIVO} unidades activas (faltan {TOTAL_OBJETIVO - resumen.activas})"
