import uuid
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxLengthValidator
from django.db import models


class AgentConfig(models.Model):
    """
    Business-owner-defined context for the qualification agent.

    All text fields feed into the system prompt at runtime. Only one
    config is active at a time (is_active=True). The Celery task fetches
    AgentConfig.objects.get(is_active=True) before each run.

    Editable via Django admin — no code changes needed to update ICP or
    scoring guidance.
    """
    name = models.CharField(max_length=255, help_text="Display name for this config")
    is_active = models.BooleanField(
        default=False,
        help_text="Only one config may be active at a time.",
    )
    company_name = models.CharField(max_length=255)
    company_description = models.TextField(
        help_text="What your company does. Injected into the agent system prompt."
    )
    ideal_customer_description = models.TextField(
        help_text="Plain English description of your ideal customer. "
                  "The agent uses this to score leads."
    )
    disqualifying_signals = models.TextField(
        help_text="Signals that make a lead cold regardless of other factors. "
                  "E.g. 'Students, hobbyists, companies with fewer than 10 employees.'"
    )
    scoring_guidance = models.TextField(
        help_text="Additional scoring instructions. "
                  "E.g. 'Weight payment-related urgency higher than generic interest.'"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Agent Config"
        verbose_name_plural = "Agent Configs"

    def save(self, *args, **kwargs):
        # Enforce singleton: deactivate all other configs when this one is activated.
        if self.is_active:
            AgentConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        active = " [ACTIVE]" if self.is_active else ""
        return f"{self.name}{active}"


class Contact(models.Model):
    """
    Existing CRM contacts. Seeded manually or imported.

    The GetCRMHistory tool looks up contacts by email_domain (computed
    from email on save) to simulate "do we know anyone at this company?"
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    company = models.CharField(max_length=255)
    email_domain = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Derived from email on save. Used for domain-based CRM lookup.",
    )
    role = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.email_domain = self.email.split("@")[-1].lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} <{self.email}>"


class ProductInfo(models.Model):
    """
    Product/service documentation articles. Searched by the agent via keywords.

    The SearchProductInfo tool does keyword matching against this table.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=500)
    content = models.TextField()
    keywords = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class RoutingRule(models.Model):
    """
    Deterministic routing thresholds. Applied post-agent, before DB write.

    The _apply_routing_rules() function selects the first active rule where
    score_min <= icp_score <= score_max. If no rule matches, a fallback
    applies (queue="general", SLA=24h).

    Editable via Django admin. These are invariants — they must always hold
    regardless of what the agent returned.
    """
    name = models.CharField(max_length=100, help_text='E.g. "hot", "warm", "cold"')
    score_min = models.FloatField()
    score_max = models.FloatField()
    queue_name = models.CharField(max_length=255)
    response_sla_minutes = models.IntegerField(
        help_text="Minutes until first human touch is required."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-score_min"]  # match highest threshold first

    def __str__(self):
        return f"{self.name} ({self.score_min}–{self.score_max}) → {self.queue_name}"


class Lead(models.Model):
    """
    Inbound lead submission. Created via POST /api/leads/.

    Status flow: new → qualifying → qualified | disqualified | failed
    The Celery task owns all status transitions.
    """
    class Status(models.TextChoices):
        NEW = "new", "New"
        QUALIFYING = "qualifying", "Qualifying"
        QUALIFIED = "qualified", "Qualified"
        DISQUALIFIED = "disqualified", "Disqualified"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    company = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True)
    message = models.TextField(
        validators=[MaxLengthValidator(5000)],
        help_text="Max 5000 characters.",
    )
    source = models.CharField(max_length=100, blank=True, help_text='E.g. "website", "referral"')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)

    # Written by the Celery task after the agent completes
    qualification_result = models.JSONField(null=True, blank=True)
    routing_queue = models.CharField(max_length=255, null=True, blank=True)
    response_sla_deadline = models.DateTimeField(null=True, blank=True)
    draft_reply = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Reverse relation to AgentAuditLog (generic FK on the agents side).
    # This GenericRelation is what enables cascade delete and lead.audit_logs.all().
    audit_logs = GenericRelation(
        "agents.AgentAuditLog",
        content_type_field="content_type",
        object_id_field="object_id",
    )

    class Meta:
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.name} <{self.email}> — {self.company}"
