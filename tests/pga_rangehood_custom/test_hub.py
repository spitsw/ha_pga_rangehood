"""Tests for hub.py — HTTP API client and device flattening."""

from __future__ import annotations

from typing import Self
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.pga_rangehood_custom.api import hub as hub_module
from custom_components.pga_rangehood_custom.api.hub import PgaAuthError, PgaHub


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
        hub = PgaHub.__new__(PgaHub)
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
        hub = PgaHub.__new__(PgaHub)
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
        hub = PgaHub.__new__(PgaHub)
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
        hub = PgaHub.__new__(PgaHub)
        flat = hub._flatten_device(raw)
        assert flat["id"] == 4
        assert flat["uid"] == ""


class TestPgaAuthError:
    """Verify PgaAuthError is raiseable and catchable."""

    def test_is_exception(self) -> None:
        assert issubclass(PgaAuthError, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        try:
            msg = "test"
            raise PgaAuthError(msg)
        except PgaAuthError:
            assert True


class TestRestoreToken:
    """Verify restored token expiry is normalized to an aware UTC datetime."""

    def test_naive_expiry_becomes_aware(self) -> None:
        """A timezone-naive stored expiry should be treated as UTC."""
        hub = PgaHub.__new__(PgaHub)
        hub.restore_token("tok", "2030-01-01T00:00:00")
        assert hub._token_expiry is not None
        assert hub._token_expiry.tzinfo is not None

    def test_aware_expiry_preserved(self) -> None:
        """An expiry that already carries an offset should be kept as-is."""
        hub = PgaHub.__new__(PgaHub)
        hub.restore_token("tok", "2030-01-01T00:00:00+02:00")
        assert hub._token_expiry is not None
        assert hub._token_expiry.utcoffset().total_seconds() == 7200

    def test_invalid_expiry_is_none(self) -> None:
        """An unparsable expiry should leave the token expiry unset."""
        hub = PgaHub.__new__(PgaHub)
        hub.restore_token("tok", "not-a-date")
        assert hub._token_expiry is None


class TestCommandResult:
    """Verify command requests expose the requestId for MQTT correlation."""

    async def test_send_command_returns_request_id(self) -> None:
        """setValue returns the generated requestId and the accepted flag."""
        hub = PgaHub.__new__(PgaHub)
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
        hub = PgaHub.__new__(PgaHub)

        async def fake_post(_device_id, _payload):
            return False

        hub._post_set_value = fake_post
        result = await hub.async_send_command("dev-1", [])

        assert result.accepted is False
        assert result.request_id

    async def test_get_status_returns_request_id(self) -> None:
        """getStatus returns the HTTP outcome and the generated requestId."""
        hub = PgaHub.__new__(PgaHub)
        captured: dict[str, object] = {}

        async def fake_post(_device_id, payload):
            captured["payload"] = payload
            return True

        hub._post_set_value = fake_post
        result = await hub.async_get_status("dev-1")

        assert result.accepted is True
        assert captured["payload"]["command"] == "getStatus"
        assert captured["payload"]["requestId"] == result.request_id


class TestRenameDevice:
    """Verify the rename request targets the right endpoint and body."""

    async def test_rename_posts_new_name(self) -> None:
        """Rename POSTs {"newName": ...} to /devices/{uid}/rename."""
        hub = PgaHub.__new__(PgaHub)
        hub._endpoint = "https://example.com"
        hub._post_json = AsyncMock(return_value=True)

        result = await hub.async_rename_device("uid-1", "New Name")

        assert result is True
        hub._post_json.assert_awaited_once()
        url, payload = hub._post_json.call_args.args
        assert url == "https://example.com/devices/uid-1/rename"
        assert payload == {"newName": "New Name"}
        assert hub._post_json.call_args.kwargs["action"] == "rename uid-1"


class _FakeResponse:
    """A stand-in for an aiohttp response: awaitable and an async context manager."""

    def __init__(self, status: int) -> None:
        self.status = status

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    def __await__(self):
        if False:  # pragma: no cover - makes this a generator
            yield
        return self


def _hub(status: int | None, *, raises: type[Exception] | None = None) -> PgaHub:
    """Return a hub whose POST either answers *status* or raises *raises*."""
    hub = PgaHub.__new__(PgaHub)
    hub._session = MagicMock()
    hub._token = "token"
    hub._token_expiry = None
    if raises is not None:
        hub._session.post = MagicMock(side_effect=raises)
    else:
        hub._session.post = MagicMock(return_value=_FakeResponse(status))
    hub.async_ensure_token = AsyncMock(return_value="token")
    return hub


class TestPostJson:
    """Verify the low-level POST maps statuses and errors to a bool."""

    async def test_success(self) -> None:
        """HTTP 200 is accepted."""
        assert await _hub(200)._post_json("url", {}, action="x") is True

    async def test_non_200_is_rejected(self) -> None:
        """A non-200 status returns False without raising."""
        assert await _hub(500)._post_json("url", {}, action="x") is False

    async def test_unauthorized_raises_and_clears_token(self) -> None:
        """HTTP 401 raises and drops the cached token."""
        hub = _hub(401)
        with pytest.raises(PgaAuthError):
            await hub._post_json("url", {}, action="x")
        assert hub._token is None
        assert hub._token_expiry is None

    async def test_timeout_returns_false(self, monkeypatch) -> None:
        """Timeout after retries returns False."""
        monkeypatch.setattr(hub_module, "_RETRY_BASE_DELAY", 0)
        assert (
            await _hub(None, raises=TimeoutError)._post_json("url", {}, action="x")
            is False
        )

    async def test_client_error_returns_false(self, monkeypatch) -> None:
        """A connection error after retries returns False."""
        monkeypatch.setattr(hub_module, "_RETRY_BASE_DELAY", 0)
        assert (
            await _hub(None, raises=aiohttp.ClientError)._post_json(
                "url", {}, action="x"
            )
            is False
        )
