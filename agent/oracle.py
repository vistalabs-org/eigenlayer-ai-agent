from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from pydantic import BaseModel
from web3 import Web3

from .utils import load_abi


class TaskStatus(IntEnum):
    CREATED = 0
    IN_PROGRESS = 1
    RESOLVED = 2


class Task(BaseModel):
    name: str
    taskCreatedBlock: int


class Oracle:
    """Client for interacting with the AIOracleServiceManager contract"""

    def __init__(
        self, web3: Web3, contract_address: str, private_key: Optional[str] = None
    ):
        """
        Initialize the AIOracle client

        Args:
            web3: Web3 instance
            contract_address: Address of the AIOracleServiceManager contract
            private_key: Private key for signing transactions (optional)
        """
        self.web3 = web3
        self.address = Web3.to_checksum_address(contract_address)
        self.private_key = private_key

        # Load contract ABI
        self.abi = load_abi("AIOracleServiceManager.json")
        self.contract = self.web3.eth.contract(address=self.address, abi=self.abi)

        # Set up account if private key is provided
        self.account = None
        if private_key:
            self.account = self.web3.eth.account.from_key(private_key)

    def get_optimal_gas_price(self):
        """Get optimal gas price based on recent blocks"""
        # Get gas prices from last few blocks
        gas_prices = []
        latest_block = self.web3.eth.block_number

        # Sample gas prices from recent transactions
        for i in range(5):  # Only check last 5 blocks
            if latest_block - i >= 0:
                block = self.web3.eth.get_block(latest_block - i, True)
                for tx in block.transactions[:5]:  # Limit to 5 transactions per block
                    if hasattr(tx, "gasPrice"):
                        gas_prices.append(tx.gasPrice)

        if not gas_prices:
            # Add 20% to the network's suggested gas price if no historical data
            return int(self.web3.eth.gas_price * 1.2)

        # Use a higher percentile for more urgent transactions (60th instead of 30th)
        gas_prices.sort()
        index = int(len(gas_prices) * 0.6)  # 60th percentile
        return gas_prices[index]

    def create_task(self, name: str) -> Tuple[str, int]:
        """
        Create a new task in the oracle

        Args:
            name: Task name

        Returns:
            Tuple of (transaction hash, task index)
        """
        if not self.account:
            raise ValueError("Private key not provided, cannot send transactions")

        # Try to get current task number, but don't fail if this doesn't work
        current_task_num = 0
        try:
            current_task_num = self.contract.functions.latestTaskNum().call()
        except Exception as e:
            print(f"Warning: Could not get latest task number: {e}")
            print("Proceeding with task creation anyway...")

        # Create transaction
        try:
            # Try to get optimal gas price
            try:
                gas_price = self.get_optimal_gas_price()
            except Exception as e:
                logger.warning(f"Could not get optimal gas price: {e}")
                gas_price = self.web3.eth.gas_price

            nonce = self.web3.eth.get_transaction_count(self.account.address, "pending")

            # Try EIP-1559 transaction style
            try:
                # Get base fee from latest block
                latest_block = self.web3.eth.get_block("latest")
                base_fee = latest_block.baseFeePerGas
                max_priority_fee = self.web3.to_wei(1, "gwei")
                max_fee_per_gas = int(base_fee * 1.5) + max_priority_fee

                # Estimate gas with buffer
                estimated_gas = self.contract.functions.createNewTask(
                    name
                ).estimate_gas({"from": self.account.address})
                gas_limit = int(estimated_gas * 1.2)  # 20% buffer

                # Build EIP-1559 transaction
                tx = self.contract.functions.createNewTask(name).build_transaction(
                    {
                        "from": self.account.address,
                        "nonce": nonce,
                        "gas": gas_limit,
                        "maxFeePerGas": max_fee_per_gas,
                        "maxPriorityFeePerGas": max_priority_fee,
                        "type": 2,  # EIP-1559 transaction
                    }
                )
            except Exception as e:
                # Fallback to legacy transaction type
                logger.warning(
                    f"Could not create EIP-1559 transaction: {e},"
                    " falling back to legacy"
                )

                # Estimate gas with buffer
                try:
                    estimated_gas = self.contract.functions.createNewTask(
                        name
                    ).estimate_gas({"from": self.account.address})
                    gas_limit = int(estimated_gas * 1.5)  # Increase buffer to 50%
                except Exception as e_gas:
                    logger.warning(
                        f"Gas estimation failed: {e_gas}, using safe default"
                    )
                    gas_limit = 300000  # Increased from 300000 to be much safer

                # Build legacy transaction
                tx = self.contract.functions.createNewTask(name).build_transaction(
                    {
                        "from": self.account.address,
                        "nonce": nonce,
                        "gas": gas_limit,
                        "gasPrice": gas_price * 1.2,  # Add 20% to gas price
                    }
                )

            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Wait for transaction receipt to get task ID from logs
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            # Try to get task ID from logs
            try:
                logs = self.contract.events.NewTaskCreated().process_receipt(receipt)
                if logs:
                    # Update current_task_num if we got it from logs
                    current_task_num = logs[0]["args"]["taskIndex"]
            except Exception as e:
                print(f"Warning: Could not extract task ID from logs: {e}")

            return tx_hash.hex(), current_task_num
        except Exception as e:
            raise ValueError(f"Failed to create task: {e}")

    def get_task_status(self, task_index: int) -> TaskStatus:
        """Get the status of a task"""
        status_value = self.contract.functions.taskStatus(task_index).call()
        return TaskStatus(status_value)

    def get_task_respondents(self, task_index: int) -> List[str]:
        """Get the addresses of all respondents for a task"""
        return self.contract.functions.taskRespondents(task_index).call()

    def get_consensus_result(self, task_index: int) -> Tuple[bytes, bool]:
        """Get the consensus result for a task"""
        return self.contract.functions.getConsensusResult(task_index).call()

    def get_task_hash(self, task_index: int) -> bytes:
        """Get the hash of a task"""
        return self.contract.functions.allTaskHashes(task_index).call()

    def reconstruct_task(self, task_index: int) -> Optional[Dict[str, Any]]:
        """
        Reconstructs a task from blockchain data by calling the getTask function.

        Args:
            task_index: Index of the task to reconstruct

        Returns:
            Dictionary with task data ('name', 'taskCreatedBlock')
            or None if not found/error.
        """
        logger.debug(f"Attempting to reconstruct task {task_index} via getTask().")

        try:
            # Call the getTask function directly
            # The function returns a tuple: (name, taskCreatedBlock)
            task_data = self.contract.functions.getTask(task_index).call()

            # Check if data was returned
            if task_data and len(task_data) == 2 and task_data[1] > 0:
                task_name = task_data[0]
                task_created_block = task_data[1]
                logger.info(f"Reconstructed task {task_index} via getTask():")
                logger.info(f"  Name: '{task_name}'")
                logger.info(f"  Block: {task_created_block}")
                return {
                    "name": task_name,
                    "taskCreatedBlock": task_created_block,
                }
            else:
                # This case might happen if the task index is invalid
                # or getTask returns unexpected data
                logger.warning(
                    f"getTask({task_index}) returned unexpected data"
                    " or task doesn't exist."
                )
                logger.warning(f"  Data received: {task_data}")
                return None

        except Exception as e:
            # Catch potential errors like ContractLogicError (if task doesn't exist),
            # ABI mismatch, connection issues etc.
            logger.error(f"Error calling getTask({task_index}) on contract.")
            logger.error(f"  Error details: {e}")
            logger.error("Is the contract deployed with getTask and ABI updated?")
            import traceback

            traceback.print_exc()  # Log the full traceback for debugging
            return None  # Indicate failure
