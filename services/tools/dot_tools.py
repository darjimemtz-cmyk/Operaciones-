"""
DOT Tools - FNG San Luis Potosí
Wrappers for DOT/NOM-087: 7-day rolling window (max 70h), fatigue ranking (>=52h), compliance.
Business rules: NEVER include instructors/movers in DOT calculations.
"""

from typing import Any, Dict, List, Optional
from dataclasses import asdict

from services.tools import tool
from services.repositories.dot_repo import (
    get_horas_dot_7dias,
    get_todas_horas_dot_7dias,
    get_cumplimiento_dot,
    get_ranking_fatiga,
    get_alertas_dot_criticas,
    get_alertas_dot_amarillas,
    get_operadores_sin_datos_dot,
    get_disponibilidad_por_producto,
    MAX_HORAS_7_DIAS,
    UMBRAL_FATIGA,
    VENTANA_DIAS,
    HorasDOT,
    CumplimientoDOT,
    FatigaRanking,
)


@tool(
    name="dot_horas_operador",
    description="Get DOT hours for a specific operator in the last 7 days. Returns hours worked, free hours, status, and daily detail. Excludes instructors/movers.",
    category="dot",
    timeout=1.5,
    cache_ttl=30,
)
def dot_horas_operador(operador_id: int) -> Optional[Dict[str, Any]]:
    result = get_horas_dot_7dias(operador_id)
    return asdict(result) if result else None


@tool(
    name="dot_todas_horas",
    description="Get DOT hours for all active operators (excl. instructors/movers) in the 7-day window. Cached for fast retrieval.",
    category="dot",
    timeout=1.5,
    cache_ttl=30,
)
def dot_todas_horas() -> List[Dict[str, Any]]:
    results = get_todas_horas_dot_7dias()
    return [asdict(r) for r in results]


@tool(
    name="dot_cumplimiento",
    description="Get overall DOT compliance summary: total operators, OK/ALERT/CRITICAL/NO_DATA counts, and compliance percentage.",
    category="dot",
    timeout=1.0,
    cache_ttl=30,
)
def dot_cumplimiento() -> Dict[str, Any]:
    result = get_cumplimiento_dot()
    return asdict(result)


@tool(
    name="dot_ranking_fatiga",
    description="Get fatigue ranking (highest hours first) for operators >= 52h (AMARILLO) or >= 70h (ROJO). Filter by product optionally.",
    category="dot",
    timeout=1.5,
    cache_ttl=30,
)
def dot_ranking_fatiga(producto: Optional[str] = None, top: int = 20) -> List[Dict[str, Any]]:
    results = get_ranking_fatiga(producto=producto, top=top)
    return [asdict(r) for r in results]


@tool(
    name="dot_alertas_criticas",
    description="Get operators in CRITICAL status (>= 70 hours in 7 days). Immediate action required.",
    category="dot",
    timeout=1.0,
    cache_ttl=30,
)
def dot_alertas_criticas() -> List[Dict[str, Any]]:
    results = get_alertas_dot_criticas()
    return [asdict(r) for r in results]


@tool(
    name="dot_alertas_amarillas",
    description="Get operators in ALERT status (52-69 hours in 7 days). Monitor closely.",
    category="dot",
    timeout=1.0,
    cache_ttl=30,
)
def dot_alertas_amarillas() -> List[Dict[str, Any]]:
    results = get_alertas_dot_amarillas()
    return [asdict(r) for r in results]


@tool(
    name="dot_sin_datos",
    description="Get operators with no DOT data in the 7-day window (SIN_DATOS). Need data entry.",
    category="dot",
    timeout=1.0,
    cache_ttl=30,
)
def dot_sin_datos() -> List[Dict[str, Any]]:
    results = get_operadores_sin_datos_dot()
    return [asdict(r) for r in results]


@tool(
    name="dot_disponibilidad",
    description="Get available hours grouped by product for relief planning. Only operators with >0 free hours and OK/ALERT status.",
    category="dot",
    timeout=1.0,
    cache_ttl=30,
)
def dot_disponibilidad() -> Dict[str, List[Dict[str, Any]]]:
    raw = get_disponibilidad_por_producto()
    result = {}
    for prod, lst in raw.items():
        result[prod] = [{"nombre": nombre, "horas_libres": hrs} for nombre, hrs in lst]
    return result


@tool(
    name="dot_horas_libres",
    description="Get free DOT hours for a specific operator (70h - hours_worked_in_7_days). Returns 70 if no data.",
    category="dot",
    timeout=1.0,
    cache_ttl=30,
)
def dot_horas_libres(operador_id: int) -> float:
    horas = get_horas_dot_7dias(operador_id)
    return horas.horas_libres if horas else MAX_HORAS_7_DIAS


@tool(
    name="dot_constantes",
    description="Get DOT/NOM-087 business constants: 7-day window, 70h max, 52h fatigue threshold.",
    category="dot",
    timeout=0.5,
    cache_ttl=3600,
)
def dot_constantes() -> Dict[str, Any]:
    return {
        "ventana_dias": VENTANA_DIAS,
        "max_horas_7_dias": MAX_HORAS_7_DIAS,
        "umbral_fatiga": UMBRAL_FATIGA,
        "niveles": {
            "VERDE": f"< {UMBRAL_FATIGA}h",
            "AMARILLO": f">= {UMBRAL_FATIGA}h y < {MAX_HORAS_7_DIAS}h",
            "ROJO": f">= {MAX_HORAS_7_DIAS}h",
        },
        "reglas_negocio": [
            "Ventana rodante estricta de 7 días (no 8)",
            "Máximo 70 horas en 7 días (NOM-087)",
            "Alerta amarilla a partir de 52 horas",
            "NUNCA incluir instructores ni movedores en cálculos DOT",
        ],
    }