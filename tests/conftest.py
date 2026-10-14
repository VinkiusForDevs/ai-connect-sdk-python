"""Shared pytest fixtures for the Vinkius Connect Python SDK tests."""

from __future__ import annotations

import pytest

from vinkius_connect import Vinkius
from fake_client import FakeClient


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def vinkius(fake_client: FakeClient) -> Vinkius:
    return Vinkius(
        app_id="vk_app_test",
        api_key="vk_app_sk_test",
        client=fake_client,
    )


def make_vinkius(fake_client: FakeClient, **kwargs) -> Vinkius:
    return Vinkius(
        app_id=kwargs.pop("app_id", "vk_app_test"),
        api_key=kwargs.pop("api_key", "vk_app_sk_test"),
        client=fake_client,
        **kwargs,
    )
