#!/usr/bin/env python3
"""
Test script for testing the agent's Oracle module with a real contract.
"""

import json
import sys
import os
import time
from pathlib import Path

# Get ABI files from the project
def find_abi_files():
    """Find all ABI files in the project"""
    abi_paths = []
    
    # Check common locations
    potential_paths = [
        "contracts/out",
        "abi",
        "build/contracts",
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".json"):
                        abi_paths.append(os.path.join(root, file))
    
    if not abi_paths:
        print("Warning: No ABI files found")
    else:
        print(f"Found {len(abi_paths)} ABI files")
        for path in abi_paths[:5]:  # Show just the first 5
            print(f"  - {path}")
        if len(abi_paths) > 5:
            print(f"  - ... and {len(abi_paths) - 5} more")
    
    return abi_paths

# Try to import Web3 and related modules
try:
    from web3 import Web3
    import web3
    print(f"Using Web3.py version: {web3.__version__}")
except ImportError:
    print("Error: web3 package is required. Please install it with: pip install web3")
    sys.exit(1)

# Try to import agent modules
try:
    from agent.oracle import Oracle
    from agent.utils import load_abi, setup_web3
    AGENT_IMPORTS_SUCCESS = True
    print("Successfully imported agent modules")
except ImportError as e:
    print(f"Warning: Failed to import agent modules: {e}")
    print("Make sure you're running this from the eigenlayer-ai-agent directory.")
    AGENT_IMPORTS_SUCCESS = False

