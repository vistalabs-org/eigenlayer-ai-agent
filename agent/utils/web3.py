"""Web3 utilities for the EigenLayer AI agent."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from eth_account.messages import encode_defunct
from web3 import Web3

logger = logging.getLogger(__name__)


def get_abi_path(filename: str) -> Path:
    """Get the path to an ABI file, searching in multiple locations"""
    # First check in the 'abis' directory in the current folder
    abi_path = Path.cwd() / "abis" / filename
    if abi_path.exists():
        return abi_path

    # Try the parent folder
    parent_abi_path = Path.cwd().parent / "abis" / filename
    if parent_abi_path.exists():
        return parent_abi_path

    # Try in a specific 'contracts/out' directory for Forge artifacts
    forge_artifacts = Path.cwd().parent / "contracts" / "out" / filename
    if forge_artifacts.exists():
        return forge_artifacts

    # If not found, check in common locations
    common_locations = [
        Path.cwd() / "abi",
        Path.cwd() / "artifacts",
        Path.cwd().parent / "abi",
        Path.cwd().parent / "artifacts",
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

        with open(abi_path, "r") as f:
            abi_json = json.load(f)

        # Handle different ABI file formats
        if isinstance(abi_json, dict):
            # Handle Forge artifacts which have an 'abi' field
            if "abi" in abi_json:
                logger.debug(f"Found 'abi' field in {filename}, using that")
                return abi_json["abi"]
            # Some other JSON format
            logger.warning(
                f"Warning: {filename} does not have an 'abi' field, using entire JSON"
            )
            return abi_json

        # Direct ABI array
        return abi_json
    except FileNotFoundError:
        logger.warning(f"ABI file {filename} not found in standard locations.")
        logger.info(
            "Checking in abis directory relative to current working directory..."
        )

        # Emergency fallback - directly check the abis directory
        direct_path = Path("abis") / filename
        if direct_path.exists():
            logger.info(f"Found ABI file directly in {direct_path}")
            with open(direct_path, "r") as f:
                abi_json = json.load(f)

            # Also check for 'abi' field in direct path
            if isinstance(abi_json, dict) and "abi" in abi_json:
                logger.info(f"Found 'abi' field in direct path {filename}, using that")
                return abi_json["abi"]
            return abi_json

        # Special case for AIOracleServiceManager - load the ABI directly
        if filename == "AIOracleServiceManager.json":
            logger.info("Using hardcoded minimal ABI for AIOracleServiceManager")
            minimal_abi = [
                {
                    "inputs": [],
                    "name": "latestTaskNum",
                    "outputs": [
                        {"internalType": "uint32", "name": "", "type": "uint32"}
                    ],
                    "stateMutability": "view",
                    "type": "function",
                },
                {
                    "inputs": [
                        {"internalType": "string", "name": "name", "type": "string"}
                    ],
                    "name": "createNewTask",
                    "outputs": [
                        {
                            "components": [
                                {
                                    "internalType": "string",
                                    "name": "name",
                                    "type": "string",
                                },
                                {
                                    "internalType": "uint32",
                                    "name": "taskCreatedBlock",
                                    "type": "uint32",
                                },
                            ],
                            "internalType": "struct IAIOracleServiceManager.Task",
                            "name": "",
                            "type": "tuple",
                        }
                    ],
                    "stateMutability": "nonpayable",
                    "type": "function",
                },
            ]
            return minimal_abi

        # Otherwise raise the original error
        raise


def sign_message(web3: Web3, message: str, private_key: str) -> bytes:
    """Sign a message using the given private key"""
    message_hash = encode_defunct(text=message)
    signed_message = web3.eth.account.sign_message(message_hash, private_key)
    return signed_message.signature


def setup_web3(provider_uri: str) -> Web3:
    """Set up Web3 connection with proxy support"""
    # Add proxy support
    request_kwargs = {"timeout": 30}

    if provider_uri == "http://localhost:8545":
        web3 = Web3(Web3.HTTPProvider(provider_uri, request_kwargs=request_kwargs))
    else:
        # Handle proxy settings
        http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

        if http_proxy or https_proxy:
            proxies = {}
            if https_proxy:
                proxies["https"] = https_proxy
            if http_proxy:
                proxies["http"] = http_proxy

            if proxies:
                logger.info(f"Using proxy settings: {proxies}")
                request_kwargs["proxies"] = proxies

        # Create Web3 instance with proxy configuration
        web3 = Web3(Web3.HTTPProvider(provider_uri, request_kwargs=request_kwargs))

    # Verify connection
    try:
        connected = web3.is_connected()
        if connected:
            logger.info(f"Successfully connected to {provider_uri}")
            logger.info(f"Chain ID: {web3.eth.chain_id}")
        else:
            logger.warning(f"Could not connect to {provider_uri}")
    except Exception as e:
        logger.error(f"Error connecting to provider: {e}")

    return web3


def load_contract(web3, address, abi_path_or_filename):
    """
    Load a contract with detailed logging

    Args:
        web3: Web3 instance
        address: Contract address
        abi_path_or_filename: Path to ABI file or just the filename

    Returns:
        Contract: Web3 contract instance
    """
    logger.info(f"Loading contract at address: {address}")
    try:
        # Check if abi_path_or_filename is a Path object or string path to a file
        if isinstance(abi_path_or_filename, (Path, str)) and (
            isinstance(abi_path_or_filename, Path)
            or "/" in abi_path_or_filename
            or "\\" in abi_path_or_filename
        ):
            # It's a path, load directly
            with open(abi_path_or_filename, "r") as f:
                abi_json = json.load(f)

            # Process the loaded ABI data
            if isinstance(abi_json, dict) and "abi" in abi_json:
                logger.debug(f"Found 'abi' field in {abi_path_or_filename}, using that")
                abi = abi_json["abi"]
            else:
                abi = abi_json
        else:
            # It's just a filename, use load_abi
            logger.debug(f"Loading ABI from filename: {abi_path_or_filename}")
            abi = load_abi(abi_path_or_filename)

        # Create contract instance
        contract = web3.eth.contract(address=web3.to_checksum_address(address), abi=abi)

        # Verify contract exists on-chain
        try:
            code = web3.eth.get_code(address)
            if code.hex() == "0x":
                logger.warning(f"No code at {address}! Contract might not be deployed.")
            else:
                logger.debug(f"Contract code verified at {address}")
        except Exception as e:
            logger.warning(f"Could not verify contract code: {e}")

        logger.info(f"Contract loaded successfully at {address}")
        return contract

    except Exception as e:
        logger.exception(f"Failed to load contract at {address}: {e}")
        raise
