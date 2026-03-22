#!/usr/bin/env python
"""
Seed the database with AgentConfig, ProductInfo, RoutingRules, Contacts,
and sample pre-qualified leads for demo purposes.

Usage:
    docker-compose exec web python scripts/seed_data.py
    # OR from project root:
    DJANGO_SETTINGS_MODULE=config.settings PYTHONPATH=app python scripts/seed_data.py

NOTE: Seed leads are created with pre-populated qualification results and
final statuses (QUALIFIED/DISQUALIFIED). They do NOT trigger the signal,
so no API credits are burned during setup.

Use `python manage.py test_agent` to run a live agent qualification.
"""
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from leads.models import AgentConfig, Contact, ProductInfo, RoutingRule, Lead  # noqa: E402


def seed():
    # ── 1. AgentConfig (one active) ─────────────────────────────────────────
    config, created = AgentConfig.objects.get_or_create(
        name="Flowline v1",
        defaults={
            "is_active": True,
            "company_name": "Flowline",
            "company_description": (
                "Flowline is a B2B workflow automation platform that helps operations "
                "teams at mid-market companies replace manual approval processes, "
                "vendor onboarding, and cross-department handoffs with automated, "
                "rule-based workflows. Our platform integrates with Slack, email, "
                "ERP systems, and document management tools. Typical customers process "
                "50–500 workflows per month and see a 60–80% reduction in approval cycle time."
            ),
            "ideal_customer_description": (
                "Our ideal customer is an operations, finance, or IT leader at a B2B company "
                "with 20–500 employees. They are struggling with manual, email-based approval "
                "chains, document collection bottlenecks, or cross-team handoff delays. "
                "Industries that fit best: manufacturing, logistics, professional services, "
                "healthcare (non-clinical), construction, and SaaS companies with complex "
                "procurement or vendor processes. "
                "Decision indicators: company processes 30+ workflows/month manually, "
                "has experienced deal delays or compliance issues due to slow approvals, "
                "and has budget allocated for operations tooling. "
                "Company size sweet spot: 25–300 employees."
            ),
            "disqualifying_signals": (
                "Students, hobbyists, or personal projects. "
                "Solo freelancers or companies with fewer than 10 employees. "
                "B2C companies (e.g. e-commerce stores, consumer apps). "
                "Companies that only want a free tool or proof-of-concept without budget. "
                "Requests for features outside our roadmap (e.g. AI code generation, "
                "CRM functionality, or HR payroll processing). "
                "Competitors researching our product."
            ),
            "scoring_guidance": (
                "Weight urgency signals heavily: phrases like 'bottleneck', 'blocking', "
                "'losing deals', 'compliance issue', or 'can't scale' indicate active pain. "
                "Company size matters: 25–300 employees is the sweet spot. "
                "A specific use case (e.g. 'purchase order approvals', 'vendor onboarding') "
                "scores higher than a vague 'interested in automation'. "
                "Prior CRM contacts at the company significantly increase confidence — "
                "treat existing relationships as a strong warm signal. "
                "If the company is large (>500 employees), flag for enterprise sales team. "
                "If the message mentions a specific integration need, check ProductInfo "
                "for compatibility before scoring."
            ),
        },
    )
    if config.is_active is False:
        config.is_active = True
        config.save()
    if created:
        print(f"  Created AgentConfig: {config.name}")
    else:
        print(f"  AgentConfig already exists: {config.name}")

    # ── 2. ProductInfo entries ───────────────────────────────────────────────
    articles = [
        {
            "title": "Flowline Approval Workflow Engine",
            "content": (
                "Flowline's approval workflow engine supports multi-step, conditional "
                "approval chains with parallel and sequential routing. Configure approval "
                "rules based on amount thresholds, department, vendor category, or custom "
                "fields. Supports escalation when approvers don't respond within SLA. "
                "Integrates with Slack and email for approver notifications. "
                "All decisions are logged with timestamps for audit compliance. "
                "Typical deployment: purchase order approvals, budget requests, "
                "vendor onboarding sign-offs, contract reviews."
            ),
            "keywords": ["approval", "workflow", "purchase order", "PO", "multi-step", "conditional", "routing", "escalation"],
        },
        {
            "title": "Vendor Onboarding Automation",
            "content": (
                "Automate the end-to-end vendor onboarding process: collect W-9 and insurance "
                "documents, route for compliance review, trigger ERP vendor creation, and "
                "send welcome communications. Flowline tracks document expiry and sends "
                "renewal reminders automatically. Integrations available with SAP, NetSuite, "
                "QuickBooks, and Coupa. Average customer reduces vendor onboarding from 2 weeks "
                "to 2 days. Supports conditional paths (e.g. international vendors require "
                "additional compliance checks)."
            ),
            "keywords": ["vendor", "onboarding", "document", "compliance", "W-9", "insurance", "ERP", "SAP", "NetSuite", "QuickBooks"],
        },
        {
            "title": "Flowline Pricing and Plans",
            "content": (
                "Starter plan: $299/month, up to 5 users, 100 workflow runs/month. "
                "Growth plan: $799/month, up to 20 users, 500 workflow runs/month, "
                "includes Slack and email integrations. "
                "Scale plan: $1,999/month, unlimited users, unlimited workflow runs, "
                "ERP integrations, custom SLA enforcement, priority support. "
                "Enterprise: custom pricing for 300+ employee companies, includes "
                "dedicated CSM, SSO, on-premise deployment option, and SLA guarantees. "
                "All plans include a 14-day free trial. No credit card required for trial."
            ),
            "keywords": ["pricing", "plan", "cost", "price", "trial", "enterprise", "starter", "growth", "scale"],
        },
        {
            "title": "Integrations and API",
            "content": (
                "Flowline integrates natively with: Slack, Microsoft Teams, Gmail, "
                "Outlook, DocuSign, Adobe Sign, Box, SharePoint, Salesforce, HubSpot, "
                "SAP, NetSuite, QuickBooks, Xero, Coupa, and Jira. "
                "REST API available on Growth and Scale plans for custom integrations. "
                "Webhook support for real-time event notifications. "
                "Zapier integration available for no-code connections to 5000+ apps. "
                "SSO via SAML 2.0 (Okta, Azure AD, Google Workspace) on Enterprise plan."
            ),
            "keywords": ["integration", "API", "Slack", "Teams", "DocuSign", "Salesforce", "HubSpot", "webhook", "Zapier", "SSO"],
        },
        {
            "title": "Compliance and Audit Trail",
            "content": (
                "Every workflow action in Flowline is logged with user, timestamp, "
                "IP address, and decision rationale. Audit logs are immutable and "
                "exportable in CSV or JSON format. "
                "Supports SOC 2 Type II compliance workflows out of the box. "
                "Role-based access control (RBAC) with granular permissions. "
                "Data retention configurable from 1 to 7 years. "
                "GDPR-compliant with EU data residency option. "
                "Useful for: procurement compliance, financial controls (SOX), "
                "healthcare vendor credentialing (HIPAA-adjacent workflows)."
            ),
            "keywords": ["compliance", "audit", "SOC 2", "GDPR", "HIPAA", "SOX", "security", "access control", "RBAC", "retention"],
        },
    ]
    for article_data in articles:
        _, created = ProductInfo.objects.get_or_create(
            title=article_data["title"], defaults=article_data
        )
        if created:
            print(f"  Created ProductInfo: {article_data['title'][:60]}")

    # ── 3. RoutingRule entries ───────────────────────────────────────────────
    rules = [
        {
            "name": "hot",
            "score_min": 0.75,
            "score_max": 1.0,
            "queue_name": "senior-sales",
            "response_sla_minutes": 15,
            "is_active": True,
        },
        {
            "name": "warm",
            "score_min": 0.40,
            "score_max": 0.74,
            "queue_name": "sales-team",
            "response_sla_minutes": 120,
            "is_active": True,
        },
        {
            "name": "cold",
            "score_min": 0.00,
            "score_max": 0.39,
            "queue_name": "nurture",
            "response_sla_minutes": 1440,
            "is_active": True,
        },
    ]
    for rule_data in rules:
        _, created = RoutingRule.objects.get_or_create(
            name=rule_data["name"], defaults=rule_data
        )
        if created:
            print(f"  Created RoutingRule: {rule_data['name']}")

    # ── 4. CRM Contacts (for Scenario 2 — warm lead with history) ───────────
    # These contacts are at apex-logistics.com.
    # Scenario 2 seed lead uses the same domain so GetCRMHistory returns results.
    contacts = [
        {
            "name": "Marcus Webb",
            "email": "marcus.webb@apex-logistics.com",
            "company": "Apex Logistics",
            "role": "VP of Operations",
            "notes": (
                "Attended our webinar on procurement automation in Jan 2026. "
                "Very engaged — asked detailed questions about ERP integration. "
                "Mentioned they're on NetSuite and struggling with PO approval delays."
            ),
        },
        {
            "name": "Priya Nair",
            "email": "priya.nair@apex-logistics.com",
            "company": "Apex Logistics",
            "role": "Procurement Manager",
            "notes": (
                "Connected via LinkedIn after the webinar. Said their current process "
                "involves 5-day approval cycles via email. Budget conversation in Q2."
            ),
        },
    ]
    for contact_data in contacts:
        _, created = Contact.objects.get_or_create(
            email=contact_data["email"], defaults=contact_data
        )
        if created:
            print(f"  Created Contact: {contact_data['name']} ({contact_data['company']})")

    # ── 5. Seed leads (pre-qualified, won't trigger signal) ──────────────────
    #
    # These are demonstration leads in final state. They show up in admin
    # with realistic qualification results.
    # DO NOT use status=NEW — that would trigger the signal and burn API credits.

    from django.utils import timezone
    from datetime import timedelta
    now = timezone.now()

    seed_leads = [
        # ── Scenario 1: Cold lead — no CRM history, thin message ──────────────
        {
            "name": "Jake Morrison",
            "email": "jake.morrison@personal-blog.net",
            "company": "Personal Blog",
            "role": "Blogger",
            "message": "Hey, I'm interested in your product. Can you tell me more?",
            "source": "website",
            "status": Lead.Status.DISQUALIFIED,
            "routing_queue": "nurture",
            "response_sla_deadline": now + timedelta(hours=24),
            "draft_reply": (
                "Hi Jake,\n\nThanks for reaching out to Flowline!\n\n"
                "Flowline is designed for operations and finance teams at B2B companies "
                "that process multi-step approvals, vendor onboarding, and cross-team "
                "workflows. Based on what you've shared, it sounds like it might not be "
                "the right fit right now — our platform works best for teams managing "
                "30+ workflows per month.\n\n"
                "That said, feel free to explore our documentation at flowline.io/docs. "
                "If your needs change, we'd love to hear from you.\n\n"
                "Best,\nFlowline Team"
            ),
            "qualification_result": {
                "icp_score": 0.08,
                "tier": "cold",
                "icp_match_reasons": [],
                "icp_gap_reasons": [
                    "No company context — appears to be a personal blog",
                    "Message provides no use case or business context",
                    "No indication of team size or workflow volume",
                    "B2C profile — personal blogger is not our ICP",
                ],
                "routing_queue": "nurture",
                "confidence": {"icp_fit": 0.95, "urgency": 0.1, "draft_reply": 0.85},
                "overall_confidence": 0.90,
                "ambiguity_flags": [],
                "contacts_consulted": 0,
                "product_info_consulted": [],
                "web_sources_consulted": [],
                "agent_type": "LeadQualificationAgent",
                "model_id": "claude-sonnet-4-6",
                "turns": 3,
                "duration_ms": 4200,
                "source": "agent",
                "draft_reply": (
                    "Hi Jake,\n\nThanks for reaching out to Flowline!\n\n"
                    "Flowline is designed for operations and finance teams at B2B companies "
                    "that process multi-step approvals, vendor onboarding, and cross-team "
                    "workflows. Based on what you've shared, it sounds like it might not be "
                    "the right fit right now — our platform works best for teams managing "
                    "30+ workflows per month.\n\n"
                    "Feel free to explore our documentation at flowline.io/docs. "
                    "If your needs change, we'd love to hear from you.\n\n"
                    "Best,\nFlowline Team"
                ),
            },
        },
        # ── Scenario 2: Warm lead — existing CRM contacts at apex-logistics.com ─
        {
            "name": "Rachel Torres",
            "email": "rachel.torres@apex-logistics.com",
            "company": "Apex Logistics",
            "role": "COO",
            "message": (
                "Hi, I'm the COO at Apex Logistics (180 employees). We've been struggling "
                "with our purchase order approval process — it takes 5+ days to get a PO "
                "signed off and it's causing delays with our suppliers. Our procurement "
                "manager mentioned your product after attending one of your webinars. "
                "We're running NetSuite and would need a native integration. "
                "Do you have enterprise pricing? We'd like to schedule a demo this week."
            ),
            "source": "referral",
            "status": Lead.Status.QUALIFIED,
            "routing_queue": "senior-sales",
            "response_sla_deadline": now + timedelta(minutes=15),
            "draft_reply": (
                "Hi Rachel,\n\nThank you for reaching out — and great to connect with "
                "another member of the Apex Logistics team!\n\n"
                "The purchase order approval pain you're describing is exactly what "
                "Flowline was built to solve. A 5-day approval cycle is leaving money "
                "on the table: supplier penalties, stalled operations, and team frustration. "
                "We've seen customers like you cut that to under 4 hours.\n\n"
                "On NetSuite integration — yes, we have a native NetSuite connector "
                "on our Scale and Enterprise plans that syncs vendors, POs, and approvals "
                "bidirectionally. Given Apex's size (180 employees), you'd likely be on "
                "our Scale or Enterprise plan.\n\n"
                "I'd love to show you a demo this week. What's your availability? "
                "I can have a 30-minute slot ready by tomorrow.\n\n"
                "Best,\nFlowline Sales"
            ),
            "qualification_result": {
                "icp_score": 0.92,
                "tier": "hot",
                "icp_match_reasons": [
                    "180-employee B2B logistics company — squarely in ICP",
                    "Explicit pain: 5+ day PO approval cycle causing supplier delays",
                    "Uses NetSuite — we have a native integration",
                    "Requesting demo this week — strong buying intent",
                    "COO outreach — executive sponsor, not just an evaluator",
                    "CRM: 2 prior contacts at apex-logistics.com (VP of Ops + Procurement Manager) — warm company",
                ],
                "icp_gap_reasons": [],
                "routing_queue": "senior-sales",
                "confidence": {"icp_fit": 0.97, "urgency": 0.95, "draft_reply": 0.92},
                "overall_confidence": 0.94,
                "ambiguity_flags": [
                    {
                        "field": "budget",
                        "description": "No explicit budget mentioned, though enterprise demo request implies allocated budget",
                        "alternatives": ["May be in early evaluation stage before budget approval"],
                    }
                ],
                "contacts_consulted": 2,
                "product_info_consulted": [],
                "web_sources_consulted": [],
                "agent_type": "LeadQualificationAgent",
                "model_id": "claude-sonnet-4-6",
                "turns": 4,
                "duration_ms": 6800,
                "source": "agent",
                "draft_reply": (
                    "Hi Rachel,\n\nThank you for reaching out — and great to connect with "
                    "another member of the Apex Logistics team!\n\n"
                    "The purchase order approval pain you're describing is exactly what "
                    "Flowline was built to solve. A 5-day approval cycle is leaving money "
                    "on the table: supplier penalties, stalled operations, and team frustration. "
                    "We've seen customers like you cut that to under 4 hours.\n\n"
                    "On NetSuite integration — yes, we have a native NetSuite connector "
                    "on our Scale and Enterprise plans that syncs vendors, POs, and approvals "
                    "bidirectionally. Given Apex's size (180 employees), you'd likely be on "
                    "our Scale or Enterprise plan.\n\n"
                    "I'd love to show you a demo this week. What's your availability? "
                    "I can have a 30-minute slot ready by tomorrow.\n\n"
                    "Best,\nFlowline Sales"
                ),
            },
        },
        # ── Scenario 3: Web-enriched — promising but unknown company ──────────
        {
            "name": "Daniel Osei",
            "email": "daniel@constructpro-africa.com",
            "company": "ConstructPro Africa",
            "role": "Operations Director",
            "message": (
                "Hello, we're a construction project management company based in Nairobi. "
                "We manage 30+ active construction sites across East Africa with about "
                "250 staff. Our subcontractor approval and payment workflow is entirely "
                "on WhatsApp and email — we're losing visibility and it's becoming a "
                "compliance nightmare. Looked at a few tools but nothing fits our "
                "multi-entity, multi-currency setup. Does Flowline handle that?"
            ),
            "source": "website",
            "status": Lead.Status.QUALIFIED,
            "routing_queue": "sales-team",
            "response_sla_deadline": now + timedelta(hours=2),
            "draft_reply": (
                "Hi Daniel,\n\nThis is exactly the kind of problem Flowline helps solve — "
                "and the combination of subcontractor approvals, multi-site visibility, "
                "and compliance documentation is a strong match for our platform.\n\n"
                "On multi-entity and multi-currency support: yes, our Scale and Enterprise "
                "plans support multi-entity workflow routing and are currency-agnostic — "
                "approvals can be configured per entity with separate approval chains and "
                "document requirements. We have a few construction customers in "
                "high-growth markets using exactly this setup.\n\n"
                "Given the compliance angle you mentioned, I'd also highlight our audit "
                "trail — every approval action is timestamped and exportable, which helps "
                "significantly with subcontractor documentation.\n\n"
                "Are you available for a 30-minute call this week? I'd love to map your "
                "workflow to what we offer and see if there's a fit.\n\n"
                "Best,\nFlowline Sales"
            ),
            "qualification_result": {
                "icp_score": 0.71,
                "tier": "warm",
                "icp_match_reasons": [
                    "250-person construction company — in ICP size range",
                    "30+ active sites, 30+ workflows — meets our volume threshold",
                    "Explicit compliance pain — strong urgency signal",
                    "Looking to replace WhatsApp/email — active buying intent",
                    "ConstructPro Africa: web research confirms active construction PM firm operating across Kenya, Uganda, Tanzania — not a small operator",
                ],
                "icp_gap_reasons": [
                    "East Africa market — may require additional discovery on data residency and currency support",
                    "Multi-entity requirement adds implementation complexity",
                ],
                "routing_queue": "sales-team",
                "confidence": {"icp_fit": 0.78, "urgency": 0.85, "draft_reply": 0.82},
                "overall_confidence": 0.76,
                "ambiguity_flags": [
                    {
                        "field": "multi_entity_support",
                        "description": "Multi-entity, multi-currency requirement confirmed but specific ERP or accounting system not mentioned — integration complexity unknown",
                        "alternatives": [
                            "May use local accounting software (e.g. Sage, Pastel) not in our integration list",
                            "Could be on QuickBooks or Xero which we support natively",
                        ],
                    }
                ],
                "contacts_consulted": 0,
                "product_info_consulted": [],
                "web_sources_consulted": [
                    "https://constructpro-africa.com/about",
                    "https://linkedin.com/company/constructpro-africa",
                ],
                "agent_type": "LeadQualificationAgent",
                "model_id": "claude-sonnet-4-6",
                "turns": 5,
                "duration_ms": 9400,
                "source": "agent",
                "draft_reply": (
                    "Hi Daniel,\n\nThis is exactly the kind of problem Flowline helps solve — "
                    "and the combination of subcontractor approvals, multi-site visibility, "
                    "and compliance documentation is a strong match for our platform.\n\n"
                    "On multi-entity and multi-currency support: yes, our Scale and Enterprise "
                    "plans support multi-entity workflow routing and are currency-agnostic — "
                    "approvals can be configured per entity with separate approval chains and "
                    "document requirements. We have a few construction customers in "
                    "high-growth markets using exactly this setup.\n\n"
                    "Given the compliance angle you mentioned, I'd also highlight our audit "
                    "trail — every approval action is timestamped and exportable, which helps "
                    "significantly with subcontractor documentation.\n\n"
                    "Are you available for a 30-minute call this week? I'd love to map your "
                    "workflow to what we offer and see if there's a fit.\n\n"
                    "Best,\nFlowline Sales"
                ),
            },
        },
        # ── Additional leads — various ICP match/mismatch combinations ─────────
        {
            "name": "Lena Fischer",
            "email": "lena.fischer@medflex-clinics.de",
            "company": "MedFlex Clinics",
            "role": "Head of Administration",
            "message": (
                "We're a network of 12 medical clinics in Germany with 90 staff. "
                "We need to automate our supplier and equipment approval workflows — "
                "currently all done via paper and email. We also need audit trails "
                "for German healthcare compliance (MDR). Is your product GDPR-compliant?"
            ),
            "source": "website",
            "status": Lead.Status.QUALIFIED,
            "routing_queue": "sales-team",
            "response_sla_deadline": now + timedelta(hours=2),
            "draft_reply": (
                "Hi Lena,\n\nYes — Flowline is GDPR-compliant with EU data residency options, "
                "and our audit trail features are specifically designed for regulated industries. "
                "Every approval action is logged with user, timestamp, and decision rationale, "
                "which aligns well with MDR documentation requirements.\n\n"
                "For a 90-person clinic network managing supplier and equipment approvals, "
                "our Growth or Scale plan would be the right fit. I'd be glad to walk you "
                "through how other healthcare-adjacent customers have configured their "
                "compliance workflows.\n\nWould a 30-minute demo work for you this week?\n\n"
                "Best,\nFlowline Sales"
            ),
            "qualification_result": {
                "icp_score": 0.68,
                "tier": "warm",
                "icp_match_reasons": [
                    "90-person clinic network — in ICP size range",
                    "12 sites, supplier + equipment approvals — meets workflow volume",
                    "GDPR and compliance requirement — we support this",
                    "Current process is paper/email — high switching motivation",
                ],
                "icp_gap_reasons": [
                    "Healthcare (clinical) — some MDR-specific requirements may be out of scope",
                    "German market — may need local support and German-language UI",
                ],
                "routing_queue": "sales-team",
                "confidence": {"icp_fit": 0.72, "urgency": 0.65, "draft_reply": 0.80},
                "overall_confidence": 0.70,
                "ambiguity_flags": [
                    {
                        "field": "mdr_compliance",
                        "description": "MDR (EU Medical Device Regulation) may require specific audit log formats beyond our standard offering",
                        "alternatives": [
                            "Standard Flowline audit trail may be sufficient",
                            "May need custom reporting module",
                        ],
                    }
                ],
                "contacts_consulted": 0,
                "product_info_consulted": [],
                "web_sources_consulted": [],
                "agent_type": "LeadQualificationAgent",
                "model_id": "claude-sonnet-4-6",
                "turns": 4,
                "duration_ms": 5600,
                "source": "agent",
                "draft_reply": (
                    "Hi Lena,\n\nYes — Flowline is GDPR-compliant with EU data residency options, "
                    "and our audit trail features are specifically designed for regulated industries. "
                    "Every approval action is logged with user, timestamp, and decision rationale, "
                    "which aligns well with MDR documentation requirements.\n\n"
                    "For a 90-person clinic network managing supplier and equipment approvals, "
                    "our Growth or Scale plan would be the right fit. I'd be glad to walk you "
                    "through how other healthcare-adjacent customers have configured their "
                    "compliance workflows.\n\nWould a 30-minute demo work for you this week?\n\n"
                    "Best,\nFlowline Sales"
                ),
            },
        },
        {
            "name": "Tom Bradley",
            "email": "tom@startup-ideas.co",
            "company": "Startup Ideas Co",
            "role": "Founder",
            "message": "Hi, I'm building a startup and thinking about workflow tools. No team yet but maybe in future.",
            "source": "website",
            "status": Lead.Status.DISQUALIFIED,
            "routing_queue": "nurture",
            "response_sla_deadline": now + timedelta(hours=24),
            "draft_reply": (
                "Hi Tom,\n\nThanks for reaching out! Flowline works best for teams "
                "that are already processing workflows at scale — typically 25+ employees "
                "handling 30+ approval-type workflows per month.\n\n"
                "It sounds like you're still in early stages, which is exciting. "
                "When your team grows and you start hitting approval bottlenecks, "
                "we'd love to talk. In the meantime, feel free to bookmark flowline.io.\n\n"
                "Best of luck with the startup!\nFlowline Team"
            ),
            "qualification_result": {
                "icp_score": 0.05,
                "tier": "cold",
                "icp_match_reasons": [],
                "icp_gap_reasons": [
                    "No team yet — below minimum company size threshold",
                    "No current workflow volume",
                    "Speculative interest, no active pain",
                ],
                "routing_queue": "nurture",
                "confidence": {"icp_fit": 0.95, "urgency": 0.05, "draft_reply": 0.90},
                "overall_confidence": 0.92,
                "ambiguity_flags": [],
                "contacts_consulted": 0,
                "product_info_consulted": [],
                "web_sources_consulted": [],
                "agent_type": "LeadQualificationAgent",
                "model_id": "claude-sonnet-4-6",
                "turns": 2,
                "duration_ms": 2900,
                "source": "agent",
                "draft_reply": (
                    "Hi Tom,\n\nThanks for reaching out! Flowline works best for teams "
                    "that are already processing workflows at scale — typically 25+ employees "
                    "handling 30+ approval-type workflows per month.\n\n"
                    "It sounds like you're still in early stages, which is exciting. "
                    "When your team grows and you start hitting approval bottlenecks, "
                    "we'd love to talk. In the meantime, feel free to bookmark flowline.io.\n\n"
                    "Best of luck with the startup!\nFlowline Team"
                ),
            },
        },
    ]

    for lead_data in seed_leads:
        _, created = Lead.objects.get_or_create(
            email=lead_data["email"],
            company=lead_data["company"],
            defaults=lead_data,
        )
        if created:
            print(f"  Created Lead: {lead_data['name']} ({lead_data['company']}) — {lead_data['status']}")

    print("\nSeed complete.")
    print(f"  {AgentConfig.objects.count()} agent config(s)")
    print(f"  {ProductInfo.objects.count()} product info articles")
    print(f"  {RoutingRule.objects.count()} routing rules")
    print(f"  {Contact.objects.count()} CRM contacts")
    print(f"  {Lead.objects.count()} leads")


if __name__ == "__main__":
    seed()
