# TETRA PEI Automated Testing Framework

A comprehensive Python-based automated testing framework for TETRA radios controlled via TETRA PEI (Peripheral Equipment Interface) using AT commands over TCP.

## Features

- **Multi-Radio Support**: Control up to 8 TETRA radios simultaneously
- **TCP-based Communication**: Connect to radios via TCP using TETRA PEI AT commands
- **Comprehensive Test Coverage**: 
  - Individual calls
  - Group calls
  - Push-to-Talk (PTT) operations
  - Text messages (SDS)
  - Status messages
  - Group registration/deregistration
- **Flexible Configuration**: YAML or JSON configuration files
- **Detailed Logging**: Comprehensive test execution reporting
- **Error Handling**: Robust error detection and reporting
- **Extensible Architecture**: Easy to add new test cases
- **Test Repetition**: Repeat individual tests or entire test suite multiple times
- **Unit Testing**: Complete test suite with radio simulator
- **Clean, Maintainable Code**: Well-documented with clear structure

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/gagarinlg/pei_test.git
cd pei_test
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Create Configuration File

Create a configuration file for your radios:

```bash
python run_tests.py --create-config my_config.yaml
```

Edit the generated configuration file to match your radio setup:

```yaml
radios:
  - id: radio_1
    host: 192.168.1.101
    port: 5000
    issi: "1001"
    description: "Radio 1"
  
  - id: radio_2
    host: 192.168.1.102
    port: 5000
    issi: "1002"
    description: "Radio 2"

test_config:
  default_timeout: 30
  retry_count: 3
  log_level: INFO
```

### 2. Run Tests

Execute the test suite:

```bash
python run_tests.py --config my_config.yaml
```

### 3. View Available Tests

List all available test cases:

```bash
python run_tests.py --list-tests
```

## Configuration

### Configuration File Format

The framework supports both YAML and JSON configuration files. See `config_example.yaml` or `config_example.json` for complete examples.

#### Radio Configuration

```yaml
radios:
  - id: radio_1              # Unique identifier
    host: 192.168.1.101      # IP address or hostname
    port: 5000               # TCP port
    issi: "1001"             # Individual Short Subscriber Identity
    description: "Radio 1"   # Optional description
```

**Required Fields:**
- `id`: Unique identifier for the radio
- `host`: IP address or hostname
- `port`: TCP port number (1-65535)

**Optional Fields:**
- `issi`: Radio's ISSI
- `description`: Human-readable description

**Constraints:**
- Minimum 1 radio, maximum 8 radios
- Each radio must have a unique ID

#### Test Configuration

```yaml
test_config:
  default_timeout: 30        # Default timeout in seconds
  retry_count: 3             # Number of retry attempts
  log_level: INFO            # Logging level
  call_setup_time: 5         # Time to wait for call setup
  ptt_response_time: 2       # Time to wait for PTT response
```

#### Group Configuration

```yaml
groups:
  - id: group_1
    gssi: "9001"             # Group Short Subscriber Identity
    name: "Test Group 1"
    description: "Primary test group"
```

## Usage Examples

### Basic Usage

Run all tests with default configuration:

```bash
python run_tests.py --config config.yaml
```

### Advanced Usage

Run tests with debug logging:

```bash
python run_tests.py --config config.yaml --log-level DEBUG
```

Repeat each test case 3 times (useful for detecting flaky tests):

```bash
python run_tests.py --config config.yaml --repeat-test 3
```

Run the entire test suite 5 times:

```bash
python run_tests.py --config config.yaml --repeat-suite 5
```

Combine both (each test runs 3 times, and entire suite runs 2 times):

```bash
python run_tests.py --config config.yaml --repeat-test 3 --repeat-suite 2
```

### Using the Framework in Code

```python
from tetra_pei_test.core.config_manager import ConfigManager
from tetra_pei_test.core.test_runner import TestRunner, setup_logging
from tetra_pei_test.examples.test_cases import IndividualCallTest, GroupCallTest

# Setup logging
setup_logging('INFO')

# Load configuration
config = ConfigManager('config.yaml')

# Create test runner
runner = TestRunner(config)

# Add tests (optionally with repeat count)
runner.add_test(IndividualCallTest(repeat=3))  # Repeat this test 3 times
runner.add_test(GroupCallTest())

# Run tests (optionally run suite multiple times)
success = runner.run_tests(iterations=2)  # Run entire suite 2 times
```

## Test Cases

The framework includes the following example test cases:

### 1. Individual Call Test
Tests individual call setup and teardown between two radios.
- Radio 1 calls Radio 2
- Radio 2 answers
- Call is maintained
- Call is ended

