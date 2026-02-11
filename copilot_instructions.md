# GitHub Copilot Instructions for TETRA PEI Testing Framework

## Project Overview

This is a Python-based automated testing framework for TETRA radios controlled via TETRA PEI (Peripheral Equipment Interface) using AT commands over TCP. The framework supports up to 8 radios and provides comprehensive testing capabilities for voice calls, PTT, and messaging.

## Code Style and Conventions

### General Guidelines
- Use clear, descriptive variable and function names
- Add docstrings to all classes and methods
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Keep functions focused and single-purpose
- Maximum line length: 100 characters

### Documentation Standards
- All classes should have a docstring describing their purpose
- All public methods should have docstrings with Args, Returns, and Raises sections
- Use inline comments sparingly, only for complex logic
- Keep comments up-to-date with code changes

### Error Handling
- Use try-except blocks for operations that can fail
- Log errors with appropriate severity levels
- Provide meaningful error messages
- Clean up resources in finally blocks or context managers
- Never silently catch exceptions without logging

### Logging
- Use the Python logging module
- Log levels:
  - DEBUG: Detailed diagnostic information
  - INFO: General operational information
  - WARNING: Warning messages for unexpected situations
  - ERROR: Error messages for failures
  - CRITICAL: Critical issues requiring immediate attention
- Include context in log messages (radio ID, command, etc.)

## Architecture

### Core Components

1. **RadioConnection** (`core/radio_connection.py`)
   - Handles TCP socket connections to radios
   - Thread-safe send/receive operations
   - Automatic timeout handling
   - Connection state management

2. **TetraPEI** (`core/tetra_pei.py`)
   - High-level TETRA PEI command interface
   - AT command formatting and parsing
   - Event detection (calls, PTT, messages)
   - Response validation

3. **TestCase** (`core/test_base.py`)
   - Abstract base class for all tests
   - Lifecycle methods: setup(), run(), teardown()
   - Assertion helpers
   - Test result tracking

4. **TestRunner** (`core/test_runner.py`)
   - Manages test execution
   - Radio connection setup/teardown
   - Result collection and reporting
   - Parallel radio operations

5. **ConfigManager** (`core/config_manager.py`)
   - Configuration file loading (YAML/JSON)
   - Schema validation
   - Default configuration generation

### Design Patterns

- **Factory Pattern**: Used for test creation
- **Template Method**: TestCase.execute() defines test lifecycle
- **Singleton**: Logger configuration
- **Observer**: Event notifications from radios

## Adding New Features

### Creating a New Test Case

```python
from tetra_pei_test.core.test_base import TestCase, TestResult
import logging

logger = logging.getLogger(__name__)

class NewFeatureTest(TestCase):
    """
    Test description here.
    
    Detailed explanation of what this test validates.
    """
    
    def __init__(self, param1: str = "default"):
        super().__init__(
            name="Descriptive Test Name",
            description="Brief description"
        )
        self.param1 = param1
    
    def setup(self) -> bool:
        """Setup resources before test execution."""
        # Optional setup code
        return True
    
    def run(self) -> TestResult:
        """
        Execute the test.
        
        Returns:
            TestResult indicating test outcome
        """
        try:
            # Get required radios
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            # Test logic here
            # Use self.assert_true(), self.assert_equal() for validations
            
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR
    
    def teardown(self) -> None:
        """Cleanup resources after test execution."""
        # Optional cleanup code
        pass
```

### Adding New AT Commands

When adding support for new TETRA PEI AT commands:

1. Add the method to `TetraPEI` class
2. Follow the existing naming convention
3. Use `_send_command()` for command transmission
4. Parse and validate responses
5. Return appropriate success/failure indication
6. Add comprehensive logging
7. Update documentation

Example:

```python
def new_pei_command(self, parameter: str) -> bool:
    """
    Brief description of the command.
    
    Args:
        parameter: Description of parameter
    
    Returns:
        True if command successful, False otherwise
    """
    logger.info(f"Executing new command on {self.radio_id}: {parameter}")
    success, response = self._send_command(f"AT+NEWCMD={parameter}")
    
    if not success:
        logger.error(f"Command failed: {response}")
        return False
    
    # Parse response if needed
    return True
```

### Configuration Schema

When modifying configuration:
- Update `ConfigManager._validate_config()` method
- Update example configuration files
- Update README.md documentation
- Maintain backward compatibility when possible

