# Agentic SOC POC

Proof-of-concept security operations workflow that combines simulated agent
telemetry, Elastic detection, Bedrock Mantle reasoning, graduated containment,
and multilingual evaluation with Sarvam AI.

## What This Repository Does

The project has two usable entry points:

1. `aws_mantle_test.py` sends a question to an AWS Bedrock Mantle model through
	 its OpenAI-compatible API and prints the answer.
2. `main.py` runs the end-to-end SOC demonstration pipeline:
	 - creates the Elastic telemetry index and mappings;
	 - simulates an agent execution trace and ingests it into Elastic;
	 - runs an ES|QL multi-signal detection query;
	 - executes graduated containment and writes an audit record to S3;
	 - runs the Sarvam-backed multilingual parity evaluation.

This is a demonstration and development POC. The containment code can create
or write to cloud resources, so use a dedicated AWS account, bucket, and least-
privilege credentials when testing it.

## Prerequisites

- Python 3.14 or newer
- `uv`
- An AWS account with access to Bedrock Mantle and S3
- An Elastic Cloud deployment and API key for the full pipeline
- A Sarvam AI API key for the multilingual evaluation
- Network access to the configured services

## Setup

From the repository root:

```powershell
uv sync
```

Create a local `.env` file. It is ignored by Git and must never be committed:

```dotenv
# AWS and Bedrock Mantle
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=replace-me
AWS_SECRET_ACCESS_KEY=replace-me
AWS_BEARER_TOKEN_BEDROCK=replace-me
MANTLE_MODEL=nvidia.nemotron-super-3-120b
MANTLE_MODEL_ID=nvidia.nemotron-super-3-120b

# Elastic Cloud
ELASTICSEARCH_URL=https://your-deployment.elastic.cloud
ELASTIC_API_KEY=replace-me

# S3 audit ledger
AUDIT_LOG_BUCKET=your-dedicated-audit-bucket

# Sarvam AI
SARVAM_API_KEY=replace-me
```

`AWS_BEARER_TOKEN_BEDROCK` is preferred by the Mantle clients. Some scripts
fall back to `AWS_SECRET_ACCESS_KEY` as the API key, while `boto3` uses the AWS
access key and secret for STS and S3 operations. Configure credentials through
your normal AWS credential mechanism where possible, rather than storing long-
lived keys in `.env`.

## Run It

### Ask a Mantle question

Pass a question on the command line:

```powershell
uv run .\aws_mantle_test.py "What is the purpose of a security operations center?"
```

Or start an interactive prompt:

```powershell
uv run .\aws_mantle_test.py
```

The model can be changed without editing code by setting `MANTLE_MODEL` in
`.env`.

### Verify service connections

This checks Bedrock Mantle, Elastic Cloud, and Sarvam AI independently:

```powershell
uv run .\verify_connection.py
```

### Run the full SOC demonstration

After the connection checks pass:

```powershell
uv run .\main.py
```

The pipeline expects the Elastic deployment and S3 bucket to be available and
uses them with the configured credentials. Review the output after each phase;
the ES|QL detection phase must find an incident before containment runs.

## Test

Run the automated tests with:

```powershell
uv run python -m unittest discover -s tests -p "test_*.py"
```

The current test suite verifies the Bedrock Nova Lite model selection in the
connection-check module using mocked AWS calls. The full pipeline tests require
additional service mocks or dedicated integration environments.

## Project Layout

| File | Responsibility |
| --- | --- |
| `main.py` | Orchestrates the end-to-end demo pipeline |
| `aws_mantle_test.py` | Standalone Mantle question-answering client |
| `verify_connection.py` | Connectivity checks for AWS/Mantle, Elastic, and Sarvam |
| `setup_elastic_schema.py` | Creates the Elastic telemetry index and mappings |
| `simulated_agent_run.py` | Generates and ingests simulated agent telemetry |
| `run_esql_detection.py` | Runs the Elastic ES|QL detection step |
| `execute_containment.py` | Performs graduated containment and records the S3 audit ledger |
| `evaluate_multilingual_parity.py` | Evaluates multilingual detection parity with Sarvam |
| `create_elastic_case.py` | Creates an Elastic case from detected incident data |
| `tests/` | Automated unit tests |

## Troubleshooting

- **Mantle authentication errors:** confirm the region, token, model name, and
	Bedrock access. Mantle uses `https://bedrock-mantle.<region>.api.aws/v1`.
- **Elastic errors:** verify `ELASTICSEARCH_URL`, `ELASTIC_API_KEY`, deployment
	status, and that the API key can create indices and run ES|QL.
- **S3 errors:** check the bucket name, region, IAM permissions, and whether the
	bucket already exists. Use a dedicated audit bucket for the POC.
- **Sarvam errors:** confirm `SARVAM_API_KEY` and outbound HTTPS access to
	`https://api.sarvam.ai/translate`.

## Security Notes

- Do not commit `.env`, access keys, bearer tokens, API keys, or generated
	runtime data.
- Use least-privilege IAM policies and short-lived credentials where possible.
- Treat the containment and S3 operations as real cloud actions, even though
	the telemetry source is simulated.
