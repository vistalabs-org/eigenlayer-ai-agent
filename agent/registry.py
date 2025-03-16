from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from web3 import Web3

from .utils import load_abi

class AgentDetails(BaseModel):
    model_type: str
    model_version: str
    tasks_completed: int
    consensus_participations: int
    rewards_earned: int

class Registry:
    """Client for interacting with the AIAgentRegistry contract"""
    
    def __init__(self, web3: Web3, contract_address: str, private_key: Optional[str] = None):
        """
        Initialize the AIAgentRegistry client
        
        Args:
            web3: Web3 instance
            contract_address: Address of the AIAgentRegistry contract
            private_key: Private key for signing transactions (optional)
        """
        self.web3 = web3
        self.address = Web3.to_checksum_address(contract_address)
        self.private_key = private_key
        
        # Load contract ABI
        self.abi = load_abi('AIAgentRegistry.json')
        self.contract = self.web3.eth.contract(address=self.address, abi=self.abi)
        
        # Set up account if private key is provided
        self.account = None
        if private_key:
            self.account = self.web3.eth.account.from_key(private_key)
    
    def get_all_agents(self) -> List[str]:
        """Get all registered agent addresses"""
        return self.contract.functions.getAllAgents().call()
    
    def get_agent_count(self) -> int:
        """Get count of registered agents"""
        return self.contract.functions.getAgentCount().call()
    
    def is_agent_registered(self, agent_address: str) -> bool:
        """Check if an agent is registered"""
        return self.contract.functions.isRegistered(agent_address).call()
    
    def get_agent_details(self, agent_address: str) -> AgentDetails:
        """Get detailed information about an agent"""
        details = self.contract.functions.getAgentDetails(agent_address).call()
        
        return AgentDetails(
            model_type=details[0],
            model_version=details[1],
            tasks_completed=details[2],
            consensus_participations=details[3],
            rewards_earned=details[4]
        )
    
    def register_agent(self, agent_address: str) -> str:
        """
        Register an agent with the registry
        
        Args:
            agent_address: Address of the agent to register
            
        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("Private key not provided, cannot send transactions")
        
        # Check if already registered
        if self.is_agent_registered(agent_address):
            return "Agent already registered"
        
        # Create transaction
        tx = self.contract.functions.registerAgent(agent_address).build_transaction({
            'from': self.account.address,
            'nonce': self.web3.eth.get_transaction_count(self.account.address),
            'gas': 200000,
            'gasPrice': self.web3.eth.gas_price
        })
        
        # Sign and send
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        return tx_hash.hex()
