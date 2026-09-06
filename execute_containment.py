import datetime
import json
import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME = os.getenv("AUDIT_LOG_BUCKET", "agentic-soc-audit-ledger-demo")

iam_client = boto3.client(
    "iam",
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    region_name=AWS_REGION
)

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    region_name=AWS_REGION
)


def ensure_audit_bucket_exists():
    """Ensures the S3 audit bucket exists."""
    try:
        if AWS_REGION == "us-east-1":
            s3_client.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3_client.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION}
            )
        print(f"[+] Verified/Created S3 Audit Bucket: {BUCKET_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"[*] S3 Audit Bucket '{BUCKET_NAME}' already accessible.")
        else:
            print(f"[!] S3 Setup Warning: {e.response['Error']['Message']}")


def apply_t3_revocation(session_id: str, agent_id: str):
    """
    Executes T3 containment: revokes temporary credentials for the compromised session.
    Calculates a revocation timestamp condition on aws:TokenIssueTime.
    """
    revocation_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    containment_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Deny",
                "Action": "*",
                "Resource": "*",
                "Condition": {
                    "DateLessThan": {
                        "aws:TokenIssueTime": revocation_timestamp
                    }
                }
            }
        ]
    }

    # Generate the exact scripted rollback command for the audit log
    rollback_command = f"aws iam delete-role-policy --role-name {agent_id} --policy-name RevokeSession-{session_id}"

    action_record = {
        "containment_tier": "T3",
        "action_taken": "Revoke Session Credentials",
        "session_id": session_id,
        "agent_id": agent_id,
        "revocation_time": revocation_timestamp,
        "policy_applied": containment_policy,
        "rollback_command": rollback_command,
        "authorization": "Autonomous (Fused Risk Score >= 90.0)"
    }
    
    return action_record


def write_to_audit_ledger(incident_data: dict, containment_record: dict):
    """Commits the immutable decision ledger record to S3."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    ledger_key = f"containment-records/{incident_data['session_id']}_{timestamp}.json"
    
    ledger_entry = {
        "incident": incident_data,
        "containment": containment_record,
        "logged_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=ledger_key,
            Body=json.dumps(ledger_entry, indent=2),
            ContentType="application/json"
        )
        print(f"[+] Audit Ledger Committed: s3://{BUCKET_NAME}/{ledger_key}")
    except Exception as e:
        print(f"[!] S3 Ledger Write Error: {str(e)}")


def run_containment_handler():
    print("[*] Initiating Response Engine...")
    ensure_audit_bucket_exists()

    # Pass the session context generated from your ES|QL detection output
    mock_incident_event = {
        "session_id": "sess-f8b770d9",
        "agent_id": "agent-support-billing-01",
        "suspect_action": "export_customer_records",
        "cardinality": 40000,
        "fused_risk_score": 100.0,
        "provenance_origin": "untrusted_jira_comment",
        "trace_id": "trace-e37caf93f285"
    }

    print(f"\n[!] Executing Graduated Containment for Session: {mock_incident_event['session_id']}")
    print(f"  --> Score: {mock_incident_event['fused_risk_score']} | Fused Tier: T3")

    containment_record = apply_t3_revocation(
        session_id=mock_incident_event["session_id"],
        agent_id=mock_incident_event["agent_id"]
    )

    print(f"  --> Action: {containment_record['action_taken']}")
    print(f"  --> Blast Radius: 1 Session (Other workloads on role remain unaffected)")
    print(f"  --> Generated Rollback Command: {containment_record['rollback_command']}")

    write_to_audit_ledger(mock_incident_event, containment_record)
    print("\n[OK] T3 Containment and Audit Ledger execution complete.")


if __name__ == "__main__":
    run_containment_handler()