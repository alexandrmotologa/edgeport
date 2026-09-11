"""Pytest shared fixtures and configuration."""

import pytest


@pytest.fixture
def sample_headers() -> dict[str, str]:
    return {
        "content-type": "application/json",
        "user-agent": "EdgePort-Test/0.1.0",
        "accept": "*/*",
    }
