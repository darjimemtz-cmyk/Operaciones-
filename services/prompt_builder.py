"""
Prompt Builder service for structuring ERP operational context.
Separates System Prompt, User Query, and Dynamic Context with token control.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import json


@dataclass
class PromptContext:
    """Structured operational context for the ERP."""
    fleet_summary: Dict[str, Any] = field(default_factory=dict)
    dot_hours: Dict[str, Any] = field(default_factory=dict)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    additional: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BuiltPrompt:
    """Result of prompt building with metadata."""
    system_prompt: str
    user_prompt: str
    total_chars: int
    estimated_tokens: int
    context_used: PromptContext
    truncated: bool = False


class PromptBuilder:
    """
    Builds structured prompts for AI queries with ERP operational context.
    
    Token estimation: ~4 chars per token (conservative)
    Max context: configurable (default ~8000 chars = ~2000 tokens for context)
    """
    
    # System prompt template - fixed, not counted in dynamic budget
    SYSTEM_PROMPT = """Eres un asistente operativo especializado en gestión de flotas y cumplimiento DOT para una empresa de transporte.
Tu rol es proporcionar respuestas concisas, accionables y basadas estrictamente en los datos proporcionados.

REGLAS CRÍTICAS:
1. NUNCA inventes datos: si no está en el contexto, indícalo explícitamente.
2. Las ventanas DOT son de 7 días rodantes (no 8).
3. Instructores y movedores NUNCA aparecen en reportes DOT.
4. Las metas de horas son fijas por unidad activa.
5. Responde en español, tono profesional y directo.
6. Prioriza alertas críticas y riesgos de incumplimiento.
7. Formato: resumen ejecutivo → detalle accionable → recomendaciones."""

    # Section headers for structured context
    FLEET_HEADER = "=== RESUMEN DE FLOTA ==="
    DOT_HEADER = "=== HORAS DOT (VENTANA 7 DÍAS) ==="
    ALERTS_HEADER = "=== ALERTAS ACTIVAS ==="
    ADDITIONAL_HEADER = "=== CONTEXTO ADICIONAL ==="

    def __init__(
        self,
        max_context_chars: int = 8000,
        max_alerts: int = 10,
        max_fleet_units: int = 50
    ):
        """
        Initialize prompt builder with size limits.
        
        Args:
            max_context_chars: Maximum characters for dynamic context (default 8000)
            max_alerts: Maximum alerts to include (default 10)
            max_fleet_units: Maximum fleet units to detail (default 50)
        """
        self.max_context_chars = max_context_chars
        self.max_alerts = max_alerts
        self.max_fleet_units = max_fleet_units

    def build(
        self,
        context: PromptContext,
        user_query: str,
        include_system: bool = True
    ) -> BuiltPrompt:
        """
        Build complete prompt with system prompt, context, and user query.
        
        Args:
            context: Structured operational context
            user_query: User's question or request
            include_system: Whether to include system prompt
            
        Returns:
            BuiltPrompt with all components and metadata
        """
        # Build dynamic context sections
        context_parts = []
        truncated = False
        
        # Fleet summary section
        fleet_text = self._build_fleet_section(context.fleet_summary)
        if fleet_text:
            context_parts.append(fleet_text)
        
        # DOT hours section
        dot_text = self._build_dot_section(context.dot_hours)
        if dot_text:
            context_parts.append(dot_text)
        
        # Alerts section
        alerts_text = self._build_alerts_section(context.alerts)
        if alerts_text:
            context_parts.append(alerts_text)
        
        # Additional context
        additional_text = self._build_additional_section(context.additional)
        if additional_text:
            context_parts.append(additional_text)
        
        # Combine context with size control
        full_context = "\n\n".join(context_parts)
        full_context, was_truncated = self._truncate_context(full_context)
        truncated = truncated or was_truncated
        
        # Build user prompt with context
        user_prompt = self._build_user_prompt(full_context, user_query)
        
        # Calculate metrics
        total_chars = len(user_prompt)
        if include_system:
            total_chars += len(self.SYSTEM_PROMPT)
        estimated_tokens = total_chars // 4
        
        return BuiltPrompt(
            system_prompt=self.SYSTEM_PROMPT if include_system else "",
            user_prompt=user_prompt,
            total_chars=total_chars,
            estimated_tokens=estimated_tokens,
            context_used=context,
            truncated=truncated
        )

    def _build_fleet_section(self, fleet_data: Dict[str, Any]) -> str:
        """Build fleet summary section with unit limit."""
        if not fleet_data:
            return ""
        
        lines = [self.FLEET_HEADER]
        
        # Summary stats
        total_units = fleet_data.get("total_unidades", 0)
        active_units = fleet_data.get("unidades_activas", 0)
        lines.append(f"Total unidades: {total_units} | Activas: {active_units}")
        
        # Unit details (limited)
        unidades = fleet_data.get("unidades", [])
        if isinstance(unidades, list):
            for i, u in enumerate(unidades[:self.max_fleet_units]):
                if isinstance(u, dict):
                    unit_id = u.get("id", u.get("unidad", f"U{i+1}"))
                    status = u.get("estado", u.get("status", "N/A"))
                    conductor = u.get("conductor", u.get("driver", "Sin asignar"))
                    lines.append(f"  - {unit_id}: {status} | Conductor: {conductor}")
            if len(unidades) > self.max_fleet_units:
                lines.append(f"  ... y {len(unidades) - self.max_fleet_units} unidades más")
        
        return "\n".join(lines)

    def _build_dot_section(self, dot_data: Dict[str, Any]) -> str:
        """Build DOT hours section (7-day rolling window)."""
        if not dot_data:
            return ""
        
        lines = [self.DOT_HEADER]
        
        # Window info
        window_days = dot_data.get("ventana_dias", 7)
        lines.append(f"Ventana rodante: {window_days} días")
        
        # Compliance summary
        cumplimiento = dot_data.get("cumplimiento", {})
        if cumplimiento:
            lines.append(f"Cumplimiento: {cumplimiento.get('porcentaje', 'N/A')}%")
            lines.append(f"Unidades en riesgo: {cumplimiento.get('en_riesgo', 0)}")
            lines.append(f"Unidades cumpliendo: {cumplimiento.get('cumpliendo', 0)}")
        
        # Unit details
        detalles = dot_data.get("detalles", [])
        if isinstance(detalles, list):
            for d in detalles[:20]:  # Limit DOT details
                if isinstance(d, dict):
                    unit = d.get("unidad", d.get("id", "N/A"))
                    horas = d.get("horas", d.get("hours", 0))
                    meta = d.get("meta", d.get("target", 70))
                    estado = d.get("estado", d.get("status", "N/A"))
                    lines.append(f"  - {unit}: {horas}h / {meta}h meta | {estado}")
        
        return "\n".join(lines)

    def _build_alerts_section(self, alerts: List[Dict[str, Any]]) -> str:
        """Build alerts section with priority ordering and limit."""
        if not alerts:
            return ""
        
        # Sort by priority: critical > warning > info
        priority_order = {"critica": 0, "critical": 0, 
                          "warning": 1, "advertencia": 1,
                          "info": 2, "informativo": 2}
        
        def get_priority(a):
            p = str(a.get("prioridad", a.get("priority", "info"))).lower()
            return priority_order.get(p, 2)
        
        sorted_alerts = sorted(alerts, key=get_priority)
        
        lines = [self.ALERTS_HEADER]
        for alert in sorted_alerts[:self.max_alerts]:
            if isinstance(alert, dict):
                prioridad = alert.get("prioridad", alert.get("priority", "info")).upper()
                mensaje = alert.get("mensaje", alert.get("message", "Sin descripción"))
                unidad = alert.get("unidad", alert.get("unit", "N/A"))
                lines.append(f"  [{prioridad}] {unidad}: {mensaje}")
        
        if len(alerts) > self.max_alerts:
            lines.append(f"  ... y {len(alerts) - self.max_alerts} alertas más")
        
        return "\n".join(lines)

    def _build_additional_section(self, additional: Dict[str, Any]) -> str:
        """Build additional context section."""
        if not additional:
            return ""
        
        lines = [self.ADDITIONAL_HEADER]
        for key, value in additional.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)[:500]
            lines.append(f"  {key}: {value}")
        
        return "\n".join(lines)

    def _truncate_context(self, context: str) -> tuple[str, bool]:
        """Truncate context to max chars, preserving structure."""
        if len(context) <= self.max_context_chars:
            return context, False
        
        # Try to truncate at section boundaries
        sections = context.split("\n\n")
        result = []
        current_len = 0
        
        for section in sections:
            section_len = len(section) + 2  # +2 for \n\n
            if current_len + section_len > self.max_context_chars:
                # Try to fit partial section
                remaining = self.max_context_chars - current_len - 50  # buffer for notice
                if remaining > 100:
                    result.append(section[:remaining] + "\n  [TRUNCADO]")
                break
            result.append(section)
            current_len += section_len
        
        return "\n\n".join(result), True

    def _build_user_prompt(self, context: str, user_query: str) -> str:
        """Build final user prompt with context and query."""
        parts = []
        
        if context:
            parts.append("CONTEXTO OPERATIVO ACTUAL:")
            parts.append(context)
            parts.append("")  # blank line
        
        parts.append("CONSULTA DEL USUARIO:")
        parts.append(user_query)
        
        return "\n".join(parts)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (conservative: 4 chars per token)."""
        return len(text) // 4

    def get_system_prompt(self) -> str:
        """Get the fixed system prompt."""
        return self.SYSTEM_PROMPT

    def build_prompt(
        self,
        user_query: str,
        context_data: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> tuple[str, str]:
        """
        Build prompt with the requested interface.
        
        Args:
            user_query: User's question or request
            context_data: Optional dict with keys: fleet_summary, dot_hours, alerts, additional
            history: Optional conversation history as list of {role, content} dicts
            
        Returns:
            Tuple of (system_prompt, full_user_prompt)
        """
        # Convert context_data to PromptContext
        context = PromptContext()
        if context_data:
            context.fleet_summary = context_data.get("fleet_summary", {})
            context.dot_hours = context_data.get("dot_hours", {})
            context.alerts = context_data.get("alerts", [])
            context.additional = context_data.get("additional", {})
        
        # Build history context if provided
        history_text = ""
        if history:
            history_lines = ["=== HISTORIAL DE CONVERSACIÓN ==="]
            for msg in history[-5:]:  # Last 5 messages only
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_lines.append(f"  [{role.upper()}]: {content[:300]}")
            history_text = "\n".join(history_lines)
        
        # Use existing build method
        built = self.build(context, user_query, include_system=True)
        
        # Prepend history to user prompt if exists
        full_user_prompt = built.user_prompt
        if history_text:
            full_user_prompt = history_text + "\n\n" + full_user_prompt
        
        return (built.system_prompt, full_user_prompt)