---
component:
  name: Component Name
  # One sentence: what transformation does this component perform?
  does: "Takes X as input, returns Y as output"

  # How to import and use (for LLM code generation)
  import: "from core.component_name import MainClass"
  main_class: MainClass
  key_methods:
    - "method_name(param: Type) -> ReturnType"
    - "another_method(param: Type) -> ReturnType"

  # Typed input/output specification
  input:
    type: str | dict | np.ndarray  # Python type hint
    description: "What the input represents"
  output:
    type: ReturnType | List[dict]
    description: "What the output represents"
    fields: [field1, field2]  # If output is dict/object, list key fields

  # Dependencies with context (why, not just what)
  depends_on:
    - component: core.other_component
      why: "Brief explanation of what this dependency provides"
      optional: false
    - component: core.another_component
      why: "Secondary dependency used by some code paths"
      optional: true

  # External API interfaces (required for components calling external APIs)
  # Omit this section if component only uses internal dependencies
  interfaces:
    external_apis:
      - name: ExampleAPI
        purpose: "What this API is used for"
        env_vars: [EXAMPLE_API_KEY]
        docs: "https://example.com/docs"
      - name: SecondaryAPI
        purpose: "Optional fallback or enrichment source"
        env_vars: [SECONDARY_API_KEY]
        optional: true

  # Deployment info (only if relevant)
  deployment:
    lambda: infrastructure/lambda/component-name  # Path or null
    docker: true | false
    standalone: true
---

# Component Name

Brief one-sentence description of what this component does and why it exists.

## Quick Start

```python
from core.component_name import MainClass

# Minimal working example
component = MainClass()
result = component.main_method(input_data)
```

## Overview

What problem does this component solve? How does it fit into the larger system?

## Usage

### Basic Usage

```python
from core.component_name import MainClass

# Initialize
component = MainClass()

# Process single item
result = component.process("input data")
```

### Advanced Usage

```python
# With configuration
component = MainClass(config_option="value")

# Batch processing
results = component.process_batch(items, batch_size=20)
```

## API Reference

### MainClass

#### `__init__(config_option: str = "default")`
Initialize the component.

#### `process(data: InputType) -> OutputType`
Main processing method.

**Parameters:**
- `data`: Description of input

**Returns:**
- Description of output

## Configuration

### Environment Variables
```bash
REQUIRED_VAR="value"
OPTIONAL_VAR="value"  # Optional, defaults to X
```

## Testing

```bash
# Run tests
pytest tests/unit/test_component_name.py -v
```

## Troubleshooting

### Common Issues

**Import Error**: Ensure PYTHONPATH includes project root
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

---

**Last Updated**: April 2026
