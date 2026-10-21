# Sirius Rangehood - Cloud Protocol

> **Disclaimer**: Reconstructed by observing the Sirius Android application and
> the traffic it exchanges with the backend. This is not official protocol
> documentation and is not guaranteed to be complete or current.

## Overview

The service exposes three channels:

| Channel | Transport | Direction | Purpose |
|---------|-----------|-----------|---------|
| REST API | HTTPS | Client → Cloud | Authentication, device discovery, enrollment, command submission |
| MQTT | MQTTS (TLS) | Cloud → Client | Live device status, command acknowledgements |
| Push | FCM (HTTPS) | Cloud → Client | Out-of-band alarm notifications |

### Deployments

The protocol is identical across white-label deployments; only the hostnames,
MQTT tenant, and application ID differ. Two known deployments:

| Deployment | Application ID | REST base URL | MQTT broker | Tenant |
|------------|----------------|---------------|-------------|--------|
| Sirius | `com.siriuscappe.app` | `https://sirius.iotpga.it/` | `ssl://sirius.iotpga.it:8884` | `codermine` |
| Pando | `com.pandocappe.app` | `https://pando.iotpga.it` | `ssl://pando.iotpga.it:8883` | `pando` |

The examples below use the Sirius deployment. For Pando, substitute the
corresponding host and tenant. (Note the Sirius base URL carries a trailing
slash; the Pando build constant does not.)

Unless stated otherwise, request and response bodies are JSON, and every
authenticated request carries:

```
Authorization: Bearer <JWT>
```

## Authentication

### POST `/users/login`

Exchanges account credentials for a bearer token.

**Request:**

```json
{
    "email": "<account-email>",
    "password": "<account-password>"
}
```

**Response (HTTP 200):**

```json
{
    "JWT": "eyJhbGciOiJIUzI1NiJ9...",
    "expires": 3600
}
```

