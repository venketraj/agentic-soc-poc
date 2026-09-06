import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from openai import OpenAI
import requests

load_dotenv()


def verify_aws_and_mantle():
    """Step 1: Test basic IAM/STS authentication first, then invoke Bedrock Mantle."""
    print("[1/3] Testing AWS Connection & Bedrock Mantle Endpoint...")
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    mantle_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK") or aws_secret_key
    model_id = os.getenv("MANTLE_MODEL_ID", "amazon.nova-lite-v1:0")

    # 1a. Verify AWS credentials reachability via STS if keys are present
    if aws_access_key and aws_secret_key:
        try:
            sts = boto3.client(
                "sts",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=region,
            )
            caller = sts.get_caller_identity()
            print(f"  --> AWS STS Auth OK! Account: {caller.get('Account')} | ARN: {caller.get('Arn')}")
        except ClientError as e:
            print(f"  --> AWS Auth WARN: {e.response.get('Error', {}).get('Message', str(e))}")
        except Exception as e:
            print(f"  --> AWS Network WARN: {str(e)}")

    # 1b. Test Bedrock Mantle OpenAI-compatible endpoint
    mantle_base_url = f"https://bedrock-mantle.{region}.api.aws/v1"
    print(f"      Invoking Mantle Endpoint: {mantle_base_url} (Model: {model_id})...")

    if not mantle_token:
        print("  --> Mantle ERROR: Missing AWS_BEARER_TOKEN_BEDROCK or AWS_SECRET_ACCESS_KEY in .env")
        return False

    try:
        client = OpenAI(
            base_url=mantle_base_url,
            api_key=mantle_token
        )

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "user", "content": "Ping test. Respond strictly with 'READY'."}
            ],
            max_tokens=15,
            temperature=0.0
        )

        output = response.choices[0].message.content.strip()
        print(f"  --> Bedrock Mantle OK! Model: {model_id} | Response: '{output}'")
        return True

    except Exception as e:
        print(f"  --> Bedrock Mantle ERROR: {str(e)}")
        print("      Check that the model name exists on Mantle and your Bearer Token/API Key is valid.")
        return False


def verify_elastic():
    """Step 2: Ping cluster first before querying cluster info."""
    print("\n[2/3] Testing Elastic Cloud Connectivity...")
    es_url = os.getenv("ELASTICSEARCH_URL")
    api_key = os.getenv("ELASTIC_API_KEY")

    if not es_url or not api_key:
        print("  --> Elastic ERROR: Missing ELASTICSEARCH_URL or ELASTIC_API_KEY in .env")
        return False

    try:
        client = Elasticsearch(es_url, api_key=api_key)

        if not client.ping():
            print("  --> Elastic ERROR: Ping failed. Cluster is unreachable or credentials invalid.")
            return False

        info = client.info()
        print(f"  --> Elastic OK! Cluster: {info['cluster_name']} (v{info['version']['number']})")
        return True
    except Exception as e:
        print(f"  --> Elastic ERROR: {str(e)}")
        return False


def verify_sarvam():
    """Step 3: Test Sarvam AI API translation endpoint."""
    print("\n[3/3] Testing Sarvam AI Connectivity...")
    sarvam_key = os.getenv("SARVAM_API_KEY")

    if not sarvam_key:
        print("  --> Sarvam AI ERROR: Missing SARVAM_API_KEY in .env")
        return False

    headers = {
        "api-subscription-key": sarvam_key,
        "Content-Type": "application/json",
    }
    payload = {
        "input": "Security alert test.",
        "source_language_code": "en-IN",
        "target_language_code": "ta-IN",
        "mode": "formal",
    }

    try:
        res = requests.post(
            "https://api.sarvam.ai/translate",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if res.status_code == 200:
            translation = res.json().get("translated_text", "")
            print(f"  --> Sarvam AI OK! Tamil Output: {translation}")
            return True
        else:
            print(f"  --> Sarvam AI ERROR: HTTP {res.status_code} - {res.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  --> Sarvam AI Network ERROR: {str(e)}")
        return False


if __name__ == "__main__":
    m_ok = verify_aws_and_mantle()
    e_ok = verify_elastic()
    s_ok = verify_sarvam()

    if m_ok and e_ok and s_ok:
        print("\nAll systems operational! Ready to proceed to Step 2 (ECS Taint Schema & Index Mapping).")
    else:
        print("\nOne or more checks failed. Review the logs above to resolve.")
        sys.exit(1)