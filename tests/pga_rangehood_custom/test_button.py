"""Tests for the filter-worn reset button."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.pga_rangehood_custom.api import CAP_FILTER_WORN
from custom_components.pga_rangehood_custom.button import (
    PgaRangehoodFilterResetButton,
)


async def test_press_writes_zero_to_filter_worn() -> None:
    """Pressing the button should write 0 to device.filter1.worn."""
    coordinator = MagicMock()
    coordinator.async_send_command = AsyncMock(return_value=True)
    button = PgaRangehoodFilterResetButton(
        coordinator, "uid-1", {"id": 1, "uid": "uid-1"}
    )

    await button.async_press()

    coordinator.async_send_command.assert_awaited_once_with(
        "uid-1", [{"id": CAP_FILTER_WORN, "value": 0}]
    )
