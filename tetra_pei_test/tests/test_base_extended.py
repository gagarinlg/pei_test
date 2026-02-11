"""
Extended unit tests for test_base.py to increase code coverage.
"""

import unittest
import time
from tetra_pei_test.core.test_base import TestCase, TestResult


class TestCaseUtilityMethods(unittest.TestCase):
    """Test cases for TestCase utility methods."""
    
    def test_assert_false_with_true_condition(self):
        """Test assert_false fails when condition is true."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="Dummy", description="Test")
            
            def run(self) -> TestResult:
                self.assert_false(True, "Should fail")
                return TestResult.PASSED
        
        test = DummyTest()
        result = test.execute()
        self.assertEqual(result, TestResult.ERROR)
        self.assertIn("Assertion failed", test.error_message)
    
    def test_assert_false_with_false_condition(self):
        """Test assert_false passes when condition is false."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="Dummy", description="Test")
            
            def run(self) -> TestResult:
                self.assert_false(False, "Should pass")
                return TestResult.PASSED
        
        test = DummyTest()
        result = test.execute()
        self.assertEqual(result, TestResult.PASSED)
    
    def test_assert_equal_with_equal_values(self):
        """Test assert_equal passes when values match."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="Dummy", description="Test")
            
            def run(self) -> TestResult:
                self.assert_equal(5, 5, "Should pass")
                return TestResult.PASSED
        
        test = DummyTest()
        result = test.execute()
        self.assertEqual(result, TestResult.PASSED)
    
    def test_assert_equal_with_unequal_values(self):
        """Test assert_equal fails when values don't match."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="Dummy", description="Test")
            
            def run(self) -> TestResult:
                self.assert_equal(5, 10)
                return TestResult.PASSED
        
        test = DummyTest()
        result = test.execute()
        self.assertEqual(result, TestResult.ERROR)
        self.assertIn("Expected 10, got 5", test.error_message)
    
    def test_assert_equal_with_custom_message(self):
        """Test assert_equal uses custom message."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="Dummy", description="Test")
            
            def run(self) -> TestResult:
                self.assert_equal(5, 10, "Custom error")
                return TestResult.PASSED
        
        test = DummyTest()
        result = test.execute()
        self.assertEqual(result, TestResult.ERROR)
        self.assertIn("Custom error", test.error_message)
        self.assertIn("Expected 10, got 5", test.error_message)
    
    def test_wait_with_timeout_condition_met(self):
        """Test wait_with_timeout when condition is met quickly."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="Dummy", description="Test")
                self.counter = 0
            
            def run(self) -> TestResult:
                def condition():
                    self.counter += 1
                    return self.counter >= 2
                
                result = self.wait_with_timeout(condition, timeout=5.0, check_interval=0.1)
                self.assert_true(result, "Should return True")
                return TestResult.PASSED
        
        test = DummyTest()
        result = test.execute()
        self.assertEqual(result, TestResult.PASSED)
    
    def test_wait_with_timeout_condition_timeout(self):
        """Test wait_with_timeout when condition never met."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="Dummy", description="Test")
            
            def run(self) -> TestResult:
                def condition():
                    return False
                
                start = time.time()
                result = self.wait_with_timeout(condition, timeout=1.0, check_interval=0.2)
                duration = time.time() - start
                
                self.assert_false(result, "Should return False on timeout")
                # Check it actually waited
                self.assert_true(duration >= 0.9, f"Should wait near timeout: {duration}s")
                return TestResult.PASSED
        
        test = DummyTest()
        result = test.execute()
        self.assertEqual(result, TestResult.PASSED)
    
    def test_get_duration_before_execution(self):
        """Test get_duration returns 0 before test execution."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="Dummy", description="Test")
            
            def run(self) -> TestResult:
                return TestResult.PASSED
        
        test = DummyTest()
        self.assertEqual(test.get_duration(), 0.0)
    
    def test_get_duration_after_execution(self):
        """Test get_duration returns actual duration after execution."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="Dummy", description="Test")
            
            def run(self) -> TestResult:
                time.sleep(0.1)
                return TestResult.PASSED
        
        test = DummyTest()
        test.execute()
        duration = test.get_duration()
        self.assertGreater(duration, 0.09)
        self.assertLess(duration, 0.5)
    
    def test_repr(self):
        """Test __repr__ string representation."""
        class DummyTest(TestCase):
            def __init__(self):
                super().__init__(name="MyTest", description="Test")
            
            def run(self) -> TestResult:
                return TestResult.PASSED
        
        test = DummyTest()
        test.execute()
        repr_str = repr(test)
        self.assertIn("MyTest", repr_str)
        self.assertIn("PASSED", repr_str)


class TestCaseErrorPaths(unittest.TestCase):
    """Test error handling paths in TestCase."""
    
    def test_setup_failure(self):
        """Test that setup failure is handled correctly."""
        class FailingSetupTest(TestCase):
            def __init__(self):
                super().__init__(name="FailingSetup", description="Test")
            
            def setup(self) -> bool:
                return False  # Simulate setup failure
            
            def run(self) -> TestResult:
                return TestResult.PASSED
        
        test = FailingSetupTest()
        result = test.execute()
        self.assertEqual(result, TestResult.ERROR)
        self.assertEqual(test.error_message, "Setup failed")
    
    def test_teardown_exception(self):
        """Test that teardown exception is logged but doesn't affect result."""
        class FailingTeardownTest(TestCase):
            def __init__(self):
                super().__init__(name="FailingTeardown", description="Test")
            
            def run(self) -> TestResult:
                return TestResult.PASSED
            
            def teardown(self) -> None:
                raise RuntimeError("Teardown failed")
        
        test = FailingTeardownTest()
        result = test.execute()
        # Test should still pass even if teardown fails
        self.assertEqual(result, TestResult.PASSED)
    
    def test_run_exception(self):
        """Test that exception in run() is caught and logged."""
        class ExceptionTest(TestCase):
            def __init__(self):
                super().__init__(name="Exception", description="Test")
            
            def run(self) -> TestResult:
                raise ValueError("Test exception")
        
        test = ExceptionTest()
        result = test.execute()
        self.assertEqual(result, TestResult.ERROR)
        self.assertIn("Exception: Test exception", test.error_message)


if __name__ == '__main__':
    unittest.main()
