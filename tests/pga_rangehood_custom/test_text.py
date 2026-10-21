"""Tests for the device-name text configuration entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.pga_rangehood_custom.api import PgaAuthError
from custom_components.pga_rangehood_custom.text import PgaRangehoodDeviceName


def _coordinator(state: dict) -> MagicMock:
    """Return a coordinator stub with one device's state."""
    coordinator = MagicMock()
    coordinator.data = {"dev1": state}
    coordinator.hub.async_rename_device = AsyncMock(return_value=True)
    return coordinator


def _device() -> dict:
    """Return a minimal discovered-device dict."""
    return {"id": 1, "uid": "dev1", "name": "Old Name", "description": "Old Name"}


def _entity(coordinator: MagicMock) -> PgaRangehoodDeviceName:
    """Build the entity and give it a hass so registry writes are no-ops."""
    return PgaRangehoodDeviceName(coordinator, "dev1", _device())


class TestDeviceName:
    """Verify reading and writing the device name."""

    def test_reads_current_name(self) -> None:
        """native_value returns the device's current name."""
        entity = _entity(_coordinator({"name": "Kitchen"}))
        assert entity.native_value == "Kitchen"

    async def test_set_value_renames(self, hass) -> None:
        """A new value calls the rename API and updates local state."""
        coordinator = _coordinator({"name": "Old Name"})
        entity = _entity(coordinator)
        entity.hass = hass

        await entity.async_set_value("New Name")

        coordinator.hub.async_rename_device.assert_awaited_once_with("dev1", "New Name")
        coordinator.set_device_name.assert_called_once_with("dev1", "New Name")

    async def test_rejected_rename_keeps_name(self, hass) -> None:
        """A rejected rename leaves the previous name in place."""
        coordinator = _coordinator({"name": "Old Name"})
        coordinator.hub.async_rename_device = AsyncMock(return_value=False)
        entity = _entity(coordinator)
        entity.hass = hass

        await entity.async_set_value("New Name")

        coordinator.set_device_name.assert_not_called()

    async def test_auth_error_triggers_reauth(self, hass) -> None:
        """An auth failure starts reauth and does not change the name."""
        coordinator = _coordinator({"name": "Old Name"})
        coordinator.hub.async_rename_device = AsyncMock(
            side_effect=PgaAuthError("rejected")
        )
        entity = _entity(coordinator)
        entity.hass = hass

        await entity.async_set_value("New Name")

        coordinator.request_reauth.assert_called_once()
        coordinator.set_device_name.assert_not_called()
