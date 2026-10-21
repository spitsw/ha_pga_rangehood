# Copyright (c) 2026 Warren Spits
"""Switch platform for Sirius Rangehood."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.switch.const import SwitchDeviceClass

from .api import (
    CAP_BI_POWER_ENABLED,
    CAP_CLEAN_AIR_ENABLED,
    CAP_POWER,
    CAP_TIMER_ACTIVE,
    CAP_TIMER_ENABLE,
    CAP_TIMER_VALUE,
)
from .entity import SiriusEntity, iter_devices

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import SiriusRangehoodConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SiriusRangehoodConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    entities = []
    for coordinator, did, device in iter_devices(entry):
        limits = device.get("_limits", {})
        if CAP_POWER in limits:
            entities.append(SiriusRangehoodPowerSwitch(coordinator, did, device))
        if CAP_BI_POWER_ENABLED in limits:
            entities.append(SiriusRangehoodBiPowerSwitch(coordinator, did, device))
        if CAP_CLEAN_AIR_ENABLED in limits:
            entities.append(SiriusRangehoodCleanAirSwitch(coordinator, did, device))
        if CAP_TIMER_ENABLE in limits:
            entities.append(SiriusRangehoodTimerSwitch(coordinator, did, device))
    async_add_entities(entities)


class SiriusRangehoodPowerSwitch(SiriusEntity, SwitchEntity):
    """Global power on/off for a Sirius device."""

    _attr_translation_key = "power"

    _unique_suffix = "power"

    @property
    def is_on(self) -> bool | None:
        """Return True when the device is powered on."""
        return self._get_bool(CAP_POWER)

    @property
    def icon(self) -> str:
        """Return the power icon reflecting the current state."""
        return "mdi:power" if self.is_on else "mdi:power-off"

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Power the device on."""
        await self._async_send_command([{"id": CAP_POWER, "value": 1.0}])

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Power the device off."""
        await self._async_send_command([{"id": CAP_POWER, "value": 0.0}])


class SiriusRangehoodCapabilitySwitch(SiriusEntity, SwitchEntity):
    """Base for a switch that writes 1/0 to a single boolean capability."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    _cap: ClassVar[str]

    @property
    def is_on(self) -> bool | None:
        """Return True when the capability is enabled."""
        return self._get_bool(self._cap)

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Enable the capability."""
        await self._async_send_command([{"id": self._cap, "value": 1.0}])

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Disable the capability."""
        await self._async_send_command([{"id": self._cap, "value": 0.0}])


class SiriusRangehoodBiPowerSwitch(SiriusRangehoodCapabilitySwitch):
    """Enable extra airflow and powerful extraction."""

    _attr_translation_key = "bi_power"

    _cap = CAP_BI_POWER_ENABLED
    _unique_suffix = "bi_power"


class SiriusRangehoodCleanAirSwitch(SiriusRangehoodCapabilitySwitch):
    """Enable the hood's air-clean mode."""

    _attr_translation_key = "clean_air"

    _cap = CAP_CLEAN_AIR_ENABLED
    _unique_suffix = "clean_air"


class SiriusRangehoodTimerSwitch(SiriusEntity, SwitchEntity):
    """Timer on/off; starts and stops the countdown timer."""

    _attr_translation_key = "timer_active"

    _unique_suffix = "timer_active"

    @property
    def is_on(self) -> bool | None:
        """Return True when the countdown timer is running."""
        return self._get_bool(CAP_TIMER_ACTIVE)

    @property
    def available(self) -> bool:
        """Return True when the timer can be started or stopped."""
        state = self._get_device_state()
        return (
            super().available
            and bool(state.get(CAP_TIMER_ENABLE, False))
            and bool(state.get(CAP_TIMER_VALUE, 0))
        )

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Start the countdown timer."""
        await self._async_send_command([{"id": CAP_TIMER_ACTIVE, "value": 1.0}])

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Stop the countdown timer."""
        await self._async_send_command([{"id": CAP_TIMER_ACTIVE, "value": 0.0}])
