"""
Command classes for AEGIS CLI.
Defines individual command implementations for better organization.
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from utils.logging_utils import LoggerMixin


class BaseCommand(ABC, LoggerMixin):
    """Base class for all AEGIS commands."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    def execute(self, **kwargs) -> None:
        """Execute the command."""
        pass


class DiscoverCommand(BaseCommand):
    """Command for cluster discovery functionality."""
    
    def execute(self, output: str = "cluster-discovery.yaml", 
                kubeconfig: Optional[str] = None,
                context: Optional[str] = None,
                timeout: Optional[int] = None) -> None:
        """Execute cluster discovery."""
        self.logger.info("Executing cluster discovery command")
        
        try:
            from ..discovery import ClusterDiscovery
            
            # Use timeout from config if not provided
            if timeout is None:
                timeout = self.config.get('cluster', {}).get('timeout', 60)
            
            # Initialize cluster discovery
            discovery = ClusterDiscovery(
                kubeconfig_path=kubeconfig,
                context=context,
                timeout=timeout
            )
            
            # Perform cluster discovery
            self.logger.info("Starting cluster discovery process...")
            discovery_data = discovery.discover_cluster()
            
            # Export to YAML
            discovery.export_to_yaml(discovery_data, output)
            
            self.logger.info(f"Cluster discovery completed successfully. Results saved to {output}")
            print(f"✅ Cluster discovery completed successfully!")
            print(f"📄 Results saved to: {output}")
            
            # Print summary
            cluster_info = discovery_data.get('cluster_info', {})
            print(f"📊 Summary:")
            print(f"   • Kubernetes version: {cluster_info.get('kubernetes_version', 'Unknown')}")
            print(f"   • Nodes: {cluster_info.get('node_count', 0)}")
            print(f"   • Namespaces: {cluster_info.get('namespace_count', 0)}")
            
            managed_service = discovery_data.get('managed_service')
            if managed_service:
                print(f"   • Managed service: {managed_service.upper()}")
            
            controllers = discovery_data.get('third_party_controllers', [])
            if controllers:
                print(f"   • Third-party controllers: {len(controllers)} found")
            
        except Exception as e:
            self.logger.error(f"Cluster discovery failed: {str(e)}")
            print(f"❌ Cluster discovery failed: {str(e)}")
            raise


class QuestionnaireCommand(BaseCommand):
    """Command for interactive questionnaire functionality."""
    
    def execute(self, input_file: str = "cluster-discovery.yaml",
                batch: bool = False) -> None:
        """Execute questionnaire."""
        self.logger.info("Executing questionnaire command")
        
        try:
            from ..questionnaire import QuestionnaireRunner, YamlUpdater
            import os
            
            # Check if cluster discovery file exists
            if not os.path.exists(input_file):
                print(f"❌ Cluster discovery file not found: {input_file}")
                print("💡 Please run 'aegis discover' first to generate cluster information.")
                return
            
            print(f"📋 Starting governance requirements questionnaire...")
            print(f"📄 Using cluster data from: {input_file}")
            
            if batch:
                print("⚠️  Batch mode not yet implemented. Running interactive mode.")
            
            # Initialize questionnaire runner
            runner = QuestionnaireRunner()
            
            # Run the questionnaire
            requirements = runner.run_questionnaire()
            
            # Check if user completed the questionnaire
            if not requirements.answers:
                print("❌ No requirements collected. Questionnaire was cancelled or incomplete.")
                return
            
            # Update the cluster discovery YAML with requirements
            yaml_updater = YamlUpdater()
            yaml_updater.append_to_cluster_yaml(requirements, input_file)
            
            # Print summary
            summary = runner.get_summary()
            print(f"\n📊 Requirements Summary:")
            print(f"   • Total questions answered: {summary['total_questions']}")
            print(f"   • Yes responses: {summary['yes_answers']}")
            print(f"   • No responses: {summary['no_answers']}")
            
            if summary['registries_count'] > 0:
                print(f"   • Allowed registries configured: {summary['registries_count']}")
            
            if summary['compliance_frameworks_count'] > 0:
                print(f"   • Compliance frameworks selected: {summary['compliance_frameworks_count']}")
            
            if summary['custom_labels_count'] > 0:
                print(f"   • Custom labels configured: {summary['custom_labels_count']}")
            
            print(f"\n✅ Governance requirements collected successfully!")
            print(f"📄 Updated cluster data saved to: {input_file}")
            print(f"🚀 You can now run 'aegis recommend' to get policy recommendations.")
            
        except Exception as e:
            self.logger.error(f"Questionnaire failed: {str(e)}")
            print(f"❌ Questionnaire failed: {str(e)}")
            raise


