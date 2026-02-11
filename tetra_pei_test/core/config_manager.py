"""
Configuration Manager

Handles loading and validation of configuration files for radio connections and tests.
"""

import json
import yaml
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path


logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configuration for TETRA PEI testing framework.
    
    Supports both JSON and YAML configuration files.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file (JSON or YAML)
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        
        if config_path:
            self.load_config(config_path)
    
    def load_config(self, config_path: str) -> bool:
        """
        Load configuration from file.
        
        Args:
            config_path: Path to configuration file
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            path = Path(config_path)
            
            if not path.exists():
                logger.error(f"Configuration file not found: {config_path}")
                return False
            
            with open(path, 'r') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    self.config = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
                    self.config = json.load(f)
                else:
                    logger.error(f"Unsupported configuration file format: {path.suffix}")
                    return False
            
            logger.info(f"Configuration loaded from {config_path}")
            
            # Validate configuration
            if not self._validate_config():
                logger.error("Configuration validation failed")
                return False
            
            return True
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def _validate_config(self) -> bool:
        """
        Validate configuration structure and required fields.
        
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(self.config, dict):
            logger.error("Configuration must be a dictionary")
            return False
        
        # Check for radios section
        if 'radios' not in self.config:
            logger.error("Configuration must contain 'radios' section")
            return False
        
        radios = self.config['radios']
        if not isinstance(radios, list):
            logger.error("'radios' must be a list")
            return False
        
        if len(radios) == 0:
            logger.error("At least one radio must be configured")
            return False
        
        if len(radios) > 8:
            logger.error("Maximum 8 radios can be configured")
            return False
        
        # Validate each radio configuration
        radio_ids = set()
        for i, radio in enumerate(radios):
            if not isinstance(radio, dict):
                logger.error(f"Radio {i} configuration must be a dictionary")
                return False
            
            # Check required fields
            required_fields = ['id', 'host', 'port']
            for field in required_fields:
                if field not in radio:
                    logger.error(f"Radio {i} missing required field: {field}")
                    return False
            
            # Check for duplicate IDs
            radio_id = radio['id']
            if radio_id in radio_ids:
                logger.error(f"Duplicate radio ID: {radio_id}")
                return False
            radio_ids.add(radio_id)
            
            # Validate port number
            try:
                port = int(radio['port'])
                if port < 1 or port > 65535:
                    logger.error(f"Radio {radio_id} has invalid port: {port}")
                    return False
            except (ValueError, TypeError):
                logger.error(f"Radio {radio_id} port must be a number")
                return False
        
        logger.info(f"Configuration validated: {len(radios)} radios configured")
        return True
    
    def get_radios(self) -> List[Dict[str, Any]]:
        """
        Get list of radio configurations.
        
        Returns:
            List of radio configuration dictionaries
        """
        return self.config.get('radios', [])
    
    def get_radio_by_id(self, radio_id: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific radio.
        
        Args:
            radio_id: Radio identifier
        
        Returns:
            Radio configuration dictionary, or None if not found
        """
        for radio in self.get_radios():
            if radio['id'] == radio_id:
                return radio
        return None
    
    def get_test_config(self) -> Dict[str, Any]:
        """
        Get test configuration section.
        
        Returns:
            Test configuration dictionary
        """
        return self.config.get('test_config', {})
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a specific configuration setting.
        
        Args:
            key: Setting key (supports dot notation for nested keys)
            default: Default value if key not found
        
        Returns:
            Setting value or default
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def create_default_config(self, output_path: str) -> bool:
        """
        Create a default configuration file.
        
        Args:
            output_path: Path where to save the configuration
        
        Returns:
            True if created successfully, False otherwise
        """
        default_config = {
            'radios': [
                {
                    'id': 'radio_1',
                    'host': '192.168.1.101',
                    'port': 5000,
                    'issi': '1001',
                    'description': 'Radio 1'
                },
                {
                    'id': 'radio_2',
                    'host': '192.168.1.102',
                    'port': 5000,
                    'issi': '1002',
                    'description': 'Radio 2'
                }
            ],
            'test_config': {
                'default_timeout': 30,
                'retry_count': 3,
                'log_level': 'INFO',
                'call_setup_time': 5,
                'ptt_response_time': 2
            },
            'groups': [
                {
                    'id': 'group_1',
                    'gssi': '9001',
                    'name': 'Test Group 1'
                },
                {
                    'id': 'group_2',
                    'gssi': '9002',
                    'name': 'Test Group 2'
                }
            ]
        }
        
        try:
            path = Path(output_path)
            
            with open(path, 'w') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
                elif path.suffix.lower() == '.json':
                    json.dump(default_config, f, indent=2)
                else:
                    logger.error(f"Unsupported file format: {path.suffix}")
                    return False
            
            logger.info(f"Default configuration created: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating default configuration: {e}")
            return False
    
    def __repr__(self) -> str:
        """String representation of the configuration."""
        num_radios = len(self.get_radios())
        return f"ConfigManager({num_radios} radios configured)"
