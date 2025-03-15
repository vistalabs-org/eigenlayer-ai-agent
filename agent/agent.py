from enum import IntEnum
from typing import Dict, Any, Optional
from pydantic import BaseModel
from web3 import Web3

from .utils import load_abi, sign_message

class AgentStatus(IntEnum):
    INACTIVE = 0
    ACTIVE = 1
    SUSPENDED = 2
    
class AgentStats(BaseModel):
    tasks_completed: int
    consensus_participations: int
    total_rewards: int
    status: AgentStatus
    
class ModelInfo(BaseModel):
    model_type: str
    model_version: str

class Agent:
    """Client for interacting with the AIAgent smart contract"""
    
    def __init__(self, web3: Web3, contract_address: str, private_key: Optional[str] = None):
        """
        Initialize the AI Agent client
        
        Args:
            web3: Web3 instance
            contract_address: Address of the AIAgent contract
            private_key: Private key for signing transactions (optional)
        """
        self.web3 = web3
        self.address = Web3.to_checksum_address(contract_address)
        self.private_key = private_key
        
        # Load contract ABI
        self.abi = load_abi('AIAgent.json')
        self.contract = self.web3.eth.contract(address=self.address, abi=self.abi)
        
        # Set up account if private key is provided
        self.account = None
        if private_key:
            self.account = self.web3.eth.account.from_key(private_key)
            
        # Get service manager address
        self.service_manager = self.contract.functions.serviceManager().call()
    
    def get_model_info(self) -> ModelInfo:
        """Get agent model type and version"""
        model_type = self.contract.functions.modelType().call()
        model_version = self.contract.functions.modelVersion().call()
        return ModelInfo(model_type=model_type, model_version=model_version)
    
    def get_status(self) -> AgentStatus:
        """Get agent status"""
        status_value = self.contract.functions.status().call()
        return AgentStatus(status_value)
    
    def get_stats(self) -> AgentStats:
        """Get agent statistics"""
        stats = self.contract.functions.getAgentStats().call()
        return AgentStats(
            tasks_completed=stats[0],
            consensus_participations=stats[1],
            total_rewards=stats[2],
            status=AgentStatus(stats[3])
        )
    
    def set_status(self, status: AgentStatus) -> str:
        """Set agent status and return transaction hash"""
        if not self.account:
            raise ValueError("Private key not provided, cannot send transactions")
        
        tx = self.contract.functions.setStatus(status).build_transaction({
            'from': self.account.address,
            'nonce': self.web3.eth.get_transaction_count(self.account.address)
        })
        
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()
    
    def update_model_info(self, model_type: str, model_version: str) -> str:
        """Update agent model information and return transaction hash"""
        if not self.account:
            raise ValueError("Private key not provided, cannot send transactions")
        
        tx = self.contract.functions.updateModelInfo(model_type, model_version).build_transaction({
            'from': self.account.address,
            'nonce': self.web3.eth.get_transaction_count(self.account.address)
        })
        
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()
    
    def process_task(self, task: Dict[str, Any], task_index: int, llm_response: str) -> str:
        """Process a task and submit agent's response"""
        if not self.account:
            raise ValueError("Private key not provided, cannot send transactions")
        
        # Get the message to sign
        message = f"Hello, {task['name']}"
        
        # Sign the message with our private key
        signature = sign_message(self.web3, message, self.private_key)
        
        # Prepare task for contract call
        task_tuple = (task['name'], task['taskCreatedBlock'])
        
        # Send transaction
        tx = self.contract.functions.processTask(
            task_tuple, 
            task_index,
            signature
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.web3.eth.get_transaction_count(self.account.address)
        })
        
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()