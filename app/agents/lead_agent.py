"""
LeadQualificationAgent: analyzes an inbound lead and produces a structured
LeadQualificationResult.

Entry point: run_lead_agent() — called via asyncio.run() from the Celery task.

The system prompt is built dynamically from the active AgentConfig, so the
agent's ICP criteria and scoring guidance are always current without code changes.
"""
import os
import time
import uuid

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage
from agents.mcp_server import lead_server
from agents.hooks import build_audit_hooks
from agents.schemas import LeadQualificationResult

_DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")


def _build_system_prompt(config) -> str:
    """
    Build the agent system prompt from the active AgentConfig.

    config: AgentConfig model instance (passed in from Celery task).
    This function is pure — no DB access.
    """
    return f"""You are a lead qualification agent for {config.company_name}.

{config.company_description}

Ideal customer profile:
{config.ideal_customer_description}

Disqualifying signals (classify as cold regardless of other factors):
{config.disqualifying_signals}

Scoring guidance:
{config.scoring_guidance}

Process:
1. Call GetCRMHistory with the lead's email domain to check for prior contacts at this company.
2. Call SearchProductInfo with keywords from the lead's message to find relevant product context.
3. If the lead's company is not in the CRM and you need more context, call WebSearch
   with a query like "[company name] company funding size industry" to research them.
   If WebSearch returns an error field, skip it and proceed with the data you have.
4. Based on your research, produce your final qualification result.

Scoring:
- icp_score: 0.0 to 1.0. Use your full judgment — this is not an average.
- tier: "hot" (>= 0.75), "warm" (0.4 – 0.74), "cold" (< 0.4)
- Be explicit about ambiguity. Use ambiguity_flags for anything uncertain.
- draft_reply: write a personalized first-touch reply that references specifics from the lead's message.

Your final output must include:
- icp_score, tier, icp_match_reasons, icp_gap_reasons
- draft_reply, routing_queue
- confidence (icp_fit, urgency, draft_reply scores), overall_confidence
- ambiguity_flags, contacts_consulted, product_info_consulted, web_sources_consulted
- agent_type: "LeadQualificationAgent"
- model_id: the model ID you are running as
- turns: 0, duration_ms: 0 (caller fills these in)
- source: "agent"
"""


async def run_lead_agent(
    lead_id: str,
    lead_name: str,
    lead_email: str,
    lead_company: str,
    lead_role: str,
    lead_message: str,
    config,  # AgentConfig instance
    model_id: str = _DEFAULT_MODEL,
    content_type_id: int = None,
) -> dict:
    """
    Run the LeadQualificationAgent for a single lead.

    Returns {"qualification_result": dict, "turns": int, "duration_ms": int, "run_id": str}.
    The Celery task is responsible for writing the result to the DB.

    Called via asyncio.run() from the Celery task.
    content_type_id is passed through to build_audit_hooks for generic FK logging.
    """
    run_id = str(uuid.uuid4())
    start_ms = int(time.time() * 1000)

    options = ClaudeAgentOptions(
        system_prompt=_build_system_prompt(config),
        mcp_servers={"leads": lead_server},
        allowed_tools=["mcp__leads__*"],
        permission_mode="bypassPermissions",
        max_turns=12,
        model=model_id,
        hooks=build_audit_hooks(
            content_type_id=content_type_id,
            object_id=lead_id,
            run_id=run_id,
        ),
        output_format={
            "type": "json_schema",
            "schema": LeadQualificationResult.model_json_schema(),
        },
    )

    email_domain = lead_email.split("@")[-1].lower() if "@" in lead_email else ""
    user_message = (
        f"Name: {lead_name}\n"
        f"Email: {lead_email}\n"
        f"Email domain: {email_domain}\n"
        f"Company: {lead_company}\n"
        f"Role: {lead_role or 'not specified'}\n\n"
        f"Message:\n{lead_message}"
    )

    async def prompt_stream():
        yield {"type": "user", "message": {"role": "user", "content": user_message}}

    turns = 0
    structured_output = None

    async for message in query(prompt=prompt_stream(), options=options):
        if isinstance(message, AssistantMessage):
            turns += 1
        elif isinstance(message, ResultMessage):
            structured_output = message.structured_output

    if structured_output is None:
        raise RuntimeError("Agent completed without producing structured output")

    duration_ms = int(time.time() * 1000) - start_ms
    return {
        "qualification_result": structured_output,
        "turns": turns,
        "duration_ms": duration_ms,
        "run_id": run_id,
    }
