"""
Extended unit tests for test_runner.py to increase code coverage.
"""

import unittest
import tempfile
import json
import time
from unittest.mock import Mock, patch
from tetra_pei_test.core.test_runner import TestRunner, setup_logging
from tetra_pei_test.core.config_manager import ConfigManager
from tetra_pei_test.core.test_base import TestCase, TestResult


class SimpleTest(TestCase):
    """Simple test for testing."""
    
    def __init__(self):
        super().__init__(name="Simple", description="Test")
    
    def run(self) -> TestResult:
        return TestResult.PASSED


class TestRunnerExtended(unittest.TestCase):
    """Extended test cases for TestRunner."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a minimal config
        self.config_data = {
            'radios': [
                {'id': 'radio_1', 'host': '127.0.0.1', 'port': 15030}
            ],
            'test_config': {'default_timeout': 5}
        }
        
        self.config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(self.config_data, self.config_file)
        self.config_file.close()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import os
        try:
            os.unlink(self.config_file.name)
        except:
            pass
    
    def test_run_tests_with_no_tests(self):
        """Test run_tests returns True when no tests added."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        result = runner.run_tests()
        self.assertTrue(result)
    
    def test_setup_radios_connection_failure(self):
        """Test setup_radios returns False on connection failure."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        with patch('tetra_pei_test.core.radio_connection.RadioConnection.connect', return_value=False):
            result = runner.setup_radios()
            self.assertFalse(result)
    
    def test_setup_radios_communication_failure(self):
        """Test setup_radios returns False when PEI test_connection fails."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        with patch('tetra_pei_test.core.radio_connection.RadioConnection.connect', return_value=True):
            with patch('tetra_pei_test.core.tetra_pei.TetraPEI.test_connection', return_value=False):
                result = runner.setup_radios()
                self.assertFalse(result)
    
    def test_setup_radios_notification_failure(self):
        """Test setup_radios continues when enable_unsolicited_notifications fails."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        with patch('tetra_pei_test.core.radio_connection.RadioConnection.connect', return_value=True):
            with patch('tetra_pei_test.core.tetra_pei.TetraPEI.test_connection', return_value=True):
                with patch('tetra_pei_test.core.tetra_pei.TetraPEI.enable_unsolicited_notifications', return_value=False):
                    result = runner.setup_radios()
                    # Should still succeed even if notifications fail
                    self.assertTrue(result)
    
    def test_teardown_radios_with_exception(self):
        """Test teardown_radios handles disconnect exceptions."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        # Add mock connection that will raise exception on disconnect
        mock_conn = Mock()
        mock_conn.disconnect.side_effect = RuntimeError("Disconnect failed")
        runner.connections['test_radio'] = mock_conn
        
        # Should not raise exception
        runner.teardown_radios()
        self.assertEqual(len(runner.connections), 0)
    
    def test_run_tests_setup_failure(self):
        """Test run_tests returns False when setup_radios fails."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        runner.add_test(SimpleTest())
        
        with patch.object(runner, 'setup_radios', return_value=False):
            result = runner.run_tests()
            self.assertFalse(result)
    
    def test_repr(self):
        """Test __repr__ string representation."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        runner.add_test(SimpleTest())
        runner.add_test(SimpleTest())
        
        repr_str = repr(runner)
        self.assertIn("TestRunner", repr_str)
        self.assertIn("2 tests", repr_str)
    
    def test_get_results(self):
        """Test get_results returns result list."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        results = runner.get_results()
        self.assertIsInstance(results, list)
    
    def test_clear_results(self):
        """Test clear_results empties result list."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        runner.results = [{'test': 'data'}]
        
        runner.clear_results()
        self.assertEqual(len(runner.results), 0)
    
    def test_clear_tests(self):
        """Test clear_tests empties test list."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        runner.add_test(SimpleTest())
        
        runner.clear_tests()
        self.assertEqual(len(runner.tests), 0)


class TestSetupLogging(unittest.TestCase):
    """Test cases for setup_logging function."""
    
    def test_setup_logging_info(self):
        """Test setup_logging with INFO level."""
        import logging
        setup_logging('INFO')
        logger = logging.getLogger()
        self.assertEqual(logger.level, logging.INFO)
    
    def test_setup_logging_debug(self):
        """Test setup_logging with DEBUG level."""
        import logging
        setup_logging('DEBUG')
        logger = logging.getLogger()
        self.assertEqual(logger.level, logging.DEBUG)
    
    def test_setup_logging_warning(self):
        """Test setup_logging with WARNING level."""
        import logging
        setup_logging('WARNING')
        logger = logging.getLogger()
        self.assertEqual(logger.level, logging.WARNING)
    
    def test_setup_logging_error(self):
        """Test setup_logging with ERROR level."""
        import logging
        setup_logging('ERROR')
        logger = logging.getLogger()
        self.assertEqual(logger.level, logging.ERROR)
    
    def test_setup_logging_critical(self):
        """Test setup_logging with CRITICAL level."""
        import logging
        setup_logging('CRITICAL')
        logger = logging.getLogger()
        self.assertEqual(logger.level, logging.CRITICAL)
    
    def test_setup_logging_invalid_level(self):
        """Test setup_logging with invalid level defaults to INFO."""
        import logging
        setup_logging('INVALID')
        logger = logging.getLogger()
        self.assertEqual(logger.level, logging.INFO)


if __name__ == '__main__':
    unittest.main()