### 2. Group Call Test
Tests group call with multiple radios.
- All radios join a group
- One radio initiates group call
- Call is maintained
- Call is ended
- All radios leave group

### 3. PTT Test
Tests Push-to-Talk functionality.
- Radios establish connection
- Radio 1 presses PTT
- Radio 2 detects transmission
- Radio 1 releases PTT
- Radio 2 detects end of transmission

### 4. Text Message Test
Tests text message (SDS) sending and receiving.
- Radio 1 sends text message to Radio 2
- Radio 2 receives the message

### 5. Status Message Test
Tests status message sending.
- Radio sends a status message

### 6. Group Registration Test
Tests group registration and deregistration.
- Radio joins multiple groups
- Radio leaves all groups

### 7. Busy Call Test
Tests calling a busy radio (3 radios required).
- Radio 1 calls Radio 2
- Radio 2 answers
- Radio 3 attempts to call Radio 2 (receives BUSY response)
- Radio 1 ends call

### 8. Emergency Call Test
Tests emergency individual call functionality.
- Radio 1 makes emergency call to Radio 2
- Radio 2 answers
- Call is maintained and ended

### 9. Emergency Group Call Test
Tests emergency group call functionality.
- All radios join a group
- Radio 1 makes emergency group call
- Call is maintained and ended

### 10. NO DIALTONE Test
Tests NO DIALTONE response when radio is not registered.

### 11. NO ANSWER Test
Tests NO ANSWER response when called party doesn't answer.

### 12. NO CARRIER Test
Tests NO CARRIER response when connection is lost.

### 13. ERROR Response Test
Tests ERROR response for invalid commands.

### 14. High Priority Message Test
Tests sending high-priority text messages.

### 15. Encryption Test
Tests encryption enable/disable functionality.
- Radio joins multiple groups
- Radio leaves all groups

## Test Repetition Features

The framework supports two types of test repetition:

### 1. Individual Test Repetition

Run a specific test case multiple times to detect intermittent failures:

**Via Command Line:**
```bash
python run_tests.py --config config.yaml --repeat-test 5
```

**In Code:**
```python
# Create a test that will run 5 times
test = GroupCallTest(repeat=5)
runner.add_test(test)
```

When a test is repeated:
- Each iteration runs independently (setup → run → teardown)
- Results from all iterations are tracked
- Overall test result is the worst case (ERROR > FAILED > SKIPPED > PASSED)
- Logs show iteration progress and pass/fail count

### 2. Test Suite Repetition

Run the entire test suite multiple times:

**Via Command Line:**
```bash
python run_tests.py --config config.yaml --repeat-suite 3
```

**In Code:**
```python
runner.add_tests([test1, test2, test3])
success = runner.run_tests(iterations=3)
```

When the suite is repeated:
- Radios are reconnected between suite iterations
- Each iteration runs all tests in order
- Results from all iterations are collected
- Summary includes total runs across all iterations

### 3. Combined Repetition

You can combine both types for comprehensive testing:

```bash
python run_tests.py --config config.yaml --repeat-test 2 --repeat-suite 3
```

This will:
1. Run each test 2 times per suite iteration
2. Run the entire suite 3 times
3. Result in 6 executions per test (2 × 3)

**Use Cases:**
- **Flaky test detection**: Use `--repeat-test` to catch intermittent failures
- **Stress testing**: Use `--repeat-suite` to test system stability over time
- **Reliability verification**: Combine both to ensure consistent behavior

## Emergency Calls and Priority Features

### Emergency Calls

The framework supports emergency calls with special handling:

```python
from tetra_pei_test.core.tetra_pei import TetraPEI

# Make emergency individual call
pei.make_individual_call("2001", emergency=True)

# Make emergency group call
pei.make_group_call("9001", emergency=True)
```

Emergency calls are sent with the `!` flag in AT commands:
- Emergency individual: `ATD<ISSI>!;`
- Emergency group: `ATD<GSSI>!#`

### Priority Messages

Send text messages with different priority levels:

```python
# Normal priority (default)
pei.send_text_message("2001", "Regular message", priority=0)

# High priority
pei.send_text_message("2001", "Important message", priority=1)

# Emergency priority
pei.send_text_message("2001", "URGENT: Emergency message", priority=2)
```

## Advanced Features

### Audio Volume Control

```python
# Set volume (0-100)
pei.set_audio_volume(75)

# Get current volume
volume = pei.get_audio_volume()
print(f"Current volume: {volume}")
```

### Encryption

