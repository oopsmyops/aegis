# AEGIS API Reference

This document provides detailed API reference for AEGIS components.

## Core Components

### AIPolicySelector

The main orchestrator for AI-powered policy selection and customization.

```python
from ai.ai_policy_selector import AIPolicySelector
from ai.bedrock_client import BedrockClient

# Initialize Bedrock client
bedrock_client = BedrockClient(config)

# Create AI policy selector
ai_selector = AIPolicySelector(
    bedrock_client=bedrock_client,
    policy_catalog_path="./policy-catalog",
    output_directory="./recommended-policies",
    config=config
)

# Run Two-Phase policy selection
selected_policies = ai_selector.select_policies_two_phase(
    cluster_info=cluster_info,
    requirements=requirements,
    policy_index=policy_index,
    target_count=20
)
```

#### Methods

##### `select_policies_two_phase(cluster_info, requirements, policy_index, target_count=20)`

Executes the complete Two-Phase AI policy selection process.

**Parameters:**
- `cluster_info` (ClusterInfo): Cluster information from discovery
- `requirements` (GovernanceRequirements): Governance requirements from questionnaire
- `policy_index` (PolicyIndex): Policy catalog index
- `target_count` (int): Target number of policies to select (default: 20)

**Returns:**
- `List[PolicyCatalogEntry]`: Selected and customized policies

**Raises:**
- `AISelectionError`: When AI selection fails
- `ValidationError`: When policy validation fails

##### `phase_one_filter(cluster_info, requirements, policy_index)`

Phase 1: Lightweight filtering of all policies to candidates.

**Parameters:**
- `cluster_info` (ClusterInfo): Cluster information
- `requirements` (GovernanceRequirements): Governance requirements  
- `policy_index` (PolicyIndex): Complete policy index

**Returns:**
- `List[str]`: List of candidate policy names

##### `phase_two_select(cluster_info, requirements, candidate_names, target_count=20)`

Phase 2: Detailed selection from candidates to final policies.

**Parameters:**
- `cluster_info` (ClusterInfo): Cluster information
- `requirements` (GovernanceRequirements): Governance requirements
- `candidate_names` (List[str]): Candidate policy names from Phase 1
- `target_count` (int): Target number of final policies

**Returns:**
- `List[PolicyCatalogEntry]`: Final selected policies

### BedrockClient

AWS Bedrock client with comprehensive error handling and fallback support.

```python
from ai.bedrock_client import BedrockClient

# Initialize client
bedrock_client = BedrockClient(config)

# Send request with automatic retries and fallbacks
response = bedrock_client.send_request_with_fallback(
    prompt="Your prompt here",
    max_tokens=4000,
    temperature=0.1
)
```

#### Methods

##### `send_request(prompt, max_tokens=None, temperature=None)`

Send a single request to AWS Bedrock.

**Parameters:**
- `prompt` (str): The prompt to send
- `max_tokens` (int, optional): Maximum tokens for response
- `temperature` (float, optional): Temperature for response generation

**Returns:**
- `str`: Response text from the model

##### `send_request_with_fallback(prompt, max_tokens=None, temperature=None)`

Send request with comprehensive fallback handling.

**Parameters:**
- `prompt` (str): The prompt to send
- `max_tokens` (int, optional): Maximum tokens for response
- `temperature` (float, optional): Temperature for response generation

**Returns:**
- `str`: Response text from the model (primary or fallback)

**Raises:**
- `AISelectionError`: When all models fail

### ClusterDiscovery

Automated Kubernetes cluster discovery and analysis.

```python
from discovery.discovery import ClusterDiscovery

# Initialize discovery
discovery = ClusterDiscovery()

# Discover cluster information
cluster_data = discovery.discover_cluster()

# Export to YAML
discovery.export_to_yaml(cluster_data, "cluster-discovery.yaml")
```

#### Methods

##### `discover_cluster()`

Perform comprehensive cluster discovery.

**Returns:**
- `Dict[str, Any]`: Complete cluster information including:
  - `discovery_metadata`: Tool metadata and timestamp
  - `cluster_info`: Basic cluster information
  - `managed_service`: Detected managed service (EKS, AKS, GKE)
  - `third_party_controllers`: List of detected controllers
  - `resources`: Resource counts and information
  - `security_features`: Security configuration details

##### `detect_managed_service()`

Detect if cluster is running on a managed Kubernetes service.

**Returns:**
- `Optional[str]`: Managed service name ('eks', 'aks', 'gke') or None

