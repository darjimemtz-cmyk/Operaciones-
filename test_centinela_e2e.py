#!/usr/bin/env python3
"""
Test End-to-End para Centinela IA - FNG San Luis Potosí
Valida el orquestador con 3 casos de prueba:
1. Saludo simple ("hola centinela")
2. Consulta puntual ("¿quién descansa hoy?")
3. Asignación táctica ("¿a quién sugieres para cubrir CO2 mañana?")
"""

import sys
import os
import time
from typing import Dict, Any

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.centinela_orchestrator import process_centinela_query, AIResponse


def run_test_case(name: str, pregunta: str, usuario: str = "Test User", rol: str = "jefe_op") -> Dict[str, Any]:
    """Ejecuta un caso de prueba y retorna métricas."""
    print(f"\n{'='*60}")
    print(f"🧪 TEST: {name}")
    print(f"   Pregunta: {pregunta}")
    print(f"{'='*60}")
    
    start_time = time.perf_counter()
    
    try:
        response = process_centinela_query(
            pregunta=pregunta,
            usuario=usuario,
            rol=rol,
            ruta_pantalla="/panel_operativo",
            historial=[],
        )
        
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        result = {
            "success": response.success,
            "provider": response.provider,
            "latency_ms": latency_ms,
            "content_length": len(response.content),
            "content_preview": response.content[:200] + "..." if len(response.content) > 200 else response.content,
            "error": None
        }
        
        print(f"   ✅ SUCCESS: success={response.success}, provider={response.provider}")
        print(f"   ⏱️  Latencia: {latency_ms} ms")
        print(f"   📝 Respuesta ({len(response.content)} chars): {result['content_preview']}")
        
    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        result = {
            "success": False,
            "provider": "error",
            "latency_ms": latency_ms,
            "content_length": 0,
            "content_preview": "",
            "error": str(e)
        }
        print(f"   ❌ ERROR: {e}")
    
    return result


def main():
    print("🚀 INICIANDO TESTS END-TO-END DE CENTINELA IA")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "Caso 1 - Saludo simple",
            "pregunta": "hola centinela",
            "expected_success": True
        },
        {
            "name": "Caso 2 - Consulta puntual",
            "pregunta": "¿quién descansa hoy?",
            "expected_success": True
        },
        {
            "name": "Caso 3 - Asignación táctica",
            "pregunta": "¿a quién sugieres para cubrir CO2 mañana?",
            "expected_success": True
        },
    ]
    
    results = []
    all_passed = True
    
    for tc in test_cases:
        result = run_test_case(tc["name"], tc["pregunta"])
        result["test_name"] = tc["name"]
        result["expected_success"] = tc["expected_success"]
        results.append(result)
        
        # Validate
        if result["success"] != tc["expected_success"]:
            print(f"   ⚠️  VALIDATION FAILED: Expected success={tc['expected_success']}, got {result['success']}")
            all_passed = False
        elif not result["success"]:
            print(f"   ⚠️  TEST FAILED: {result['error']}")
            all_passed = False
        else:
            print(f"   ✅ VALIDATION PASSED")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE RESULTADOS")
    print("=" * 60)
    
    for r in results:
        status = "✅ PASS" if r["success"] == r["expected_success"] and r["success"] else "❌ FAIL"
        print(f"   {status} | {r['test_name']} | success={r['success']} | provider={r['provider']} | latency={r['latency_ms']}ms")
    
    print("=" * 60)
    if all_passed:
        print("🎉 TODOS LOS TESTS PASARON EN VERDE")
        return 0
    else:
        print("💥 ALGUNOS TESTS FALLARON")
        return 1


if __name__ == "__main__":
    sys.exit(main())