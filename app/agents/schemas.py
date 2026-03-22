from pydantic import BaseModel


class QualificationConfidence(BaseModel):
    """Per-field confidence scores (0.0 to 1.0)."""
    icp_fit: float
    urgency: float
    draft_reply: float


class AmbiguityFlag(BaseModel):
    """An ambiguity the agent explicitly identified."""
    field: str
    description: str
    alternatives: list[str]


class LeadQualificationResult(BaseModel):
    """
    The contract between LeadQualificationAgent judgment and deterministic
    post-processing. Stored in Lead.qualification_result as JSON.

    icp_score is the agent's holistic assessment (0.0 to 1.0).
    _apply_routing_rules() uses this score to determine the final
    routing_queue and response_sla_deadline — the agent's routing_queue
    suggestion is advisory only.
    """
    # Agent decisions
    icp_score: float              # 0.0 to 1.0
    tier: str                     # "hot" | "warm" | "cold"
    icp_match_reasons: list[str]  # criteria that matched
    icp_gap_reasons: list[str]    # criteria that did not match
    draft_reply: str              # personalized first-touch reply to send
    routing_queue: str            # agent suggestion; overridden by RoutingRule

    # Confidence and transparency
    confidence: QualificationConfidence
    overall_confidence: float
    ambiguity_flags: list[AmbiguityFlag]

    # Context used (for audit trail)
    contacts_consulted: int            # how many CRM contacts the agent reviewed
    product_info_consulted: list[str]  # ProductInfo IDs the agent found relevant
    web_sources_consulted: list[str]   # URLs from web search (empty in Phase 1)

    # Metadata
    agent_type: str      # "LeadQualificationAgent"
    model_id: str        # which Claude model produced this
    turns: int           # how many agent turns were needed
    duration_ms: int
    source: str          # "agent"
