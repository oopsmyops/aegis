"""
AWS Bedrock client for AI-powered policy selection and customization.
Handles communication with AWS Bedrock API with comprehensive error handling.
"""

import json
import logging
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from interfaces import BedrockClientInterface
from exceptions import AISelectionError, NetworkError


class BedrockClient(BedrockClientInterface):
    """AWS Bedrock client for AI policy operations."""
    
    def __init__(self, region: str = "us-east-1", model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"):
        """Initialize Bedrock client."""
        self.region = region
        self.model_id = model_id
        self.logger = logging.getLogger(__name__)
        
        try:
            self.client = boto3.client('bedrock-runtime', region_name=region)
        except NoCredentialsError:
            raise AISelectionError(
                "AWS credentials not found",
                "Please configure AWS credentials using AWS CLI, environment variables, or IAM roles"
            )
        except Exception as e:
            raise AISelectionError(f"Failed to initialize Bedrock client: {e}")
    
    def send_request(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.1, 
                     retry_count: int = 3, timeout: int = 60) -> str:
        """Send request to AWS Bedrock and return response with comprehensive error handling."""
        if not prompt.strip():
            raise AISelectionError("Empty prompt provided")
        
        # Validate parameters
        if max_tokens <= 0 or max_tokens > 100000:
            raise AISelectionError(f"Invalid max_tokens: {max_tokens}. Must be between 1 and 100000")
        
        if temperature < 0 or temperature > 1:
            raise AISelectionError(f"Invalid temperature: {temperature}. Must be between 0 and 1")
        
        # Prepare request body based on model type
        if "claude" in self.model_id.lower():
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
        elif "nova" in self.model_id.lower():
            # Amazon Nova model format
            body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "inferenceConfig": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9
                }
            }
        else:
            # Generic format for other models
            body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature,
                    "topP": 0.9
                }
            }
        
        # Retry logic with exponential backoff
        import time
        for attempt in range(retry_count):
            try:
                self.logger.info(f"Sending request to Bedrock model: {self.model_id} (attempt {attempt + 1}/{retry_count})")
                
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json"
                )
                
                response_body = json.loads(response['body'].read())
                
                # Extract response text based on model type
                if "claude" in self.model_id.lower():
                    if 'content' in response_body and response_body['content']:
                        response_text = response_body['content'][0]['text']
                    else:
                        raise AISelectionError("Invalid response format from Claude model")
                elif "nova" in self.model_id.lower():
                    # Amazon Nova model response format
                    if 'output' in response_body and 'message' in response_body['output']:
                        message = response_body['output']['message']
                        if 'content' in message and message['content']:
                            response_text = message['content'][0]['text']
                        else:
                            raise AISelectionError("Invalid response format from Nova model")
                    else:
                        raise AISelectionError("Invalid response format from Nova model")
                else:
                    # Generic format for other models
                    if 'results' in response_body and response_body['results']:
                        response_text = response_body['results'][0]['outputText']
                    else:
                        raise AISelectionError("Invalid response format from model")
                
                # Validate response
                if not response_text or not response_text.strip():
                    raise AISelectionError("Empty response from model")
                
                self.logger.info(f"Successfully received response from Bedrock (length: {len(response_text)})")
                return response_text.strip()
                        
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                
                if error_code == 'ValidationException':
                    raise AISelectionError(f"Invalid request parameters: {error_message}")
                elif error_code == 'ResourceNotFoundException':
                    raise AISelectionError(f"Model not found: {self.model_id}")
                elif error_code == 'AccessDeniedException':
                    raise AISelectionError(
                        "Access denied to Bedrock service",
                        "Please ensure your AWS credentials have bedrock:InvokeModel permissions"
                    )
                elif error_code == 'ThrottlingException':
                    if attempt < retry_count - 1:
                        wait_time = (2 ** attempt) + 1  # Exponential backoff
                        self.logger.warning(f"Request throttled, retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise NetworkError(f"Request throttled after {retry_count} attempts: {error_message}")
                elif error_code == 'ServiceUnavailableException':
                    if attempt < retry_count - 1:
                        wait_time = (2 ** attempt) + 1
                        self.logger.warning(f"Service unavailable, retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise NetworkError(f"Service unavailable after {retry_count} attempts: {error_message}")
                else:
                    raise AISelectionError(f"Bedrock API error ({error_code}): {error_message}")
                    
            except BotoCoreError as e:
                if attempt < retry_count - 1:
                    wait_time = (2 ** attempt) + 1
                    self.logger.warning(f"Network error, retrying in {wait_time} seconds: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    raise NetworkError(f"Network error after {retry_count} attempts: {e}")
            except json.JSONDecodeError as e:
                if attempt < retry_count - 1:
                    wait_time = (2 ** attempt) + 1
                    self.logger.warning(f"JSON decode error, retrying in {wait_time} seconds: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    raise AISelectionError(f"Failed to parse Bedrock response after {retry_count} attempts: {e}")
            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = (2 ** attempt) + 1
                    self.logger.warning(f"Unexpected error, retrying in {wait_time} seconds: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    raise AISelectionError(f"Unexpected error after {retry_count} attempts: {e}")
        
        # This should never be reached due to the retry logic above
        raise AISelectionError("Failed to get response after all retry attempts")
    
    def is_available(self) -> bool:
        """Check if Bedrock service is available."""
        try:
            # Simple test request to check availability
            test_prompt = "Hello"
            self.send_request(test_prompt, max_tokens=10)
            return True
        except Exception as e:
            self.logger.warning(f"Bedrock service not available: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            "model_id": self.model_id,
            "region": self.region,
            "available": self.is_available()
        }
    
    def validate_model_id(self, model_id: str) -> bool:
        """Validate if a model ID is supported."""
        supported_models = [
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-v2:1",
            "anthropic.claude-v2",
            "anthropic.claude-instant-v1",
            "amazon.nova-pro-v1:0",
            "amazon.nova-lite-v1:0",
            "amazon.nova-micro-v1:0"
        ]
        return model_id in supported_models
    
    def send_request_with_fallback(self, prompt: str, max_tokens: int = 4000, 
                                 temperature: float = 0.1, fallback_models: list = None) -> str:
        """Send request with automatic fallback to alternative models."""
        if fallback_models is None:
            fallback_models = [
                "anthropic.claude-3-haiku-20240307-v1:0",
                "amazon.nova-lite-v1:0",
                "anthropic.claude-instant-v1"
            ]
        
        # Try primary model first
        try:
            return self.send_request(prompt, max_tokens, temperature)
        except Exception as primary_error:
            self.logger.warning(f"Primary model {self.model_id} failed: {primary_error}")
            
            # Try fallback models
            original_model = self.model_id
            for fallback_model in fallback_models:
                if fallback_model == original_model:
                    continue
                    
                try:
                    self.logger.info(f"Trying fallback model: {fallback_model}")
                    self.model_id = fallback_model
                    result = self.send_request(prompt, max_tokens, temperature)
                    self.logger.info(f"Successfully used fallback model: {fallback_model}")
                    return result
                except Exception as fallback_error:
                    self.logger.warning(f"Fallback model {fallback_model} failed: {fallback_error}")
                    continue
                finally:
                    # Restore original model
                    self.model_id = original_model
            
            # If all models failed, raise the original error
            raise AISelectionError(f"All models failed. Primary error: {primary_error}")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Bedrock service with detailed diagnostics."""
        test_results = {
            "service_available": False,
            "model_accessible": False,
            "credentials_valid": False,
            "region_valid": False,
            "error_details": []
        }
        
        try:
            # Test basic service availability
            self.client.list_foundation_models()
            test_results["service_available"] = True
            test_results["credentials_valid"] = True
            test_results["region_valid"] = True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                test_results["error_details"].append("Access denied - check IAM permissions")
            elif error_code == 'UnauthorizedOperation':
                test_results["credentials_valid"] = False
                test_results["error_details"].append("Invalid credentials")
            else:
                test_results["error_details"].append(f"Service error: {error_code}")
        except NoCredentialsError:
            test_results["credentials_valid"] = False
            test_results["error_details"].append("No AWS credentials found")
        except Exception as e:
            test_results["error_details"].append(f"Connection error: {e}")
        
        # Test model accessibility
        if test_results["service_available"]:
            try:
                test_prompt = "Hello"
                self.send_request(test_prompt, max_tokens=10)
                test_results["model_accessible"] = True
            except Exception as e:
                test_results["error_details"].append(f"Model test failed: {e}")
        
        return test_results
    
    def get_optimal_token_limit(self, prompt_length: int) -> int:
        """Calculate optimal token limit based on prompt length and model capabilities."""
        # Rough estimation: 1 token ≈ 4 characters
        estimated_prompt_tokens = prompt_length // 4
        
        # Model-specific token limits
        model_limits = {
            "claude-3-sonnet": 200000,
            "claude-3-haiku": 200000,
            "claude-v2": 100000,
            "claude-instant": 100000,
            "nova-pro": 300000,
            "nova-lite": 300000,
            "nova-micro": 128000
        }
        
        # Find model limit
        max_model_tokens = 100000  # Default fallback
        for model_key, limit in model_limits.items():
            if model_key in self.model_id.lower():
                max_model_tokens = limit
                break
        
        # Reserve tokens for response (at least 1000, up to 25% of limit)
        response_tokens = max(1000, min(max_model_tokens // 4, 4000))
        
        # Calculate available tokens for response
        available_tokens = max_model_tokens - estimated_prompt_tokens - 1000  # Safety buffer
        
        return min(available_tokens, response_tokens)
    
    def chunk_large_request(self, prompt: str, max_chunk_size: int = 50000) -> List[str]:
        """Split large prompts into manageable chunks."""
        if len(prompt) <= max_chunk_size:
            return [prompt]
        
        chunks = []
        current_pos = 0
        
        while current_pos < len(prompt):
            # Find a good breaking point (end of sentence or paragraph)
            end_pos = min(current_pos + max_chunk_size, len(prompt))
            
            if end_pos < len(prompt):
                # Look for sentence or paragraph breaks
                for break_char in ['\n\n', '\n', '. ', '! ', '? ']:
                    last_break = prompt.rfind(break_char, current_pos, end_pos)
                    if last_break > current_pos:
                        end_pos = last_break + len(break_char)
                        break
            
            chunk = prompt[current_pos:end_pos].strip()
            if chunk:
                chunks.append(chunk)
            
            current_pos = end_pos
        
        return chunks