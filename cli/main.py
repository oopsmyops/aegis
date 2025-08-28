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

try:
    from config import ConfigurationManager
    from utils.logging_utils import setup_logging, get_logger
    from exceptions import AegisError
except ImportError:
    # Fallback for binary execution - try absolute imports
    try:
        from aegis.config import ConfigurationManager
        from aegis.utils.logging_utils import setup_logging, get_logger
        from aegis.exceptions import AegisError
    except ImportError:
        # Final fallback - add current directory to path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from config import ConfigurationManager
        from utils.logging_utils import setup_logging, get_logger
        from exceptions import AegisError


@click.group()
@click.option("--config", "-c", help="Configuration file path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--debug", is_flag=True, help="Enable debug mode with detailed error traces"
)
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], verbose: bool, debug: bool):
    """AEGIS - AI Enabled Governance Insights & Suggestions for Kubernetes.

    AEGIS automates Kubernetes governance by discovering cluster configurations,
    gathering requirements through interactive questionnaires, and using AI to
    recommend appropriate policies from a curated catalog.

    Quick Start:
      aegis health              # Check system health
      aegis config --init       # Initialize configuration
      aegis run --all           # Run complete workflow

    Step-by-step:
      aegis discover            # Scan cluster
      aegis questionnaire       # Gather requirements
      aegis catalog             # Build policy catalog
      aegis recommend           # Get AI recommendations
    """

    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["verbose"] = verbose

    # Initialize configuration with better error handling
    # Skip config loading for help and version commands
    if (
        ctx.invoked_subcommand in ["version", "help"]
        or "--help" in sys.argv
        or "-h" in sys.argv
    ):
        ctx.obj["config"] = {}
        ctx.obj["config_manager"] = None
        return

    try:
        config_manager = ConfigurationManager(config)
        ctx.obj["config"] = config_manager.load_config()
        ctx.obj["config_manager"] = config_manager
    except Exception as e:
        click.echo(f"❌ Error loading configuration: {e}", err=True)
        if debug:
            import traceback

            click.echo(f"Debug trace:\n{traceback.format_exc()}", err=True)
        click.echo(
            f"💡 Try running 'aegis config --init' to create default configuration",
            err=True,
        )
        sys.exit(1)

    # Setup logging with enhanced configuration
    log_level = (
        "DEBUG"
        if (verbose or debug)
        else ctx.obj["config"].get("logging", {}).get("level", "INFO")
    )
    log_file = ctx.obj["config"].get("logging", {}).get("file")

    try:
        setup_logging(level=log_level, log_file=log_file)
        logger = get_logger("cli.main")
        logger.info(f"AEGIS CLI started with log level: {log_level}")
        if debug:
            logger.debug("Debug mode enabled - detailed error traces will be shown")
    except Exception as e:
        click.echo(f"⚠️  Warning: Could not setup logging: {e}", err=True)
        # Continue without logging rather than failing


@cli.command()
@click.option(
    "--output", "-o", default="cluster-discovery.yaml", help="Output file path"
)
@click.option("--kubeconfig", help="Kubeconfig file path")
@click.option("--context", help="Cluster name (Kubernetes context)")
@click.option("--timeout", type=int, help="Discovery timeout in seconds")
@click.pass_context
def discover(
    ctx: click.Context,
    output: str,
    kubeconfig: Optional[str],
    context: Optional[str],
    timeout: Optional[int],
):
    """Discover cluster information and configuration."""
    logger = get_logger("cli.discover")
    logger.info("Starting cluster discovery...")

    try:
        try:
            from discovery.discovery import ClusterDiscovery
        except ImportError:
            from aegis.discovery.discovery import ClusterDiscovery
        import time

        # Use timeout from config if not provided
        if timeout is None:
            timeout = ctx.obj["config"].get("cluster", {}).get("timeout", 60)

        # Show initial progress
        click.echo(f"🔍 Starting cluster discovery...")
        click.echo(f"⚙️  Configuration:")
        click.echo(f"   • Kubeconfig: {kubeconfig or '~/.kube/config (default)'}")
        click.echo(f"   • Context: {context or 'current context'}")
        click.echo(f"   • Timeout: {timeout} seconds")
        click.echo(f"   • Output: {output}")

        start_time = time.time()

        # Initialize cluster discovery with progress
        click.echo(f"\n📡 Initializing cluster connection...")
        discovery = ClusterDiscovery(
            kubeconfig_path=kubeconfig, context=context, timeout=timeout
        )

        # Perform cluster discovery with progress updates
        click.echo(f"� Scamnning cluster resources...")
        logger.info("Starting cluster discovery process...")

        with click.progressbar(length=100, label="Discovering cluster") as bar:
            # Simulate progress updates (in real implementation, discovery would update progress)
            discovery_data = discovery.discover_cluster()
            bar.update(100)

        # Export to YAML
        click.echo(f"💾 Saving results to {output}...")
        discovery.export_to_yaml(discovery_data, output)

        end_time = time.time()
        duration = end_time - start_time

        logger.info(
            f"Cluster discovery completed successfully. Results saved to {output}"
        )
        click.echo(f"\n✅ Cluster discovery completed successfully in {duration:.1f}s!")
        click.echo(f"📄 Results saved to: {output}")

        # Print detailed summary
        cluster_info = discovery_data.get("cluster_info", {})
        click.echo(f"\n📊 Cluster Summary:")
        click.echo(
            f"   • Kubernetes version: {cluster_info.get('kubernetes_version', 'Unknown')}"
        )
        click.echo(f"   • Nodes: {cluster_info.get('node_count', 0)}")
        click.echo(f"   • Namespaces: {cluster_info.get('namespace_count', 0)}")

        managed_service = discovery_data.get("managed_service")
        if managed_service:
            click.echo(f"   • Managed service: {managed_service.upper()}")

        controllers = discovery_data.get("third_party_controllers", [])
        if controllers:
            click.echo(f"   • Third-party controllers: {len(controllers)} found")
            for controller in controllers[:3]:  # Show first 3
                click.echo(
                    f"     - {controller.get('name', 'Unknown')} ({controller.get('type', 'unknown')})"
                )
            if len(controllers) > 3:
                click.echo(f"     - ... and {len(controllers) - 3} more")

        # Show next steps
        click.echo(f"\n🚀 Next Steps:")
        click.echo(f"   1. Run 'aegis questionnaire' to gather governance requirements")
        click.echo(f"   2. Or run 'aegis run --all' for complete workflow")

    except AegisError as e:
        logger.error(f"Discovery failed: {e}")
        click.echo(f"❌ Discovery failed: {e}", err=True)
        click.echo(f"💡 Troubleshooting tips:")
        click.echo(f"   • Check your kubeconfig file and cluster connectivity")
        click.echo(f"   • Verify you have proper RBAC permissions")
        click.echo(f"   • Try increasing timeout with --timeout option")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during discovery: {e}")
        click.echo(f"❌ Unexpected error: {e}", err=True)
        click.echo(
            f"💡 Please check the log file for more details: {ctx.obj['config'].get('logging', {}).get('file', './aegis.log')}"
        )
        sys.exit(1)


