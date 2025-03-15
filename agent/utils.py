import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from web3 import Web3
from eth_account.messages import encode_defunct
import pkg_resources

logger = logging.getLogger(__name__)

def get_abi_path(filename: str) -> Path:
    """Get the path to the ABI file"""
    # Try to load from the package resources
    try:
        resource_path = pkg_resources.resource_filename("agent", f"abi/{filename}")
        if os.path.exists(resource_path):
            return Path(resource_path)
    except Exception:
        pass
    
    # Try to load from the current directory
    current_dir = Path(__file__).parent.absolute()
    abi_path = current_dir / 'abi' / filename
    
    if abi_path.exists():
        return abi_path
    
    # Try to load from the user's home directory
    home_path = Path.home() / '.eigenlayer' / 'abi' / filename
    
    if home_path.exists():
        return home_path
    
    # If we can't find the ABI, raise an error
    raise FileNotFoundError(f"Could not find ABI file: {filename}")

def load_abi(filename: str) -> Dict[str, Any]:
    """Load ABI from a JSON file"""
    abi_path = get_abi_path(filename)
    
    with open(abi_path, 'r') as f:
        abi_json = json.load(f)
    
    # Handle different ABI file formats
    if isinstance(abi_json, dict) and 'abi' in abi_json:
        return abi_json['abi']
    return abi_json

def sign_message(web3: Web3, message: str, private_key: str) -> bytes:
    """Sign a message using the given private key"""
    message_hash = encode_defunct(text=message)
    signed_message = web3.eth.account.sign_message(message_hash, private_key)
    return signed_message.signature

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from a JSON file"""
    if config_path is None:
        # Look for config in standard locations
        locations = [
            Path.cwd() / "eigenlayer_config.json",
            Path.home() / ".eigenlayer" / "config.json"
        ]
        
        for loc in locations:
            if loc.exists():
                config_path = loc
                break
        else:
            return {}  # Return empty config if no file found
    else:
        config_path = Path(config_path)
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load config from {config_path}: {e}")
        return {}

def setup_web3(provider_url: Optional[str] = None) -> Web3:
    """Setup Web3 connection"""
    if provider_url is None:
        # Try to get provider URL from environment variable
        provider_url = os.environ.get("WEB3_PROVIDER_URI")
        
        if provider_url is None:
            # Use a default provider if none is specified
            provider_url = "http://localhost:8545"
    
    if provider_url.startswith("http"):
        return Web3(Web3.HTTPProvider(provider_url))
    elif provider_url.startswith("ws"):
        return Web3(Web3.WebsocketProvider(provider_url))
    else:
        raise ValueError(f"Unsupported provider URL: {provider_url}")

def create_directory_structure():
    """Create the necessary directory structure"""
    # Create the ABI directory
    abi_dir = Path.home() / '.eigenlayer' / 'abi'
    abi_dir.mkdir(parents=True, exist_ok=True)
    
    # Create the config directory
    config_dir = Path.home() / '.eigenlayer'
    config_dir.mkdir(parents=True, exist_ok=True)