"""Tests for hub.py — HTTP API client and device flattening."""

from __future__ import annotations

from unittest.mock import AsyncMock

from custom_components.pga_rangehood_custom.api.hub import SiriusAuthError, SiriusHub


class TestFlattenDevice:
    """Verify _flatten_device processes API responses correctly."""

    def test_flatten_basic(self) -> None:
        """Should flatten properties and capabilities into one dict."""
        raw = {
            "id": 1,
            "uid": "uid-1",
            "description": "My Rangehood",
            "properties": [
                {"id": "property.device.fw.version", "value": "1.2.3"},
                {"id": "property.device.network.rssi", "value": -70},
            ],
            "capabilities": [
                {
                    "capabilityUid": "device.fanSpeed",
                    "value": 3,
                    "minValue": 0,
                    "maxValue": 4,
                },
            ],
        }
        hub = SiriusHub.__new__(SiriusHub)
        flat = hub._flatten_device(raw)

        assert flat["id"] == 1
        assert flat["uid"] == "uid-1"
        assert flat["name"] == "My Rangehood"
        assert flat["property.device.fw.version"] == "1.2.3"
        assert flat["property.device.network.rssi"] == -70
        # Capability value is NOT stored in the flat dict — live state
        # comes from MQTT. Only _limits captures min/max bounds.
        assert "device.fanSpeed" not in flat
        assert "_limits" in flat
        assert flat["_limits"]["device.fanSpeed"] == {"min": 0.0, "max": 4.0}

    def test_flatten_name_from_description(self) -> None:
        """Should derive the name from `description`, ignoring property.device_name."""
        raw = {
            "id": 2,
            "uid": "uid-2",
            "description": "Fallback Name",
            "properties": [
                {"id": "property.device_name", "value": "Kitchen Rangehood"},
            ],
            "capabilities": [],
        }
        hub = SiriusHub.__new__(SiriusHub)
        flat = hub._flatten_device(raw)
        assert flat["name"] == "Fallback Name"

    def test_flatten_no_properties(self) -> None:
        """Should handle devices with no properties or capabilities."""
        raw = {
            "id": 3,
            "uid": "uid-3",
            "description": "Bare Device",
            "properties": [],
            "capabilities": [],
        }
        hub = SiriusHub.__new__(SiriusHub)
        flat = hub._flatten_device(raw)
        assert flat["id"] == 3
        assert flat["uid"] == "uid-3"

    def test_flatten_missing_optional_fields(self) -> None:
        """Should handle missing uid gracefully."""
        raw = {
            "id": 4,
            "description": "No UID",
            "properties": [],
            "capabilities": [],
        }
        hub = SiriusHub.__new__(SiriusHub)
        flat = hub._flatten_device(raw)
        assert flat["id"] == 4
        assert flat["uid"] == ""


class TestSiriusAuthError:
    """Verify SiriusAuthError is raiseable and catchable."""

    def test_is_exception(self) -> None:
        assert issubclass(SiriusAuthError, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        try:
            msg = "test"
            raise SiriusAuthError(msg)
        except SiriusAuthError:
            assert True


class TestRestoreToken:
    """Verify restored token expiry is normalized to an aware UTC datetime."""

    def test_naive_expiry_becomes_aware(self) -> None:
        """A timezone-naive stored expiry should be treated as UTC."""
        hub = SiriusHub.__new__(SiriusHub)
        hub.restore_token("tok", "2030-01-01T00:00:00")
        assert hub._token_expiry is not None
        assert hub._token_expiry.tzinfo is not None

    def test_aware_expiry_preserved(self) -> None:
        """An expiry that already carries an offset should be kept as-is."""
        hub = SiriusHub.__new__(SiriusHub)
        hub.restore_token("tok", "2030-01-01T00:00:00+02:00")
        assert hub._token_expiry is not None
        assert hub._token_expiry.utcoffset().total_seconds() == 7200

    def test_invalid_expiry_is_none(self) -> None:
        """An unparsable expiry should leave the token expiry unset."""
        hub = SiriusHub.__new__(SiriusHub)
        hub.restore_token("tok", "not-a-date")
        assert hub._token_expiry is None


class TestCommandResult:
    """Verify command requests expose the requestId for MQTT correlation."""

    async def test_send_command_returns_request_id(self) -> None:
        """setValue returns the generated requestId and the accepted flag."""
        hub = SiriusHub.__new__(SiriusHub)
        captured: dict[str, object] = {}

        async def fake_post(_device_id, payload):
            captured["payload"] = payload
            return True

        hub._post_set_value = fake_post
        result = await hub.async_send_command("dev-1", [{"id": "x", "value": 1}])

        assert result.accepted is True
        assert result.request_id
        assert captured["payload"]["requestId"] == result.request_id

    async def test_send_command_reports_rejection(self) -> None:
        """A rejected setValue still carries a requestId for bookkeeping."""
        hub = SiriusHub.__new__(SiriusHub)

        async def fake_post(_device_id, _payload):
            return False

        hub._post_set_value = fake_post
        result = await hub.async_send_command("dev-1", [])

        assert result.accepted is False
        assert result.request_id

    async def test_get_status_returns_accepted(self) -> None:
        """getStatus returns the HTTP outcome; its ack is not awaited."""
        hub = SiriusHub.__new__(SiriusHub)
        captured: dict[str, object] = {}

        async def fake_post(_device_id, payload):
            captured["payload"] = payload
            return True

        hub._post_set_value = fake_post
        result = await hub.async_get_status("dev-1")

        assert result is True
        assert captured["payload"]["command"] == "getStatus"
        assert captured["payload"]["requestId"]


class TestRenameDevice:
    """Verify the rename request targets the right endpoint and body."""

    async def test_rename_posts_new_name(self) -> None:
        """Rename POSTs {"newName": ...} to /devices/{uid}/rename."""
        hub = SiriusHub.__new__(SiriusHub)
        hub._endpoint = "https://example.com"
        hub._post_json = AsyncMock(return_value=True)

        result = await hub.async_rename_device("uid-1", "New Name")

        assert result is True
        hub._post_json.assert_awaited_once()
        url, payload = hub._post_json.call_args.args
        assert url == "https://example.com/devices/uid-1/rename"
        assert payload == {"newName": "New Name"}
        assert hub._post_json.call_args.kwargs["action"] == "rename uid-1"
