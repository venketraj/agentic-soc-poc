import json
import os
import unittest
from unittest.mock import patch

from botocore.exceptions import ClientError

import verify_connection


class VerifyBedrockNovaLiteTests(unittest.TestCase):
    @patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret", "AWS_DEFAULT_REGION": "us-east-1"}, clear=False)
    @patch("boto3.client")
    def test_uses_amazon_nova_lite_model(self, mock_boto_client):
        mock_bedrock = mock_boto_client.return_value
        response_body = {
            "output": {
                "message": {
                    "content": [{"text": "READY"}]
                }
            }
        }
        mock_bedrock.invoke_model.return_value = {
            "body": type("Body", (), {"read": lambda self: json.dumps(response_body).encode()})()
        }

        self.assertTrue(verify_connection.verify_bedrock())
        mock_bedrock.invoke_model.assert_called_once()
        self.assertEqual(mock_bedrock.invoke_model.call_args.kwargs["modelId"], "amazon.nova-2-lite-v1:0")


if __name__ == "__main__":
    unittest.main()
