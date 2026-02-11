# Test Helper API Guide

This guide shows how to use the test helper API to create complex multi-radio test cases easily.

## Overview

The test helper API provides four main classes to simplify test creation:

1. **CallSession** - Manage call lifecycle with automatic cleanup
2. **PTTSession** - Manage PTT operations with automatic release
3. **RadioGroup** - Manage groups of radios
4. **TestScenarioBuilder** - Fluent API for building complex scenarios

## CallSession

Context manager that handles call setup and teardown automatically.

### Basic Usage

```python
from tetra_pei_test.core.test_helpers import CallSession

# Individual call - automatically ended when context exits
with CallSession(radio1, "2001", "individual") as call:
    call.wait(2)  # Keep call active for 2 seconds
# Call is now ended

# Group call
with CallSession(radio1, "9001", "group") as call:
    call.wait(3)

# Emergency call
with CallSession(radio1, "2001", "individual", emergency=True) as call:
    call.wait(2)
```

### Parallel Calls

```python
# Multiple calls active simultaneously
with CallSession(radio1, "9001", "group") as call1, \
     CallSession(radio2, "9002", "group") as call2:
    # Both calls active
    call1.wait(2)
    # Do something with both calls
# Both calls automatically ended
```

## PTTSession

Context manager that handles PTT press and release automatically.

### Basic Usage

```python
from tetra_pei_test.core.test_helpers import PTTSession

# Manual timing
with PTTSession(radio1) as ptt:
    time.sleep(2)  # PTT pressed for 2 seconds
# PTT automatically released

# Auto-release after duration
with PTTSession(radio1, press_duration=2):
    pass  # PTT pressed and released after 2 seconds
```

### Parallel PTT

```python
# Multiple radios transmitting simultaneously
with PTTSession(radio1) as ptt1, \
     PTTSession(radio2) as ptt2:
    time.sleep(3)  # Both PTTs active
# Both PTTs automatically released
```

### Sequential PTT

```python
# One after another
for radio in [radio1, radio2, radio3]:
    with PTTSession(radio, press_duration=1):
        pass  # Each radio transmits for 1 second
```

## RadioGroup

Helper class for managing multiple radios as a group.

### Basic Usage

```python
from tetra_pei_test.core.test_helpers import RadioGroup

# Create group
group = RadioGroup([radio1, radio2, radio3], ["Radio1", "Radio2", "Radio3"])

# Join all radios to a group
group.join_group("9001")

# Make a call from one radio
with group.make_call("9001", caller_index=0) as caller:
    # caller is radio at index 0
    time.sleep(2)
# Call automatically ended

# Leave group
group.leave_group("9001")

# Access individual radios
radio = group.get(0)  # or group[0]
```

## TestScenarioBuilder

Fluent API for building complex test scenarios with a readable, chainable interface.

### Basic Example

```python
from tetra_pei_test.core.test_helpers import TestScenarioBuilder

# Assuming you have a dict of radios: {"radio_1": pei1, "radio_2": pei2, ...}

builder = TestScenarioBuilder(radios)

# Setup groups: group_id -> [radio_indices]
builder.setup_groups({
    "9001": [0, 1],  # Radios at indices 0 and 1
    "9002": [2, 3]   # Radios at indices 2 and 3
})

# Establish parallel calls: (target, radio_index, call_type)
builder.parallel_calls([
    ("9001", 0, "group"),
    ("9002", 2, "group")
])

# Sequential PTT: (radio_index, duration_seconds)
builder.with_ptt([
    (0, 2),
    (2, 2)
], parallel=False)

# Parallel PTT
builder.with_ptt([
    (0, 2),
    (2, 2)
], parallel=True)

# Wait
builder.wait(1)

# Cleanup everything
builder.cleanup()
```

### Full Scenario Example

```python
def run(self):
    try:
        builder = TestScenarioBuilder(self.radios)
        
        # Setup 3 groups with 2 radios each
        builder.setup_groups({
            "9001": [0, 1],
            "9002": [2, 3],
            "9003": [4, 5]
        })
        
        # Establish 3 parallel calls
        builder.parallel_calls([
            ("9001", 0, "group"),
            ("9002", 2, "group"),
            ("9003", 4, "group")
        ])
        
        # Each group takes turns transmitting
        builder.with_ptt([
            (0, 2),
            (2, 2),
            (4, 2)
        ], parallel=False)
        
        builder.wait(1)
        
        # All groups transmit simultaneously
        builder.with_ptt([
            (0, 2),
            (2, 2),
            (4, 2)
        ], parallel=True)
        
        # Cleanup
        builder.cleanup()
        
        return TestResult.PASSED
    except Exception as e:
        self.error_message = str(e)
        return TestResult.ERROR
```

## Complete Test Examples

### Example 1: Simple Parallel Calls with Sequential PTT

