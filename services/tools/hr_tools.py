"""
HR Tools - FNG San Luis Potosí
Wrappers for active operators, breaks (day/morning), license/medical expirations.
Business rules: Exclude instructors/movers from operational counts.
"""

from typing import Any, Dict, List, Optional
from dataclasses import asdict
from datetime import date, timedelta

from services.tools import tool
from services.repositories.operadores_repo import (
    get_operadores_activos,
    get_operador_by_id,
    get_operadores_por_producto,
    contar_activos_por_producto,
    get_vigencias_por_vencer,
    get_descansos_en_fecha,
    buscar_operador_por_nombre_parcial,
    PRODUCTOS_VALIDOS,
    Operador,
    VigenciaProxima,
    Descanso,
)


@tool(
    name="hr_operadores_activos",
    description="Get all active operators (excl. instructors/movers). Optionally filter by product.",
    category="hr",
    timeout=1.0,
    cache_ttl=60,
)
def hr_operadores_activos(producto: Optional[str] = None) -> List[Dict[str, Any]]:
    ops = get_operadores_activos(producto=producto)
    return [asdict(op) for op in ops]


@tool(
    name="hr_operador_by_id",
    description="Get a single active operator by ID. Returns None if not found or is instructor/mover.",
    category="hr",
    timeout=0.5,
    cache_ttl=60,
)
def hr_operador_by_id(operador_id: int) -> Optional[Dict[str, Any]]:
    op = get_operador_by_id(operador_id)
    return asdict(op) if op else None


@tool(
    name="hr_operadores_por_producto",
    description="Get all active operators grouped by product (ARGON, NITROGENO, OXIGENO, CO2).",
    category="hr",
    timeout=1.0,
    cache_ttl=60,
)
def hr_operadores_por_producto() -> Dict[str, List[Dict[str, Any]]]:
    grouped = get_operadores_por_producto()
    return {prod: [asdict(op) for op in ops] for prod, ops in grouped.items()}


@tool(
    name="hr_contar_activos_por_producto",
    description="Count active operators per product. Excludes instructors/movers.",
    category="hr",
    timeout=0.5,
    cache_ttl=60,
)
def hr_contar_activos_por_producto() -> Dict[str, int]:
    return contar_activos_por_producto()


@tool(
    name="hr_vigencias_proximas",
    description="Get licenses/medicals expiring within N days (default 30). Includes operator name, product, type, expiry date, days remaining.",
    category="hr",
    timeout=1.0,
    cache_ttl=60,
)
def hr_vigencias_proximas(dias: int = 30, producto: Optional[str] = None) -> List[Dict[str, Any]]:
    results = get_vigencias_por_vencer(dias=dias, producto=producto)
    return [asdict(v) for v in results]


@tool(
    name="hr_vigencias_vencidas",
    description="Get already expired licenses/medicals. Requires immediate action.",
    category="hr",
    timeout=1.0,
    cache_ttl=60,
)
def hr_vigencias_vencidas() -> List[Dict[str, Any]]:
    results = get_vigencias_por_vencer(dias=0)
    return [asdict(v) for v in results if v.dias_restantes < 0]


@tool(
    name="hr_descansos_hoy",
    description="Get operators resting today (DE, D1, D2, V1, V2, etc.). Filter by product optionally.",
    category="hr",
    timeout=1.0,
    cache_ttl=30,
)
def hr_descansos_hoy(producto: Optional[str] = None) -> List[Dict[str, Any]]:
    hoy = date.today().strftime("%Y-%m-%d")
    results = get_descansos_en_fecha(hoy, producto=producto)
    return [asdict(d) for d in results]


@tool(
    name="hr_descansos_manana",
    description="Get operators resting tomorrow. For advance planning.",
    category="hr",
    timeout=1.0,
    cache_ttl=30,
)
def hr_descansos_manana(producto: Optional[str] = None) -> List[Dict[str, Any]]:
    manana = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    results = get_descansos_en_fecha(manana, producto=producto)
    return [asdict(d) for d in results]


@tool(
    name="hr_descansos_fecha",
    description="Get operators resting on a specific date (YYYY-MM-DD). For historical or future queries.",
    category="hr",
    timeout=1.0,
    cache_ttl=30,
)
def hr_descansos_fecha(fecha: str, producto: Optional[str] = None) -> List[Dict[str, Any]]:
    results = get_descansos_en_fecha(fecha, producto=producto)
    return [asdict(d) for d in results]


@tool(
    name="hr_buscar_operador",
    description="Search operators by partial name match (case-insensitive). Excludes instructors/movers.",
    category="hr",
    timeout=1.0,
    cache_ttl=60,
)
def hr_buscar_operador(nombre_parcial: str) -> List[Dict[str, Any]]:
    results = buscar_operador_por_nombre_parcial(nombre_parcial)
    return [asdict(op) for op in results]


@tool(
    name="hr_productos_validos",
    description="Get valid product codes in operation.",
    category="hr",
    timeout=0.5,
    cache_ttl=3600,
)
def hr_productos_validos() -> List[str]:
    return list(PRODUCTOS_VALIDOS)