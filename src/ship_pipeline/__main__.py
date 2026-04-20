"""Module execution entrypoint.

Usage:
    uv run python -m ship_pipeline
"""

from .cli import run

if __name__ == "__main__":
    raise SystemExit(run())
