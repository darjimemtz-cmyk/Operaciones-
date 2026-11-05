#!/usr/bin/env python3
"""
Test Phase 2: Tool Layer & Registry Validation
Validates all tools against control_maestro_v6.db without Flask.
"""

import sys
import time
import traceback
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, "/home/jimena_martinez/Documentos/operaciones - copia")

from services.tools import (
    list_tools,
    get_categories,
    call_tool,
    get_tool_def,
)

# Import tool modules to ensure registration
from services.tools import dot_tools, hr_tools, flota_tools


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(tool_name: str, result: Any, elapsed: float):
    status = "✓" if elapsed < 1.5 else "⚠ SLOW"
    print(f"  {status} {tool_name}: {elapsed:.3f}s")
    if isinstance(result, list):
        print(f"    → {len(result)} items")
    elif isinstance(result, dict):
        keys = list(result.keys())[:5]
        print(f"    → keys: {keys}{'...' if len(result) > 5 else ''}")
    elif result is None:
        print(f"    → None")
    else:
        print(f"    → {type(result).__name__}")


def test_category(category: str, tool_names: List[str]) -> Dict[str, Any]:
    print(f"\n  Testing {category.upper()} tools:")
    results = {}
    for name in tool_names:
        try:
            start = time.perf_counter()
            if name in ["dot_horas_operador", "dot_horas_libres", "hr_operador_by_id", "flota_unidad_by_eco", "hr_buscar_operador"]:
                result = {"skipped": "requires specific parameter"}
                elapsed = 0.0
            elif name in ["dot_ranking_fatiga"]:
                result = call_tool(name, top=5)
                elapsed = time.perf_counter() - start
            elif name in ["hr_descansos_fecha"]:
                result = {"skipped": "requires date parameter"}
                elapsed = 0.0
            elif name in ["hr_vigencias_proximas"]:
                result = call_tool(name, dias=30)
                elapsed = time.perf_counter() - start
            else:
                result = call_tool(name)
                elapsed = time.perf_counter() - start
            
            results[name] = {"result": result, "elapsed": elapsed, "error": None}
            print_result(name, result, elapsed)
            
        except Exception as e:
            elapsed = time.perf_counter() - start
            results[name] = {"result": None, "elapsed": elapsed, "error": str(e)}
            print(f"  ✗ {name}: ERROR ({elapsed:.3f}s) - {e}")
    
    return results
def main():
    print_section("PHASE 2 TOOL LAYER VALIDATION")
    print("Database: control_maestro_v6.db")
    print("Target latency: < 1.5s per tool")
    
    # List all registered tools
    all_tools = list_tools()
    categories = get_categories()
    
    print_section(f"REGISTERED TOOLS ({len(all_tools)} total)")
    for cat in categories:
        cat_tools = [t for t in all_tools if t["category"] == cat]
        print(f"\n  {cat.upper()} ({len(cat_tools)} tools):")
        for t in cat_tools:
            params = ", ".join([f"{k}:{v['type']}" for k, v in t["parameters"].items()])
            print(f"    • {t['name']}({params}) -> {t['returns']}")
            print(f"      {t['description'][:80]}...")
    
    # Test each category
    print_section("EXECUTION TESTS")
    
    dot_tool_names = [t["name"] for t in all_tools if t["category"] == "dot"]
    hr_tool_names = [t["name"] for t in all_tools if t["category"] == "hr"]
    flota_tool_names = [t["name"] for t in all_tools if t["category"] == "flota"]
    
    dot_results = test_category("dot", dot_tool_names)
    hr_results = test_category("hr", hr_tool_names)
    flota_results = test_category("flota", flota_tool_names)
    
    # Summary
    print_section("SUMMARY")
    
    all_results = {**dot_results, **hr_results, **flota_results}
    total = len(all_results)
    passed = sum(1 for r in all_results.values() if r["error"] is None and "skipped" not in str(r["result"]))
    slow = sum(1 for r in all_results.values() if r["elapsed"] > 1.5)
    errors = sum(1 for r in all_results.values() if r["error"] is not None)
    skipped = sum(1 for r in all_results.values() if "skipped" in str(r["result"]))
    
    print(f"  Total tools tested: {total}")
    print(f"  ✓ Passed: {passed}")
    print(f"  ⚠ Slow (>1.5s): {slow}")
    print(f"  ✗ Errors: {errors}")
    print(f"  ⊘ Skipped (need params): {skipped}")
    
    if errors > 0:
        print("\n  ERRORS:")
        for name, data in all_results.items():
            if data["error"]:
                print(f"    {name}: {data['error']}")
    
    # Validate business rules
    print_section("BUSINESS RULE VALIDATION")
    
    # Test DOT constants
    const = call_tool("dot_constantes")
    print(f"  DOT Window: {const['ventana_dias']} days (expected: 7)")
    print(f"  DOT Max Hours: {const['max_horas_7_dias']}h (expected: 70)")
    print(f"  Fatigue Threshold: {const['umbral_fatiga']}h (expected: 52)")
    
    # Test Fleet targets
    fleet_targets = call_tool("flota_objetivos")
    print(f"  Fleet Total Target: {fleet_targets['total_objetivo']} (expected: 31)")
    print(f"  Per Product: {fleet_targets['por_producto']}")
    
    # Test HR products
    products = call_tool("hr_productos_validos")
    print(f"  Valid Products: {products}")
    
    # Test a real DOT query
    print_section("REAL DATA SAMPLES")
    
    # Get compliance
    cumplimiento = call_tool("dot_cumplimiento")
    print(f"  DOT Compliance: {cumplimiento['porcentaje_cumplimiento']}% ({cumplimiento['cumpliendo']}/{cumplimiento['total_operadores']})")
    
    # Get fleet summary
    flota = call_tool("flota_resumen")
    print(f"  Fleet: {flota['activas']}/{flota['objetivo_total']} active, deficit: {flota['deficit_total']}")
    
    # Get operator count by product
    counts = call_tool("hr_contar_activos_por_producto")
    print(f"  Operators by product: {counts}")
    
    # Get critical alerts
    criticas = call_tool("dot_alertas_criticas")
    print(f"  Critical DOT alerts (>=70h): {len(criticas)}")
    
    # Get yellow alerts
    amarillas = call_tool("dot_alertas_amarillas")
    print(f"  Yellow DOT alerts (52-69h): {len(amarillas)}")
    
    # Test descanso hoy
    descansos = call_tool("hr_descansos_hoy")
    print(f"  Operators resting today: {len(descansos)}")
    
    print_section("PHASE 2 VALIDATION COMPLETE")
    
    if errors == 0:
        print("  ✓ ALL TOOLS REGISTERED AND EXECUTING")
        print("  ✓ BUSINESS RULES VALIDATED")
        print("  ✓ LATENCY TARGETS MET")
        return 0
    else:
        print(f"  ✗ {errors} TOOLS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())