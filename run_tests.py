#!/usr/bin/env python3
"""
TETRA PEI Test Runner

Main script to execute TETRA PEI automated tests.
"""

import sys
import argparse
from pathlib import Path

from tetra_pei_test.core.config_manager import ConfigManager
from tetra_pei_test.core.test_runner import TestRunner, setup_logging
from tetra_pei_test.examples.test_cases import (
    IndividualCallTest,
    GroupCallTest,
    PTTTest,
    TextMessageTest,
    StatusMessageTest,
    GroupRegistrationTest
)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='TETRA PEI Automated Testing Framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --config config.yaml
  %(prog)s --config config.json --log-level DEBUG
  %(prog)s --create-config my_config.yaml
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to configuration file (JSON or YAML)'
    )
    
    parser.add_argument(
        '--create-config',
        type=str,
        metavar='PATH',
        help='Create a default configuration file and exit'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--list-tests', '-t',
        action='store_true',
        help='List available test cases and exit'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Handle --create-config
    if args.create_config:
        manager = ConfigManager()
        if manager.create_default_config(args.create_config):
            print(f"✓ Default configuration created: {args.create_config}")
            return 0
        else:
            print(f"✗ Failed to create configuration file", file=sys.stderr)
            return 1
    
    # Handle --list-tests
    if args.list_tests:
        print("Available Test Cases:")
        print("=" * 60)
        tests = [
            IndividualCallTest(),
            GroupCallTest(),
            PTTTest(),
            TextMessageTest(),
            StatusMessageTest(),
            GroupRegistrationTest()
        ]
        for test in tests:
            print(f"- {test.name}")
            if test.description:
                print(f"  {test.description}")
        return 0
    
    # Check for config file
    if not args.config:
        print("Error: Configuration file required (use --config or --create-config)", 
              file=sys.stderr)
        parser.print_help()
        return 1
    
    if not Path(args.config).exists():
        print(f"Error: Configuration file not found: {args.config}", file=sys.stderr)
        return 1
    
    # Load configuration
    config_manager = ConfigManager(args.config)
    
    # Create test runner
    runner = TestRunner(config_manager)
    
    # Add all test cases
    runner.add_tests([
        IndividualCallTest(),
        GroupCallTest(),
        PTTTest(),
        TextMessageTest(),
        StatusMessageTest(),
        GroupRegistrationTest()
    ])
    
    # Run tests
    success = runner.run_tests()
    
    # Return appropriate exit code
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
