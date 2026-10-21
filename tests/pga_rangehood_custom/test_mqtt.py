"""Tests for mqtt.py — aiomqtt message parsing and subscription tracking."""

from __future__ import annotations

import asyncio
import json
import ssl
from types import SimpleNamespace
from unittest.mock import MagicMock

import aiomqtt
import pytest

from custom_components.pga_rangehood_custom.api.mqtt import (
    _BROKER_ROOT_CA,
    _X509_V_FLAG_NO_CHECK_TIME,
    PgaMQTT,
    _build_tls_context,
)


def _make_mqtt(status_callback=None, connection_callback=None):
    """Build a PgaMQTT without connecting."""
    return PgaMQTT(
        MagicMock(),
        "mqtts://broker.example.com:8884",
        "user",
        "pass",
        status_callback,
        connection_callback=connection_callback,
    )


def _message(topic: str, payload: bytes, *, retain: bool = False) -> SimpleNamespace:
    """Build a stand-in for an `aiomqtt.Message`."""
    return SimpleNamespace(
        topic=SimpleNamespace(value=topic), payload=payload, retain=retain
    )


class TestInit:
    """Verify endpoint parsing and defaults."""

    def test_parses_endpoint(self) -> None:
        """Extract host and port from the mqtts:// URL."""
        mqtt = _make_mqtt()
        assert mqtt._host == "broker.example.com"
        assert mqtt._port == 8884

    def test_default_port(self) -> None:
        """Default to port 8884 when the URL omits a port."""
        mqtt = PgaMQTT(MagicMock(), "mqtts://broker.example.com", "user", "pass")
        assert mqtt._port == 8884

    def test_not_connected_initially(self) -> None:
        """The client starts disconnected."""
        assert _make_mqtt().connected is False


class TestSubscribeDevice:
    """Verify devices are tracked for (re)subscription."""

    def test_registers_device(self) -> None:
        """subscribe_device should register the device id."""
        mqtt = _make_mqtt()
        mqtt.subscribe_device("device-1")
        assert "device-1" in mqtt._subscribed_devices

    def test_status_topic(self) -> None:
        """The status topic is scoped to the tenant (Sirius by default)."""
        mqtt = _make_mqtt()
        assert (
            mqtt._status_topic("device-1") == "root/codermine/devices/device-1/status"
        )

    def test_status_topic_uses_custom_tenant(self) -> None:
        """A Pando-style tenant is reflected in the topic."""
        mqtt = PgaMQTT(
            MagicMock(),
            "mqtts://pando.iotpga.it:8883",
            "user",
            "pass",
            tenant="pando",
        )
        assert mqtt._status_topic("device-1") == "root/pando/devices/device-1/status"

    def test_response_topic(self) -> None:
        """The response topic is a per-device wildcard."""
        assert (
            _make_mqtt()._response_topic("device-1")
            == "root/codermine/devices/device-1/response/#"
        )


class TestHandleMessage:
    """Verify status payloads are parsed and forwarded."""

    def test_parses_valid_payload(self) -> None:
        """Flatten `values` and extract the device id from the topic."""
        callback = MagicMock()
        mqtt = _make_mqtt(callback)
        payload = json.dumps(
            {"values": [{"id": "device.fanSpeed", "value": 3}]}
        ).encode()
        mqtt._handle_message(
            _message("root/codermine/devices/device-1/status", payload)
        )
        callback.assert_called_once_with("device-1", {"device.fanSpeed": 3})

    def test_multiple_values(self) -> None:
        """Flatten multiple values."""
        callback = MagicMock()
        mqtt = _make_mqtt(callback)
        payload = json.dumps(
            {
                "values": [
                    {"id": "device.onOff", "value": 1.0},
                    {"id": "device.fanSpeed", "value": 2},
                ]
            }
        ).encode()
        mqtt._handle_message(
            _message("root/codermine/devices/device-1/status", payload)
        )
        callback.assert_called_once_with(
            "device-1", {"device.onOff": 1.0, "device.fanSpeed": 2}
        )

    def test_skips_non_dict_items(self) -> None:
        """Skip values entries that are not dicts or lack an id."""
        callback = MagicMock()
        mqtt = _make_mqtt(callback)
        payload = json.dumps(
            {
                "values": [
                    {"id": "device.onOff", "value": 1.0},
                    "not-a-dict",
                    {"notId": "device.fanSpeed", "value": 3},
                ]
            }
        ).encode()
        mqtt._handle_message(
            _message("root/codermine/devices/device-1/status", payload)
        )
        callback.assert_called_once_with("device-1", {"device.onOff": 1.0})

    def test_invalid_json(self) -> None:
        """Invalid JSON must not raise or call the callback."""
        callback = MagicMock()
        mqtt = _make_mqtt(callback)
        mqtt._handle_message(
            _message("root/codermine/devices/device-1/status", b"not-json")
        )
        callback.assert_not_called()

    def test_missing_device_id_in_topic(self) -> None:
        """No callback when the topic has no `devices/<id>` segment."""
        callback = MagicMock()
        mqtt = _make_mqtt(callback)
        payload = json.dumps({"values": [{"id": "x", "value": 1}]}).encode()
        mqtt._handle_message(_message("root/unknown/status", payload))
        callback.assert_not_called()


