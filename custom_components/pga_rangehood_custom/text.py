# Copyright (c) 2026 Warren Spits
"""Text platform for Sirius Rangehood device configuration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr

from .api import SiriusAuthError
from .const import DOMAIN
from .entity import SiriusEntity, iter_devices

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import SiriusRangehoodConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SiriusRangehoodConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the text platform."""
    entities = [
        SiriusRangehoodDeviceName(c, did, d) for c, did, d in iter_devices(entry)
    ]
    async_add_entities(entities)


class SiriusRangehoodDeviceName(SiriusEntity, TextEntity):
    """Configuration text entity that renames the device on the Sirius server."""

    _attr_translation_key = "device_name"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:rename-box"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 1

    _unique_suffix = "device_name"

    @property
    def native_value(self) -> str | None:
        """Return the current device name."""
        return self._get_device_state().get("name")

    async def async_set_value(self, value: str) -> None:
        """Rename the device on the Sirius server and reflect it locally."""
        try:
            renamed = await self.coordinator.hub.async_rename_device(
                self._device_id, value
            )
        except SiriusAuthError:
            self.coordinator.request_reauth()
            return
        if not renamed:
            _LOGGER.warning(
                "Rename rejected for device %s; keeping the previous name",
                self._device_id,
            )
            return
        self.coordinator.set_device_name(self._device_id, value)
        self._async_update_registry_name(value)

    @callback
    def _async_update_registry_name(self, name: str) -> None:
        """Mirror the new name onto the device registry entry."""
        registry = dr.async_get(self.hass)
        entry = registry.async_get_device(identifiers={(DOMAIN, self._device_id)})
        if entry is not None:
            registry.async_update_device(entry.id, name=name)
