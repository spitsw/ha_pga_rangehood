# Copyright (c) 2026 Warren Spits
"""Sensor platform for PGA rangehood diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, NamedTuple

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory

from .api import (
    CAP_FAN_FLOW,
    CAP_FAN_POWER,
    CAP_FILTER2_VALUE,
    CAP_FILTER_VALUE,
    CAP_HOOD_POWER,
    CAP_LIGHT2_POWER,
    CAP_LIGHT_POWER,
    CAP_TIMER_ACTIVE,
    CAP_TIMER_ENABLE,
    CAP_TIMER_VALUE,
    PROP_DEVICE_CLASS,
    PROP_DEVICE_REF,
    PROP_DEVICE_TYPE,
    PROP_FW_CODE,
    PROP_FW_VERSION,
    PROP_IP_ADDRESS,
    PROP_RSSI,
    PROP_SECURE_ID,
    PROP_SSID,
)
from .entity import PgaEntity, iter_devices

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import PgaRangehoodCoordinator
    from .data import PgaRangehoodConfigEntry


class _SensorSpec(NamedTuple):
    """Declarative definition of one sensor entity."""

    key: str
    translation_key: str
    icon: str
    device_class: SensorDeviceClass | None = None
    unit: str | None = None


def _descriptions(
    specs: tuple[_SensorSpec, ...], **extra: Any
) -> tuple[SensorEntityDescription, ...]:
    """Build an entity description per spec, applying *extra* to each."""
    return tuple(
        SensorEntityDescription(
            key=spec.key,
            translation_key=spec.translation_key,
            icon=spec.icon,
            device_class=spec.device_class,
            native_unit_of_measurement=spec.unit,
            **extra,
        )
        for spec in specs
    )


_DIAGNOSTIC_SENSORS: tuple[_SensorSpec, ...] = (
    _SensorSpec(PROP_IP_ADDRESS, "ip_address", "mdi:ip-network"),
    _SensorSpec(
        PROP_RSSI, "rssi", "mdi:wifi", SensorDeviceClass.SIGNAL_STRENGTH, "dBm"
    ),
    _SensorSpec(PROP_SSID, "ssid", "mdi:wifi-settings"),
    _SensorSpec(PROP_FW_VERSION, "firmware_version", "mdi:chip"),
    _SensorSpec(PROP_DEVICE_REF, "device_ref", "mdi:tag-text"),
    _SensorSpec(PROP_DEVICE_TYPE, "device_type", "mdi:chip"),
    _SensorSpec(PROP_DEVICE_CLASS, "device_class", "mdi:shape"),
    _SensorSpec(PROP_FW_CODE, "firmware_code", "mdi:counter"),
    _SensorSpec(PROP_SECURE_ID, "secure_id", "mdi:shield-key"),
)

SENSOR_DESCRIPTIONS = _descriptions(
    _DIAGNOSTIC_SENSORS, entity_category=EntityCategory.DIAGNOSTIC
)

# Read-only measurement capabilities, created only when a device exposes them.
_CAPABILITY_SENSORS: tuple[_SensorSpec, ...] = (
    _SensorSpec(
        CAP_LIGHT_POWER,
        "light_power",
        "mdi:lightbulb-outline",
        SensorDeviceClass.POWER,
        "W",
    ),
    _SensorSpec(
        CAP_LIGHT2_POWER,
        "light2_power",
        "mdi:lightbulb-outline",
        SensorDeviceClass.POWER,
        "W",
    ),
    _SensorSpec(CAP_FAN_POWER, "fan_power", "mdi:fan", SensorDeviceClass.POWER, "W"),
    _SensorSpec(
        CAP_HOOD_POWER, "hood_power", "mdi:counter", SensorDeviceClass.POWER, "W"
    ),
    _SensorSpec(
        CAP_FAN_FLOW,
        "fan_flow",
        "mdi:weather-windy",
        SensorDeviceClass.VOLUME_FLOW_RATE,
        "m³/h",
    ),
)

CAPABILITY_SENSOR_DESCRIPTIONS = _descriptions(
    _CAPABILITY_SENSORS,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PgaRangehoodConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    entities = []
    for coordinator, did, device in iter_devices(entry):
        limits = device.get("_limits", {})
        entities.extend(
            PgaRangehoodSensor(coordinator, did, device, desc)
            for desc in SENSOR_DESCRIPTIONS
        )
        if CAP_FILTER_VALUE in limits:
            entities.append(PgaRangehoodFilterCountdown(coordinator, did, device))
        if CAP_FILTER2_VALUE in limits:
            entities.append(
                PgaRangehoodSecondaryFilterCountdown(coordinator, did, device)
            )
        entities.extend(
            PgaRangehoodSensor(coordinator, did, device, desc)
            for desc in CAPABILITY_SENSOR_DESCRIPTIONS
            if desc.key in limits
        )
        if CAP_TIMER_ENABLE in limits:
            entities.append(PgaRangehoodTimerOffTime(coordinator, did, device))
    async_add_entities(entities)


class PgaRangehoodSensor(PgaEntity, SensorEntity):
    """Generic diagnostic sensor for a rangehood."""

    def __init__(
        self,
        coordinator: PgaRangehoodCoordinator,
        device_id: str,
        device: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor described by *description*."""
        # One class covers every description, so the unique-id suffix comes from
        # the description and must be set before the base class builds the id.
        self._unique_suffix = description.key
        super().__init__(coordinator, device_id, device)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return the raw device value for the described key."""
        return self._get_device_state().get(self.entity_description.key)


class PgaRangehoodFilterCountdown(PgaEntity, SensorEntity):
    """Filter clean countdown displayed in hours (API returns seconds)."""

    _attr_translation_key = "filter_clean_countdown"
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:air-filter"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    _cap_filter_value = CAP_FILTER_VALUE
    _unique_suffix = CAP_FILTER_VALUE

    @property
    def native_value(self) -> float | None:
        """Return the remaining filter life in hours."""
        value = self._get_float(self._cap_filter_value)
        return None if value is None else round(value / 3600, 1)


class PgaRangehoodSecondaryFilterCountdown(PgaRangehoodFilterCountdown):
    """Secondary filter clean countdown displayed in hours."""

    _attr_translation_key = "secondary_filter_clean_countdown"

    _cap_filter_value = CAP_FILTER2_VALUE
    _unique_suffix = CAP_FILTER2_VALUE


class PgaRangehoodTimerOffTime(PgaEntity, SensorEntity):
    """Turn-off time for the countdown timer (timestamp for live countdown)."""

    _attr_translation_key = "timer_off_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    _unique_suffix = "timer_off"

    @property
    def native_value(self) -> datetime | None:
        """Return the moment the timer will turn the device off."""
        remaining = self._get_float(CAP_TIMER_VALUE)
        if self._get_bool(CAP_TIMER_ACTIVE) and remaining is not None:
            return datetime.now(UTC) + timedelta(seconds=remaining)
        return None