##### `scan_third_party_controllers()`

Scan for third-party controllers and operators.

**Returns:**
- `List[Dict[str, Any]]`: List of detected controllers with metadata

### QuestionnaireRunner

Interactive governance requirements gathering system.

```python
from questionnaire.questionnaire_runner import QuestionnaireRunner
from questionnaire.question_bank import QuestionBank

# Initialize questionnaire
bank = QuestionBank()
runner = QuestionnaireRunner(bank)

# Run interactive questionnaire
requirements = runner.run_questionnaire()

# Get summary
summary = runner.get_summary()
```

#### Methods

##### `run_questionnaire()`

Execute the complete interactive questionnaire.

**Returns:**
- `GovernanceRequirements`: Collected governance requirements

##### `get_summary()`

Get summary of questionnaire responses.

**Returns:**
- `Dict[str, Any]`: Summary including:
  - `total_questions`: Number of questions asked
  - `yes_answers`: Number of "yes" responses
  - `no_answers`: Number of "no" responses
  - `categories`: List of categories covered

### PolicyCatalogManager

Policy catalog management and GitHub repository processing.

```python
from catalog.catalog_manager import PolicyCatalogManager

# Initialize catalog manager
catalog_manager = PolicyCatalogManager(config)

# Create catalog from repositories
repo_urls = ["https://github.com/kyverno/policies"]
catalog_manager.create_catalog_from_repos(repo_urls)

# Build policy index
policy_index = catalog_manager.build_policy_index()

# Get detailed policies
detailed_policies = catalog_manager.get_policies_detailed(policy_names)
```

#### Methods

##### `create_catalog_from_repos(repo_urls)`

Create policy catalog from GitHub repositories.

**Parameters:**
- `repo_urls` (List[str]): List of GitHub repository URLs

##### `build_policy_index()`

Build lightweight policy index for AI processing.

**Returns:**
- `PolicyIndex`: Indexed policy catalog

##### `get_policies_detailed(policy_names)`

Get detailed information for specific policies.

**Parameters:**
- `policy_names` (List[str]): List of policy names

**Returns:**
- `List[Dict[str, Any]]`: Detailed policy information

### KyvernoValidator

Kyverno policy validation and test case management.

```python
from ai.kyverno_validator import KyvernoValidator

# Initialize validator
validator = KyvernoValidator(bedrock_client, enable_ai_fixes=True)

# Validate policies
report = validator.validate_policies("./recommended-policies")

# Save validation report
validator.save_validation_report(report, "validation-report.yaml")
```

#### Methods

##### `validate_policies(policies_directory)`

Validate all policies in a directory using Kyverno CLI.

**Parameters:**
- `policies_directory` (str): Path to directory containing policies

**Returns:**
- `Dict[str, Any]`: Validation report with results and statistics

##### `check_kyverno_available()`

Check if Kyverno CLI is available.

**Returns:**
- `bool`: True if Kyverno CLI is available

## Data Models

### ClusterInfo

Represents comprehensive cluster information.

```python
from models import ClusterInfo, ThirdPartyController, ControllerType

cluster_info = ClusterInfo(
    version="1.28.0",
    managed_service="EKS",
    node_count=3,
    namespace_count=12,
    third_party_controllers=[
        ThirdPartyController(
            name="nginx-ingress-controller",
            type=ControllerType.INGRESS,
            namespace="ingress-nginx"
        )
    ],
    security_features={"rbac_enabled": True},
    compliance_frameworks=["CIS", "NIST"]
)
```

### GovernanceRequirements

Represents governance requirements from questionnaire.

```python
from models import GovernanceRequirements, RequirementAnswer

requirements = GovernanceRequirements(
    answers=[
        RequirementAnswer(
            question_id="img_registry_enforcement",
            answer=True,
            category="image_security"
        )
    ],
    registries=["docker.io", "gcr.io"],
    compliance_frameworks=["CIS"],
    custom_labels={"env": "production"}
)
```

### PolicyCatalogEntry

Represents a policy in the catalog.

```python
from models import PolicyCatalogEntry

policy = PolicyCatalogEntry(
    name="require-pod-resources",
    category="best-practices",
    description="Require resource requests and limits",
    relative_path="best-practices/require-pod-resources.yaml",
    test_directory="best-practices/require-pod-resources",
    source_repo="https://github.com/kyverno/policies",
    tags=["resources", "limits"]
)
```

### RecommendedPolicy

Represents a recommended policy with customizations.

