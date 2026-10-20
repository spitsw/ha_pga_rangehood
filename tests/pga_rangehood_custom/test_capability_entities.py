"""Tests for capability-driven entities: fan range, colour mode, airflow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.light.const import ColorMode
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

from custom_components.pga_rangehood_custom.api import (
    CAP_CLEAN_AIR_ENABLED,
    CAP_FAN_FLOW,
    CAP_FAN_SPEED,
    CAP_LIGHT_BRIGHTNESS,
    CAP_LIGHT_COLOR_TEMP,
    CAP_LIGHT_ONOFF,
    CAP_LIGHT_POWER,
)
from custom_components.pga_rangehood_custom.fan import SiriusRangehoodFan
from custom_components.pga_rangehood_custom.fan import (
    async_setup_entry as setup_fans,
)
from custom_components.pga_rangehood_custom.light import SiriusRangehoodLight
from custom_components.pga_rangehood_custom.sensor import (
    CAPABILITY_SENSOR_DESCRIPTIONS,
    SiriusRangehoodSensor,
)
from custom_components.pga_rangehood_custom.sensor import (
    async_setup_entry as setup_sensors,
)
from custom_components.pga_rangehood_custom.switch import SiriusRangehoodCleanAirSwitch
from custom_components.pga_rangehood_custom.switch import (
    async_setup_entry as setup_switches,
)


def _coordinator(state: dict | None = None) -> MagicMock:
    """Return a coordinator stub with one device's state."""
    coordinator = MagicMock()
    coordinator.data = {"dev1": state or {}}
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


def _capability_description(key: str):
    """Return the read-only capability sensor description for a key."""
    return next(d for d in CAPABILITY_SENSOR_DESCRIPTIONS if d.key == key)


class TestFanRange:
    """The fan derives its speed range and mapping from device limits."""

    def test_speed_count_from_limits(self) -> None:
        """speed_count follows the advertised maximum speed."""
        limits = {CAP_FAN_SPEED: {"min": 0.0, "max": 3.0}}
        fan = SiriusRangehoodFan(_coordinator(), "dev1", _device(limits=limits))
        assert fan.speed_count == 3
        assert round(3 * 100 / fan.speed_count) == 100

    def test_speed_count_defaults_without_limits(self) -> None:
        """Without bounds the fan falls back to the boost speed."""
        fan = SiriusRangehoodFan(_coordinator(), "dev1", _device())
        assert fan.speed_count == 4

    def test_speed_count_guards_zero_max(self) -> None:
        """A malformed zero maximum falls back to the boost speed."""
        limits = {CAP_FAN_SPEED: {"min": 0.0, "max": 0.0}}
        fan = SiriusRangehoodFan(_coordinator(), "dev1", _device(limits=limits))
        assert fan.speed_count == 4

    async def test_set_percentage_scales_to_range(self) -> None:
        """A percentage is scaled to the device's own speed range."""
        limits = {CAP_FAN_SPEED: {"min": 0.0, "max": 4.0}}
        coordinator = _coordinator()
        fan = SiriusRangehoodFan(coordinator, "dev1", _device(limits=limits))
        await fan.async_set_percentage(50)
        coordinator.async_send_command.assert_awaited_once_with(
            "dev1", [{"id": CAP_FAN_SPEED, "value": 2}]
        )

    async def test_fan_created_only_with_capability(self, hass) -> None:
        """No fan entity when the device does not advertise fanSpeed."""
        add = MagicMock()
        await setup_fans(hass, _entry([_device()], _coordinator()), add)
        assert add.call_args[0][0] == []

        add = MagicMock()
        limits = {CAP_FAN_SPEED: {"min": 0.0, "max": 4.0}}
        await setup_fans(hass, _entry([_device(limits=limits)], _coordinator()), add)
        assert [type(e) for e in add.call_args[0][0]] == [SiriusRangehoodFan]


