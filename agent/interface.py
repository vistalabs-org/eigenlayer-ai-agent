"""Client for interacting with AIAgent contract"""

from typing import Optional

from loguru import logger
from web3 import Web3

from .utils import load_abi


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
            private_key_hex = self.private_key
            if private_key_hex.startswith("0x"):
                private_key_hex = private_key_hex[2:]
            self.account = self.web3.eth.account.from_key(private_key_hex)
            logger.info(f"Using account: {self.account.address}")
        else:
            logger.warning(
                "No private key provided. Only read ops available."
            )

    def get_status(self):
        """Get the status of the agent from the contract"""
        return self.contract.functions.status().call()

    def process_task(self, task_index: int, decision: bool):
        """
        Process a task and submit the agent's response

        Args:
            task_index: The task index
            decision: The boolean decision (True for YES, False for NO)

        Returns:
            Transaction hash string
        """
        if not self.account:
            raise ValueError(
                "Private key not provided, cannot send transactions"
            )

        logger.info(f"Processing task {task_index} with decision {decision}")
        gas_price = self.web3.to_wei(1, "gwei")

        tx_build = self.contract.functions.processTask(
            task_index, decision
        ).build_transaction(
            {
                "from": self.account.address,
                "nonce": self.web3.eth.get_transaction_count(
                    self.account.address
                 ),
                "gas": 5000000,  # Increased gas limit
                "gasPrice": gas_price,
            }
        )

        logger.info(f"Transaction details: {tx_build}")

        signed_tx = self.web3.eth.account.sign_transaction(
            tx_build, self.private_key
        )
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        return tx_hash.hex()
