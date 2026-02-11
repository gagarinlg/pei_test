"""
Unit tests for ConfigManager class.
"""

import unittest
import os
import tempfile
import json
import yaml
from tetra_pei_test.core.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temp files
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)
    
    def test_create_default_config_json(self):
        """Test creating default JSON configuration."""
        config_path = os.path.join(self.temp_dir, "config.json")
        manager = ConfigManager()
        result = manager.create_default_config(config_path)
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(config_path))
    
    def test_create_default_config_yaml(self):
        """Test creating default YAML configuration."""
        config_path = os.path.join(self.temp_dir, "config.yaml")
        manager = ConfigManager()
        result = manager.create_default_config(config_path)
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(config_path))
    
    def test_load_json_config(self):
        """Test loading JSON configuration."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {
            'radios': [
                {'id': 'radio1', 'host': '192.168.1.1', 'port': 5000}
            ]
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager(config_path)
        self.assertEqual(len(manager.get_radios()), 1)
    
    def test_load_yaml_config(self):
        """Test loading YAML configuration."""
        config_path = os.path.join(self.temp_dir, "config.yaml")
        config_data = {
            'radios': [
                {'id': 'radio1', 'host': '192.168.1.1', 'port': 5000}
            ]
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_path)
        self.assertEqual(len(manager.get_radios()), 1)
    
    def test_validation_missing_radios(self):
        """Test validation with missing radios section."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {'test': 'value'}
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        self.assertFalse(result)
    
    def test_validation_missing_required_fields(self):
        """Test validation with missing required fields."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {
            'radios': [
                {'id': 'radio1'}  # Missing host and port
            ]
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        self.assertFalse(result)
    
    def test_validation_too_many_radios(self):
        """Test validation with more than 8 radios."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {
            'radios': [
                {'id': f'radio{i}', 'host': '192.168.1.1', 'port': 5000}
                for i in range(9)
            ]
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        self.assertFalse(result)
    
    def test_get_radio_by_id(self):
        """Test getting radio configuration by ID."""
        config_path = os.path.join(self.temp_dir, "config.json")
        manager = ConfigManager()
        manager.create_default_config(config_path)
        manager.load_config(config_path)
        
        radio = manager.get_radio_by_id('radio_1')
        self.assertIsNotNone(radio)
        self.assertEqual(radio['id'], 'radio_1')
    
    def test_get_setting(self):
        """Test getting configuration setting."""
        config_path = os.path.join(self.temp_dir, "config.json")
        manager = ConfigManager()
        manager.create_default_config(config_path)
        manager.load_config(config_path)
        
        timeout = manager.get_setting('test_config.default_timeout')
        self.assertEqual(timeout, 30)


if __name__ == '__main__':
    unittest.main()
