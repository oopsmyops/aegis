# AEGIS AI Policy Selection System

This module implements the AI-powered policy selection and customization system for AEGIS, as specified in task 5 of the implementation plan.

## Components Implemented

### 1. BedrockClient (`bedrock_client.py`)
- **Purpose**: AWS Bedrock API communication with comprehensive error handling
- **Features**:
  - Support for Claude and other Bedrock models
  - Robust error handling for various AWS API errors
  - Availability checking and model validation
  - Configurable parameters (temperature, max_tokens)

### 2. PolicyCustomizer (`policy_customizer.py`)
- **Purpose**: Registry replacement, label modification, and parameter customization
- **Features**:
  - Registry pattern replacement in policy YAML
  - Custom label injection into metadata and templates
  - Compliance framework annotations
  - Requirement-based policy strengthening
  - YAML structure validation

### 3. CategoryDeterminer (`category_determiner.py`)
- **Purpose**: AI-powered dynamic category organization
- **Features**:
  - AI-driven category determination based on cluster context
  - Intelligent policy-to-category assignment
  - Fallback category logic when AI is unavailable
  - Context-aware category naming

### 4. AIPolicySelector (`ai_policy_selector.py`)
- **Purpose**: Main orchestrator for policy selection and customization
- **Features**:
  - AI-powered policy selection from catalog index
  - Complete workflow orchestration
  - Fallback rule-based selection
  - Policy validation and fixing
  - Comprehensive recommendation generation

## Key Features

### AI Integration
- Uses AWS Bedrock (Claude models) for intelligent decision making
- Graceful fallback to rule-based logic when AI is unavailable
- Context-aware prompts for better AI responses
- Token-efficient policy sampling for large catalogs

### Policy Customization
- Registry allowlist enforcement
- Custom label injection
- Compliance framework alignment
- Security context strengthening
- Resource limit enforcement

### Error Handling
- Comprehensive exception hierarchy
- Graceful degradation on failures
- Detailed logging for debugging
- Validation at multiple levels

### Scalability
- Efficient policy sampling for large catalogs (350+ policies)
- Memory-efficient YAML processing
- Configurable batch sizes and limits
- Concurrent processing support

## Usage Example

```python
from ai import BedrockClient, AIPolicySelector
from models import ClusterInfo, GovernanceRequirements, PolicyIndex

# Initialize components
bedrock_client = BedrockClient(region="us-east-1")
ai_selector = AIPolicySelector(bedrock_client)

# Generate recommendations
recommendation = ai_selector.generate_complete_recommendation(
    cluster_info=cluster_info,
    requirements=requirements,
    policy_index=policy_index,
    target_count=20
)

# Access results
print(f"Selected {len(recommendation.recommended_policies)} policies")
print(f"Categories: {recommendation.categories}")
print(f"Validation: {recommendation.validation_summary}")
```

## Testing

### Integration Tests (`test_ai_integration.py`)
- Tests all components with mock data
- Validates fallback behavior
- Ensures error handling works correctly

### Demo Workflow (`demo_ai_workflow.py`)
- Complete end-to-end demonstration
- Uses real policy index data
- Shows both AI and fallback modes

## Configuration

The AI system respects the following configuration parameters:

```yaml
ai:
  provider: "aws-bedrock"
  model: "anthropic.claude-3-sonnet-20240229-v1:0"
  region: "us-east-1"
  max_tokens: 4000
  temperature: 0.1
  policy_count:
    min_best_practices: 10
    total_target: 20
    max_total: 30
```

## Requirements Addressed

This implementation addresses the following requirements from the specification:

- **4.1**: AI analyzes cluster-discovery.yaml to understand cluster characteristics
- **4.2**: AWS Bedrock model determines applicable policy categories and selects from catalog
- **4.3**: AI modifies registries, labels, and parameters based on requirements
- **4.4**: AI generates test cases for policies lacking tests
- **4.6**: AI provides fallback recommendations when Bedrock is unavailable

## Error Handling

The system handles various error scenarios:

- AWS credential issues
- Bedrock service unavailability
- Invalid policy YAML
- Missing policy files
- Network connectivity issues
- Token limit exceeded
- Invalid AI responses

## Performance Considerations

- Policy sampling limits AI token usage
- Efficient YAML parsing and modification
- Concurrent policy processing
- Memory-efficient data structures
- Configurable timeouts and retries

## Security

- No sensitive data stored permanently
- AWS credentials handled through standard SDK
- Policy validation before output
- Audit mode by default for generated policies
- Comprehensive logging for security monitoring