# Test Infrastructure Pattern for Finance Skills

## Overview

Pattern for testing multi-component finance analysis pipelines with ground truth data.

## Structure

```
skill-name/
├── SKILL.md
├── scripts/
│   ├── component1.py
│   ├── component2.py
│   ├── pipeline.py
│   └── test_runner.py          ← Test orchestrator
└── references/
    ├── test_case1.json         ← Ground truth data
    ├── test_case2.json
    └── TEST_INFRASTRUCTURE.md  ← This file
```

## Test Runner Pattern

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Path resolution: scripts/ → references/
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

# Import components
from component1 import Component1
from component2 import Component2

def test_component1():
    """Test with ground truth"""
    # Load test data from references/
    test_path = script_dir.parent / "references" / "test_case1.json"
    with open(test_path) as f:
        data = json.load(f)
    
    # Run component
    component = Component1()
    result = component.process(data)
    
    # Validate against expected values
    assert result["output"] == data["expected_output"]
    return True

def main():
    tests = [
        ("Component 1", test_component1),
        ("Component 2", test_component2),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ {test_name} failed: {e}")
            results.append((test_name, False))
    
    # Summary
    passed = sum(1 for _, success in results if success)
    print(f"\n{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
```

## Ground Truth Format

```json
{
  "ticker": "KAEF",
  "timestamp": "09:15",
  "input_data": {
    "prev": 635,
    "open": 660,
    "high": 780,
    "low": 600
  },
  "expected_bias": "HEAVILY_BEARISH",
  "expected_ratio": 3.41,
  "expected_wall": {"price": 790, "lot": 33750}
}
```

## Key Pitfalls

### 1. Path Resolution (scripts/ → references/)

**Problem**: Scripts in `scripts/` can't find files in `references/` using relative paths.

**Solution**:
```python
script_dir = Path(__file__).parent
test_path = script_dir.parent / "references" / "test_file.json"
```

**NOT**:
```python
test_path = script_dir / "references" / "test_file.json"  # ✗ Wrong
```

### 2. F-string with Nested Quotes

**Problem**: `f"text {', '.join(f'{x.get(\"key\", 0):,}' for x in items)}"`

**Solution**: Extract expression first:
```python
formatted = ', '.join(f"{x.get('key', 0):,}" for x in items)
result = f"text {formatted}"
```

### 3. Import Path for Components

**Problem**: Test runner can't import sibling modules.

**Solution**:
```python
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from component1 import Component1  # Now works
```

### 4. Python Interpreter Path

**Problem**: System Python lacks packages.

**Solution**: Always use venv Python:
```bash
~/.hermes/hermes-agent/venv/bin/python3.11 test_runner.py
```

## Test Execution

```bash
# Run all tests
~/.hermes/hermes-agent/venv/bin/python3.11 test_runner.py

# Run with debug output
~/.hermes/hermes-agent/venv/bin/python3.11 test_runner.py --debug

# Run specific test
~/.hermes/hermes-agent/venv/bin/python3.11 test_runner.py --test component1
```

## Validation Patterns

### 1. Exact Match
```python
assert result["value"] == expected["value"]
```

### 2. Tolerance Match (for floats)
```python
diff = abs(result["ratio"] - expected["ratio"]) / expected["ratio"]
assert diff < 0.1  # Within 10%
```

### 3. Enum Match
```python
assert result["bias"] in ["BULLISH", "NEUTRAL", "BEARISH", "HEAVILY_BEARISH"]
assert result["bias"] == expected["bias"]
```

### 4. Structure Match
```python
assert "walls" in result
assert len(result["walls"]["ask"]) > 0
assert result["walls"]["ask"][0]["price"] == expected["wall"]["price"]
```

## Integration Test Pattern

```python
def test_pipeline_integration():
    """Test full pipeline with real data"""
    real_file = Path.home() / ".hermes/test_data.jpg"
    if not real_file.exists():
        return True  # Skip if no real data
    
    pipeline = Pipeline()
    result = pipeline.run(str(real_file))
    
    # Validate structure
    assert "ocr_data" in result
    assert "analysis" in result
    assert "recommendations" in result
    
    # Validate confidence
    assert result["metadata"]["confidence"] > 0
    
    return True
```

## Session Notes (2026-05-11)

- Pattern validated with `idx-orderbook-analysis` skill
- 5 components tested: validator, analyzer, recommendation engine, tracker, pipeline
- All tests passing with ground truth from live trading sessions (KAEF, IRRA, FIRE, WBSA)
- Path resolution pitfall caught and fixed during development
- F-string nested quotes issue resolved in output_formatter.py

## Reusable for

- Stock analysis pipelines
- Financial data validation
- Multi-stage processing workflows
- Any skill with ground truth test data
