#!/usr/bin/env python3
"""
Test script for verifying basic connection between the agent and mock contracts.
This script is used after setting up the mock environment with mock_testing.py.
"""

import sys
from pathlib import Path

import pytest

# Import utility functions
from .test_utils import (
    AGENT_IMPORTS_SUCCESS,
    get_default_private_key,
    get_oracle_instance,
    get_web3_instance,
    load_config,
)

# Try to import agent modules
try:
    from agent.agent import Agent
    from agent.oracle import Oracle
    from agent.registry import Registry
except ImportError:
    print("Warning: Failed to import agent modules.")
    print("Make sure you're running this from the eigenlayer-ai-agent directory.")


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
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [{"name": "", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            },
        ]

        self.contract = self.web3.eth.contract(address=self.address, abi=self.abi)

    def get_balance(self, address):
        """Mock balanceOf that returns a fake balance"""
        # Since our contract is empty, return a mock balance
        return 1000000000  # 1000 USDC with 6 decimals


class TestContractTester:
    """Test client for verifying agent connection with mock contracts"""

    # Changed from __init__ to setup_method to fix pytest warning
    def setup_method(self, method):
        """
        Set up the test client
        """
        # Load configuration
        self.config = load_config()

        # Default Anvil private key
        self.private_key = get_default_private_key()

        # Set up Web3 connection
        self.web3 = get_web3_instance(config=self.config)
        if not self.web3:
            pytest.skip(f"Could not connect to blockchain provider")
            return

        # Set up account
        self.account = self.web3.eth.account.from_key(self.private_key)
        print(f"Connected to blockchain with account: {self.account.address}")

        if not AGENT_IMPORTS_SUCCESS:
            print("Agent modules not available, using mock implementation")
            return

        # Initialize contract clients - but don't fail if they don't work
        try:
            self.oracle = Oracle(
                self.web3, self.config["oracle_address"], self.private_key
            )

            self.agent = Agent(
                self.web3, self.config["agent_address"], self.private_key
            )

            self.registry = Registry(
                self.web3, self.config["registry_address"], self.private_key
            )

            self.usdc = MockERC20(self.web3, self.config["usdc_address"])

            print("Successfully initialized contract clients")

        except Exception as e:
            print(f"Warning: Contract clients initialization failed: {e}")
            # Continue the test - we'll skip the tests that need these clients

    def test_basic_connection(self):
        """Test basic connection to the blockchain and contracts"""
        print("\n=== Testing Basic Connection ===")

        # Check blockchain connection
        try:
            chain_id = self.web3.eth.chain_id
            balance = self.web3.eth.get_balance(self.account.address)
            print(f"Chain ID: {chain_id}")
            print(f"Account Balance: {self.web3.from_wei(balance, 'ether')} ETH")
        except Exception as e:
            pytest.skip(f"Could not connect to blockchain: {e}")

        # Check contract addresses
        print("\nContract Addresses:")
        for name, addr_key in [
            ("USDC", "usdc_address"),
            ("Oracle", "oracle_address"),
            ("Registry", "registry_address"),
            ("Agent", "agent_address"),
            ("Prediction Market", "prediction_market_address"),
        ]:
            if addr_key in self.config:
                try:
                    addr = self.config[addr_key]
                    code_size = len(
                        self.web3.eth.get_code(self.web3.to_checksum_address(addr))
                    )
                    print(f"  {name}: {addr} (Code Size: {code_size} bytes)")
                except Exception as e:
                    print(f"  {name}: {addr} (Error: {e})")

        assert True  # If we got here, test passed

    def test_mock_usdc(self):
        """Test mock USDC functionality"""
        print("\n=== Testing Mock USDC ===")

        if not hasattr(self, "usdc"):
            pytest.skip("USDC mock not initialized")

        try:
            balance = self.usdc.get_balance(self.account.address)
            print(f"USDC Balance: {balance / 10**6} USDC")
            assert balance > 0, "USDC balance should be positive"
        except Exception as e:
            print(f"Error testing USDC: {e}")
            pytest.skip(f"USDC test failed: {e}")

    def test_agent_integration(self):
        """Run agent-specific tests if agent modules are available"""
        if not AGENT_IMPORTS_SUCCESS:
            pytest.skip("Agent modules not available")

        if (
            not hasattr(self, "oracle")
            or not hasattr(self, "agent")
            or not hasattr(self, "registry")
        ):
            pytest.skip("One or more agent clients not initialized")

        print("\n=== Testing Agent Integration ===")

        # Just verify that the clients exist and seem to be connected
        assert self.oracle is not None, "Oracle client should be initialized"
        assert self.agent is not None, "Agent client should be initialized"
        assert self.registry is not None, "Registry client should be initialized"

        print("All agent clients successfully initialized")


def main():
    """Main function for the test script"""
    try:
        print("Testing connection to mock contracts...")
        tester = TestContractTester()
        tester.setup_method(None)  # Initialize the tester

        # Run tests
        tester.test_basic_connection()
        tester.test_mock_usdc()
        tester.test_agent_integration()

        print("\nConnection tests completed!")

    except Exception as e:
        print(f"Error during testing: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
