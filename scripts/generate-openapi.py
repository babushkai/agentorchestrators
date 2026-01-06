#!/usr/bin/env python3
"""Generate OpenAPI specification from FastAPI app."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_orchestrator.api.app import create_app


def main() -> None:
    """Generate OpenAPI spec and save to file."""
    app = create_app()

    # Get OpenAPI schema
    openapi_schema = app.openapi()

    # Output path
    output_dir = Path(__file__).parent.parent / "docs" / "api"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save as JSON
    json_path = output_dir / "openapi.json"
    with open(json_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"✅ OpenAPI JSON saved to: {json_path}")

    # Save as YAML
    try:
        import yaml
        yaml_path = output_dir / "openapi.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(openapi_schema, f, sort_keys=False, default_flow_style=False)
        print(f"✅ OpenAPI YAML saved to: {yaml_path}")
    except ImportError:
        print("⚠️  PyYAML not installed, skipping YAML generation")


if __name__ == "__main__":
    main()
