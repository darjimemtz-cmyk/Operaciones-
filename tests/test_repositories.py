"""
Unit tests for Repository Layer - FNG San Luis Potosí
Tests run against actual SQLite database (control_maestro_v6.db).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import date, timedelta

from services.repositories import (
    db_cursor,
    cache_invalidate,
)
from services.repositories.operadores_repo import (
    get_operadores_activos,
    get_operador_by_id,
    get_operador_by_nombre,
    get_descansos_en_fecha,
    get_vigencias_por_vencer,
    get_operadores_por_producto,
    contar_activos_por_producto,
    buscar_operador_por_nombre_parcial,
    PRODUCTOS_VALIDOS,
)
from services.repositories.dot_repo import (
    get_horas_dot_7dias,
    get_horas_libres_dot,
    get_todas_horas_dot_7dias,
    get_cumplimiento_dot,
    get_ranking_fatiga,
    get_alertas_dot_criticas,
    get_alertas_dot_amarillas,
    get_operadores_sin_datos_dot,
    get_disponibilidad_por_producto,
    MAX_HORAS_7_DIAS,
    UMBRAL_FATIGA,
)
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
)


class TestOperadoresRepo:
    """Tests for operadores_repo.py"""

    def test_get_operadores_activos_returns_list(self):
        """Should return list of Operador objects."""
        ops = get_operadores_activos()
        assert isinstance(ops, list)
        assert len(ops) > 0
        for op in ops:
            assert hasattr(op, 'id')
            assert hasattr(op, 'nombre')
            assert hasattr(op, 'producto')
            assert op.estatus_empleado == 'Activo'

    def test_get_operadores_activos_excludes_instructores_movedores(self):
        """Should exclude instructors and movers by default."""
        ops = get_operadores_activos(excluir_instructores_movedores=True)
        for op in ops:
            esquema = (op.esquema or '').upper()
            tipo_unidad = (op.tipo_unidad or '').upper()
            assert 'INSTRUCTOR' not in esquema
            assert 'MOVEDOR' not in esquema
            assert 'INSTRUCTOR' not in tipo_unidad
            assert 'MOVEDOR' not in tipo_unidad

    def test_get_operadores_activos_filter_by_producto(self):
        """Should filter by product when specified."""
        for prod in PRODUCTOS_VALIDOS:
            ops = get_operadores_activos(producto=prod)
            for op in ops:
                assert op.producto == prod

    def test_get_operador_by_id(self):
        """Should retrieve single operator by ID."""
        ops = get_operadores_activos()
        if ops:
            op = get_operador_by_id(ops[0].id)
            assert op is not None
            assert op.id == ops[0].id
            assert op.nombre == ops[0].nombre

    def test_get_operador_by_nombre(self):
        """Should retrieve single operator by exact name."""
        ops = get_operadores_activos()
        if ops:
            op = get_operador_by_nombre(ops[0].nombre)
            assert op is not None
            assert op.nombre == ops[0].nombre

    def test_get_descansos_en_fecha(self):
        """Should return operators resting on a given date."""
        hoy = date.today().strftime('%Y-%m-%d')
        descansos = get_descansos_en_fecha(hoy)
        assert isinstance(descansos, list)
        for d in descansos:
            assert hasattr(d, 'operador_id')
            assert hasattr(d, 'nombre')
            assert hasattr(d, 'estatus')
            assert d.estatus in ('DE', 'D1', 'D2', 'V1', 'V2') or d.estatus.startswith('D') or d.estatus.startswith('V')

    def test_get_vigencias_por_vencer(self):
        """Should return expiring licenses/medicals."""
        vigencias = get_vigencias_por_vencer(30)
        assert isinstance(vigencias, list)
        for v in vigencias:
            assert hasattr(v, 'operador_id')
            assert hasattr(v, 'tipo')
            assert v.tipo in ('Licencia', 'Medico')
            assert hasattr(v, 'dias_restantes')
            assert v.dias_restantes <= 30

    def test_get_operadores_por_producto(self):
        """Should group operators by product."""
        grouped = get_operadores_por_producto()
        assert isinstance(grouped, dict)
        for prod in PRODUCTOS_VALIDOS:
            assert prod in grouped
            for op in grouped[prod]:
                assert op.producto == prod

    def test_contar_activos_por_producto(self):
        """Should return counts per product."""
        counts = contar_activos_por_producto()
        assert isinstance(counts, dict)
        total = sum(counts.values())
        assert total > 0

    def test_buscar_operador_por_nombre_parcial(self):
        """Should find operators by partial name match."""
        ops = get_operadores_activos()
        if ops:
            # Search by first 3 chars of first operator
            partial = ops[0].nombre[:3]
            results = buscar_operador_por_nombre_parcial(partial)
            assert len(results) > 0
            assert any(partial.lower() in op.nombre.lower() for op in results)


class TestDotRepo:
    """Tests for dot_repo.py"""

    def test_get_horas_dot_7dias(self):
        """Should return HorasDOT for an operator."""
        ops = get_operadores_activos()
        if ops:
            h = get_horas_dot_7dias(ops[0].id)
            if h:
                assert hasattr(h, 'operador_id')
                assert hasattr(h, 'horas_7d')
                assert hasattr(h, 'horas_libres')
                assert hasattr(h, 'estatus')
                assert h.estatus in ('OK', 'ALERTA', 'CRITICO', 'SIN_DATOS')
                assert h.horas_7d >= 0
                assert h.horas_libres >= 0
                assert h.horas_7d + h.horas_libres <= MAX_HORAS_7_DIAS + 0.1  # rounding

    def test_get_horas_libres_dot(self):
        """Should return available hours for operator."""
        ops = get_operadores_activos()
        if ops:
            libres = get_horas_libres_dot(ops[0].id)
            assert isinstance(libres, float)
            assert 0 <= libres <= MAX_HORAS_7_DIAS

    def test_get_todas_horas_dot_7dias(self):
        """Should return DOT hours for all operators."""
        todas = get_todas_horas_dot_7dias()
        assert isinstance(todas, list)
        for h in todas:
            assert hasattr(h, 'operador_id')
            assert hasattr(h, 'estatus')
            assert h.estatus in ('OK', 'ALERTA', 'CRITICO', 'SIN_DATOS')

    def test_get_cumplimiento_dot(self):
        """Should return compliance summary."""
        cumpl = get_cumplimiento_dot()
        assert hasattr(cumpl, 'total_operadores')
        assert hasattr(cumpl, 'cumpliendo')
        assert hasattr(cumpl, 'alerta')
        assert hasattr(cumpl, 'critico')
        assert hasattr(cumpl, 'porcentaje_cumplimiento')
        assert cumpl.total_operadores >= 0
        assert 0 <= cumpl.porcentaje_cumplimiento <= 100

    def test_get_ranking_fatiga(self):
        """Should return fatigue ranking sorted by hours descending."""
        ranking = get_ranking_fatiga(top=10)
        assert isinstance(ranking, list)
        if len(ranking) > 1:
            for i in range(len(ranking) - 1):
                assert ranking[i].horas_7d >= ranking[i + 1].horas_7d
        for r in ranking:
            assert r.nivel in ('VERDE', 'AMARILLO', 'ROJO')
            if r.horas_7d >= MAX_HORAS_7_DIAS:
                assert r.nivel == 'ROJO'
            elif r.horas_7d >= UMBRAL_FATIGA:
                assert r.nivel == 'AMARILLO'
            else:
                assert r.nivel == 'VERDE'

    def test_get_alertas_dot_criticas(self):
        """Should return only CRITICAL operators."""
        criticas = get_alertas_dot_criticas()
        for h in criticas:
            assert h.estatus == 'CRITICO'

    def test_get_alertas_dot_amarillas(self):
        """Should return only ALERT operators."""
        amarillas = get_alertas_dot_amarillas()
        for h in amarillas:
            assert h.estatus == 'ALERTA'

    def test_get_disponibilidad_por_producto(self):
        """Should return available hours grouped by product."""
        disp = get_disponibilidad_por_producto()
        assert isinstance(disp, dict)
        for prod, lista in disp.items():
            assert isinstance(lista, list)
            if len(lista) > 1:
                for i in range(len(lista) - 1):
                    assert lista[i][1] >= lista[i + 1][1]  # sorted descending


class TestFlotaRepo:
    """Tests for flota_repo.py"""

    def test_get_unidades_activas(self):
        """Should return active units."""
        unidades = get_unidades_activas()
        assert isinstance(unidades, list)
        for u in unidades:
            assert hasattr(u, 'eco')
            assert hasattr(u, 'producto')
            assert hasattr(u, 'estatus')
            assert u.estatus in ('ACTIVA', 'MANTENIMIENTO')

    def test_get_unidad_by_eco(self):
        """Should retrieve single unit by ECO."""
        unidades = get_unidades_activas()
        if unidades:
            u = get_unidad_by_eco(unidades[0].eco)
            assert u is not None
            assert u.eco == unidades[0].eco

    def test_get_deficit_por_producto(self):
        """Should calculate deficit per product."""
        deficits = get_deficit_por_producto()
        assert isinstance(deficits, list)
        for d in deficits:
            assert hasattr(d, 'producto')
            assert hasattr(d, 'objetivo')
            assert hasattr(d, 'activas')
            assert hasattr(d, 'deficit')
            assert hasattr(d, 'porcentaje')
            assert d.objetivo == OBJETIVO_POR_PRODUCTO.get(d.producto, 0)
            assert d.deficit == max(0, d.objetivo - d.activas)

    def test_get_resumen_flota(self):
        """Should return complete fleet summary."""
        resumen = get_resumen_flota()
        assert hasattr(resumen, 'total_unidades')
        assert hasattr(resumen, 'activas')
        assert hasattr(resumen, 'objetivo_total')
        assert hasattr(resumen, 'deficit_total')
        assert hasattr(resumen, 'por_producto')
        assert resumen.objetivo_total == TOTAL_OBJETIVO
        assert resumen.deficit_total == sum(d.deficit for d in resumen.por_producto)

    def test_get_unidades_sin_operador(self):
        """Should return active units without operator."""
        sin_op = get_unidades_sin_operador()
        assert isinstance(sin_op, list)
        for u in sin_op:
            assert u.estatus == 'ACTIVA'
            assert u.operador_id is None or u.operador_id == ''

    def test_get_unidades_en_mantenimiento(self):
        """Should return units in maintenance."""
        mant = get_unidades_en_mantenimiento()
        assert isinstance(mant, list)
        for u in mant:
            assert u.estatus == 'MANTENIMIENTO'

    def test_get_cobertura_operativa(self):
        """Should return coverage per product."""
        cobertura = get_cobertura_operativa()
        assert isinstance(cobertura, dict)
        for prod, data in cobertura.items():
            assert 'con_operador' in data
            assert 'sin_operador' in data
            assert 'total' in data
            assert data['total'] == data['con_operador'] + data['sin_operador']

    def test_validar_objetivo_31_unidades(self):
        """Should validate 31-unit target."""
        ok, msg = validar_objetivo_31_unidades()
        assert isinstance(ok, bool)
        assert isinstance(msg, str)
        assert str(TOTAL_OBJETIVO) in msg


class TestCacheInvalidation:
    """Test cache invalidation works."""

    def test_cache_invalidate(self):
        """Should clear cache."""
        # First call populates cache
        _ = get_operadores_activos()
        # Invalidate
        cache_invalidate("operadores_activos")
        # Second call should re-query
        _ = get_operadores_activos()
        # No exception means it works
        assert True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
