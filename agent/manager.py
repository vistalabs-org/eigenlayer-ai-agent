import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Callable
from web3 import Web3
from enum import IntEnum

from .agent import Agent, AgentStatus
from .oracle import Oracle, TaskStatus 
from .registry import Registry
from .llm import OpenRouterBackend

logger = logging.getLogger(__name__)

class AgentManager:
    """High-level manager for coordinating AI agents with the oracle system"""
    
    def __init__(self, 
                 web3: Web3, 
                 oracle_address: str, 
                 registry_address: str, 
                 agent_address: str, 
                 private_key: str,
                 ai_backend: OpenRouterBackend):
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
        self.agent = Agent(web3, agent_address, private_key)
        self.ai_backend = ai_backend
        
        # Check if agent is registered
        try:
            self.is_registered = self.registry.is_agent_registered(agent_address)
        except Exception as e:
            logger.warning(f"Could not check agent registration: {e}")
            self.is_registered = False
    
    async def setup(self):
        """Setup the agent - register if needed, ensure active status"""
        if not self.is_registered:
            logger.info(f"Registering agent {self.agent.address}")
            try:
                tx_hash = self.registry.register_agent(self.agent.address)
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt.status == 1:
                    logger.info(f"Agent registration successful")
                    self.is_registered = True
                else:
                    logger.error(f"Agent registration failed")
            except Exception as e:
                logger.error(f"Error registering agent: {e}")
        
        # Check and update agent status if needed
        status = self.agent.get_status()
        if status != AgentStatus.ACTIVE:
            logger.info(f"Activating agent (current status: {status.name})")
            try:
                tx_hash = self.agent.set_status(AgentStatus.ACTIVE)
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt.status == 1:
                    logger.info(f"Agent activated successfully")
                else:
                    logger.error(f"Failed to activate agent")
            except Exception as e:
                logger.error(f"Error activating agent: {e}")
    
    async def monitor_tasks(self, polling_interval: int = 10):
        """
        Monitor for new tasks and process them
        
        Args:
            polling_interval: Seconds between polling for new tasks
        """
        logger.info(f"Starting task monitoring for agent {self.agent.address}")
        
        # Ensure agent is set up
        await self.setup()
        
        # Last processed task
        last_processed_task = -1
        
        while True:
            try:
                # Get latest task number
                latest_task = self.oracle.contract.functions.latestTaskNum().call()
                
                # Process any unprocessed tasks
                for task_index in range(last_processed_task + 1, latest_task):
                    await self.process_task(task_index)
                
                # Update last processed task
                last_processed_task = latest_task - 1
                
            except Exception as e:
                logger.error(f"Error monitoring tasks: {e}")
            
            # Wait before next poll
            await asyncio.sleep(polling_interval)
    
    async def process_task(self, task_index: int):
        """
        Process a specific task
        
        Args:
            task_index: Index of the task to process
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
                return
            
            # Get task responders
            respondents = self.oracle.get_task_respondents(task_index)
            agent_address = self.agent.account.address.lower()
            
            # Check if we already responded
            if agent_address in [r.lower() for r in respondents]:
                logger.info(f"Already responded to task {task_index}, skipping")
                return
            
            # Generate AI response
            query = task['name']
            logger.info(f"Generating response for task: {query}")
            
            response = self.ai_backend.generate_response(query)
            
            # Process the task via the agent contract
            tx_hash = self.agent.process_task(task, task_index, response)
            logger.info(f"Submitted response for task {task_index}, tx: {tx_hash}")
            
            # Wait for transaction confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt.status == 1:
                logger.info(f"Response for task {task_index} confirmed")
            else:
                logger.error(f"Response for task {task_index} failed")
                
        except Exception as e:
            logger.error(f"Error processing task {task_index}: {e}")