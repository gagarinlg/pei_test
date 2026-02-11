"""
Unit tests for repeat functionality in test framework.
"""

import unittest
import time
from tetra_pei_test.core.test_base import TestCase, TestResult
from tetra_pei_test.core.test_runner import TestRunner
from tetra_pei_test.core.config_manager import ConfigManager
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator
import tempfile
import json


class SimplePassingTest(TestCase):
    """A simple test that always passes."""
    
    def __init__(self, repeat: int = 1):
        super().__init__(
            name="Simple Passing Test",
            description="A test that always passes",
            repeat=repeat
        )
        self.run_count = 0
    
    def run(self) -> TestResult:
        self.run_count += 1
        return TestResult.PASSED


class SimpleFailingTest(TestCase):
    """A simple test that always fails."""
    
    def __init__(self, repeat: int = 1):
        super().__init__(
            name="Simple Failing Test",
            description="A test that always fails",
            repeat=repeat
        )
        self.run_count = 0
    
    def run(self) -> TestResult:
        self.run_count += 1
        self.error_message = "Intentional failure"
        return TestResult.FAILED


class FlakeyTest(TestCase):
    """A test that fails on first run, passes on subsequent runs."""
    
    def __init__(self, repeat: int = 1):
        super().__init__(
            name="Flakey Test",
            description="Fails first time, passes after",
            repeat=repeat
        )
        self.run_count = 0
    
    def run(self) -> TestResult:
        self.run_count += 1
        if self.run_count == 1:
            self.error_message = "First run failure"
            return TestResult.FAILED
        return TestResult.PASSED


class TestRepeatFunctionality(unittest.TestCase):
    """Test cases for repeat functionality."""
    
    def test_single_test_no_repeat(self):
        """Test that a test runs once by default."""
        test = SimplePassingTest()
        test.execute()
        
        self.assertEqual(test.run_count, 1)
        self.assertEqual(test.result, TestResult.PASSED)
        self.assertEqual(len(test.iteration_results), 1)
    
    def test_single_test_with_repeat(self):
        """Test that a test can be repeated multiple times."""
        test = SimplePassingTest(repeat=3)
        test.execute()
        
        self.assertEqual(test.run_count, 3)
        self.assertEqual(test.result, TestResult.PASSED)
        self.assertEqual(len(test.iteration_results), 3)
        self.assertTrue(all(r == TestResult.PASSED for r in test.iteration_results))
    
    def test_repeat_with_failures(self):
        """Test that failures are properly tracked in repeated tests."""
        test = SimpleFailingTest(repeat=3)
        test.execute()
        
        self.assertEqual(test.run_count, 3)
        self.assertEqual(test.result, TestResult.FAILED)
        self.assertEqual(len(test.iteration_results), 3)
        self.assertTrue(all(r == TestResult.FAILED for r in test.iteration_results))
    
    def test_repeat_with_flakey_test(self):
        """Test that mixed results are aggregated correctly."""
        test = FlakeyTest(repeat=3)
        test.execute()
        
        self.assertEqual(test.run_count, 3)
        # Should fail overall because at least one iteration failed
        self.assertEqual(test.result, TestResult.FAILED)
        self.assertEqual(len(test.iteration_results), 3)
        # First should fail, rest should pass
        self.assertEqual(test.iteration_results[0], TestResult.FAILED)
        self.assertEqual(test.iteration_results[1], TestResult.PASSED)
        self.assertEqual(test.iteration_results[2], TestResult.PASSED)
    
    def test_repeat_zero_becomes_one(self):
        """Test that repeat=0 is treated as repeat=1."""
        test = SimplePassingTest(repeat=0)
        self.assertEqual(test.repeat, 1)
        test.execute()
        self.assertEqual(test.run_count, 1)
    
    def test_repeat_negative_becomes_one(self):
        """Test that negative repeat is treated as repeat=1."""
        test = SimplePassingTest(repeat=-5)
        self.assertEqual(test.repeat, 1)
        test.execute()
        self.assertEqual(test.run_count, 1)
    
    def test_result_aggregation_priority(self):
        """Test that results are aggregated with correct priority."""
        # ERROR has highest priority
        test = SimplePassingTest(repeat=1)
        test.iteration_results = [TestResult.PASSED, TestResult.ERROR, TestResult.FAILED]
        result = test._aggregate_results()
        self.assertEqual(result, TestResult.ERROR)
        
        # FAILED is next
        test.iteration_results = [TestResult.PASSED, TestResult.FAILED, TestResult.SKIPPED]
        result = test._aggregate_results()
        self.assertEqual(result, TestResult.FAILED)
        
        # SKIPPED is next
        test.iteration_results = [TestResult.PASSED, TestResult.SKIPPED]
        result = test._aggregate_results()
        self.assertEqual(result, TestResult.SKIPPED)
        
        # All PASSED
        test.iteration_results = [TestResult.PASSED, TestResult.PASSED]
        result = test._aggregate_results()
        self.assertEqual(result, TestResult.PASSED)


