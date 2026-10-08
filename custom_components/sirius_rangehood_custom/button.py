# Copyright (c) 2026 Warren Spits
"""Button platform for Sirius Rangehood controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity

from .api import CAP_FILTER_WORN
from .entity import SiriusEntity, iter_devices

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SiriusRangehoodCoordinator
    from .data import SiriusRangehoodConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SiriusRangehoodConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    entities = [
        SiriusRangehoodFilterResetButton(coordinator, did, device)
        for coordinator, did, device in iter_devices(entry)
        if CAP_FILTER_WORN in device.get("_limits", {})
    ]
    async_add_entities(entities)


class SiriusRangehoodFilterResetButton(SiriusEntity, ButtonEntity):
    """Reset the filter-worn flag (and the filter clean countdown)."""

    _attr_translation_key = "reset_filter_worn"

    def __init__(
        self,
        coordinator: SiriusRangehoodCoordinator,
        device_id: str,
        device: dict[str, Any],
    ) -> None:
        """Initialize the filter-worn reset button."""
        super().__init__(
            coordinator, device_id, device, unique_suffix="reset_filter_worn"
        )

    async def async_press(self) -> None:
        """Clear the filter-worn flag, resetting the filter clean countdown."""
        await self._async_send_command([{"id": CAP_FILTER_WORN, "value": 0}])
