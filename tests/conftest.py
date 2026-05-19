"""Shared test configuration.

Sets minimal env vars so that Settings() doesn't fail during test collection.
"""

import os

# Provide dummy values for required config fields during testing.
# These are never used — agents are not called in unit tests.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy")
