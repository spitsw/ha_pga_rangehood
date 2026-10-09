"""Tests for the Sirius Rangehood coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.sirius_rangehood_custom.api import CommandResult
from custom_components.sirius_rangehood_custom.coordinator import (
    SiriusRangehoodCoordinator,
)


@pytest.fixture
def fake_hub() -> MagicMock:
    """Return a hub mock whose heartbeat requests always succeed."""
    hub = MagicMock()
    hub.async_get_status = AsyncMock(return_value=True)
    return hub


@pytest.fixture
def fake_entry() -> MagicMock:
    """Return a minimal config-entry stand-in."""
    entry = MagicMock()
    entry.entry_id = "test-entry"
    return entry


async def test_apply_mqtt_update_merges_state(hass, fake_hub, fake_entry) -> None:
    """apply_mqtt_update should merge the payload into the coordinator data."""
    coordinator = SiriusRangehoodCoordinator(
        hass, fake_entry, fake_hub, {"dev1": {"device.onOff": 0}}
    )

    coordinator.apply_mqtt_update("dev1", {"device.onOff": 1})

    assert coordinator.data == {"dev1": {"device.onOff": 1}}


async def test_apply_mqtt_update_ignores_unknown_device(
    hass, fake_hub, fake_entry
) -> None:
    """Updates for unknown devices must be ignored entirely (no dispatch)."""
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {"dev1": {}})

    coordinator.apply_mqtt_update("other", {"device.onOff": 1})

    assert coordinator.data is None


async def test_mqtt_availability_uses_grace(hass, fake_hub, fake_entry) -> None:
    """Entities stay available within the grace window, then go unavailable."""
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    assert coordinator.mqtt_available is True

    coordinator.set_mqtt_connected(False)
    assert coordinator.mqtt_connected is False
    assert coordinator.mqtt_available is True  # still within the grace period

    # Pretend the grace period elapsed.
    coordinator._mqtt_down_since -= timedelta(seconds=60)
    assert coordinator.mqtt_available is False

    coordinator.set_mqtt_connected(True)
    assert coordinator.mqtt_available is True

    await coordinator.async_shutdown()


def _mqtt_stub(response):
    """Return an MQTT stub whose acknowledgement resolves to *response*."""
    mqtt = MagicMock()
    mqtt.wait_for_response = AsyncMock(return_value=response)
    return mqtt


async def test_send_command_confirms_via_mqtt(hass, fake_hub, fake_entry) -> None:
    """An accepted command awaits its requestId on the response topic."""
    fake_hub.async_send_command = AsyncMock(
        return_value=CommandResult(accepted=True, request_id="rid-1")
    )
    mqtt = _mqtt_stub({"status": 0})
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    coordinator.attach_mqtt(mqtt)

    assert await coordinator.async_send_command("dev1", []) is True
    mqtt.wait_for_response.assert_awaited_once_with("rid-1")


async def test_send_command_rejected_skips_mqtt(hass, fake_hub, fake_entry) -> None:
    """A rejected HTTP request never waits on the MQTT response."""
    fake_hub.async_send_command = AsyncMock(
        return_value=CommandResult(accepted=False, request_id="rid-2")
    )
    mqtt = _mqtt_stub({"status": 0})
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    coordinator.attach_mqtt(mqtt)

    assert await coordinator.async_send_command("dev1", []) is False
    mqtt.wait_for_response.assert_not_awaited()


async def test_send_command_timeout_is_inconclusive(hass, fake_hub, fake_entry) -> None:
    """A missing acknowledgement is not a failure; the command still sent."""
    fake_hub.async_send_command = AsyncMock(
        return_value=CommandResult(accepted=True, request_id="rid-3")
    )
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    coordinator.attach_mqtt(_mqtt_stub(None))

    assert await coordinator.async_send_command("dev1", []) is True


async def test_send_command_nonzero_status_is_accepted(
    hass, fake_hub, fake_entry
) -> None:
    """A non-zero status is logged but the command was still delivered."""
    fake_hub.async_send_command = AsyncMock(
        return_value=CommandResult(accepted=True, request_id="rid-4")
    )
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    coordinator.attach_mqtt(_mqtt_stub({"status": 7}))

    assert await coordinator.async_send_command("dev1", []) is True


async def test_send_command_without_mqtt(hass, fake_hub, fake_entry) -> None:
    """Without an attached MQTT client the command still succeeds over HTTP."""
    fake_hub.async_send_command = AsyncMock(
        return_value=CommandResult(accepted=True, request_id="rid-5")
    )
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})

    assert await coordinator.async_send_command("dev1", []) is True
