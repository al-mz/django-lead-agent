"""
Celery tasks for the leads app.

qualify_lead_task: Runs the LeadQualificationAgent for a new lead.
sweep_zombie_leads: Periodic task that marks stuck "qualifying" leads as failed.
"""
import asyncio
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


class AgentFailedError(Exception):
    """Raised when the agent completes without producing a qualification result."""


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def qualify_lead_task(self, lead_id: str):
    """
    Celery task: receives a new lead ID, runs the LeadQualificationAgent
    via asyncio.run().

    The MCP server (lead_server) is imported at module level by lead_agent —
    already initialized, no subprocess spawning, no cold start.

    Idempotent: if the lead is already qualified or disqualified, skip.
    """
    from leads.models import Lead, AgentConfig
    from agents.lead_agent import run_lead_agent
    from django.contrib.contenttypes.models import ContentType

    try:
        lead = Lead.objects.get(id=lead_id)

        if lead.status in (Lead.Status.QUALIFIED, Lead.Status.DISQUALIFIED):
            return

        lead.status = Lead.Status.QUALIFYING
        lead.save(update_fields=["status", "updated_at"])

        config = AgentConfig.objects.get(is_active=True)
        content_type_id = ContentType.objects.get_for_model(Lead).id

        result = asyncio.run(
            run_lead_agent(
                lead_id=lead_id,
                lead_name=lead.name,
                lead_email=lead.email,
                lead_company=lead.company,
                lead_role=lead.role,
                lead_message=lead.message,
                config=config,
                content_type_id=content_type_id,
            )
        )

        qual_dict = result["qualification_result"]
        qual_dict["turns"] = result["turns"]
        qual_dict["duration_ms"] = result["duration_ms"]
        qual_dict["total_cost_usd"] = result["total_cost_usd"]
        qual_dict["usage"] = result["usage"]

        # Apply invariants in-memory before DB write.
        # The DB never holds a state that violates routing rules.
        routing_queue, sla_deadline = _apply_routing_rules(qual_dict)

        final_status = (
            Lead.Status.QUALIFIED
            if qual_dict.get("tier") != "cold"
            else Lead.Status.DISQUALIFIED
        )

        Lead.objects.filter(id=lead_id).update(
            qualification_result=qual_dict,
            routing_queue=routing_queue,
            response_sla_deadline=sla_deadline,
            draft_reply=qual_dict.get("draft_reply", ""),
            status=final_status,
        )

        logger.info(
            "Lead qualified",
            extra={
                "lead_id": lead_id,
                "tier": qual_dict.get("tier"),
                "icp_score": qual_dict.get("icp_score"),
                "turns": result["turns"],
                "duration_ms": result["duration_ms"],
            },
        )

    except Exception as exc:
        logger.exception("Qualification failed", extra={"lead_id": lead_id})
        if self.request.retries >= self.max_retries:
            from leads.models import Lead as L
            L.objects.filter(id=lead_id).update(status=L.Status.FAILED)
            raise
        from leads.models import Lead as L
        L.objects.filter(id=lead_id).update(status=L.Status.NEW)
        raise self.retry(exc=exc)


def _apply_routing_rules(qual_dict: dict) -> tuple:
    """
    Pure function — no DB writes.

    Returns (routing_queue, sla_deadline) computed from the agent's
    in-memory result. The RoutingRule with the matching score range wins.
    Falls back to ("general", now + 24h) if no rule matches.

    Called before the DB write so invariants are enforced, not patched.
    """
    from leads.models import RoutingRule

    icp_score = qual_dict.get("icp_score", 0.0)

    rule = (
        RoutingRule.objects.filter(
            is_active=True,
            score_min__lte=icp_score,
            score_max__gte=icp_score,
        )
        .order_by("-score_min")
        .first()
    )

    if rule:
        queue = rule.queue_name
        sla_deadline = timezone.now() + timedelta(minutes=rule.response_sla_minutes)
    else:
        queue = qual_dict.get("routing_queue", "general")
        sla_deadline = timezone.now() + timedelta(hours=24)

    return queue, sla_deadline


@shared_task
def sweep_zombie_leads():
    """
    Periodic task (every 10 minutes via Celery beat).

    Leads that enter "qualifying" and never exit — due to worker OOM-kill
    or node termination — are surfaced as "failed".
    """
    from leads.models import Lead

    cutoff = timezone.now() - timedelta(minutes=10)
    swept = Lead.objects.filter(
        status=Lead.Status.QUALIFYING,
        updated_at__lt=cutoff,
    ).update(status=Lead.Status.FAILED)

    if swept:
        logger.warning("Swept zombie leads", extra={"count": swept})
    return swept
