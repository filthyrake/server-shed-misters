#!/usr/bin/env python3
"""
Secure secrets loader for API credentials.

This module provides a secure way to load API credentials from:
1. Docker secrets (files in /run/secrets/) - preferred
2. Environment variables - fallback for development

Priority order: Docker secrets > Environment variables

This prevents credentials from being visible in docker inspect and process lists.
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default Docker secrets directory
SECRETS_DIR = Path("/run/secrets")


def load_secret(secret_name: str, env_var_name: Optional[str] = None) -> Optional[str]:
    """
    Load a secret from Docker secrets file or environment variable.
    
    Priority:
    1. Docker secrets file (/run/secrets/{secret_name})
    2. Environment variable (if env_var_name provided)
    
    Args:
        secret_name: Name of the secret file in /run/secrets/
        env_var_name: Name of environment variable to use as fallback
        
    Returns:
        Secret value as string, or None if not found
        
    Example:
        token = load_secret("switchbot_token", "SWITCHBOT_TOKEN")
    """
    # Try Docker secret first
    secret_file = SECRETS_DIR / secret_name
    if secret_file.exists():
        try:
            # Use explicit encoding and limit file size for security
            # Secrets should be small (< 1KB for API tokens)
            MAX_SECRET_SIZE = 1024  # 1KB should be more than enough for any API token
            file_size = secret_file.stat().st_size
            if file_size > MAX_SECRET_SIZE:
                # Don't log file name to avoid potential sensitive info leakage
                logger.warning(f"Secret file '{secret_name}' is too large ({file_size} bytes), skipping")  # nosec
                return None
            
            value = secret_file.read_text(encoding='utf-8').rstrip('\n\r')
            if value:
                # Log metadata only, never the actual secret value
                # secret_name is safe to log (e.g., "switchbot_token" not the actual token)
                logger.info(f"Loaded secret '{secret_name}' from Docker secrets")  # nosec - logging metadata, not secret value
                return value
        except Exception as e:
            # Don't expose file system details in logs
            logger.warning(f"Failed to read secret file '{secret_name}': {type(e).__name__}")  # nosec - logging error type, not secret
    
    # Fallback to environment variable
    if env_var_name:
        value = os.environ.get(env_var_name)
        if value:
            # Log metadata only, never the actual secret value
            logger.info(f"Loaded secret '{secret_name}' from environment variable {env_var_name}")  # nosec - logging metadata, not secret value
            return value
    
    return None


def load_required_secret(secret_name: str, env_var_name: Optional[str] = None) -> str:
    """
    Load a required secret, raising ValueError if not found.
    
    Args:
        secret_name: Name of the secret file in /run/secrets/
        env_var_name: Name of environment variable to use as fallback
        
    Returns:
        Secret value as string
        
    Raises:
        ValueError: If secret is not found in either location
    """
    value = load_secret(secret_name, env_var_name)
    if not value:
        raise ValueError(
            f"Required secret '{secret_name}' not found. "
            f"Expected in /run/secrets/{secret_name} or environment variable {env_var_name}"
        )
    return value


class APICredentials:
    """Container for API credentials loaded securely."""
    
    def __init__(self):
        """Load all API credentials from Docker secrets or environment variables."""
        self.switchbot_token = load_required_secret("switchbot_token", "SWITCHBOT_TOKEN")
        self.switchbot_secret = load_required_secret("switchbot_secret", "SWITCHBOT_SECRET")
        self.rachio_api_token = load_required_secret("rachio_api_token", "RACHIO_API_TOKEN")
        
        # Log successful initialization without details
        logger.info("API credentials initialized successfully")  # nosec - no sensitive data logged
    
    def __repr__(self):
        """Return safe representation without exposing credentials."""
        return (
            f"APICredentials(switchbot_token={'*' * 8}, "
            f"switchbot_secret={'*' * 8}, "
            f"rachio_api_token={'*' * 8})"
        )
