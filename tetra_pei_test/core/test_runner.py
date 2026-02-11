"""
Test Runner

Manages test execution, radio connections, and result reporting.
"""

import logging
import sys
from typing import List, Dict, Optional
from datetime import datetime

from .config_manager import ConfigManager
from .radio_connection import RadioConnection
from .tetra_pei import TetraPEI
from .test_base import TestCase, TestResult


logger = logging.getLogger(__name__)


class TestRunner:
    """
    Manages the execution of TETRA PEI test cases.
    
    Handles radio connections, test scheduling, and result reporting.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize test runner.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.radios: Dict[str, TetraPEI] = {}
        self.connections: Dict[str, RadioConnection] = {}
        self.tests: List[TestCase] = []
        self.results: List[Dict] = []
    
    def setup_radios(self) -> bool:
        """
        Setup connections to all configured radios.
        
        Returns:
            True if all radios connected successfully, False otherwise
        """
        logger.info("Setting up radio connections...")
        
        radio_configs = self.config.get_radios()
        
        for radio_config in radio_configs:
            radio_id = radio_config['id']
            host = radio_config['host']
            port = radio_config['port']
            
            # Create connection
            connection = RadioConnection(
                radio_id=radio_id,
                host=host,
                port=port,
                timeout=self.config.get_setting('test_config.default_timeout', 5.0)
            )
            
            # Connect to radio
            if not connection.connect():
                logger.error(f"Failed to connect to radio {radio_id}")
                return False
            
            self.connections[radio_id] = connection
            
            # Create PEI handler
            pei = TetraPEI(connection)
            
            # Test connection
            if not pei.test_connection():
                logger.error(f"Failed to communicate with radio {radio_id}")
                connection.disconnect()
                return False
            
            # Enable notifications
            if not pei.enable_unsolicited_notifications():
                logger.warning(f"Failed to enable notifications for radio {radio_id}")
            
            self.radios[radio_id] = pei
            logger.info(f"Successfully setup radio {radio_id}")
        
        logger.info(f"All {len(self.radios)} radios connected successfully")
        return True
    
    def teardown_radios(self) -> None:
        """Disconnect all radios."""
        logger.info("Disconnecting radios...")
        
        for radio_id, connection in self.connections.items():
            try:
                connection.disconnect()
                logger.info(f"Disconnected radio {radio_id}")
            except Exception as e:
                logger.error(f"Error disconnecting radio {radio_id}: {e}")
        
        self.radios.clear()
        self.connections.clear()
    
    def add_test(self, test: TestCase) -> None:
        """
        Add a test case to the test suite.
        
        Args:
            test: TestCase instance to add
        """
        self.tests.append(test)
        logger.info(f"Added test: {test.name}")
    
    def add_tests(self, tests: List[TestCase]) -> None:
        """
        Add multiple test cases to the test suite.
        
        Args:
            tests: List of TestCase instances
        """
        for test in tests:
            self.add_test(test)
    
    def run_tests(self) -> bool:
        """
        Execute all test cases in the suite.
        
        Returns:
            True if all tests passed, False otherwise
        """
        if not self.tests:
            logger.warning("No tests to run")
            return True
        
        logger.info(f"\n{'#'*60}")
        logger.info(f"# Starting Test Execution")
        logger.info(f"# Total tests: {len(self.tests)}")
        logger.info(f"# Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'#'*60}\n")
        
        # Setup radios
        if not self.setup_radios():
            logger.error("Failed to setup radios. Aborting test execution.")
            return False
        
        try:
            # Run each test
            for i, test in enumerate(self.tests, 1):
                logger.info(f"\n[Test {i}/{len(self.tests)}]")
                
                # Set radios for test
                test.set_radios(self.radios)
                
                # Execute test
                result = test.execute()
                
                # Record result
                self.results.append({
                    'test_name': test.name,
                    'description': test.description,
                    'result': result,
                    'duration': test.get_duration(),
                    'error_message': test.error_message,
                    'timestamp': datetime.now()
                })
        
        finally:
            # Always teardown radios
            self.teardown_radios()
        
        # Print summary
        self._print_summary()
        
        # Return overall success
        return self._all_tests_passed()
    
    def _print_summary(self) -> None:
        """Print test execution summary."""
        passed = sum(1 for r in self.results if r['result'] == TestResult.PASSED)
        failed = sum(1 for r in self.results if r['result'] == TestResult.FAILED)
        errors = sum(1 for r in self.results if r['result'] == TestResult.ERROR)
        skipped = sum(1 for r in self.results if r['result'] == TestResult.SKIPPED)
        
        total_duration = sum(r['duration'] for r in self.results)
        
        logger.info(f"\n{'#'*60}")
        logger.info(f"# Test Execution Summary")
        logger.info(f"{'#'*60}")
        logger.info(f"Total tests:   {len(self.results)}")
        logger.info(f"Passed:        {passed}")
        logger.info(f"Failed:        {failed}")
        logger.info(f"Errors:        {errors}")
        logger.info(f"Skipped:       {skipped}")
        logger.info(f"Total duration: {total_duration:.2f}s")
        logger.info(f"{'#'*60}\n")
        
        # Print failed tests details
        if failed > 0 or errors > 0:
            logger.info("Failed/Error Tests Details:")
            logger.info("-" * 60)
            
            for result in self.results:
                if result['result'] in [TestResult.FAILED, TestResult.ERROR]:
                    logger.info(f"\nTest: {result['test_name']}")
                    logger.info(f"Result: {result['result'].value}")
                    logger.info(f"Duration: {result['duration']:.2f}s")
                    if result['error_message']:
                        logger.info(f"Error: {result['error_message']}")
            
            logger.info("-" * 60)
    
    def _all_tests_passed(self) -> bool:
        """Check if all tests passed."""
        return all(r['result'] == TestResult.PASSED for r in self.results)
    
    def get_results(self) -> List[Dict]:
        """Get list of test results."""
        return self.results
    
    def clear_results(self) -> None:
        """Clear test results."""
        self.results.clear()
    
    def clear_tests(self) -> None:
        """Clear test suite."""
        self.tests.clear()
    
    def __repr__(self) -> str:
        """String representation of the test runner."""
        return f"TestRunner({len(self.radios)} radios, {len(self.tests)} tests)"


def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging for the test framework.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
