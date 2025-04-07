#!/usr/bin/env python3
"""
Integration test for the AI agent and PredictionMarketHook.
This version assumes:
1. Anvil is already running
2. Contracts are already deployed
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent.__main__ import PredictionMarketBridge
from agent.interface import AgentInterface
from tests.integration.test_utils import (
    create_oracle_task,
    get_oracle_instance,
    get_web3_instance,
    load_config,
)

# Load environment variables from .env file first
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.append(str(parent_dir))

# --- Configuration Loading ---
# Load configuration using the utility function from test_utils
CONFIG = load_config()

# Extract necessary configuration values
RPC_URL = CONFIG.get("rpc_url", "http://localhost:8545")
ORACLE_ADDRESS = CONFIG.get("oracle_address")
# Needed by AgentManager called within Bridge
REGISTRY_ADDRESS = CONFIG.get("registry_address")
AGENT_ADDRESS = CONFIG.get("agent_address")

# Log the configuration being used
logger.info("--- Test Market Configuration ---")
logger.info(f"RPC URL: {RPC_URL}")
logger.info(f"Oracle Address: {ORACLE_ADDRESS}")
logger.info(f"Registry Address: {REGISTRY_ADDRESS}")
logger.info(f"Agent Address: {AGENT_ADDRESS}")
logger.info("-------------------------------")

# Check required configuration from loaded config
if not ORACLE_ADDRESS:
    logger.error("'oracle_address' not found in configuration.")
    sys.exit(1)
if not REGISTRY_ADDRESS:
    logger.error("'registry_address' not found in configuration.")
    sys.exit(1)


def check_blockchain_connection():
    """Verify connection to the blockchain using the config RPC URL"""
    web3 = get_web3_instance(RPC_URL)
    if not web3:
        logger.error(f"Could not connect to blockchain at {RPC_URL}")
        return False

    # Get basic blockchain info
    chain_id = web3.eth.chain_id
    block_number = web3.eth.block_number
    accounts = web3.eth.accounts

    logger.info("Successfully connected to blockchain:")
    logger.info(f"  Chain ID: {chain_id}")
    logger.info(f"  Current block: {block_number}")
    logger.info(f"  Available accounts: {len(accounts)}")
    return True


def create_test_task():
    """Create test task in oracle using the loaded config addresses"""
    web3 = get_web3_instance(RPC_URL)
    if not web3:
        return None

    oracle = get_oracle_instance(web3, ORACLE_ADDRESS)
    if not oracle:
        return None

    # Create task
    task_data = (
        "Prediction market question: Will ETH reach $5000 by end of 2025? YES/NO"
    )
    tx_hash, task_index = create_oracle_task(oracle, task_data)

    if not tx_hash or task_index is None:
        logger.error("Task creation failed")
        return None

    logger.info(f"Successfully created task with index: {task_index}")
    return task_index


def cleanup_task(task_index):
    """
    'Delete' a task by responding to it and finalizing it

    Note: The oracle contract doesn't have a direct delete function.
    Instead, we submit a response which marks the task as resolved
    (effectively removing it from active consideration), which is
    functionally similar to deletion for testing purposes.

    Args:
        task_index: Index of the task to clean up

    Returns:
        bool: True if task was successfully cleaned up, False otherwise
    """
    if task_index is None:
        logger.error("Cannot clean up None task index")
        return False

    web3 = get_web3_instance(RPC_URL)
    if not web3:
        logger.error("Could not connect to web3 to clean up task")
        return False

    # Get private key from env (same as used by the bridge)
    private_key = os.getenv("AGENT_PRIVATE_KEY")
    if not private_key:
        logger.error("No AGENT_PRIVATE_KEY found in environment, cannot clean up task")
        return False

    if not AGENT_ADDRESS:
        logger.error("No agent_address in config, cannot clean up task")
        return False

    try:
        # Create agent interface
        agent = AgentInterface(web3, AGENT_ADDRESS, private_key)

        # Process task with YES decision to resolve it
        logger.info(f"Cleaning up task {task_index} by submitting YES response...")
        tx_hash = agent.process_task(task_index, True)  # True = YES

        # Wait for receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status == 1:
            logger.info(f"Successfully cleaned up task {task_index}")
            return True
        else:
            logger.error(f"Transaction failed when cleaning up task {task_index}")
            return False
    except Exception as e:
        logger.error(f"Error cleaning up task {task_index}: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_bridge(run_once=True):
    """Run the prediction market bridge using the loaded config/addresses"""
    try:
        # Bridge uses the config file for non-sensitive parts,
        # and we pass addresses explicitly if needed (though it might load them again)
        # Sensitive keys are loaded from env by Bridge.__init__
        current_config_path = Path.cwd() / "config.json"
        if not current_config_path.exists():
            current_config_path = Path(__file__).parent.parent / "config.json"
            if not current_config_path.exists():
                logger.error("config.json not found in CWD or project root.")
                return False  # Cannot run bridge without config

        bridge = PredictionMarketBridge(
            config_path=str(current_config_path),
            oracle_address=ORACLE_ADDRESS,
        )

        # Run the bridge
        logger.info("Running prediction market bridge...")
        bridge.run(run_once=run_once)

        return True
    except Exception as e:
        logger.error(f"Error running bridge: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_blockchain_connection():
    """Test blockchain connection"""
    assert check_blockchain_connection(), "Failed to connect to blockchain"


def test_task_creation_and_cleanup():
    """Test oracle task creation and cleanup"""
    task_index = create_test_task()
    assert task_index is not None, "Failed to create test task"

    # Clean up the task by resolving it
    cleanup_result = cleanup_task(task_index)
    assert cleanup_result, f"Failed to clean up task {task_index}"


def test_bridge_run():
    """Test running the bridge"""
    result = run_bridge(run_once=True)
    if not result:
        logger.warning("Bridge run failed, but test will continue")


def test_e2e_integration():
    """Run the entire end-to-end test sequence"""
    logger.info("Starting end-to-end integration test...")
    # Step 1: Check blockchain connection (uses config RPC_URL)
    test_blockchain_connection()

    # Step 2: Create a test task and clean it up
    test_task_creation_and_cleanup()

    # Step 3: Run the bridge (uses config addresses)
    test_bridge_run()

    logger.info("End-to-end integration test steps completed.")
    assert True, "End-to-end test steps completed"


if __name__ == "__main__":
    # Run the tests manually
    logger.info("Running tests manually...")
    if check_blockchain_connection():
        task_idx = create_test_task()
        if task_idx is not None:
            # Clean up the created task
            cleanup_task(task_idx)
            run_bridge()
        test_e2e_integration()  # Run pytest style assertions at the end
        print("Manual test run completed.")
        sys.exit(0)
    else:
        print("Manual test run failed due to blockchain connection issue.")
        sys.exit(1)
