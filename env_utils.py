#!/usr/bin/env python3

"""
Environment variable parsing utilities with validation and bounds checking.

Provides safe parsing functions that handle invalid input gracefully and enforce
bounds checking to prevent hardware damage from extreme configuration values.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def safe_get_env_float(
    key: str,
    default: float,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> float:
    """
    Safely get float environment variable with bounds checking.
    
    Args:
        key: Environment variable name
        default: Default value if not set or invalid
        min_val: Minimum allowed value (inclusive), or None for no minimum
        max_val: Maximum allowed value (inclusive), or None for no maximum
        
    Returns:
        Parsed and validated float value
        
    Examples:
        >>> safe_get_env_float("TEMP_HIGH", 95.0, min_val=32.0, max_val=130.0)
        95.0
    """
    raw_value = os.environ.get(key)
    
    # If not set, use default
    if raw_value is None:
        logger.debug(f"{key} not set, using default: {default}")
        return default
    
    # Try to parse as float
    try:
        value = float(raw_value)
    except (ValueError, TypeError) as e:
        logger.error(
            f"Invalid value for {key}='{raw_value}': {e}. "
            f"Using default: {default}"
        )
        return default
    
    # Check minimum bound
    if min_val is not None and value < min_val:
        logger.warning(
            f"{key}={value} is below minimum {min_val}, "
            f"using minimum value"
        )
        return min_val
    
    # Check maximum bound
    if max_val is not None and value > max_val:
        logger.warning(
            f"{key}={value} exceeds maximum {max_val}, "
            f"using maximum value"
        )
        return max_val
    
    return value


def safe_get_env_int(
    key: str,
    default: int,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> int:
    """
    Safely get integer environment variable with bounds checking.
    
    Args:
        key: Environment variable name
        default: Default value if not set or invalid
        min_val: Minimum allowed value (inclusive), or None for no minimum
        max_val: Maximum allowed value (inclusive), or None for no maximum
        
    Returns:
        Parsed and validated integer value
        
    Examples:
        >>> safe_get_env_int("MISTER_DURATION", 600, min_val=60, max_val=7200)
        600
    """
    raw_value = os.environ.get(key)
    
    # If not set, use default
    if raw_value is None:
        logger.debug(f"{key} not set, using default: {default}")
        return default
    
    # Try to parse as int
    try:
        value = int(raw_value)
    except (ValueError, TypeError) as e:
        logger.error(
            f"Invalid value for {key}='{raw_value}': {e}. "
            f"Using default: {default}"
        )
        return default
    
    # Check minimum bound
    if min_val is not None and value < min_val:
        logger.warning(
            f"{key}={value} is below minimum {min_val}, "
            f"using minimum value"
        )
        return min_val
    
    # Check maximum bound
    if max_val is not None and value > max_val:
        logger.warning(
            f"{key}={value} exceeds maximum {max_val}, "
            f"using maximum value"
        )
        return max_val
    
    return value