class CatalogCommand(BaseCommand):
    """Command for policy catalog management."""
    
    def execute(self, repos: Optional[str] = None,
                output: Optional[str] = None,
                refresh: bool = False) -> None:
        """Execute catalog creation."""
        self.logger.info("Executing catalog command")
        
        try:
            from ..catalog import PolicyCatalogManager
            
            # Override output directory if provided
            if output:
                self.config['catalog']['local_storage'] = output
            
            # Parse repository URLs
            repo_urls = []
            if repos:
                repo_urls = [url.strip() for url in repos.split(',')]
            else:
                # Use repositories from config
                repo_urls = [repo['url'] for repo in self.config.get('catalog', {}).get('repositories', [])]
            
            if not repo_urls:
                print("❌ No repositories specified. Use --repos option or configure repositories in config file.")
                return
            
            print(f"🚀 Starting policy catalog creation...")
            print(f"📂 Output directory: {self.config['catalog']['local_storage']}")
            print(f"📦 Repositories to process: {len(repo_urls)}")
            
            for i, repo_url in enumerate(repo_urls, 1):
                print(f"   {i}. {repo_url}")
            
            # Initialize catalog manager
            catalog_manager = PolicyCatalogManager(self.config)
            
            # Create catalog from repositories
            print(f"\n📥 Cloning and processing repositories...")
            catalog_manager.create_catalog_from_repos(repo_urls)
            
            # Build policy index
            print(f"🔍 Building policy index...")
            policy_index = catalog_manager.build_policy_index()
            
            # Print summary
            print(f"\n✅ Policy catalog created successfully!")
            print(f"📄 Catalog location: {self.config['catalog']['local_storage']}")
            print(f"📊 Index file: {self.config['catalog']['index_file']}")
            
            print(f"\n📈 Catalog Summary:")
            print(f"   • Total policies: {policy_index.total_policies}")
            print(f"   • Categories: {len(policy_index.categories)}")
            
            # Show category breakdown
            for category, policies in policy_index.categories.items():
                print(f"   • {category}: {len(policies)} policies")
            
            print(f"\n🚀 You can now run 'aegis recommend' to get AI-powered policy recommendations!")
            
        except Exception as e:
            self.logger.error(f"Catalog creation failed: {str(e)}")
            print(f"❌ Catalog creation failed: {str(e)}")
            raise


class RecommendCommand(BaseCommand):
    """Command for AI policy recommendation."""
    
    def execute(self, input_file: str = "cluster-discovery.yaml",
                output: str = "./recommended-policies",
                count: Optional[int] = None,
                validate: bool = False) -> None:
        """Execute policy recommendation."""
        self.logger.info("Executing recommend command")
        
        try:
            import yaml
            import json
            import time
            from datetime import datetime
            from ..ai import BedrockClient, AIPolicySelector
            from ..models import ClusterInfo, GovernanceRequirements, PolicyIndex, PolicyCatalogEntry
            
            # Check if cluster discovery file exists
            if not os.path.exists(input_file):
                print(f"❌ Cluster discovery file not found: {input_file}")
                print("💡 Please run 'aegis discover' and 'aegis questionnaire' first.")
                return
            
            # Check if policy index exists
            index_path = self.config['catalog']['index_file']
            if not os.path.exists(index_path):
                print(f"❌ Policy index not found: {index_path}")
                print("💡 Please run 'aegis catalog' first to build the policy catalog.")
                return
            
            print(f"🚀 Starting AI-powered policy recommendation...")
            print(f"📄 Input file: {input_file}")
            print(f"📂 Output directory: {output}")
            
            start_time = time.time()
            
            # Load cluster info and requirements from YAML (simplified)
            with open(input_file, 'r', encoding='utf-8') as f:
                cluster_data = yaml.safe_load(f)
            
            # Extract cluster info (simplified for demo)
            cluster_info = ClusterInfo(
                version=cluster_data.get('cluster_info', {}).get('kubernetes_version', 'unknown'),
                managed_service=cluster_data.get('managed_service'),
                node_count=cluster_data.get('cluster_info', {}).get('node_count', 0),
                namespace_count=cluster_data.get('cluster_info', {}).get('namespace_count', 0)
            )
            
            # Extract requirements (simplified for demo)
            requirements = GovernanceRequirements(
                compliance_frameworks=cluster_data.get('governance_requirements', {}).get('compliance_frameworks', []),
                registries=cluster_data.get('governance_requirements', {}).get('registries', [])
            )
            
            # Load policy index
            with open(index_path, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            # Convert to PolicyIndex object (simplified)
            categories = {}
            for category, policies_data in index_data.get('categories', {}).items():
                policies = []
                for policy_data in policies_data:
                    policy = PolicyCatalogEntry(
                        name=policy_data['name'],
                        category=policy_data['category'],
                        description=policy_data['description'],
                        relative_path=policy_data['relative_path'],
                        test_directory=policy_data.get('test_directory'),
                        source_repo=policy_data.get('source_repo', ''),
                        tags=policy_data.get('tags', [])
                    )
                    policies.append(policy)
                categories[category] = policies
            
            policy_index = PolicyIndex(
                categories=categories,
                total_policies=index_data.get('total_policies', 0),
                last_updated=datetime.now()
            )
            
            # Initialize AI components
            bedrock_client = BedrockClient(
                region=self.config['ai']['region'],
                model_id=self.config['ai']['model']
            )
            
            ai_selector = AIPolicySelector(
                bedrock_client, 
                self.config['catalog']['local_storage'],
                output,
                self.config
            )
            
            # Generate recommendations
            target_count = count or self.config['ai']['policy_count']['total_target']
            recommendation = ai_selector.generate_complete_recommendation(
                cluster_info=cluster_info,
                requirements=requirements,
                policy_index=policy_index,
                target_count=target_count
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"\n✅ Policy recommendation completed successfully in {duration:.1f}s!")
            print(f"📂 Output directory: {output}")
            print(f"📊 Total policies recommended: {len(recommendation.recommended_policies)}")
            print(f"🎉 Recommendation process completed!")
            
        except Exception as e:
            self.logger.error(f"Recommendation failed: {str(e)}")
            print(f"❌ Policy recommendation failed: {str(e)}")
            raise