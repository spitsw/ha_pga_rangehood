# Copyright (c) 2026 Warren Spits
"""Integration setup for PGA rangehoods."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .api import SIRIUS_MQTT_TENANT, PgaAuthError, PgaHub, PgaMQTT
from .const import (
    CONF_ENDPOINT,
    CONF_INSECURE_TLS,
    CONF_MQTT_TENANT,
    CONF_MQTTS_ENDPOINT,
    DOMAIN,
)
from .coordinator import PgaRangehoodCoordinator
from .data import PgaRangehoodData
from .entity import device_key

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

    from .data import PgaRangehoodConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.FAN,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.TEXT,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PgaRangehoodConfigEntry,
) -> bool:
    """Set up a PGA rangehood integration from a config entry."""
    endpoint = entry.data[CONF_ENDPOINT]
    mqtts_endpoint = entry.data[CONF_MQTTS_ENDPOINT]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    insecure_tls = entry.data.get(CONF_INSECURE_TLS, False)
    tenant = entry.data.get(CONF_MQTT_TENANT, SIRIUS_MQTT_TENANT)

    session = async_get_clientsession(hass, verify_ssl=not insecure_tls)
    hub = PgaHub(session, endpoint, username, password)

    # Auth token persistence
    store = Store[dict[str, Any]](hass, 1, f"{DOMAIN}_auth_{entry.entry_id}")
    hub.attach_store(store)
    stored = await store.async_load()
    if stored:
        hub.restore_token(stored.get("token"), stored.get("expiry"))

    # Discover devices: gets static properties + initial capability values
    devices = await _async_discover_devices(hub)

    # Shared device state: uid (str) -> flattened state dict. These are the
    # same dicts held in `devices`, so a rename or MQTT merge stays in sync.
    device_states: dict[str, dict[str, Any]] = {}
    for device in devices:
        device_states[device_key(device)] = device

    # Coordinator owns the authoritative state and the getStatus heartbeat.
    coordinator = PgaRangehoodCoordinator(hass, entry, hub, device_states)

    # MQTT: aiomqtt drives the socket on the HA event loop, so its callbacks
    # fire on the loop directly — no background thread or thread bridge.
    mqtt = PgaMQTT(
        hass,
        mqtts_endpoint,
        username,
        password,
        coordinator.apply_mqtt_update,
        connection_callback=coordinator.set_mqtt_connected,
        auth_callback=coordinator.request_reauth,
        identifier=entry.entry_id,
        tenant=tenant,
    )
    coordinator.attach_mqtt(mqtt)
    for device in devices:
        mqtt.subscribe_device(device_key(device))
    mqtt_connected = await mqtt.async_start()
    coordinator.set_mqtt_connected(mqtt_connected)

    try:
        # Initial refresh sends getStatus to bootstrap live state via MQTT
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.exception("Initial refresh failed, cleaning up")
        await mqtt.async_stop()
        msg = f"Initial refresh failed: {err}"
        raise ConfigEntryNotReady(msg) from err

    _LOGGER.info(
        "Rangehood setup complete: %d device(s), %s",
        len(devices),
        "MQTT connected" if mqtt_connected else "MQTT offline",
    )

    await _async_start_token_refresh(hass, entry, hub)

    entry.runtime_data = PgaRangehoodData(
        hub=hub,
        mqtt=mqtt,
        coordinator=coordinator,
        devices=devices,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_discover_devices(hub: PgaHub) -> list[dict[str, Any]]:
    """Discover devices, mapping failures to config-entry setup exceptions."""
    try:
        devices = await hub.async_discover_devices()
    except PgaAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except Exception as err:
        msg = f"Device discovery failed: {err}"
        raise ConfigEntryNotReady(msg) from err
    if not devices:
        msg = "No devices discovered"
        raise ConfigEntryNotReady(msg)
    return devices


async def _async_start_token_refresh(
    hass: HomeAssistant,
    entry: PgaRangehoodConfigEntry,
    hub: PgaHub,
) -> None:
    """
    Keep the auth token fresh, rescheduling with a single timer.

    One cancel handle is reused across reschedules (instead of registering a
    new ``async_on_unload`` callback per refresh), so a long-running entry does
    not accumulate unload callbacks.
    """
    cancel: CALLBACK_TYPE | None = None

    async def _refresh(now: datetime | None = None) -> None:  # noqa: ARG001
        """Refresh the token and schedule the next attempt."""
        nonlocal cancel
        try:
            await hub.async_ensure_token()
        except Exception:
            _LOGGER.exception("Failed to refresh auth token")
        if cancel is not None:
            cancel()
            cancel = None
        expiry = hub.token_expiry
        if expiry is None:
            return
        remaining = (expiry - datetime.now(UTC)).total_seconds() - 60
        if remaining > 0:
            cancel = async_call_later(hass, remaining, _refresh)

    def _cancel() -> None:
        if cancel is not None:
            cancel()

    entry.async_on_unload(_cancel)
    await _refresh()


async def async_unload_entry(
    hass: HomeAssistant,
    entry: PgaRangehoodConfigEntry,
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = entry.runtime_data
    if unloaded and data:
        await data.mqtt.async_stop()
        await data.coordinator.async_shutdown()

    return unloaded
