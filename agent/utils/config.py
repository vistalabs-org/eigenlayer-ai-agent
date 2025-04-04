"""Configuration utilities for the EigenLayer AI agent."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from a JSON file or default location.
    Environment variables should be loaded separately where needed.

    Args:
        config_path: Path to the configuration file

    Returns:
        Dict containing configuration data
    """
    if config_path:
        config_path = Path(config_path)
    else:
        config_path = Path.cwd() / "config.json"

    logger.info(f"Loading configuration from {config_path}")

    if not config_path.exists():
        logger.warning(
            f"Configuration file {config_path} not found. "
            f"Returning empty config."
        )
        return {}

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        logger.debug(f"Configuration loaded successfully from {config_path}")
        return config
    except Exception as e:
        logger.exception(f"Error loading configuration from {config_path}: {e}")
        raise  # Re-raise exception after logging


def create_directory_structure():
    """Create necessary directories for the agent"""
    # Create data directory
    data_dir = Path.cwd() / "data"
    if not data_dir.exists():
        data_dir.mkdir()
        logger.info(f"Created data directory: {data_dir}")

    # Create subdirectories
    tasks_dir = data_dir / "tasks"
    if not tasks_dir.exists():
        tasks_dir.mkdir()
        logger.info(f"Created tasks directory: {tasks_dir}")

    responses_dir = data_dir / "responses"
    if not responses_dir.exists():
        responses_dir.mkdir()
        logger.info(f"Created responses directory: {responses_dir}")
