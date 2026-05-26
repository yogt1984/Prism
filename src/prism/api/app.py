"""Prism REST API — FastAPI application factory."""

from importlib.metadata import version as pkg_version

from fastapi import FastAPI

from prism.api.rate_limit import RateLimitMiddleware
from prism.api.routes import router


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    try:
        ver = pkg_version("prism")
    except Exception:
        ver = "0.1.0-dev"

    app = FastAPI(
        title="Prism API",
        description="AI-curated multi-perspective news briefings.",
        version=ver,
    )
    app.add_middleware(RateLimitMiddleware)
    app.include_router(router)
    return app
