"""Tests for integration setup and unload."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.pga_rangehood_custom as sirius
from custom_components.pga_rangehood_custom.api import (
    DEFAULT_SIRIUS_ENDPOINT,
    DEFAULT_SIRIUS_MQTTS_ENDPOINT,
    CommandResult,
)
from custom_components.pga_rangehood_custom.const import (
    CONF_ENDPOINT,
    CONF_INSECURE_TLS,
    CONF_MQTTS_ENDPOINT,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def _stub_status_refresh(monkeypatch) -> None:
    """Skip the fresh-state wait during setup tests."""
    monkeypatch.setattr(
        sirius.SiriusRangehoodCoordinator,
        "_async_refresh_device",
        AsyncMock(return_value=True),
    )


class _FakeHub:
    """Stand-in for SiriusHub with no network access."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def attach_store(self, _store: Any) -> None:
        pass

    def restore_token(self, _token: Any, _expiry: Any) -> None:
        pass

    @property
    def token_expiry(self):
        return None

    async def async_discover_devices(self, *, retry: bool = True):
        return [
            {
                "id": 1,
                "uid": "uid-1",
                "name": "Test Rangehood",
                "description": "Test Rangehood",
                "_limits": {"device.fanSpeed": {"min": 0.0, "max": 4.0}},
            }
        ]

    async def async_ensure_token(self, *, retry: bool = True) -> str:
        return "token"

    async def async_get_status(self, _device_id: str) -> CommandResult:
        return CommandResult(accepted=True, request_id="test")

    async def async_send_command(self, _device_id: str, _params: Any) -> CommandResult:
        return CommandResult(accepted=True, request_id="test")


class _FakeMQTT:
    """Stand-in for SiriusMQTT with no network access."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.connected = False

    async def async_start(self) -> bool:
        return True

    async def async_stop(self) -> None:
        pass

    def subscribe_device(self, _device_id: str) -> None:
        pass


async def test_setup_and_unload(hass, monkeypatch) -> None:
    """The entry should load, forward platforms, and unload cleanly."""
    monkeypatch.setattr(sirius, "SiriusHub", _FakeHub)
    monkeypatch.setattr(sirius, "SiriusMQTT", _FakeMQTT)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ENDPOINT: DEFAULT_SIRIUS_ENDPOINT,
            CONF_MQTTS_ENDPOINT: DEFAULT_SIRIUS_MQTTS_ENDPOINT,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_INSECURE_TLS: False,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_device_state_shares_discovery_dict(hass, monkeypatch) -> None:
    """The coordinator state and the device list share the same dicts."""
    monkeypatch.setattr(sirius, "SiriusHub", _FakeHub)
    monkeypatch.setattr(sirius, "SiriusMQTT", _FakeMQTT)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ENDPOINT: DEFAULT_SIRIUS_ENDPOINT,
            CONF_MQTTS_ENDPOINT: DEFAULT_SIRIUS_MQTTS_ENDPOINT,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_INSECURE_TLS: False,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = entry.runtime_data
    device = data.devices[0]
    key = device.get("uid") or str(device["id"])
    assert data.coordinator.device_states[key] is device
