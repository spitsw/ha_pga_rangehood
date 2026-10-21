"""Tests for entity helpers."""

from __future__ import annotations

from custom_components.pga_rangehood_custom.const import (
    PROVIDER_CUSTOM,
    PROVIDER_PANDO,
    PROVIDER_SIRIUS,
)
from custom_components.pga_rangehood_custom.entity import manufacturer_for_provider


class TestManufacturerForProvider:
    """Verify the device manufacturer maps from the provider."""

    def test_sirius(self) -> None:
        assert manufacturer_for_provider(PROVIDER_SIRIUS) == "Sirius"

    def test_pando(self) -> None:
        assert manufacturer_for_provider(PROVIDER_PANDO) == "Pando"

    def test_unknown_uses_endpoint_host(self) -> None:
        """An unknown provider is labelled by its endpoint host."""
        assert (
            manufacturer_for_provider(PROVIDER_CUSTOM, "https://custom.example.com")
            == "custom.example.com"
        )
        assert manufacturer_for_provider("mystery") == "Rangehood"
