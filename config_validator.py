#!/usr/bin/env python3

"""
Configuration validation module for Server Shed Mister Controller.

Validates configuration values on startup to prevent invalid or dangerous
configurations from running. Provides both critical errors (prevent startup)
and warnings (allow but log).
"""

import logging
from typing import List
from dataclasses import dataclass
from enum import Enum

from mister_controller import MisterConfig

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Severity level of a validation issue"""
    CRITICAL = "critical"  # Prevents startup
    WARNING = "warning"    # Allows startup but logs warning
    INFO = "info"          # Just informational


@dataclass
class ValidationIssue:
    """Represents a configuration validation issue"""
    level: ValidationLevel
    message: str


class ConfigValidator:
    """Validates MisterConfig instances for safety and correctness"""
    
    # Temperature bounds (Fahrenheit)
    MIN_TEMP = 32.0  # Freezing point
    MAX_TEMP = 130.0  # Dangerously high
    
    # Humidity bounds (percentage)
    MIN_HUMIDITY = 0.0
    MAX_HUMIDITY = 100.0
    
    # Duration bounds (seconds)
    MIN_MISTER_DURATION = 60  # 1 minute minimum
    MAX_MISTER_DURATION = 7200  # 2 hours maximum
    MIN_CHECK_INTERVAL = 10  # 10 seconds minimum
    MAX_CHECK_INTERVAL = 3600  # 1 hour maximum (prevent excessive API calls)
    MIN_COOLDOWN = 60  # 1 minute minimum
    MAX_COOLDOWN = 86400  # 24 hours maximum
    
    # Device ID validation
    MIN_DEVICE_ID_LENGTH = 10  # Minimum length for device IDs (SwitchBot and Rachio)
    
    @staticmethod
    def validate_config(config: MisterConfig) -> List[ValidationIssue]:
        """
        Validate a MisterConfig instance.
        
        Args:
            config: The configuration to validate
            
        Returns:
            List of ValidationIssue objects (empty if valid)
        """
        issues = []
        
        # Temperature threshold validation
        issues.extend(ConfigValidator._validate_temperature_thresholds(config))
        
        # Humidity threshold validation
        issues.extend(ConfigValidator._validate_humidity_thresholds(config))
        
        # Duration validation
        issues.extend(ConfigValidator._validate_durations(config))
        
        # Dangerous combinations
        issues.extend(ConfigValidator._validate_combinations(config))
        
        return issues
    
    @staticmethod
    def _validate_temperature_thresholds(config: MisterConfig) -> List[ValidationIssue]:
        """Validate temperature threshold values"""
        issues = []
        
        # Check temperature_threshold_high bounds
        if config.temperature_threshold_high < ConfigValidator.MIN_TEMP:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"TEMP_HIGH={config.temperature_threshold_high}°F is below freezing ({ConfigValidator.MIN_TEMP}°F)"
            ))
        
        if config.temperature_threshold_high > ConfigValidator.MAX_TEMP:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"TEMP_HIGH={config.temperature_threshold_high}°F is dangerously high (max {ConfigValidator.MAX_TEMP}°F)"
            ))
        
        # Check temperature_threshold_low bounds
        if config.temperature_threshold_low < ConfigValidator.MIN_TEMP:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"TEMP_LOW={config.temperature_threshold_low}°F is below freezing ({ConfigValidator.MIN_TEMP}°F)"
            ))
        
        if config.temperature_threshold_low > ConfigValidator.MAX_TEMP:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"TEMP_LOW={config.temperature_threshold_low}°F is dangerously high (max {ConfigValidator.MAX_TEMP}°F)"
            ))
        
        # Check logical consistency
        # TEMP_HIGH triggers misting start (when temp > TEMP_HIGH), TEMP_LOW triggers misting stop (when temp < TEMP_LOW).
        # When TEMP_HIGH and TEMP_LOW differ, this creates hysteresis (misting only starts above TEMP_HIGH and stops below TEMP_LOW).
        # When equal, acts as a single threshold with no hysteresis (misting starts and stops at the same temperature).
        if config.temperature_threshold_low > config.temperature_threshold_high:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"TEMP_LOW={config.temperature_threshold_low}°F should be <= TEMP_HIGH={config.temperature_threshold_high}°F (start and stop thresholds)"
            ))
        
        # Warning for unusual values
        if config.temperature_threshold_high < 60:
            issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                f"TEMP_HIGH={config.temperature_threshold_high}°F is unusually low for misting threshold"
            ))
        
        if config.temperature_threshold_high > 110:
            issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                f"TEMP_HIGH={config.temperature_threshold_high}°F is very high - equipment may be at risk"
            ))
        
        return issues
    
    @staticmethod
    def _validate_humidity_thresholds(config: MisterConfig) -> List[ValidationIssue]:
        """Validate humidity threshold values"""
        issues = []
        
        # Check humidity_threshold_low bounds
        if not (ConfigValidator.MIN_HUMIDITY <= config.humidity_threshold_low <= ConfigValidator.MAX_HUMIDITY):
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"HUMIDITY_LOW={config.humidity_threshold_low}% must be between {ConfigValidator.MIN_HUMIDITY}-{ConfigValidator.MAX_HUMIDITY}%"
            ))
        
        # Check humidity_threshold_high bounds
        if not (ConfigValidator.MIN_HUMIDITY <= config.humidity_threshold_high <= ConfigValidator.MAX_HUMIDITY):
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"HUMIDITY_HIGH={config.humidity_threshold_high}% must be between {ConfigValidator.MIN_HUMIDITY}-{ConfigValidator.MAX_HUMIDITY}%"
            ))
        
        # Check logical consistency
        if config.humidity_threshold_low > config.humidity_threshold_high:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"HUMIDITY_LOW={config.humidity_threshold_low}% should be <= HUMIDITY_HIGH={config.humidity_threshold_high}%"
            ))
        
        # Warning for unusual values
        if config.humidity_threshold_low > 80:
            issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                f"HUMIDITY_LOW={config.humidity_threshold_low}% is very high - misting may rarely trigger"
            ))
        
        if config.humidity_threshold_high < 20:
            issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                f"HUMIDITY_HIGH={config.humidity_threshold_high}% is very low - misting may rarely stop on humidity"
            ))
        
        return issues
    
    @staticmethod
    def _validate_durations(config: MisterConfig) -> List[ValidationIssue]:
        """Validate duration and timing values"""
        issues = []
        
        # Mister duration validation
        if config.mister_duration_seconds <= 0:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"MISTER_DURATION={config.mister_duration_seconds}s must be positive"
            ))
        elif config.mister_duration_seconds < ConfigValidator.MIN_MISTER_DURATION:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"MISTER_DURATION={config.mister_duration_seconds}s is too short (minimum {ConfigValidator.MIN_MISTER_DURATION}s)"
            ))
        elif config.mister_duration_seconds > ConfigValidator.MAX_MISTER_DURATION:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"MISTER_DURATION={config.mister_duration_seconds}s is too long (maximum {ConfigValidator.MAX_MISTER_DURATION}s / {ConfigValidator.MAX_MISTER_DURATION // 3600} hours)"
            ))
        
        # Check interval validation
        if config.check_interval_seconds <= 0:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"CHECK_INTERVAL={config.check_interval_seconds}s must be positive"
            ))
        elif config.check_interval_seconds < ConfigValidator.MIN_CHECK_INTERVAL:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"CHECK_INTERVAL={config.check_interval_seconds}s is too short (minimum {ConfigValidator.MIN_CHECK_INTERVAL}s)"
            ))
        
        # Cooldown validation
        if config.cooldown_seconds <= 0:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"COOLDOWN_SECONDS={config.cooldown_seconds}s must be positive"
            ))
        elif config.cooldown_seconds < ConfigValidator.MIN_COOLDOWN:
            issues.append(ValidationIssue(
                ValidationLevel.CRITICAL,
                f"COOLDOWN_SECONDS={config.cooldown_seconds}s is too short (minimum {ConfigValidator.MIN_COOLDOWN}s)"
            ))
        
        return issues
    
    @staticmethod
    def _validate_combinations(config: MisterConfig) -> List[ValidationIssue]:
        """Validate dangerous or problematic configuration combinations"""
        issues = []
        
        # Check interval vs mister duration
        # If check interval >= duration, system won't check conditions while misting
        if config.check_interval_seconds >= config.mister_duration_seconds:
            issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                f"CHECK_INTERVAL={config.check_interval_seconds}s is greater than or equal to MISTER_DURATION={config.mister_duration_seconds}s. This prevents condition checks during misting, so the system cannot stop misting early if conditions change mid-cycle."
            ))
        
        # Cooldown vs mister duration
        if config.cooldown_seconds < config.mister_duration_seconds:
            issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                f"COOLDOWN_SECONDS={config.cooldown_seconds}s is less than MISTER_DURATION={config.mister_duration_seconds}s - this allows overlapping misting cycles"
            ))
        
        # Very long cooldown
        if config.cooldown_seconds > 3600:  # 1 hour
            issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                f"COOLDOWN_SECONDS={config.cooldown_seconds}s is very long ({config.cooldown_seconds // 60} minutes) - misting may be infrequent"
            ))
        
        # Very short duration with long cooldown (inefficient)
        if config.mister_duration_seconds < 300 and config.cooldown_seconds > 600:
            issues.append(ValidationIssue(
                ValidationLevel.INFO,
                f"Short MISTER_DURATION={config.mister_duration_seconds}s with long COOLDOWN_SECONDS={config.cooldown_seconds}s may be inefficient"
            ))
        
        return issues
    
    @staticmethod
    def has_critical_issues(issues: List[ValidationIssue]) -> bool:
        """Check if any issues are critical (prevent startup)"""
        return any(issue.level == ValidationLevel.CRITICAL for issue in issues)
    
    @staticmethod
    def log_validation_results(issues: List[ValidationIssue], config: MisterConfig) -> None:
        """Log validation results with appropriate levels"""
        if not issues:
            logger.info("✓ Configuration validation passed")
            ConfigValidator._log_config_summary(config)
            return
        
        # Group issues by level
        critical = [i for i in issues if i.level == ValidationLevel.CRITICAL]
        warnings = [i for i in issues if i.level == ValidationLevel.WARNING]
        info = [i for i in issues if i.level == ValidationLevel.INFO]
        
        if critical:
            logger.error("❌ Configuration validation FAILED with critical errors:")
            for issue in critical:
                logger.error(f"  CRITICAL: {issue.message}")
        
        if warnings:
            logger.warning("⚠️  Configuration validation warnings:")
            for issue in warnings:
                logger.warning(f"  WARNING: {issue.message}")
        
        if info:
            logger.info("ℹ️  Configuration notes:")
            for issue in info:
                logger.info(f"  INFO: {issue.message}")
        
        if not critical:
            logger.info("✓ Configuration accepted with warnings")
            ConfigValidator._log_config_summary(config)
    
    @staticmethod
    def _log_config_summary(config: MisterConfig) -> None:
        """Log a summary of the configuration"""
        logger.info("=" * 60)
        logger.info("CONFIGURATION SUMMARY:")
        logger.info(f"  Temperature thresholds: {config.temperature_threshold_low:.1f}°F - {config.temperature_threshold_high:.1f}°F")
        logger.info(f"  Humidity thresholds: {config.humidity_threshold_low:.0f}% - {config.humidity_threshold_high:.0f}%")
        logger.info(f"  Misting duration: {config.mister_duration_seconds}s ({config.mister_duration_seconds // 60}m)")
        logger.info(f"  Check interval: {config.check_interval_seconds}s")
        logger.info(f"  Cooldown period: {config.cooldown_seconds}s ({config.cooldown_seconds // 60}m)")
        logger.info("=" * 60)
