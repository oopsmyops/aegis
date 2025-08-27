"""
Main CLI entry point for AEGIS.
Handles command-line interface and routing to appropriate modules.
"""

import click
import sys
import os
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ConfigurationManager
from utils.logging_utils import setup_logging, get_logger
from exceptions import AegisError


@click.group()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], verbose: bool):
    """AEGIS - AI Enabled Governance Insights & Suggestions for Kubernetes."""
    
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Initialize configuration
    try:
        config_manager = ConfigurationManager(config)
        ctx.obj['config'] = config_manager.load_config()
        ctx.obj['config_manager'] = config_manager
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)
    
    # Setup logging
    log_level = "DEBUG" if verbose else ctx.obj['config'].get('logging', {}).get('level', 'INFO')
    log_file = ctx.obj['config'].get('logging', {}).get('file')
    setup_logging(level=log_level, log_file=log_file)


@cli.command()
@click.option('--output', '-o', default='cluster-discovery.yaml', help='Output file path')
@click.option('--kubeconfig', help='Kubeconfig file path')
@click.option('--context', help='Cluster name (Kubernetes context)')
@click.option('--timeout', type=int, help='Discovery timeout in seconds')
@click.pass_context
def discover(ctx: click.Context, output: str, kubeconfig: Optional[str], 
             context: Optional[str], timeout: Optional[int]):
    """Discover cluster information and configuration."""
    logger = get_logger('cli.discover')
    logger.info("Starting cluster discovery...")
    
    try:
        from discovery.discovery import ClusterDiscovery
        
        # Use timeout from config if not provided
        if timeout is None:
            timeout = ctx.obj['config'].get('cluster', {}).get('timeout', 60)
        
        # Initialize cluster discovery
        discovery = ClusterDiscovery(
            kubeconfig_path=kubeconfig,
            context=context,
            timeout=timeout
        )
        
        # Perform cluster discovery
        logger.info("Starting cluster discovery process...")
        discovery_data = discovery.discover_cluster()
        
        # Export to YAML
        discovery.export_to_yaml(discovery_data, output)
        
        logger.info(f"Cluster discovery completed successfully. Results saved to {output}")
        click.echo(f"✅ Cluster discovery completed successfully!")
        click.echo(f"📄 Results saved to: {output}")
        
        # Print summary
        cluster_info = discovery_data.get('cluster_info', {})
        click.echo(f"📊 Summary:")
        click.echo(f"   • Kubernetes version: {cluster_info.get('kubernetes_version', 'Unknown')}")
        click.echo(f"   • Nodes: {cluster_info.get('node_count', 0)}")
        click.echo(f"   • Namespaces: {cluster_info.get('namespace_count', 0)}")
        
        managed_service = discovery_data.get('managed_service')
        if managed_service:
            click.echo(f"   • Managed service: {managed_service.upper()}")
        
        controllers = discovery_data.get('third_party_controllers', [])
        if controllers:
            click.echo(f"   • Third-party controllers: {len(controllers)} found")
            
    except AegisError as e:
        logger.error(f"Discovery failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during discovery: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--input', '-i', default='cluster-discovery.yaml', help='Input cluster discovery file')
@click.option('--batch', is_flag=True, help='Run in batch mode with defaults')
@click.pass_context
def questionnaire(ctx: click.Context, input: str, batch: bool):
    """Run interactive questionnaire to gather requirements."""
    logger = get_logger('cli.questionnaire')
    logger.info("Starting questionnaire...")
    
    try:
        from questionnaire import QuestionnaireRunner, YamlUpdater
        
        # Check if cluster discovery file exists
        if not os.path.exists(input):
            click.echo(f"❌ Cluster discovery file not found: {input}")
            click.echo("💡 Please run 'aegis discover' first to generate cluster information.")
            sys.exit(1)
        
        click.echo(f"📋 Starting governance requirements questionnaire...")
        click.echo(f"📄 Using cluster data from: {input}")
        
        if batch:
            click.echo("⚠️  Batch mode not yet implemented. Running interactive mode.")
        
        # Initialize questionnaire runner
        runner = QuestionnaireRunner()
        
        # Run the questionnaire
        requirements = runner.run_questionnaire()
        
        # Check if user completed the questionnaire
        if not requirements.answers:
            click.echo("❌ No requirements collected. Questionnaire was cancelled or incomplete.")
            sys.exit(1)
        
        # Update the cluster discovery YAML with requirements
        yaml_updater = YamlUpdater()
        yaml_updater.append_to_cluster_yaml(requirements, input)
        
        # Print summary
        summary = runner.get_summary()
        click.echo(f"\n📊 Requirements Summary:")
        click.echo(f"   • Total questions answered: {summary['total_questions']}")
        click.echo(f"   • Yes responses: {summary['yes_answers']}")
        click.echo(f"   • No responses: {summary['no_answers']}")
        
        if summary['registries_count'] > 0:
            click.echo(f"   • Allowed registries configured: {summary['registries_count']}")
        
        if summary['compliance_frameworks_count'] > 0:
            click.echo(f"   • Compliance frameworks selected: {summary['compliance_frameworks_count']}")
        
        if summary['custom_labels_count'] > 0:
            click.echo(f"   • Custom labels configured: {summary['custom_labels_count']}")
        
        click.echo(f"\n✅ Governance requirements collected successfully!")
        click.echo(f"📄 Updated cluster data saved to: {input}")
        click.echo(f"🚀 You can now run 'aegis recommend' to get policy recommendations.")
        
    except AegisError as e:
        logger.error(f"Questionnaire failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during questionnaire: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--repos', help='Comma-separated repository URLs')
@click.option('--output', '-o', help='Catalog output directory')
@click.option('--refresh', is_flag=True, help='Force refresh of existing catalog')
@click.pass_context
def catalog(ctx: click.Context, repos: Optional[str], output: Optional[str], refresh: bool):
    """Build policy catalog from GitHub repositories."""
    logger = get_logger('cli.catalog')
    logger.info("Starting catalog creation...")
    
    try:
        from catalog import PolicyCatalogManager
        
        # Get configuration
        config = ctx.obj['config']
        
        # Override output directory if provided
        if output:
            config['catalog']['local_storage'] = output
        
        # Parse repository URLs
        repo_urls = []
        if repos:
            repo_urls = [url.strip() for url in repos.split(',')]
        else:
            # Use repositories from config
            repo_urls = [repo['url'] for repo in config.get('catalog', {}).get('repositories', [])]
        
        if not repo_urls:
            click.echo("❌ No repositories specified. Use --repos option or configure repositories in config file.")
            sys.exit(1)
        
        click.echo(f"🚀 Starting policy catalog creation...")
        click.echo(f"📂 Output directory: {config['catalog']['local_storage']}")
        click.echo(f"📦 Repositories to process: {len(repo_urls)}")
        
        for i, repo_url in enumerate(repo_urls, 1):
            click.echo(f"   {i}. {repo_url}")
        
        # Initialize catalog manager
        catalog_manager = PolicyCatalogManager(config)
        
        # Create catalog from repositories
        click.echo(f"\n📥 Cloning and processing repositories...")
        catalog_manager.create_catalog_from_repos(repo_urls)
        
        # Build policy index
        click.echo(f"🔍 Building policy index...")
        policy_index = catalog_manager.build_policy_index()
        
        # Print summary
        click.echo(f"\n✅ Policy catalog created successfully!")
        click.echo(f"📄 Catalog location: {config['catalog']['local_storage']}")
        click.echo(f"📊 Index file: {config['catalog']['index_file']}")
        
        click.echo(f"\n📈 Catalog Summary:")
        click.echo(f"   • Total policies: {policy_index.total_policies}")
        click.echo(f"   • Categories: {len(policy_index.categories)}")
        
        # Show category breakdown
        for category, policies in policy_index.categories.items():
            click.echo(f"   • {category}: {len(policies)} policies")
        
        click.echo(f"\n🚀 You can now run 'aegis recommend' to get AI-powered policy recommendations!")
        
    except AegisError as e:
        logger.error(f"Catalog creation failed: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during catalog creation: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--input', '-i', default='cluster-discovery.yaml', help='Input cluster discovery file')
@click.option('--output', '-o', help='Output directory for recommended policies')
@click.option('--count', type=int, help='Target number of policies to recommend')
@click.option('--fix', is_flag=True, help='Enable Kyverno validation, test case generation, and automatic policy fixing (default: disabled)')
@click.option('--catalog-path', help='Path to policy catalog directory')
@click.option('--index-file', help='Path to policy index JSON file')
@click.option('--ai-model', help='AI model to use (e.g., anthropic.claude-3-sonnet-20240229-v1:0)')
@click.option('--ai-region', help='AWS region for Bedrock service')
@click.option('--temperature', type=float, help='AI temperature setting (0.0-1.0)')
@click.option('--max-tokens', type=int, help='Maximum tokens for AI requests')
@click.option('--no-ai', is_flag=True, help='Use rule-based selection instead of AI')
@click.pass_context
def recommend(ctx: click.Context, input: str, output: Optional[str], count: Optional[int], 
              fix: bool, catalog_path: Optional[str], index_file: Optional[str],
              ai_model: Optional[str], ai_region: Optional[str], temperature: Optional[float],
              max_tokens: Optional[int], no_ai: bool):
    """Generate AI-powered policy recommendations."""
    logger = get_logger('cli.recommend')
    logger.info("Starting policy recommendation...")
    
    try:
        import yaml
        import json
        from datetime import datetime
        from ai import BedrockClient, AIPolicySelector
        from models import ClusterInfo, GovernanceRequirements, PolicyIndex, PolicyCatalogEntry
        
        def load_policy_index_from_file(index_path: str) -> PolicyIndex:
            """Load policy index from JSON file."""
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Convert to PolicyIndex object
                categories = {}
                for category, policies_data in data.get('categories', {}).items():
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
                
                return PolicyIndex(
                    categories=categories,
                    total_policies=data.get('total_policies', 0),
                    last_updated=datetime.now()
                )
                
            except Exception as e:
                logger.error(f"Error loading policy index: {e}")
                return PolicyIndex()
        
        # Get configuration and apply overrides
        config = ctx.obj['config'].copy()
        
        # Apply CLI overrides
        if output:
            config['output']['directory'] = output
        if count:
            config['ai']['policy_count']['total_target'] = count
        if catalog_path:
            config['catalog']['local_storage'] = catalog_path
        if index_file:
            config['catalog']['index_file'] = index_file
        if ai_model:
            config['ai']['model'] = ai_model
        if ai_region:
            config['ai']['region'] = ai_region
        if temperature is not None:
            config['ai']['temperature'] = temperature
        if max_tokens:
            config['ai']['max_tokens'] = max_tokens
        config['output']['validate_policies'] = fix
        config['output']['include_tests'] = True  # Always copy existing tests from catalog
        config['output']['fix_policies'] = fix
        
        # Check if cluster discovery file exists
        if not os.path.exists(input):
            click.echo(f"❌ Cluster discovery file not found: {input}")
            click.echo("💡 Please run 'aegis discover' and 'aegis questionnaire' first.")
            sys.exit(1)
        
        # Check if policy index exists
        index_path = config['catalog']['index_file']
        if not os.path.exists(index_path):
            click.echo(f"❌ Policy index not found: {index_path}")
            click.echo("💡 Please run 'aegis catalog' first to build the policy catalog.")
            sys.exit(1)
        
        click.echo(f"🚀 Starting AI-powered policy recommendation...")
        click.echo(f"📄 Input file: {input}")
        click.echo(f"📂 Output directory: {config['output']['directory']}")
        click.echo(f"🎯 Target policies: {config['ai']['policy_count']['total_target']}")
        click.echo(f"🤖 AI Model: {config['ai']['model']}")
        click.echo(f"🌍 Region: {config['ai']['region']}")
        
        # Show Two-Phase selection info
        two_phase_config = config.get('ai', {}).get('two_phase_selection', {})
        if two_phase_config.get('enabled', True):
            click.echo(f"🔄 Two-Phase Selection: Enabled")
            click.echo(f"   • Phase 1 candidates: {two_phase_config.get('phase_one_candidates', 150)}")
            click.echo(f"   • Phase 2 target: {two_phase_config.get('phase_two_target', 20)}")
        else:
            click.echo(f"⚙️  Two-Phase Selection: Disabled (using legacy selection)")
        
        # Load cluster info and requirements from YAML
        click.echo(f"\n📥 Loading cluster information and requirements...")
        with open(input, 'r', encoding='utf-8') as f:
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
        click.echo(f"📚 Loading policy index from: {index_path}")
        policy_index = load_policy_index_from_file(index_path)
        click.echo(f"   ✓ Loaded {policy_index.total_policies} policies from {len(policy_index.categories)} categories")
        
        # Initialize AI components
        if no_ai:
            click.echo(f"⚙️  Using rule-based policy selection (AI disabled)")
            # Create mock client for rule-based selection
            class MockBedrockClient:
                def __init__(self):
                    self.model_id = "rule-based-fallback"
                def send_request(self, prompt, max_tokens=4000, temperature=0.1):
                    raise Exception("AI disabled - using rule-based selection")
            
            bedrock_client = MockBedrockClient()
        else:
            click.echo(f"🤖 Initializing AI components...")
            try:
                bedrock_client = BedrockClient(
                    region=config['ai']['region'],
                    model_id=config['ai']['model']
                )
                if not bedrock_client.is_available():
                    click.echo(f"⚠️  AI service not available, falling back to rule-based selection")
            except Exception as e:
                click.echo(f"⚠️  AI initialization failed: {e}")
                click.echo(f"⚠️  Falling back to rule-based selection")
        
        # Create AI policy selector with output directory and full configuration
        ai_selector = AIPolicySelector(
            bedrock_client, 
            config['catalog']['local_storage'],
            config['output']['directory'],
            config  # Pass full configuration for Two-Phase selection
        )
        
        # Generate recommendations with optional validation and organized output
        click.echo(f"\n🔍 Generating policy recommendations...")
        click.echo(f"   • Validation & Test Generation: {'Enabled' if fix else 'Disabled'}")
        
        if fix:
            click.echo(f"🔍 Advanced mode - policies will be validated and organized")
            # Use the new organized output method that includes validation
            output_result = ai_selector.generate_organized_output(
                cluster_info=cluster_info,
                requirements=requirements,
                policy_index=policy_index,
                target_count=config['ai']['policy_count']['total_target']
            )
            recommendation = output_result['recommendation']
            validation_results = output_result['validation_results']
            created_files = output_result['created_files']
            deployment_guide = output_result['deployment_guide']
            validation_report = output_result['validation_report']
        else:
            click.echo(f"📝 Basic mode - generating recommendations with existing tests (no validation)")
            recommendation = ai_selector.generate_complete_recommendation(
                cluster_info=cluster_info,
                requirements=requirements,
                policy_index=policy_index,
                target_count=config['ai']['policy_count']['total_target']
            )
            validation_results = []
            created_files = {}
            deployment_guide = None
            validation_report = None
        
        # Handle output based on validation mode
        output_dir = config['output']['directory']
        
        if fix and created_files:
            # Files already created by OutputManager
            click.echo(f"📁 Policies organized with validation and test cases...")
            total_written = sum(len(files) for files in created_files.values())
        else:
            # Basic organization mode - copy policies and existing tests
            click.echo(f"📁 Organizing policies into categories with existing tests...")
            os.makedirs(output_dir, exist_ok=True)
            
            category_assignment = ai_selector.category_determiner.assign_policies_to_categories(
                [p.original_policy for p in recommendation.recommended_policies],
                recommendation.categories
            )
            
            total_written = 0
            for category, policies in category_assignment.items():
                if not policies:
                    continue
                    
                category_dir = os.path.join(output_dir, category.lower().replace(' ', '-').replace('&', 'and'))
                os.makedirs(category_dir, exist_ok=True)
                
                for policy_entry in policies:
                    recommended_policy = next(
                        (rp for rp in recommendation.recommended_policies 
                         if rp.original_policy.name == policy_entry.name), None
                    )
                    
                    if recommended_policy:
                        policy_dir = os.path.join(category_dir, policy_entry.name)
                        os.makedirs(policy_dir, exist_ok=True)
                        
                        # Write policy file using original filename from catalog
                        original_filename = os.path.basename(recommended_policy.original_policy.relative_path)
                        policy_file = os.path.join(policy_dir, original_filename)
                        with open(policy_file, 'w', encoding='utf-8') as f:
                            f.write(recommended_policy.customized_content)
                        
                        # Copy existing tests from catalog if available
                        if recommended_policy.original_policy.test_directory:
                            import shutil
                            catalog_test_path = os.path.join(
                                config['catalog']['local_storage'], 
                                recommended_policy.original_policy.test_directory
                            )
                            if os.path.exists(catalog_test_path):
                                try:
                                    # Copy all test-related files and directories, excluding the main policy file
                                    test_files_copied = 0
                                    
                                    def copy_test_files_recursive(src_dir, dst_dir):
                                        """Recursively copy all test files and directories."""
                                        nonlocal test_files_copied
                                        
                                        for item in os.listdir(src_dir):
                                            src_item = os.path.join(src_dir, item)
                                            dst_item = os.path.join(dst_dir, item)
                                            
                                            if os.path.isdir(src_item):
                                                # Copy subdirectories (like .chainsaw-test)
                                                os.makedirs(dst_item, exist_ok=True)
                                                copy_test_files_recursive(src_item, dst_item)
                                            elif item.endswith(('.yaml', '.yml')):
                                                # Skip the main policy file (it has the same name as in relative_path)
                                                original_policy_filename = os.path.basename(recommended_policy.original_policy.relative_path)
                                                if item != original_policy_filename:
                                                    shutil.copy2(src_item, dst_item)
                                                    test_files_copied += 1
                                            else:
                                                # Copy other files (like .md, .txt, etc.)
                                                shutil.copy2(src_item, dst_item)
                                                test_files_copied += 1
                                    
                                    copy_test_files_recursive(catalog_test_path, policy_dir)
                                    
                                    if test_files_copied > 0:
                                        click.echo(f"   ✓ Copied {test_files_copied} test files for {policy_entry.name}")
                                except Exception as e:
                                    click.echo(f"   ⚠️  Could not copy tests for {policy_entry.name}: {e}")
                        
                        total_written += 1
        
        # Print results
        click.echo(f"\n✅ Policy recommendation completed successfully!")
        click.echo(f"📂 Output directory: {output_dir}")
        
        if validation_report:
            click.echo(f"📄 Validation report: {validation_report}")
        if deployment_guide:
            click.echo(f"📋 Deployment guide: {deployment_guide}")
        
        click.echo(f"\n📊 Recommendation Summary:")
        click.echo(f"   • Total policies recommended: {len(recommendation.recommended_policies)}")
        click.echo(f"   • Categories: {len(recommendation.categories)}")
        click.echo(f"   • AI model used: {recommendation.ai_model_used}")
        click.echo(f"   • Files created: {total_written}")
        
        # Show validation results if available
        if validation_results:
            passed_count = sum(1 for r in validation_results if r.passed)
            failed_count = len(validation_results) - passed_count
            fixed_count = sum(1 for r in validation_results if r.fixed_content)
            
            click.echo(f"\n🔍 Validation Results:")
            click.echo(f"   • Passed: {passed_count}")
            click.echo(f"   • Failed: {failed_count}")
            click.echo(f"   • Auto-fixed: {fixed_count}")
            click.echo(f"   • Success rate: {(passed_count/len(validation_results)*100):.1f}%")
            
            if failed_count > 0:
                click.echo(f"   ⚠️  {failed_count} policies failed validation - check validation report")
        else:
            click.echo(f"\n📈 Basic Validation Results:")
            for status, count in recommendation.validation_summary.items():
                if count > 0:
                    click.echo(f"   • {status.title()}: {count}")
        
        # Show categories
        if created_files:
            click.echo(f"\n📁 Categories Created:")
            for category, files in created_files.items():
                click.echo(f"   • {category}: {len(files)} files")
        
        # Show additional features used (only when --fix is enabled)
        if fix:
            features_used = []
            if validation_results:
                features_used.append("Kyverno validation")
            if any(r.fixed_content for r in validation_results) if validation_results else False:
                features_used.append("automatic policy fixing")
            if any(p.test_content for p in recommendation.recommended_policies):
                features_used.append("test case generation")
            
            if features_used:
                click.echo(f"\n🚀 Features Used: {', '.join(features_used)}")
        
        click.echo(f"\n🎉 Recommendation process completed!")
        click.echo(f"💡 Review the policies in {output_dir} before applying to your cluster")
        
        if deployment_guide:
            click.echo(f"📖 See DEPLOYMENT_GUIDE.md for detailed deployment instructions")
        
    except AegisError as e:
        logger.error(f"Recommendation failed: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during recommendation: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--all', 'run_all', is_flag=True, help='Execute complete workflow')
@click.pass_context
def run(ctx: click.Context, run_all: bool):
    """Execute AEGIS workflow."""
    if run_all:
        logger = get_logger('cli.run')
        logger.info("Starting complete AEGIS workflow...")
        
        try:
            # This will orchestrate all components when implemented
            click.echo("Complete workflow will be implemented after individual components.")
        except AegisError as e:
            logger.error(f"Workflow failed: {e}")
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    else:
        click.echo("Use --all flag to run complete workflow")


@cli.command()
@click.option('--init', is_flag=True, help='Initialize default configuration')
@click.pass_context
def config(ctx: click.Context, init: bool):
    """Manage AEGIS configuration."""
    if init:
        try:
            config_manager = ConfigurationManager()
            default_config = config_manager.get_default_config()
            config_manager.save_config(default_config, "./aegis-config.yaml")
            click.echo("Default configuration saved to aegis-config.yaml")
        except Exception as e:
            click.echo(f"Error initializing configuration: {e}", err=True)
            sys.exit(1)
    else:
        click.echo("Use --init to create default configuration")


@cli.command()
def version():
    """Show AEGIS version information."""
    import __init__
    __version__ = __init__.__version__
    __description__ = __init__.__description__
    click.echo(f"AEGIS v{__version__}")
    click.echo(__description__)


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()