## Testing

### Unit Tests

- All new features must have unit tests
- Use the `TetraRadioSimulator` for testing radio interactions
- Test both success and failure scenarios
- Mock external dependencies
- Aim for >80% code coverage

### Integration Tests

- Test complete workflows end-to-end
- Use multiple simulated radios
- Validate error handling paths
- Test timeout scenarios
- Verify cleanup/teardown logic

### Running Tests

```bash
# Run all unit tests
python -m unittest discover tetra_pei_test/tests

# Run specific test
python -m unittest tetra_pei_test.tests.test_tetra_pei

# Run with verbose output
python -m unittest discover tetra_pei_test/tests -v
```

## Common Patterns

### Thread Safety

When accessing shared resources (like sockets):

```python
with self._lock:
    # Thread-safe operations here
    self.socket.sendall(data)
```

### Timeout Handling

All blocking operations should have timeouts:

```python
def wait_for_event(self, timeout: float = 5.0) -> bool:
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if self.check_condition():
            return True
        time.sleep(0.1)  # Prevent busy waiting
    
    return False
```

### Resource Cleanup

Always clean up resources in finally blocks:

```python
try:
    connection.connect()
    # Do work
finally:
    connection.disconnect()
```

### Error Messages

Error messages should be:
- Specific and actionable
- Include relevant context (radio ID, command, etc.)
- Consistent in format
- Helpful for debugging

Example:
```python
logger.error(f"Failed to send command to {self.radio_id}: {command} - {error}")
```

## API Design

### Method Naming
- Use verb_noun pattern: `make_call()`, `send_message()`, `check_status()`
- Boolean methods should start with `is_`, `has_`, or `check_`: `is_connected()`, `has_message()`
- Use clear, unabbreviated names: `register_to_network()` not `reg_net()`

### Return Values
- Use `bool` for simple success/failure
- Use `Optional[T]` for values that might not exist
- Use `Tuple[bool, T]` when returning both status and data
- Raise exceptions for unexpected errors, return False for expected failures

### Parameters
- Use type hints for all parameters
- Provide sensible defaults where appropriate
- Use keyword arguments for optional parameters
- Document all parameters in docstrings

## Common Issues and Solutions

### Socket Errors
- Always set timeouts on sockets
- Handle `socket.timeout` separately from `socket.error`
- Mark connections as disconnected on errors
- Log the specific error for debugging

### AT Command Timing
- Some commands need time to complete (e.g., registration)
- Use appropriate timeouts based on command type
- Don't rely on fixed delays; poll for status when possible
- Document expected response times

### Test Reliability
- Clean up state between tests (disconnect calls, leave groups)
- Don't assume radio state; verify it
- Use unique identifiers to avoid conflicts
- Implement proper teardown even if test fails

## Dependencies

Current dependencies:
- `pyyaml>=6.0` - YAML configuration file support

When adding new dependencies:
- Justify the need
- Use stable, well-maintained packages
- Pin major versions in requirements.txt
- Update documentation

## Version Control

### Commit Messages
- Use present tense: "Add feature" not "Added feature"
- Be specific: "Fix PTT detection timeout" not "Fix bug"
- Reference issues when applicable: "Fix #123: Handle connection timeout"

### Branch Strategy
- `main` - Production-ready code
- `develop` - Integration branch
- `feature/*` - New features
- `bugfix/*` - Bug fixes

## Performance Considerations

- Minimize socket operations (batch when possible)
- Use appropriate buffer sizes for TCP
- Don't poll unnecessarily; use events/callbacks
- Clean up threads and connections promptly
- Consider connection pooling for high-volume testing

## Security

- Never log sensitive data (passwords, keys)
- Validate all configuration inputs
- Use timeouts to prevent DoS
- Sanitize user inputs before sending to radios
- Document any security assumptions

## Future Enhancements

Areas for future improvement:
- Asynchronous operation support (asyncio)
- Web-based test dashboard
- Test result database storage
- Real-time monitoring and alerting
- Support for additional TETRA PEI commands
- Performance metrics collection
- Parallel test execution
- Test replay and debugging tools

## Contact and Support

For questions or issues:
- Check README.md documentation first
- Review existing code patterns
- Consult TETRA PEI specification
- Open GitHub issue for bugs or feature requests
