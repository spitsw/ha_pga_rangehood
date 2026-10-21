# Copyright (c) 2026 Warren Spits
"""Button platform for PGA rangehood controls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity

from .api import CAP_FILTER_WORN
from .entity import PgaEntity, iter_devices

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import PgaRangehoodConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PgaRangehoodConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    entities = [
        PgaRangehoodFilterResetButton(coordinator, did, device)
        for coordinator, did, device in iter_devices(entry)
        if CAP_FILTER_WORN in device.get("_limits", {})
    ]
    async_add_entities(entities)


class PgaRangehoodFilterResetButton(PgaEntity, ButtonEntity):
    """Reset the filter-worn flag (and the filter clean countdown)."""

    _attr_translation_key = "reset_filter_worn"

    _unique_suffix = "reset_filter_worn"

    async def async_press(self) -> None:
        """Clear the filter-worn flag, resetting the filter clean countdown."""
        await self._async_send_command([{"id": CAP_FILTER_WORN, "value": 0}])
