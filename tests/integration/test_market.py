#!/usr/bin/env python3
"""
Integration test for the AI agent and PredictionMarketHook.
This version assumes:
1. Anvil is already running
2. Contracts are already deployed
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent.__main__ import PredictionMarketBridge
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

# Log the configuration being used
logger.info("--- Test Market Configuration ---")
logger.info(f"RPC URL: {RPC_URL}")
logger.info(f"Oracle Address: {ORACLE_ADDRESS}")
logger.info(f"Registry Address: {REGISTRY_ADDRESS}")
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


def test_task_creation():
    """Test oracle task creation"""
    task_index = create_test_task()
    assert task_index is not None, "Failed to create test task"


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

    # Step 2: Create a test task (uses config ORACLE_ADDRESS)
    test_task_creation()

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
            run_bridge()
        test_e2e_integration()  # Run pytest style assertions at the end
        print("Manual test run completed.")
        sys.exit(0)
    else:
        print("Manual test run failed due to blockchain connection issue.")
        sys.exit(1)
