"""Logging utilities for the EigenLayer AI agent."""

import sys
import time
from pathlib import Path

from loguru import logger


def setup_logging(log_level="INFO"):
    """
    Set up logging configuration to write logs to a dedicated folder

    Args:
        log_level: The logging level (default: "INFO")
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Create a timestamped log file name
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_file = logs_dir / f"agent_run_{timestamp}.log"

    # Convert string log level to integer if needed
    if isinstance(log_level, str):
        log_level = log_level.upper()

    # Remove default handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # Add file handler with rotation
    logger.add(
        log_file,
        rotation="10 MB",
        retention="1 week",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.info(f"Logging initialized. Log file: {log_file}")
    return log_file
