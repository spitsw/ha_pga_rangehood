"""Tests for the secondary (filter2 / light2) entities and their gating."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.sensor import SensorDeviceClass

from custom_components.pga_rangehood_custom.api import (
    CAP_FAN_POWER,
    CAP_FILTER2_VALUE,
    CAP_FILTER2_WORN,
    CAP_FILTER_VALUE,
    CAP_FILTER_WORN,
    CAP_HOOD_POWER,
    CAP_LIGHT2_BRIGHTNESS,
    CAP_LIGHT2_COLOR_TEMP,
    CAP_LIGHT2_ONOFF,
    CAP_LIGHT2_POWER,
    CAP_LIGHT_ONOFF,
    CAP_LIGHT_POWER,
)
from custom_components.pga_rangehood_custom.binary_sensor import (
    SiriusRangehoodSecondaryFilterWorn,
)
from custom_components.pga_rangehood_custom.binary_sensor import (
    async_setup_entry as setup_binary_sensors,
)
from custom_components.pga_rangehood_custom.light import (
    SiriusRangehoodLight,
    SiriusRangehoodSecondaryLight,
)
from custom_components.pga_rangehood_custom.light import (
    async_setup_entry as setup_lights,
)
from custom_components.pga_rangehood_custom.sensor import (
    CAPABILITY_SENSOR_DESCRIPTIONS,
    SiriusRangehoodFilterCountdown,
    SiriusRangehoodSecondaryFilterCountdown,
    SiriusRangehoodSensor,
)
from custom_components.pga_rangehood_custom.sensor import (
    async_setup_entry as setup_sensors,
)


def _coordinator(state: dict) -> MagicMock:
    """Return a coordinator stub with one device's state."""
    coordinator = MagicMock()
    coordinator.data = {"dev1": state}
    coordinator.async_send_command = AsyncMock(return_value=True)
    return coordinator


def _device(*, limits: dict | None = None) -> dict:
    """Return a minimal discovered-device dict."""
    device = {"id": 1, "uid": "dev1", "name": "Test", "description": "Test"}
    device["_limits"] = limits if limits is not None else {}
    return device


def _entry(devices: list[dict], coordinator: MagicMock) -> MagicMock:
    """Return a config-entry stub exposing runtime_data."""
    entry = MagicMock()
    entry.runtime_data.devices = devices
    entry.runtime_data.coordinator = coordinator
    return entry


class TestSecondaryLight:
    """Verify the secondary light reads and writes the light2 capabilities."""

    def test_reads_light2_state(self) -> None:
        """State is read from the light2 capability ids."""
        state = {
            CAP_LIGHT2_ONOFF: 1,
            CAP_LIGHT2_BRIGHTNESS: 50,
            CAP_LIGHT2_COLOR_TEMP: 4000,
        }
        entity = SiriusRangehoodSecondaryLight(_coordinator(state), "dev1", _device())
        assert entity.is_on is True
        assert entity.color_temp_kelvin == 4000
        assert entity.brightness == 113  # (50 - 10) / (100 - 10) * 255

    async def test_turn_on_sends_light2_onoff(self) -> None:
        """A bare turn_on sends the light2 onOff capability."""
        coordinator = _coordinator({})
        entity = SiriusRangehoodSecondaryLight(coordinator, "dev1", _device())
        await entity.async_turn_on()
        coordinator.async_send_command.assert_awaited_once_with(
            "dev1", [{"id": CAP_LIGHT2_ONOFF, "value": 1.0}]
        )

    async def test_turn_off_sends_light2_off(self) -> None:
        """turn_off sends the light2 onOff capability as 0."""
        coordinator = _coordinator({})
        entity = SiriusRangehoodSecondaryLight(coordinator, "dev1", _device())
        await entity.async_turn_off()
        coordinator.async_send_command.assert_awaited_once_with(
            "dev1", [{"id": CAP_LIGHT2_ONOFF, "value": 0.0}]
        )


class TestSecondaryFilterWorn:
    """Verify the secondary filter-worn binary sensor reads filter2.worn."""

    def test_reads_filter2_worn(self) -> None:
        """The worn flag comes from device.filter2.worn."""
        entity = SiriusRangehoodSecondaryFilterWorn(
            _coordinator({CAP_FILTER2_WORN: 1}), "dev1", _device()
        )
        assert entity.is_on is True

    def test_unknown_when_absent(self) -> None:
        """No value yields None rather than a false positive."""
        entity = SiriusRangehoodSecondaryFilterWorn(_coordinator({}), "dev1", _device())
        assert entity.is_on is None


class TestSecondaryFilterCountdown:
    """Verify the secondary filter countdown reads filter2Value as hours."""

    def test_seconds_to_hours(self) -> None:
        """device.filter2Value (seconds) is reported in hours."""
        entity = SiriusRangehoodSecondaryFilterCountdown(
            _coordinator({CAP_FILTER2_VALUE: 7200}), "dev1", _device()
        )
        assert entity.native_value == 2.0