```python
from models import RecommendedPolicy

recommended = RecommendedPolicy(
    original_policy=policy_catalog_entry,
    customized_content="# Policy YAML content",
    test_content="# Test YAML content",
    category="resource-management",
    validation_status="passed",
    customizations_applied=["registry_replacement"]
)
```

## Configuration

### Complete Configuration Schema

```yaml
# Cluster connection
cluster:
  kubeconfig_path: ~/.kube/config  # Path to kubeconfig file
  context: null                    # Kubernetes context (null = current)
  timeout: 60                      # Connection timeout in seconds

# Questionnaire settings
questionnaire:
  total_questions: 19              # Number of questions (fixed)

# Policy catalog
catalog:
  local_storage: ./policy-catalog  # Local catalog directory
  index_file: ./policy-catalog/policy-index.json  # Index file path
  repositories:                    # GitHub repositories
  - url: https://github.com/kyverno/policies
    branch: main

# AI configuration
ai:
  provider: aws-bedrock            # AI provider (currently only aws-bedrock)
  model: amazon.nova-pro-v1:0      # Primary AI model
  region: us-east-1                # AWS region
  max_tokens: 4000                 # Maximum tokens per request
  temperature: 0.1                 # Response temperature (0.0-1.0)
  
  # Policy selection
  policy_count:
    total_target: 20               # Target number of policies
  
  # Two-Phase selection
  two_phase_selection:
    enabled: true                  # Enable Two-Phase selection
    phase_one_candidates: 150      # Max candidates from Phase 1
    phase_one_max_tokens: 2000     # Phase 1 token limit
    phase_one_temperature: 0.1     # Phase 1 temperature
    phase_two_max_tokens: 4000     # Phase 2 token limit
    phase_two_temperature: 0.1     # Phase 2 temperature
  
  # Error handling
  error_handling:
    enable_fallbacks: true         # Enable fallback models
    max_retry_attempts: 3          # Max retry attempts
    fallback_models:               # Fallback model list
    - anthropic.claude-3-haiku-20240307-v1:0
    - amazon.nova-lite-v1:0
    emergency_selection: true      # Enable rule-based emergency selection

# Output settings
output:
  directory: ./recommended-policies  # Output directory
  dynamic_categories: true          # Use AI-determined categories
  include_tests: true               # Include test files
  validate_policies: false          # Run validation by default
  fix_policies: false               # Enable AI policy fixing

# Logging
logging:
  level: INFO                      # Log level (DEBUG, INFO, WARNING, ERROR)
  file: ./aegis.log               # Log file path
```

## Error Handling

### Exception Hierarchy

```python
from exceptions import (
    AegisError,           # Base exception
    ClusterDiscoveryError,  # Cluster discovery errors
    QuestionnaireError,     # Questionnaire errors
    CatalogError,          # Catalog management errors
    AISelectionError,      # AI selection errors
    ValidationError,       # Policy validation errors
    ConfigurationError     # Configuration errors
)
```

### Error Handling Best Practices

1. **Catch specific exceptions** rather than generic Exception
2. **Use fallback mechanisms** for external service failures
3. **Log errors with context** for debugging
4. **Provide actionable error messages** to users
5. **Implement retry logic** for transient failures

```python
try:
    response = bedrock_client.send_request_with_fallback(prompt)
except AISelectionError as e:
    logger.error(f"AI selection failed: {e}")
    # Implement fallback logic
    response = fallback_selection(cluster_info, requirements)
```

## Testing

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific component
python -m pytest tests/test_ai_selector.py -v

# Integration tests
python -m pytest tests/integration/ -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Test Fixtures

Use provided test fixtures for consistent testing:

```python
from tests.fixtures import (
    create_sample_cluster_info,
    create_sample_governance_requirements,
    create_sample_policy_catalog_entries
)

def test_my_function():
    cluster_info = create_sample_cluster_info()
    requirements = create_sample_governance_requirements()
    # Your test code here
```

## CLI Reference

### Command Structure

```bash
python main.py <command> [options]
```

### Available Commands

- `discover` - Cluster discovery
- `questionnaire` - Interactive requirements gathering
- `catalog` - Policy catalog management
- `recommend` - AI policy recommendation
- `validate` - Policy validation
- `run` - Execute complete workflow
- `config` - Configuration management
- `version` - Show version information

### Global Options

- `--help` - Show help message
- `--verbose` - Enable verbose output
- `--config <file>` - Use specific configuration file

For detailed command options, use `python main.py <command> --help`.