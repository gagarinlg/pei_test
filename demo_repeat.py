#!/usr/bin/env python3
"""
Simple demonstration of test repetition features.
"""

from tetra_pei_test.core.test_base import TestCase, TestResult
from tetra_pei_test.core.test_runner import TestRunner, setup_logging
from tetra_pei_test.core.config_manager import ConfigManager
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator
import tempfile
import json
import time

# Simple test that counts how many times it runs
class CountingTest(TestCase):
    run_counter = 0
    
    def __init__(self, repeat: int = 1):
        super().__init__(
            name="Counting Test",
            description="Demonstrates repeat functionality",
            repeat=repeat
        )
    
    def run(self) -> TestResult:
        CountingTest.run_counter += 1
        print(f"  → Test execution #{CountingTest.run_counter}")
        time.sleep(0.1)  # Small delay to make it visible
        return TestResult.PASSED

def main():
    print("=" * 70)
    print("TETRA PEI Test Repetition Demo")
    print("=" * 70)
    
    # Setup logging
    setup_logging('INFO')
    
    # Start a simple simulator
    print("\n1. Starting radio simulator...")
    simulator = TetraRadioSimulator(
        radio_id="demo_radio",
        host="127.0.0.1",
        port=15020,
        issi="9999"
    )
    simulator.start()
    time.sleep(0.5)
    print("   ✓ Simulator started")
    
    # Create config
    config_data = {
        'radios': [{'id': 'demo_radio', 'host': '127.0.0.1', 'port': 15020}],
        'test_config': {'default_timeout': 5}
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        config_file = f.name
    
    config = ConfigManager(config_file)
    
    try:
        # Demo 1: Individual test repetition
        print("\n" + "=" * 70)
        print("DEMO 1: Individual Test Repetition (repeat test 3 times)")
        print("=" * 70)
        CountingTest.run_counter = 0
        
        runner = TestRunner(config)
        runner.add_test(CountingTest(repeat=3))
        runner.run_tests()
        
        print(f"\n✓ Test ran {CountingTest.run_counter} times (expected: 3)")
        
        # Demo 2: Suite repetition
        print("\n" + "=" * 70)
        print("DEMO 2: Suite Repetition (run suite 2 times)")
        print("=" * 70)
        CountingTest.run_counter = 0
        
        runner = TestRunner(config)
        runner.add_test(CountingTest(repeat=1))
        runner.run_tests(iterations=2)
        
        print(f"\n✓ Test ran {CountingTest.run_counter} times (expected: 2)")
        
        # Demo 3: Combined
        print("\n" + "=" * 70)
        print("DEMO 3: Combined (repeat test 2x, run suite 2x = 4 total)")
        print("=" * 70)
        CountingTest.run_counter = 0
        
        runner = TestRunner(config)
        runner.add_test(CountingTest(repeat=2))
        runner.run_tests(iterations=2)
        
        print(f"\n✓ Test ran {CountingTest.run_counter} times (expected: 4)")
        
        print("\n" + "=" * 70)
        print("✓ All demos completed successfully!")
        print("=" * 70)
        
    finally:
        simulator.stop()
        import os
        os.unlink(config_file)

if __name__ == '__main__':
    main()