class TestConnectionState:
    """Verify connectivity changes reach the connection callback."""

    def test_set_connected_notifies(self) -> None:
        """A connectivity change notifies the callback once."""
        callback = MagicMock()
        mqtt = _make_mqtt(connection_callback=callback)
        mqtt._set_connected(connected=True)
        assert mqtt.connected is True
        callback.assert_called_once_with(True)

    def test_repeated_state_does_not_notify(self) -> None:
        """Re-setting the same state does not re-notify."""
        callback = MagicMock()
        mqtt = _make_mqtt(connection_callback=callback)
        mqtt._set_connected(connected=False)  # already disconnected
        callback.assert_not_called()


class TestTlsContext:
    """Verify the TLS context is built off the event loop and only when needed."""

    def test_build_tolerates_expired_leaf(self) -> None:
        """Verify the chain; skip only the expired leaf's time check."""
        context = _build_tls_context()
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        assert context.verify_flags & _X509_V_FLAG_NO_CHECK_TIME

    def test_init_defers_context_creation(self) -> None:
        """Constructing the client must not read CA paths on the event loop."""
        assert _make_mqtt()._tls_context is None

    def test_new_client_requires_started_context(self) -> None:
        """Building the client before async_start() is a programming error."""
        mqtt = _make_mqtt()
        with pytest.raises(RuntimeError):
            mqtt._new_client()

    def test_broker_root_is_bundled(self) -> None:
        """The broker's legacy root certificate ships beside mqtt.py."""
        assert _BROKER_ROOT_CA.is_file()


class TestWaitForResponse:
    """Verify command acknowledgements are correlated by requestId."""

    async def test_response_resolves_waiter(self) -> None:
        """A matching response topic resolves the pending waiter."""
        mqtt = _make_mqtt()
        task = asyncio.create_task(mqtt.wait_for_response("rid-1"))
        await asyncio.sleep(0)  # let the waiter register
        payload = json.dumps({"timestamp": "2026-09-28T13:43:57", "status": 0})
        mqtt._handle_message(
            _message("root/codermine/devices/device-1/response/rid-1", payload.encode())
        )
        assert await task == {"timestamp": "2026-09-28T13:43:57", "status": 0}

    async def test_timeout_is_inconclusive(self) -> None:
        """No acknowledgement within the timeout returns None and cleans up."""
        mqtt = _make_mqtt()
        result = await mqtt.wait_for_response("rid-2", timeout=0.01)
        assert result is None
        assert "rid-2" not in mqtt._pending_responses

    def test_unmatched_response_is_ignored(self) -> None:
        """A response with no pending waiter must not raise."""
        mqtt = _make_mqtt()
        mqtt._handle_message(
            _message(
                "root/codermine/devices/device-1/response/unknown",
                b'{"status": 0}',
            )
        )
        assert mqtt._pending_responses == {}

    def test_retained_message_is_ignored(self) -> None:
        """A retained status message is not treated as live state."""
        callback = MagicMock()
        mqtt = _make_mqtt(callback)
        payload = json.dumps(
            {"values": [{"id": "device.fanSpeed", "value": 3}]}
        ).encode()
        mqtt._handle_message(
            _message("root/codermine/devices/device-1/status", payload, retain=True)
        )
        callback.assert_not_called()


class TestClientOptions:
    """Verify the MQTT client is built with the expected options."""

    def test_uses_v311_and_bounded_queue(self, monkeypatch) -> None:
        """The client pins MQTT v3.1.1 and bounds the incoming queue."""
        mqtt = _make_mqtt()
        mqtt._tls_context = _build_tls_context()
        captured: dict = {}

        def fake_client(**kwargs):
            captured.update(kwargs)
            return object()

        monkeypatch.setattr(aiomqtt, "Client", fake_client)
        mqtt._new_client()

        assert captured["protocol"] is aiomqtt.ProtocolVersion.V311
        assert captured["max_queued_incoming_messages"] == 256


class TestAuthFailure:
    """Verify a credential rejection triggers the auth callback."""

    async def test_bad_credentials_trigger_reauth(self) -> None:
        """A CONNACK rejection (rc 4/5) calls the auth callback and stops."""
        callback = MagicMock()
        mqtt = PgaMQTT(
            MagicMock(),
            "mqtts://broker.example.com:8884",
            "user",
            "pass",
            auth_callback=callback,
        )

        class _RejectedClient:
            async def __aenter__(self):
                raise aiomqtt.MqttCodeError(4, "bad credentials")

            async def __aexit__(self, *_args):
                return False

        mqtt._new_client = _RejectedClient

        await mqtt._run()

        callback.assert_called_once()
