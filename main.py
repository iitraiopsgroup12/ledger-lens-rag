"""Entrypoint to run the FastAPI application programmatically using Uvicorn.

This module starts the application defined in `src/rag_mcp/api/server.py` so
that you can run the project with `python main.py` instead of calling
`uvicorn` externally.
"""
from __future__ import annotations

import argparse
import logging

import uvicorn

from rag_mcp.api.server import app as fastapi_app
from rag_mcp.config import get_settings
from rag_mcp.utils.logging import configure_logging


def main(argv: list[str] | None = None) -> None:
    """Configure logging and run the FastAPI app with uvicorn.

    Args:
        argv: Optional list of CLI arguments (for testing). If None the
            arguments from the environment are used.
    """
    parser = argparse.ArgumentParser(prog="ledger-lens-rag")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload (dev only)")
    args = parser.parse_args(argv)

    # Load settings and configure structured logging
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting ledger-lens-rag FastAPI server", extra={"host": args.host, "port": args.port})

    # Run uvicorn programmatically
    uvicorn.run(
        fastapi_app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,  # we configure logging ourselves
    )


if __name__ == "__main__":
    main()
