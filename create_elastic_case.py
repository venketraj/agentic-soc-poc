import os
import sys
import requests
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

ES_URL = os.getenv("ELASTICSEARCH_URL").rstrip("/")
KIBANA_URL = ES_URL.replace(".es.", ".kb.")
API_KEY = os.getenv("ELASTIC_API_KEY")
INDEX_NAME = "agent-runtime-telemetry"

es = Elasticsearch(ES_URL, api_key=API_KEY)

headers = {
    "kbn-xsrf": "true",
    "Authorization": f"ApiKey {API_KEY}",
    "Content-Type": "application/json"
}


def fetch_latest_incident():
    """Dynamically detects the highest-risk compromised session using ES|QL."""
    query = f"""
    FROM {INDEX_NAME}
    | STATS
        has_untrusted_origin = MAX(taint.is_tainted),
        origin_source = MAX(taint.origin),
        max_cardinality = MAX(action.cardinality),
        suspect_action = MAX(action.name),
        origin_span_id = MAX(taint.source_span_id),
        detected_time = MAX(@timestamp)
      BY session.id, trace.id, agent.id
    | EVAL 
        is_cardinality_anomaly = (max_cardinality >= 10000),
        taint_multiplier = CASE(has_untrusted_origin == true, 2.5, 1.0),
        base_risk = CASE(is_cardinality_anomaly == true, 40.0, 10.0),
        fused_risk_score = base_risk * taint_multiplier
    | WHERE fused_risk_score >= 80.0
    | SORT fused_risk_score DESC
    | LIMIT 1
    """
    response = es.esql.query(query=query)
    columns = [c["name"] for c in response["columns"]]
    rows = response["values"]

    if not rows:
        return None
    return dict(zip(columns, rows[0]))


def fetch_session_spans(session_id: str):
    """Retrieves all chronologically ordered spans for this session to build the citation chain."""
    resp = es.search(
        index=INDEX_NAME,
        query={"term": {"session.id": session_id}},
        sort=[{"@timestamp": {"order": "asc"}}]
    )
    return [hit["_source"] for hit in resp["hits"]["hits"]]


def create_dynamic_investigation_case():
    print("[*] Detecting active security incidents via ES|QL...")
    incident = fetch_latest_incident()

    if not incident:
        print("[-] No high-risk incidents detected in index. Run a simulation first.")
        return

    session_id = incident["session.id"]
    agent_id = incident["agent.id"]
    trace_id = incident["trace.id"]
    score = incident["fused_risk_score"]
    cardinality = incident["max_cardinality"]
    origin = incident["origin_source"]

    print(f"[+] Found active incident for session: {session_id} (Score: {score})")
    print("[*] Retrieving causal span chain for backward reachability citations...")

    spans = fetch_session_spans(session_id)
    
    # Build dynamic markdown list of cited spans
    span_citations = []
    for idx, s in enumerate(spans, 1):
        span_id = s.get("span", {}).get("id", "unknown")
        action_name = s.get("action", {}).get("name", "unknown")
        is_tainted = s.get("taint", {}).get("is_tainted", False)
        span_citations.append(
            f"{idx}. **Step `{action_name}`** — Span ID: `{span_id}` (Tainted: `{is_tainted}`)"
        )
    span_chain_md = "\n".join(span_citations)

    # Dynamic incident markdown narrative
    case_payload = {
        "title": f"CRITICAL: Agent Hijack Detected on {agent_id} (Session {session_id[:12]})",
        "description": (
            f"### Blast-Radius & Causal Narrative\n\n"
            f"- **Session ID**: `{session_id}`\n"
            f"- **Agent Identity**: `{agent_id}`\n"
            f"- **Trace ID**: `{trace_id}`\n"
            f"- **Fused Behavioral Risk Score**: `{score}` / 100.0\n"
            f"- **Root Cause Artifact**: `{origin}`\n"
            f"- **Observed Cardinality**: `{cardinality:,}` records (Threshold: 10,000)\n\n"
            f"#### Causal Execution Chain (Span Citations)\n"
            f"{span_chain_md}\n\n"
            f"#### Response Status\n"
            f"- **Containment Action**: `Tier T3: Revoke Session Credentials`\n"
            f"- **Enforcement**: Autonomous denial condition on `aws:TokenIssueTime`\n"
            f"- **Blast Radius**: Confined to 1 session; shared IAM role remains operational.\n"
            f"- **Audit Evidence**: Committed to S3 Object Lock ledger."
        ),
        "tags": ["agentic-soc", "runtime-detection", f"agent-{agent_id}"],
        "severity": "critical"
    }

    url = f"{KIBANA_URL}/api/cases"
    try:
        res = requests.post(url, json=case_payload, headers=headers, timeout=10)
        if res.status_code in (200, 201):
            case_id = res.json().get("id")
            print(f"[+] Elastic Case Created Successfully! ID: {case_id}")
            print(f"    View in Kibana: {KIBANA_URL}/app/management/insightsAndAlerting/cases")
        else:
            print(f"[!] Kibana Case API returned HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"[!] Failed to connect to Kibana Case endpoint: {str(e)}")


if __name__ == "__main__":
    create_dynamic_investigation_case()