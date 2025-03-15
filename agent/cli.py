import asyncio
import os
import click
import logging
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

from .utils import setup_web3, load_config, create_directory_structure
from .manager import AgentManager
from .llm import OpenRouterBackend

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

@click.group()
def cli():
    """EigenLayer AI Agent CLI"""
    pass

@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to config file')
@click.option('--provider', '-p', envvar='WEB3_PROVIDER_URI', help='Web3 provider URL')
@click.option('--private-key', envvar='PRIVATE_KEY', help='Private key for signing transactions')
@click.option('--oracle-address', envvar='ORACLE_ADDRESS', help='Oracle contract address')
@click.option('--registry-address', envvar='REGISTRY_ADDRESS', help='Registry contract address')
@click.option('--agent-address', envvar='AGENT_ADDRESS', help='Agent contract address')
@click.option('--api-key', envvar='OPENROUTER_API_KEY', help='API key for OpenRouter')
@click.option('--tavily-api-key', envvar='TAVILY_API_KEY', help='API key for Tavily web search (optional)')
@click.option('--model', '-m', default='openai/gpt-3.5-turbo', envvar='AI_MODEL', help='Model to use (e.g., openai/gpt-4-turbo, anthropic/claude-3-opus)')
@click.option('--enable-search/--disable-search', default=False, envvar='ENABLE_SEARCH', help='Enable web search for responses (requires Tavily API key)')
@click.option('--interval', '-i', default=10, envvar='POLLING_INTERVAL', help='Polling interval in seconds')
def run(config, provider, private_key, oracle_address, registry_address, agent_address, 
        api_key, tavily_api_key, model, enable_search, interval):
    """Run the AI agent"""
    # Load configuration
    cfg = load_config(config)
    
    # Override config with command line arguments
    if provider:
        cfg['provider'] = provider
    if oracle_address:
        cfg['oracle_address'] = oracle_address
    if registry_address:
        cfg['registry_address'] = registry_address
    if agent_address:
        cfg['agent_address'] = agent_address
    if api_key:
        cfg['api_key'] = api_key
    if tavily_api_key:
        cfg['tavily_api_key'] = tavily_api_key
    if model:
        cfg['model'] = model
    if enable_search:
        cfg['enable_search'] = True
    
    # Check for required configuration
    required = ['provider', 'oracle_address', 'registry_address', 'agent_address']
    missing = [key for key in required if key not in cfg]
    if missing:
        raise click.ClickException(f"Missing required configuration: {', '.join(missing)}")
    
    if not private_key:
        raise click.ClickException("Private key is required. Set PRIVATE_KEY environment variable or use --private-key option.")
    
    if not api_key and 'api_key' not in cfg:
        raise click.ClickException("OpenRouter API key is required. Set it via --api-key or OPENROUTER_API_KEY environment variable.")
    
    if enable_search and not tavily_api_key and 'tavily_api_key' not in cfg:
        raise click.ClickException("Tavily API key is required for web search. Set it via --tavily-api-key or TAVILY_API_KEY environment variable.")
    
    # Setup web3
    web3 = setup_web3(cfg['provider'])
    
    # Setup AI backend
    backend_kwargs = {}
    if 'api_key' in cfg:
        backend_kwargs['api_key'] = cfg['api_key']
    if 'model' in cfg:
        backend_kwargs['model'] = cfg['model']
    if 'tavily_api_key' in cfg:
        backend_kwargs['tavily_api_key'] = cfg['tavily_api_key']
    
    try:
        ai_backend = OpenRouterBackend(api_key=api_key or cfg.get('api_key'), 
                                       model=model or cfg.get('model', 'openai/gpt-3.5-turbo'),
                                       tavily_api_key=tavily_api_key or cfg.get('tavily_api_key'))
    except Exception as e:
        raise click.ClickException(f"Failed to initialize OpenRouter backend: {e}")
    
    # Create agent manager
    manager = AgentManager(
        web3=web3,
        oracle_address=cfg['oracle_address'],
        registry_address=cfg['registry_address'],
        agent_address=cfg['agent_address'],
        private_key=private_key,
        ai_backend=ai_backend
    )
    
    # Set search mode if enabled and available
    if cfg.get('enable_search', False):
        if 'tavily_api_key' not in cfg:
            click.echo("Warning: Web search enabled but no Tavily API key provided. Search will be disabled.")
        else:
            click.echo("Web search enabled. AI responses will be augmented with search results.")
            # Here you would set the search mode on the manager
            # This part depends on how your manager is implemented to support search
    
    # Run the agent
    click.echo(f"Starting AI agent using model {ai_backend.model}")
    try:
        asyncio.run(manager.monitor_tasks(polling_interval=interval))
    except KeyboardInterrupt:
        click.echo("Agent stopped")