```python
# Enable encryption with key ID 1
pei.enable_encryption(key_id=1)

# Check encryption status
status = pei.get_encryption_status()
print(f"Encryption enabled: {status['enabled']}")

# Disable encryption
pei.disable_encryption()
```

### Network Operations

```python
# Get signal strength
rssi = pei.get_signal_strength()
print(f"Signal strength: {rssi}")

# Attach to network
pei.attach_to_network()

# Check attachment status
attached = pei.get_network_attachment_status()

# Detach from network
pei.detach_from_network()

# Scan for available networks
networks = pei.scan_for_networks()
for network in networks:
    print(f"Network: {network['name']}")
```

### Operating Modes

```python
# Set to Trunked Mode Operation
pei.set_operating_mode('TMO')

# Set to Direct Mode Operation
pei.set_operating_mode('DMO')
```

### Location Services

```python
# Send GPS coordinates
pei.send_location_info(latitude=51.5074, longitude=-0.1278)
```

### Message Management

```python
# Read stored SDS message
message = pei.read_sds_message(index=1)

# Delete SDS message
pei.delete_sds_message(index=1)
```

### Response Type Checking

All commands return their response type, which you can check:

```python
result = pei.make_individual_call("2001")
response_type = pei.get_last_response_type()

if response_type == "OK":
    print("Call initiated successfully")
elif response_type == "BUSY":
    print("Called party is busy")
elif response_type == "NO ANSWER":
    print("Called party did not answer")
elif response_type == "NO DIALTONE":
    print("No network connection")
```

## Creating Custom Tests

To create a custom test case, inherit from the `TestCase` base class:

```python
from tetra_pei_test.core.test_base import TestCase, TestResult
import logging

logger = logging.getLogger(__name__)

class MyCustomTest(TestCase):
    def __init__(self, repeat: int = 1):
        super().__init__(
            name="My Custom Test",
            description="Description of what this test does",
            repeat=repeat  # Optional: specify repeat count
        )
    
    def run(self) -> TestResult:
        """Execute the test."""
        try:
            # Get radios
            radio1 = self.radios['radio_1']
            radio2 = self.radios['radio_2']
            
            # Perform test operations
            if not radio1.test_connection():
                self.error_message = "Connection test failed"
                return TestResult.FAILED
            
            # More test logic here...
            
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception: {str(e)}"
            return TestResult.ERROR
    
    def setup(self) -> bool:
        """Optional setup before test."""
        return True
    
    def teardown(self) -> None:
        """Optional cleanup after test."""
        pass
```

## TETRA PEI AT Commands

The framework implements comprehensive TETRA PEI AT commands with full response handling:

### AT Command Responses

All AT commands return one of the following final responses:
- `OK` - Command executed successfully
- `ERROR` - Command syntax error or execution failure
- `NO CARRIER` - Call disconnected by remote party
- `NO DIALTONE` - No network or dial tone available
- `BUSY` - Called party is busy (already in a call)
- `NO ANSWER` - Called party did not answer

### Basic Commands
- `AT` - Test connection
- `AT+CGMI` - Get manufacturer
- `AT+CGMM` - Get model
- `AT+CGMR` - Get revision
- `AT+CGSN` - Get serial number/IMEI

### Network Commands
- `AT+COPS=0` - Register to network
- `AT+COPS=?` - Scan for available networks
- `AT+CREG?` - Check registration status
- `AT+CGATT=1` - Attach to network
- `AT+CGATT=0` - Detach from network
- `AT+CGATT?` - Get network attachment status
- `AT+CSQ` - Get signal strength

### Call Commands
- `ATD<ISSI>;` - Make individual call
- `ATD<ISSI>!;` - Make **emergency** individual call
- `ATD<GSSI>#` - Make group call
- `ATD<GSSI>!#` - Make **emergency** group call
- `ATA` - Answer call
- `ATH` - End call

### PTT Commands
- `AT+CTXD=1` - Press PTT
- `AT+CTXD=0` - Release PTT
- `AT+CTXD?` - Query PTT status

### Group Commands
- `AT+CTGS=<GSSI>` - Join group
- `AT+CTGL=<GSSI>` - Leave group

### Message Commands
- `AT+CMGS="<target>","<message>",<priority>` - Send text message (priority: 0=normal, 1=high, 2=emergency)
- `AT+CTSDSR=<target>,<status>` - Send status message
- `AT+CMGR=<index>` - Read stored SDS message
- `AT+CMGD=<index>` - Delete stored SDS message

### Notification Commands
- `AT+CLIP=1` - Enable calling line identification
- `AT+CRC=1` - Enable extended ring format
- `AT+CNMI=2,1` - Enable message notifications

