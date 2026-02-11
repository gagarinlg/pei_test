#!/usr/bin/env python3
"""
Demo script showing TETRA PEI testing framework with simulator.

This script demonstrates the framework by:
1. Starting radio simulators
2. Running example tests against the simulators
3. Displaying test results
"""

import sys
import time
import tempfile
from pathlib import Path

from tetra_pei_test.core.config_manager import ConfigManager
from tetra_pei_test.core.test_runner import TestRunner, setup_logging
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator
from tetra_pei_test.examples.test_cases import (
    IndividualCallTest,
    GroupCallTest,
    PTTTest,
    TextMessageTest,
    StatusMessageTest,
    GroupRegistrationTest
)


def main():
    """Run demo with simulators."""
    print("=" * 70)
    print("TETRA PEI Testing Framework - Demo with Simulator")
    print("=" * 70)
    print()
    
    # Setup logging
    setup_logging('INFO')
    
    # Start simulators
    print("Starting radio simulators...")
    simulators = []
    
    for i in range(1, 3):
        simulator = TetraRadioSimulator(
            radio_id=f"radio_{i}",
            host="127.0.0.1",
            port=15000 + i,
            issi=f"100{i}"
        )
        if simulator.start():
            simulators.append(simulator)
            print(f"  ✓ Started simulator for radio_{i} on port {15000 + i}")
        else:
            print(f"  ✗ Failed to start simulator for radio_{i}")
            return 1
    
    print()
    time.sleep(1)  # Give simulators time to start
    
    # Create temporary config file
    print("Creating configuration...")
    config_data = {
        'radios': [
            {
                'id': 'radio_1',
                'host': '127.0.0.1',
                'port': 15001,
                'issi': '1001',
                'description': 'Simulated Radio 1'
            },
            {
                'id': 'radio_2',
                'host': '127.0.0.1',
                'port': 15002,
                'issi': '1002',
                'description': 'Simulated Radio 2'
            }
        ],
        'test_config': {
            'default_timeout': 10,
            'retry_count': 3,
            'log_level': 'INFO'
        }
    }
    
    # Save config to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        import json
        json.dump(config_data, f)
        config_path = f.name
    
    print(f"  ✓ Configuration created\n")
    
    try:
        # Load configuration
        config_manager = ConfigManager(config_path)
        
        # Create test runner
        runner = TestRunner(config_manager)
        
        # Add subset of tests that work well with simulator
        print("Adding test cases...")
        runner.add_tests([
            IndividualCallTest(),
            GroupCallTest(),
            PTTTest(),
            TextMessageTest(),
            StatusMessageTest(),
            GroupRegistrationTest()
        ])
        print(f"  ✓ Added {len(runner.tests)} test cases\n")
        
        # Run tests
        print("=" * 70)
        print("Starting Test Execution")
        print("=" * 70)
        print()
        
        success = runner.run_tests()
        
        print()
        print("=" * 70)
        if success:
            print("✓ All tests completed successfully!")
        else:
            print("✗ Some tests failed. Check logs above for details.")
        print("=" * 70)
        
        return 0 if success else 1
        
    finally:
        # Cleanup
        print("\nCleaning up...")
        
        # Stop simulators
        for simulator in simulators:
            simulator.stop()
            print(f"  ✓ Stopped {simulator.radio_id}")
        
        # Remove temp config
        try:
            Path(config_path).unlink()
        except:
            pass
        
        print("\nDemo completed!")


if __name__ == '__main__':
    sys.exit(main())
