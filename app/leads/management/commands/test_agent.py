"""
Management command: test the LeadQualificationAgent standalone (without Celery).

Usage:
    python manage.py test_agent
    python manage.py test_agent --email john@acme.com --name "John Smith" --company "Acme Corp"
    python manage.py test_agent --message "We need help automating our invoicing workflow"
"""
import asyncio
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the LeadQualificationAgent standalone on a test lead (no Celery)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            default="Sarah Chen",
            help="Lead's full name",
        )
        parser.add_argument(
            "--email",
            default="sarah.chen@meridian-ops.com",
            help="Lead's email address",
        )
        parser.add_argument(
            "--company",
            default="Meridian Operations",
            help="Lead's company name",
        )
        parser.add_argument(
            "--role",
            default="Head of Operations",
            help="Lead's role/title",
        )
        parser.add_argument(
            "--message",
            default=(
                "Hi, we're a 120-person logistics company and we're drowning in manual "
                "approval workflows. Right now it takes 3-4 days to get a purchase order "
                "approved because it bounces between email threads. We process about 200 "
                "POs per month and it's becoming a real bottleneck as we scale. "
                "I saw your product mentioned in a blog post about workflow automation — "
                "does your platform handle multi-step approval chains with conditional routing? "
                "We'd love a demo if so."
            ),
            help="Lead's inquiry message",
        )
        parser.add_argument(
            "--source",
            default="website",
            help="Lead source (e.g. website, referral)",
        )

    def handle(self, *args, **options):
        from leads.models import Lead, AgentConfig
        from agents.lead_agent import run_lead_agent
        from leads.tasks import _apply_routing_rules
        from django.contrib.contenttypes.models import ContentType

        try:
            config = AgentConfig.objects.get(is_active=True)
        except AgentConfig.DoesNotExist:
            self.stderr.write(
                "No active AgentConfig found. "
                "Run: docker-compose exec web python scripts/seed_data.py first."
            )
            return

        # Create a real lead in the DB (status=new, signal will NOT fire
        # because test_agent calls run_lead_agent directly)
        lead = Lead.objects.create(
            name=options["name"],
            email=options["email"],
            company=options["company"],
            role=options["role"],
            message=options["message"],
            source=options["source"],
            status=Lead.Status.QUALIFYING,  # skip signal — we run the agent directly below
        )
        self.stdout.write(f"Created lead: {lead.id}")
        self.stdout.write(f"Lead: {lead.name} <{lead.email}> — {lead.company}")
        self.stdout.write(f"Config: {config.name}")
        self.stdout.write("Running LeadQualificationAgent...\n")

        content_type_id = ContentType.objects.get_for_model(Lead).id

        result = asyncio.run(
            run_lead_agent(
                lead_id=str(lead.id),
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

        routing_queue, sla_deadline = _apply_routing_rules(qual_dict)

        final_status = (
            Lead.Status.QUALIFIED
            if qual_dict.get("tier") != "cold"
            else Lead.Status.DISQUALIFIED
        )

        Lead.objects.filter(id=lead.id).update(
            qualification_result=qual_dict,
            routing_queue=routing_queue,
            response_sla_deadline=sla_deadline,
            draft_reply=qual_dict.get("draft_reply", ""),
            status=final_status,
        )

        lead.refresh_from_db()
        self.stdout.write(f"\nAgent completed in {result['turns']} turns, {result['duration_ms']}ms")
        self.stdout.write(f"Lead status: {lead.status}")
        self.stdout.write(f"Tier: {qual_dict.get('tier')} (ICP score: {qual_dict.get('icp_score')})")
        self.stdout.write(f"Routing queue: {routing_queue}")
        self.stdout.write(f"SLA deadline: {sla_deadline.strftime('%Y-%m-%d %H:%M UTC')}")
        self.stdout.write(f"Overall confidence: {qual_dict.get('overall_confidence')}")

        match_reasons = qual_dict.get("icp_match_reasons", [])
        if match_reasons:
            self.stdout.write(f"ICP match reasons: {', '.join(match_reasons)}")

        gap_reasons = qual_dict.get("icp_gap_reasons", [])
        if gap_reasons:
            self.stdout.write(f"ICP gap reasons: {', '.join(gap_reasons)}")

        flags = qual_dict.get("ambiguity_flags", [])
        if flags:
            self.stdout.write(f"Ambiguity flags:")
            for flag in flags:
                self.stdout.write(f"  [{flag.get('field')}] {flag.get('description')}")

        audit_logs = lead.audit_logs.all()
        self.stdout.write(f"\nAudit log entries: {audit_logs.count()}")
        for log in audit_logs:
            self.stdout.write(f"  {log.tool_name} — {log.duration_ms}ms")

        self.stdout.write(f"\nDraft reply:\n{qual_dict.get('draft_reply', '')}")