### Audio Commands
- `AT+CLVL=<level>` - Set audio volume (0-100)
- `AT+CLVL?` - Get current audio volume

### Encryption Commands
- `AT+CTENC=<key_id>` - Enable encryption with specified key
- `AT+CTENC=0` - Disable encryption
- `AT+CTENC?` - Get encryption status

### Advanced Commands
- `AT+CTOM=<mode>` - Set operating mode (TMO/DMO)
- `AT+CTLOC=<lat>,<lon>` - Send location information
- `AT+CTAL=<mode>` - Set ambient listening (0=off, 1=on)
- `AT+CTDGNA=<mode>` - Set DGNA mode (0=disabled, 1=enabled)

## Architecture

### Project Structure

```
tetra_pei_test/
├── core/
│   ├── __init__.py
│   ├── radio_connection.py    # TCP connection handler
│   ├── tetra_pei.py           # TETRA PEI protocol implementation
│   ├── test_base.py           # Base test class
│   ├── test_runner.py         # Test execution manager
│   └── config_manager.py      # Configuration handler
├── examples/
│   ├── __init__.py
│   └── test_cases.py          # Example test cases
├── simulator/
│   ├── __init__.py
│   └── radio_simulator.py     # Radio simulator for testing
└── tests/
    ├── __init__.py
    ├── test_radio_connection.py
    ├── test_tetra_pei.py
    └── test_config_manager.py
```

### Key Components

#### RadioConnection
Handles low-level TCP communication with radios.
- Connection management
- Data sending/receiving
- Timeout handling
- Thread-safe operations

#### TetraPEI
Implements TETRA PEI protocol using AT commands.
- High-level command methods
- Response parsing
- Event detection
- Error handling

#### TestRunner
Manages test execution and reporting.
- Radio setup/teardown
- Test scheduling
- Result collection
- Summary generation

#### ConfigManager
Handles configuration loading and validation.
- YAML/JSON support
- Schema validation
- Default configuration generation

## Unit Testing

Run the unit test suite:

```bash
python -m unittest discover tetra_pei_test/tests
```

Run specific test modules:

```bash
python -m unittest tetra_pei_test.tests.test_radio_connection
python -m unittest tetra_pei_test.tests.test_tetra_pei
python -m unittest tetra_pei_test.tests.test_config_manager
```

### Radio Simulator

The framework includes a radio simulator for unit testing:

```python
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator

# Create and start simulator
simulator = TetraRadioSimulator(
    radio_id="sim_radio",
    host="127.0.0.1",
    port=5000,
    issi="9999"
)
simulator.start()

# Simulator responds to AT commands
# ... perform tests ...

# Stop simulator
simulator.stop()
```

## Error Handling

The framework provides comprehensive error handling:

### Connection Errors
- TCP connection failures
- Socket timeouts
- Connection drops

### Command Errors
- AT command failures
- Invalid responses
- Timeout waiting for response

### Test Failures
- Expected events not occurring
- Assertion failures
- Unexpected exceptions

All errors are logged with detailed information and reported in test results.

## Logging

### Log Levels

- **DEBUG**: Detailed information for debugging
- **INFO**: General information about test execution
- **WARNING**: Warning messages
- **ERROR**: Error messages
- **CRITICAL**: Critical errors

### Log Output

Logs are written to stdout with timestamps:

```
2024-01-15 10:30:45 - tetra_pei_test.core.test_runner - INFO - Setting up radio connections...
2024-01-15 10:30:46 - tetra_pei_test.core.radio_connection - INFO - Successfully connected to radio radio_1
```

## Troubleshooting

### Common Issues

**Cannot connect to radio**
- Verify IP address and port in configuration
- Check network connectivity
- Ensure radio PEI interface is enabled
- Check firewall settings

**Tests fail with timeout**
- Increase `default_timeout` in configuration
- Check radio response time
- Verify radio is registered to network

**AT commands fail**
- Check TETRA PEI implementation on radio
- Verify command syntax
- Check radio state (registered, in call, etc.)

**Unit tests fail**
- Install required dependencies: `pip install pyyaml`
- Check Python version (3.7+)
- Verify all files are present

## Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests
5. Submit a pull request

## License

This project is provided as-is for educational and testing purposes.

## Support

For issues, questions, or contributions, please use the GitHub issue tracker.

## Version History

- **1.0.0** - Initial release
  - Multi-radio support
  - Basic TETRA PEI commands
  - Example test cases
  - Radio simulator
  - Unit tests
  - Comprehensive documentation