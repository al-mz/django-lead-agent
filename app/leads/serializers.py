from rest_framework import serializers
from agents.models import AgentAuditLog
from leads.models import Lead


class AgentAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentAuditLog
        fields = ["id", "tool_name", "tool_input", "duration_ms", "logged_at"]


class LeadCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ["id", "name", "email", "company", "role", "message", "source", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]


class LeadDetailSerializer(serializers.ModelSerializer):
    audit_logs = AgentAuditLogSerializer(many=True, read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id", "name", "email", "company", "role", "message", "source",
            "status", "qualification_result", "routing_queue",
            "response_sla_deadline", "draft_reply",
            "audit_logs", "created_at", "updated_at",
        ]