class TestLightColourMode:
    """The light picks its colour mode and range from device limits."""

    def test_colour_temp_range_from_limits(self) -> None:
        """Colour-temperature bounds come from the device metadata."""
        limits = {
            CAP_LIGHT_ONOFF: {"min": 0.0, "max": 1.0},
            CAP_LIGHT_COLOR_TEMP: {"min": 2200.0, "max": 5000.0},
        }
        light = SiriusRangehoodLight(_coordinator(), "dev1", _device(limits=limits))
        assert light.supported_color_modes == {ColorMode.COLOR_TEMP}
        assert light.min_color_temp_kelvin == 2200
        assert light.max_color_temp_kelvin == 5000

    def test_brightness_bounds_from_limits(self) -> None:
        """Brightness is normalized against the device's own range."""
        limits = {
            CAP_LIGHT_ONOFF: {},
            CAP_LIGHT_BRIGHTNESS: {"min": 20.0, "max": 80.0},
        }
        device = _device(limits=limits)
        low = SiriusRangehoodLight(
            _coordinator({CAP_LIGHT_BRIGHTNESS: 20}), "dev1", device
        )
        mid = SiriusRangehoodLight(
            _coordinator({CAP_LIGHT_BRIGHTNESS: 50}), "dev1", device
        )
        assert low.brightness == 0
        assert mid.brightness == 128

    async def test_turn_on_always_includes_onoff(self) -> None:
        """Setting brightness also turns the light on."""
        limits = {
            CAP_LIGHT_ONOFF: {},
            CAP_LIGHT_BRIGHTNESS: {"min": 10.0, "max": 100.0},
        }
        coordinator = _coordinator()
        light = SiriusRangehoodLight(coordinator, "dev1", _device(limits=limits))

        await light.async_turn_on(brightness=128)

        params = coordinator.async_send_command.call_args.args[1]
        assert {"id": CAP_LIGHT_ONOFF, "value": 1.0} in params

    def test_brightness_only_mode(self) -> None:
        """A light without colour temperature is a plain dimmer."""
        limits = {CAP_LIGHT_ONOFF: {}, CAP_LIGHT_BRIGHTNESS: {}}
        light = SiriusRangehoodLight(_coordinator(), "dev1", _device(limits=limits))
        assert light.supported_color_modes == {ColorMode.BRIGHTNESS}

    def test_onoff_only_mode(self) -> None:
        """A light with no colour capabilities is on/off only."""
        limits = {CAP_LIGHT_ONOFF: {}}
        light = SiriusRangehoodLight(_coordinator(), "dev1", _device(limits=limits))
        assert light.supported_color_modes == {ColorMode.ONOFF}


class TestCleanAirSwitch:
    """The air-clean switch is gated and writes the capability."""

    async def test_writes_capability(self) -> None:
        """Turning on writes 1 to device.cleanAirEnabled."""
        coordinator = _coordinator({CAP_CLEAN_AIR_ENABLED: 0})
        switch = SiriusRangehoodCleanAirSwitch(coordinator, "dev1", _device())
        await switch.async_turn_on()
        coordinator.async_send_command.assert_awaited_once_with(
            "dev1", [{"id": CAP_CLEAN_AIR_ENABLED, "value": 1.0}]
        )

    def test_reads_state(self) -> None:
        """is_on reflects the capability value."""
        switch = SiriusRangehoodCleanAirSwitch(
            _coordinator({CAP_CLEAN_AIR_ENABLED: 1}), "dev1", _device()
        )
        assert switch.is_on is True

    async def test_gated_by_capability(self, hass) -> None:
        """The switch appears only when the capability is advertised."""
        add = MagicMock()
        await setup_switches(hass, _entry([_device()], _coordinator()), add)
        assert add.call_args[0][0] == []

        add = MagicMock()
        limits = {CAP_CLEAN_AIR_ENABLED: {"min": 0.0, "max": 1.0}}
        await setup_switches(
            hass, _entry([_device(limits=limits)], _coordinator()), add
        )
        assert [type(e) for e in add.call_args[0][0]] == [SiriusRangehoodCleanAirSwitch]


class TestAirflowSensor:
    """The airflow sensor is a measurement gated by capability."""

    def test_reads_value_and_state_class(self) -> None:
        """device.fanFlow is reported as a measurement in m³/h."""
        sensor = SiriusRangehoodSensor(
            _coordinator({CAP_FAN_FLOW: 320}),
            "dev1",
            _device(),
            _capability_description(CAP_FAN_FLOW),
        )
        assert sensor.native_value == 320
        assert sensor.entity_description.state_class is SensorStateClass.MEASUREMENT
        assert sensor.entity_description.native_unit_of_measurement == "m³/h"

    async def test_gated_by_capability(self, hass) -> None:
        """The airflow sensor appears only when the capability is advertised."""
        add = MagicMock()
        await setup_sensors(hass, _entry([_device()], _coordinator()), add)
        keys = [e.entity_description.key for e in add.call_args[0][0]]
        assert CAP_FAN_FLOW not in keys

        add = MagicMock()
        limits = {CAP_FAN_FLOW: {"min": 0.0, "max": 1000.0}}
        await setup_sensors(hass, _entry([_device(limits=limits)], _coordinator()), add)
        keys = [e.entity_description.key for e in add.call_args[0][0]]
        assert CAP_FAN_FLOW in keys


class TestPowerSensorStatistics:
    """Power sensors feed long-term statistics."""

    def test_power_state_class(self) -> None:
        """A power sensor is a MEASUREMENT in Watts."""
        desc = _capability_description(CAP_LIGHT_POWER)
        assert desc.state_class is SensorStateClass.MEASUREMENT
        assert desc.device_class is SensorDeviceClass.POWER
