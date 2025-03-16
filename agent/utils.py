import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from web3 import Web3
from eth_account.messages import encode_defunct
# Removing pkg_resources import as it's deprecated
# Use importlib.metadata instead if needed

logger = logging.getLogger(__name__)

def get_abi_path(filename: str) -> Path:
    """Get the path to an ABI file, searching in multiple locations"""
    # First check in the 'abis' directory in the current folder
    abi_path = Path.cwd() / 'abis' / filename
    if abi_path.exists():
        return abi_path
        
    # Try the parent folder
    parent_abi_path = Path.cwd().parent / 'abis' / filename
    if parent_abi_path.exists():
        return parent_abi_path
        
    # Try in a specific 'contracts/out' directory for Forge artifacts
    forge_artifacts = Path.cwd().parent / 'contracts' / 'out' / filename
    if forge_artifacts.exists():
        return forge_artifacts
        
    # If not found, check in common locations
    common_locations = [
        Path.cwd() / 'abi',
        Path.cwd() / 'artifacts',
        Path.cwd().parent / 'abi',
        Path.cwd().parent / 'artifacts',
    ]
    
    for location in common_locations:
        potential_abi = location / filename
        if potential_abi.exists():
            return potential_abi
    
    # If we still haven't found it, raise an error
    raise FileNotFoundError(f"Could not find ABI file: {filename}")

def load_abi(filename: str) -> Any:
    """Load ABI from a JSON file"""
    try:
        abi_path = get_abi_path(filename)
        
        with open(abi_path, 'r') as f:
            abi_json = json.load(f)
        
        # Handle different ABI file formats
        if isinstance(abi_json, dict) and 'abi' in abi_json:
            return abi_json['abi']
        return abi_json
    except FileNotFoundError:
        print(f"Warning: ABI file {filename} not found in standard locations.")
        print("Checking in abis directory relative to current working directory...")
        
        # Emergency fallback - directly check the abis directory
        direct_path = Path('abis') / filename
        if direct_path.exists():
            print(f"Found ABI file directly in {direct_path}")
            with open(direct_path, 'r') as f:
                abi_json = json.load(f)
            return abi_json
        
        # Special case for AIOracleServiceManager - load the ABI directly
        if filename == 'AIOracleServiceManager.json':
            print("Using hardcoded minimal ABI for AIOracleServiceManager")
            minimal_abi = [
                {
                    "inputs": [],
                    "name": "latestTaskNum",
                    "outputs": [{"internalType": "uint32", "name": "", "type": "uint32"}],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [{"internalType": "string", "name": "name", "type": "string"}],
                    "name": "createNewTask", 
                    "outputs": [{"components":[{"internalType":"string","name":"name","type":"string"},{"internalType":"uint32","name":"taskCreatedBlock","type":"uint32"}],"internalType":"struct IAIOracleServiceManager.Task","name":"","type":"tuple"}],
                    "stateMutability": "nonpayable",
                    "type": "function"
                }
            ]
            return minimal_abi
        
        # Otherwise raise the original error
        raise

def sign_message(web3: Web3, message: str, private_key: str) -> bytes:
    """Sign a message using the given private key"""
    message_hash = encode_defunct(text=message)
    signed_message = web3.eth.account.sign_message(message_hash, private_key)
    return signed_message.signature

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from a file or default location"""
    if config_path:
        config_path = Path(config_path)
    else:
        config_path = Path.cwd() / "eigenlayer_config.json"
    
    if not config_path.exists():
        return {}
    
    with open(config_path, 'r') as f:
        return json.load(f)

def setup_web3(provider_uri: str) -> Web3:
    """Set up Web3 connection with proxy support"""
    # Add proxy support
    request_kwargs = {'timeout': 30}
    
    if provider_uri == "http://localhost:8545":
        web3 = Web3(Web3.HTTPProvider(provider_uri, request_kwargs=request_kwargs))
    else:
        
        # Handle proxy settings
        http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        
        if http_proxy or https_proxy:
            proxies = {}
            if https_proxy:
                proxies['https'] = https_proxy
            if http_proxy:
                proxies['http'] = http_proxy
            
            if proxies:
                print(f"Using proxy settings: {proxies}")
                request_kwargs['proxies'] = proxies
        
        # Create Web3 instance with proxy configuration
        web3 = Web3(Web3.HTTPProvider(provider_uri, request_kwargs=request_kwargs))
    
    # Verify connection
    try:
        connected = web3.is_connected()
        if connected:
            print(f"Successfully connected to {provider_uri}")
            print(f"Chain ID: {web3.eth.chain_id}")
        else:
            print(f"Warning: Could not connect to {provider_uri}")
    except Exception as e:
        print(f"Error connecting to provider: {e}")
    
    return web3

def create_directory_structure():
    """Create necessary directories for the agent"""
    # Create data directory
    data_dir = Path.cwd() / "data"
    if not data_dir.exists():
        data_dir.mkdir()
    
    # Create subdirectories
    tasks_dir = data_dir / "tasks"
    if not tasks_dir.exists():
        tasks_dir.mkdir()
    
    responses_dir = data_dir / "responses"
    if not responses_dir.exists():
        responses_dir.mkdir()
