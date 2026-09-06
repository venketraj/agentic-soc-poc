import os
import sys
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

INDEX_NAME = "agent-runtime-telemetry"

def create_telemetry_index():
    es_url = os.getenv("ELASTICSEARCH_URL")
    api_key = os.getenv("ELASTIC_API_KEY")

    if not es_url or not api_key:
        print("[!] Missing ELASTICSEARCH_URL or ELASTIC_API_KEY.")
        sys.exit(1)

    es = Elasticsearch(es_url, api_key=api_key)

    index_mapping = {
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "trace": {
                    "properties": {
                        "id": {"type": "keyword"}
                    }
                },
                "span": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "parent_id": {"type": "keyword"}
                    }
                },
                "session": {
                    "properties": {
                        "id": {"type": "keyword"}
                    }
                },
                "agent": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "role": {"type": "keyword"}
                    }
                },
                "action": {
                    "properties": {
                        "name": {"type": "keyword"},
                        "type": {"type": "keyword"},
                        "cardinality": {"type": "long"},
                        "parameters": {"type": "object", "enabled": False}
                    }
                },
                "taint": {
                    "properties": {
                        "is_tainted": {"type": "boolean"},
                        "origin": {"type": "keyword"},
                        "trust_level": {"type": "keyword"},
                        "source_span_id": {"type": "keyword"},
                        "metadata": {
                            "properties": {
                                "language": {"type": "keyword"},
                                "source_ref": {"type": "keyword"}
                            }
                        }
                    }
                }
            }
        }
    }

    print(f"[*] Checking if index '{INDEX_NAME}' exists...")
    if es.indices.exists(index=INDEX_NAME):
        print(f"[-] Index '{INDEX_NAME}' already exists. Deleting for fresh setup...")
        es.indices.delete(index=INDEX_NAME)

    print(f"[+] Creating index '{INDEX_NAME}' with ECS Taint Schema...")
    response = es.indices.create(index=INDEX_NAME, body=index_mapping)
    print(f"  --> Elastic Index Created: {response.get('acknowledged', False)}")

if __name__ == "__main__":
    create_telemetry_index()