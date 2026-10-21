# Copyright (c) 2026 Warren Spits
"""Fan platform for PGA rangehood."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.fan import FanEntity
from homeassistant.components.fan.const import FanEntityFeature

from .api import CAP_FAN_SPEED, FAN_SPEED_BOOST, FAN_SPEED_LOW, FAN_SPEED_OFF
from .entity import PgaEntity, iter_devices

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import PgaRangehoodCoordinator
    from .data import PgaRangehoodConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PgaRangehoodConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fan platform."""
    entities = [
        PgaRangehoodFan(coordinator, device_id, device)
        for coordinator, device_id, device in iter_devices(entry)
        if CAP_FAN_SPEED in device.get("_limits", {})
    ]
    async_add_entities(entities)


class PgaRangehoodFan(PgaEntity, FanEntity):
    """Representation of a rangehood fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    _unique_suffix = "fan"

    def __init__(
        self,
        coordinator: PgaRangehoodCoordinator,
        device_id: str,
        device: dict[str, Any],
    ) -> None:
        """Initialize the fan entity and its speed range."""
        super().__init__(coordinator, device_id, device)
        bounds = device.get("_limits", {}).get(CAP_FAN_SPEED)
        max_speed = int(bounds["max"]) if bounds else FAN_SPEED_OFF
        self._max_speed = max_speed if max_speed >= FAN_SPEED_LOW else FAN_SPEED_BOOST
        self._attr_speed_count = self._max_speed

    @property
    def is_on(self) -> bool | None:
        """Return True when the fan is running (speed greater than 0)."""
        speed = self._get_float(CAP_FAN_SPEED)
        return speed is not None and speed > 0

    @property
    def percentage(self) -> int | None:
        """Return the current fan speed as a percentage of the device range."""
        speed = self._get_float(CAP_FAN_SPEED)
        if speed is None:
            return None
        return round(int(speed) * 100 / self._max_speed)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed from a percentage of the device range."""
        speed = min(self._max_speed, round(percentage * self._max_speed / 100))
        await self._async_send_command([{"id": CAP_FAN_SPEED, "value": speed}])

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Turn the fan on, optionally at a given percentage."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._async_send_command(
                [{"id": CAP_FAN_SPEED, "value": FAN_SPEED_LOW}]
            )

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Turn the fan off."""
        await self._async_send_command([{"id": CAP_FAN_SPEED, "value": FAN_SPEED_OFF}])
