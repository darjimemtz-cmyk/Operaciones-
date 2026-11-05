"""
Flota Tools - FNG San Luis Potosí
Wrappers for fleet status of 31 target units, product deficits, operational coverage.
Business rule: 31 unidades objetivo (ARGON:8, NITROGENO:2, OXIGENO:12, CO2:9).
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import asdict

from services.tools import tool
from services.repositories.flota_repo import (
    get_unidades_activas,
    get_unidad_by_eco,
    get_deficit_por_producto,
    get_resumen_flota,
    get_unidades_sin_operador,
    get_unidades_en_mantenimiento,
    get_cobertura_operativa,
    validar_objetivo_31_unidades,
    TOTAL_OBJETIVO,
    OBJETIVO_POR_PRODUCTO,
    Unidad,
    DeficitProducto,
    ResumenFlota,
)


@tool(
    name="flota_unidades_activas",
    description="Get all active fleet units (ACTIVA + MANTENIMIENTO) derived from operators with ECO assigned. Excludes instructors/movers.",
    category="flota",
    timeout=1.0,
    cache_ttl=60,
)
def flota_unidades_activas() -> List[Dict[str, Any]]:
    """
    Get active fleet units.
    
    Returns:
        List of unit dicts: eco, producto, estatus, operador_asignado, operador_id,
        kilometraje, ultima_revision
    """
    unidades = get_unidades_activas()
    return [asdict(u) for u in unidades]


@tool(
    name="flota_unidad_by_eco",
    description="Get a specific unit by ECO code.",
    category="flota",
    timeout=0.5,
    cache_ttl=60,
)
def flota_unidad_by_eco(eco: str) -> Optional[Dict[str, Any]]:
    unidad = get_unidad_by_eco(eco)
    return asdict(unidad) if unidad else None


@tool(
    name="flota_deficit_por_producto",
    description="Get unit deficit per product vs targets (ARGON:8, NITROGENO:2, OXIGENO:12, CO2:9). Returns objetivo, activas, deficit, porcentaje.",
    category="flota",
    timeout=1.0,
    cache_ttl=30,
)
def flota_deficit_por_producto() -> List[Dict[str, Any]]:
    """
    Get deficit analysis by product.
    
    Returns:
        List of dicts with producto, objetivo, activas, deficit, porcentaje
    """
    deficits = get_deficit_por_producto()
    return [asdict(d) for d in deficits]


@tool(
    name="flota_resumen",
    description="Get complete fleet summary: total, active, maintenance, baja, unassigned, target (31), total deficit, and per-product breakdown.",
    category="flota",
    timeout=1.0,
    cache_ttl=30,
)
def flota_resumen() -> Dict[str, Any]:
    """
    Get executive fleet summary.
    
    Returns:
        Dict with total_unidades, activas, mantenimiento, baja, sin_asignar,
        objetivo_total, deficit_total, por_producto (list of DeficitProducto)
    """
    resumen = get_resumen_flota()
    return asdict(resumen)


@tool(
    name="flota_sin_operador",
    description="Get units without assigned operator (ECO exists but no active operator). Status: SIN_ASIGNAR.",
    category="flota",
    timeout=1.0,
    cache_ttl=30,
)
def flota_sin_operador() -> List[Dict[str, Any]]:
    unidades = get_unidades_sin_operador()
    return [asdict(u) for u in unidades]


@tool(
    name="flota_en_mantenimiento",
    description="Get units in maintenance (operator resting: DE, D1, D2, V1, V2). Status: MANTENIMIENTO.",
    category="flota",
    timeout=1.0,
    cache_ttl=30,
)
def flota_en_mantenimiento() -> List[Dict[str, Any]]:
    unidades = get_unidades_en_mantenimiento()
    return [asdict(u) for u in unidades]


@tool(
    name="flota_cobertura_operativa",
    description="Get operational coverage: units with/without operator per product.",
    category="flota",
    timeout=1.0,
    cache_ttl=30,
)
def flota_cobertura_operativa() -> Dict[str, Any]:
    """
    Get coverage breakdown by product.
    
    Returns:
        Dict mapping producto -> {con_operador, sin_operador, total}
    """
    return get_cobertura_operativa()


@tool(
    name="flota_validar_objetivo_31",
    description="Validate if fleet meets 31-unit target. Returns (ok, message).",
    category="flota",
    timeout=0.5,
    cache_ttl=30,
)
def flota_validar_objetivo_31() -> Dict[str, Any]:
    """
    Validate 31-unit fleet target.
    
    Returns:
        Dict with ok (bool), message (str), activas (int), objetivo (int), faltan (int)
    """
    ok, msg = validar_objetivo_31_unidades()
    resumen = get_resumen_flota()
    return {
        "ok": ok,
        "message": msg,
        "activas": resumen.activas,
        "objetivo": TOTAL_OBJETIVO,
        "faltan": max(0, TOTAL_OBJETIVO - resumen.activas),
    }


@tool(
    name="flota_objetivos",
    description="Get target unit counts per product (immutable business config).",
    category="flota",
    timeout=0.5,
    cache_ttl=3600,
)
def flota_objetivos() -> Dict[str, Any]:
    return {
        "total_objetivo": TOTAL_OBJETIVO,
        "por_producto": OBJETIVO_POR_PRODUCTO,
        "regla": "31 unidades objetivo derivadas de operadores activos con ECO asignado (excluye instructores/movedores)",
    }