The same email and password are also used as the MQTT username/password
(see [MQTT connection](#connection)).

`expires` is the token lifetime in seconds. A request rejected with HTTP `401`
means the token is absent or expired; obtain a new one via `/users/login`.

## REST API

### Endpoint index

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/users/login` | Authenticate, obtain a JWT |
| `POST` | `/users/subscribe` | Register a new account |
| `POST` | `/users/confirm` | Confirm an account |
| `POST` | `/users/lost_password` | Begin password recovery |
| `POST` | `/users/recover_password` | Complete password recovery |
| `GET` | `/users/profile` | Read the account profile |
| `POST` | `/users/profile` | Update the account profile |
| `DELETE` | `/api/me` | Delete the account |
| `GET` | `/devices` | List the account's devices |
| `POST` | `/devices/{uid}/set_value` | Submit a command to a device |
| `POST` | `/devices/{uid}/claim/{securityId}` | Claim a device |
| `POST` | `/devices/{uid}/evict` | Remove a device |
| `POST` | `/devices/{uid}/rename` | Rename a device |
| `POST` | `/devices/{uid}/share` | Share a device with a guest |
| `GET` | `/manuals` | List device manuals |

Paths are resolved against the deployment's base URL (see
[Deployments](#deployments)). `{uid}` is the device's `uid` (the
human-readable identifier), not the numeric `id`. `GET /manuals` is served
from a separate manuals host, not the main base URL.

### GET `/devices`

Returns every device registered to the account, including its static properties
and capability definitions.

**Response (HTTP 200):**

```json
[
    {
        "id": 10000,
        "uid": "PGA-DEVICE001",
        "description": "Rangehood",
        "enable": true,
        "properties": [
            { "id": "property.device.ref", "value": "REF-001" },
            { "id": "property.device.type", "value": "TYPE-A12345" },
            { "id": "property.device_name", "value": "EXAMPLE RANGEHOOD MODEL" },
            { "id": "property.device_class", "value": "0" },
            { "id": "property.device.fw.code", "value": "V02" },
            { "id": "property.device.secureId", "value": "abcd1234ef" },
            { "id": "property.device.fw.version", "value": "2" },
            { "id": "property.device.network.rssi", "value": "-65" },
            { "id": "property.device.network.ssid", "value": "HomeWiFi" },
            { "id": "property.device.network.address", "value": "192.168.1.100" }
        ],
        "capabilities": [
            { "capabilityUid": "device.onOff",                  "capabilityType": "4", "value": 0.0,     "minValue": 0.0,    "maxValue": 1.0 },
            { "capabilityUid": "device.fanSpeed",               "capabilityType": "0", "value": 0.0,     "minValue": 0.0,    "maxValue": 4.0 },
            { "capabilityUid": "device.boostValue",             "capabilityType": "0", "value": 300.0,   "minValue": 0.0,    "maxValue": 7200.0 },
            { "capabilityUid": "device.lightOnOff",             "capabilityType": "4", "value": 0.0,     "minValue": 0.0,    "maxValue": 1.0 },
            { "capabilityUid": "device.timerValue",             "capabilityType": "0", "value": 300.0,   "minValue": 60.0,   "maxValue": 7200.0 },
            { "capabilityUid": "device.filter1.worn",           "capabilityType": "4", "value": 0.0,     "minValue": 0.0,    "maxValue": 1.0 },
            { "capabilityUid": "device.filter1Value",           "capabilityType": "0", "value": 360000.0,"minValue": 0.0,    "maxValue": 360000.0 },
            { "capabilityUid": "device.timer.active",           "capabilityType": "4", "value": 0.0,     "minValue": 0.0,    "maxValue": 1.0 },
            { "capabilityUid": "device.timer.enable",           "capabilityType": "4", "value": 0.0,     "minValue": 0.0,    "maxValue": 1.0 },
            { "capabilityUid": "device.biPowerEnabled",         "capabilityType": "4", "value": 0.0,     "minValue": 0.0,    "maxValue": 1.0 },
            { "capabilityUid": "device.lightBrightness",        "capabilityType": "0", "value": 50.0,    "minValue": 10.0,   "maxValue": 100.0 },
            { "capabilityUid": "device.timer.modifiable",       "capabilityType": "4", "value": 0.0,     "minValue": 0.0,    "maxValue": 1.0 },
            { "capabilityUid": "device.lightColorTemperature",  "capabilityType": "0", "value": 2700.0,  "minValue": 2700.0, "maxValue": 6000.0 }
        ]
    }
]
```

**Device fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Internal numeric device ID (not used as a path parameter) |
| `uid` | string | Human-readable device ID (used as `{uid}` in REST paths and in MQTT topics) |
| `description` | string | Device type label |
| `enable` | bool | Whether the device is active on the server |
| `properties[]` | array | Static `id`/`value` configuration pairs |
| `capabilities[]` | array | Capability definitions (see [Capability model](#capability-model)) |

`value` in a `capabilities[]` entry is the configured/initial value, not
necessarily the live operational state. Live values are delivered over MQTT.

### POST `/devices/{uid}/set_value`

Submits a command to a device. The HTTP response body is not significant; the
definitive result is the acknowledgement delivered asynchronously on the
[response topic](#response-message).

**Request body:**

```json
{
    "command": "getStatus",
    "deviceType": "smartphone",
    "parameters": [],
    "requestId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Command name (see below) |
| `deviceType` | string | Origin of the command; `"smartphone"` |
| `parameters[]` | array | Capability `id`/`value` pairs; empty for commands that take no input |
| `requestId` | string | Client-generated UUIDv4; echoed on the response topic |

#### Commands

| Command | Parameters | Effect |
|---------|------------|--------|
| `getStatus` | none | Device publishes its full state on the `status` topic |
| `getCapabilities` | none | Device publishes its capability list |
| `setValue` | one or more `{ "id", "value" }` | Device applies the given capabilities |
| `setWifiConfig` | WiFi credentials | Configures the device's WiFi (see below) |

Example `setValue` with multiple parameters:

```json
{
    "command": "setValue",
    "deviceType": "smartphone",
    "parameters": [
        { "id": "device.lightOnOff", "value": 1 },
        { "id": "device.lightBrightness", "value": 80 },
        { "id": "device.lightColorTemperature", "value": 4000 }
    ],
    "requestId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

`setWifiConfig` is not sent to the cloud base URL. It is posted to the device's
own setup access point at `http://192.168.1.1/command`, using the same body
shape.

### Device and account management

| Endpoint | Request body |
|----------|--------------|
| `POST /devices/{uid}/claim/{securityId}` | none |
| `POST /devices/{uid}/evict` | none |
| `POST /devices/{uid}/rename` | `{ "newName": "<name>" }` |
| `POST /devices/{uid}/share` | `{ "guestEmail": "<email>" }` |
| `GET /users/profile?limit=N` | none |
| `POST /users/profile` | profile object |

## Capability model

A device exposes a set of capabilities. Each capability has a dotted `id`, a
numeric `capabilityType`, and `minValue`/`maxValue`. Its `value` is either the
configured value (in `GET /devices`) or the live value (over MQTT).

### Types

| `capabilityType` | Meaning |
|------------------|---------|
| `0` | Integer number |
| `1` | Decimal number |
| `2` | Enum |
| `3` | String |
| `4` | Boolean (`0` / `1`) |

### Value semantics

- `device.fanSpeed`: `0` off, `1` low, `2` medium, `3` high, `4` boost.
- `device.lightBrightness` / `device.light2Brightness`: percent, `10`-`100`.
- `device.lightColorTemperature` / `device.light2ColorTemperature`: Kelvin,
  `2700`-`6000`.
- `device.timerValue`: seconds, `60`-`7200`.
- `device.boostValue`: remaining boost time in seconds, `0`-`7200` (read-only;
  boost is started by setting `device.fanSpeed` to `4`).
- `device.filterMode`: `0` = inhaling.
- `device.serviceFunctionCmd`: `1` = filter-change action opened, `2` = closed,
  `0` = clear/reset.
- `device.filter1.worn` / `device.filter2.worn`: set to `0` to reset the
  filter indicator.

### Capabilities

The capabilities observed across Sirius devices. A given device exposes only
the subset reported by `GET /devices`; `capabilityType`, `minValue`, and
`maxValue` are authoritative from that response.

**Access**: `RW` = can be set with `setValue`; `R` = reported by the device
only.

| Capability | Type | Access | Meaning |
|------------|------|--------|---------|
| `device.onOff` | bool | RW | Global power (fan + light) |
| `device.hoodPower` | num | R | Instantaneous power draw (W) |
| `device.fanSpeed` | num | RW | Fan speed |
| `device.fanFlow` | num | R | Fan airflow |
| `device.fanPower` | num | R | Fan power draw (W) |
| `device.boostValue` | num | R | Remaining boost time (seconds) |
| `device.autoModeEnabled` | bool | RW | Auto mode |
| `device.qualityAirEnabled` | bool | RW | Air-quality mode |
| `device.qualityAirValue` | num | R | Air-quality index |
| `device.cleanAirEnabled` | bool | RW | Clean-air mode |
| `device.airLinkEnabled` | bool | RW | Air-link mode |
| `device.amperelinkEnabled` | bool | RW | Ampere-link mode |
| `device.biPowerEnabled` | bool | RW | Bi-power mode |
| `device.lastTimeEnabled` | bool | RW | "Last time" mode |
| `device.lastTimeValue` | num | R | "Last time" countdown |
| `device.co2` | num | R | CO2 level |
| `device.temp` | num | R | Temperature |
| `device.hum` | num | R | Humidity |
| `device.iaq500` | num | R | Air-quality (IAQ) index |
| `device.lightOnOff` | bool | RW | Light on/off |
| `device.lightBrightness` | num | RW | Light brightness |
| `device.lightColorTemperature` | num | RW | Light colour temperature |
| `device.lightPower` | num | R | Light power draw (W) |
| `device.light2OnOff` | bool | RW | Second light on/off |
| `device.light2Brightness` | num | RW | Second light brightness |
| `device.light2ColorTemperature` | num | RW | Second light colour temperature |
| `device.light2Power` | num | R | Second light power draw (W) |
| `device.filterMode` | num | R | Filter mode |
| `device.filterType` | num | R | Filter type |
| `device.filter1.worn` | bool | RW | Main filter worn (write `0` to reset) |
| `device.filter1Value` | num | R | Main filter remaining life |
| `device.filter2.worn` | bool | RW | Secondary filter worn (write `0` to reset) |
| `device.filter2Value` | num | R | Secondary filter remaining life |
| `device.serviceFunctionEn` | bool | R | Service-function mode active |
| `device.serviceFunctionCmd` | num | RW | Service-function command |
| `device.timerValue` | num | RW | Timer duration |
| `device.timer.active` | bool | RW | Timer running |
| `device.timer.enable` | bool | R | Timer enabled |
| `device.timer.modifiable` | bool | R | Timer can be modified |

## MQTT

### Connection

- Broker: `ssl://<host>:<port>`; Sirius uses `sirius.iotpga.it:8884`, Pando
  uses `pando.iotpga.it:8883` (see [Deployments](#deployments)).
- Authentication: MQTT `username` = account email, `password` = account
  password. `clientId` is a client-generated UUID.
- Subscriptions and publications use QoS `0`. No Last Will is configured.
- A client subscribes to the device's `status` topic and to the device's
  response wildcard (see [Topics](#topics)).

> **TLS caveat**: the broker's leaf certificate expired in 2024 and is never
> renewed, so a client has to disable OpenSSL's certificate **time check**
> (`X509_V_FLAG_NO_CHECK_TIME`) to complete the handshake. The certificate
> **chain and hostname are still verified** (against DigiCert's legacy Global
> Root CA, which current trust stores no longer ship), so the broker is still
> authenticated as `*.iotpga.it`. What is given up is time validity, so a lapsed
> or future-dated leaf, or a leaked one whose key an attacker holds, is accepted;
> certificate expiry is therefore not a usable trust signal on this channel.
> Revocation (CRL/OCSP) is not checked either way.

### Topics

Topic paths embed the tenant: `codermine` for Sirius, `pando` for Pando.

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `root/{tenant}/devices/{uid}/status` | Cloud → Client | Live device state |
| `root/{tenant}/devices/{uid}/response/{requestId}` | Cloud → Client | Command acknowledgement |
| `root/{tenant}/devices/{uid}/request` | Client → Cloud | Defined, but commands are submitted over REST instead |
| `root/{tenant}/devices/{uid}/capabilities` | Cloud → Client | Capability list |

Templates:

```
root/%s/devices/%s/request
root/%s/devices/%s/response/%s
root/%s/devices/%s/status
```

Clients subscribe to the device's `status` topic and to
`root/{tenant}/devices/{uid}/response/#` (all responses for the device).

### Status message

Published on `root/{tenant}/devices/{uid}/status`.

**Payload:**

```json
{
    "deviceId": "PGA-DEVICE001",
    "values": [
        { "id": "device.onOff", "value": 0 },
        { "id": "device.biPowerEnabled", "value": 1 },
        { "id": "device.fanSpeed", "value": 0 },
        { "id": "device.lightOnOff", "value": 0 },
        { "id": "device.lightBrightness", "value": 100 },
        { "id": "device.lightColorTemperature", "value": 3294 },
        { "id": "device.timer.enable", "value": 0 },
        { "id": "device.timer.active", "value": 0 },
        { "id": "device.timer.modifiable", "value": 0 },
        { "id": "device.timerValue", "value": 0 },
        { "id": "device.boostValue", "value": 0 },
        { "id": "device.filter1.worn", "value": 0 },
        { "id": "device.filter1Value", "value": 101340 }
    ],
    "timestamp": "2026-09-28T13:37:23"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `deviceId` | string | Device `uid` the message applies to |
| `values[]` | array | Capability `id`/`value` pairs |
| `timestamp` | string | ISO-8601, second precision |

A status message is published after the device processes a `getStatus`
command, and after any state change (a physical control, or a `setValue`
command). `values[]` may be partial; merge non-absent entries onto the last
known state. Entries whose `id` is not among the device's known capabilities
should be ignored. The value's type follows the capability's `capabilityType`.

### Response message

Published on `root/{tenant}/devices/{uid}/response/{requestId}`, where
`{requestId}` equals the `requestId` sent in the REST `set_value` body.

**Payload:**

```json
{
    "timestamp": "2026-09-28T13:43:57",
    "status": 0
}
```

`status` is `0` on success and non-zero on error. A response with a missing or
non-zero `status` is a failure.

**Correlation:** a response is matched to its command by the last segment of
the topic. A response with no matching pending command (for example one that
arrives after the client has already timed out, or a duplicate) is discarded.

A reference client applies a timeout of roughly 20 seconds to each command; if
no acknowledgement arrives it treats the command as failed.

## Interaction flows

### Startup

```
1. Client ── HTTPS POST /users/login ───────────────► Cloud ── { JWT, expires }
2. Client ── HTTPS GET /devices ────────────────────► Cloud ── [{ id, uid, props, caps }]
3. Client ── HTTPS POST /devices/{uid}/set_value ───► Cloud   (command: getStatus)
4. Device ── state ──► Cloud ── MQTT devices/{uid}/status ─► Client
```

### Command

```
1. Client ── HTTPS POST /devices/{uid}/set_value ───► Cloud   (command: setValue)
2. Cloud ── MQTT devices/{uid}/response/{requestId} ─► Client (status: 0)
3. Device ── state ──► Cloud ── MQTT devices/{uid}/status ─► Client
```

The REST call and the MQTT acknowledgement report two different things: the
HTTP response acknowledges receipt, the MQTT `status` reports whether the
device applied the command. No explicit `getStatus` is needed afterwards,
because the device publishes its new state after applying a change.

### Heartbeat

Polling `getStatus` periodically (for example every 5 minutes) resynchronises
state if a status message was missed.

## Push notifications

The cloud can deliver alarm notifications over Firebase Cloud Messaging. Each
deployment uses its own Firebase project (Sirius `prjsiriusapp`, Pando
`prjpandoapp`); the payload format below is the same for both. A data payload
containing `deviceId` together with `warning.tempValue` and
`warning.humidityValue` denotes an alarm.

| Key | Meaning |
|-----|---------|
| `deviceId` | Device the alarm refers to |
| `warning.tempValue` | Current temperature |
| `warning.tempThs` | Temperature threshold |
| `warning.humidityValue` | Current humidity |
| `warning.humidityThs` | Humidity threshold |

Push alerts are informational and do not replace MQTT status updates.
