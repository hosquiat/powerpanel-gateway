"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from powerpanel_gateway.config import Settings
from powerpanel_gateway.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(mock=True, data_dir=tmp_path, api_token="")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent.parent / "examples" / "sample-pwrstat-output"
