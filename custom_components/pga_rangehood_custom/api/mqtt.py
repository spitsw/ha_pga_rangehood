# Copyright (c) 2026 Warren Spits
"""MQTTS client for receiving real-time status from rangehood devices."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import ssl
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import aiomqtt

from .const import SIRIUS_MQTT_TENANT

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

StatusCallback = Callable[[str, dict[str, Any]], None]  # device_id, payload
ConnectionCallback = Callable[[bool], None]  # connected
AuthCallback = Callable[[], None]  # broker rejected the credentials

_TOPIC_ERRORS = (ValueError, IndexError)
_JSON_ERRORS = (json.JSONDecodeError, UnicodeDecodeError)

_RECONNECT_MIN_DELAY = 1.0
_RECONNECT_MAX_DELAY = 120.0
_CONNECT_TIMEOUT = 10.0
_MAX_QUEUED_MESSAGES = 256

# MQTT CONNACK return codes that mean the broker rejected the credentials.
_AUTH_ERROR_CODES = (4, 5)

# Seconds to wait for a command acknowledgement on the response topic. A
# timeout is inconclusive, not a failure: the device may simply be slow.
RESPONSE_TIMEOUT = 5.0

# OpenSSL X509_V_FLAG_NO_CHECK_TIME (not exposed by Python's `ssl`). It disables
# certificate time checks while still validating the chain and hostname.
_X509_V_FLAG_NO_CHECK_TIME = 0x200000

# The broker's chain ends at DigiCert's legacy "DigiCert Global Root CA", which
# current certifi (2026.x) and some OS trust stores no longer ship, so it is
# bundled to keep the chain verifiable everywhere.
_BROKER_ROOT_CA = Path(__file__).with_name("digicert_global_root_ca.pem")


def _build_tls_context() -> ssl.SSLContext:
    """
    Build the MQTT TLS context.

    Reads CA material from disk, so this must run in an executor rather than on
    the event loop. The broker's chain and hostname are verified against the
    system trust store plus the bundled broker root, but its expired leaf is
    tolerated by disabling OpenSSL's time checks (see ADR-1).
    """
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=str(_BROKER_ROOT_CA))
    context.verify_flags |= _X509_V_FLAG_NO_CHECK_TIME
    return context


class SiriusMQTT:
    """
    Manages an MQTTS connection to the rangehood cloud broker.

    The broker belongs to the provider's cloud; the client subscribes to
    per-device status topics. aiomqtt drives paho-mqtt's socket on the Home
    Assistant event loop (no background thread), so the callbacks fire on the
    loop directly.
    """

    _DEFAULT_PORT = 8884
    _KEEPALIVE = 60

    def __init__(  # noqa: PLR0913
        self,
        hass: HomeAssistant,
        mqtts_endpoint: str,
        username: str,
        password: str,
        status_callback: StatusCallback | None = None,
        *,
        connection_callback: ConnectionCallback | None = None,
        auth_callback: AuthCallback | None = None,
        identifier: str | None = None,
        tenant: str = SIRIUS_MQTT_TENANT,
    ) -> None:
        """Parse the broker endpoint and store connection details."""
        self._hass = hass
        self._username = username
        self._password = password
        self._status_callback = status_callback
        self._connection_callback = connection_callback
        self._auth_callback = auth_callback
        self._identifier = identifier
        self._tenant = tenant

        parsed = urlparse(mqtts_endpoint)
        self._host = parsed.hostname or "localhost"
        self._port = parsed.port or self._DEFAULT_PORT

        # Built in async_start() via an executor: create_default_context()
        # reads the system CA paths and must not block the event loop.
        self._tls_context: ssl.SSLContext | None = None

        self._subscribed_devices: set[str] = set()
        self._pending_responses: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._task: asyncio.Task[None] | None = None
        self._connected = False
        self._connected_event: asyncio.Event | None = None

    @property
    def connected(self) -> bool:
        """Return True when the client is connected to the broker."""
        return self._connected

    @property
    def host(self) -> str:
        """Return the broker host."""
        return self._host

    def _new_client(self) -> aiomqtt.Client:
        """Build an aiomqtt client. Must run on the event loop (aiomqtt needs one)."""
        context = self._tls_context
        if context is None:
            msg = "async_start() must be awaited before the MQTT client is built"
            raise RuntimeError(msg)
        return aiomqtt.Client(
            hostname=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            tls_context=context,
            keepalive=self._KEEPALIVE,
            identifier=self._identifier,
            protocol=aiomqtt.ProtocolVersion.V311,
            max_queued_incoming_messages=_MAX_QUEUED_MESSAGES,
        )

    async def async_start(self) -> bool:
        """Start consuming messages; return True once initially connected."""
        self._tls_context = await self._hass.async_add_executor_job(_build_tls_context)
        self._connected_event = asyncio.Event()
        self._task = self._hass.async_create_background_task(
            self._run(), f"Rangehood MQTT ({self._host})"
        )
        try:
            await asyncio.wait_for(self._connected_event.wait(), _CONNECT_TIMEOUT)
        except TimeoutError:
            _LOGGER.warning(
                "MQTT broker %s did not connect within %ss",
                self._host,
                _CONNECT_TIMEOUT,
            )
            return False
        return True

    async def async_stop(self) -> None:
        """Stop consuming and disconnect."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._set_connected(connected=False)

    def subscribe_device(self, device_id: str) -> None:
        """Register a device to subscribe to (applied on each connect)."""
        self._subscribed_devices.add(device_id)

    async def _run(self) -> None:
        """Maintain the connection, reconnecting with exponential backoff."""
        client = self._new_client()
        delay = _RECONNECT_MIN_DELAY
        while True:
            try:
                async with client:
                    self._set_connected(connected=True)
                    delay = _RECONNECT_MIN_DELAY
                    for device_id in self._subscribed_devices:
                        await client.subscribe(self._status_topic(device_id), qos=1)
                        await client.subscribe(self._response_topic(device_id), qos=1)
                        _LOGGER.debug(
                            "Subscribed to MQTT status and response for %s", device_id
                        )
                    async for message in client.messages:
                        self._handle_message(message)
            except aiomqtt.MqttError as err:
                self._set_connected(connected=False)
                if (
                    isinstance(err, aiomqtt.MqttCodeError)
                    and err.rc in _AUTH_ERROR_CODES
                ):
                    _LOGGER.warning(
                        "MQTT broker %s rejected the credentials (%s); reauth needed",
                        self._host,
                        err,
                    )
                    if self._auth_callback is not None:
                        self._auth_callback()
                    return
                _LOGGER.warning(
                    "MQTT connection to %s lost (%s); retrying in %.0fs",
                    self._host,
                    err,
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, _RECONNECT_MAX_DELAY)

    def _set_connected(self, *, connected: bool) -> None:
        """Record connectivity and notify the listener (HA event loop only)."""
        if connected == self._connected:
            return
        self._connected = connected
        if connected and self._connected_event is not None:
            self._connected_event.set()
        if self._connection_callback:
            self._connection_callback(connected)

    def _handle_message(self, message: aiomqtt.Message) -> None:
        """Route a message: responses resolve waiters, status updates forward."""
        if message.retain:
            return
        topic = message.topic.value
        try:
            raw = json.loads(message.payload.decode("utf-8"))
        except _JSON_ERRORS as err:
            _LOGGER.warning("Invalid MQTT payload on %s: %s", topic, err)
            return

        payload = raw if isinstance(raw, dict) else {}

        if "/response/" in topic:
            self._handle_response(topic, payload)
            return

        values_list = payload.pop("values", [])

        # The device ID is always the path segment after "devices" in the
        # topic (root/{tenant}/devices/{device_id}/status).
        parts = topic.split("/")
        try:
            device_id = parts[parts.index("devices") + 1]
        except _TOPIC_ERRORS:
            _LOGGER.debug(
                "MQTT message on %s: could not extract device ID from topic", topic
            )
            return

        flat: dict[str, object] = {}
        for item in values_list:
            if isinstance(item, dict) and "id" in item:
                flat[item["id"]] = item["value"]

        _LOGGER.debug("MQTT status update for %s: %s", device_id, flat)
        if self._status_callback:
            self._status_callback(device_id, flat)

    async def wait_for_response(
        self,
        request_id: str,
        *,
        timeout: float = RESPONSE_TIMEOUT,  # noqa: ASYNC109
    ) -> dict[str, Any] | None:
        """
        Wait for the broker's acknowledgement of *request_id*.

        Returns the parsed response payload, or None when no acknowledgement
        arrived within *timeout* seconds. A timeout is inconclusive, not a
        failure: the device may still be processing the command.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending_responses[request_id] = future
        try:
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            return None
        finally:
            self._pending_responses.pop(request_id, None)

    def _handle_response(self, topic: str, payload: dict[str, Any]) -> None:
        """Resolve a pending command waiter from a response-topic message."""
        request_id = topic.rsplit("/", 1)[1]
        future = self._pending_responses.pop(request_id, None)
        if future is None or future.done():
            _LOGGER.debug(
                "Unmatched MQTT response on %s (no pending request): %s",
                topic,
                payload,
            )
            return
        _LOGGER.debug("MQTT response for request %s: %s", request_id, payload)
        future.set_result(payload)

    def _status_topic(self, device_id: str) -> str:
        """Return the status topic for a device, scoped to the provider tenant."""
        return f"root/{self._tenant}/devices/{device_id}/status"

    def _response_topic(self, device_id: str) -> str:
        """Return the command-acknowledgement topic wildcard for a device."""
        return f"root/{self._tenant}/devices/{device_id}/response/#"