class TestGating:
    """Verify secondary entities are created only when advertised."""

    async def test_light_created_when_capability_present(self, hass) -> None:
        """The secondary light appears when device.light2OnOff is advertised."""
        limits = {
            CAP_LIGHT_ONOFF: {"min": 0.0, "max": 1.0},
            CAP_LIGHT2_ONOFF: {"min": 0.0, "max": 1.0},
        }
        add = MagicMock()
        await setup_lights(
            hass, _entry([_device(limits=limits)], _coordinator({})), add
        )
        types = [type(e) for e in add.call_args[0][0]]
        assert SiriusRangehoodSecondaryLight in types
        assert SiriusRangehoodLight in types

    async def test_light_absent_without_capability(self, hass) -> None:
        """No secondary light when the capability is not advertised."""
        add = MagicMock()
        await setup_lights(hass, _entry([_device()], _coordinator({})), add)
        types = [type(e) for e in add.call_args[0][0]]
        assert SiriusRangehoodSecondaryLight not in types

    async def test_filter_entities_created_when_present(self, hass) -> None:
        """Both secondary filter entities appear when advertised."""
        coordinator = _coordinator({})
        limits = {
            CAP_FILTER_WORN: {"min": 0.0, "max": 1.0},
            CAP_FILTER_VALUE: {"min": 0.0, "max": 360000.0},
            CAP_FILTER2_WORN: {"min": 0.0, "max": 1.0},
            CAP_FILTER2_VALUE: {"min": 0.0, "max": 360000.0},
        }
        entry = _entry([_device(limits=limits)], coordinator)

        binary_add = MagicMock()
        await setup_binary_sensors(hass, entry, binary_add)
        assert SiriusRangehoodSecondaryFilterWorn in [
            type(e) for e in binary_add.call_args[0][0]
        ]

        sensor_add = MagicMock()
        await setup_sensors(hass, entry, sensor_add)
        sensor_types = [type(e) for e in sensor_add.call_args[0][0]]
        assert SiriusRangehoodSecondaryFilterCountdown in sensor_types
        assert SiriusRangehoodFilterCountdown in sensor_types

    async def test_filter_absent_without_capabilities(self, hass) -> None:
        """Neither secondary filter entity appears when not advertised."""
        entry = _entry([_device()], _coordinator({}))

        binary_add = MagicMock()
        await setup_binary_sensors(hass, entry, binary_add)
        assert SiriusRangehoodSecondaryFilterWorn not in [
            type(e) for e in binary_add.call_args[0][0]
        ]

        sensor_add = MagicMock()
        await setup_sensors(hass, entry, sensor_add)
        assert SiriusRangehoodSecondaryFilterCountdown not in [
            type(e) for e in sensor_add.call_args[0][0]
        ]


def _power_description(key: str):
    """Return the power sensor description for a capability key."""
    return next(d for d in CAPABILITY_SENSOR_DESCRIPTIONS if d.key == key)


class TestPowerSensors:
    """Verify the read-only light power-draw sensors."""

    def test_light_power_reads_watts(self) -> None:
        """device.lightPower is reported in Watts."""
        entity = SiriusRangehoodSensor(
            _coordinator({CAP_LIGHT_POWER: 12.5}),
            "dev1",
            _device(),
            _power_description(CAP_LIGHT_POWER),
        )
        assert entity.native_value == 12.5
        assert entity.entity_description.native_unit_of_measurement == "W"
        assert entity.entity_description.device_class is SensorDeviceClass.POWER

    def test_unique_id_comes_from_the_description(self) -> None:
        """One sensor class gives each description its own unique id."""
        entity = SiriusRangehoodSensor(
            _coordinator({}),
            "dev1",
            _device(),
            _power_description(CAP_FAN_POWER),
        )
        assert entity.unique_id == f"dev1_{CAP_FAN_POWER}"

    def test_secondary_light_power_reads_watts(self) -> None:
        """device.light2Power is reported in Watts."""
        entity = SiriusRangehoodSensor(
            _coordinator({CAP_LIGHT2_POWER: 8}),
            "dev1",
            _device(),
            _power_description(CAP_LIGHT2_POWER),
        )
        assert entity.native_value == 8

    def test_fan_and_hood_power_read_watts(self) -> None:
        """device.fanPower and device.hoodPower are reported in Watts."""
        fan = SiriusRangehoodSensor(
            _coordinator({CAP_FAN_POWER: 45}),
            "dev1",
            _device(),
            _power_description(CAP_FAN_POWER),
        )
        hood = SiriusRangehoodSensor(
            _coordinator({CAP_HOOD_POWER: 120}),
            "dev1",
            _device(),
            _power_description(CAP_HOOD_POWER),
        )
        assert fan.native_value == 45
        assert hood.native_value == 120
        assert fan.entity_description.device_class is SensorDeviceClass.POWER

    async def test_power_sensors_created_when_present(self, hass) -> None:
        """A power sensor appears only for the capabilities advertised."""
        limits = {
            CAP_LIGHT_POWER: {"min": 0.0, "max": 100.0},
            CAP_LIGHT2_POWER: {"min": 0.0, "max": 100.0},
            CAP_FAN_POWER: {"min": 0.0, "max": 500.0},
            CAP_HOOD_POWER: {"min": 0.0, "max": 500.0},
        }
        add = MagicMock()
        await setup_sensors(
            hass, _entry([_device(limits=limits)], _coordinator({})), add
        )
        keys = [
            e.entity_description.key
            for e in add.call_args[0][0]
            if isinstance(e, SiriusRangehoodSensor)
        ]
        assert CAP_LIGHT_POWER in keys
        assert CAP_LIGHT2_POWER in keys
        assert CAP_FAN_POWER in keys
        assert CAP_HOOD_POWER in keys

    async def test_power_sensors_absent_without_capability(self, hass) -> None:
        """No power sensors when the capabilities are not advertised."""
        add = MagicMock()
        await setup_sensors(hass, _entry([_device()], _coordinator({})), add)
        keys = [
            e.entity_description.key
            for e in add.call_args[0][0]
            if isinstance(e, SiriusRangehoodSensor)
        ]
        assert CAP_LIGHT_POWER not in keys
        assert CAP_LIGHT2_POWER not in keys
        assert CAP_FAN_POWER not in keys
        assert CAP_HOOD_POWER not in keys
