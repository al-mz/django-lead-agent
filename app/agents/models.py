import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AgentAuditLog(models.Model):
    """
    One row per MCP tool call. Written by the PostToolUse hook.

    Uses a generic FK so this model works for any domain object
    (Lead, Contract, etc.) without schema changes.
    The domain model must add a GenericRelation for cascade delete and
    reverse queryset access.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Generic FK — points to any domain object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    run_id = models.UUIDField()
    tool_use_id = models.CharField(max_length=255)
    tool_name = models.CharField(max_length=255)
    tool_input = models.JSONField()
    tool_output = models.TextField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True)
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["logged_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id", "logged_at"]),
        ]

    def __str__(self):
        return f"{self.tool_name} @ {self.logged_at}"