@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to config file')
@click.option('--provider', '-p', envvar='WEB3_PROVIDER_URI', help='Web3 provider URL')
@click.option('--private-key', envvar='PRIVATE_KEY', help='Private key for signing transactions')
@click.option('--task-name', required=True, help='Name of the task to create')
@click.option('--oracle-address', envvar='ORACLE_ADDRESS', help='Oracle contract address')
def create_task(config, provider, private_key, task_name, oracle_address):
    """Create a new task in the oracle"""
    # Load configuration
    cfg = load_config(config)
    
    # Override config with command line arguments
    if provider:
        cfg['provider'] = provider
    if oracle_address:
        cfg['oracle_address'] = oracle_address
    
    # Check for required configuration
    if 'oracle_address' not in cfg:
        raise click.ClickException("Oracle address is required. Set it via --oracle-address or ORACLE_ADDRESS environment variable.")
    
    if 'provider' not in cfg:
        raise click.ClickException("Web3 provider URI is required. Set it via --provider or WEB3_PROVIDER_URI environment variable.")
    
    if not private_key:
        raise click.ClickException("Private key is required. Set PRIVATE_KEY environment variable or use --private-key option.")
    
    # Setup web3
    web3 = setup_web3(cfg['provider'])
    
    # Create oracle client
    from .oracle import Oracle
    oracle = Oracle(web3, cfg['oracle_address'], private_key)
    
    # Create task
    try:
        tx_hash, task_index = oracle.create_task(task_name)
        click.echo(f"Task created: index={task_index}, tx_hash={tx_hash}")
    except Exception as e:
        raise click.ClickException(f"Failed to create task: {e}")

@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to config file')
@click.option('--provider', '-p', envvar='WEB3_PROVIDER_URI', help='Web3 provider URL')
@click.option('--registry-address', envvar='REGISTRY_ADDRESS', help='Registry contract address')
def list_agents(config, provider, registry_address):
    """List all registered agents"""
    # Load configuration
    cfg = load_config(config)
    
    # Override config with command line arguments
    if provider:
        cfg['provider'] = provider
    if registry_address:
        cfg['registry_address'] = registry_address
    
    # Check for required configuration
    if 'registry_address' not in cfg:
        raise click.ClickException("Registry address is required. Set it via --registry-address or REGISTRY_ADDRESS environment variable.")
    
    if 'provider' not in cfg:
        raise click.ClickException("Web3 provider URI is required. Set it via --provider or WEB3_PROVIDER_URI environment variable.")
    
    # Setup web3
    web3 = setup_web3(cfg['provider'])
    
    # Create registry client
    from .registry import Registry
    registry = Registry(web3, cfg['registry_address'])
    
    # List agents
    try:
        agents = registry.get_all_agents()
        click.echo(f"Found {len(agents)} registered agents:")
        for i, agent in enumerate(agents):
            try:
                details = registry.get_agent_details(agent)
                click.echo(f"{i+1}. {agent}")
                click.echo(f"   Model: {details['model_type']} {details['model_version']}")
                click.echo(f"   Tasks: {details['tasks_completed']}")
                click.echo(f"   Consensus participations: {details['consensus_participations']}")
                click.echo(f"   Rewards: {details['rewards_earned']}")
            except Exception as e:
                click.echo(f"{i+1}. {agent} (Error fetching details: {e})")
    except Exception as e:
        raise click.ClickException(f"Failed to list agents: {e}")

