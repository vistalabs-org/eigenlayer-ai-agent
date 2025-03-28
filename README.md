# EigenLayer AI Agent

An AI agent system integrated with EigenLayer for prediction markets and oracle services.

## High-Level Schema

```mermaid
graph TD;

%% Define main components
subgraph User
    A[User Creates Market]
    B[User Trades]
end

subgraph Python_Agents
    subgraph Agent 1
        K1[AI Agent]
        Q1[LLM Backend]
    end
    subgraph Agent 2
        K2[AI Agent]
        Q2[LLM Backend]
    end
    subgraph Agent3
        K3[AI Agent]
        Q3[LLM Backend]
    end
end

subgraph EigenLayer
    D[PredictionMarketHook]
    E[AIOracleServiceManager]
end

%% Define connections
A -->|Interacts with| D
B -->|Interacts with| D
D --> E[AIOracleServiceManager]

E -->|Communicates with| K1
E -->|Communicates with| K2
E -->|Communicates with| K3

K1 -->|Uses| Q1
K2 -->|Uses| Q2
K3 -->|Uses| Q3
```


## Installation

### Using Poetry

```bash
git clone https://github.com/vistalabs-org/eigenlayer-ai-agent.git
cd eigenlayer-ai-agent
poetry install
```

## Configuration

Create a configuration file `config.json` with the following structure:

```json
{
  "rpc_url": "http://localhost:8545",
  "oracle_address": "0x...",
  "registry_address": "0x...",
  "agent_address": "0x...",
  "model": "openai/gpt-4-turbo",
  "api_key": "your-openrouter-api-key",
  "private_key": "your-private-key"
}
```


## Usage

### Run the AI Agent

```bash
poetry run agent --config config.json
```

### Command Line Options

```
--config CONFIG       Path to configuration file
--interval INTERVAL   Polling interval in seconds
--run-once            Run the script once and exit
--oracle-address ORACLE_ADDRESS
                      Override Oracle address from config
--market-address MARKET_ADDRESS
                      Address of PredictionMarketHook contract
```

## Development

### Testing

```bash
poetry run pytest
```

### Format Code

```bash
poetry run black .
poetry run isort .
```


## Detailed Schema


```mermaid
graph TD;

%% Define subgraphs
subgraph User
    A[User Creates Market]
end

subgraph Python_Agent
    K[PredictionMarketBridge.py]
    L[AgentManager.py]
    M[Oracle.py]
    N[AgentInterface.py]
    O[OpenRouterBackend.py]
    P[Registry.py]
    Q[LLM Backend]
end

%% Define connections
A --> K
K --> L
L --> M
L --> N
L --> P
K --> O
O --> Q
```