"""
Audit hooks for agent runs.

build_audit_hooks() is called by the Celery task with the content_type_id
and object_id of the domain object being processed (e.g. a Lead).
This keeps hooks.py domain-agnostic — it does not import from any domain app.

Set AGENT_VERBOSE=true in the environment to enable live terminal output
of tool calls and results during agent runs (useful for demos and debugging).
"""
import json
import os
import time

from claude_agent_sdk import HookMatcher
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

_console = Console(highlight=False, force_terminal=True)
_VERBOSE = os.environ.get("AGENT_VERBOSE", "").lower() in ("1", "true", "yes")


def _short_tool_name(tool_name: str) -> str:
    """Strip MCP server prefix (e.g. mcp__leads__GetCRMHistory → GetCRMHistory)."""
    parts = tool_name.split("__")
    return parts[-1] if len(parts) >= 3 else tool_name


def _tool_input_summary(tool_input: dict) -> str:
    """Compact single-line representation of tool input for terminal display."""
    try:
        return json.dumps(tool_input, separators=(", ", "="))[1:-1]
    except (TypeError, ValueError):
        return str(tool_input)


def _response_preview(tool_response) -> str:
    """Extract a short readable preview from a tool response."""
    if tool_response is None:
        return ""
    # SDK delivers tool response as a list of content blocks: [{"type": "text", "text": "..."}]
    if isinstance(tool_response, list):
        blocks = tool_response
    elif isinstance(tool_response, dict):
        blocks = tool_response.get("content", [])
    else:
        text = str(tool_response).strip()
        return text[:120] + "…" if len(text) > 120 else text

    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "").strip()
            return text[:120] + "…" if len(text) > 120 else text

    return str(tool_response)[:120]


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

    When AGENT_VERBOSE=true, also prints live tool call progress to the terminal.
    """
    call_start_times: dict[str, int] = {}

    async def pre_tool(input_data: dict, tool_use_id: str, context: dict) -> dict:
        call_start_times[tool_use_id] = int(time.time() * 1000)
        if _VERBOSE:
            tool_name = _short_tool_name(input_data.get("tool_name", context.get("tool_name", "unknown")))
            summary = _tool_input_summary(input_data.get("tool_input", {}))
            _console.print(f"[green bold] TOOL [/green bold]  {tool_name}  [dim]{summary}[/dim]")
        return {}

    async def post_tool(input_data: dict, tool_use_id: str, context: dict) -> dict:
        from agents.models import AgentAuditLog

        duration = int(time.time() * 1000) - call_start_times.pop(
            tool_use_id, int(time.time() * 1000)
        )
        tool_name = input_data.get("tool_name", context.get("tool_name", "unknown"))

        if _VERBOSE:
            preview = _response_preview(input_data.get("tool_response"))
            _console.print(
                f"[blue bold] DONE [/blue bold]  {_short_tool_name(tool_name)}  [dim]{duration}ms[/dim]  {preview}"
            )

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


def agent_start(email: str) -> None:
    """Print a start banner to the terminal. No-op when AGENT_VERBOSE is off."""
    if not _VERBOSE:
        return
    _console.print(Rule(style="dim"))
    _console.print(f"[red bold] AGENT [/red bold]  Qualifying: [bold]{email}[/bold]")
    _console.print(Rule(style="dim"))


def agent_think(text: str) -> None:
    """Print Claude's reasoning text as it arrives. No-op when AGENT_VERBOSE is off."""
    if not _VERBOSE:
        return
    text = text.strip()
    if text:
        _console.print(f"[magenta bold] THINK [/magenta bold]  [dim]{text}[/dim]")


def agent_result(tier: str, score: float, queue: str, duration_ms: int, cost_usd: float | None) -> None:
    """Print the final qualification result. No-op when AGENT_VERBOSE is off."""
    if not _VERBOSE:
        return
    cost_str = f"  ${cost_usd:.4f}" if cost_usd is not None else ""
    _console.print(Rule(style="dim"))
    _console.print(
        f"[yellow bold] RESULT [/yellow bold]  tier=[bold]{tier}[/bold]"
        f"  score=[bold]{score}[/bold]"
        f"  queue=[bold]{queue}[/bold]"
        f"  [dim]{duration_ms / 1000:.1f}s{cost_str}[/dim]"
    )
    _console.print(Rule(style="dim"))


def agent_draft(draft_reply: str) -> None:
    """Print the draft reply in a panel. No-op when AGENT_VERBOSE is off."""
    if not _VERBOSE:
        return
    _console.print(Panel(
        draft_reply.strip(),
        title="[cyan bold] DRAFT REPLY [/cyan bold]",
        border_style="cyan",
        padding=(1, 2),
    ))
