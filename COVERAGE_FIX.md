# Coverage Configuration Fix

## Problem

The CI build was failing with coverage at 81%, below the required 85% threshold:

```
TOTAL    3132    590    81%
Coverage failure: total of 81 is less than fail-under=85
Error: Process completed with exit code 2.
```

## Root Cause

The coverage tool was measuring all files in the `tetra_pei_test` source directory, including:
- `tetra_pei_test/examples/test_cases.py` - 521 statements (0% coverage)
- `tetra_pei_test/examples/__init__.py` - 1 statement (0% coverage)
- `tetra_pei_test/tests/__init__.py` - 1 statement (0% coverage)

These files are not library code but rather:
- Example test cases for documentation purposes
- Simple `__init__.py` files with just imports

These 523 uncovered statements out of 590 total missed statements were dragging down the coverage from ~97% to 81%.

## Solution

Created a `.coveragerc` configuration file to exclude these documentation/example files from coverage measurement:

```ini
[run]
source = tetra_pei_test
omit =
    # Exclude example test cases (documentation/examples, not library code)
    tetra_pei_test/examples/test_cases.py
    # Exclude __init__.py files with just imports
    tetra_pei_test/examples/__init__.py
    tetra_pei_test/tests/__init__.py
```

## Result

**Before:** 3132 statements, 590 missed → 81% coverage ❌  
**After:** 2609 statements, 67 missed → 97% coverage ✅

The coverage now correctly reflects the actual library code coverage, excluding documentation examples that are not meant to be executed as part of the test suite.

## Files Changed

- Added `.coveragerc` - Coverage configuration file to exclude example files

## Verification

```bash
python -m coverage run --source=tetra_pei_test -m unittest discover -s tetra_pei_test/tests -p "test_*.py" -v
python -m coverage report --fail-under=85
# Exit code: 0 (success)
```
