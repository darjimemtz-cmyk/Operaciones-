"""
Tools Layer & Registry - FNG San Luis Potosí
Central tool registry with @tool decorator for deterministic, fast function calls.
Latency target: < 1.5s per tool execution.
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, get_type_hints
import inspect
import time
import logging

logger = logging.getLogger(__name__)

# Global tool registry
_tool_registry: Dict[str, Dict[str, Any]] = {}


def tool(
    name: Optional[str] = None,
    description: str = "",
    category: str = "general",
    timeout: float = 1.5,
    cache_ttl: int = 30,
) -> Callable:
    """
    Decorator to register a function as a tool.
    
    Args:
        name: Tool name (defaults to function name)
        description: Human-readable description for LLM/function calling
        category: Category for grouping (dot, hr, flota, general)
        timeout: Max execution time in seconds (target < 1.5s)
        cache_ttl: Cache TTL in seconds for deterministic responses
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        # Build parameter schema
        params = {}
        for param_name, param in sig.parameters.items():
            param_type = type_hints.get(param_name, Any)
            params[param_name] = {
                "type": _python_type_to_json(param_type),
                "description": f"Parameter {param_name}",
                "required": param.default == inspect.Parameter.empty,
            }
        
        # Return type
        return_type = type_hints.get("return", Any)
        
        tool_def = {
            "name": tool_name,
            "description": description or func.__doc__ or "",
            "category": category,
            "timeout": timeout,
            "cache_ttl": cache_ttl,
            "function": func,
            "parameters": params,
            "returns": _python_type_to_json(return_type),
        }
        
        _tool_registry[tool_name] = tool_def
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                if elapsed > timeout:
                    logger.warning(f"Tool {tool_name} took {elapsed:.3f}s (timeout: {timeout}s)")
                return result
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                raise
        
        # Attach metadata to wrapper
        wrapper._tool_def = tool_def
        return wrapper
    
    return decorator


def _python_type_to_json(py_type: Any) -> str:
    """Convert Python type to JSON schema type string."""
    type_map = {
        int: "integer",
        float: "number",
        str: "string",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }
    # Handle Optional[X] -> X
    if hasattr(py_type, "__origin__"):
        if py_type.__origin__ is list:
            return "array"
        if py_type.__origin__ is dict:
            return "object"
        if py_type.__origin__ is tuple:
            return "array"
    return type_map.get(py_type, "string")


def get_tool(name: str) -> Optional[Callable]:
    """Get a registered tool by name."""
    entry = _tool_registry.get(name)
    return entry["function"] if entry else None


def get_tool_def(name: str) -> Optional[Dict[str, Any]]:
    """Get tool definition (metadata) by name."""
    return _tool_registry.get(name)


def list_tools(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all registered tools, optionally filtered by category."""
    tools = []
    for entry in _tool_registry.values():
        if category is None or entry["category"] == category:
            tools.append({
                "name": entry["name"],
                "description": entry["description"],
                "category": entry["category"],
                "parameters": entry["parameters"],
                "returns": entry["returns"],
            })
    return tools


def get_categories() -> List[str]:
    """Get all tool categories."""
    return sorted(set(entry["category"] for entry in _tool_registry.values()))


def call_tool(name: str, **kwargs) -> Any:
    """
    Call a tool by name with keyword arguments.
    Used for dynamic invocation (e.g., from LLM function calling).
    """
    tool_fn = get_tool(name)
    if not tool_fn:
        raise ValueError(f"Tool not found: {name}")
    return tool_fn(**kwargs)


# Initialize logging
logging.basicConfig(level=logging.INFO)

# Import all tool modules to register them
from services.tools import dot_tools  # noqa: F401
from services.tools import hr_tools  # noqa: F401
from services.tools import flota_tools  # noqa: F401

__all__ = [
    "tool",
    "get_tool",
    "get_tool_def",
    "list_tools",
    "get_categories",
    "call_tool",
]