@cli.command()
@click.option(
    "--input",
    "-i",
    default="cluster-discovery.yaml",
    help="Input cluster discovery file",
)
@click.option("--batch", is_flag=True, help="Run in batch mode with defaults")
@click.pass_context
def questionnaire(ctx: click.Context, input: str, batch: bool):
    """Run interactive questionnaire to gather requirements."""
    logger = get_logger("cli.questionnaire")
    logger.info("Starting questionnaire...")

    try:
        try:
            from questionnaire import QuestionnaireRunner, YamlUpdater
        except ImportError:
            from aegis.questionnaire import QuestionnaireRunner, YamlUpdater
        import time

        # Check if cluster discovery file exists
        if not os.path.exists(input):
            click.echo(f"❌ Cluster discovery file not found: {input}")
            click.echo(
                "💡 Please run 'aegis discover' first to generate cluster information."
            )
            click.echo("💡 Or use 'aegis run --all' for complete workflow")
            sys.exit(1)

        start_time = time.time()

        click.echo(f"📋 Starting governance requirements questionnaire...")
        click.echo(f"📄 Using cluster data from: {input}")

        if batch:
            click.echo("⚠️  Batch mode not yet implemented. Running interactive mode.")

        # Show questionnaire info
        total_questions = (
            ctx.obj["config"].get("questionnaire", {}).get("total_questions", 20)
        )
        click.echo(
            f"❓ You will be asked up to {total_questions} yes/no questions about governance requirements"
        )
        click.echo(
            f"💡 Some questions may have follow-up prompts for additional details"
        )
        click.echo(f"⏭️  Press Ctrl+C at any time to cancel\n")

        # Initialize questionnaire runner
        click.echo(f"🚀 Initializing questionnaire...")
        runner = QuestionnaireRunner()

        # Run the questionnaire with progress tracking
        click.echo(f"📝 Starting interactive questionnaire...\n")
        requirements = runner.run_questionnaire()

        # Check if user completed the questionnaire
        if not requirements.answers:
            click.echo(
                "\n❌ No requirements collected. Questionnaire was cancelled or incomplete."
            )
            click.echo(
                "💡 You can restart with 'aegis questionnaire' or use 'aegis run --all'"
            )
            sys.exit(1)

        # Update the cluster discovery YAML with requirements
        click.echo(f"\n💾 Saving requirements to {input}...")
        yaml_updater = YamlUpdater()
        yaml_updater.append_to_cluster_yaml(requirements, input)

        end_time = time.time()
        duration = end_time - start_time

        # Print detailed summary
        summary = runner.get_summary()
        click.echo(
            f"\n✅ Governance requirements collected successfully in {duration:.1f}s!"
        )
        click.echo(f"\n📊 Requirements Summary:")
        click.echo(f"   • Total questions answered: {summary['total_questions']}")
        click.echo(f"   • Yes responses: {summary['yes_answers']}")
        click.echo(f"   • No responses: {summary['no_answers']}")

        if summary["registries_count"] > 0:
            click.echo(
                f"   • Allowed registries configured: {summary['registries_count']}"
            )

        if summary["compliance_frameworks_count"] > 0:
            click.echo(
                f"   • Compliance frameworks selected: {summary['compliance_frameworks_count']}"
            )

        if summary["custom_labels_count"] > 0:
            click.echo(
                f"   • Custom labels configured: {summary['custom_labels_count']}"
            )

        click.echo(f"\n📄 Updated cluster data saved to: {input}")

        # Show next steps
        click.echo(f"\n🚀 Next Steps:")
        click.echo(f"   1. Run 'aegis catalog' to build policy catalog (if not done)")
        click.echo(
            f"   2. Run 'aegis recommend' to get AI-powered policy recommendations"
        )
        click.echo(
            f"   3. Or run 'aegis run --all --skip-discovery --skip-questionnaire' to continue workflow"
        )

    except KeyboardInterrupt:
        logger.info("Questionnaire cancelled by user")
        click.echo(f"\n⚠️  Questionnaire cancelled by user")
        click.echo(f"💡 You can restart with 'aegis questionnaire' when ready")
        sys.exit(1)
    except AegisError as e:
        logger.error(f"Questionnaire failed: {e}")
        click.echo(f"❌ Questionnaire failed: {e}", err=True)
        click.echo(f"💡 Troubleshooting tips:")
        click.echo(f"   • Ensure the cluster discovery file is valid YAML")
        click.echo(f"   • Check file permissions for writing updates")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during questionnaire: {e}")
        click.echo(f"❌ Unexpected error: {e}", err=True)
        click.echo(
            f"💡 Please check the log file for more details: {ctx.obj['config'].get('logging', {}).get('file', './aegis.log')}"
        )
        sys.exit(1)


@cli.command()
@click.option("--repos", help="Comma-separated repository URLs")
@click.option("--output", "-o", help="Catalog output directory")
@click.option("--refresh", is_flag=True, help="Force refresh of existing catalog")
@click.pass_context
def catalog(
    ctx: click.Context, repos: Optional[str], output: Optional[str], refresh: bool
):
    """Build policy catalog from GitHub repositories."""
    logger = get_logger("cli.catalog")
    logger.info("Starting catalog creation...")

    try:
        try:
            from catalog import PolicyCatalogManager
        except ImportError:
            from aegis.catalog import PolicyCatalogManager
        import time

        # Get configuration
        config = ctx.obj["config"]

        # Override output directory if provided
        if output:
            config["catalog"]["local_storage"] = output

        # Parse repository URLs
        repo_urls = []
        if repos:
            repo_urls = [url.strip() for url in repos.split(",")]
        else:
            # Use repositories from config
            repo_urls = [
                repo["url"]
                for repo in config.get("catalog", {}).get("repositories", [])
            ]

        if not repo_urls:
            click.echo(
                "❌ No repositories specified. Use --repos option or configure repositories in config file."
            )
            click.echo(
                "💡 Example: aegis catalog --repos https://github.com/kyverno/policies"
            )
            sys.exit(1)

        start_time = time.time()

        click.echo(f"🚀 Starting policy catalog creation...")
        click.echo(f"📂 Output directory: {config['catalog']['local_storage']}")
        click.echo(f"📦 Repositories to process: {len(repo_urls)}")
        click.echo(f"🔄 Refresh mode: {'Enabled' if refresh else 'Disabled'}")

        for i, repo_url in enumerate(repo_urls, 1):
            click.echo(f"   {i}. {repo_url}")

        # Check if catalog already exists
        if os.path.exists(config["catalog"]["local_storage"]) and not refresh:
            click.echo(
                f"\n⚠️  Catalog directory already exists. Use --refresh to force rebuild."
            )

        # Initialize catalog manager
        click.echo(f"\n🔧 Initializing catalog manager...")
        catalog_manager = PolicyCatalogManager(config)

        # Create catalog from repositories with progress
        click.echo(f"� Cldoning and processing repositories...")

        with click.progressbar(
            repo_urls, label="Processing repositories"
        ) as repos_progress:
            for repo_url in repos_progress:
                # In real implementation, this would be called per repository
                pass

        catalog_manager.create_catalog_from_repos(repo_urls)

        # Build policy index with progress
        click.echo(f"� Buildinag policy index...")
        with click.progressbar(length=100, label="Building index") as bar:
            policy_index = catalog_manager.build_policy_index()
            bar.update(100)

        end_time = time.time()
        duration = end_time - start_time

        # Print detailed summary
        click.echo(f"\n✅ Policy catalog created successfully in {duration:.1f}s!")
        click.echo(f"📄 Catalog location: {config['catalog']['local_storage']}")
        click.echo(f"📊 Index file: {config['catalog']['index_file']}")

        click.echo(f"\n📈 Catalog Summary:")
        click.echo(f"   • Total policies: {policy_index.total_policies}")
        click.echo(f"   • Categories: {len(policy_index.categories)}")

        # Show category breakdown with more details
        for category, policies in policy_index.categories.items():
            click.echo(f"   • {category}: {len(policies)} policies")

        # Show storage usage
        try:
            import shutil

            total, used, free = shutil.disk_usage(config["catalog"]["local_storage"])
            catalog_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(
                    config["catalog"]["local_storage"]
                )
                for filename in filenames
            ) / (
                1024 * 1024
            )  # MB
            click.echo(f"   • Catalog size: {catalog_size:.1f} MB")
        except:
            pass

        # Show next steps
        click.echo(f"\n🚀 Next Steps:")
        click.echo(
            f"   1. Run 'aegis recommend' to get AI-powered policy recommendations"
        )
        click.echo(
            f"   2. Or run 'aegis run --all --skip-catalog' to continue workflow"
        )
        click.echo(
            f"   3. Use 'aegis catalog --refresh' to update catalog with latest policies"
        )

    except AegisError as e:
        logger.error(f"Catalog creation failed: {e}")
        click.echo(f"❌ Catalog creation failed: {e}", err=True)
        click.echo(f"💡 Troubleshooting tips:")
        click.echo(f"   • Check internet connectivity for GitHub access")
        click.echo(f"   • Verify repository URLs are accessible")
        click.echo(f"   • Ensure sufficient disk space for catalog")
        click.echo(f"   • Try with --refresh flag to force rebuild")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during catalog creation: {e}")
        click.echo(f"❌ Unexpected error: {e}", err=True)
        click.echo(
            f"💡 Please check the log file for more details: {ctx.obj['config'].get('logging', {}).get('file', './aegis.log')}"
        )
        sys.exit(1)


