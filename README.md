# EigenLayer AI Agent

A Python package that integrates AI models with EigenLayer smart contracts to provide decentralized AI inference services.

## Features

- Connect AI models to EigenLayer's decentralized network
- Use OpenRouter to access models from OpenAI, Anthropic, Mistral, and more
- Augment responses with web search capabilities via Tavily
- Submit AI model outputs with cryptographic verification on-chain
- Register and manage AI agents in the EigenLayer network

## Installation

```bash
# Install with pip
pip install -e .

# Or with Poetry
poetry install
```

## Quick Start

1. Initialize configuration files:
   ```bash
   eigenlayer-agent init
   ```

2. Edit the `.env` file with your API keys and settings:
   ```bash
   nano .env
   ```

3. Run a command:
   ```bash
   # Run the agent
   eigenlayer-agent run
   
   # List available models
   eigenlayer-agent list-openrouter-models
   ```

## Usage

```bash
# Run an agent
eigenlayer-agent run --api-key your_openrouter_key --model openai/gpt-4-turbo

# Enable web search capability
eigenlayer-agent run --api-key your_openrouter_key --tavily-api-key your_tavily_key --enable-search

# Test web search
eigenlayer-agent test-search --query "What is EigenLayer?"

# Create a new task
eigenlayer-agent create-task --task-name "sentiment-analysis"

# List registered agents
eigenlayer-agent list-agents
```

## Environment Variables

Set these in your `.env` file to avoid passing them as command-line arguments:

```
# Web3 connection
WEB3_PROVIDER_URI=http://localhost:8545
PRIVATE_KEY=your_private_key

# Contract addresses
ORACLE_ADDRESS=0x...
REGISTRY_ADDRESS=0x...
AGENT_ADDRESS=0x...

# API keys and configuration
OPENROUTER_API_KEY=your_openrouter_api_key
AI_MODEL=openai/gpt-4-turbo
TAVILY_API_KEY=your_tavily_api_key
ENABLE_SEARCH=false
POLLING_INTERVAL=10
```

## Configuration File

The agent also uses a JSON configuration file: `eigenlayer_config.json`:

```json
{
  "provider": "http://localhost:8545",
  "oracle_address": "0x...",
  "registry_address": "0x...",
  "agent_address": "0x...",
  "model": "openai/gpt-4-turbo"
}
```

## Required API Keys

- **OpenRouter API Key**: Access to language models (OpenAI, Anthropic, etc.)
  - Sign up at: [https://openrouter.ai](https://openrouter.ai)
  
- **Tavily API Key**: Optional, for web search capabilities
  - Sign up at: [https://tavily.com](https://tavily.com)

## System Requirements

- Python >=3.10
- Web3 provider (Ethereum node)
- EigenLayer contracts deployed

## License

MIT License 