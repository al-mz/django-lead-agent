"""
Audit hooks for agent runs.

build_audit_hooks() is called by the Celery task with the content_type_id
and object_id of the domain object being processed (e.g. a Lead).
This keeps hooks.py domain-agnostic — it does not import from any domain app.
"""
import json
import time
from claude_agent_sdk import HookMatcher


def _serialize_tool_response(value) -> str | None:
    """Normalize tool_response (Any) to a JSON string for TextField storage."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)


def build_audit_hooks(content_type_id: int, object_id: str, run_id: str) -> dict:
    """
    Returns a hooks dict compatible with ClaudeAgentOptions.

    PreToolUse: records wall-clock start time per tool_use_id.
    PostToolUse: persists one AgentAuditLog row with duration_ms.
    """
    call_start_times: dict[str, int] = {}

    async def pre_tool(input_data: dict, tool_use_id: str, context: dict) -> dict:
        call_start_times[tool_use_id] = int(time.time() * 1000)
        return {}

    async def post_tool(input_data: dict, tool_use_id: str, context: dict) -> dict:
        from agents.models import AgentAuditLog

        duration = int(time.time() * 1000) - call_start_times.pop(
            tool_use_id, int(time.time() * 1000)
        )
        tool_name = input_data.get("tool_name", context.get("tool_name", "unknown"))

        await AgentAuditLog.objects.acreate(
            content_type_id=content_type_id,
            object_id=object_id,
            run_id=run_id,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            tool_input=input_data.get("tool_input", {}),
            tool_output=_serialize_tool_response(input_data.get("tool_response")),
            duration_ms=duration,
        )
        return {}

    return {
        "PreToolUse": [HookMatcher(matcher="mcp__leads__.*", hooks=[pre_tool])],
        "PostToolUse": [HookMatcher(matcher="mcp__leads__.*", hooks=[post_tool])],
    }
