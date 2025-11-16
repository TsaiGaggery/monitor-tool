# Testing Guide

This directory contains unit and integration tests for the monitor-tool project.

## Setup

### Install Test Dependencies

```bash
# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-mock pytest-cov
```

Or install all requirements including test dependencies:

```bash
pip install -r requirements.txt
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run with Coverage Report

```bash
pytest --cov=src --cov-report=html
```

Then open `htmlcov/index.html` in your browser to see the coverage report.

### Run Specific Test File

```bash
pytest tests/unit/test_data_logger.py
pytest tests/unit/test_cpu_monitor.py
```

### Run Specific Test Class

```bash
pytest tests/unit/test_data_logger.py::TestDataLoggerInit
```

### Run Specific Test

```bash
pytest tests/unit/test_data_logger.py::TestDataLoggerInit::test_creates_database_file
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Tests Matching Pattern

```bash
pytest -k "cleanup"  # Run all tests with 'cleanup' in name
```

## Test Structure

```
tests/
├── unit/                    # Unit tests with mocked dependencies
│   ├── test_data_logger.py  # DataLogger tests
│   ├── test_cpu_monitor.py  # CPUMonitor tests
│   └── ...
├── integration/             # Integration tests (future)
│   └── ...
└── README.md               # This file
```

## Writing Tests

### Unit Tests

Unit tests should mock all external dependencies (filesystem, hardware, network):

```python
import pytest
from unittest.mock import Mock, patch

@patch('module.external_dependency')
def test_something(mock_dependency):
    mock_dependency.return_value = 'mocked_value'
    # Test code here
    assert result == expected
```

### Test Fixtures

Use pytest fixtures for reusable test setup:

```python
@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Setup
    yield db
    # Teardown
```

### Parametrized Tests

Test multiple scenarios with `@pytest.mark.parametrize`:

```python
@pytest.mark.parametrize("input,expected", [
    (0, 0),
    (50, 50),
    (100, 100),
])
def test_values(input, expected):
    assert process(input) == expected
```

## Test Coverage

Current test coverage:

- **DataLogger**: ~90% (initialization, logging, cleanup, queries, thread-safety)
- **CPUMonitor**: ~80% (usage, frequency, temperature, error handling)
- **Other modules**: TBD

### Coverage Goals

- Maintain >80% coverage for critical modules
- 100% coverage for data storage and logging
- Mock all hardware dependencies

## Continuous Integration

Tests can be run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install pytest pytest-mock pytest-cov
    pytest --cov=src --cov-report=xml
```

## Troubleshooting

### Import Errors

If you get import errors, make sure src is in PYTHONPATH:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest
```

### Permission Errors

Some tests may require permissions (e.g., accessing /sys files). Run in a container or VM for isolation.

### Hardware Mocking

All hardware access should be mocked. If tests try to access real hardware, add mocks:

```python
@patch('psutil.cpu_percent')
@patch('psutil.cpu_freq')
def test_cpu_monitor(mock_freq, mock_percent):
    # Test code
```

## Future Tests

Planned test additions:

- [ ] MemoryMonitor tests
- [ ] GPUMonitor tests (Intel/NVIDIA/AMD)
- [ ] NPUMonitor tests
- [ ] NetworkMonitor tests
- [ ] DiskMonitor tests
- [ ] FrequencyController tests
- [ ] CLI integration tests
- [ ] GUI widget tests
