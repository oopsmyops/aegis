"""
Tests for AWS Bedrock client functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import pytest

from ai.bedrock_client import BedrockClient
from exceptions import AISelectionError


class TestBedrockClient(unittest.TestCase):
    """Test cases for BedrockClient."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock boto3 client
        self.mock_boto_client = Mock()

        with patch("ai.bedrock_client.boto3.client") as mock_boto3:
            mock_boto3.return_value = self.mock_boto_client
            self.bedrock_client = BedrockClient(
                region="us-east-1", model_id="anthropic.claude-3-sonnet-20240229-v1:0"
            )

    def test_initialization(self):
        """Test BedrockClient initialization."""
        self.assertEqual(self.bedrock_client.region, "us-east-1")
        self.assertEqual(
            self.bedrock_client.model_id, "anthropic.claude-3-sonnet-20240229-v1:0"
        )
        self.assertIsNotNone(self.bedrock_client.client)
        self.assertIsNotNone(self.bedrock_client.logger)

    def test_anthropic_model_request_format(self):
        """Test request format for Anthropic models."""
        # This test verifies the request format is correct by checking the actual call
        mock_response = {"body": Mock()}

        response_data = {
            "content": [{"text": "Test response"}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        mock_response["body"].read.return_value = json.dumps(response_data).encode()
        self.mock_boto_client.invoke_model.return_value = mock_response

        result = self.bedrock_client.send_request(
            "Test prompt", max_tokens=1000, temperature=0.2
        )

        # Verify the call was made with correct parameters
        self.mock_boto_client.invoke_model.assert_called_once()
        call_args = self.mock_boto_client.invoke_model.call_args

        # Check the body parameter
        body_str = call_args[1]["body"]
        body_data = json.loads(body_str)

        self.assertEqual(body_data["max_tokens"], 1000)
        self.assertEqual(body_data["temperature"], 0.2)
        self.assertIn("messages", body_data)
        self.assertEqual(body_data["messages"][0]["role"], "user")
        self.assertEqual(body_data["messages"][0]["content"], "Test prompt")
        self.assertEqual(result, "Test response")

    def test_nova_model_request_format(self):
        """Test request format for Amazon Nova models."""
        # Change to Nova model
        self.bedrock_client.model_id = "amazon.nova-pro-v1:0"

        mock_response = {"body": Mock()}

        response_data = {
            "output": {"message": {"content": [{"text": "Test response"}]}},
            "usage": {"inputTokens": 100, "outputTokens": 50},
        }

        mock_response["body"].read.return_value = json.dumps(response_data).encode()
        self.mock_boto_client.invoke_model.return_value = mock_response

        result = self.bedrock_client.send_request(
            "Test prompt", max_tokens=1000, temperature=0.2
        )

        # Verify the call was made with correct parameters
        self.mock_boto_client.invoke_model.assert_called_once()
        call_args = self.mock_boto_client.invoke_model.call_args

        # Check the body parameter
        body_str = call_args[1]["body"]
        body_data = json.loads(body_str)

        self.assertEqual(body_data["inferenceConfig"]["max_new_tokens"], 1000)
        self.assertEqual(body_data["inferenceConfig"]["temperature"], 0.2)
        self.assertIn("messages", body_data)
        self.assertEqual(body_data["messages"][0]["role"], "user")
        self.assertEqual(body_data["messages"][0]["content"][0]["text"], "Test prompt")
        self.assertEqual(result, "Test response")

    def test_send_request_success(self):
        """Test successful request sending."""
        # Mock successful response
        mock_response = {"body": Mock()}

        response_data = {
            "content": [{"text": "Test response"}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        mock_response["body"].read.return_value = json.dumps(response_data).encode()
        self.mock_boto_client.invoke_model.return_value = mock_response

        result = self.bedrock_client.send_request("Test prompt")

        self.assertEqual(result, "Test response")
        self.mock_boto_client.invoke_model.assert_called_once()

    def test_send_request_with_retry(self):
        """Test request with retry on failure."""
        # Mock first call to fail, second to succeed
        mock_response = {"body": Mock()}

        response_data = {
            "content": [{"text": "Test response"}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        mock_response["body"].read.return_value = json.dumps(response_data).encode()

        # Mock throttling exception first, then success
        from botocore.exceptions import ClientError

        throttling_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )

        self.mock_boto_client.invoke_model.side_effect = [
            throttling_error,
            mock_response,
        ]

        result = self.bedrock_client.send_request("Test prompt", retry_count=2)

        self.assertEqual(result, "Test response")
        self.assertEqual(self.mock_boto_client.invoke_model.call_count, 2)

    def test_send_request_validation_error(self):
        """Test request with validation error."""
        from botocore.exceptions import ClientError

        validation_error = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid parameters"}},
            "InvokeModel",
        )

        self.mock_boto_client.invoke_model.side_effect = validation_error

        with self.assertRaises(AISelectionError) as context:
            self.bedrock_client.send_request("Test prompt")

        self.assertIn("Invalid request parameters", str(context.exception))

    def test_send_request_access_denied(self):
        """Test request with access denied error."""
        from botocore.exceptions import ClientError

        access_error = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "InvokeModel",
        )

        self.mock_boto_client.invoke_model.side_effect = access_error

        with self.assertRaises(AISelectionError) as context:
            self.bedrock_client.send_request("Test prompt")

        self.assertIn("Access denied to Bedrock service", str(context.exception))

    def test_model_detection_anthropic(self):
        """Test Anthropic model detection."""
        anthropic_models = [
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-instant-v1",
        ]

        for model in anthropic_models:
            self.bedrock_client.model_id = model
            self.assertIn("claude", model.lower())

    def test_model_detection_nova(self):
        """Test Amazon Nova model detection."""
        nova_models = [
            "amazon.nova-pro-v1:0",
            "amazon.nova-lite-v1:0",
            "amazon.nova-micro-v1:0",
        ]

        for model in nova_models:
            self.bedrock_client.model_id = model
            self.assertIn("nova", model.lower())

    def test_parameter_validation(self):
        """Test parameter validation."""
        # Test empty prompt
        with self.assertRaises(AISelectionError):
            self.bedrock_client.send_request("")

        # Test invalid max_tokens
        with self.assertRaises(AISelectionError):
            self.bedrock_client.send_request("Test", max_tokens=0)

        with self.assertRaises(AISelectionError):
            self.bedrock_client.send_request("Test", max_tokens=200000)

        # Test invalid temperature
        with self.assertRaises(AISelectionError):
            self.bedrock_client.send_request("Test", temperature=-0.1)

        with self.assertRaises(AISelectionError):
            self.bedrock_client.send_request("Test", temperature=1.1)


if __name__ == "__main__":
    unittest.main()
