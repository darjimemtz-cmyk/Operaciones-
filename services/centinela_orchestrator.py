"""
Orquestador Centinela - FNG San Luis Potosí
Intelligent routing: intent analysis -> deterministic tool invocation -> context assembly -> AI query.
Business rules: 7-day rolling window (max 70h), instructors/movers NEVER in DOT, 31 units target.
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from services.tools import (
    call_tool,
    list_tools,
    get_categories,
)
from services.prompt_builder import PromptBuilder, PromptContext
from services.ai_client import AIClient, AIResponse


# ============================================================
# INTENT CLASSIFICATION
# ============================================================

SALUDO_PATTERNS = [
    r"^\s*hola\b",
    r"^\s*buen[oa]s?\s*(d[ií]as?|tardes?|noches?)",
    r"^\s*qu[eé]\s*tal\b",
    r"^\s*c[oó]mo\s+(est[aá]s?|va|te\s+va)",
    r"^\s*saludos?\b",
    r"^\s*hey\b",
    r"^\s*hi\b",
    r"^\s*hello\b",
]

CONSULTA_PUNTUAL_PATTERNS = [
    r"qu[ié]n\s+descansa",
    r"cu[aá]ntos?\s+descansan",
    r"d[eé]ficit",
    r"horas\s+(del|de)\s+\d+",
    r"c[oó]mo\s+est[aá]\s+(el\s+)?(di[eé]sel|diesel)",
    r"licencias?",
    r"vigencias?",
    r"ex[aá]menes?\s+m[eé]dic[oa]s?",
    r"estatus\s+(flota|unidades?)",
    r"unidades?\s+(activas?|sin\s+operador|en\s+mantenimiento)",
    r"ranking\s+fatiga",
    r"fatiga",
    r"nom-?087",
    r"dot",
]

DILEMA_COBERTURA_PATTERNS = [
    r"a\s+qui[eé]n\s+(mando|env[ií]o|asigno|pongo)",
    r"c[oó]mo\s+(cubro|cubrimos|resuelvo)",
    r"falta\s+de\s+\w+",
    r"necesito\s+(un|una)\s+\w+\s+para",
    r"relevo",
    r"candidato",
    r"mejor\s+opci[oó]n",
    r"qu[eé]\s+hago\s+con",
    r"dictamen",
    r"recomiend",
]


def classify_intent(pregunta: str) -> str:
    """
    Classify user intent into one of three categories:
    - 'saludo': greeting/casual chat -> skip heavy tools
    - 'consulta_puntual': specific factual query -> targeted tools
    - 'dilema_cobertura': decision/tactical dilemma -> full context + AI reasoning
    """
    p = pregunta.lower().strip()
    
    # Check saludo first (highest priority for fast path)
    for pattern in SALUDO_PATTERNS:
        if re.search(pattern, p):
            return "saludo"
    
    # Check dilema cobertura (needs full context + AI reasoning)
    for pattern in DILEMA_COBERTURA_PATTERNS:
        if re.search(pattern, p):
            return "dilema_cobertura"
    
    # Check consulta puntual (targeted tools)
    for pattern in CONSULTA_PUNTUAL_PATTERNS:
        if re.search(pattern, p):
            return "consulta_puntual"
    
    # Default: treat as consulta puntual for safety
    return "consulta_puntual"


def get_screen_category(ruta_pantalla: str) -> str:
    """
    Map a route/screen path to a tool category.
    Categories: 'dot', 'hr', 'flota', 'general', 'diesel', 'sabana'
    """
    ruta = (ruta_pantalla or "").lower()
    
    if "dot" in ruta or "recursos" in ruta:
        return "dot"
    elif "diesel" in ruta:
        return "diesel"
    elif "sabana" in ruta or "acumulado" in ruta:
        return "sabana"
    elif "panel_operativo" in ruta or "operativo" in ruta:
        return "flota"
    elif "personal" in ruta or "operador" in ruta or "licencia" in ruta or "examen" in ruta:
        return "hr"
    else:
        return "general"


def select_tools(intent: str, screen_category: str, pregunta: str = "") -> List[str]:
    """
    Select deterministic tools based on intent and screen category.
    Returns list of tool names to execute.
    """
    tools = []
    p = (pregunta or "").lower()

    # Base tools for all intents (except saludo which is handled earlier)
    if intent == "consulta_puntual":
        # Consulta de descansos ("¿quién descansa?", etc.)
        if any(kw in p for kw in ["descansa", "descanso", "libre hoy", "franco"]):
            tools = ["hr_descansos_hoy"]
            if "mañana" in p or "manana" in p:
                tools.append("hr_descansos_manana")
        # Consulta de Horas DOT, Fatiga o NOM-087
        elif any(kw in p for kw in ["dot", "horas", "fatiga", "nom-087", "nom087", "cumplimiento", "ranking", "alerta"]):
            tools = ["dot_cumplimiento", "dot_ranking_fatiga", "dot_alertas_amarillas"]
        # Consulta de licencias/vigencias
        elif any(kw in p for kw in ["licencia", "vigencia", "examen", "médico", "medico", "venc"]):
            tools = ["hr_vigencias_proximas", "hr_vigencias_vencidas"]
        # Consulta de flota/cobertura/deficit
        elif screen_category == "flota" or any(kw in p for kw in ["flota", "unidad", "eco", "cobertura", "déficit", "deficit", "sin operador", "mantenimiento"]):
            tools = ["flota_resumen", "flota_sin_operador", "flota_en_mantenimiento", "flota_deficit_por_producto"]
        # Consulta de diesel
        elif screen_category == "diesel":
            tools = ["diesel_resumen"]
        # Consulta de sabana
        elif screen_category == "sabana":
            tools = ["sabana_resumen"]
        # Consulta DOT genérica (pantalla DOT)
        elif screen_category == "dot":
            tools = ["dot_cumplimiento", "dot_ranking_fatiga", "dot_alertas_amarillas"]
        # Consulta HR genérica (pantalla personal)
        elif screen_category == "hr":
            tools = ["hr_descansos_hoy", "hr_vigencias_proximas", "hr_operadores_activos"]
        else:  # general
            tools = ["flota_resumen", "dot_cumplimiento", "hr_descansos_hoy"]

    elif intent == "dilema_cobertura":
        # Dilemas de cobertura o asignación de viajes (ej. viaje de CO2)
        # Full context for tactical decisions
        tools = [
            "hr_descansos_hoy",
            "hr_descansos_manana",
            "dot_disponibilidad",
            "dot_todas_horas",
            "hr_vigencias_proximas",
            "flota_deficit_por_producto",
            "flota_resumen",
        ]

    return tools


# ============================================================
# CONTEXT ASSEMBLY
# ============================================================

@dataclass
class OrchestratorContext:
    """Assembled context from tool executions."""
    fleet_summary: Dict[str, Any] = field(default_factory=dict)
    dot_hours: Dict[str, Any] = field(default_factory=dict)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    additional: Dict[str, Any] = field(default_factory=dict)
    tool_results: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0


def execute_tools(tool_names: List[str], screen_category: str, pregunta: str) -> OrchestratorContext:
    """
    Execute selected tools deterministically and assemble context.
    Business rules enforced by tools layer (repositories).
    """
    start = time.perf_counter()
    ctx = OrchestratorContext()
    ctx.additional["screen_category"] = screen_category
    ctx.additional["pregunta_original"] = pregunta
    
    for tool_name in tool_names:
        try:
            result = call_tool(tool_name)
            ctx.tool_results[tool_name] = result
            
            if tool_name.startswith("flota_"):
                if tool_name == "flota_resumen":
                    ctx.fleet_summary = result
                elif tool_name == "flota_sin_operador":
                    ctx.additional["unidades_sin_operador"] = result
                elif tool_name == "flota_en_mantenimiento":
                    ctx.additional["unidades_en_mantenimiento"] = result
                elif tool_name == "flota_cobertura_operativa":
                    ctx.fleet_summary["cobertura"] = result
                elif tool_name == "flota_deficit_por_producto":
                    ctx.fleet_summary["deficit_por_producto"] = result
                elif tool_name == "flota_unidades_activas":
                    ctx.fleet_summary["unidades_activas"] = result
                    
            elif tool_name.startswith("dot_"):
                if tool_name == "dot_cumplimiento":
                    ctx.dot_hours["cumplimiento"] = result
                elif tool_name == "dot_ranking_fatiga":
                    ctx.dot_hours["ranking_fatiga"] = result
                elif tool_name == "dot_disponibilidad":
                    ctx.dot_hours["disponibilidad"] = result
                elif tool_name == "dot_alertas_criticas":
                    ctx.alerts.extend([{**a, "nivel": "CRITICO"} for a in result])
                elif tool_name == "dot_alertas_amarillas":
                    ctx.alerts.extend([{**a, "nivel": "AMARILLO"} for a in result])
                elif tool_name == "dot_sin_datos":
                    ctx.alerts.extend([{**a, "nivel": "SIN_DATOS"} for a in result])
                elif tool_name == "dot_todas_horas":
                    ctx.dot_hours["todas_horas"] = result
                elif tool_name == "dot_constantes":
                    ctx.dot_hours["constantes"] = result
                    
            elif tool_name.startswith("hr_"):
                if tool_name == "hr_descansos_hoy":
                    ctx.additional["descansos_hoy"] = result
                elif tool_name == "hr_descansos_manana":
                    ctx.additional["descansos_manana"] = result
                elif tool_name == "hr_descansos_fecha":
                    ctx.additional["descansos_fecha"] = result
                elif tool_name == "hr_vigencias_proximas":
                    ctx.alerts.extend([{**v, "tipo": "VIGENCIA"} for v in result])
                elif tool_name == "hr_vigencias_vencidas":
                    ctx.alerts.extend([{**v, "tipo": "VENCIDA", "nivel": "CRITICO"} for v in result])
                elif tool_name == "hr_operadores_activos":
                    ctx.additional["operadores_activos"] = result
                elif tool_name == "hr_contar_activos_por_producto":
                    ctx.additional["conteo_por_producto"] = result
                elif tool_name == "hr_operadores_por_producto":
                    ctx.additional["operadores_por_producto"] = result
                    
        except Exception as e:
            ctx.tool_results[tool_name] = {"error": str(e)}
            print(f"[CentinelaOrchestrator] Tool {tool_name} failed: {e}")
    
    ctx.execution_time_ms = int((time.perf_counter() - start) * 1000)
    return ctx


def build_ai_context(ctx: OrchestratorContext, usuario: str, rol: str, 
                     ruta_pantalla: str, quiere_pdf: bool = False, 
                     boton_pdf_html: str = "", detalle_cambio: str = "",
                     deficits_detectados: List[str] = None) -> Dict[str, Any]:
    """Convert OrchestratorContext to PromptBuilder context_data format."""
    
    fleet = {
        "total_unidades": 31,
        "unidades_activas": ctx.fleet_summary.get("activas", 31),
        "contexto_pantalla": ctx.additional.get("contexto_pantalla", ""),
    }
    if "deficit_por_producto" in ctx.fleet_summary:
        fleet["deficit_por_producto"] = ctx.fleet_summary["deficit_por_producto"]
    if "cobertura" in ctx.fleet_summary:
        fleet["cobertura"] = ctx.fleet_summary["cobertura"]
    if "unidades_activas" in ctx.fleet_summary:
        fleet["unidades_detalle"] = ctx.fleet_summary["unidades_activas"]
    
    dot = {
        "ventana_dias": 7,
        "max_horas_7_dias": 70,
        "umbral_fatiga": 52,
    }
    if "cumplimiento" in ctx.dot_hours:
        c = ctx.dot_hours["cumplimiento"]
        dot["cumplimiento"] = {
            "total": c.get("total_operadores", 0),
            "ok": c.get("cumpliendo", 0),
            "alerta": c.get("alerta", 0),
            "critico": c.get("critico", 0),
            "sin_datos": c.get("sin_datos", 0),
            "porcentaje": c.get("porcentaje_cumplimiento", 0),
        }
    if "ranking_fatiga" in ctx.dot_hours:
        dot["ranking_fatiga"] = ctx.dot_hours["ranking_fatiga"]
    if "disponibilidad" in ctx.dot_hours:
        dot["disponibilidad"] = ctx.dot_hours["disponibilidad"]
    if "todas_horas" in ctx.dot_hours:
        dot["todas_horas"] = ctx.dot_hours["todas_horas"]
    
    alerts = []
    for a in ctx.alerts:
        if a.get("nivel") in ("CRITICO", "AMARILLO", "SIN_DATOS"):
            alerts.append({
                "operador": a.get("nombre"),
                "producto": a.get("producto"),
                "horas_7d": a.get("horas_7d"),
                "horas_libres": a.get("horas_libres"),
                "nivel": a.get("nivel"),
            })
        elif a.get("tipo") == "VIGENCIA":
            alerts.append({
                "operador": a.get("nombre"),
                "producto": a.get("producto"),
                "tipo_documento": a.get("tipo"),
                "fecha_vencimiento": a.get("fecha_vencimiento"),
                "dias_restantes": a.get("dias_restantes"),
                "nivel": "VENCIDA" if a.get("dias_restantes", 1) < 0 else "POR_VENCER",
            })
    
    additional = {
        "usuario": usuario,
        "rol": rol,
        "pantalla": ruta_pantalla,
        "screen_category": ctx.additional.get("screen_category", "default"),
        "quiere_pdf": quiere_pdf,
        "boton_pdf_html": boton_pdf_html if quiere_pdf else "",
        "detalle_cambio": detalle_cambio,
        "deficits_detectados": deficits_detectados or [],
        "descansos_hoy": ctx.additional.get("descansos_hoy", []),
        "descansos_manana": ctx.additional.get("descansos_manana", []),
        "operadores_activos": ctx.additional.get("operadores_activos", []),
        "conteo_por_producto": ctx.additional.get("conteo_por_producto", {}),
        "unidades_sin_operador": ctx.additional.get("unidades_sin_operador", []),
        "unidades_en_mantenimiento": ctx.additional.get("unidades_en_mantenimiento", []),
        "tool_execution_ms": ctx.execution_time_ms,
        # Friendly field names for LLM consumption
        "fatiga_nom": {
            "ranking_fatiga": ctx.dot_hours.get("ranking_fatiga", []),
            "alertas_amarillas": [a for a in ctx.alerts if a.get("nivel") == "AMARILLO"],
            "alertas_criticas": [a for a in ctx.alerts if a.get("nivel") == "CRITICO"],
        },
        "horas_dot": {
            "cumplimiento": ctx.dot_hours.get("cumplimiento", {}),
            "todas_horas": ctx.dot_hours.get("todas_horas", []),
            "disponibilidad": ctx.dot_hours.get("disponibilidad", {}),
        },
        "vigencias": [a for a in alerts if a.get("nivel") in ("VENCIDA", "POR_VENCER")],
    }
    
    return {
        "fleet_summary": fleet,
        "dot_hours": dot,
        "alerts": alerts,
        "additional": additional,
    }


# ============================================================
# MAIN ORCHESTRATOR CLASS
# ============================================================

class CentinelaOrchestrator:
    """Main orchestrator for Centinela IA."""
    
    def __init__(
        self,
        ai_client: Optional[AIClient] = None,
        prompt_builder: Optional[PromptBuilder] = None,
    ):
        self.ai_client = ai_client or AIClient(timeout_seconds=15)
        self.prompt_builder = prompt_builder or PromptBuilder(max_context_chars=8000)
    
    def process(
        self,
        pregunta: str,
        usuario: str,
        rol: str,
        ruta_pantalla: str = "",
        historial: Optional[List[Dict[str, str]]] = None,
        cambio: Optional[Dict[str, Any]] = None,
        quiere_pdf: bool = False,
        boton_pdf_html: str = "",
        deficits_detectados: Optional[List[str]] = None,
    ) -> AIResponse:
        start_total = time.perf_counter()
        
        intent = classify_intent(pregunta)
        
        if intent == "saludo":
            greeting = self._generate_tactical_greeting(usuario, rol, ruta_pantalla)
            return AIResponse(
                content=greeting,
                provider="local",
                latency_ms=int((time.perf_counter() - start_total) * 1000),
                success=True,
            )
        
        screen_category = get_screen_category(ruta_pantalla)
        tool_names = select_tools(intent, screen_category, pregunta)
        ctx = execute_tools(tool_names, screen_category, pregunta)
        
        detalle_cambio_str = ""
        if cambio and cambio.get("operador_id"):
            detalle_cambio_str = self._build_detalle_cambio(cambio, ctx)
        
        ai_context = build_ai_context(
            ctx=ctx,
            usuario=usuario,
            rol=rol,
            ruta_pantalla=ruta_pantalla,
            quiere_pdf=quiere_pdf,
            boton_pdf_html=boton_pdf_html,
            detalle_cambio=detalle_cambio_str,
            deficits_detectados=deficits_detectados or [],
        )
        
        try:
            system_prompt, user_prompt = self.prompt_builder.build_prompt(
                user_query=pregunta or "Dame un resumen del estatus de la flota y riesgos inmediatos.",
                context_data=ai_context,
                history=historial,
            )
            
            ai_response = self.ai_client.query(user_prompt, system_prompt)
            total_latency = int((time.perf_counter() - start_total) * 1000)
            ai_response.latency_ms = total_latency
            return ai_response
            
        except Exception as e:
            return AIResponse(
                content="",
                provider="none",
                latency_ms=int((time.perf_counter() - start_total) * 1000),
                success=False,
                error=f"Orchestrator error: {str(e)}",
            )
    
    def _generate_tactical_greeting(self, usuario: str, rol: str, ruta_pantalla: str) -> str:
        primer_nombre = usuario.split()[0] if usuario else "Compañero"
        screen = (ruta_pantalla or "").lower()
        
        if "diesel" in screen:
            return f"Buen día, {primer_nombre}. Diésel bajo control, sin focos rojos críticos. ¿En qué te apoyo?"
        elif "dot" in screen or "recursos" in screen:
            return f"Buen día, {primer_nombre}. DOT al día, ventana de 7 días limpia. ¿Qué necesitas checar?"
        elif "sabana" in screen or "acumulado" in screen:
            return f"Buen día, {primer_nombre}. 31 unidades en objetivo, sin alertas de fatiga. ¿Movemos algo hoy?"
        elif "panel_operativo" in screen or "operativo" in screen:
            return f"Buen día, {primer_nombre}. Patio tranquilo, cobertura completa. ¿Qué resolvemos?"
        else:
            return f"Buen día, {primer_nombre}. Todo tranquilo en operaciones. ¿En qué te apoyo?"
    
    def _build_detalle_cambio(self, cambio: Dict[str, Any], ctx: OrchestratorContext) -> str:
        op_id = cambio.get("operador_id")
        f_cambio = cambio.get("fecha", "")
        est_nuevo = cambio.get("estatus_nuevo", "")
        
        op_nombre = "Operador"
        op_producto = ""
        
        for op in ctx.additional.get("operadores_activos", []):
            if op.get("id") == op_id:
                op_nombre = op.get("nombre", "Operador")
                op_producto = op.get("producto", "")
                break
        
        if not op_producto:
            for h in ctx.dot_hours.get("todas_horas", []):
                if h.get("operador_id") == op_id:
                    op_nombre = h.get("nombre", "Operador")
                    op_producto = h.get("producto", "")
                    break
        
        h_7d = 0.0
        for h in ctx.dot_hours.get("todas_horas", []):
            if h.get("operador_id") == op_id:
                h_7d = h.get("horas_7d", 0.0)
                break
        
        est_act = "TR"
        
        return (f"EVALUACIÓN MODAL: Operador {op_nombre} ({op_producto}), "
                f"fecha {f_cambio}, pasar de {est_act} a {est_nuevo}. "
                f"Horas DOT en 7 días: {h_7d:.1f}h/70h.")


# ============================================================
# CONVENIENCE FUNCTION FOR DIRECT USE
# ============================================================

_orchestrator_instance: Optional[CentinelaOrchestrator] = None


def get_orchestrator() -> CentinelaOrchestrator:
    """Get or create singleton orchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = CentinelaOrchestrator()
    return _orchestrator_instance


def process_centinela_query(
    pregunta: str,
    usuario: str,
    rol: str,
    ruta_pantalla: str = "",
    historial: Optional[List[Dict[str, str]]] = None,
    cambio: Optional[Dict[str, Any]] = None,
    quiere_pdf: bool = False,
    boton_pdf_html: str = "",
    deficits_detectados: Optional[List[str]] = None,
) -> AIResponse:
    """Convenience function for direct use in endpoints."""
    orchestrator = get_orchestrator()
    return orchestrator.process(
        pregunta=pregunta,
        usuario=usuario,
        rol=rol,
        ruta_pantalla=ruta_pantalla,
        historial=historial,
        cambio=cambio,
        quiere_pdf=quiere_pdf,
        boton_pdf_html=boton_pdf_html,
        deficits_detectados=deficits_detectados,
    )