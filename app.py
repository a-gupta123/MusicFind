"""Vercel loads this module and serves the FastAPI app."""

from findmusic.web import app

__all__ = ["app"]
