"""
Management command: print a human-readable report of what the LeadQualificationAgent did.

Usage:
    python manage.py agent_report <lead_id>
    python manage.py agent_report <lead_id> --run-id <run_id>

Shows the tool call sequence (inputs + outputs), timing, and the final qualification
decision. Useful for debugging agent behaviour and understanding the agent's reasoning.
"""
import json
from django.core.management.base import BaseCommand, CommandError
from leads.models import Lead
from agents.models import AgentAuditLog


def _extract_tool_output(raw: str | None) -> object:
    """
    Parse the raw tool_response string from the SDK into a Python object.

    MCP tools return {"content": [{"type": "text", "text": "<json>"}]}.
    The SDK may give us the full envelope {"content": [...]} or just the
    stripped content list [...]. We handle both and parse the inner JSON text.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw

    # Normalise: accept {"content": [...]} envelope or bare [...] list of blocks
    content_items = None
    if isinstance(parsed, dict) and "content" in parsed:
        content_items = parsed["content"]
    elif (
        isinstance(parsed, list)
        and parsed
        and isinstance(parsed[0], dict)
        and parsed[0].get("type") in ("text", "image", "resource")
    ):
        content_items = parsed

    if content_items:
        texts = []
        for item in content_items:
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    texts.append(json.loads(item["text"]))
                except (json.JSONDecodeError, TypeError):
                    texts.append(item["text"])
        if len(texts) == 1:
            return texts[0]
        if texts:
            return texts

    return parsed


def _format_tool_output(tool_name: str, output: object) -> str:
    """
    Produce a concise, readable summary of a tool's output.
    Falls back to pretty-printed JSON for unknown tools.
    """
    if output is None:
        return "(no output recorded — run agent_report after upgrading to capture outputs)"

    if tool_name == "mcp__leads__GetCRMHistory":
        if isinstance(output, dict):
            count = output.get("contact_count", 0)
            contacts = output.get("contacts", [])
            if count == 0:
                return f"No contacts found for domain {output.get('domain', '?')}"
            lines = [f"{count} contact(s) at {output.get('domain', '?')}:"]
            for c in contacts:
                lines.append(f"    · {c.get('name', '?')} ({c.get('role', '?')})")
                if c.get("notes"):
                    lines.append(f"      Notes: {c['notes'][:100]}")
            return "\n".join(lines)

    elif tool_name == "mcp__leads__SearchProductInfo":
        if isinstance(output, list):
            if not output:
                return "No matching product info found"
            lines = [f"{len(output)} article(s) found:"]
            for a in output:
                lines.append(f"    · {a.get('title', '?')} (id: {str(a.get('id', '?'))[:8]}…)")
            return "\n".join(lines)

    elif tool_name == "mcp__leads__WebSearch":
        if isinstance(output, list):
            lines = [f"{len(output)} result(s):"]
            for r in output:
                lines.append(f"    · {r.get('title', '?')} — {r.get('url', '?')[:60]}")
            return "\n".join(lines)
        if isinstance(output, dict) and "error" in output:
            return f"Error: {output['error']}"

    # Fallback: pretty-print whatever we have
    try:
        return json.dumps(output, indent=4, default=str)
    except Exception:
        return str(output)


def _format_tool_input(tool_name: str, tool_input: dict) -> str:
    if not tool_input:
        return "(no args)"
    parts = []
    for k, v in tool_input.items():
        if isinstance(v, list):
            parts.append(f"{k}=[{', '.join(repr(x) for x in v)}]")
        else:
            parts.append(f"{k}={v!r}")
    return ", ".join(parts)


DIVIDER = "=" * 60
SECTION  = "-" * 60


class Command(BaseCommand):
    help = "Print a human-readable agent run report for a lead"

    def add_arguments(self, parser):
        parser.add_argument("lead_id", help="UUID of the lead to inspect")
        parser.add_argument(
            "--run-id",
            default=None,
            help="Specific run_id to show (default: latest run for the lead)",
        )

    def handle(self, *args, **options):
        lead_id = options["lead_id"]
        run_id_filter = options["run_id"]

        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            raise CommandError(f"Lead {lead_id!r} not found")

        logs_qs = AgentAuditLog.objects.filter(
            object_id=lead_id
        ).order_by("logged_at")
        if run_id_filter:
            logs_qs = logs_qs.filter(run_id=run_id_filter)

        logs = list(logs_qs)
        if not logs:
            raise CommandError(
                f"No audit logs found for lead {lead_id}"
                + (f" and run {run_id_filter}" if run_id_filter else "")
            )

        # If multiple runs exist (retries), default to the latest
        run_ids = list(dict.fromkeys(str(log.run_id) for log in logs))
        if not run_id_filter and len(run_ids) > 1:
            self.stdout.write(
                f"\nNote: {len(run_ids)} run(s) found. Showing latest. "
                f"Use --run-id to pick a specific run.\n"
                f"Available: {', '.join(run_ids)}\n"
            )
            active_run_id = run_ids[-1]
            logs = [log for log in logs if str(log.run_id) == active_run_id]
        else:
            active_run_id = run_ids[0]

        qr = lead.qualification_result or {}

        # ── Header ───────────────────────────────────────────────────────────
        self.stdout.write(DIVIDER)
        self.stdout.write("AGENT RUN REPORT")
        self.stdout.write(DIVIDER)

        # ── Lead ─────────────────────────────────────────────────────────────
        self.stdout.write("\nLEAD")
        self.stdout.write(f"  ID:       {lead.id}")
        self.stdout.write(f"  Name:     {lead.name}")
        self.stdout.write(f"  Email:    {lead.email}")
        self.stdout.write(f"  Company:  {lead.company}")
        self.stdout.write(f"  Role:     {lead.role or '(not specified)'}")
        self.stdout.write(f"  Message:\n    {lead.message[:300]}")
        if len(lead.message) > 300:
            self.stdout.write("    [… truncated]")
        self.stdout.write(f"  Created:  {lead.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # ── Run metadata ─────────────────────────────────────────────────────
        total_tool_ms = sum(log.duration_ms or 0 for log in logs)
        self.stdout.write(f"\nRUN")
        self.stdout.write(f"  Run ID:     {active_run_id}")
        self.stdout.write(f"  Status:     {lead.status}")
        self.stdout.write(f"  Turns:      {qr.get('turns', '?')}")
        self.stdout.write(f"  Total time: {qr.get('duration_ms', '?')} ms")
        self.stdout.write(f"  Tool time:  {total_tool_ms} ms")

        # ── Tool calls ───────────────────────────────────────────────────────
        self.stdout.write(f"\nTOOL CALLS ({len(logs)})")
        self.stdout.write(SECTION)

        for i, log in enumerate(logs, 1):
            short_name = log.tool_name.split("__")[-1]
            duration = f"{log.duration_ms}ms" if log.duration_ms is not None else "?ms"
            self.stdout.write(f"\n  {i}. {short_name:<30} [{duration}]")
            self.stdout.write(f"     Input:  {_format_tool_input(log.tool_name, log.tool_input)}")
            output = _extract_tool_output(log.tool_output)
            formatted = _format_tool_output(log.tool_name, output)
            output_lines = formatted.splitlines()
            self.stdout.write(f"     Output: {output_lines[0]}")
            for line in output_lines[1:]:
                self.stdout.write(f"             {line}")

        # ── Qualification result ──────────────────────────────────────────────
        self.stdout.write(f"\n{SECTION}")
        self.stdout.write("QUALIFICATION RESULT")
        self.stdout.write(SECTION)

        if not qr:
            self.stdout.write("  (no qualification result stored)")
        else:
            conf = qr.get("confidence", {})
            self.stdout.write(f"  ICP Score:   {qr.get('icp_score', '?'):.2f}")
            self.stdout.write(f"  Tier:        {qr.get('tier', '?')}")
            self.stdout.write(
                f"  Confidence:  icp_fit={conf.get('icp_fit', '?')}  "
                f"urgency={conf.get('urgency', '?')}  "
                f"draft_reply={conf.get('draft_reply', '?')}"
            )
            self.stdout.write(f"  Overall confidence: {qr.get('overall_confidence', '?')}")
            self.stdout.write(f"  Routing queue: {lead.routing_queue or '?'}")

            sla = lead.response_sla_deadline
            self.stdout.write(
                f"  SLA deadline: "
                + (sla.strftime("%Y-%m-%d %H:%M UTC") if sla else "not set")
            )

            match_reasons = qr.get("icp_match_reasons", [])
            if match_reasons:
                self.stdout.write(f"  ICP match:   {', '.join(match_reasons)}")

            gap_reasons = qr.get("icp_gap_reasons", [])
            if gap_reasons:
                self.stdout.write(f"  ICP gaps:    {', '.join(gap_reasons)}")

            flags = qr.get("ambiguity_flags", [])
            if flags:
                self.stdout.write("  Ambiguity flags:")
                for flag in flags:
                    self.stdout.write(
                        f"    · [{flag.get('field')}] {flag.get('description')}"
                    )
                    alts = flag.get("alternatives", [])
                    if alts:
                        self.stdout.write(f"      Alternatives: {', '.join(alts)}")

            self.stdout.write(f"\n  Draft reply:")
            draft = qr.get("draft_reply", "")
            for line in draft.splitlines():
                self.stdout.write(f"    {line}")

            self.stdout.write(f"\n  Model:  {qr.get('model_id', '?')}")
            self.stdout.write(f"  Source: {qr.get('source', '?')}")

        self.stdout.write(f"\n{DIVIDER}\n")
