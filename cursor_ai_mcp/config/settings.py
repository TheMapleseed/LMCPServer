# config/settings.py
"""
Configuration Management

This module provides configuration management for the Cursor AI
coordination service.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, field, asdict
import uuid

# Set up module logger
logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """
    Configuration settings for the coordination service.
    
    This class provides a type-safe way to manage configuration settings
    for the service, with support for loading from environment variables
    and configuration files.
    """
    
    # Instance identification
    instance_id: Optional[str] = None
    
    # Project configuration
    project_root: str = "."
    
    # CAICR configuration
    lldb_database_path: str = "./.caicr/history.db"
    coordination_port: int = 15001
    sync_interval_ms: int = 1000
    max_history_entries: int = 1000
    encryption_enabled: bool = True
    
    # Cursor AI MCP configuration
    cursor_ai_host: str = "127.0.0.1"
    cursor_ai_port: int = 15000
    
    # Logging configuration
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Metrics configuration
    metrics_enabled: bool = True
    metrics_file: Optional[str] = None
    
    # Additional configuration
    additional_config: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_env(cls) -> 'Settings':
        """
        Create settings from environment variables.
        
        Environment variables are prefixed with CAICR_ and upper-cased.
        For example, instance_id becomes CAICR_INSTANCE_ID.
        """
        settings = cls()
        
        # Get settings from environment variables
        for field_name in settings.__annotations__:
            env_name = f"CAICR_{field_name.upper()}"
            env_value = os.environ.get(env_name)
            
            if env_value is not None:
                field_type = settings.__annotations__[field_name]
                
                try:
                    # Convert to the appropriate type
                    if field_type == str or field_type == Optional[str]:
                        setattr(settings, field_name, env_value)
                    elif field_type == int:
                        setattr(settings, field_name, int(env_value))
                    elif field_type == bool:
                        setattr(settings, field_name, env_value.lower() in ("true", "yes", "1"))
                    elif field_type == Dict[str, Any]:
                        setattr(settings, field_name, json.loads(env_value))
                except Exception as e:
                    logger.warning(f"Failed to convert environment variable {env_name}: {str(e)}")
        
        return settings
    
    @classmethod
    def from_file(cls, file_path: str) -> 'Settings':
        """
        Create settings from a JSON configuration file.
        
        Args:
            file_path: Path to the configuration file
        
        Returns:
            Settings: Configuration settings
        
        Raises:
            ValueError: If the file doesn't exist or contains invalid JSON
        """
        if not os.path.exists(file_path):
            raise ValueError(f"Configuration file doesn't exist: {file_path}")
        
        try:
            with open(file_path, "r") as f:
                config = json.load(f)
            
            settings = cls()
            
            # Apply configuration values
            for key, value in config.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
                else:
                    settings.additional_config[key] = value
            
            return settings
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {str(e)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to a dictionary."""
        return asdict(self)
    
    def to_file(self, file_path: str) -> None:
        """
        Save settings to a JSON configuration file.
        
        Args:
            file_path: Path to the configuration file
        """
        try:
            with open(file_path, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save configuration to {file_path}: {str(e)}")
    
    def update(self, **kwargs) -> None:
        """
        Update settings with new values.
        
        Args:
            **kwargs: New settings values
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.additional_config[key] = value


def load_settings(
    config_file: Optional[str] = None,
    env_override: bool = True
) -> Settings:
    """
    Load settings from a configuration file and/or environment variables.
    
    Args:
        config_file: Path to the configuration file (optional)
        env_override: Whether environment variables should override
                     configuration file values
    
    Returns:
        Settings: Configuration settings
    """
    if config_file and os.path.exists(config_file):
        try:
            settings = Settings.from_file(config_file)
        except ValueError as e:
            logger.warning(f"Failed to load configuration file: {str(e)}")
            settings = Settings()
    else:
        settings = Settings()
    
    if env_override:
        env_settings = Settings.from_env()
        
        # Update settings with environment values (if set)
        for field_name in settings.__annotations__:
            env_value = getattr(env_settings, field_name)
            
            # Only override if the environment variable was actually set
            if field_name == "additional_config":
                # Merge additional config
                settings.additional_config.update(env_settings.additional_config)
            elif env_value is not None and (
                not isinstance(env_value, (str, bytes)) or len(env_value) > 0
            ):
                setattr(settings, field_name, env_value)
    
    # Ensure we have an instance ID
    if not settings.instance_id:
        settings.instance_id = str(uuid.uuid4())
    
    return settings 