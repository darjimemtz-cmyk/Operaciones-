#!/usr/bin/env python3
"""
Test de Validación Integral para Centinela IA - FNG San Luis Potosí
Prueba la inteligencia, tono y reglas de negocio del nuevo orquestador.

Escenarios probados:
1. Saludo Casual - Respuesta breve, natural, saluda por nombre
2. Consulta Puntual - Respuesta directa con nombres y estatus
3. Regla NOM-087 y Fatiga - Ventana 7 días (máx 70h), >=52h crítico, NO instructores/movedores
4. Dilema Táctico de Asignación - Razonamiento como copiloto cruzando producto, descanso, horas DOT
"""

import sys
import os
import time
from typing import Dict, Any, List

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.centinela_orchestrator import process_centinela_query, AIResponse
def run_test_case(
    name: str,
    pregunta: str,
    usuario: str = "Jimena Martínez",
    rol: str = "jefe_op",
    validaciones: List[str] = None
) -> Dict[str, Any]:
    """Ejecuta un caso de prueba y retorna métricas con validaciones."""
    print(f"\n{'='*70}")
    print(f"🧪 TEST: {name}")
    print(f"   Pregunta: {pregunta}")
    print(f"   Usuario: {usuario} | Rol: {rol}")
    print(f"{'='*70}")

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
            "content": response.content,
            "error": None
        }

        print(f"   ✅ SUCCESS: success={response.success}, provider={response.provider}")
        print(f"   ⏱️  Latencia: {latency_ms} ms")
        print(f"   📝 Respuesta completa ({len(response.content)} chars):")
        print(f"   {'-'*70}")
        print(response.content)
        print(f"   {'-'*70}")

        # Run validations if provided
        if validaciones:
            print(f"\n   🔍 VALIDACIONES:")
            for i, val in enumerate(validaciones, 1):
                # Simple keyword-based validation
                content_lower = response.content.lower()
                passed = val.lower() in content_lower
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"      {i}. {status} - '{val}' {'encontrado' if passed else 'NO encontrado'}")

    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        result = {
            "success": False,
            "provider": "error",
            "latency_ms": latency_ms,
            "content_length": 0,
            "content": "",
            "error": str(e)
        }
        print(f"   ❌ ERROR: {e}")

    return result


def main():
    print("🚀 INICIANDO TESTS DE VALIDACIÓN INTEGRAL DE CENTINELA IA")
    print("=" * 70)
    print("Usuario de prueba: Jimena Martínez (jefe_op)")
    print("=" * 70)

    test_cases = [
        {
            "name": "Escenario 1 - Saludo Casual",
            "pregunta": "hola centinela",
            "validaciones": [
                "jimena",  # Saluda por su nombre
                "hola",    # Saludo natural
            ],
            "criterio_exito": "Respuesta breve (1-2 renglones), natural, saluda por nombre 'Jimena', sin reportes ni tablas"
        },
        {
            "name": "Escenario 2 - Consulta Puntual: ¿Quién descansa hoy?",
            "pregunta": "¿quién descansa hoy?",
            "validaciones": [
                "descansa",  # Menciona quién descansa
                "estatus",   # Menciona estatus
            ],
            "criterio_exito": "Respuesta directa con nombres y estatus de operadores que descansan hoy según BD, sin rodeos corporativos"
        },
        {
            "name": "Escenario 3 - Regla NOM-087 y Fatiga: Horas DOT y zona crítica",
            "pregunta": "¿cómo andamos de horas DOT y quién está en zona crítica?",
            "validaciones": [
                "7 días",      # Ventana rodante de 7 días
                "70h",         # Máximo 70 horas
                "52h",         # Zona crítica >= 52h
            ],
            "criterio_exito": "Respeta ventana 7 días (máx 70h), reporta >=52h como crítico, NUNCA lista instructores ni movedores"
        },
        {
            "name": "Escenario 4 - Dilema Táctico: Cubrir viaje CO2 mañana",
            "pregunta": "Tengo que cubrir un viaje de CO2 mañana, ¿a quién me recomiendas jalar que esté en descanso?",
            "validaciones": [
                "co2",         # Entiende el producto CO2
                "descanso",    # Considera quién está en descanso
                "horas",       # Considera horas DOT libres
                "margen",      # Menciona margen de horas
            ],
            "criterio_exito": "Razonamiento como copiloto: cruza producto (CO2), quién descansa, quién tiene buen margen DOT"
        },
    ]

    results = []
    all_passed = True

    for tc in test_cases:
        result = run_test_case(
            tc["name"],
            tc["pregunta"],
            validaciones=tc.get("validaciones")
        )
        result["test_name"] = tc["name"]
        result["criterio_exito"] = tc["criterio_exito"]
        results.append(result)

        # Basic validation - check if successful
        if not result["success"]:
            print(f"   ⚠️  TEST FALLÓ: {result['error']}")
            all_passed = False
        else:
            print(f"   ✅ TEST COMPLETADO")

    # Summary
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE RESULTADOS")
    print("=" * 70)

    for r in results:
        status = "✅ PASS" if r["success"] else "❌ FAIL"
        print(f"\n   {status} | {r['test_name']}")
        print(f"      success={r['success']} | provider={r['provider']} | latency={r['latency_ms']}ms | chars={r['content_length']}")
        print(f"      Criterio: {r['criterio_exito']}")

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 TODOS LOS TESTS SE EJECUTARON CORRECTAMENTE")
        print("   Revisa las respuestas arriba para validar criterios de éxito manualmente.")
        return 0
    else:
        print("💥 ALGUNOS TESTS FALLARON EN EJECUCIÓN")
        return 1


if __name__ == "__main__":
    sys.exit(main())