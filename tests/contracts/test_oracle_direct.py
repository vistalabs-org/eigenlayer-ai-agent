#!/usr/bin/env python3
"""
Direct oracle contract testing script without mocks.
This script tests interactions with the oracle contract deployed on a local Anvil instance.
"""

import json
import sys
from pathlib import Path
from web3 import Web3
import web3

print(f"Using Web3.py version: {web3.__version__}")

class OracleContractTester:
    """Test client for interacting directly with the deployed Oracle contract"""
    
    def __init__(self, config_path=None):
        """Initialize the tester with the local config"""
        # Load configuration
        if config_path is None:
            config_path = Path("eigenlayer_config.local.json")
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        # Connect to the blockchain
        provider_uri = self.config["provider"]
        self.web3 = Web3(Web3.HTTPProvider(provider_uri))
        if not self.web3.is_connected():
            raise ConnectionError(f"Failed to connect to {provider_uri}")
        
        print(f"Connected to blockchain at {provider_uri}")
        print(f"Chain ID: {self.web3.eth.chain_id}")
        
        # Default Anvil private key and account
        self.private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        self.account = self.web3.eth.account.from_key(self.private_key)
        print(f"Using account: {self.account.address}")
        
        # Load oracle contract address
        self.oracle_address = self.web3.to_checksum_address(self.config["oracle_address"])
        print(f"Oracle contract address: {self.oracle_address}")
        
        # Check if the contract has code at the address
        code_size = len(self.web3.eth.get_code(self.oracle_address))
        if code_size == 0:
            print("Warning: No contract code found at the oracle address.")
        else:
            print(f"Contract code size: {code_size} bytes")
    
    def create_minimal_oracle_abi(self):
        """Create a minimal ABI for basic oracle interactions"""
        # This is a minimal ABI covering common oracle functionality
        # In a production environment, you'd use the full ABI
        return [
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
                "name": "getTaskStatus",
                "inputs": [{"name": "taskId", "type": "uint256"}],
                "outputs": [{"type": "uint8"}],
                "stateMutability": "view"
            },
            {
                "type": "function",
                "name": "resolveTask",
                "inputs": [
                    {"name": "taskId", "type": "uint256"},
                    {"name": "result", "type": "string"}
                ],
                "outputs": [],
                "stateMutability": "nonpayable"
            },
            {
                "type": "function",
                "name": "getTaskCount",
                "inputs": [],
                "outputs": [{"type": "uint256"}],
                "stateMutability": "view"
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
                            {"name": "createdAt", "type": "uint256"}
                        ]
                    }
                ],
                "stateMutability": "view"
            }
        ]
    
    def test_oracle_contract(self):
        """Test basic oracle contract functionality"""
        # Create contract instance with minimal ABI
        oracle_contract = self.web3.eth.contract(
            address=self.oracle_address,
            abi=self.create_minimal_oracle_abi()
        )
        
        print("\n=== Testing Oracle Contract ===")
        
        # Try to call view functions first
        try:
            # Try to get task count 
            # Note: This may fail if the contract doesn't have this exact function
            try:
                task_count = oracle_contract.functions.getTaskCount().call()
                print(f"Task count: {task_count}")
            except Exception as e:
                print(f"Could not get task count: {e}")
            
            # Try with a different function name that might exist
            try:
                task_count = oracle_contract.functions.taskCount().call()
                print(f"Task count (alternative method): {task_count}")
            except Exception as e:
                print(f"Could not get task count with alternative method: {e}")
            
            # Try to get information about a task if tasks exist
            try:
                task_details = oracle_contract.functions.getTaskDetails(0).call()
                print(f"Task 0 details: {task_details}")
            except Exception as e:
                print(f"Could not get task details: {e}")
            
            # Try using a different function name
            try:
                task_status = oracle_contract.functions.getTaskStatus(0).call()
                print(f"Task 0 status: {task_status}")
            except Exception as e:
                print(f"Could not get task status: {e}")
            
            return True
        except Exception as e:
            print(f"Error testing oracle contract: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def try_create_task(self, task_data="Test task data"):
        """Try to create a new task in the oracle"""
        # Create contract instance with minimal ABI
        oracle_contract = self.web3.eth.contract(
            address=self.oracle_address,
            abi=self.create_minimal_oracle_abi()
        )
        
        print("\n=== Creating a New Task ===")
        
        try:
            # Try to create a task
            # Note: This is a write operation that will require gas
            task_type = 1  # Assuming 1 is a valid task type
            
            # Build transaction
            tx = oracle_contract.functions.createTask(
                task_type, 
                task_data
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.web3.eth.get_transaction_count(self.account.address),
                'gas': 500000,
                'gasPrice': self.web3.eth.gas_price
            })
            
            # Sign transaction
            signed_tx = self.account.sign_transaction(tx)
            
            # Send transaction
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"Transaction sent: {tx_hash.hex()}")
            
            # Wait for transaction receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"Transaction confirmed in block {receipt.blockNumber}")
            print(f"Gas used: {receipt.gasUsed}")
            
            if receipt.status == 1:
                print("Task created successfully!")
            else:
                print("Transaction failed!")
            
            return True
        except Exception as e:
            print(f"Error creating task: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def inspect_contract(self):
        """Try to inspect the contract bytecode and estimate function signatures"""
        print("\n=== Inspecting Contract Bytecode ===")
        
        # Get contract bytecode
        bytecode = self.web3.eth.get_code(self.oracle_address).hex()
        
        # We can't easily reverse engineer the ABI from bytecode
        # But we can check if it's a minimal contract or contains real code
        
        if len(bytecode) <= 100:
            print("This appears to be a minimal contract without much functionality.")
            print("The mock contract deployed might not have the Oracle functionality implemented.")
            
            if bytecode.startswith("0x60806040"):
                print("This appears to be a standard Solidity contract.")
            
            print(f"Bytecode: {bytecode}")
        else:
            print(f"Contract has substantial bytecode ({len(bytecode)} bytes)")
            print("This may be a functional contract, but we need the correct ABI to interact with it.")
        
        return True

def main():
    """Main function to run the oracle contract tests"""
    try:
        tester = OracleContractTester()
        
        # Test view functions first
        tester.test_oracle_contract()
        
        # Inspect contract
        tester.inspect_contract()
        
        # Ask before trying to create a task
        print("\nWould you like to try creating a task? This will use gas. (y/n)")
        response = input().strip().lower()
        
        if response == 'y':
            tester.try_create_task()
        
        print("\nOracle contract testing completed!")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 