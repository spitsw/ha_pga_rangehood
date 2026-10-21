"""Tests for the Sirius Rangehood coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.pga_rangehood_custom.api import (
    CAP_FAN_SPEED,
    CAP_HOOD_POWER,
    CommandResult,
)
from custom_components.pga_rangehood_custom.coordinator import (
    SiriusRangehoodCoordinator,
)


@pytest.fixture
def fake_hub() -> MagicMock:
    """Return a hub mock whose heartbeat requests always succeed."""
    hub = MagicMock()
    hub.async_get_status = AsyncMock(
        return_value=CommandResult(accepted=True, request_id="rid")
    )
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
    """An accepted command is confirmed by its requestId on the response topic."""
    fake_hub.async_send_command = AsyncMock(
        return_value=CommandResult(accepted=True, request_id="rid-1")
    )
    mqtt = _mqtt_stub({"status": 0})
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    coordinator.set_mqtt_connected(True)
    coordinator.attach_mqtt(mqtt)

    await coordinator.async_send_command("dev1", [])
    mqtt.wait_for_response.assert_awaited_once_with("rid-1")


async def test_send_command_requires_mqtt(hass, fake_hub, fake_entry) -> None:
    """A command is refused while MQTT is unavailable."""
    fake_hub.async_send_command = AsyncMock()
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    coordinator.attach_mqtt(_mqtt_stub({"status": 0}))

    with pytest.raises(HomeAssistantError):
        await coordinator.async_send_command("dev1", [])
    fake_hub.async_send_command.assert_not_awaited()


async def test_send_command_rejected_raises(hass, fake_hub, fake_entry) -> None:
    """A rejected HTTP request raises and never waits on the MQTT response."""
    fake_hub.async_send_command = AsyncMock(
        return_value=CommandResult(accepted=False, request_id="rid-2")
    )
    mqtt = _mqtt_stub({"status": 0})
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    coordinator.set_mqtt_connected(True)
    coordinator.attach_mqtt(mqtt)

    with pytest.raises(HomeAssistantError):
        await coordinator.async_send_command("dev1", [])
    mqtt.wait_for_response.assert_not_awaited()


async def test_send_command_timeout_raises(hass, fake_hub, fake_entry) -> None:
    """A missing acknowledgement is an error (result unknown)."""
    fake_hub.async_send_command = AsyncMock(
        return_value=CommandResult(accepted=True, request_id="rid-3")
    )
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    coordinator.set_mqtt_connected(True)
    coordinator.attach_mqtt(_mqtt_stub(None))

    with pytest.raises(HomeAssistantError):
        await coordinator.async_send_command("dev1", [])


async def test_send_command_nonzero_status_raises(hass, fake_hub, fake_entry) -> None:
    """A non-zero acknowledgement status is an error."""
    fake_hub.async_send_command = AsyncMock(
        return_value=CommandResult(accepted=True, request_id="rid-4")
    )
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {})
    coordinator.set_mqtt_connected(True)
    coordinator.attach_mqtt(_mqtt_stub({"status": 7}))

    with pytest.raises(HomeAssistantError):
        await coordinator.async_send_command("dev1", [])


async def test_send_command_rejects_out_of_range(hass, fake_hub, fake_entry) -> None:
    """A value outside the device's limits is refused before sending."""
    fake_hub.async_send_command = AsyncMock()
    device = {"_limits": {CAP_FAN_SPEED: {"min": 0.0, "max": 4.0}}}
    coordinator = SiriusRangehoodCoordinator(
        hass, fake_entry, fake_hub, {"dev1": device}
    )
    coordinator.set_mqtt_connected(True)
    coordinator.attach_mqtt(_mqtt_stub({"status": 0}))

    with pytest.raises(HomeAssistantError):
        await coordinator.async_send_command(
            "dev1", [{"id": CAP_FAN_SPEED, "value": 9}]
        )
    fake_hub.async_send_command.assert_not_awaited()


async def test_send_command_rejects_non_writable(hass, fake_hub, fake_entry) -> None:
    """A capability outside the writable allowlist is refused."""
    fake_hub.async_send_command = AsyncMock()
    device = {"_limits": {CAP_HOOD_POWER: {"min": 0.0, "max": 500.0}}}
    coordinator = SiriusRangehoodCoordinator(
        hass, fake_entry, fake_hub, {"dev1": device}
    )
    coordinator.set_mqtt_connected(True)
    coordinator.attach_mqtt(_mqtt_stub({"status": 0}))

    with pytest.raises(HomeAssistantError):
        await coordinator.async_send_command(
            "dev1", [{"id": CAP_HOOD_POWER, "value": 1}]
        )
    fake_hub.async_send_command.assert_not_awaited()


async def test_update_data_returns_fresh_state(hass, fake_hub, fake_entry) -> None:
    """The heartbeat returns the state pushed after its getStatus."""
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {"dev1": {}})
    coordinator.set_mqtt_connected(True)

    async def get_status(device_id: str) -> CommandResult:
        # The device pushes its status in response to getStatus.
        coordinator.apply_mqtt_update(device_id, {"device.onOff": 1})
        return CommandResult(accepted=True, request_id="rid")

    fake_hub.async_get_status = AsyncMock(side_effect=get_status)

    assert (await coordinator._async_update_data())["dev1"]["device.onOff"] == 1


async def test_update_data_raises_without_fresh_state(
    hass, fake_hub, fake_entry, monkeypatch
) -> None:
    """A heartbeat that receives no fresh state fails the update."""
    monkeypatch.setattr(SiriusRangehoodCoordinator, "_STATUS_TIMEOUT", 0.01)
    coordinator = SiriusRangehoodCoordinator(hass, fake_entry, fake_hub, {"dev1": {}})

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
