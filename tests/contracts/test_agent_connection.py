#!/usr/bin/env python3
"""
Test script for verifying basic connection between the agent and mock contracts.
This script is used after setting up the mock environment with mock_testing.py.
"""

import json
import sys
from pathlib import Path

# Try to import agent modules
try:
    from agent.oracle import Oracle
    from agent.agent import Agent
    from agent.registry import Registry
    from agent.utils import setup_web3
    AGENT_IMPORTS_SUCCESS = True
except ImportError:
    print("Warning: Failed to import agent modules.")
    print("Make sure you're running this from the eigenlayer-ai-agent directory.")
    AGENT_IMPORTS_SUCCESS = False

# Web3 is required for basic operations
try:
    from web3 import Web3
except ImportError:
    print("Error: web3 package is required. Please install it with: pip install web3")
    sys.exit(1)

class MockERC20:
    """Simple mock ERC20 implementation for USDC"""
    
    def __init__(self, web3, address):
        self.web3 = web3
        self.address = address
        
        # Minimal ABI for name() and balanceOf()
        self.abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        self.contract = self.web3.eth.contract(address=self.address, abi=self.abi)
    
    def get_balance(self, address):
        """Mock balanceOf that returns a fake balance"""
        # Since our contract is empty, return a mock balance
        return 1000000000  # 1000 USDC with 6 decimals

class MockContractTester:
    """Test client for verifying agent connection with mock contracts"""
    
    def __init__(self, config_path=None):
        """
        Initialize the test client
        
        Args:
            config_path: Path to the configuration file
        """
        if config_path is None:
            config_path = Path("eigenlayer_config.local.json")
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        # Default Anvil private key
        self.private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        
        # Set up Web3 connection
        self.web3 = Web3(Web3.HTTPProvider(self.config["provider"]))
        if not self.web3.is_connected():
            raise ConnectionError(f"Failed to connect to {self.config['provider']}")
            
        self.account = self.web3.eth.account.from_key(self.private_key)
        print(f"Connected to blockchain with account: {self.account.address}")
        
        if not AGENT_IMPORTS_SUCCESS:
            print("Agent modules not available, using mock implementation")
            return
        
        # Initialize contract clients
        try:
            self.oracle = Oracle(
                self.web3,
                self.config["oracle_address"],
                self.private_key
            )
            
            self.agent = Agent(
                self.web3,
                self.config["agent_address"],
                self.private_key
            )
            
            self.registry = Registry(
                self.web3,
                self.config["registry_address"],
                self.private_key
            )
            
            self.usdc = MockERC20(
                self.web3,
                self.config["usdc_address"]
            )
            
            print("Successfully initialized contract clients")
            
        except Exception as e:
            print(f"Error initializing contract clients: {e}")
    
    def test_basic_connection(self):
        """Test basic connection to the blockchain and contracts"""
        print("\n=== Testing Basic Connection ===")
        
        # Check blockchain connection
        chain_id = self.web3.eth.chain_id
        balance = self.web3.eth.get_balance(self.account.address)
        print(f"Chain ID: {chain_id}")
        print(f"Account Balance: {self.web3.from_wei(balance, 'ether')} ETH")
        
        # Check contract addresses
        print("\nContract Addresses:")
        for name, addr_key in [
            ("USDC", "usdc_address"),
            ("Oracle", "oracle_address"),
            ("Registry", "registry_address"),
            ("Agent", "agent_address"),
            ("Prediction Market", "prediction_market_address")
        ]:
            if addr_key in self.config:
                addr = self.config[addr_key]
                code_size = len(self.web3.eth.get_code(self.web3.to_checksum_address(addr)))
                print(f"  {name}: {addr} (Code Size: {code_size} bytes)")
        
        return True
    
    def test_mock_usdc(self):
        """Test mock USDC functionality"""
        print("\n=== Testing Mock USDC ===")
        
        try:
            balance = self.usdc.get_balance(self.account.address)
            print(f"USDC Balance: {balance / 10**6} USDC")
            return True
        except Exception as e:
            print(f"Error testing USDC: {e}")
            return False
    
    def run_agent_tests(self):
        """Run agent-specific tests if agent modules are available"""
        if not AGENT_IMPORTS_SUCCESS:
            print("\nSkipping agent tests (modules not available)")
            return False
        
        print("\n=== Testing Agent Integration ===")
        
        try:
            # Just initialize the clients to test connectivity
            # We won't call actual methods since our contracts are empty
            print("Oracle client initialized:", self.oracle is not None)
            print("Agent client initialized:", self.agent is not None)
            print("Registry client initialized:", self.registry is not None)
            return True
        except Exception as e:
            print(f"Error testing agent integration: {e}")
            return False


def main():
    """Main function for the test script"""
    try:
        print("Testing connection to mock contracts...")
        tester = MockContractTester()
        
        # Run tests
        tester.test_basic_connection()
        tester.test_mock_usdc()
        tester.run_agent_tests()
        
        print("\nConnection tests completed!")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 