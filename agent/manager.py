import asyncio
from enum import IntEnum
from typing import Any, Dict

from eth_account.messages import encode_defunct
from loguru import logger
from web3 import Web3

from .interface import AgentInterface
from .llm import OpenRouterBackend
from .oracle import Oracle, TaskStatus
from .registry import Registry


# Define agent status enum (moved from agent.py)
class AgentStatus(IntEnum):
    INACTIVE = 0
    ACTIVE = 1
    SUSPENDED = 2


class AgentManager:
    """High-level manager for coordinating AI agents with the oracle system"""

    def __init__(
        self,
        web3: Web3,
        oracle_address: str,
        registry_address: str,
        agent_address: str,
        private_key: str,
        ai_backend: OpenRouterBackend,
    ):
        """
        Initialize the AI Agent Manager

        Args:
            web3: Web3 instance
            oracle_address: AIOracleServiceManager contract address
            registry_address: AIAgentRegistry contract address
            agent_address: AIAgent contract address
            private_key: Private key for transactions
            ai_backend: OpenRouterBackend instance for generating responses
        """
        self.web3 = web3
        self.oracle = Oracle(web3, oracle_address, private_key)
        self.registry = Registry(web3, registry_address, private_key)
        self.agent_address = Web3.to_checksum_address(agent_address)
        self.private_key = private_key
        self.ai_backend = ai_backend

        # Set up account
        if self.private_key:
            # Remove '0x' prefix if present for web3.py
            private_key_hex = self.private_key
            if private_key_hex.startswith("0x"):
                private_key_hex = private_key_hex[2:]
            self.account = self.web3.eth.account.from_key(private_key_hex)
            logger.info(f"Using account: {self.account.address}")
        else:
            self.account = None
            logger.warning(
                "No private key provided. Only read operations will be available."
            )

        # Check if agent is registered
        try:
            self.is_registered = self.registry.is_agent_registered(agent_address)
        except Exception as e:
            logger.warning(f"Could not check agent registration: {e}")
            self.is_registered = False

        # Add this for the AIAgent client
        self.agent = AgentInterface(web3, agent_address, private_key)

    async def setup(self):
        # TODO: Add a check to see if the agent is already registered
        """Setup the agent - register if needed"""
        if not self.is_registered:
            logger.info(f"Checking agent registration: {self.agent_address}")
            try:
                if hasattr(self.registry, "register_agent"):
                    tx_hash = self.registry.register_agent(self.agent_address)
                    receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
                    if receipt.status == 1:
                        logger.info("Agent registration successful")
                        self.is_registered = True
                    else:
                        logger.error("Agent registration failed")
                else:
                    logger.warning("Registry does not support agent registration")
            except Exception as e:
                logger.error(f"Error registering agent: {e}")

    async def monitor_tasks(self, polling_interval: int = 10):
        """
        Monitor for new tasks and process them

        Args:
            polling_interval: Seconds between polling for new tasks
        """
        logger.info(f"Starting task monitoring for agent {self.agent_address}")

        # Ensure agent is set up
        await self.setup()

        # Cache for processed tasks
        processed_tasks = set()

        while True:
            try:
                # Get latest task number
                latest_task = self.oracle.contract.functions.latestTaskNum().call()
                logger.info(f"Latest task number: {latest_task}")

                # Process all unprocessed tasks
                for task_index in range(latest_task):
                    if task_index in processed_tasks:
                        continue

                    # Check task status
                    try:
                        task_status = self.oracle.get_task_status(task_index)
                        logger.info(f"Task {task_index} status: {task_status}")

                        # Skip if task is already resolved
                        if task_status == TaskStatus.RESOLVED:
                            processed_tasks.add(task_index)
                            continue

                        # Process task
                        await self.process_task(task_index, processed_tasks)

                    except Exception as e:
                        logger.error(f"Error checking task {task_index}: {e}")

                # Wait before next poll
                await asyncio.sleep(polling_interval)

            except KeyboardInterrupt:
                logger.info("\nExiting on user request")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(polling_interval)

    async def process_task(self, task_index: int, processed_tasks: set):
        """
        Process a specific task

        Args:
            task_index: Index of the task to process
            processed_tasks: Set of already processed task indices
        """
        logger.info(f"Processing task {task_index}")

        try:
            # Get task data
            task = self.oracle.reconstruct_task(task_index)

            # Get task status
            status = self.oracle.get_task_status(task_index)

            # Only process if not resolved
            if status == TaskStatus.RESOLVED:
                logger.info(f"Task {task_index} already resolved, skipping")
                processed_tasks.add(task_index)
                return

            # Get task responders
            respondents = self.oracle.get_task_respondents(task_index)
            agent_address = self.account.address.lower()

            # Check if we already responded
            if agent_address in [r.lower() for r in respondents]:
                logger.info(f"Already responded to task {task_index}, skipping")
                processed_tasks.add(task_index)
                return

            # Generate AI response
            query = task.get("name", "")
            logger.info(f"Generating response for task: {query}")

            # Get AI response
            response = self.get_ai_response(task)

            # Submit response to blockchain
            if self.private_key:
                self.submit_response(task_index, task, response)
                logger.info(f"Submitted response for task {task_index}")
            else:
                logger.info(f"Would submit response for task {task_index}: {response}")
                logger.info("(Not submitting because no private key provided)")

            # Mark as processed
            processed_tasks.add(task_index)

        except Exception as e:
            logger.error(f"Error processing task {task_index}: {e}")

    def get_ai_response(self, task: Dict[str, Any]) -> str:
        """
        Use AI agent to generate a response

        Args:
            task: Task data

        Returns:
            Response string (YES or NO)
        """
        task_content = task.get("name", "")

        prompt = f"""
        You are evaluating a prediction market question.
        Your task is to respond with either YES or NO,
        followed by a brief explanation of your reasoning.

        Question: {task_content}

        Response format: Start with YES or NO (capitalized),
        followed by your explanation.
        """

        # Call AI agent if available or return mock response for testing
        if self.ai_backend:
            full_response = self.ai_backend.generate_response(prompt)
            logger.info(f"AI response: {full_response}")
        else:
            # Mock response for testing when no API key is available
            logger.info("Using mock response (no API key provided)")
            full_response = (
                "YES, based on current market trends and analyst projections."
            )

        # Extract YES/NO from response - improved parsing
        response_upper = full_response.strip().upper()

        if response_upper.startswith("NO"):
            return "NO"
        elif response_upper.startswith("YES"):
            return "YES"
        else:
            # Default to NO if unclear, but log the issue
            logger.warning(
                "Could not clearly extract YES/NO from response,"
                " defaulting to NO. Response: {full_response[:100]}..."
            )
            return "NO"

    def submit_response(self, task_index: int, task: Dict[str, Any], response: str):
        """
        Submit response via AIAgent contract

        Args:
            task_index: Task index
            task: Task data
            response: Response string
        """
        if not self.account:
            raise ValueError("Cannot submit response without a private key")

        # Sign the response with minimal data
        message = f"Task{task_index}"  # Very short message - same as in contract

        logger.info(f"Signing message: {message}")
        signature_hash = self.web3.keccak(text=message)

        signable_message = encode_defunct(hexstr=signature_hash.hex())
        signature_object = self.web3.eth.account.sign_message(
            signable_message, private_key=self.private_key
        )

        # Extract signature bytes
        signature_bytes = signature_object.signature

        # Submit to blockchain via the AIAgent contract
        try:
            # Pass only task_index and signature to the optimized function
            tx_hash = self.agent.process_task(task_index, signature_bytes)

            # Wait for receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt["status"] == 1:
                logger.info(f"Response submitted successfully via AIAgent: {tx_hash}")
            else:
                logger.error(f"Response submission via AIAgent failed: {receipt}")
        except Exception as e:
            logger.error(f"Error submitting response via AIAgent: {e}")
            raise
