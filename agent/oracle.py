from enum import IntEnum
from typing import Tuple, Dict, Any, List, Optional
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
    
    def __init__(self, web3: Web3, contract_address: str, private_key: Optional[str] = None):
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
        self.abi = load_abi('AIOracleServiceManager.json')
        self.contract = self.web3.eth.contract(address=self.address, abi=self.abi)
        
        # Set up account if private key is provided
        self.account = None
        if private_key:
            self.account = self.web3.eth.account.from_key(private_key)
    
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
        
        # Get current task number
        current_task_num = self.contract.functions.latestTaskNum().call()
        
        # Create transaction
        tx = self.contract.functions.createNewTask(name).build_transaction({
            'from': self.account.address,
            'nonce': self.web3.eth.get_transaction_count(self.account.address),
            'gas': 300000,  # Provide reasonable gas estimate
            'gasPrice': self.web3.eth.gas_price
        })
        
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        return tx_hash.hex(), current_task_num
    
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
    
    def reconstruct_task(self, task_index: int) -> Dict[str, Any]:
        """Attempt to reconstruct task data from events"""
        # Get task creation event
        event_filter = self.contract.events.NewTaskCreated.create_filter(
            fromBlock=0,
            argument_filters={'taskIndex': task_index}
        )
        events = event_filter.get_all_entries()
        
        if not events:
            raise ValueError(f"No task found with index {task_index}")
        
        # Extract task data from event
        task_data = events[0]['args']['task']
        
        return {
            'name': task_data[0],
            'taskCreatedBlock': task_data[1]
        }