"""Tests for const.py — constants and manifest consistency."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.pga_rangehood_custom.api import (
    CAP_FAN_SPEED,
    DEFAULT_SIRIUS_ENDPOINT,
    DEFAULT_SIRIUS_MQTTS_ENDPOINT,
)
from custom_components.pga_rangehood_custom.api.const import VERSION
from custom_components.pga_rangehood_custom.const import DOMAIN

_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "custom_components"
    / "pga_rangehood_custom"
    / "manifest.json"
)


class TestConstants:
    """Verify important constants are present and well-formed."""

    def test_domain(self) -> None:
        assert DOMAIN == "pga_rangehood_custom"

    def test_cap_fan_speed(self) -> None:
        assert CAP_FAN_SPEED == "device.fanSpeed"

    def test_default_endpoints(self) -> None:
        assert DEFAULT_SIRIUS_ENDPOINT == "https://sirius.iotpga.it"
        assert DEFAULT_SIRIUS_MQTTS_ENDPOINT == "mqtts://sirius.iotpga.it:8884"


class TestManifest:
    """Keep the manifest consistent with the code constants."""

    def test_version_matches_const(self) -> None:
        """VERSION in api/const.py must match manifest version."""
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        assert manifest["version"] == VERSION

    def test_integration_type_is_hub(self) -> None:
        """One entry serves an account with multiple devices, so it is a hub."""
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        assert manifest["integration_type"] == "hub"