@cli.command()
def init():
    """Initialize the EigenLayer AI agent"""
    # Create directory structure
    create_directory_structure()
    
    # Create sample config
    config_path = Path.cwd() / "eigenlayer_config.json"
    if not config_path.exists():
        sample_config = {
            "provider": "http://localhost:8545",
            "oracle_address": "0x...",
            "registry_address": "0x...",
            "agent_address": "0x...",
            "model": "openai/gpt-4-turbo"
        }
        
        with open(config_path, 'w') as f:
            import json
            json.dump(sample_config, f, indent=2)
        
        click.echo(f"Created sample config at {config_path}")
    
    # Create .env file
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        with open(env_path, 'w') as f:
            f.write("# EigenLayer AI Agent Environment Variables\n\n")
            f.write("# Web3 connection\n")
            f.write("WEB3_PROVIDER_URI=http://localhost:8545\n")
            f.write("PRIVATE_KEY=\n\n")
            f.write("# Contract addresses\n")
            f.write("ORACLE_ADDRESS=\n")
            f.write("REGISTRY_ADDRESS=\n")
            f.write("AGENT_ADDRESS=\n\n")
            f.write("# OpenRouter configuration\n")
            f.write("OPENROUTER_API_KEY=\n")
            f.write("AI_MODEL=openai/gpt-3.5-turbo\n\n")
            f.write("# Web search configuration\n")
            f.write("TAVILY_API_KEY=\n")
            f.write("ENABLE_SEARCH=false\n\n")
            f.write("# Other settings\n")
            f.write("POLLING_INTERVAL=10\n")
        
        click.echo(f"Created .env file at {env_path}")
    
    click.echo("Initialization complete. Edit the config files to add your contract addresses and API keys.")

@cli.command()
@click.option('--api-key', envvar='OPENROUTER_API_KEY', help='OpenRouter API key')
def list_openrouter_models(api_key):
    """List all available models on OpenRouter"""
    if not api_key:
        raise click.ClickException("OpenRouter API key is required. Set it via --api-key or OPENROUTER_API_KEY environment variable.")
    
    try:
        backend = OpenRouterBackend(api_key=api_key)
        models = backend.list_available_models()
        click.echo(f"Available models on OpenRouter ({len(models)}):")
        for model in models:
            click.echo(f"- {model}")
    except Exception as e:
        raise click.ClickException(f"Error fetching models: {e}")

@cli.command()
@click.option('--api-key', envvar='OPENROUTER_API_KEY', help='OpenRouter API key')
@click.option('--tavily-api-key', envvar='TAVILY_API_KEY', help='Tavily API key')
@click.option('--query', required=True, help='Search query to test')
def test_search(api_key, tavily_api_key, query):
    """Test the Tavily web search integration"""
    if not api_key:
        raise click.ClickException("OpenRouter API key is required. Set it via --api-key or OPENROUTER_API_KEY environment variable.")
    if not tavily_api_key:
        raise click.ClickException("Tavily API key is required. Set it via --tavily-api-key or TAVILY_API_KEY environment variable.")
    
    try:
        backend = OpenRouterBackend(api_key=api_key, tavily_api_key=tavily_api_key)
        click.echo(f"Searching for: {query}")
        
        # Perform web search
        results = backend.search_web(query)
        click.echo(f"Found {len(results)} results:")
        
        for i, result in enumerate(results, 1):
            click.echo(f"\n{i}. {result['title']}")
            click.echo(f"   {result['content'][:150]}...")
            click.echo(f"   Source: {result['url']}")
        
        # Generate response with search
        click.echo("\nGenerating response with search results...")
        response = backend.generate_response_with_search(query)
        click.echo("\nAI Response:")
        click.echo(response)
        
    except Exception as e:
        raise click.ClickException(f"Error testing search: {e}")

def main():
    """Entry point for the CLI"""
    cli()

if __name__ == '__main__':
    main()