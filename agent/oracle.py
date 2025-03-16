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
        
        # Try to get current task number, but don't fail if this doesn't work
        current_task_num = 0
        try:
            current_task_num = self.contract.functions.latestTaskNum().call()
        except Exception as e:
            print(f"Warning: Could not get latest task number: {e}")
            print("Proceeding with task creation anyway...")
        
        # Create transaction
        try:
            tx = self.contract.functions.createNewTask(name).build_transaction({
                'from': self.account.address,
                'nonce': self.web3.eth.get_transaction_count(self.account.address),
                'gas': 500000,  # Increased gas limit for safety
                'gasPrice': self.web3.eth.gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            # Wait for transaction receipt to get task ID from logs
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Try to get task ID from logs
            try:
                logs = self.contract.events.NewTaskCreated().process_receipt(receipt)
                if logs:
                    # Update current_task_num if we got it from logs
                    current_task_num = logs[0]['args']['taskIndex']
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
    
    def reconstruct_task(self, task_index: int) -> Dict[str, Any]:
        """Attempt to reconstruct task data from events"""
        try:
            # Get task creation event using get_logs directly
            # This is a more compatible approach than using create_filter
            event_signature_hash = self.web3.keccak(text="NewTaskCreated(uint32,(string,uint32))").hex()
            logs = self.web3.eth.get_logs({
                'address': self.address,
                'fromBlock': 0,
                'toBlock': 'latest',
                'topics': [event_signature_hash]
            })
            
            # Filter for the specific task index
            for log in logs:
                # Decode the log data
                try:
                    decoded_log = self.contract.events.NewTaskCreated().process_log(log)
                    if decoded_log['args']['taskIndex'] == task_index:
                        task_data = decoded_log['args']['task']
                        return {
                            'name': task_data[0],
                            'taskCreatedBlock': task_data[1]
                        }
                except Exception as e:
                    print(f"Error decoding log: {e}")
                    continue
            
            raise ValueError(f"No task found with index {task_index}")
        except Exception as e:
            # Fallback: try to get task data directly if possible
            print(f"Error reconstructing task from events: {e}")
            
            # Simpler structure for debugging
            return {
                'name': f"Task {task_index}",
                'taskCreatedBlock': 0
            }
