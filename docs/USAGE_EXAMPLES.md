# AEGIS Usage Examples

This document provides comprehensive usage examples for different scenarios and use cases.

## Table of Contents

1. [Basic Workflow Examples](#basic-workflow-examples)
2. [Advanced Configuration Examples](#advanced-configuration-examples)
3. [Integration Examples](#integration-examples)
4. [Troubleshooting Examples](#troubleshooting-examples)
5. [Automation Examples](#automation-examples)

## Basic Workflow Examples

### Example 1: Complete Workflow for New Cluster

This example shows the complete AEGIS workflow for a new EKS cluster.

```bash
# Step 1: Initialize AEGIS configuration
python main.py config --init

# Step 2: Discover cluster information
python main.py discover --context my-eks-cluster --output cluster-discovery.yaml

# Step 3: Run interactive questionnaire
python main.py questionnaire --input cluster-discovery.yaml

# Step 4: Create policy catalog (one-time setup)
python main.py catalog --repos https://github.com/kyverno/policies

# Step 5: Get AI policy recommendations
python main.py recommend --input cluster-discovery.yaml --count 25 --output ./policies

# Step 6: Validate recommended policies
python main.py validate --directory ./policies --fix
```

**Expected Output Structure:**
```
./
├── aegis-config.yaml           # Configuration file
├── cluster-discovery.yaml     # Cluster info + requirements
├── policy-catalog/             # Downloaded policy catalog
│   ├── policy-index.json      # Policy index
│   └── [policy directories]   # Organized policies
└── policies/                   # Recommended policies
    ├── DEPLOYMENT_GUIDE.md    # Deployment instructions
    ├── SUMMARY.yaml           # Policy summary
    ├── kyverno-validation-report.yaml  # Validation results
    └── [category directories] # Organized by category
```

### Example 2: Quick Start with Defaults

For users who want to get started quickly with minimal configuration.

```bash
# Run complete workflow with defaults
python main.py run --all

# This is equivalent to:
# 1. python main.py discover
# 2. python main.py questionnaire --batch  # Uses defaults
# 3. python main.py catalog --repos https://github.com/kyverno/policies
# 4. python main.py recommend
```

### Example 3: Targeted Policy Selection

Select policies for specific use cases or compliance requirements.

```bash
# Discover cluster
python main.py discover --output cluster-discovery.yaml

# Create custom requirements file
cat > custom-requirements.yaml << EOF
governance_requirements:
  configurations:
    allowed_registries: ["docker.io", "gcr.io", "quay.io"]
    compliance_frameworks: ["CIS", "NIST", "SOC2"]
    required_labels:
      env: "production"
      team: "platform"
      cost-center: "engineering"
EOF

# Merge with cluster discovery
python -c "
import yaml
with open('cluster-discovery.yaml', 'r') as f:
    cluster_data = yaml.safe_load(f)
with open('custom-requirements.yaml', 'r') as f:
    req_data = yaml.safe_load(f)
cluster_data.update(req_data)
with open('cluster-discovery.yaml', 'w') as f:
    yaml.dump(cluster_data, f)
"

# Get recommendations with specific count
python main.py recommend --input cluster-discovery.yaml --count 30 --output ./compliance-policies
```

## Advanced Configuration Examples

### Example 4: Multi-Model AI Configuration

Configure AEGIS to use multiple AI models with fallbacks.

```yaml
# aegis-config.yaml
ai:
  provider: aws-bedrock
  model: amazon.nova-pro-v1:0
  region: us-east-1
  max_tokens: 4000
  temperature: 0.1
  
  policy_count:
    total_target: 25
  
  two_phase_selection:
    enabled: true
    phase_one_candidates: 200
    phase_one_max_tokens: 3000
    phase_two_max_tokens: 5000
  
  error_handling:
    enable_fallbacks: true
    max_retry_attempts: 5
    fallback_models:
    - anthropic.claude-3-sonnet-20240229-v1:0
    - anthropic.claude-3-haiku-20240307-v1:0
    - amazon.nova-lite-v1:0
    emergency_selection: true

output:
  directory: ./recommended-policies
  validate_policies: true
  fix_policies: true
  dynamic_categories: true

logging:
  level: DEBUG
  file: ./aegis-debug.log
```

```bash
# Use the advanced configuration
python main.py recommend --input cluster-discovery.yaml --config ./aegis-config.yaml
```

### Example 5: Custom Policy Catalog

Create a custom policy catalog from multiple sources.

```bash
# Create catalog from multiple repositories
python main.py catalog \
  --repos "https://github.com/kyverno/policies,https://github.com/nirmata/kyverno-policies,https://github.com/your-org/custom-policies" \
  --output ./custom-catalog

# Use custom catalog for recommendations
python main.py recommend \
  --input cluster-discovery.yaml \
  --catalog-path ./custom-catalog \
  --output ./custom-policies
```

### Example 6: Environment-Specific Configuration

Configure AEGIS for different environments (dev, staging, production).

**Development Environment:**
```yaml
# dev-config.yaml
ai:
  model: amazon.nova-lite-v1:0  # Cheaper model for dev
  policy_count:
    total_target: 10            # Fewer policies for dev
  
output:
  validate_policies: false      # Skip validation in dev
  
logging:
  level: DEBUG
```

**Production Environment:**
```yaml
# prod-config.yaml
ai:
  model: amazon.nova-pro-v1:0   # More capable model
  policy_count:
    total_target: 30            # More comprehensive policies
  
  error_handling:
    enable_fallbacks: true
    max_retry_attempts: 5
  
output:
  validate_policies: true       # Always validate in prod
  fix_policies: true
  
logging:
  level: INFO
```

```bash
# Use environment-specific config
python main.py recommend --config ./prod-config.yaml --input cluster-discovery.yaml
```

## Integration Examples

### Example 7: CI/CD Pipeline Integration

Integrate AEGIS into your CI/CD pipeline for automated policy management.

**GitHub Actions Workflow:**
```yaml
# .github/workflows/aegis-policy-update.yml
name: AEGIS Policy Update

on:
  schedule:
    - cron: '0 2 * * 1'  # Weekly on Monday at 2 AM
  workflow_dispatch:

jobs:
  update-policies:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install AEGIS
      run: |
        pip install -r requirements.txt
        pip install -e .
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-east-1
    
    - name: Setup kubectl
      uses: azure/setup-kubectl@v3
      with:
        version: 'v1.28.0'
    
    - name: Configure kubeconfig
      run: |
        aws eks update-kubeconfig --name ${{ secrets.CLUSTER_NAME }} --region us-east-1
    
    - name: Run AEGIS discovery
      run: |
        python main.py discover --output cluster-discovery.yaml
    
    - name: Run AEGIS questionnaire (batch mode)
      run: |
        python main.py questionnaire --input cluster-discovery.yaml --batch
    
    - name: Update policy catalog
      run: |
        python main.py catalog --repos https://github.com/kyverno/policies --refresh
    
    - name: Generate policy recommendations
      run: |
        python main.py recommend --input cluster-discovery.yaml --output ./updated-policies --fix
    
    - name: Create Pull Request
      uses: peter-evans/create-pull-request@v5
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
        commit-message: 'Update Kyverno policies via AEGIS'
        title: 'Automated Policy Update'
        body: |
          This PR contains updated Kyverno policies generated by AEGIS.
          
          ## Changes
          - Updated cluster discovery information
          - Refreshed policy catalog
          - Generated new policy recommendations
          - Validated all policies
          
          Please review the changes before merging.
        branch: aegis-policy-update
```

### Example 8: Terraform Integration

Use AEGIS with Terraform for infrastructure-as-code workflows.

```hcl
# terraform/main.tf
resource "null_resource" "aegis_policy_generation" {
  depends_on = [module.eks_cluster]
  
  provisioner "local-exec" {
    command = <<-EOT
      # Wait for cluster to be ready
      aws eks update-kubeconfig --name ${module.eks_cluster.cluster_name} --region ${var.aws_region}
      
      # Run AEGIS workflow
      cd ${path.module}/../aegis
      python main.py discover --context ${module.eks_cluster.cluster_name} --output cluster-discovery.yaml
      python main.py questionnaire --input cluster-discovery.yaml --batch
      python main.py recommend --input cluster-discovery.yaml --output ../terraform/generated-policies
    EOT
  }
  
  triggers = {
    cluster_version = module.eks_cluster.cluster_version
    node_groups = jsonencode(module.eks_cluster.node_groups)
  }
}

resource "kubernetes_manifest" "kyverno_policies" {
  for_each = fileset("${path.module}/generated-policies", "**/*.yaml")
  
  manifest = yamldecode(file("${path.module}/generated-policies/${each.value}"))
  
  depends_on = [null_resource.aegis_policy_generation]
}
```

### Example 9: ArgoCD Integration

Deploy AEGIS-generated policies using ArgoCD.

```yaml
# argocd/aegis-policies-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: aegis-policies
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/k8s-policies
    targetRevision: HEAD
    path: aegis-generated
  destination:
    server: https://kubernetes.default.svc
    namespace: kyverno
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

**Pre-sync Hook for Policy Generation:**
```yaml
# argocd/aegis-presync-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: aegis-policy-generator
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
spec:
  template:
    spec:
      containers:
      - name: aegis
        image: your-org/aegis:latest
        command:
        - /bin/bash
        - -c
        - |
          # Run AEGIS workflow
          python main.py discover --output /tmp/cluster-discovery.yaml
          python main.py questionnaire --input /tmp/cluster-discovery.yaml --batch
          python main.py recommend --input /tmp/cluster-discovery.yaml --output /workspace/policies
          
          # Commit to git repository
          cd /workspace
          git add .
          git commit -m "Update policies via AEGIS" || true
          git push origin main
        volumeMounts:
        - name: workspace
          mountPath: /workspace
        env:
        - name: AWS_REGION
          value: "us-east-1"
      volumes:
      - name: workspace
        emptyDir: {}
      restartPolicy: Never
```

## Troubleshooting Examples

### Example 10: Debug Mode and Logging

Enable comprehensive debugging for troubleshooting issues.

```yaml
# debug-config.yaml
logging:
  level: DEBUG
  file: ./aegis-debug.log

ai:
  error_handling:
    enable_fallbacks: true
    max_retry_attempts: 1  # Fail fast for debugging
    emergency_selection: false  # Disable to see AI errors
```

```bash
# Run with debug configuration
python main.py recommend --config debug-config.yaml --input cluster-discovery.yaml

# Monitor logs in real-time
tail -f aegis-debug.log
```

### Example 11: Handling Network Issues

Configure AEGIS for environments with network restrictions.

```yaml
# network-restricted-config.yaml
catalog:
  repositories:
  - url: https://internal-git.company.com/policies/kyverno-policies
    branch: main

ai:
  # Use local AI model or proxy
  provider: aws-bedrock
  region: us-east-1
  
  error_handling:
    enable_fallbacks: true
    max_retry_attempts: 10
    emergency_selection: true  # Fall back to rule-based selection
```

### Example 12: Offline Mode

Run AEGIS in environments without internet access.

```bash
# Pre-download policy catalog (on machine with internet)
python main.py catalog --repos https://github.com/kyverno/policies --output ./offline-catalog

# Copy catalog to offline environment
scp -r ./offline-catalog user@offline-machine:/path/to/aegis/

# Run AEGIS offline (uses rule-based selection)
python main.py recommend \
  --input cluster-discovery.yaml \
  --catalog-path ./offline-catalog \
  --no-ai \
  --output ./offline-policies
```

## Automation Examples

### Example 13: Scheduled Policy Updates

Automate regular policy updates using cron jobs.

```bash
#!/bin/bash
# /usr/local/bin/aegis-update.sh

set -e

AEGIS_DIR="/opt/aegis"
CLUSTER_NAME="production-cluster"
OUTPUT_DIR="/var/lib/aegis/policies"
LOG_FILE="/var/log/aegis/update.log"

cd $AEGIS_DIR

echo "$(date): Starting AEGIS policy update" >> $LOG_FILE

# Update kubeconfig
aws eks update-kubeconfig --name $CLUSTER_NAME --region us-east-1

# Run AEGIS workflow
python main.py discover --output cluster-discovery.yaml >> $LOG_FILE 2>&1
python main.py questionnaire --input cluster-discovery.yaml --batch >> $LOG_FILE 2>&1
python main.py catalog --repos https://github.com/kyverno/policies --refresh >> $LOG_FILE 2>&1
python main.py recommend --input cluster-discovery.yaml --output $OUTPUT_DIR --fix >> $LOG_FILE 2>&1

# Apply policies if validation passes
if [ -f "$OUTPUT_DIR/kyverno-validation-report.yaml" ]; then
    SUCCESS_RATE=$(python -c "
import yaml
with open('$OUTPUT_DIR/kyverno-validation-report.yaml', 'r') as f:
    report = yaml.safe_load(f)
print(report['validation_report']['success_rate'])
")
    
    if (( $(echo "$SUCCESS_RATE >= 95.0" | bc -l) )); then
        echo "$(date): Validation passed ($SUCCESS_RATE%), applying policies" >> $LOG_FILE
        kubectl apply -R -f $OUTPUT_DIR/ >> $LOG_FILE 2>&1
    else
        echo "$(date): Validation failed ($SUCCESS_RATE%), skipping deployment" >> $LOG_FILE
        exit 1
    fi
fi

echo "$(date): AEGIS policy update completed" >> $LOG_FILE
```

```bash
# Add to crontab
# Run every Sunday at 3 AM
0 3 * * 0 /usr/local/bin/aegis-update.sh
```

### Example 14: Multi-Cluster Management

Manage policies across multiple clusters.

```bash
#!/bin/bash
# multi-cluster-aegis.sh

CLUSTERS=("dev-cluster" "staging-cluster" "prod-cluster")
BASE_DIR="/opt/aegis"

for cluster in "${CLUSTERS[@]}"; do
    echo "Processing cluster: $cluster"
    
    # Create cluster-specific directory
    CLUSTER_DIR="$BASE_DIR/$cluster"
    mkdir -p $CLUSTER_DIR
    cd $CLUSTER_DIR
    
    # Update kubeconfig for cluster
    aws eks update-kubeconfig --name $cluster --region us-east-1
    
    # Copy base configuration
    cp $BASE_DIR/base-config.yaml ./aegis-config.yaml
    
    # Customize configuration for cluster
    case $cluster in
        "dev-cluster")
            sed -i 's/total_target: 20/total_target: 10/' aegis-config.yaml
            sed -i 's/validate_policies: true/validate_policies: false/' aegis-config.yaml
            ;;
        "prod-cluster")
            sed -i 's/total_target: 20/total_target: 30/' aegis-config.yaml
            sed -i 's/fix_policies: false/fix_policies: true/' aegis-config.yaml
            ;;
    esac
    
    # Run AEGIS workflow
    python $BASE_DIR/main.py discover --context $cluster --output cluster-discovery.yaml
    python $BASE_DIR/main.py questionnaire --input cluster-discovery.yaml --batch
    python $BASE_DIR/main.py recommend --input cluster-discovery.yaml --output ./policies
    
    # Generate cluster-specific report
    echo "Cluster: $cluster" > cluster-report.md
    echo "Generated: $(date)" >> cluster-report.md
    echo "" >> cluster-report.md
    
    if [ -f "./policies/SUMMARY.yaml" ]; then
        echo "## Policy Summary" >> cluster-report.md
        python -c "
import yaml
with open('./policies/SUMMARY.yaml', 'r') as f:
    summary = yaml.safe_load(f)
print(f\"Total Policies: {summary['total_policies']}\")
print(f\"Categories: {', '.join(summary['categories'])}\")
" >> cluster-report.md
    fi
    
    echo "Completed cluster: $cluster"
done

# Generate consolidated report
python $BASE_DIR/scripts/generate-multi-cluster-report.py
```

### Example 15: Policy Drift Detection

Detect and alert on policy drift between AEGIS recommendations and deployed policies.

```python
#!/usr/bin/env python3
# policy-drift-detector.py

import yaml
import subprocess
import sys
from pathlib import Path

def get_deployed_policies():
    """Get currently deployed Kyverno policies."""
    result = subprocess.run(
        ["kubectl", "get", "clusterpolicy", "-o", "yaml"],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print(f"Error getting deployed policies: {result.stderr}")
        return []
    
    deployed = yaml.safe_load(result.stdout)
    return [item['metadata']['name'] for item in deployed.get('items', [])]

def get_recommended_policies(aegis_output_dir):
    """Get AEGIS recommended policies."""
    recommended = []
    
    for policy_file in Path(aegis_output_dir).rglob("*.yaml"):
        if policy_file.name in ["SUMMARY.yaml", "kyverno-validation-report.yaml"]:
            continue
            
        try:
            with open(policy_file, 'r') as f:
                policy = yaml.safe_load(f)
                if policy.get('kind') == 'ClusterPolicy':
                    recommended.append(policy['metadata']['name'])
        except Exception as e:
            print(f"Error reading {policy_file}: {e}")
    
    return recommended

def detect_drift(deployed, recommended):
    """Detect policy drift."""
    deployed_set = set(deployed)
    recommended_set = set(recommended)
    
    missing = recommended_set - deployed_set
    extra = deployed_set - recommended_set
    
    return {
        'missing': list(missing),
        'extra': list(extra),
        'drift_detected': len(missing) > 0 or len(extra) > 0
    }

def main():
    if len(sys.argv) != 2:
        print("Usage: policy-drift-detector.py <aegis-output-dir>")
        sys.exit(1)
    
    aegis_output_dir = sys.argv[1]
    
    print("Detecting policy drift...")
    
    deployed = get_deployed_policies()
    recommended = get_recommended_policies(aegis_output_dir)
    
    drift = detect_drift(deployed, recommended)
    
    if drift['drift_detected']:
        print("⚠️  Policy drift detected!")
        
        if drift['missing']:
            print(f"\nMissing policies (recommended but not deployed):")
            for policy in drift['missing']:
                print(f"  - {policy}")
        
        if drift['extra']:
            print(f"\nExtra policies (deployed but not recommended):")
            for policy in drift['extra']:
                print(f"  - {policy}")
        
        sys.exit(1)
    else:
        print("✅ No policy drift detected")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

```bash
# Add to monitoring script
#!/bin/bash
# monitor-policy-drift.sh

# Generate fresh recommendations
python main.py recommend --input cluster-discovery.yaml --output ./current-recommendations

# Check for drift
python policy-drift-detector.py ./current-recommendations

# Send alert if drift detected
if [ $? -ne 0 ]; then
    # Send Slack notification
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"Policy drift detected in production cluster!"}' \
        $SLACK_WEBHOOK_URL
    
    # Create GitHub issue
    gh issue create \
        --title "Policy Drift Detected" \
        --body "AEGIS detected policy drift in the production cluster. Please review and update policies." \
        --label "security,policies"
fi
```

These examples demonstrate the flexibility and power of AEGIS for various use cases, from simple policy generation to complex multi-cluster automation workflows.