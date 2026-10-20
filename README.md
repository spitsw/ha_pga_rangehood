# Sirius & Pando Rangehood

Home Assistant integration for WiFi-enabled **Sirius** and **Pando** rangehoods.

> **How it works — control goes through the cloud.** This integration does
> **not** talk to your rangehood directly. It signs in to your **Sirius** or
> **Pando** account and controls the rangehood **via that provider's cloud**:
> commands are sent to its REST API, and live state arrives over an MQTT
> connection to its broker. Your Home Assistant instance and the rangehood must
> each be able to reach the cloud — no direct or local network connection to the
> device is used.

## Quick Start

1. **Install** — see [Installation](#installation) below, then restart HA.
2. **Add** — go to **Settings → Devices & Services → Add Integration** and search for "Sirius & Pando Rangehood".
3. **Log in** — pick **Sirius** or **Pando** and enter your cloud email and password.

That's it. Your fan, light(s), timer, power switches, filter controls and
sensors appear automatically.

If you use custom server endpoints or need to disable TLS verification,
choose **Configure custom endpoints** after logging in.

---

## What you get

**Controls**

| Control | What it does |
|---------|-------------|
| **Fan** | 5 speeds (off / low / med / high / boost) |
| **Light** | Brightness and colour temperature (warm → cool) |
| **Secondary Light** | Second light's brightness and colour temperature (if the model has one) |
| **Global Power** | Turn fan and light on/off together |
| **Bi-Power** | Extra airflow and powerful extraction (if supported) |
| **Air Clean** | Hood air-clean mode (if supported) |
| **Timer Active** | Start / stop the countdown timer |
| **Timer Duration** | Set the countdown length in seconds |
| **Device Name** | Rename the rangehood (a configuration text entity) |
| **Reset Filter Worn** | Clear the filter-worn flag and restart the clean countdown (a button) |

**Sensors**

| Sensor | What it shows |
|--------|---------------|
| **Filter Clean Countdown** | Estimated remaining filter life (hours) |
| **Secondary Filter Clean Countdown** | Same for the second filter, if the model has one |
| **Turn-off Time** | The moment the countdown timer will switch the rangehood off |
| **Light / Secondary Light / Fan / Hood Power** | Live power draw in Watts — reported only for the parts a model measures |
| **Fan Airflow** | Reported airflow in m³/h (if the model reports it) |
| **Diagnostics** | IP address, WiFi signal (RSSI), SSID, firmware version & code, device ref / type / class, secure ID |

**Binary sensors**

| Binary sensor | What it shows |
|---------------|---------------|
| **Filter Worn** | The filter needs cleaning |
| **Secondary Filter Worn** | The second filter needs cleaning, if the model has one |

Live values are pushed from the cloud over MQTT. If that connection drops,
entities become **Unavailable** after about 30 seconds and a **Repairs**
notification ("Rangehood MQTT connection lost") appears; both clear
automatically once the broker is reachable again.

Entities are created only for the capabilities your rangehood actually
reports, and the fan speed range and light colour-temperature range are taken
from the device's own metadata. A model with no second light, no filter 2, or
no power metering simply shows fewer entities.

---

## Installation

### Option 1: HACS (recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed.
2. Add this repository as a **custom repository** in HACS:
   - URL: `https://github.com/spitsw/ha_pga_rangehood`
   - Category: **Integration**
3. Search for "Sirius & Pando Rangehood" in HACS and install.
4. Restart Home Assistant.

### Option 2: Manual

Copy the `custom_components/pga_rangehood_custom/` folder into your
Home Assistant `custom_components/` directory and restart.

---

## Configuration

### First-time setup

1. **Settings → Devices & Services → Add Integration**.
2. Search for `Sirius & Pando Rangehood` and select it.
3. Choose a provider:
   - **Log in to Sirius** (recommended) — uses the Sirius cloud.
   - **Log in to Pando** — uses the Pando cloud.
   - **Configure custom endpoints (advanced)** — for a non-standard server, or
     to disable TLS certificate verification. Custom setup also asks for the
     **MQTT topic tenant** (the path segment after `root/` in the broker topics,
     e.g. `codermine` for Sirius, `pando` for Pando).
4. Enter your cloud **email** and **password**. If you chose custom endpoints,
   your credentials are validated against them.

One entry is created per account, and one Home Assistant device per discovered
rangehood. The device's **manufacturer** reflects the chosen brand (Sirius or
Pando).

### Re-configuration

If your credentials change or you need to switch provider / update endpoints:
- Go to **Settings → Devices & Services → Sirius & Pando Rangehood → Configure**.
- You'll be asked to **log in**, or to **change endpoints**; changing endpoints
  never requires a successful login, so a broken server URL can always be
  corrected.
- Use **Re-authenticate** when prompted if your token expires.

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| "Invalid authentication" | Check your password in the provider's mobile app first |
| "No devices found" | Login worked, but no rangehood is linked to your account |
| Entities show "unknown" | Wait up to 30 seconds — the first status update arrives via MQTT |
| Entities show "Unavailable" | The cloud MQTT broker is unreachable. Check **Settings → System → Repairs** and confirm the broker port is allowed (8884 for Sirius, 8883 for Pando); it reconnects automatically |
| Entities don't update | Check HA logs for "MQTT" errors. Network or firewall may block the broker port (8884 for Sirius, 8883 for Pando) |
| Re-auth prompt | Token expired — re-enter your password when prompted |

### Debug logging

Enable it from the UI: **Settings → Devices & Services → Sirius & Pando
Rangehood → Enable debug logging** — the integration declares a `loggers`
entry, so no YAML is required. To configure it in YAML instead:

```yaml
logger:
  logs:
    custom_components.pga_rangehood_custom: debug
```

---

## Technical Reference

For developers and advanced users:

- **Architecture decisions** — see [ARCHITECTURE.md](/ARCHITECTURE.md) for
  ADR-1 through ADR-12 covering the design rationale.
- **Protocol details** — MQTT topics, HTTP endpoints, capability IDs are
  documented in [PROTOCOL.md](/PROTOCOL.md).
- **Tests** — `pytest tests/pga_rangehood_custom/`
- **License** — MIT

---

## Disclaimer

This integration is a custom component and is not affiliated with,
endorsed by, or supported by Sirius, Pando, P.G.A. S.R.L., or any of its
affiliates. All product names, logos, and brands are property of
their respective owners.

## Tested Devices

| Model | Status |
|-------|--------|
| SL926 DL 850 T-SHAPE ARISIT | Confirmed working |