```python
class MyParallelCallTest(TestCase):
    def run(self):
        try:
            radios = [self.radios[rid] for rid in list(self.radios.keys())[:4]]
            
            # Setup groups
            group1 = RadioGroup([radios[0], radios[1]])
            group2 = RadioGroup([radios[2], radios[3]])
            
            group1.join_group("9001")
            group2.join_group("9002")
            
            # Establish parallel calls
            with CallSession(radios[0], "9001", "group") as call1, \
                 CallSession(radios[2], "9002", "group") as call2:
                
                # Sequential PTT
                with PTTSession(radios[0], press_duration=2):
                    pass
                
                with PTTSession(radios[2], press_duration=2):
                    pass
            
            # Cleanup
            group1.leave_group("9001")
            group2.leave_group("9002")
            
            return TestResult.PASSED
        except Exception as e:
            self.error_message = str(e)
            return TestResult.ERROR
```

### Example 2: Complex PTT Patterns

```python
class ComplexPTTTest(TestCase):
    def run(self):
        try:
            radios = [self.radios[rid] for rid in list(self.radios.keys())[:3]]
            
            group = RadioGroup(radios)
            group.join_group("9001")
            
            with CallSession(radios[0], "9001", "group"):
                # Rapid PTT cycles
                for i in range(5):
                    with PTTSession(radios[0], press_duration=0.5):
                        pass
                    time.sleep(0.2)
                
                # Quick succession from different radios
                for radio in radios:
                    with PTTSession(radio, press_duration=1):
                        pass
                    time.sleep(0.1)
                
                # Overlapping PTT
                radios[0].press_ptt()
                time.sleep(0.5)
                radios[1].press_ptt()
                time.sleep(1)
                radios[0].release_ptt()
                time.sleep(0.5)
                radios[1].release_ptt()
            
            group.leave_group("9001")
            return TestResult.PASSED
        except Exception as e:
            self.error_message = str(e)
            return TestResult.ERROR
```

### Example 3: Using Fluent API

```python
class FluentAPITest(TestCase):
    def run(self):
        try:
            # Clean, readable test using fluent API
            (TestScenarioBuilder(self.radios)
                .setup_groups({
                    "9001": [0, 1, 2],
                    "9002": [3, 4, 5]
                })
                .parallel_calls([
                    ("9001", 0, "group"),
                    ("9002", 3, "group")
                ])
                .with_ptt([(0, 2), (3, 2)], parallel=False)
                .wait(1)
                .with_ptt([(0, 2), (3, 2)], parallel=True)
                .wait(1)
                .cleanup())
            
            return TestResult.PASSED
        except Exception as e:
            self.error_message = str(e)
            return TestResult.ERROR
```

## Best Practices

### 1. Use Context Managers for Cleanup

Always use context managers (`with` statements) for calls and PTT:

```python
# Good - automatic cleanup
with CallSession(radio, "9001", "group"):
    with PTTSession(radio):
        time.sleep(2)

# Avoid - manual cleanup (error-prone)
radio.make_group_call("9001")
radio.press_ptt()
time.sleep(2)
radio.release_ptt()
radio.end_call()
```

### 2. Use RadioGroup for Multiple Radios

When working with multiple radios doing the same thing:

```python
# Good - clean and clear
group = RadioGroup(radios)
group.join_group("9001")

# Avoid - repetitive
for radio in radios:
    radio.join_group("9001")
```

### 3. Use TestScenarioBuilder for Complex Tests

For tests with multiple steps and parallel operations:

```python
# Good - readable and maintainable
TestScenarioBuilder(radios)
    .setup_groups({"9001": [0, 1, 2]})
    .parallel_calls([("9001", 0)])
    .with_ptt([(0, 2)], parallel=False)
    .cleanup()

# Avoid - harder to read and maintain
radios[0].join_group("9001")
radios[1].join_group("9001")
radios[2].join_group("9001")
radios[0].make_group_call("9001")
radios[0].press_ptt()
time.sleep(2)
radios[0].release_ptt()
radios[0].end_call()
radios[0].leave_group("9001")
radios[1].leave_group("9001")
radios[2].leave_group("9001")
```

### 4. Handle Exceptions Properly

The helpers are designed to work in try/except blocks:

```python
def run(self):
    try:
        with CallSession(radio1, "9001", "group"):
            # Test code here
            pass
        return TestResult.PASSED
    except Exception as e:
        self.error_message = str(e)
        return TestResult.ERROR
```

## Summary

The test helper API makes complex test creation:
- **Easier** - Less boilerplate code
- **Safer** - Automatic cleanup prevents resource leaks
- **Clearer** - Code intent is obvious
- **More maintainable** - Changes are localized

See the example test cases in `tetra_pei_test/examples/test_cases.py` for complete working examples.
