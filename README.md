# AEGIS - AI Enabled Governance Insights & Suggestions

AEGIS is a comprehensive CLI tool that automates Kubernetes cluster governance by combining intelligent cluster discovery, interactive requirement gathering, policy catalog management, and AI-powered policy selection and customization.

Named after the protective shield in Greek mythology, AEGIS aligns with Kyverno's mission to secure Kubernetes workloads through intelligent policy recommendation and validation.

## Features

- **Automated Cluster Discovery**: Comprehensive cluster analysis including third-party controllers and managed service detection
- **Interactive Requirements Gathering**: Targeted questionnaire system for governance requirements
- **Policy Catalog Management**: Automated policy catalog creation from GitHub repositories
- **AI-Powered Policy Selection**: AWS Bedrock integration for intelligent policy recommendation and customization
- **Policy Validation**: Automated Kyverno policy testing and validation

## Installation

```bash
# Install from source
git clone <repository-url>
cd aegis-cli
pip install -r requirements.txt
pip install -e .

# Or install from PyPI (when available)
pip install aegis-cli
```

## Quick Start

```bash
# Initialize configuration
aegis config --init

# Run complete workflow
aegis run --all

# Or run individual commands
aegis discover                    # Cluster discovery
aegis questionnaire              # Interactive requirements
aegis catalog --repos <urls>    # Build policy catalog
aegis recommend                  # AI policy selection
```

## Configuration

AEGIS uses YAML configuration files. The default configuration locations are:
- `./aegis-config.yaml`
- `~/.aegis/config.yaml`
- `/etc/aegis/config.yaml`

Example configuration:
```yaml
cluster:
  kubeconfig_path: ~/.kube/config
  context: null
  timeout: 60

ai:
  provider: aws-bedrock
  model: anthropic.claude-3-sonnet-20240229-v1:0
  region: us-east-1

output:
  directory: ./recommended-policies
  validate_policies: true
```

## Requirements

- Python 3.8+
- Kubernetes cluster access
- AWS credentials (for Bedrock integration)
- Kyverno CLI (for policy validation)

## Architecture

AEGIS consists of four main components:
1. **Cluster Discovery Engine** - Automated cluster analysis
2. **Interactive Questionnaire System** - Requirement gathering
3. **Policy Catalog Manager** - GitHub repository processing
4. **AI Policy Selector** - Bedrock-powered policy selection

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.