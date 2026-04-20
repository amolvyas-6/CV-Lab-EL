"""Command-line entrypoint for the ship dataset pipeline."""

from __future__ import annotations

import logging

from .config import build_arg_parser, build_run_config
from .errors import PipelineError
from .runner import run_local_pipeline
from .utils import configure_logging

LOGGER = logging.getLogger("ship_pipeline.cli")


def main() -> int:
    """Executes pipeline using parsed CLI arguments."""
    parser = build_arg_parser()
    args = parser.parse_args()

    configure_logging(args.log_level)

    config = build_run_config(args)
    run_summary = run_local_pipeline(config)
    LOGGER.info("Run summary: %s", run_summary)

    LOGGER.info("Pipeline run completed successfully.")
    return 0


def run() -> int:
    """Executes CLI with robust top-level error handling."""
    try:
        return main()
    except PipelineError as exc:
        LOGGER.error("Pipeline failed: %s", exc)
        return 1
    except FileNotFoundError as exc:
        LOGGER.error("Missing file/directory: %s", exc)
        return 1
    except KeyboardInterrupt:
        LOGGER.warning("Execution interrupted by user.")
        return 130


def entrypoint() -> None:
    """Console script entrypoint with process exit code propagation."""
    raise SystemExit(run())


if __name__ == "__main__":
    entrypoint()