class TestSuiteRepeat(unittest.TestCase):
    """Test cases for suite-level repeat functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a minimal config
        self.config_data = {
            'radios': [
                {'id': 'radio_1', 'host': '127.0.0.1', 'port': 15010, 'issi': '1001'}
            ],
            'test_config': {'default_timeout': 5}
        }
        
        # Create temp config file
        self.config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(self.config_data, self.config_file)
        self.config_file.close()
        
        # Start simulator
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15010,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.simulator.stop()
        time.sleep(0.5)
        import os
        os.unlink(self.config_file.name)
    
    def test_suite_single_iteration(self):
        """Test running suite once."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        runner.add_tests([
            SimplePassingTest(),
            SimplePassingTest()
        ])
        
        success = runner.run_tests(iterations=1)
        
        self.assertTrue(success)
        self.assertEqual(len(runner.results), 2)
    
    def test_suite_multiple_iterations(self):
        """Test running suite multiple times."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        runner.add_tests([
            SimplePassingTest(),
            SimplePassingTest()
        ])
        
        success = runner.run_tests(iterations=3)
        
        self.assertTrue(success)
        # 2 tests * 3 iterations = 6 results
        self.assertEqual(len(runner.results), 6)
        
        # Check suite iteration tracking
        suite_iterations = [r.get('suite_iteration') for r in runner.results]
        self.assertEqual(suite_iterations, [1, 1, 2, 2, 3, 3])
    
    def test_suite_iterations_with_failures(self):
        """Test that suite iterations handle failures correctly."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        runner.add_tests([
            SimplePassingTest(),
            SimpleFailingTest()
        ])
        
        success = runner.run_tests(iterations=2)
        
        self.assertFalse(success)
        self.assertEqual(len(runner.results), 4)
        
        # Count results
        passed = sum(1 for r in runner.results if r['result'] == TestResult.PASSED)
        failed = sum(1 for r in runner.results if r['result'] == TestResult.FAILED)
        self.assertEqual(passed, 2)  # 2 iterations of passing test
        self.assertEqual(failed, 2)  # 2 iterations of failing test
    
    def test_combined_repeat_and_iterations(self):
        """Test combining test repeat with suite iterations."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        # Add test that repeats 2 times
        runner.add_test(SimplePassingTest(repeat=2))
        
        # Run suite 3 times
        success = runner.run_tests(iterations=3)
        
        self.assertTrue(success)
        # 1 test * 3 suite iterations = 3 results
        # But each test runs 2 times internally
        self.assertEqual(len(runner.results), 3)
        
        # Each result should have 2 iteration results
        for result in runner.results:
            self.assertEqual(len(result['iteration_results']), 2)
    
    def test_iterations_zero_becomes_one(self):
        """Test that iterations=0 is treated as iterations=1."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        runner.add_test(SimplePassingTest())
        success = runner.run_tests(iterations=0)
        
        self.assertTrue(success)
        self.assertEqual(len(runner.results), 1)
    
    def test_iterations_negative_becomes_one(self):
        """Test that negative iterations is treated as iterations=1."""
        config = ConfigManager(self.config_file.name)
        runner = TestRunner(config)
        
        runner.add_test(SimplePassingTest())
        success = runner.run_tests(iterations=-3)
        
        self.assertTrue(success)
        self.assertEqual(len(runner.results), 1)


if __name__ == '__main__':
    unittest.main()
