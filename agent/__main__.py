#!/usr/bin/env python3
"""
Prediction Market Bridge

This is the main entry point for the Prediction Market AI Agent system.
It connects the AI agent to the PredictionMarketHook contract.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from loguru import logger
from web3.exceptions import ContractLogicError

from agent.llm import OpenRouterBackend
from agent.manager import AgentManager
from agent.oracle import Oracle, TaskStatus
from agent.utils.config import load_config
from agent.utils.logger import setup_logging
from agent.utils.web3 import setup_web3


class PredictionMarketBridge:
    """Bridge between AI agent and prediction market contracts"""

    def __init__(
        self,
        config_path: str,
    ):
        """
        Initialize the bridge

        Args:
            config_path: Path to the configuration file
        """
        # Load NON-SENSITIVE configuration from JSON
        self.config = load_config(config_path)

        # Set up Web3 connection
        provider_uri = self.config.get("rpc_url", "http://localhost:8545")
        self.web3 = setup_web3(provider_uri)

        # Load SENSITIVE keys from environment variables
        self.agent_private_key = os.getenv("AGENT_PRIVATE_KEY")
        self.api_key = os.getenv("API_KEY")

        if not self.agent_private_key:
            logger.warning(
                "PRIVATE_KEY environment variable not set. "
                "Only read operations will be available."
            )

        # Set up account
        if self.agent_private_key:

            private_key_hex = self.agent_private_key
            if self.agent_private_key.startswith("0x"):
                private_key_hex = private_key_hex[2:]
            self.account = self.web3.eth.account.from_key(private_key_hex)
            logger.info(f"Using account: {self.account.address}")
        else:
            self.account = None

        # Set up Oracle client - Load from config
        oracle_addr = self.config.get("oracle_address")
        if not oracle_addr:
            raise ValueError(
                "Oracle address ('oracle_address') not found in config file, "
                "and ORACLE_ADDRESS env var not set."
            )

        self.oracle = Oracle(self.web3, oracle_addr, self.agent_private_key)
        logger.info(f"Connected to Oracle at {oracle_addr}")

        # Use registry address from config
        registry_addr = self.config.get("registry_address")
        if not registry_addr:
            logger.warning(
                "Registry address ('registry_address') not provided in config. "
                "Some features will be limited."
            )

        # Agent address: Prefer config, then derive from AGENT_PRIVATE_KEY
        agent_addr = self.config.get("agent_address")
        if not agent_addr:
            if self.agent_private_key:
                key = self.agent_private_key.replace("0x", "")
                agent_account = self.web3.eth.account.from_key(key)
                agent_addr = agent_account.address
                logger.info(
                    f"Using address derived from AGENT_PRIVATE_KEY: {agent_addr}"
                )
            else:
                error_msg = (
                    "Agent address ('agent_address') not in config, "
                    "and cannot derive from env vars "
                )
                raise ValueError(error_msg)

        # Set up AI agent using OpenRouterBackend
        model = self.config.get("model", "google/gemma-3-27b-it:free")

        if not self.api_key:
            logger.warning(
                "API_KEY environment variable not set. "
                "Using a mock response for testing."
            )
            self.llm = None
        else:
            self.llm = OpenRouterBackend(api_key=self.api_key, model=model)
            logger.info(f"Initialized LLM with model {model}")

        # Initialize AgentManager if registry address is provided
        if registry_addr:
            self.agent_manager = AgentManager(
                web3=self.web3,
                oracle_address=oracle_addr,
                registry_address=registry_addr,
                agent_address=agent_addr,
                private_key=self.agent_private_key,
                ai_backend=self.llm,
            )
        else:
            self.agent_manager = None

        # Set up PredictionMarketHook - Load address from config
        self.market_hook = None
        effective_market_address = self.config.get("prediction_market_address")

        if effective_market_address:
            # Load ABI for PredictionMarketHook
            try:
                with open(
                    Path(__file__).parent.parent / "abis" / "PredictionMarketHook.json",
                    "r",
                ) as f:
                    hook_abi = json.load(f)
                self.market_hook = self.web3.eth.contract(
                    address=self.web3.to_checksum_address(
                        effective_market_address
                    ),  # Use effective address
                    abi=hook_abi,
                )
                logger.info(
                    f"Connected to PredictionMarketHook at {effective_market_address}"
                )
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load PredictionMarketHook ABI: {e}")
                logger.warning("PredictionMarketHook integration will be limited")
            except Exception as e:  # Catch potential address errors
                logger.warning(
                    "Error connecting to PredictionMarketHook at "
                    f"{effective_market_address}: {e}"
                )
        else:
            logger.warning(
                "PredictionMarketHook address ('prediction_market_address') "
                "not found in config file. Market state checking will be disabled."
            )

        # Cache for processed tasks
        self.processed_tasks = set()

    async def run_async(self, interval: int = 30, run_once: bool = False):
        """
        Async version of the main processing loop

        Args:
            interval: Time between checks in seconds
            run_once: Run only once instead of continuous polling
        """
        logger.info(f"Starting bridge with polling interval of {interval} seconds")

        # Setup phase - register agent if needed
        if self.agent_manager:
            await self.agent_manager.setup()

        while True:
            try:
                # Check for new tasks
                await self.process_pending_tasks_async()

                # Exit if only running once
                if run_once:
                    break

                # Wait before next check
                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                logger.info("\nExiting on user request")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                import traceback

                traceback.print_exc()
                if run_once:
                    break
                await asyncio.sleep(interval)

    def run(self, interval: int = 30, run_once: bool = False):
        """
        Main processing loop

        Args:
            interval: Time between checks in seconds
            run_once: Run only once instead of continuous polling
        """
        try:
            asyncio.run(self.run_async(interval, run_once))
        except KeyboardInterrupt:
            logger.info("\nExiting on user request")

    async def process_pending_tasks_async(self):
        """Async version of process_pending_tasks"""
        try:
            # Get latest task number
            latest_task_num = self.oracle.contract.functions.latestTaskNum().call()
            logger.info(f"Latest task number: {latest_task_num}")

            # Process all unprocessed tasks
            for task_index in range(latest_task_num):
                if task_index in self.processed_tasks:
                    continue

                # Check task status
                try:
                    task_status = self.oracle.get_task_status(task_index)
                    logger.info(f"Task {task_index} status: {task_status}")

                    # Skip if task is already resolved
                    if task_status == TaskStatus.RESOLVED:
                        self.processed_tasks.add(task_index)
                        continue

                    # Process task
                    await self.process_task_async(task_index)

                except ContractLogicError as e:
                    logger.error(f"Error getting task {task_index}: {e}")
                except Exception as e:
                    logger.error(f"Error processing task {task_index}: {e}")
                    import traceback

                    traceback.print_exc()

        except Exception as e:
            logger.error(f"Error checking pending tasks: {e}")
            import traceback

            traceback.print_exc()

    async def process_task_async(self, task_index: int):
        """
        Async version of process_task

        Args:
            task_index: Index of the task to process
        """
        try:
            # Get task data
            task = self.oracle.reconstruct_task(task_index)
            # Task reconstruction might return None or raise error if task not found
            if not task:
                logger.warning(f"Could not reconstruct task {task_index}. Skipping.")
                self.processed_tasks.add(task_index)  # Mark as processed
                return

            logger.info(
                f"Checking if task {task_index} should be processed: "
                f"{task.get('name')}"
            )

            # Check if task meets processing criteria (e.g., market state)
            if not self.should_process_task(task_index, task):
                # Reason for skipping is logged within should_process_task
                self.processed_tasks.add(task_index)
                return

            # Get AI response
            response = await self.get_ai_response_async(task)

            # Submit response to blockchain
            if self.agent_private_key:
                await self.submit_response_async(task_index, task, response)
                logger.info(f"Submitted response for task {task_index}")
            else:
                logger.info(f"Would submit response for task {task_index}: {response}")
                logger.info("(Not submitting because no private key provided)")

            # Mark as processed
            self.processed_tasks.add(task_index)

        except Exception as e:
            logger.error(f"Error processing task {task_index}: {e}")
            import traceback

            traceback.print_exc()

    def should_process_task(self, task_index: int, task: Dict[str, Any]) -> bool:
        """
        Check if a task should be processed.
        Currently, it only processes tasks associated with markets
        in the InResolution state (state 3).

        Args:
            task_index: The numerical index of the task.
            task: Task data dictionary (expecting 'name' field).

        Returns:
            True if the task should be processed, False otherwise.
        """
        # 1. Check if we have the market hook contract available
        if not self.market_hook:
            logger.warning(
                "Market hook contract not available. Cannot check market state. "
                "Skipping task."
            )
            return False

        # 2. Get the Market ID directly from the Oracle Manager contract
        market_id_bytes = b"\x00" * 32
        try:
            # Call Oracle contract to get the linked Market ID for this task
            market_id_bytes = self.oracle.contract.functions.getMarketIdForTask(
                task_index
            ).call()
            if market_id_bytes == b"\x00" * 32:
                # Task is not linked to a market ID (or oracle call failed implicitly)
                logger.warning(
                    f"Task {task_index} is not linked to a market ID in the Oracle."
                )
                return False
            # Convert bytes32 to hex string for logging
            market_id_hex = "0x" + market_id_bytes.hex()
            logger.debug(f"Retrieved Market ID {market_id_hex} for Task {task_index}.")
        except Exception as e:
            logger.error(
                f"Failed to get Market ID for task {task_index} from oracle"
                f" contract: {e}. Skipping."
            )
            return False

        # 3. Get Market State from the contract using the correct market_id
        try:
            # Assuming the MarketState enum corresponds to uint8/int:
            # Created=0, Active=1, Closed=2, InResolution=3, Resolved=4,
            # Cancelled=5, Disputed=6
            IN_RESOLUTION_STATE = 3

            logger.debug(f"Querying state for market ID: {market_id_hex}")
            # Call getMarketById using the bytes32 market ID from the oracle
            market_data = self.market_hook.functions.getMarketById(
                market_id_bytes
            ).call()
            # Index 6 corresponds to the 'state' field
            # in the Market struct based on ABI
            current_state = market_data[6]

            logger.info(
                f"Market {market_id_hex} state is: {current_state}. "
                f"Required state for processing: {IN_RESOLUTION_STATE}"
            )

            # 4. Compare state
            if current_state == IN_RESOLUTION_STATE:
                logger.info(
                    f"Market {market_id_hex} is InResolution. "
                    "Task should be processed."
                )
                return True
            else:
                logger.info(
                    f"Market {market_id_hex} is not InResolution. " "Skipping task."
                )
                return False

        except ContractLogicError as e:
            logger.error(
                f"Contract logic error checking state for market {market_id_hex}: {e}."
                " Skipping task."
            )
            return False
        except Exception as e:
            # Catch other potential errors like ABI mismatch, connection issues etc.
            logger.error(
                f"Failed to get state for market {market_id_hex}: {e}. "
                "Skipping task."
            )
            import traceback

            traceback.print_exc()
            return False

    async def get_ai_response_async(self, task: Dict[str, Any]) -> str:
        """
        Async version of get_ai_response

        Args:
            task: Task data

        Returns:
            Response from AI agent
        """
        # Use manager if available, otherwise use direct implementation
        if self.agent_manager:
            return self.agent_manager.get_ai_response(task)

        # --- Direct Implementation (Fallback/Alternative) ---
        # This part should ideally not be used if AgentManager is correctly set up
        logger.warning("Using direct LLM call, AgentManager might not be configured.")

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
        if self.llm:
            response = self.llm.generate_response(prompt)
            logger.info(f"AI response: {response}")
        else:
            # Mock response for testing when no API key is available
            logger.info("Using mock response (no API key provided)")
            response = "YES, based on current market trends and analyst projections."

        # Extract YES/NO from response
        if response.startswith("YES"):
            decision = "YES"
        elif response.startswith("NO"):
            decision = "NO"
        else:
            # Default to NO if unclear
            logger.info(f"Could not extract clear YES/NO from response: {response}")
            decision = "NO"

        return decision
        # --- End Direct Implementation ---

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
            return self.web3.eth.gas_price

        # Use a lower percentile for less urgent transactions
        gas_prices.sort()
        index = int(len(gas_prices) * 0.3)  # 30th percentile
        return gas_prices[index]

    async def submit_response_async(
        self, task_index: int, task: Dict[str, Any], response: str
    ):
        """
        Async version of submit_response.
        Ensures response is submitted via AgentManager if available.

        Args:
            task_index: Task index
            task: Task data
            response: Response string ("YES" or "NO")
        """
        # If manager is available, let it handle response submission
        if self.agent_manager:
            self.agent_manager.submit_response(task_index, task, response)
            return
        else:
            # This case should not happen if registry_address is in config
            logger.error(
                "AgentManager not initialized. Cannot submit response via "
                "AIAgent contract. Configure 'registry_address' in config.json."
            )
            # Optionally, raise an error or just log and return
            # raise ValueError("AgentManager not available for response submission")
            return

        # --- Removed Direct Submission Logic ---
        # The following logic directly called the Oracle and bypassed the AIAgent,
        # which is incorrect for the intended flow.

        # if not self.account:
        #     raise ValueError("Cannot submit response without a private key")
        #
        # # Create task struct to pass to respondToTask
        # task_struct = {
        #     "name": task.get("name", ""),
        #     "taskCreatedBlock": task.get("taskCreatedBlock", 0),
        # }
        #
        # # Sign the response - THIS IS NOT THE SIGNATURE THE CONTRACT EXPECTS
        # # The contract expects the signature to *be* the response data
        # # for the AgentManager flow. Direct signing here is misleading.
        # message = f"Task {task_index} response: {response[:10]}" # Limit message size
        # signature_hash = self.web3.keccak(text=message)
        #
        # try:
        #     # Use encode_defunct from eth_account.messages if available
        #     from eth_account.messages import encode_defunct
        #     signable_message = encode_defunct(hexstr=signature_hash.hex())
        #     signature = self.web3.eth.account.sign_message(
        #         signable_message, private_key=self.agent_private_key
        #     ).signature
        # except ImportError:
        #     # Fallback for older web3.py versions
        #     signature = self.web3.eth.account.sign_message(
        #         Web3.to_bytes(hexstr=signature_hash.hex()),
        #         private_key=self.agent_private_key,
        #     ).signature
        #
        # # Submit to blockchain DIRECTLY TO ORACLE - INCORRECT PATH
        # try:
        #     nonce = self.web3.eth.get_transaction_count(self.account.address)
        #     # ... [Rest of direct transaction building logic removed] ...
        #
        # except Exception as e:
        #     logger.error(f"Error submitting response directly: {e}") # Log context
        #     raise
        # --- End Removed Direct Submission Logic ---

    async def resolve_market_async(self, market_id: str, decision: bool):
        """
        Async version of resolve_market (kept for potential direct use/testing)

        Args:
            market_id: ID of the market to resolve
            decision: True for YES, False for NO
        """
        if not self.market_hook:
            logger.warning(
                "Cannot resolve market: PredictionMarketHook not initialized"
            )
            return

        if not self.account:
            logger.warning("Cannot resolve market without a private key")
            return

        try:
            nonce = self.web3.eth.get_transaction_count(self.account.address)

            # Try to get optimal gas price
            try:
                gas_price = self.get_optimal_gas_price()
            except Exception as e:
                logger.warning(f"Could not get optimal gas price: {e}")
                gas_price = self.web3.eth.gas_price

            # Try EIP-1559 transaction style
            try:
                # Get base fee from latest block
                latest_block = self.web3.eth.get_block("latest")
                base_fee = latest_block.baseFeePerGas
                max_priority_fee = self.web3.to_wei(1, "gwei")
                max_fee_per_gas = int(base_fee * 1.5) + max_priority_fee

                # Estimate gas with buffer
                estimated_gas = self.market_hook.functions.resolveMarket(
                    market_id, decision
                ).estimate_gas({"from": self.account.address})
                gas_limit = int(estimated_gas * 1.2)  # 20% buffer

                # Build EIP-1559 transaction
                tx = self.market_hook.functions.resolveMarket(
                    market_id, decision
                ).build_transaction(
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
                    estimated_gas = self.market_hook.functions.resolveMarket(
                        market_id, decision
                    ).estimate_gas({"from": self.account.address})
                    gas_limit = int(estimated_gas * 1.2)  # 20% buffer
                except Exception as e_gas:
                    logger.warning(
                        f"Gas estimation failed: {e_gas}, using safe default"
                    )
                    gas_limit = 200000  # Reduced from 300000

                # Build legacy transaction
                tx = self.market_hook.functions.resolveMarket(
                    market_id, decision
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "nonce": nonce,
                        "gas": gas_limit,
                        "gasPrice": gas_price,
                    }
                )

            # Sign and send
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, self.agent_private_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Wait for receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt["status"] == 1:
                logger.info(f"Market resolved successfully: {tx_hash.hex()}")
            else:
                logger.error(f"Market resolution failed: {receipt}")

        except Exception as e:
            logger.error(f"Error resolving market: {e}")
            import traceback

            traceback.print_exc()

    def resolve_market(self, market_id: str, decision: bool):
        """
        Resolve a prediction market based on AI decision

        Args:
            market_id: ID of the market to resolve
            decision: True for YES, False for NO
        """
        try:
            asyncio.run(self.resolve_market_async(market_id, decision))
        except Exception as e:
            logger.error(f"Error resolving market: {e}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="AI Prediction Market Bridge")

    parser.add_argument(
        "--config", type=str, help="Path to configuration file", default="config.json"
    )

    parser.add_argument(
        "--interval", type=int, help="Polling interval in seconds", default=30
    )

    parser.add_argument(
        "--run-once", action="store_true", help="Run the script once and exit"
    )

    return parser.parse_args()


def main():
    # Load .env file first
    load_dotenv()

    # Set up logging first thing
    setup_logging("DEBUG")  # Use DEBUG level for maximum verbosity

    try:
        # Parse command line arguments (only --config, --interval, --run-once remain)
        args = parse_args()

        logger.info("Starting EigenLayer AI Agent")

        # Create the bridge using only the config path
        # The constructor now handles loading addresses from the config
        bridge = PredictionMarketBridge(config_path=args.config)

        # Run the main processing loop
        bridge.run(interval=args.interval, run_once=args.run_once)

    except Exception as e:
        logger.exception(f"Fatal error in main: {str(e)}")
        sys.exit(1)


def handle_worker_request(request_data):
    """
    Handler function for processing requests from the Cloudflare Worker.
    This function acts as the bridge between the Worker and the Python agent.
    It simulates what would happen if you ran 'python agent --config config.yml'.
    
    Args:
        request_data: Dictionary containing request information:
            url: Full URL of the request
            method: HTTP method (GET, POST, etc.)
            path: URL path
            headers: Request headers
            body: Request body (parsed if JSON)
            env: Environment variables from Cloudflare
    
    Returns:
        Dictionary with:
            status: HTTP status code
            headers: Response headers
            body: Response body
    """
    try:
        from loguru import logger
        
        # Log request info
        method = request_data['method']
        path = request_data['path']
        logger.info(f"Received request: {method} {path}")
        
        # Load configuration (similar to --config flag)
        from agent.utils.config import load_config
        config = load_config('/config.json')  # Path will be set by the worker.js
        
        # Basic routing
        if path == "/" or path == "/status":
            # Return simple status response
            return {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "status": "running",
                    "version": "0.1.0",
                    "message": "EigenLayer AI Agent is running",
                    "config": {
                        # Only show non-sensitive config info
                        "rpc_url": config.get("rpc_url"),
                        "oracle_address": config.get("oracle_address"),
                        "registry_address": config.get("registry_address"),
                        "has_agent_address": bool(config.get("agent_address")),
                    }
                }
            }
        elif path == "/run-once" and method == "POST":
            # Simulate running the agent once
            try:
                # In a real environment, we would create and run the bridge
                # PredictionMarketBridge(config_path='/config.json').run(run_once=True)
                
                # Just simulate the response for now
                return {
                    "status": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "result": "Agent run-once simulated",
                        "message": "In a real environment, this would process pending tasks",
                        "config_loaded": bool(config)
                    }
                }
            except Exception as e:
                logger.error(f"Error simulating agent run: {e}")
                return {
                    "status": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "error": f"Error simulating agent run: {str(e)}"
                    }
                }
                
        elif path == "/task" and method == "POST":
            # Process a task request
            if not request_data.get('body'):
                return {
                    "status": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": "Request body is required"}
                }
            
            # Extract task data
            body = request_data['body']
            task_data = body.get('task')
            
            if not task_data:
                return {
                    "status": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": "Task data is required"}
                }
            
            # Process the task using the agent's logic
            # This is a simplified version - in a real implementation, 
            # you would use the actual agent logic
            return {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "result": "Task processed successfully",
                    "decision": "YES",
                    "confidence": 0.85,
                    "task": task_data,
                    "note": "This is a simulated response."
                }
            }
        else:
            # Unknown endpoint
            return {
                "status": 404,
                "headers": {"Content-Type": "application/json"},
                "body": {"error": f"Unknown endpoint: {path}"}
            }
            
    except Exception as e:
        # Log the error and return a 500 response
        import traceback
        error_details = traceback.format_exc()
        
        return {
            "status": 500,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "error": str(e),
                "details": error_details
            }
        }


if __name__ == "__main__":
    main()
