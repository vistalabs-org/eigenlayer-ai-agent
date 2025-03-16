#!/usr/bin/env python3
"""
Integration test for the Prediction Market Bridge.

This script demonstrates and tests the integration between the AI agent
and the PredictionMarketHook contract.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.append(str(parent_dir))

from agent.__main__ import PredictionMarketBridge
from agent.oracle import Oracle
from agent.llm import OpenRouterBackend
from agent.utils import setup_web3

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test Prediction Market Integration")
    
    parser.add_argument(
        "--config", 
        type=str,
        help="Path to configuration file",
        default=str(parent_dir / "eigenlayer_config.json")
    )
    
    parser.add_argument(
        "--oracle-address",
        type=str,
        help="Override Oracle address from config",
        default="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"  # Default from deploy script
    )
    
    parser.add_argument(
        "--market-address",
        type=str,
        help="Address of PredictionMarketHook contract",
        # This will be specific to your deployment
        default=""
    )
    
    parser.add_argument(
        "--private-key",
        type=str,
        help="Private key for sending transactions",
        default="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"  # Default anvil key
    )
    
    return parser.parse_args()

def test_create_ai_task():
    """Test creating a task in the AI Oracle"""
    args = parse_args()
    
    print("=== Testing AI Task Creation ===")
    
    # Set up Web3 connection
    web3 = setup_web3("http://localhost:8545")
    
    # Set up Oracle client
    oracle = Oracle(web3, args.oracle_address, args.private_key)
    
    # Create a task
    task_data = "Prediction market question: Will ETH reach $5000 by the end of 2025? Please respond with YES or NO."
    
    tx_hash, task_index = oracle.create_task(task_data)
    
    print(f"Created task with hash: {tx_hash}")
    print(f"Task index: {task_index}")
    
    # Wait for transaction to be mined
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Transaction status: {'Success' if receipt['status'] == 1 else 'Failed'}")
    
    return task_index

def test_bridge():
    """Test the prediction market bridge"""
    args = parse_args()
    
    print("=== Testing Prediction Market Bridge ===")
    
    # Create a bridge instance
    try:
        bridge = PredictionMarketBridge(
            config_path=args.config,
            oracle_address=args.oracle_address,
            market_address=args.market_address
        )
        
        # Run the bridge once
        print("Running bridge to process any pending tasks...")
        bridge.run(run_once=True)
        
        print("Bridge test completed successfully!")
        
    except Exception as e:
        print(f"Error in bridge test: {e}")
        import traceback
        traceback.print_exc()

def test_full_integration():
    """Test the full integration flow"""
    print("=== Starting Full Integration Test ===")
    
    # 1. Create a task
    task_index = test_create_ai_task()
    
    # 2. Wait a moment for the transaction to be fully processed
    print("Waiting for transaction to be processed...")
    time.sleep(2)
    
    # 3. Run the bridge to process the task
    test_bridge()
    
    print("=== Full Integration Test Complete ===")

if __name__ == "__main__":
    # Configure logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the full integration test
    test_full_integration()
