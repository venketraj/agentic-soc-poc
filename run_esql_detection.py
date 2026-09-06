import os
import sys
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

ES_URL = os.getenv("ELASTICSEARCH_URL")
ES_API_KEY = os.getenv("ELASTIC_API_KEY")
INDEX_NAME = "agent-runtime-telemetry"

es = Elasticsearch(ES_URL, api_key=ES_API_KEY)

def execute_esql_detection():
    print("[*] Running ES|QL Multi-Signal Detection Engine...")

    # ES|QL query: Group by session, check for untrusted ingest, and flag bulk data actions
    query = f"""
    FROM {INDEX_NAME}
    | STATS
        has_untrusted_origin = MAX(taint.is_tainted),
        origin_source = MAX(taint.origin),
        max_cardinality = MAX(action.cardinality),
        suspect_action = MAX(action.name),
        total_spans = COUNT(span.id)
      BY session.id, trace.id, agent.id
    | EVAL 
        is_cardinality_anomaly = (max_cardinality >= 10000),
        taint_multiplier = CASE(has_untrusted_origin == true, 2.5, 1.0),
        base_risk = CASE(is_cardinality_anomaly == true, 40.0, 10.0),
        fused_risk_score = base_risk * taint_multiplier
    | WHERE fused_risk_score >= 80.0
    | SORT fused_risk_score DESC
    | LIMIT 5
    """

    try:
        response = es.esql.query(query=query)
        columns = [c["name"] for c in response["columns"]]
        rows = response["values"]

        if not rows:
            print("[-] No high-risk incident detected across current sessions.")
            return None

        print(f"\n[!] HIGH-RISK INCIDENT DETECTED: {len(rows)} matching session(s)\n")
        
        # Display formatted detection table
        header = f"{'Session ID':<18} | {'Agent ID':<25} | {'Suspect Action':<25} | {'Cardinality':<12} | {'Risk Score':<10}"
        print(header)
        print("-" * len(header))

        incident_context = {}
        for row in rows:
            row_dict = dict(zip(columns, row))
            print(
                f"{str(row_dict.get('session.id')):<18} | "
                f"{str(row_dict.get('agent.id')):<25} | "
                f"{str(row_dict.get('suspect_action')):<25} | "
                f"{str(row_dict.get('max_cardinality')):<12} | "
                f"{str(row_dict.get('fused_risk_score')):<10}"
            )
            incident_context = row_dict

        # Evaluate Graduated Containment Tier based on Fused Risk Score
        score = float(incident_context.get("fused_risk_score", 0))
        tier = "NONE"
        if score >= 90:
            tier = "T3: Revoke Session Credentials"
        elif score >= 60:
            tier = "T2: Downgrade Session to Read-Only"
        elif score >= 30:
            tier = "T1: Throttle Invocations"

        print(f"\n[+] Recommended Response: {tier}")
        print(f"  --> Root Cause Provenance: {incident_context.get('origin_source')}")
        print(f"  --> Trace ID for Blast-Radius Graph: {incident_context.get('trace.id')}")
        return incident_context

    except Exception as e:
        print(f"[!] ES|QL Execution Failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    execute_esql_detection()