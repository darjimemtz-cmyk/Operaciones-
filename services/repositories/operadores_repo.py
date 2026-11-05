"""
Operadores Repository - FNG San Luis Potosí
Typed queries for operators, breaks, and document expirations.
Business rules: exclude instructors/movers, active status only.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from services.repositories import (
    db_cursor,
    rows_to_dicts,
    row_to_dict,
    cached_query,
    DEFAULT_TTL,
    LONG_TTL,
)

# Productos válidos en operación
PRODUCTOS_VALIDOS = ("ARGON", "NITROGENO", "OXIGENO", "CO2")

@dataclass
class Operador:
    """Operador activo en operación."""
    id: int
    no_empleado: str
    nombre: str
    linea_negocio: str
    producto: str
    esquema: str
    eco: str
    vigencia_licencia: Optional[str]
    vigencia_medica: Optional[str]
    tipo_jornada: str
    estatus_empleado: str
    tipo_unidad: str
    base: str
    orden_posicion: int

@dataclass
class VigenciaProxima:
    """Documento por vencer."""
    operador_id: int
    nombre: str
    producto: str
    tipo: str  # "Licencia" o "Medico"
    fecha_vencimiento: str
    dias_restantes: int

@dataclass
class Descanso:
    """Operador en descanso en fecha dada."""
    operador_id: int
    nombre: str
    producto: str
    estatus: str  # DE, D1, D2, V1, V2, etc.

def _map_operador(row) -> Operador:
    """Map database row to Operador dataclass."""
    return Operador(
        id=row["id"],
        no_empleado=row["no_empleado"] or "N/A",
        nombre=row["nombre"],
        linea_negocio=row["linea_negocio"] or "",
        producto=row["producto"] or "",
        esquema=row["esquema"] or "",
        eco=row["eco"] or "",
        vigencia_licencia=row["vigencia_licencia"] if row["vigencia_licencia"] != "N/A" else None,
        vigencia_medica=row["vigencia_medica"] if row["vigencia_medica"] != "N/A" else None,
        tipo_jornada=row["tipo_jornada"] or "Variable",
        estatus_empleado=row["estatus_empleado"] or "Activo",
        tipo_unidad=row["tipo_unidad"] or "N/A",
        base=row["base"] or "San Luis Potosí",
        orden_posicion=row["orden_posicion"] or 999,
    )
def get_operadores_activos(
    producto: Optional[str] = None,
    excluir_instructores_movedores: bool = True,
    solo_con_esquema: bool = True,
) -> List[Operador]:
    """
    Get all active operators, optionally filtered by product.
    Excludes instructors and movers by default (business rule).
    Cached for LONG_TTL (60s) as this is a relatively static catalog.
    """
    def _query() -> List[Operador]:
        with db_cursor() as c:
            conditions = ["o.estatus_empleado = 'Activo'"]
            params: List[Any] = []

            if excluir_instructores_movedores:
                conditions.append("UPPER(COALESCE(o.esquema, '')) NOT LIKE '%INSTRUCTOR%'")
                conditions.append("UPPER(COALESCE(o.esquema, '')) NOT LIKE '%MOVEDOR%'")
                conditions.append("UPPER(COALESCE(o.tipo_unidad, '')) NOT LIKE '%INSTRUCTOR%'")
                conditions.append("UPPER(COALESCE(o.tipo_unidad, '')) NOT LIKE '%MOVEDOR%'")

            if solo_con_esquema:
                conditions.append("COALESCE(o.esquema, '') != ''")
                conditions.append("UPPER(COALESCE(o.esquema, '')) != 'VARIOS'")

            if producto:
                conditions.append("o.producto = ?")
                params.append(producto)

            where_clause = " AND ".join(conditions)
            sql = f"""
                SELECT o.id, o.no_empleado, o.nombre, o.linea_negocio, o.producto,
                       o.esquema, o.eco, o.vigencia_licencia, o.vigencia_medica,
                       o.tipo_jornada, o.estatus_empleado, o.tipo_unidad, o.base, o.orden_posicion
                FROM operadores o
                WHERE {where_clause}
                ORDER BY o.orden_posicion, o.nombre
            """
            c.execute(sql, params)
            return [_map_operador(row) for row in c.fetchall()]

    cache_key = f"operadores_activos:{producto or 'all'}:excluir={excluir_instructores_movedores}"
    return cached_query(cache_key, _query, LONG_TTL)


def get_operador_by_id(operador_id: int) -> Optional[Operador]:
    """Get single operator by ID."""
    with db_cursor() as c:
        c.execute("""
            SELECT id, no_empleado, nombre, linea_negocio, producto, esquema, eco,
                   vigencia_licencia, vigencia_medica, tipo_jornada, estatus_empleado,
                   tipo_unidad, base, orden_posicion
            FROM operadores
            WHERE id = ? AND estatus_empleado = 'Activo'
        """, (operador_id,))
        row = c.fetchone()
        return _map_operador(row) if row else None


def get_operador_by_nombre(nombre: str) -> Optional[Operador]:
    """Get single operator by exact name."""
    with db_cursor() as c:
        c.execute("""
            SELECT id, no_empleado, nombre, linea_negocio, producto, esquema, eco,
                   vigencia_licencia, vigencia_medica, tipo_jornada, estatus_empleado,
                   tipo_unidad, base, orden_posicion
            FROM operadores
            WHERE nombre = ? AND estatus_empleado = 'Activo'
        """, (nombre,))
        row = c.fetchone()
        return _map_operador(row) if row else None
def get_descansos_en_fecha(fecha: str, producto: Optional[str] = None) -> List[Descanso]:
    """
    Get operators resting on a specific date.
    Estatus considered as descanso: DE, D%, V% (descanso, vacaciones, etc.)
    Cached for DEFAULT_TTL (30s).
    """
    def _query() -> List[Descanso]:
        with db_cursor() as c:
            params: List[Any] = [fecha]
            where = "l.fecha = ? AND o.estatus_empleado = 'Activo'"
            where += " AND (l.estatus = 'DE' OR l.estatus LIKE 'D%' OR l.estatus LIKE 'V%')"

            if producto:
                where += " AND o.producto = ?"
                params.append(producto)

            where += " AND UPPER(COALESCE(o.esquema, '')) NOT LIKE '%INSTRUCTOR%'"
            where += " AND UPPER(COALESCE(o.esquema, '')) NOT LIKE '%MOVEDOR%'"

            sql = f"""
                SELECT o.id as operador_id, o.nombre, o.producto, l.estatus
                FROM logistica_diaria l
                JOIN operadores o ON l.operador_id = o.id
                WHERE {where}
                ORDER BY o.producto, o.nombre
            """
            c.execute(sql, params)
            rows = c.fetchall()
            return [Descanso(
                operador_id=row["operador_id"],
                nombre=row["nombre"],
                producto=row["producto"],
                estatus=row["estatus"],
            ) for row in rows]

    cache_key = f"descansos:{fecha}:{producto or 'all'}"
    return cached_query(cache_key, _query, DEFAULT_TTL)


def get_vigencias_por_vencer(dias: int = 30, producto: Optional[str] = None) -> List[VigenciaProxima]:
    """
    Get licenses and medical exams expiring within N days.
    Returns both expired (dias < 0) and upcoming (0 <= dias <= N).
    Cached for LONG_TTL (60s).
    """
    def _query() -> List[VigenciaProxima]:
        hoy = date.today()
        with db_cursor() as c:
            params: List[Any] = []
            where = "o.estatus_empleado = 'Activo'"
            where += " AND UPPER(COALESCE(o.esquema, '')) NOT LIKE '%INSTRUCTOR%'"
            where += " AND UPPER(COALESCE(o.esquema, '')) NOT LIKE '%MOVEDOR%'"

            if producto:
                where += " AND o.producto = ?"
                params.append(producto)

            sql = f"""
                SELECT o.id, o.nombre, o.producto, o.vigencia_licencia, o.vigencia_medica
                FROM operadores o
                WHERE {where}
            """
            c.execute(sql, params)
            results: List[VigenciaProxima] = []
            for row in c.fetchall():
                for tipo, val in [("Licencia", row["vigencia_licencia"]), ("Medico", row["vigencia_medica"])]:
                    if val and val != "N/A":
                        try:
                            f_venc = datetime.strptime(val, "%Y-%m-%d").date()
                            d_dif = (f_venc - hoy).days
                            if d_dif <= dias:
                                results.append(VigenciaProxima(
                                    operador_id=row["id"],
                                    nombre=row["nombre"],
                                    producto=row["producto"],
                                    tipo=tipo,
                                    fecha_vencimiento=val,
                                    dias_restantes=d_dif,
                                ))
                        except ValueError:
                            continue
            results.sort(key=lambda v: (v.dias_restantes >= 0, v.dias_restantes))
            return results

    cache_key = f"vigencias_por_vencer:{dias}:{producto or 'all'}"
    return cached_query(cache_key, _query, LONG_TTL)
def get_operadores_por_producto() -> Dict[str, List[Operador]]:
    """Get all active operators grouped by product. Cached for LONG_TTL."""
    def _query() -> Dict[str, List[Operador]]:
        ops = get_operadores_activos()
        grouped: Dict[str, List[Operador]] = {p: [] for p in PRODUCTOS_VALIDOS}
        for op in ops:
            if op.producto in grouped:
                grouped[op.producto].append(op)
        return grouped

    return cached_query("operadores_por_producto", _query, LONG_TTL)


def contar_activos_por_producto() -> Dict[str, int]:
    """Count active operators per product. Cached for LONG_TTL."""
    def _query() -> Dict[str, int]:
        with db_cursor() as c:
            c.execute("""
                SELECT o.producto, COUNT(*) as cnt
                FROM operadores o
                WHERE o.estatus_empleado = 'Activo'
                  AND UPPER(COALESCE(o.esquema, '')) NOT LIKE '%INSTRUCTOR%'
                  AND UPPER(COALESCE(o.esquema, '')) NOT LIKE '%MOVEDOR%'
                  AND COALESCE(o.esquema, '') != ''
                  AND UPPER(COALESCE(o.esquema, '')) != 'VARIOS'
                GROUP BY o.producto
            """)
            return {row["producto"]: row["cnt"] for row in c.fetchall()}

    return cached_query("contar_activos_por_producto", _query, LONG_TTL)


def get_candidatos_relevo(
    fecha: str,
    producto_objetivo: str,
    min_horas_libres: float = 15.0,
) -> List[Tuple[Operador, float]]:
    """
    Get operators resting on a date who have enough DOT hours free for a relief shift.
    Returns list of (Operador, horas_libres) sorted by horas_libres DESC.
    """
    from services.repositories.dot_repo import get_horas_libres_dot  # lazy import to avoid cycle

    descansando = get_descansos_en_fecha(fecha, producto=None)
    candidatos: List[Tuple[Operador, float]] = []

    for desc in descansando:
        op = get_operador_by_id(desc.operador_id)
        if not op:
            continue
        if op.producto != producto_objetivo and not _puede_cruzar(op.producto, producto_objetivo):
            continue
        horas_libres = get_horas_libres_dot(op.id)
        if horas_libres >= min_horas_libres:
            candidatos.append((op, horas_libres))

    candidatos.sort(key=lambda x: x[1], reverse=True)
    return candidatos


def _puede_cruzar(producto_origen: str, producto_destino: str) -> bool:
    """Reglas de cruce estructural entre productos."""
    if producto_origen == "OXIGENO" and producto_destino in ("CO2", "ARGON"):
        return True
    if producto_origen == producto_destino:
        return True
    return False


def buscar_operador_por_nombre_parcial(nombre_parcial: str) -> List[Operador]:
    """Search operators by partial name match (case-insensitive)."""
    with db_cursor() as c:
        c.execute("""
            SELECT id, no_empleado, nombre, linea_negocio, producto, esquema, eco,
                   vigencia_licencia, vigencia_medica, tipo_jornada, estatus_empleado,
                   tipo_unidad, base, orden_posicion
            FROM operadores
            WHERE estatus_empleado = 'Activo'
              AND LOWER(nombre) LIKE LOWER(?)
              AND UPPER(COALESCE(esquema, '')) NOT LIKE '%INSTRUCTOR%'
              AND UPPER(COALESCE(esquema, '')) NOT LIKE '%MOVEDOR%'
            ORDER BY nombre
        """, (f"%{nombre_parcial}%",))
        return [_map_operador(row) for row in c.fetchall()]
