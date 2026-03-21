"""Pytest configuration for worker tests."""

from __future__ import annotations

from typing import Any


def pytest_addoption(parser: Any, pluginmanager: Any) -> None:
    """Register pytest-asyncio ini keys when the plugin is not installed."""
    if pluginmanager.hasplugin("asyncio") or pluginmanager.hasplugin("pytest_asyncio"):
        return

    parser.addini(
        "asyncio_default_fixture_loop_scope",
        "Fallback registration for environments without pytest-asyncio.",
        default="function",
    )
