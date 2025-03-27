#!/usr/bin/env python3
"""
Prediction Market Bridge

This is the main entry point for the Prediction Market AI Agent system.
It connects the AI agent to the PredictionMarketHook contract.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from web3 import Web3
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
        oracle_address: Optional[str] = None,
        market_address: Optional[str] = None,
    ):
        """
        Initialize the bridge

        Args:
            config_path: Path to the configuration file
            oracle_address: Override Oracle address from config
            market_address: Address of PredictionMarketHook contract
        """
        # Load configuration
        self.config = load_config(config_path)

        # Set up Web3 connection
        provider_uri = self.config.get("rpc_url", "http://localhost:8545")
        self.web3 = setup_web3(provider_uri)

        # Get private key for transactions
        self.private_key = self.config.get("private_key", None)
        if not self.private_key:
            logger.warning(
                "No private key found in config. "
                "Only read operations will be available."
            )

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

        # Set up Oracle client
        oracle_addr = oracle_address or self.config.get("oracle_address")
        if not oracle_addr:
            raise ValueError("Oracle address not provided in config or command line")

        self.oracle = Oracle(self.web3, oracle_addr, self.private_key)
        logger.info(f"Connected to Oracle at {oracle_addr}")

        # Use registry address from config
        registry_addr = self.config.get("registry_address")
        if not registry_addr:
            logger.warning(
                "Registry address not provided in config. "
                "Some features will be limited."
            )

        # Use agent address or account address
        agent_addr = self.config.get("agent_address")
        if not agent_addr and self.account:
            agent_addr = self.account.address
            logger.info(f"Using account address as agent address: {agent_addr}")
        elif not agent_addr:
            raise ValueError(
                "Agent address not provided in config and no account available"
            )

        # Set up AI agent using OpenRouterBackend
        model = self.config.get("model", "google/gemma-3-27b-it:free")
        api_key = self.config.get("api_key", None)

        if not api_key:
            logger.warning(
                "No API key found in config. Using a mock response for testing."
            )
            self.llm = None
        else:
            self.llm = OpenRouterBackend(api_key=api_key, model=model)
            logger.info(f"Initialized LLM with model {model}")

        # Initialize AgentManager if registry address is provided
        if registry_addr:
            self.agent_manager = AgentManager(
                web3=self.web3,
                oracle_address=oracle_addr,
                registry_address=registry_addr,
                agent_address=agent_addr,
                private_key=self.private_key,
                ai_backend=self.llm,
            )
        else:
            self.agent_manager = None

        # Set up PredictionMarketHook if address provided
        self.market_hook = None
        if market_address:
            # Load ABI for PredictionMarketHook
            try:
                with open(
                    Path(__file__).parent.parent / "abis" / "PredictionMarketHook.json",
                    "r",
                ) as f:
                    hook_abi = json.load(f)
                self.market_hook = self.web3.eth.contract(
                    address=self.web3.to_checksum_address(market_address), abi=hook_abi
                )
                logger.info(f"Connected to PredictionMarketHook at {market_address}")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load PredictionMarketHook ABI: {e}")
                logger.warning("PredictionMarketHook integration will be limited")

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
            logger.info(f"Processing task {task_index}: {task}")

            # Check if task is related to prediction markets
            if not self.is_prediction_market_task(task):
                logger.info(
                    f"Task {task_index} is not related to prediction markets, skipping"
                )
                self.processed_tasks.add(task_index)
                return

            # Get AI response
            response = await self.get_ai_response_async(task)

            # Submit response to blockchain
            if self.private_key:
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

    def is_prediction_market_task(self, task: Dict[str, Any]) -> bool:
        """
        Check if a task is related to prediction markets

        Args:
            task: Task data

        Returns:
            True if the task is for a prediction market
        """
        # Process all tasks
        return True

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
                    if hasattr(tx, 'gasPrice'):
                        gas_prices.append(tx.gasPrice)
        
        if not gas_prices:
            return self.web3.eth.gas_price
        
        # Use a lower percentile for less urgent transactions
        gas_prices.sort()
        index = int(len(gas_prices) * 0.3)  # 30th percentile
        return gas_prices[index]

    async def submit_response_async(self, task_index: int, task: Dict[str, Any], response: str):
        """
        Async version of submit_response

        Args:
            task_index: Task index
            task: Task data
            response: Response string
        """
        # If manager is available, let it handle response submission
        if self.agent_manager:
            self.agent_manager.submit_response(task_index, task, response)
            return

        if not self.account:
            raise ValueError("Cannot submit response without a private key")

        # Create task struct to pass to respondToTask
        task_struct = {
            "name": task.get("name", ""),
            "taskCreatedBlock": task.get("taskCreatedBlock", 0),
        }

        # Sign the response with more efficient approach
        message = f"Task {task_index} response: {response[:10]}"  # Limit message size
        signature_hash = self.web3.keccak(text=message)
        
        try:
            # Use encode_defunct from eth_account.messages if available
            from eth_account.messages import encode_defunct
            signable_message = encode_defunct(hexstr=signature_hash.hex())
            signature = self.web3.eth.account.sign_message(
                signable_message, 
                private_key=self.private_key
            ).signature
        except ImportError:
            # Fallback for older web3.py versions
            signature = self.web3.eth.account.sign_message(
                Web3.to_bytes(hexstr=signature_hash.hex()), 
                private_key=self.private_key
            ).signature

        # Submit to blockchain
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
                latest_block = self.web3.eth.get_block('latest')
                base_fee = latest_block.baseFeePerGas
                max_priority_fee = self.web3.to_wei(1, 'gwei')
                max_fee_per_gas = int(base_fee * 1.5) + max_priority_fee
                
                # Estimate gas with buffer
                estimated_gas = self.oracle.contract.functions.respondToTask(
                    task_struct, task_index, signature
                ).estimate_gas({"from": self.account.address})
                gas_limit = int(estimated_gas * 1.2)  # 20% buffer
                
                # Build EIP-1559 transaction
                tx = self.oracle.contract.functions.respondToTask(
                    task_struct, task_index, signature
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "nonce": nonce,
                        "gas": gas_limit,
                        "maxFeePerGas": max_fee_per_gas,
                        "maxPriorityFeePerGas": max_priority_fee,
                        "type": 2  # EIP-1559 transaction
                    }
                )
            except Exception as e:
                # Fallback to legacy transaction type
                logger.warning(f"Could not create EIP-1559 transaction: {e}, falling back to legacy")
                
                # Estimate gas with buffer
                try:
                    estimated_gas = self.oracle.contract.functions.respondToTask(
                        task_struct, task_index, signature
                    ).estimate_gas({"from": self.account.address})
                    gas_limit = int(estimated_gas * 1.2)  # 20% buffer
                except Exception as e_gas:
                    logger.warning(f"Gas estimation failed: {e_gas}, using safe default")
                    gas_limit = 300000  # Reduced from 500000
                
                # Build legacy transaction
                tx = self.oracle.contract.functions.respondToTask(
                    task_struct, task_index, signature
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "nonce": nonce,
                        "gas": gas_limit,
                        "gasPrice": gas_price,
                    }
                )

            # Sign and send
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Wait for receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt["status"] == 1:
                logger.info(f"Response submitted successfully: {tx_hash.hex()}")
            else:
                logger.error(f"Response submission failed: {receipt}")

        except Exception as e:
            logger.error(f"Error submitting response: {e}")
            raise

    async def resolve_market_async(self, market_id: str, decision: bool):
        """
        Async version of resolve_market

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
                latest_block = self.web3.eth.get_block('latest')
                base_fee = latest_block.baseFeePerGas
                max_priority_fee = self.web3.to_wei(1, 'gwei')
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
                        "type": 2  # EIP-1559 transaction
                    }
                )
            except Exception as e:
                # Fallback to legacy transaction type
                logger.warning(f"Could not create EIP-1559 transaction: {e}, falling back to legacy")
                
                # Estimate gas with buffer
                try:
                    estimated_gas = self.market_hook.functions.resolveMarket(
                        market_id, decision
                    ).estimate_gas({"from": self.account.address})
                    gas_limit = int(estimated_gas * 1.2)  # 20% buffer
                except Exception as e_gas:
                    logger.warning(f"Gas estimation failed: {e_gas}, using safe default")
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
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
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

    parser.add_argument(
        "--oracle-address", type=str, help="Override Oracle address from config"
    )

    parser.add_argument(
        "--market-address", type=str, help="Address of PredictionMarketHook contract"
    )

    return parser.parse_args()


def main():
    # Set up logging first thing
    setup_logging("DEBUG")  # Use DEBUG level for maximum verbosity

    try:
        # Parse command line arguments
        args = parse_args()

        logger.info("Starting EigenLayer AI Agent")

        # Create the bridge using the parsed arguments
        bridge = PredictionMarketBridge(
            config_path=args.config,
            oracle_address=args.oracle_address,
            market_address=args.market_address,
        )

        # Run the main processing loop
        bridge.run(interval=args.interval, run_once=args.run_once)

    except Exception as e:
        logger.exception(f"Fatal error in main: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
