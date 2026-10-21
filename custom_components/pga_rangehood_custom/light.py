# Copyright (c) 2026 Warren Spits
"""Light platform for PGA rangehood."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.light import LightEntity
from homeassistant.components.light.const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
)

from .api import (
    CAP_LIGHT2_BRIGHTNESS,
    CAP_LIGHT2_COLOR_TEMP,
    CAP_LIGHT2_ONOFF,
    CAP_LIGHT_BRIGHTNESS,
    CAP_LIGHT_COLOR_TEMP,
    CAP_LIGHT_ONOFF,
    LIGHT_BRIGHTNESS_MAX,
    LIGHT_BRIGHTNESS_MIN,
    LIGHT_COLOR_TEMP_KELVIN_MAX,
    LIGHT_COLOR_TEMP_KELVIN_MIN,
)
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
    """Set up the light platform."""
    entities = []
    for coordinator, device_id, device in iter_devices(entry):
        limits = device.get("_limits", {})
        if CAP_LIGHT_ONOFF in limits:
            entities.append(PgaRangehoodLight(coordinator, device_id, device))
        if CAP_LIGHT2_ONOFF in limits:
            entities.append(PgaRangehoodSecondaryLight(coordinator, device_id, device))
    async_add_entities(entities)


class PgaRangehoodLight(PgaEntity, LightEntity):
    """Representation of a rangehood light."""

    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_supported_color_modes: set[ColorMode] = {ColorMode.COLOR_TEMP}  # noqa: RUF012
    _attr_min_color_temp_kelvin = LIGHT_COLOR_TEMP_KELVIN_MIN
    _attr_max_color_temp_kelvin = LIGHT_COLOR_TEMP_KELVIN_MAX

    _cap_onoff = CAP_LIGHT_ONOFF
    _cap_brightness = CAP_LIGHT_BRIGHTNESS
    _cap_color_temp = CAP_LIGHT_COLOR_TEMP
    _unique_suffix = "light"

    def __init__(
        self,
        coordinator: PgaRangehoodCoordinator,
        device_id: str,
        device: dict[str, Any],
    ) -> None:
        """Initialize the light entity from the device's colour capabilities."""
        super().__init__(coordinator, device_id, device)
        limits = device.get("_limits", {})
        self._brightness_min = LIGHT_BRIGHTNESS_MIN
        self._brightness_max = LIGHT_BRIGHTNESS_MAX
        if (bounds := limits.get(self._cap_brightness)) is not None:
            low = int(bounds.get("min", LIGHT_BRIGHTNESS_MIN))
            high = int(bounds.get("max", LIGHT_BRIGHTNESS_MAX))
            if high > low:
                self._brightness_min = low
                self._brightness_max = high
        if self._cap_color_temp in limits:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.COLOR_TEMP
            bounds = limits[self._cap_color_temp]
            self._attr_min_color_temp_kelvin = int(bounds["min"])
            self._attr_max_color_temp_kelvin = int(bounds["max"])
        elif self._cap_brightness in limits:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self) -> bool | None:
        """Return True when the light is on."""
        return self._get_bool(self._cap_onoff)

    @property
    def brightness(self) -> int | None:
        """Return the light brightness on the Home Assistant 0-255 scale."""
        pct = self._get_float(self._cap_brightness)
        if pct is None:
            return None
        pct = max(self._brightness_min, min(self._brightness_max, pct))
        normalized = (pct - self._brightness_min) / (
            self._brightness_max - self._brightness_min
        )
        return round(normalized * 255)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the light colour temperature in Kelvin."""
        value = self._get_float(self._cap_color_temp)
        return None if value is None else round(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, applying brightness and colour temperature if given."""
        params = [{"id": self._cap_onoff, "value": 1.0}]

        if ATTR_BRIGHTNESS in kwargs:
            ha_brightness = kwargs[ATTR_BRIGHTNESS]
            pct = self._brightness_min + (ha_brightness / 255) * (
                self._brightness_max - self._brightness_min
            )
            params.append(
                {
                    "id": self._cap_brightness,
                    "value": round(
                        max(self._brightness_min, min(self._brightness_max, pct)), 1
                    ),
                }
            )
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            params.append(
                {
                    "id": self._cap_color_temp,
                    "value": round(float(kwargs[ATTR_COLOR_TEMP_KELVIN])),
                }
            )

        await self._async_send_command(params)

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Turn the light off."""
        await self._async_send_command([{"id": self._cap_onoff, "value": 0.0}])


class PgaRangehoodSecondaryLight(PgaRangehoodLight):
    """Representation of a rangehood secondary light."""

    _attr_translation_key = "secondary_light"

    _cap_onoff = CAP_LIGHT2_ONOFF
    _cap_brightness = CAP_LIGHT2_BRIGHTNESS
    _cap_color_temp = CAP_LIGHT2_COLOR_TEMP
    _unique_suffix = "light2"
