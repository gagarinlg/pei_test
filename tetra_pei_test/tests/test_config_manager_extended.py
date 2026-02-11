"""
Extended unit tests for config_manager.py to increase code coverage.
"""

import unittest
import os
import tempfile
import json
import yaml
from unittest.mock import patch
from tetra_pei_test.core.config_manager import ConfigManager


class TestConfigManagerExtended(unittest.TestCase):
    """Extended test cases for ConfigManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temp files
        for file in os.listdir(self.temp_dir):
            try:
                os.remove(os.path.join(self.temp_dir, file))
            except:
                pass
        try:
            os.rmdir(self.temp_dir)
        except:
            pass
    
    def test_load_config_file_not_found(self):
        """Test loading non-existent config file."""
        config_path = os.path.join(self.temp_dir, "nonexistent.yaml")
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_load_config_invalid_yaml(self):
        """Test loading invalid YAML file."""
        config_path = os.path.join(self.temp_dir, "invalid.yaml")
        with open(config_path, 'w') as f:
            f.write("invalid: yaml: content:\n  - broken")
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_load_config_invalid_json(self):
        """Test loading invalid JSON file."""
        config_path = os.path.join(self.temp_dir, "invalid.json")
        with open(config_path, 'w') as f:
            f.write('{"invalid": json content}')
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_load_config_unsupported_format(self):
        """Test loading unsupported file format."""
        config_path = os.path.join(self.temp_dir, "config.txt")
        with open(config_path, 'w') as f:
            f.write('some text')
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_validation_not_dict(self):
        """Test validation fails if config is not a dictionary."""
        config_path = os.path.join(self.temp_dir, "config.json")
        with open(config_path, 'w') as f:
            json.dump(["not", "a", "dict"], f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_validation_radios_not_list(self):
        """Test validation fails if radios is not a list."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {'radios': 'not a list'}
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_validation_no_radios(self):
        """Test validation fails if radios list is empty."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {'radios': []}
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_validation_radio_not_dict(self):
        """Test validation fails if radio config is not a dict."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {'radios': ['not a dict']}
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_validation_radio_missing_field(self):
        """Test validation fails if radio missing required field."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {
            'radios': [
                {'id': 'radio1', 'host': '192.168.1.1'}  # Missing port
            ]
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_validation_duplicate_radio_id(self):
        """Test validation fails with duplicate radio IDs."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {
            'radios': [
                {'id': 'radio1', 'host': '192.168.1.1', 'port': 5000},
                {'id': 'radio1', 'host': '192.168.1.2', 'port': 5000}
            ]
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_validation_invalid_port_type(self):
        """Test validation fails with non-numeric port."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {
            'radios': [
                {'id': 'radio1', 'host': '192.168.1.1', 'port': 'not_a_number'}
            ]
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_validation_port_out_of_range(self):
        """Test validation fails with port out of valid range."""
        config_path = os.path.join(self.temp_dir, "config.json")
        config_data = {
            'radios': [
                {'id': 'radio1', 'host': '192.168.1.1', 'port': 99999}
            ]
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        manager = ConfigManager()
        result = manager.load_config(config_path)
        
        self.assertFalse(result)
    
    def test_get_radio_by_id_not_found(self):
        """Test get_radio_by_id returns None for unknown ID."""
        config_path = os.path.join(self.temp_dir, "config.json")
        manager = ConfigManager()
        manager.create_default_config(config_path)
        manager.load_config(config_path)
        
        radio = manager.get_radio_by_id('nonexistent')
        self.assertIsNone(radio)
    
    def test_get_test_config(self):
        """Test get_test_config returns config section."""
        config_path = os.path.join(self.temp_dir, "config.json")
        manager = ConfigManager()
        manager.create_default_config(config_path)
        manager.load_config(config_path)
        
        test_config = manager.get_test_config()
        self.assertIsInstance(test_config, dict)
        self.assertIn('default_timeout', test_config)
    
    def test_get_setting_nested(self):
        """Test get_setting with dot notation."""
        config_path = os.path.join(self.temp_dir, "config.json")
        manager = ConfigManager()
        manager.create_default_config(config_path)
        manager.load_config(config_path)
        
        timeout = manager.get_setting('test_config.default_timeout')
        self.assertEqual(timeout, 30)
    
    def test_get_setting_with_default(self):
        """Test get_setting returns default for non-existent key."""
        config_path = os.path.join(self.temp_dir, "config.json")
        manager = ConfigManager()
        manager.create_default_config(config_path)
        manager.load_config(config_path)
        
        value = manager.get_setting('nonexistent.key', default='default_value')
        self.assertEqual(value, 'default_value')
    
    def test_create_default_config_unsupported_format(self):
        """Test create_default_config fails with unsupported format."""
        config_path = os.path.join(self.temp_dir, "config.txt")
        manager = ConfigManager()
        result = manager.create_default_config(config_path)
        
        self.assertFalse(result)
    
    def test_create_default_config_exception(self):
        """Test create_default_config handles exceptions."""
        # Try to write to a directory that doesn't exist
        config_path = "/nonexistent/directory/config.yaml"
        manager = ConfigManager()
        result = manager.create_default_config(config_path)
        
        self.assertFalse(result)
    
    def test_load_config_generic_exception(self):
        """Test load_config handles generic exceptions."""
        config_path = os.path.join(self.temp_dir, "config.json")
        # Create valid config first
        with open(config_path, 'w') as f:
            json.dump({'radios': [{'id': 'r1', 'host': 'h', 'port': 5000}]}, f)
        
        manager = ConfigManager()
        # Mock open to raise a generic exception
        with patch('builtins.open', side_effect=RuntimeError("Generic error")):
            result = manager.load_config(config_path)
            self.assertFalse(result)
    
    def test_repr(self):
        """Test __repr__ string representation."""
        config_path = os.path.join(self.temp_dir, "config.json")
        manager = ConfigManager()
        manager.create_default_config(config_path)
        manager.load_config(config_path)
        
        repr_str = repr(manager)
        self.assertIn("ConfigManager", repr_str)
        self.assertIn("radios", repr_str)


if __name__ == '__main__':
    unittest.main()
