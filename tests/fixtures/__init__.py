"""
Test fixtures for AEGIS testing.
"""

from .sample_policies import (
    create_sample_policy_catalog_entries,
    create_sample_recommended_policies,
    create_sample_cluster_info,
    create_sample_governance_requirements,
    create_sample_cluster_discovery_yaml,
    create_sample_governance_requirements_yaml,
    SAMPLE_POLICY_YAML,
    SAMPLE_TEST_YAML,
    SAMPLE_GOOD_RESOURCE_YAML,
    SAMPLE_BAD_RESOURCE_YAML,
    POLICY_TEMPLATES,
    TEST_RESOURCE_TEMPLATES
)

__all__ = [
    'create_sample_policy_catalog_entries',
    'create_sample_recommended_policies', 
    'create_sample_cluster_info',
    'create_sample_governance_requirements',
    'create_sample_cluster_discovery_yaml',
    'create_sample_governance_requirements_yaml',
    'SAMPLE_POLICY_YAML',
    'SAMPLE_TEST_YAML',
    'SAMPLE_GOOD_RESOURCE_YAML',
    'SAMPLE_BAD_RESOURCE_YAML',
    'POLICY_TEMPLATES',
    'TEST_RESOURCE_TEMPLATES'
]