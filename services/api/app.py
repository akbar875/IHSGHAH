"""Vercel ASGI entrypoint; dependencies are installed from pyproject.toml."""

from saham_signal.transport.http import create_app

app = create_app()
