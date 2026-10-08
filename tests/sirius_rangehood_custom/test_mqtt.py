"""Tests for mqtt.py — aiomqtt message parsing and subscription tracking."""

from __future__ import annotations

import json
import ssl
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.sirius_rangehood_custom.api.mqtt import (
    _BROKER_ROOT_CA,
    _X509_V_FLAG_NO_CHECK_TIME,
    SiriusMQTT,
    _build_tls_context,
)


def _make_mqtt(status_callback=None, connection_callback=None):
    """Build a SiriusMQTT without connecting."""
    return SiriusMQTT(
        MagicMock(),
        "mqtts://broker.example.com:8884",
        "user",
        "pass",
        status_callback,
        connection_callback=connection_callback,
    )


def _message(topic: str, payload: bytes) -> SimpleNamespace:
    """Build a stand-in for an `aiomqtt.Message`."""
    return SimpleNamespace(topic=SimpleNamespace(value=topic), payload=payload)


class TestInit:
    """Verify endpoint parsing and defaults."""

    def test_parses_endpoint(self) -> None:
        """Extract host and port from the mqtts:// URL."""
        mqtt = _make_mqtt()
        assert mqtt._host == "broker.example.com"
        assert mqtt._port == 8884

    def test_default_port(self) -> None:
        """Default to port 8884 when the URL omits a port."""
        mqtt = SiriusMQTT(MagicMock(), "mqtts://broker.example.com", "user", "pass")
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
        """The status topic is per-device."""
        assert (
            SiriusMQTT._status_topic("device-1")
            == "root/codermine/devices/device-1/status"
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
