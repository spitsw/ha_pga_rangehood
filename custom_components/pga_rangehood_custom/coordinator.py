# Copyright (c) 2026 Warren Spits
"""DataUpdateCoordinator for Sirius Rangehood."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GET_STATUS_INTERVAL,
    WRITABLE_CAPABILITIES,
    SiriusAuthError,
    SiriusHub,
    SiriusMQTT,
)
from .const import CONF_PROVIDER, DOMAIN, PROVIDER_SIRIUS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

_LOGGER = logging.getLogger(__name__)

MQTT_ISSUE_ID = "mqtt_unavailable"


class SiriusRangehoodCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """
    Owns the authoritative per-device state for a Sirius account.

    Both data paths funnel through this coordinator: MQTT push updates via
    :meth:`apply_mqtt_update`, and the periodic HTTP ``getStatus`` heartbeat
    via :meth:`_async_update_data`. It also tracks MQTT broker connectivity so
    entities can go unavailable and a Repairs issue can surface on outage.
    """

    _MQTT_GRACE_PERIOD = timedelta(seconds=30)
    _STATUS_TIMEOUT = 20.0

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hub: SiriusHub,
        device_states: dict[str, dict[str, Any]],
    ) -> None:
        """Initialize the coordinator with the discovered device state."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} devices",
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=GET_STATUS_INTERVAL),
        )
        self._entry = entry
        self._hub = hub
        self._mqtt: SiriusMQTT | None = None
        self.device_states = device_states
        self._fresh = {did: asyncio.Event() for did in device_states}
        self._mqtt_connected = False
        self._mqtt_down_since: datetime | None = None
        self._grace_unsub: CALLBACK_TYPE | None = None
        self._mqtt_repair_raised = False

    @property
    def hub(self) -> SiriusHub:
        """Return the HTTP API client backing this coordinator."""
        return self._hub

    def attach_mqtt(self, mqtt: SiriusMQTT) -> None:
        """Attach the MQTT client used to confirm command acknowledgements."""
        self._mqtt = mqtt

    @property
    def provider(self) -> str:
        """Return the configured provider (sirius / pando / custom)."""
        return self._entry.data.get(CONF_PROVIDER, PROVIDER_SIRIUS)

    @property
    def mqtt_connected(self) -> bool:
        """Return True while the MQTT broker connection is up."""
        return self._mqtt_connected

    @property
    def mqtt_available(self) -> bool:
        """
        Return True when MQTT state is fresh enough to trust.

        A short grace period after a disconnect avoids flapping entities
        unavailable during paho's automatic reconnect.
        """
        if self._mqtt_connected:
            return True
        if self._mqtt_down_since is None:
            return True
        return datetime.now(UTC) - self._mqtt_down_since < self._MQTT_GRACE_PERIOD

    def set_mqtt_connected(self, connected: bool) -> None:  # noqa: FBT001
        """
        Record broker connectivity and refresh consumers.

        aiomqtt runs on the HA event loop, so this is called directly from
        the MQTT task (see ADR-2).
        """
        if self._grace_unsub is not None:
            self._grace_unsub()
            self._grace_unsub = None
        self._mqtt_connected = connected
        if connected:
            self._mqtt_down_since = None
            self._clear_mqtt_repair()
        else:
            self._mqtt_down_since = datetime.now(UTC)
            self._grace_unsub = async_call_later(
                self.hass,
                self._MQTT_GRACE_PERIOD.total_seconds(),
                self._on_mqtt_grace_elapsed,
            )
        self.async_set_updated_data(self._snapshot())

    def _on_mqtt_grace_elapsed(self, _now: datetime) -> None:
        """Raise the outage repair once the grace period has passed."""
        self._grace_unsub = None
        self._raise_mqtt_repair()
        self.async_set_updated_data(self._snapshot())

    def _raise_mqtt_repair(self) -> None:
        if self._mqtt_repair_raised:
            return
        self._mqtt_repair_raised = True
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            MQTT_ISSUE_ID,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=MQTT_ISSUE_ID,
        )

    def _clear_mqtt_repair(self) -> None:
        if not self._mqtt_repair_raised:
            return
        self._mqtt_repair_raised = False
        ir.async_delete_issue(self.hass, DOMAIN, MQTT_ISSUE_ID)

    async def async_shutdown(self) -> None:
        """Cancel pending timers before shutting the coordinator down."""
        if self._grace_unsub is not None:
            self._grace_unsub()
            self._grace_unsub = None
        await super().async_shutdown()

    def request_reauth(self) -> None:
        """Ask Home Assistant to start the re-authentication flow."""
        self._entry.async_start_reauth(self.hass)

    def set_device_name(self, device_id: str, name: str) -> None:
        """Record a renamed device in the state and refresh listeners."""
        if device_id in self.device_states:
            self.device_states[device_id]["name"] = name
            self.async_set_updated_data(self._snapshot())

    def _snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a shallow copy of the device state for listeners."""
        return dict(self.device_states)

    async def async_send_command(
        self, device_id: str, params: list[dict[str, Any]]
    ) -> None:
        """
        Send a setValue command and require the device to acknowledge it.

        Refuses to send while MQTT is down, validates the values against the
        device's own limits and the writable-capability allowlist, and raises
        ``HomeAssistantError`` when the HTTP request is rejected, when no
        acknowledgement arrives, or when the device reports a non-zero status.
        A command is never retried automatically.
        """
        mqtt = self._mqtt
        if not self._mqtt_connected or mqtt is None:
            msg = "Rangehood MQTT connection is unavailable"
            raise HomeAssistantError(msg)
        self._validate_command(device_id, params)

        started = time.monotonic()
        result = await self._hub.async_send_command(device_id, params)
        if not result.accepted:
            msg = f"The rangehood rejected the command for {device_id}"
            raise HomeAssistantError(msg)

        response = await mqtt.wait_for_response(result.request_id)
        if response is None:
            msg = "Timed out waiting for the rangehood acknowledgement; result unknown"
            raise HomeAssistantError(msg)
        if response.get("status") != 0:
            msg = "The rangehood rejected the command"
            raise HomeAssistantError(msg)
        _LOGGER.debug(
            "Command for %s acknowledged in %.2fs: %s",
            device_id,
            time.monotonic() - started,
            response,
        )

    def _validate_command(self, device_id: str, params: list[dict[str, Any]]) -> None:
        """Reject commands targeting a non-writable or out-of-range capability."""
        limits = self.device_states.get(device_id, {}).get("_limits", {})
        for param in params:
            cap = param.get("id")
            bounds = limits.get(cap)
            value = param.get("value")
            if cap not in WRITABLE_CAPABILITIES:
                msg = f"{cap} is not a writable capability"
                raise HomeAssistantError(msg)
            if (
                bounds is None
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
            ):
                msg = f"{cap} cannot be set on this device"
                raise HomeAssistantError(msg)
            if not bounds["min"] <= value <= bounds["max"]:
                msg = f"{value} is outside the supported range for {cap}"
                raise HomeAssistantError(msg)

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Refresh each device's state, waiting for the pushed status."""
        _LOGGER.debug("Coordinator update for %d device(s)", len(self.device_states))
        results = await asyncio.gather(
            *(self._async_refresh_device(did) for did in self.device_states)
        )
        if self.device_states and not any(results):
            msg = "No fresh device state received"
            raise UpdateFailed(msg)
        return self._snapshot()

    async def _async_refresh_device(self, device_id: str) -> bool:
        """Request a getStatus and wait for the fresh status it triggers."""
        fresh = self._fresh[device_id]
        fresh.clear()
        try:
            accepted = await self._hub.async_get_status(device_id)
        except SiriusAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception:
            _LOGGER.exception("getStatus failed for device %s", device_id)
            return False
        if not accepted:
            _LOGGER.debug("getStatus request not accepted for %s", device_id)
            return False
        try:
            await asyncio.wait_for(fresh.wait(), self._STATUS_TIMEOUT)
        except TimeoutError:
            _LOGGER.debug(
                "No fresh status for %s within %.0fs", device_id, self._STATUS_TIMEOUT
            )
            return False
        return True

    def apply_mqtt_update(self, device_id: str, payload: dict[str, Any]) -> None:
        """
        Merge an MQTT status payload and notify listeners.

        aiomqtt runs on the HA event loop, so this is called directly from
        the MQTT task (see ADR-2).
        """
        if device_id in self.device_states:
            _LOGGER.debug("MQTT status for device %s: %s", device_id, payload)
            self.device_states[device_id].update(payload)
            if (fresh := self._fresh.get(device_id)) is not None:
                fresh.set()
            self.async_set_updated_data(self._snapshot())