class OracleModuleTester:
    """Test the Oracle module with real contracts"""
    
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path("eigenlayer_config.local.json")
            # Check local file first, fall back to main config
            if not config_path.exists():
                config_path = Path("eigenlayer_config.json")
        
        if not config_path.exists():
            # Create a default config with known local addresses
            print(f"Configuration file not found: {config_path}, using default local setup")
            self.config = {
                "provider": "http://localhost:8545",
                "oracle_address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
                "registry_address": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
                "agent_address": "0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9"
            }
        else:
            with open(config_path, "r") as f:
                self.config = json.load(f)
        
        # Default Anvil private key 
        self.private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        
        # Set up Web3 connection
        self.provider_uri = self.config["provider"]
        self.web3 = Web3(Web3.HTTPProvider(self.provider_uri))
        if not self.web3.is_connected():
            raise ConnectionError(f"Failed to connect to {self.provider_uri}")
            
        self.account = self.web3.eth.account.from_key(self.private_key)
        print(f"Connected to blockchain at {self.provider_uri}")
        print(f"Chain ID: {self.web3.eth.chain_id}")
        print(f"Using account: {self.account.address}")
        
        # Initialize Oracle client
        self.oracle_address = self.config["oracle_address"]
        
        # Check if the contract has code
        code_size = len(self.web3.eth.get_code(self.web3.to_checksum_address(self.oracle_address)))
        if code_size == 0:
            print("Warning: No contract code found at the oracle address.")
        else:
            print(f"Oracle contract code size: {code_size} bytes")
        
        # Find ABI files
        self.abi_files = find_abi_files()
    
    def initialize_oracle_client(self):
        """Try to initialize the Oracle client with different approaches"""
        print("\n=== Initializing Oracle Client ===")
        
        # Method 1: Using agent's Oracle module directly
        if AGENT_IMPORTS_SUCCESS:
            try:
                self.oracle = Oracle(
                    self.web3,
                    self.oracle_address,
                    self.private_key
                )
                print("Successfully initialized Oracle client using agent module")
                return True
            except Exception as e:
                print(f"Error initializing with agent module: {e}")
                import traceback
                traceback.print_exc()
        
        # Method 2: Try to manually create Oracle client with known ABI from files
        try:
            # Try to find oracle ABI file
            oracle_abi = None
            for abi_path in self.abi_files:
                if "Oracle" in abi_path:
                    print(f"Found potential Oracle ABI file: {abi_path}")
                    try:
                        with open(abi_path, "r") as f:
                            abi_data = json.load(f)
                        
                        # Check if it's just the ABI or a compilation output
                        if isinstance(abi_data, list):
                            oracle_abi = abi_data
                        elif "abi" in abi_data:
                            oracle_abi = abi_data["abi"]
                        
                        print("Successfully loaded Oracle ABI")
                        break
                    except Exception as e:
                        print(f"Error loading ABI from {abi_path}: {e}")
            
            if oracle_abi:
                # Create contract with the ABI
                self.oracle_contract = self.web3.eth.contract(
                    address=self.web3.to_checksum_address(self.oracle_address),
                    abi=oracle_abi
                )
                print("Successfully created Oracle contract with ABI")
                return True
            else:
                print("Could not find a valid Oracle ABI")
        except Exception as e:
            print(f"Error creating Oracle contract with ABI: {e}")
            import traceback
            traceback.print_exc()
        
        # Method 3: Use a minimal ABI for basic functionality
        try:
            minimal_abi = [
                {
                    "type": "function",
                    "name": "latestTaskNum",
                    "inputs": [],
                    "outputs": [{"type": "uint256"}],
                    "stateMutability": "view"
                },
                {
                    "type": "function",
                    "name": "createTask",
                    "inputs": [
                        {"name": "taskType", "type": "uint8"},
                        {"name": "data", "type": "string"}
                    ],
                    "outputs": [{"type": "uint256"}],
                    "stateMutability": "nonpayable"
                },
                {
                    "type": "function",
                    "name": "getTask",
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
                                {"name": "createdAt", "type": "uint256"}
                            ]
                        }
                    ],
                    "stateMutability": "view"
                }
            ]
            
            self.oracle_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(self.oracle_address),
                abi=minimal_abi
            )
            print("Created Oracle contract with minimal ABI")
            return True
        except Exception as e:
            print(f"Error creating Oracle contract with minimal ABI: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_oracle_module(self):
        """Test the Oracle module functionality"""
        if not hasattr(self, "oracle") and not hasattr(self, "oracle_contract"):
            print("No Oracle client initialized. Run initialize_oracle_client() first.")
            return False
        
        print("\n=== Testing Oracle Module ===")
        
        # Test Oracle client if available
        if hasattr(self, "oracle"):
            try:
                print("Testing agent's Oracle module:")
                
                try:
                    # Try to get latest task number
                    task_num = self.oracle.contract.functions.latestTaskNum().call()
                    print(f"Latest task number: {task_num}")
                except Exception as e:
                    print(f"Could not get latest task number: {e}")
                
                try:
                    # Try to get a task
                    task = self.oracle.reconstruct_task(0)
                    print(f"Task 0: {task}")
                except Exception as e:
                    print(f"Could not get task 0: {e}")
                
                return True
            except Exception as e:
                print(f"Error testing Oracle module: {e}")
                import traceback
                traceback.print_exc()
        
        # Test with contract if available
        if hasattr(self, "oracle_contract"):
            try:
                print("Testing with direct contract instance:")
                
                try:
                    # Try to get latest task number using different function names
                    try:
                        task_num = self.oracle_contract.functions.latestTaskNum().call()
                        print(f"Latest task number: {task_num}")
                    except Exception:
                        try:
                            task_num = self.oracle_contract.functions.taskCount().call()
                            print(f"Task count: {task_num}")
                        except Exception as e:
                            print(f"Could not get task count: {e}")
                except Exception as e:
                    print(f"Error getting task count: {e}")
                
                try:
                    # Try to get a task
                    try:
                        task = self.oracle_contract.functions.getTask(0).call()
                        print(f"Task 0: {task}")
                    except Exception:
                        try:
                            task = self.oracle_contract.functions.tasks(0).call()
                            print(f"Task 0: {task}")
                        except Exception as e:
                            print(f"Could not get task 0: {e}")
                except Exception as e:
                    print(f"Error getting task: {e}")
                
                return True
            except Exception as e:
                print(f"Error testing with direct contract: {e}")
                import traceback
                traceback.print_exc()
        
        return False
    
    def try_create_task(self, task_data="Test task from agent"):
        """Try to create a task using the Oracle"""
        if not hasattr(self, "oracle"):
            print("No Oracle client initialized. Run initialize_oracle_client() first.")
            return False
        
        print("\n=== Creating a Task ===")
        
        # Try with Oracle client
        try:
            print("Creating task with Oracle module...")
            tx_hash, task_index = self.oracle.create_task(task_data)
            print(f"Created task with transaction hash: {tx_hash}")
            print(f"Task index: {task_index}")
            return True
        except Exception as e:
            print(f"Error creating task with Oracle module: {e}")
            import traceback
            traceback.print_exc()
        
        # Alternative direct approach with Web3 - get contract using the same ABI as the Oracle client
        try:
            print("Trying fallback direct contract approach...")
            
            # Make sure we have the contract ABI
            if not hasattr(self.oracle, "contract"):
                print("No contract available in Oracle client")
                return False
                
            # Get function from contract
            contract = self.oracle.contract
            func = contract.functions.createNewTask(task_data)
            
            # Get latest transaction details
            nonce = self.web3.eth.get_transaction_count(self.account.address)
            gas_price = self.web3.eth.gas_price
            
            # Build transaction
            tx = func.build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 3000000,
                'gasPrice': gas_price
            })
            
            # Sign transaction
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            
            # Fix Web3.py version compatibility - use raw_transaction instead of rawTransaction
            raw_tx = signed_tx.raw_transaction if hasattr(signed_tx, 'raw_transaction') else signed_tx.rawTransaction
            
            # Send transaction
            tx_hash = self.web3.eth.send_raw_transaction(raw_tx)
            print(f"Transaction hash: {tx_hash.hex()}")
            
            # Wait for receipt
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            if tx_receipt['status'] == 1:
                print(f"Transaction successful, task created")
                # Try to get task index from event logs
                try:
                    receipt_logs = contract.events.NewTaskCreated().process_receipt(tx_receipt)
                    if receipt_logs:
                        print(f"Task created with index: {receipt_logs[0]['args']['taskIndex']}")
                except Exception as e:
                    print(f"Could not get task index from logs: {e}")
                
                return True
            else:
                print(f"Transaction failed")
                return False
        except Exception as e:
            print(f"Error with fallback approach: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main function to run the tests"""
    try:
        tester = OracleModuleTester()
        
        # Initialize the Oracle client
        if tester.initialize_oracle_client():
            # Test the Oracle functionality
            tester.test_oracle_module()
            
            # Ask if user wants to try creating a task
            print("\nWould you like to try creating a task? This will use gas. (y/n)")
            response = input().strip().lower()
            
            if response == 'y':
                tester.try_create_task()
        
        print("\nOracle module testing completed!")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
