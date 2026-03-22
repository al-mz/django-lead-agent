"""
In-process MCP server for the LeadQualificationAgent.

Created ONCE at module level. Celery workers import this at startup.
All tools are read-only — the agent never writes to the DB.
"""
import json
import os
from claude_agent_sdk import tool, create_sdk_mcp_server


@tool(
    "GetCRMHistory",
    "Look up existing contacts at a company by email domain. "
    "Returns names, roles, and notes for prior contacts.",
    {"email_domain": str, "limit": int},
)
async def get_crm_history(args: dict) -> dict:
    from leads.models import Contact

    domain = args.get("email_domain", "").lower().strip()
    limit = min(args.get("limit", 5), 20)

    contacts = [
        c async for c in Contact.objects.filter(
            email_domain=domain
        ).values("name", "email", "company", "role", "notes", "created_at")[:limit]
    ]

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "domain": domain,
                    "contact_count": len(contacts),
                    "contacts": [
                        {
                            "name": c["name"],
                            "email": c["email"],
                            "role": c["role"],
                            "notes": c["notes"],
                            "first_seen": c["created_at"].isoformat(),
                        }
                        for c in contacts
                    ],
                }),
            }
        ]
    }


@tool(
    "SearchProductInfo",
    "Search product and service documentation by keywords. "
    "Use this to find relevant product context for the lead's message.",
    {
        "type": "object",
        "properties": {
            "keywords": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer"},
        },
        "required": ["keywords"],
    },
)
async def search_product_info(args: dict) -> dict:
    from leads.models import ProductInfo
    from django.db.models import Q

    keywords = args.get("keywords", [])
    query = Q()
    for kw in keywords:
        query |= Q(keywords__contains=kw)
    # keywords__contains does exact-match lookups against the JSONField array.
    # Seed data keywords must match the agent's search terms exactly.

    limit = min(args.get("limit", 3), 20)
    articles = [
        a async for a in ProductInfo.objects.filter(query).values(
            "id", "title", "content"
        )[:limit]
    ]

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps([
                    {
                        "id": str(a["id"]),
                        "title": a["title"],
                        "content": a["content"][:500],
                    }
                    for a in articles
                ]),
            }
        ]
    }


@tool(
    "WebSearch",
    "Search the web for information about the lead's company or industry. "
    "Use this when CRM history and product docs don't provide enough context.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "num_results": {"type": "integer"},
        },
        "required": ["query"],
    },
)
async def web_search(args: dict) -> dict:
    import httpx

    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return {"content": [{"type": "text", "text": json.dumps({"error": "BRAVE_API_KEY not set"})}]}

    query = args.get("query", "")
    num_results = min(args.get("num_results", 5), 10)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
                params={"q": query, "count": num_results},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        # Degrade gracefully — agent continues reasoning on internal data only.
        return {"content": [{"type": "text", "text": json.dumps({"error": str(exc), "results": []})}]}

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": r.get("description", "")[:300],
        }
        for r in data.get("web", {}).get("results", [])
    ]

    return {
        "content": [{"type": "text", "text": json.dumps(results)}]
    }


# ─── Server (instantiated once at module level) ───────────────────────────────

lead_server = create_sdk_mcp_server(
    name="leads",
    version="1.0.0",
    tools=[get_crm_history, search_product_info, web_search],
)
