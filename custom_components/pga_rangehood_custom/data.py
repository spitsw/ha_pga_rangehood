# Copyright (c) 2026 Warren Spits
"""Runtime data shared across the PGA rangehood integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .api import PgaHub, PgaMQTT
    from .coordinator import PgaRangehoodCoordinator


@dataclass
class PgaRangehoodData:
    """Runtime data held on the config entry while it is loaded."""

    hub: PgaHub
    mqtt: PgaMQTT
    coordinator: PgaRangehoodCoordinator
    devices: list[dict[str, Any]]


type PgaRangehoodConfigEntry = ConfigEntry[PgaRangehoodData]
