from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.html import format_html
import json

from agents.models import AgentAuditLog
from leads.models import AgentConfig, Contact, ProductInfo, RoutingRule, Lead


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    list_display = ["name", "company_name", "is_active", "updated_at"]
    list_filter = ["is_active"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "is_active", "company_name"]}),
        ("Agent Context (fed into system prompt)", {
            "fields": ["company_description", "ideal_customer_description",
                       "disqualifying_signals", "scoring_guidance"],
        }),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "company", "role", "created_at"]
    search_fields = ["name", "email", "company"]
    readonly_fields = ["email_domain", "created_at"]


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ["title", "created_at"]
    search_fields = ["title", "content"]


@admin.register(RoutingRule)
class RoutingRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "score_min", "score_max", "queue_name", "response_sla_minutes", "is_active"]
    list_filter = ["is_active"]


class AgentAuditLogInline(GenericTabularInline):
    """Compact audit log inline — raw rows for reference."""
    model = AgentAuditLog
    ct_field = "content_type"
    ct_fk_field = "object_id"
    extra = 0
    readonly_fields = ["tool_name", "tool_input", "tool_output", "duration_ms", "logged_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


def _render_reasoning_timeline(lead) -> str:
    """
    Render the agent's tool-call sequence as a human-readable HTML timeline.
    Returns an HTML string suitable for format_html wrapping.

    Used as a readonly field in LeadAdmin — this is the demo centrepiece.
    """
    logs = list(lead.audit_logs.order_by("logged_at"))
    if not logs:
        return "<p style='color:#999'>No tool calls recorded for this lead.</p>"

    rows = []
    for i, log in enumerate(logs, 1):
        short_name = log.tool_name.split("__")[-1]
        duration = f"{log.duration_ms}ms" if log.duration_ms is not None else "?"

        try:
            input_str = json.dumps(log.tool_input, indent=2)
        except Exception:
            input_str = str(log.tool_input)

        output_str = "—"
        if log.tool_output:
            try:
                parsed = json.loads(log.tool_output)
                # Unwrap MCP content envelope if present
                if isinstance(parsed, dict) and "content" in parsed:
                    items = parsed["content"]
                elif isinstance(parsed, list):
                    items = parsed
                else:
                    items = None
                if items:
                    texts = []
                    for item in items:
                        if isinstance(item, dict) and item.get("type") == "text":
                            try:
                                texts.append(json.dumps(json.loads(item["text"]), indent=2))
                            except Exception:
                                texts.append(item["text"])
                    output_str = "\n".join(texts) if texts else json.dumps(parsed, indent=2)
                else:
                    output_str = json.dumps(parsed, indent=2)
            except Exception:
                output_str = log.tool_output[:1000]

        rows.append(
            f"<tr>"
            f"<td style='padding:8px;font-weight:bold;white-space:nowrap'>{i}. {short_name}</td>"
            f"<td style='padding:8px;color:#666;white-space:nowrap'>{duration}</td>"
            f"<td style='padding:8px'><pre style='margin:0;font-size:11px'>{input_str}</pre></td>"
            f"<td style='padding:8px'><pre style='margin:0;font-size:11px;max-height:150px;overflow:auto'>{output_str}</pre></td>"
            f"</tr>"
        )

    header = (
        "<table style='width:100%;border-collapse:collapse;font-size:13px'>"
        "<thead><tr style='background:#f8f8f8'>"
        "<th style='padding:8px;text-align:left'>Step</th>"
        "<th style='padding:8px;text-align:left'>Duration</th>"
        "<th style='padding:8px;text-align:left'>Input</th>"
        "<th style='padding:8px;text-align:left'>Output</th>"
        "</tr></thead><tbody>"
    )
    return header + "".join(rows) + "</tbody></table>"


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        "id", "name", "email", "company", "status",
        "tier_display", "icp_score_display", "routing_queue", "created_at",
    ]
    list_filter = ["status", "routing_queue"]
    search_fields = ["name", "email", "company"]
    readonly_fields = [
        "id", "created_at", "updated_at",
        "qualification_result_pretty",
        "reasoning_timeline",
    ]
    inlines = [AgentAuditLogInline]

    fieldsets = [
        (None, {"fields": ["id", "name", "email", "company", "role", "message", "source", "status"]}),
        ("Qualification Result", {
            "fields": [
                "routing_queue", "response_sla_deadline", "draft_reply",
                "qualification_result_pretty",
            ],
        }),
        ("Agent Reasoning Trace", {
            "fields": ["reasoning_timeline"],
            "classes": ["wide"],
        }),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]

    def tier_display(self, obj):
        if not obj.qualification_result:
            return "—"
        tier = obj.qualification_result.get("tier", "—")
        colors = {"hot": "#c00", "warm": "#e65c00", "cold": "#555"}
        color = colors.get(tier, "#000")
        return format_html("<span style='color:{};font-weight:bold'>{}</span>", color, tier)
    tier_display.short_description = "Tier"

    def icp_score_display(self, obj):
        if not obj.qualification_result:
            return "—"
        score = obj.qualification_result.get("icp_score")
        if score is None:
            return "—"
        return f"{score:.2f}"
    icp_score_display.short_description = "ICP Score"

    def qualification_result_pretty(self, obj):
        if not obj.qualification_result:
            return "—"
        formatted = json.dumps(obj.qualification_result, indent=2)
        return format_html(
            "<pre style='max-height:400px;overflow:auto;font-size:12px'>{}</pre>",
            formatted,
        )
    qualification_result_pretty.short_description = "Qualification Result (JSON)"

    def reasoning_timeline(self, obj):
        html = _render_reasoning_timeline(obj)
        return format_html("{}", html)
    reasoning_timeline.short_description = "Agent Reasoning Trace"


@admin.register(AgentAuditLog)
class AgentAuditLogAdmin(admin.ModelAdmin):
    list_display = ["content_object", "tool_name", "duration_ms", "logged_at"]
    list_filter = ["tool_name"]
    readonly_fields = [
        "content_type", "object_id", "run_id", "tool_use_id",
        "tool_name", "tool_input", "tool_output", "duration_ms", "logged_at",
    ]
