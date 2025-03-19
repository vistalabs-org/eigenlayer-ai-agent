#!/usr/bin/env python3
"""
Common utility functions for integration tests.
"""

import json
import logging
import os
import sys
from pathlib import Path

# Try to import Web3 and related modules
try:
    import web3
    from web3 import Web3
except ImportError:
    print("Error: web3 package is required. Please install it with: pip install web3")
    sys.exit(1)

# Try to import agent modules
try:
    from agent.oracle import Oracle
    from agent.utils import load_abi, setup_web3

    AGENT_IMPORTS_SUCCESS = True
except ImportError as e:
    print(f"Warning: Failed to import agent modules: {e}")
    print("Make sure you're running this from the eigenlayer-ai-agent directory.")
    AGENT_IMPORTS_SUCCESS = False


def load_config(config_path=None):
    """
    Load configuration from the specified path or search in common locations.
    Returns the loaded config as a dictionary.
    """
    if config_path and Path(config_path).exists():
        with open(config_path, "r") as f:
            config = json.load(f)
            print(f"Using configuration from {config_path}")
            return config

    config_paths = [Path("config.json"), Path.cwd() / "config.json"]

    for path in config_paths:
        if path.exists():
            with open(path, "r") as f:
                config = json.load(f)
                print(f"Using configuration from {path}")
                return config

    # Default config if none found
    print("No configuration file found, using default local setup")
    return {
        "provider": "http://localhost:8545",
        "oracle_address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        "registry_address": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
        "agent_address": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
        "usdc_address": "0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9",
        "prediction_market_address": "0x0165878A594ca255338adfa4d48449f69242Eb8F",
    }


def get_default_private_key():
    """Get the default private key for Anvil testing."""
    return "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def get_web3_instance(provider_uri=None, config=None):
    """
    Get a Web3 instance connected to the specified provider URI.
    If provider_uri is not specified, it's extracted from config.
    If config is not specified, it's loaded using load_config().
    """
    if not provider_uri:
        if not config:
            config = load_config()
        provider_uri = config.get("provider", "http://localhost:8545")

    web3 = setup_web3(provider_uri)
    if not web3.is_connected():
        print(f"Could not connect to {provider_uri}")
        return None

    return web3


def get_oracle_instance(web3, oracle_address=None, private_key=None, config=None):
    """
    Create an Oracle instance with the specified parameters.
    If oracle_address or private_key are not specified, they're extracted from config.
    If config is not specified, it's loaded using load_config().
    """
    if not config:
        config = load_config()

    if not oracle_address:
        oracle_address = config.get("oracle_address")

    if not private_key:
        private_key = get_default_private_key()

    try:
        return Oracle(web3, oracle_address, private_key)
    except Exception as e:
        print(f"Error creating Oracle instance: {e}")
        return None


def create_oracle_task(
    oracle,
    task_data="Prediction market question: Will ETH reach $5000 by the end of 2025? Please respond with YES or NO.",
):
    """
    Create a task in the Oracle contract and return the transaction hash and task index.
    """
    try:
        tx_hash, task_index = oracle.create_task(task_data)
        print(f"Created task with hash: {tx_hash}")
        print(f"Task index: {task_index}")

        # Wait for transaction to be mined
        receipt = oracle.web3.eth.wait_for_transaction_receipt(tx_hash)
        print(
            f"Transaction status: {'Success' if receipt['status'] == 1 else 'Failed'}"
        )

        if receipt["status"] == 1:
            return tx_hash, task_index
        else:
            print(f"Task creation failed")
            return None, None
    except Exception as e:
        print(f"Error creating task: {e}")
        return None, None


def create_minimal_oracle_abi():
    """Create a minimal ABI for basic oracle interactions."""
    # This is a minimal ABI covering common oracle functionality
    # In a production environment, you'd use the full ABI
    return [
        {
            "type": "function",
            "name": "createTask",
            "inputs": [
                {"name": "taskType", "type": "uint8"},
                {"name": "data", "type": "string"},
            ],
            "outputs": [{"type": "uint256"}],
            "stateMutability": "nonpayable",
        },
        {
            "type": "function",
            "name": "getTaskStatus",
            "inputs": [{"name": "taskId", "type": "uint256"}],
            "outputs": [{"type": "uint8"}],
            "stateMutability": "view",
        },
        {
            "type": "function",
            "name": "resolveTask",
            "inputs": [
                {"name": "taskId", "type": "uint256"},
                {"name": "result", "type": "string"},
            ],
            "outputs": [],
            "stateMutability": "nonpayable",
        },
        {
            "type": "function",
            "name": "getTaskCount",
            "inputs": [],
            "outputs": [{"type": "uint256"}],
            "stateMutability": "view",
        },
        {
            "type": "function",
            "name": "getTaskDetails",
            "inputs": [{"name": "taskId", "type": "uint256"}],
            "outputs": [
                {
                    "type": "tuple",
                    "components": [
                        {"name": "creator", "type": "address"},
                        {"name": "taskType", "type": "uint8"},
                        {"name": "status", "type": "uint8"},
                        {"name": "data", "type": "string"},
                        {"name": "result", "type": "string"},
                        {"name": "createdAt", "type": "uint256"},
                    ],
                }
            ],
            "stateMutability": "view",
        },
    ]