@cli.command()
@click.option(
    "--input",
    "-i",
    default="cluster-discovery.yaml",
    help="Input cluster discovery file",
)
@click.option("--output", "-o", help="Output directory for recommended policies")
@click.option("--count", type=int, help="Target number of policies to recommend")
@click.option(
    "--fix",
    is_flag=True,
    help="Enable Kyverno validation, test case generation, and automatic policy fixing (default: disabled)",
)
@click.option("--catalog-path", help="Path to policy catalog directory")
@click.option("--index-file", help="Path to policy index JSON file")
@click.option(
    "--ai-model", help="AI model to use (e.g., anthropic.claude-3-sonnet-20240229-v1:0)"
)
@click.option("--ai-region", help="AWS region for Bedrock service")
@click.option("--temperature", type=float, help="AI temperature setting (0.0-1.0)")
@click.option("--max-tokens", type=int, help="Maximum tokens for AI requests")
@click.option("--no-ai", is_flag=True, help="Use rule-based selection instead of AI")
@click.pass_context
def recommend(
    ctx: click.Context,
    input: str,
    output: Optional[str],
    count: Optional[int],
    fix: bool,
    catalog_path: Optional[str],
    index_file: Optional[str],
    ai_model: Optional[str],
    ai_region: Optional[str],
    temperature: Optional[float],
    max_tokens: Optional[int],
    no_ai: bool,
):
    """Generate AI-powered policy recommendations."""
    logger = get_logger("cli.recommend")
    logger.info("Starting policy recommendation...")

    try:
        import yaml
        import json
        import time
        from datetime import datetime

        try:
            from ai import BedrockClient, AIPolicySelector
            from models import (
                ClusterInfo,
                GovernanceRequirements,
                PolicyIndex,
                PolicyCatalogEntry,
            )
        except ImportError:
            from aegis.ai import BedrockClient, AIPolicySelector
            from aegis.models import (
                ClusterInfo,
                GovernanceRequirements,
                PolicyIndex,
                PolicyCatalogEntry,
            )

        def load_policy_index_from_file(index_path: str) -> PolicyIndex:
            """Load policy index from JSON file."""
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Convert to PolicyIndex object
                categories = {}
                for category, policies_data in data.get("categories", {}).items():
                    policies = []
                    for policy_data in policies_data:
                        policy = PolicyCatalogEntry(
                            name=policy_data["name"],
                            category=policy_data["category"],
                            description=policy_data["description"],
                            relative_path=policy_data["relative_path"],
                            test_directory=policy_data.get("test_directory"),
                            source_repo=policy_data.get("source_repo", ""),
                            tags=policy_data.get("tags", []),
                        )
                        policies.append(policy)
                    categories[category] = policies

                return PolicyIndex(
                    categories=categories,
                    total_policies=data.get("total_policies", 0),
                    last_updated=datetime.now(),
                )

            except Exception as e:
                logger.error(f"Error loading policy index: {e}")
                return PolicyIndex()

        # Get configuration and apply overrides
        config = ctx.obj["config"].copy()

        # Apply CLI overrides
        if output:
            config["output"]["directory"] = output
        if count:
            config["ai"]["policy_count"]["total_target"] = count
        if catalog_path:
            config["catalog"]["local_storage"] = catalog_path
        if index_file:
            config["catalog"]["index_file"] = index_file
        if ai_model:
            config["ai"]["model"] = ai_model
        if ai_region:
            config["ai"]["region"] = ai_region
        if temperature is not None:
            config["ai"]["temperature"] = temperature
        if max_tokens:
            config["ai"]["max_tokens"] = max_tokens
        config["output"]["validate_policies"] = fix
        config["output"][
            "include_tests"
        ] = True  # Always copy existing tests from catalog
        config["output"]["fix_policies"] = fix

        # Check if cluster discovery file exists
        if not os.path.exists(input):
            click.echo(f"❌ Cluster discovery file not found: {input}")
            click.echo(
                "💡 Please run 'aegis discover' and 'aegis questionnaire' first."
            )
            sys.exit(1)

        # Check if policy index exists
        index_path = config["catalog"]["index_file"]
        if not os.path.exists(index_path):
            click.echo(f"❌ Policy index not found: {index_path}")
            click.echo(
                "💡 Please run 'aegis catalog' first to build the policy catalog."
            )
            sys.exit(1)

        click.echo(f"🚀 Starting AI-powered policy recommendation...")
        click.echo(f"📄 Input file: {input}")
        click.echo(f"📂 Output directory: {config['output']['directory']}")
        click.echo(
            f"🎯 Target policies: {config['ai']['policy_count']['total_target']}"
        )
        click.echo(f"🤖 AI Model: {config['ai']['model']}")
        click.echo(f"🌍 Region: {config['ai']['region']}")

        # Show Two-Phase selection info
        two_phase_config = config.get("ai", {}).get("two_phase_selection", {})
        if two_phase_config.get("enabled", True):
            click.echo(f"🔄 Two-Phase Selection: Enabled")
            click.echo(
                f"   • Phase 1 candidates: {two_phase_config.get('phase_one_candidates', 150)}"
            )
            click.echo(
                f"   • Phase 2 target: {config['ai']['policy_count']['total_target']}"
            )
        else:
            click.echo(f"⚙️  Two-Phase Selection: Disabled (using legacy selection)")

        start_time = time.time()

        # Load cluster info and requirements from YAML
        click.echo(f"\n📥 Loading cluster information and requirements...")
        with open(input, "r", encoding="utf-8") as f:
            cluster_data = yaml.safe_load(f)

        # Extract cluster info (simplified for demo)
        cluster_info = ClusterInfo(
            version=cluster_data.get("cluster_info", {}).get(
                "kubernetes_version", "unknown"
            ),
            managed_service=cluster_data.get("managed_service"),
            node_count=cluster_data.get("cluster_info", {}).get("node_count", 0),
            namespace_count=cluster_data.get("cluster_info", {}).get(
                "namespace_count", 0
            ),
        )

        # Extract requirements (simplified for demo)
        requirements = GovernanceRequirements(
            compliance_frameworks=cluster_data.get("governance_requirements", {}).get(
                "compliance_frameworks", []
            ),
            registries=cluster_data.get("governance_requirements", {}).get(
                "registries", []
            ),
        )

        # Load policy index
        click.echo(f"📚 Loading policy index from: {index_path}")
        policy_index = load_policy_index_from_file(index_path)
        click.echo(
            f"   ✓ Loaded {policy_index.total_policies} policies from {len(policy_index.categories)} categories"
        )

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
                    region=config["ai"]["region"], model_id=config["ai"]["model"]
                )
                if not bedrock_client.is_available():
                    click.echo(
                        f"⚠️  AI service not available, falling back to rule-based selection"
                    )
            except Exception as e:
                click.echo(f"⚠️  AI initialization failed: {e}")
                click.echo(f"⚠️  Falling back to rule-based selection")

        # Create AI policy selector with output directory and full configuration
        ai_selector = AIPolicySelector(
            bedrock_client,
            config["catalog"]["local_storage"],
            config["output"]["directory"],
            config,  # Pass full configuration for Two-Phase selection
        )

        # Generate recommendations with optional validation and organized output
        click.echo(f"\n🔍 Generating policy recommendations...")
        click.echo(
            f"   • Validation & Test Generation: {'Enabled' if fix else 'Disabled'}"
        )

        # Use progress tracking for AI operations
        try:
            from utils.progress_utils import ProgressTracker, progress_spinner
        except ImportError:
            from aegis.utils.progress_utils import ProgressTracker, progress_spinner

        if fix:
            click.echo(f"🔍 Advanced mode - policies will be validated and organized")

            with progress_spinner("Running AI policy selection and validation"):
                # Use the new organized output method that includes validation
                output_result = ai_selector.generate_organized_output(
                    cluster_info=cluster_info,
                    requirements=requirements,
                    policy_index=policy_index,
                    target_count=config["ai"]["policy_count"]["total_target"],
                )

            recommendation = output_result["recommendation"]
            validation_results = output_result["validation_results"]
            created_files = output_result["created_files"]
            deployment_guide = output_result["deployment_guide"]
            validation_report = output_result["validation_report"]
        else:
            click.echo(
                f"📝 Basic mode - generating recommendations with existing tests (no validation)"
            )

            with progress_spinner("Running AI policy selection"):
                recommendation = ai_selector.generate_complete_recommendation(
                    cluster_info=cluster_info,
                    requirements=requirements,
                    policy_index=policy_index,
                    target_count=config["ai"]["policy_count"]["total_target"],
                )

            validation_results = []
            created_files = {}
            deployment_guide = None
            validation_report = None

        # Handle output based on validation mode
        output_dir = config["output"]["directory"]

        if fix and created_files:
            # Files already created by OutputManager
            click.echo(f"📁 Policies organized with validation and test cases...")
            total_written = sum(len(files) for files in created_files.values())
        else:
            # Basic organization mode - copy policies and existing tests
            click.echo(f"📁 Organizing policies into categories with existing tests...")
            os.makedirs(output_dir, exist_ok=True)

            category_assignment = (
                ai_selector.category_determiner.assign_policies_to_categories(
                    [p.original_policy for p in recommendation.recommended_policies],
                    recommendation.categories,
                )
            )

            total_written = 0
            for category, policies in category_assignment.items():
                if not policies:
                    continue

                category_dir = os.path.join(
                    output_dir, category.lower().replace(" ", "-").replace("&", "and")
                )
                os.makedirs(category_dir, exist_ok=True)

                for policy_entry in policies:
                    recommended_policy = next(
                        (
                            rp
                            for rp in recommendation.recommended_policies
                            if rp.original_policy.name == policy_entry.name
                        ),
                        None,
                    )

                    if recommended_policy:
                        policy_dir = os.path.join(category_dir, policy_entry.name)
                        os.makedirs(policy_dir, exist_ok=True)

                        # Write policy file using original filename from catalog
                        original_filename = os.path.basename(
                            recommended_policy.original_policy.relative_path
                        )
                        policy_file = os.path.join(policy_dir, original_filename)
                        with open(policy_file, "w", encoding="utf-8") as f:
                            f.write(recommended_policy.customized_content)

                        # Copy existing tests from catalog if available
                        if recommended_policy.original_policy.test_directory:
                            import shutil

                            catalog_test_path = os.path.join(
                                config["catalog"]["local_storage"],
                                recommended_policy.original_policy.test_directory,
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
                                                copy_test_files_recursive(
                                                    src_item, dst_item
                                                )
                                            elif item.endswith((".yaml", ".yml")):
                                                # Skip the main policy file (it has the same name as in relative_path)
                                                original_policy_filename = os.path.basename(
                                                    recommended_policy.original_policy.relative_path
                                                )
                                                if item != original_policy_filename:
                                                    shutil.copy2(src_item, dst_item)
                                                    test_files_copied += 1
                                            else:
                                                # Copy other files (like .md, .txt, etc.)
                                                shutil.copy2(src_item, dst_item)
                                                test_files_copied += 1

                                    copy_test_files_recursive(
                                        catalog_test_path, policy_dir
                                    )

                                    if test_files_copied > 0:
                                        click.echo(
                                            f"   ✓ Copied {test_files_copied} test files for {policy_entry.name}"
                                        )
                                except Exception as e:
                                    click.echo(
                                        f"   ⚠️  Could not copy tests for {policy_entry.name}: {e}"
                                    )

                        total_written += 1

        # Calculate duration and show results
        end_time = time.time()
        duration = end_time - start_time

        # Print results with enhanced formatting
        click.echo(
            f"\n✅ Policy recommendation completed successfully in {duration:.1f}s!"
        )
        click.echo(f"📂 Output directory: {output_dir}")

        if validation_report:
            click.echo(f"📄 Validation report: {validation_report}")
        if deployment_guide:
            click.echo(f"📋 Deployment guide: {deployment_guide}")

        # Use progress utilities for better formatting
        try:
            from utils.progress_utils import (
                show_operation_summary,
                show_validation_summary,
                show_file_operations,
                show_next_steps,
            )
        except ImportError:
            from aegis.utils.progress_utils import (
                show_operation_summary,
                show_validation_summary,
                show_file_operations,
                show_next_steps,
            )

        # Show recommendation summary
        recommendation_stats = {
            "Total policies recommended": len(recommendation.recommended_policies),
            "Categories": len(recommendation.categories),
            "AI model used": recommendation.ai_model_used,
            "Files created": total_written,
        }

        show_operation_summary(
            "Policy Recommendation", recommendation_stats, duration, True
        )

        # Show validation results if available
        if validation_results:
            passed_count = sum(1 for r in validation_results if r.passed)
            failed_count = len(validation_results) - passed_count
            fixed_count = sum(1 for r in validation_results if r.fixed_content)
            success_rate = (passed_count / len(validation_results)) * 100

            failed_policy_names = [
                r.policy_name for r in validation_results if not r.passed
            ]
            show_validation_summary(
                len(validation_results),
                passed_count,
                failed_count,
                success_rate,
                failed_policy_names,
            )

            if fixed_count > 0:
                click.echo(f"   • Auto-fixed: {fixed_count}")
        else:
            # Show basic validation summary
            if recommendation.validation_summary:
                click.echo(f"\n📈 Basic Validation Results:")
                for status, count in recommendation.validation_summary.items():
                    if count > 0:
                        click.echo(f"   • {status.title()}: {count}")

        # Show categories and files created
        if created_files:
            click.echo(f"\n📁 Categories Created:")
            for category, files in created_files.items():
                click.echo(f"   • {category}: {len(files)} files")

        # Show file operations summary
        all_created_files = []
        if created_files:
            for category, files in created_files.items():
                all_created_files.extend([f"{category}/{f}" for f in files])

        if all_created_files:
            show_file_operations(all_created_files)

        # Show additional features used (only when --fix is enabled)
        if fix:
            features_used = []
            if validation_results:
                features_used.append("Kyverno validation")
            if (
                any(r.fixed_content for r in validation_results)
                if validation_results
                else False
            ):
                features_used.append("automatic policy fixing")
            if any(p.test_content for p in recommendation.recommended_policies):
                features_used.append("test case generation")

            if features_used:
                click.echo(f"\n🚀 Advanced Features Used: {', '.join(features_used)}")

        # Show next steps
        next_steps = [
            f"Review the generated policies in {output_dir}",
            "Check the deployment guide (if generated) for implementation instructions",
            "Apply policies to your cluster using kubectl or GitOps workflow",
            "Monitor policy violations and adjust configurations as needed",
        ]

        if fix and validation_results and any(not r.passed for r in validation_results):
            next_steps.insert(
                1,
                "Review validation report for any failed policies that need attention",
            )

        show_next_steps(next_steps)

    except KeyboardInterrupt:
        logger.info("Policy recommendation cancelled by user")
        click.echo(f"\n⚠️  Policy recommendation cancelled by user")
        click.echo(f"💡 You can restart with 'aegis recommend' when ready")
        sys.exit(1)
    except AegisError as e:
        logger.error(f"Recommendation failed: {e}")
        click.echo(f"❌ Policy recommendation failed: {e}", err=True)

        # Show specific troubleshooting tips based on error type
        try:
            from utils.progress_utils import show_troubleshooting_tips
        except ImportError:
            from aegis.utils.progress_utils import show_troubleshooting_tips

        if "cluster-discovery.yaml" in str(e).lower():
            tips = [
                "Run 'aegis discover' to generate cluster information",
                "Run 'aegis questionnaire' to add governance requirements",
                "Verify the cluster-discovery.yaml file is valid YAML format",
            ]
        elif "policy index" in str(e).lower() or "catalog" in str(e).lower():
            tips = [
                "Run 'aegis catalog' to build the policy catalog",
                "Check internet connectivity for GitHub repository access",
                "Verify the policy index file exists and is readable",
            ]
        elif "ai" in str(e).lower() or "bedrock" in str(e).lower():
            tips = [
                "Check AWS credentials and Bedrock service availability",
                "Verify the AI model is available in your region",
                "Try using --no-ai flag for rule-based selection",
                "Check network connectivity to AWS services",
            ]
        else:
            tips = [
                "Check the log file for detailed error information",
                "Verify all input files exist and are readable",
                "Try running individual commands (discover, questionnaire, catalog) first",
                "Use 'aegis run --all' for complete workflow with better error recovery",
            ]

        show_troubleshooting_tips(tips)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during recommendation: {e}")
        click.echo(f"❌ Unexpected error during policy recommendation: {e}", err=True)

        try:
            from utils.progress_utils import show_troubleshooting_tips
        except ImportError:
            from aegis.utils.progress_utils import show_troubleshooting_tips

        tips = [
            f"Check the log file for more details: {ctx.obj['config'].get('logging', {}).get('file', './aegis.log')}",
            "Verify all dependencies are installed correctly",
            "Try running with --verbose flag for more detailed output",
            "Report this issue if it persists with log details",
        ]
        show_troubleshooting_tips(tips)
        sys.exit(1)


@cli.command()
@click.option(
    "--directory", "-d", required=True, help="Directory containing policies to validate"
)
@click.option("--fix", is_flag=True, help="Enable AI-powered fixes for failing tests")
@click.option("--ai-model", help="AI model to use for fixes")
@click.option("--ai-region", help="AWS region for Bedrock service")
@click.pass_context
def validate(
    ctx: click.Context,
    directory: str,
    fix: bool,
    ai_model: Optional[str],
    ai_region: Optional[str],
):
    """Validate existing policy directory with Kyverno CLI and optionally apply AI fixes."""
    logger = get_logger("cli.validate")
    logger.info(f"Starting validation of directory: {directory}")

    try:
        import yaml

        try:
            from ai import BedrockClient, KyvernoValidator
            from models import RecommendedPolicy, PolicyCatalogEntry
        except ImportError:
            from aegis.ai import BedrockClient, KyvernoValidator
            from aegis.models import RecommendedPolicy, PolicyCatalogEntry

        # Check if directory exists
        if not os.path.exists(directory):
            click.echo(f"❌ Directory not found: {directory}")
            sys.exit(1)

        click.echo(f"🔍 Validating policies in: {directory}")
        click.echo(f"🤖 AI fixes: {'Enabled' if fix else 'Disabled'}")

        # Initialize Bedrock client if fixes are enabled
        bedrock_client = None
        if fix:
            try:
                config = ctx.obj["config"]

                # Apply CLI overrides
                if ai_model:
                    config["ai"]["model"] = ai_model
                if ai_region:
                    config["ai"]["region"] = ai_region

                bedrock_client = BedrockClient(
                    region=config["ai"]["region"], model_id=config["ai"]["model"]
                )

                if not bedrock_client.is_available():
                    click.echo(f"⚠️  AI service not available, disabling fixes")
                    fix = False
                    bedrock_client = None

            except Exception as e:
                click.echo(f"⚠️  Could not initialize AI service: {e}")
                click.echo(f"⚠️  Disabling AI fixes")
                fix = False
                bedrock_client = None

        # Initialize validator
        validator = KyvernoValidator(bedrock_client=bedrock_client, enable_ai_fixes=fix)

        # Find all policies in the directory
        click.echo(f"📁 Scanning for policy files...")
        policies = []

        for root, dirs, files in os.walk(directory):
            for file in files:
                if (
                    file.endswith(".yaml")
                    and not file.startswith("kyverno-test")
                    and not file.startswith("resource")
                    and not file.startswith("policy-info")
                ):
                    policy_file = os.path.join(root, file)
                    try:
                        with open(policy_file, "r", encoding="utf-8") as f:
                            policy_content = f.read()

                        # Parse policy name - handle multi-document YAML files
                        try:
                            # Try single document first
                            policy_data = yaml.safe_load(policy_content)
                            if not policy_data:
                                # Try multi-document
                                documents = list(yaml.safe_load_all(policy_content))
                                policy_data = next(
                                    (
                                        doc
                                        for doc in documents
                                        if doc
                                        and doc.get("kind")
                                        in ["ClusterPolicy", "Policy"]
                                    ),
                                    None,
                                )

                            if not policy_data or policy_data.get("kind") not in [
                                "ClusterPolicy",
                                "Policy",
                            ]:
                                continue
                        except yaml.YAMLError:
                            continue

                        policy_name = policy_data.get("metadata", {}).get(
                            "name", file.replace(".yaml", "")
                        )

                        # Create minimal policy entry
                        catalog_entry = PolicyCatalogEntry(
                            name=policy_name,
                            category="Existing",
                            description="Existing policy for validation",
                            relative_path=os.path.relpath(policy_file, directory),
                            test_directory=None,
                            source_repo="existing",
                            tags=[],
                        )

                        recommended_policy = RecommendedPolicy(
                            original_policy=catalog_entry,
                            customized_content=policy_content,
                            test_content=None,
                            category="Existing",
                            customizations_applied=[],
                            validation_status="pending",
                        )

                        policies.append(recommended_policy)

                    except Exception as e:
                        click.echo(f"⚠️  Could not process {policy_file}: {e}")

        if not policies:
            click.echo(f"❌ No valid policy files found in {directory}")
            sys.exit(1)

        click.echo(f"✅ Found {len(policies)} policies to validate")

        # Run validation with progress indicator
        click.echo(f"\n🚀 Running Kyverno validation...")

        try:
            from utils.progress_utils import progress_spinner
        except ImportError:
            from aegis.utils.progress_utils import progress_spinner

        with progress_spinner("Validating policies with Kyverno CLI"):
            validation_results, report_file = validator.validate_policies_with_report(
                policies, directory
            )

        # Print results - read from the validation report for accurate test statistics
        validation_report = {}
        failed_policies = []

        try:
            import yaml

            with open(report_file, "r") as f:
                report_data = yaml.safe_load(f)

            validation_report = report_data.get("validation_report", {})
            total_tests = validation_report.get("total_tests", 0)
            failed_tests = validation_report.get("failed_tests", 0)
            success_rate = validation_report.get("success_rate", 0)
            failed_policies = validation_report.get("failed_policies", [])
            test_file_errors = validation_report.get("test_file_errors", [])

            click.echo(f"\n📊 Validation Results:")
            click.echo(f"   • Total tests: {total_tests}")
            click.echo(f"   • Failed tests: {failed_tests}")
            click.echo(f"   • Success rate: {success_rate}%")

            if failed_policies:
                click.echo(f"   • Failed policies: {len(failed_policies)}")

            if test_file_errors:
                click.echo(f"   • Test file errors: {len(test_file_errors)}")

        except Exception as e:
            # Fallback to policy-level statistics if report reading fails
            passed = sum(1 for r in validation_results if r.passed)
            failed = len(validation_results) - passed

            click.echo(f"\n📊 Validation Results:")
            click.echo(f"   • Total policies: {len(validation_results)}")
            click.echo(f"   • Passed: {passed}")
            click.echo(f"   • Failed: {failed}")
            click.echo(
                f"   • Success rate: {(passed/len(validation_results)*100):.1f}%"
            )

        # Additional statistics for AI fixes
        fixed = sum(1 for r in validation_results if r.fixed_content)
        generated = sum(1 for r in validation_results if r.generated_tests)

        if fix:
            click.echo(f"   • AI fixes applied: {fixed}")
            click.echo(f"   • Test cases generated: {generated}")

        if report_file:
            click.echo(f"\n📄 Detailed report: {report_file}")

        # Show failed policies from the report
        if failed_policies:
            click.echo(f"\n❌ Failed Policies:")
            for policy_name in failed_policies:
                click.echo(f"   • {policy_name}")

            # Show failure details from the report
            failures = validation_report.get("failure", [])
            if failures:
                click.echo(f"\n🔍 Test Failures:")
                for failure in failures[:3]:  # Show first 3 failures
                    policy = failure.get("POLICY", "Unknown")
                    reason = failure.get("REASON", "Unknown reason")
                    resource = failure.get("RESOURCE", "Unknown resource")
                    click.echo(f"   • {policy}: {reason}")
                    click.echo(f"     Resource: {resource}")

        # Show test file errors if any
        if "test_file_errors" in locals() and test_file_errors:
            click.echo(f"\n🚨 Test File Errors:")
            for error in test_file_errors:
                path = error.get("path", "Unknown file")
                error_msg = error.get("error", "Unknown error")
                click.echo(f"   • {path}")
                click.echo(f"     Error: {error_msg}")

        if not failed_policies and not (
            test_file_errors if "test_file_errors" in locals() else []
        ):
            # Check if any policies failed at the policy level (fallback)
            failed_count = len(validation_results) - sum(
                1 for r in validation_results if r.passed
            )
            if failed_count > 0:
                click.echo(f"\n❌ Failed Policies:")
                for result in validation_results:
                    if not result.passed:
                        click.echo(f"   • {result.policy_name}")
                        for error in result.errors[:2]:  # Show first 2 errors
                            click.echo(f"     - {error}")
                        if len(result.errors) > 2:
                            click.echo(
                                f"     - ... and {len(result.errors) - 2} more errors"
                            )

        if fix and (fixed > 0 or generated > 0):
            click.echo(f"\n🔧 AI Fixes Applied:")
            if fixed > 0:
                click.echo(f"   • {fixed} policies had test cases fixed")
            if generated > 0:
                click.echo(f"   • {generated} policies had test cases generated")
            click.echo(f"   • Re-run validation to see if issues are resolved")

        click.echo(f"\n✅ Validation completed!")

        # Exit with error code if there were failures
        # Check if there were any failed tests from the report
        failed_tests = (
            validation_report.get("failed_tests", 0) if validation_report else 0
        )
        if failed_tests > 0:
            sys.exit(1)

    except AegisError as e:
        logger.error(f"Validation failed: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during validation: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--all", "run_all", is_flag=True, help="Execute complete workflow")
@click.option(
    "--skip-discovery",
    is_flag=True,
    help="Skip cluster discovery (use existing cluster-discovery.yaml)",
)
@click.option(
    "--skip-questionnaire",
    is_flag=True,
    help="Skip questionnaire (use existing requirements in cluster-discovery.yaml)",
)
@click.option(
    "--skip-catalog", is_flag=True, help="Skip catalog creation (use existing catalog)"
)
@click.option("--output", "-o", help="Output directory for recommended policies")
@click.option("--count", type=int, help="Target number of policies to recommend")
@click.option(
    "--fix", is_flag=True, help="Enable Kyverno validation and automatic fixing"
)
@click.pass_context
def run(
    ctx: click.Context,
    run_all: bool,
    skip_discovery: bool,
    skip_questionnaire: bool,
    skip_catalog: bool,
    output: Optional[str],
    count: Optional[int],
    fix: bool,
):
    """Execute AEGIS workflow."""
    if run_all:
        logger = get_logger("cli.run")
        logger.info("Starting complete AEGIS workflow...")

        try:
            import time
            import os
            from datetime import datetime

            # Progress tracking
            total_steps = 4
            current_step = 0

            def show_progress(step_name: str, step_num: int):
                nonlocal current_step
                current_step = step_num
                progress = (current_step / total_steps) * 100
                click.echo(f"\n{'='*60}")
                click.echo(f"🚀 Step {step_num}/{total_steps}: {step_name}")
                click.echo(f"📊 Progress: {progress:.0f}%")
                click.echo(f"🕐 Time: {datetime.now().strftime('%H:%M:%S')}")
                click.echo(f"{'='*60}")

            start_time = time.time()

            click.echo(f"🎯 AEGIS Complete Workflow Starting...")
            click.echo(
                f"⚙️  Configuration: {ctx.obj.get('config_manager', {}).config_path or 'default'}"
            )

            # Step 1: Cluster Discovery
            if not skip_discovery:
                show_progress("Cluster Discovery", 1)
                try:
                    ctx.invoke(discover)
                    click.echo(f"✅ Cluster discovery completed successfully!")
                except Exception as e:
                    logger.error(f"Cluster discovery failed: {e}")
                    click.echo(f"❌ Cluster discovery failed: {e}")
                    click.echo(
                        f"💡 Use --skip-discovery to skip this step if you have existing cluster-discovery.yaml"
                    )
                    sys.exit(1)
            else:
                show_progress("Cluster Discovery (Skipped)", 1)
                if not os.path.exists("cluster-discovery.yaml"):
                    click.echo(
                        f"❌ cluster-discovery.yaml not found. Cannot skip discovery."
                    )
                    sys.exit(1)
                click.echo(f"⏭️  Using existing cluster-discovery.yaml")

            # Step 2: Requirements Questionnaire
            if not skip_questionnaire:
                show_progress("Requirements Questionnaire", 2)
                try:
                    ctx.invoke(questionnaire)
                    click.echo(f"✅ Requirements questionnaire completed successfully!")
                except Exception as e:
                    logger.error(f"Questionnaire failed: {e}")
                    click.echo(f"❌ Questionnaire failed: {e}")
                    click.echo(
                        f"💡 Use --skip-questionnaire to skip this step if requirements are already in cluster-discovery.yaml"
                    )
                    sys.exit(1)
            else:
                show_progress("Requirements Questionnaire (Skipped)", 2)
                click.echo(
                    f"⏭️  Using existing requirements from cluster-discovery.yaml"
                )

            # Step 3: Policy Catalog Creation
            if not skip_catalog:
                show_progress("Policy Catalog Creation", 3)
                try:
                    ctx.invoke(catalog)
                    click.echo(f"✅ Policy catalog created successfully!")
                except Exception as e:
                    logger.error(f"Catalog creation failed: {e}")
                    click.echo(f"❌ Catalog creation failed: {e}")
                    click.echo(
                        f"💡 Use --skip-catalog to skip this step if you have an existing catalog"
                    )
                    sys.exit(1)
            else:
                show_progress("Policy Catalog Creation (Skipped)", 3)
                config = ctx.obj["config"]
                index_path = config["catalog"]["index_file"]
                if not os.path.exists(index_path):
                    click.echo(
                        f"❌ Policy index not found: {index_path}. Cannot skip catalog creation."
                    )
                    sys.exit(1)
                click.echo(f"⏭️  Using existing policy catalog")

            # Step 4: AI Policy Recommendation
            show_progress("AI Policy Recommendation", 4)
            try:
                # Prepare arguments for recommend command
                recommend_kwargs = {}
                if output:
                    recommend_kwargs["output"] = output
                if count:
                    recommend_kwargs["count"] = count
                recommend_kwargs["fix"] = fix

                ctx.invoke(recommend, **recommend_kwargs)
                click.echo(f"✅ AI policy recommendation completed successfully!")
            except Exception as e:
                logger.error(f"Policy recommendation failed: {e}")
                click.echo(f"❌ Policy recommendation failed: {e}")
                sys.exit(1)

            # Workflow completion summary
            end_time = time.time()
            duration = end_time - start_time

            click.echo(f"\n{'='*60}")
            click.echo(f"🎉 AEGIS Complete Workflow Finished!")
            click.echo(f"⏱️  Total duration: {duration:.1f} seconds")
            click.echo(
                f"📂 Output directory: {output or ctx.obj['config']['output']['directory']}"
            )
            click.echo(f"🚀 Your Kubernetes governance policies are ready!")
            click.echo(f"{'='*60}")

            # Show next steps
            click.echo(f"\n📋 Next Steps:")
            click.echo(f"   1. Review the generated policies in the output directory")
            click.echo(f"   2. Check the deployment guide (if generated)")
            click.echo(f"   3. Apply policies to your cluster using kubectl or GitOps")
            click.echo(f"   4. Monitor policy violations and adjust as needed")

            if fix:
                click.echo(
                    f"\n🔍 Validation was enabled - check validation reports for any issues"
                )

        except KeyboardInterrupt:
            logger.info("Workflow cancelled by user")
            click.echo(f"\n⚠️  Workflow cancelled by user")
            sys.exit(1)
        except AegisError as e:
            logger.error(f"Workflow failed: {e}")
            click.echo(f"❌ Workflow failed: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error in workflow: {e}")
            click.echo(f"❌ Unexpected error: {e}", err=True)
            sys.exit(1)
    else:
        click.echo("🚀 AEGIS - AI Enabled Governance Insights & Suggestions")
        click.echo("")
        click.echo("Available workflow options:")
        click.echo("  --all                    Execute complete workflow")
        click.echo("  --skip-discovery         Skip cluster discovery step")
        click.echo("  --skip-questionnaire     Skip requirements questionnaire")
        click.echo("  --skip-catalog          Skip policy catalog creation")
        click.echo("  --output DIR            Output directory for policies")
        click.echo("  --count N               Target number of policies")
        click.echo("  --fix                   Enable validation and fixing")
        click.echo("")
        click.echo("Example: aegis run --all --fix --count 25")
        click.echo("Example: aegis run --all --skip-discovery --skip-questionnaire")


@cli.command()
@click.option("--init", is_flag=True, help="Initialize default configuration")
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
    try:
        from .. import __version__, __description__

        click.echo(f"AEGIS v{__version__}")
        click.echo(__description__)
    except ImportError:
        # Fallback if import fails
        click.echo("AEGIS v0.1.0")
        click.echo("AI-powered Kubernetes governance policy recommendation tool")


@cli.command()
def examples():
    """Show usage examples and common workflows."""
    click.echo("🚀 AEGIS Usage Examples")
    click.echo("=" * 50)

    click.echo("\n📋 Complete Workflow:")
    click.echo("  aegis run --all                    # Run everything automatically")
    click.echo("  aegis run --all --fix              # Include validation & fixes")

    click.echo("\n🔧 Step-by-step Workflow:")
    click.echo("  aegis config --init                # Initialize configuration")
    click.echo("  aegis discover                     # Scan cluster")
    click.echo("  aegis questionnaire                # Gather requirements")
    click.echo("  aegis catalog                      # Build policy catalog")
    click.echo("  aegis recommend                    # Get recommendations")
    click.echo("  aegis validate -d ./policies --fix # Validate & fix policies")

    click.echo("\n⚙️  Configuration Examples:")
    click.echo("  aegis discover --context prod-cluster")
    click.echo("  aegis catalog --repos https://github.com/kyverno/policies")
    click.echo("  aegis recommend --count 15 --fix")

    click.echo("\n🔍 Validation Examples:")
    click.echo("  aegis validate -d ./my-policies")
    click.echo("  aegis validate -d ./policies --fix")

    click.echo("\n🏥 Health & Troubleshooting:")
    click.echo("  aegis health                       # Check system health")
    click.echo("  aegis version                      # Show version info")
    click.echo("  aegis --debug discover             # Debug mode")

    click.echo("\n💡 Pro Tips:")
    click.echo("  • Use --fix for automatic policy validation and test generation")
    click.echo("  • Run 'aegis health' first to check dependencies")
    click.echo("  • Use --verbose for detailed progress information")
    click.echo("  • Check logs in ./aegis.log for troubleshooting")


@cli.command()
@click.pass_context
def health(ctx: click.Context):
    """Check AEGIS system health and dependencies."""
    logger = get_logger("cli.health")
    logger.info("Running health check...")

    click.echo(f"🏥 AEGIS Health Check")
    click.echo(f"{'='*50}")

    health_status = True

    # Check configuration
    try:
        config = ctx.obj["config"]
        click.echo(f"✅ Configuration: Loaded successfully")
        click.echo(
            f"   • Config file: {ctx.obj.get('config_manager', {}).config_path or 'default'}"
        )
    except Exception as e:
        click.echo(f"❌ Configuration: Failed to load - {e}")
        health_status = False

    # Check Kubernetes connectivity
    try:
        from kubernetes import client, config as k8s_config

        k8s_config.load_kube_config()
        v1 = client.CoreV1Api()
        v1.list_namespace(limit=1)
        click.echo(f"✅ Kubernetes: Connected successfully")
    except Exception as e:
        click.echo(f"❌ Kubernetes: Connection failed - {e}")
        health_status = False

    # Check AWS Bedrock (if configured)
    try:
        ai_config = config.get("ai", {})
        if ai_config.get("provider") == "aws-bedrock":
            try:
                from ai import BedrockClient
            except ImportError:
                from aegis.ai import BedrockClient

            bedrock_client = BedrockClient(
                region=ai_config.get("region", "us-east-1"),
                model_id=ai_config.get(
                    "model", "anthropic.claude-3-sonnet-20240229-v1:0"
                ),
            )
            if bedrock_client.is_available():
                click.echo(f"✅ AWS Bedrock: Available")
                click.echo(f"   • Region: {ai_config.get('region')}")
                click.echo(f"   • Model: {ai_config.get('model')}")
            else:
                click.echo(f"⚠️  AWS Bedrock: Service unavailable")
                click.echo(f"   • Check AWS credentials and region configuration")
        else:
            click.echo(
                f"ℹ️  AWS Bedrock: Not configured (using alternative AI provider)"
            )
    except Exception as e:
        click.echo(f"❌ AWS Bedrock: Error - {e}")
        health_status = False

    # Check policy catalog
    try:
        catalog_config = config.get("catalog", {})
        index_file = catalog_config.get("index_file", "./policy-index.json")
        local_storage = catalog_config.get("local_storage", "./policy-catalog")

        if os.path.exists(index_file):
            click.echo(f"✅ Policy Catalog: Index found")
            click.echo(f"   • Index file: {index_file}")
        else:
            click.echo(f"⚠️  Policy Catalog: Index not found")
            click.echo(f"   • Run 'aegis catalog' to build catalog")

        if os.path.exists(local_storage):
            click.echo(f"✅ Policy Storage: Directory exists")
            click.echo(f"   • Storage path: {local_storage}")
        else:
            click.echo(f"⚠️  Policy Storage: Directory not found")
            click.echo(f"   • Run 'aegis catalog' to create storage")
    except Exception as e:
        click.echo(f"❌ Policy Catalog: Error - {e}")
        health_status = False

    # Check Kyverno CLI (if validation is enabled)
    try:
        import subprocess

        result = subprocess.run(
            ["kyverno", "version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            click.echo(f"✅ Kyverno CLI: Available")
            version_line = (
                result.stdout.split("\n")[0] if result.stdout else "Unknown version"
            )
            click.echo(f"   • {version_line}")
        else:
            click.echo(f"⚠️  Kyverno CLI: Not available")
            click.echo(f"   • Install from: https://kyverno.io/docs/kyverno-cli/")
    except subprocess.TimeoutExpired:
        click.echo(f"⚠️  Kyverno CLI: Command timeout")
    except FileNotFoundError:
        click.echo(f"⚠️  Kyverno CLI: Not installed")
        click.echo(f"   • Install from: https://kyverno.io/docs/kyverno-cli/")
    except Exception as e:
        click.echo(f"⚠️  Kyverno CLI: Error checking - {e}")

    # Check file permissions
    try:
        import tempfile

        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tmp.write(b"test")
            tmp.flush()
        click.echo(f"✅ File System: Write permissions OK")
    except Exception as e:
        click.echo(f"❌ File System: Write permission error - {e}")
        health_status = False

    # Show overall status
    click.echo(f"\n{'='*50}")
    if health_status:
        click.echo(f"🎉 Overall Status: Healthy")
        click.echo(f"💡 All core components are working correctly")
    else:
        click.echo(f"⚠️  Overall Status: Issues detected")
        click.echo(f"💡 Please address the issues above before using AEGIS")

    # Show next steps
    click.echo(f"\n🚀 Recommended Next Steps:")
    if not os.path.exists(
        config.get("catalog", {}).get("index_file", "./policy-index.json")
    ):
        click.echo(f"   1. Run 'aegis catalog' to build policy catalog")
    click.echo(f"   2. Run 'aegis discover' to scan your cluster")
    click.echo(f"   3. Run 'aegis questionnaire' to gather requirements")
    click.echo(f"   4. Run 'aegis recommend' to get policy recommendations")
    click.echo(f"   5. Or use 'aegis run --all' for complete workflow")

    if not health_status:
        sys.exit(1)


@cli.command()
def version():
    """Show AEGIS version information."""
    click.echo("AEGIS CLI v1.0.0")
    click.echo("AI Enabled Governance Insights & Suggestions for Kubernetes")


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n⚠️  Operation cancelled by user.", err=True)
        sys.exit(130)  # Standard exit code for SIGINT
    except AegisError as e:
        click.echo(f"❌ AEGIS Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)

        # Show debug trace if available
        import os

        if os.environ.get("AEGIS_DEBUG") or "--debug" in sys.argv:
            import traceback

            click.echo(f"\nDebug trace:\n{traceback.format_exc()}", err=True)
        else:
            click.echo(
                f"💡 Run with --debug flag for detailed error information", err=True
            )

        sys.exit(1)


if __name__ == "__main__":
    main()
