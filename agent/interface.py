"""Client for interacting with AIAgent contract"""

from typing import Optional

from loguru import logger
from web3 import Web3

from agent.utils.web3 import load_abi


class AgentInterface:
    """Client for interacting with the AIAgent contract"""

    def __init__(
        self, web3: Web3, contract_address: str, private_key: Optional[str] = None
    ):
        """
        Initialize the AIAgent client

        Args:
            web3: Web3 instance
            contract_address: Address of the AIAgent contract
            private_key: Private key for signing transactions (optional)
        """
        self.web3 = web3
        self.address = Web3.to_checksum_address(contract_address)
        self.private_key = private_key

        # Load contract ABI
        self.abi = load_abi("AIAgent.json")
        self.contract = self.web3.eth.contract(address=self.address, abi=self.abi)

        # Set up account if private key is provided
        self.account = None
        if private_key:
            self.account = self.web3.eth.account.from_key(private_key)

    def get_status(self):
        """Get the agent's status"""
        status_value = self.contract.functions.status().call()
        return status_value

    def process_task(self, task_index, signature):
        """
        Process a task and submit the agent's response

        Args:
            task_index: The task index
            signature: The signature representing the response

        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("Private key not provided, cannot send transactions")

        logger.info(f"Processing task {task_index} with signature {signature}")
        gas_price = self.web3.to_wei(1, "gwei")

        tx = self.contract.functions.processTask(
            task_index, signature
        ).build_transaction(
            {
                "from": self.account.address,
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
                "gas": 3000000,
                "gasPrice": gas_price,
            }
        )

        logger.info(f"Transaction: {tx}")

        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        return tx_hash.hex()
