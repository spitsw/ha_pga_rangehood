# Copyright (c) 2026 Warren Spits
"""Shared entity base for Sirius Rangehood entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PROP_DEVICE_NAME, PROP_FW_CODE, PROP_FW_VERSION, SiriusAuthError
from .const import DOMAIN, PROVIDERS
from .coordinator import SiriusRangehoodCoordinator

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .data import SiriusRangehoodConfigEntry


def manufacturer_for_provider(provider: str, endpoint: str = "") -> str:
    """Return the device-registry manufacturer name for a provider."""
    if (known := PROVIDERS.get(provider)) is not None:
        return known.name
    host = urlparse(endpoint).hostname if isinstance(endpoint, str) else None
    return host or "Rangehood"


def device_key(device: dict[str, Any]) -> str:
    """Return a device's stable key: its uid, falling back to the numeric id."""
    return device.get("uid", str(device["id"]))


def iter_devices(
    entry: SiriusRangehoodConfigEntry,
) -> Iterator[tuple[SiriusRangehoodCoordinator, str, dict[str, Any]]]:
    """Yield (coordinator, device_id, device) for every discovered device."""
    data = entry.runtime_data
    for device in data.devices:
        yield data.coordinator, device_key(device), device


def sirius_device_info(
    device_id: str, device: dict[str, Any], *, manufacturer: str
) -> DeviceInfo:
    """Build a DeviceInfo dict for a rangehood device."""
    model = device.get(PROP_DEVICE_NAME) or device.get("description") or "Rangehood"
    fw_version = device.get(PROP_FW_VERSION)
    fw_code = device.get(PROP_FW_CODE)
    if fw_version and fw_code:
        sw_version = f"{fw_version} ({fw_code})"
    elif fw_version:
        sw_version = str(fw_version)
    else:
        sw_version = None
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=device.get("name", f"Rangehood {device_id}"),
        manufacturer=manufacturer,
        model=model,
        sw_version=sw_version,
    )


class SiriusEntity(CoordinatorEntity[SiriusRangehoodCoordinator]):
    """Base class for Sirius Rangehood entities."""

    _attr_has_entity_name = True

    _device_id: str

    def __init__(
        self,
        coordinator: SiriusRangehoodCoordinator,
        device_id: str,
        device: dict[str, Any],
        *,
        unique_suffix: str,
    ) -> None:
        """Initialize the entity, its unique id, and its device registry entry."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{unique_suffix}"
        self._attr_device_info = sirius_device_info(
            device_id,
            device,
            manufacturer=manufacturer_for_provider(
                coordinator.provider, coordinator.hub.endpoint
            ),
        )

    @property
    def available(self) -> bool:
        """Return True when the coordinator is healthy and MQTT is usable."""
        return super().available and self.coordinator.mqtt_available

    def _get_device_state(self) -> dict[str, Any]:
        """Return latest device state from the coordinator."""
        return self.coordinator.data.get(self._device_id, {})

    async def _async_send_command(self, params: list[dict[str, Any]]) -> None:
        """Send a setValue command, confirming it via the MQTT response topic."""
        try:
            await self.coordinator.async_send_command(self._device_id, params)
        except SiriusAuthError:
            self.coordinator.request_reauth()
