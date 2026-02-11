"""
Test Framework Base Classes

Provides base classes and utilities for creating TETRA PEI tests.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from enum import Enum

from .tetra_pei import TetraPEI
from .radio_connection import RadioConnection


logger = logging.getLogger(__name__)


class TestResult(Enum):
    """Test execution results."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class TestCase(ABC):
    """
    Base class for TETRA PEI test cases.
    
    All test cases should inherit from this class and implement the run() method.
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialize test case.
        
        Args:
            name: Test case name
            description: Test case description
        """
        self.name = name
        self.description = description
        self.result = TestResult.SKIPPED
        self.error_message = ""
        self.start_time = 0.0
        self.end_time = 0.0
        self.radios: Dict[str, TetraPEI] = {}
    
    def set_radios(self, radios: Dict[str, TetraPEI]) -> None:
        """
        Set the radio instances for this test.
        
        Args:
            radios: Dictionary mapping radio_id to TetraPEI instance
        """
        self.radios = radios
    
    @abstractmethod
    def run(self) -> TestResult:
        """
        Execute the test case.
        
        This method must be implemented by subclasses.
        
        Returns:
            TestResult indicating test outcome
        """
        pass
    
    def setup(self) -> bool:
        """
        Setup method called before test execution.
        
        Override this method to add custom setup logic.
        
        Returns:
            True if setup successful, False otherwise
        """
        return True
    
    def teardown(self) -> None:
        """
        Teardown method called after test execution.
        
        Override this method to add custom cleanup logic.
        """
        pass
    
    def execute(self) -> TestResult:
        """
        Execute the complete test lifecycle (setup, run, teardown).
        
        Returns:
            TestResult indicating test outcome
        """
        logger.info(f"{'='*60}")
        logger.info(f"Executing test: {self.name}")
        if self.description:
            logger.info(f"Description: {self.description}")
        logger.info(f"{'='*60}")
        
        self.start_time = time.time()
        
        try:
            # Setup phase
            if not self.setup():
                self.result = TestResult.ERROR
                self.error_message = "Setup failed"
                logger.error(f"Test {self.name}: Setup failed")
                return self.result
            
            # Run test
            self.result = self.run()
            
        except Exception as e:
            self.result = TestResult.ERROR
            self.error_message = f"Exception: {str(e)}"
            logger.error(f"Test {self.name} raised exception: {e}", exc_info=True)
        
        finally:
            # Teardown phase (always executed)
            try:
                self.teardown()
            except Exception as e:
                logger.error(f"Teardown failed for {self.name}: {e}")
            
            self.end_time = time.time()
        
        # Log result
        duration = self.end_time - self.start_time
        logger.info(f"Test {self.name}: {self.result.value} (duration: {duration:.2f}s)")
        if self.error_message:
            logger.info(f"Error message: {self.error_message}")
        logger.info(f"{'='*60}\n")
        
        return self.result
    
    def assert_true(self, condition: bool, message: str = "") -> None:
        """
        Assert that a condition is true.
        
        Args:
            condition: Condition to check
            message: Error message if assertion fails
        
        Raises:
            AssertionError: If condition is false
        """
        if not condition:
            error = f"Assertion failed: {message}" if message else "Assertion failed"
            logger.error(error)
            raise AssertionError(error)
    
    def assert_false(self, condition: bool, message: str = "") -> None:
        """
        Assert that a condition is false.
        
        Args:
            condition: Condition to check
            message: Error message if assertion fails
        
        Raises:
            AssertionError: If condition is true
        """
        self.assert_true(not condition, message)
    
    def assert_equal(self, actual: Any, expected: Any, message: str = "") -> None:
        """
        Assert that two values are equal.
        
        Args:
            actual: Actual value
            expected: Expected value
            message: Error message if assertion fails
        
        Raises:
            AssertionError: If values are not equal
        """
        if actual != expected:
            error = f"Expected {expected}, got {actual}"
            if message:
                error = f"{message}: {error}"
            logger.error(error)
            raise AssertionError(error)
    
    def wait_with_timeout(self, condition_func, timeout: float = 10.0, 
                         check_interval: float = 0.5) -> bool:
        """
        Wait for a condition to become true within a timeout.
        
        Args:
            condition_func: Function that returns True when condition is met
            timeout: Maximum time to wait in seconds
            check_interval: Time between checks in seconds
        
        Returns:
            True if condition met, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if condition_func():
                return True
            time.sleep(check_interval)
        
        return False
    
    def get_duration(self) -> float:
        """Get test execution duration in seconds."""
        if self.end_time > 0:
            return self.end_time - self.start_time
        return 0.0
    
    def __repr__(self) -> str:
        """String representation of the test case."""
        return f"TestCase('{self.name}', result={self.result.value})"
