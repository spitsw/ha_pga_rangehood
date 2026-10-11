# Copyright (c) 2026 Warren Spits
"""Constants for the Sirius Rangehood integration (HA layer)."""

from __future__ import annotations

from typing import NamedTuple

from .api import (
    DEFAULT_PANDO_ENDPOINT,
    DEFAULT_PANDO_MQTTS_ENDPOINT,
    DEFAULT_SIRIUS_ENDPOINT,
    DEFAULT_SIRIUS_MQTTS_ENDPOINT,
    PANDO_MQTT_TENANT,
    SIRIUS_MQTT_TENANT,
)

DOMAIN = "sirius_rangehood_custom"

CONF_PROVIDER = "provider"
CONF_SIRIUS_ENDPOINT = "sirius_endpoint"
CONF_SIRIUS_MQTTS_ENDPOINT = "sirius_mqtts_endpoint"
CONF_MQTT_TENANT = "mqtt_tenant"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"  # noqa: S105
CONF_INSECURE_TLS = "insecure_tls"

# Provider choices offered during setup.
PROVIDER_SIRIUS = "sirius"
PROVIDER_PANDO = "pando"
PROVIDER_CUSTOM = "custom"


class Provider(NamedTuple):
    """Connection settings and display name for a supported cloud provider."""

    name: str
    endpoint: str
    mqtts_endpoint: str
    tenant: str


# Built-in providers. Add a brand here (plus a config-flow menu option) to
# support it; custom endpoints are configured per entry and live outside this
# table.
PROVIDERS: dict[str, Provider] = {
    PROVIDER_SIRIUS: Provider(
        "Sirius",
        DEFAULT_SIRIUS_ENDPOINT,
        DEFAULT_SIRIUS_MQTTS_ENDPOINT,
        SIRIUS_MQTT_TENANT,
    ),
    PROVIDER_PANDO: Provider(
        "Pando",
        DEFAULT_PANDO_ENDPOINT,
        DEFAULT_PANDO_MQTTS_ENDPOINT,
        PANDO_MQTT_TENANT,
    ),
}

# Provider assumed when an entry predates the `provider` key.
DEFAULT_PROVIDER = PROVIDER_SIRIUS
