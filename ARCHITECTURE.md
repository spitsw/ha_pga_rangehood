# Architecture & Design Decisions

This document records key architectural decisions (ADRs) for the Sirius
Rangehood integration.

---

## ADR-1: Direct MQTT via aiomqtt over HA's MQTT integration

**Status**: Accepted

**Context**: HA's built-in `mqtt` integration is a single global broker
configuration — only one MQTT connection can exist for the entire HA
instance. The Sirius rangehood requires a separate MQTT connection to
`mqtts://sirius.iotpga.it:8884` with its own credentials, subscriptions,
and message parsing.

HA's MQTT integration does support TLS with `tls_insecure: true` (which
disables certificate hostname validation), so the expired certificate
alone is not a blocker. However, adding a second MQTT broker via the
global integration is not supported.

**Decision**: Use the `aiomqtt` library (an async wrapper over
`paho-mqtt`) directly, managing the connection lifecycle and TLS context
independently of HA's infrastructure.

**Consequences**:
- No dependency on HA's global MQTT integration — the component
  works regardless of the user's existing MQTT setup.
- Full control over TLS configuration: the expired broker certificate is
  accepted (`CERT_NONE`), independent of HA's MQTT settings.
- `aiomqtt` drives paho-mqtt's socket on the HA event loop (via
  `add_reader`), so there is no background thread and no callback
  bridging (see ADR-2).
- The `/status` topic subscription and `values[]` payload flattening
  are handled directly rather than through HA's MQTT platform
  configuration.

---

## ADR-2: MQTT callbacks run on the HA event loop (aiomqtt)

**Status**: Accepted (supersedes the former paho-thread bridge)

**Context**: `paho-mqtt` invokes its callbacks (`on_message`, `on_connect`,
…) from a background network thread, and HA data structures
(`device_states`, `coordinator.data`) may only be touched on the HA event
loop. A thread bridge (`call_soon_threadsafe`) was previously required.

**Decision**: Use `aiomqtt`, which runs paho-mqtt's socket directly on the
event loop (no background thread). A single background task
(`entry.async_create_background_task`) connects, (re)subscribes, and
consumes `client.messages`, invoking the coordinator's
`apply_mqtt_update` / `set_mqtt_connected` **directly** on the loop.

```
aiomqtt task (HA event loop)
  → async for message in client.messages
      → _handle_message(message) → status_callback(device_id, values)
          → coordinator.apply_mqtt_update(...)
```

**Consequences**:
- No thread bridge and no `call_soon_threadsafe` for state updates.
- Reconnection is an explicit loop in the task (ADR-10) driven by
  `aiomqtt.MqttError`.

---

## ADR-3: Coordinator as single source of truth

**Status**: Accepted

**Context**: Device state arrives from two paths — MQTT push messages and
a periodic HTTP `getStatus` call. Entities need a unified, consistent view
of device state without having to merge two sources themselves.

**Decision**: A `DataUpdateCoordinator` owns the authoritative
`device_states` dict. Both data paths funnel into it:

- **MQTT push** (primary): Parsed status payloads are merged into the
  coordinator via the thread-safe bridge (ADR-2).
- **HTTP `getStatus`** (every 300 s): Sends a no-op status request for
  each device. The device responds via MQTT if it chooses to, but the
  actual state data always arrives through the MQTT push path. The HTTP
  call exists because HA's `DataUpdateCoordinator` requires a periodic
  `update_method` callback — without it, `last_update_success` would not
  be set and `CoordinatorEntity` subclasses might show as unavailable.

All entities read `coordinator.data.get(device_id)` and are automatically
notified when data changes via `async_set_updated_data`.

**Consequences**:
- Entities are simple — no per-entity polling or merge logic.
- Single `async_set_updated_data` call per MQTT update notifies all entities.
- HTTP `getStatus` is functionally a no-op that satisfies the coordinator
  pattern; state data is never read from the HTTP response.

---

## ADR-4: HTTP for commands, MQTT for live state

**Status**: Accepted

**Context**: The Sirius IoT platform exposes two channels: an HTTPS REST
API for command execution and device discovery, and an MQTT broker for
live status updates. Commands (`setValue`) can only be sent via HTTP.

**Decision**:
- **Commands** → HTTPS POST to `/devices/{id}/set_value`. The device
  processes the command and publishes its new state via MQTT.
- **Live state** → MQTT subscription to
  `root/codermine/devices/{id}/status` and `response/#`.
- **Periodic heartbeat** → HTTP `getStatus` (via the coordinator) keeps
  the MQTT data stream alive.

```
User action → FanEntity.async_turn_on()
                → hub.async_send_command()
                    → HTTP POST /set_value {command: "setValue", ...}
Device responds → MQTT status topic
                    → aiomqtt message loop → coordinator
                        → FanEntity updated via CoordinatorEntity
```

**Consequences**:
- Commands are synchronous (HTTP request/response) but state updates are
  asynchronous (MQTT push).
- Entities optimistically update locally after sending a command, then
  converge when the MQTT status arrives.

---

## ADR-5: Fan speed model (0-4)

**Status**: Accepted

**Context**: HA's fan entity expects a `percentage` (0-100) and a
`speed_count`. The Sirius API uses integer speeds 0 (off) through 4
(boost).

**Decision**: Map speeds to percentages linearly:
| Speed | Value | Percentage |
|-------|-------|------------|
| Off | 0 | 0 |
| Low | 1 | 25 |
| Medium | 2 | 50 |
| High | 3 | 75 |
| Boost | 4 | 100 |

`speed_count = 5` (HA counts non-off presets, so this is 4 + 1 for off).

`async_set_percentage` uses nearest-match: `min(PERCENTAGE_TO_SPEED.items(),
key=lambda x: abs(x[0] - percentage))`. Setting 10% lands on speed 0 (off);
setting 37% lands on speed 1 (low); etc.

**Consequences**:
- User sees a 5-step slider in the HA UI.
- Percentage and speed always round-trip cleanly (bijection).

---

## ADR-6: Proactive token refresh

**Status**: Accepted

**Context**: The Sirius JWT has a configurable expiry (default 1 hour). An
expired token causes every API call to first do a login round-trip, which
adds latency.

**Decision**: After setup, schedule `async_ensure_token()` to run 60 seconds
before the token's expiry. This keeps a valid token cached in the hub,
so API calls never wait for a login.

```python
remaining = (token_expiry - datetime.now()).total_seconds() - 60
if remaining > 0:
    async_call_later(hass, remaining, _refresh_token)
```

**Consequences**:
- API calls are fast (no login wait).
- If HA restarts, the token is re-persisted via `Store` and restored on
  next setup.
- On token rejection by the server (e.g. clock drift), the existing 401
  → reauth path still catches it.

---

## ADR-7: Discovery via `/devices/` at setup time only

**Status**: Accepted

**Context**: The `/devices/` API returns all devices registered to the
account at setup time. Device discovery is a one-time operation.

**Decision**: Devices are discovered once during `async_setup_entry`
via the `/devices/` API. No periodic polling is performed. MQTT
subscriptions are created for each discovered device's specific topic
(`.../devices/{uid}/status`), so messages from unknown devices are
never received.

If a new rangehood is paired to the account after initial setup, the
user must reconfigure the integration (**Settings → Devices & Services
→ Sirius Rangehood → Configure**) to trigger a fresh discovery.

**Consequences**:
- New devices are not discovered automatically — reconfiguration is
  required.
- MQTT cannot be used for discovery because topics are device-specific
  and subscription happens at setup time.
- This is acceptable for 1–3 devices where pairing is rare.

---

## ADR-8: Reauth on auth failure

**Status**: Accepted

**Context**: When the Sirius password changes or the JWT is rejected,
the user needs to re-enter credentials without losing their existing
configuration.

**Decision**: A central `_trigger_reauth()` helper fires
`hass.config_entries.async_start_reauth(entry_id)` on any
`SiriusAuthError`. The reauth flow (in `config_flow.py`) uses
`async_update_reload_and_abort()` — it updates the existing entry's data
and reloads it, preserving all entity state and device registry entries.

The error is raised by `hub.py` in two places:
1. **Login**: HTTP 200 with no `JWT` field → wrong credentials.
2. **API call**: HTTP 401 → token rejected by server.

**Consequences**:
- User never loses their device registry entries or automations.
- Only auth failures trigger reauth — transient timeouts do not
  (see commit `c8ada64`).

---

## ADR-9: Retry with exponential backoff for HTTP calls

**Status**: Accepted

**Context**: The Sirius server is an external cloud service subject to
network glitches, rate limiting (429), and temporary outages (502/503/504).
The component uses HTTP for both commands (`setValue`) and polling
(`getStatus`). A single transient failure should not cause a visible
failure to the user.

**Decision**: Wrap all HTTP API calls in `_run_with_retry()` — an
async retry loop that catches `asyncio.TimeoutError` and
`aiohttp.ClientError`. It retries up to 3 times with a doubling delay
(2 s, 4 s, 8 s).

The retry only applies to *network-level* failures. Application-level
failures (wrong credentials → `SiriusAuthError`, HTTP 4xx) propagate
immediately without retry.

**Consequences**:
- A brief network blip (1–5 s) will not cause a command to fail.
- A sustained outage eventually fails cleanly — the last exception
  propagates to the caller.
- The MQTT stream is unaffected by HTTP retries (separate connection,
  see ADR-1).
- The coordinator's HTTP `getStatus` heartbeat also benefits, reducing
  false-positive reauth triggers from transient errors.

---

## ADR-10: MQTT reconnect with exponential backoff

**Status**: Accepted

**Context**: A dropped MQTT connection should be re-established without
hammering the Sirius broker during a cloud outage. (`paho-mqtt`'s own
`reconnect_delay_set` is not used — `aiomqtt` surfaces the disconnect as an
`MqttError` and the reconnect loop is ours, see ADR-2.)

**Decision**: The MQTT task reconnects in a loop, doubling the delay from
**1 s up to a 120 s cap** after each failure (`aiomqtt.MqttError`), and
re-subscribes to every device topic on each successful reconnect.

```python
delay = 1
while True:
    try:
        async with client:  # connect
            subscribe(...)  # (re)subscribe on every connect
            async for message in client.messages:
                ...
    except aiomqtt.MqttError:
        await asyncio.sleep(delay)
        delay = min(delay * 2, 120)
```

**Consequences**:
- No unnecessary load on the Sirius broker during outages.
- Reconnection is automatic (within the task) — no external logic needed.
- The component continues to work via the HTTP `getStatus` heartbeat while
  MQTT is disconnected (coordinator fallback).

---

## ADR-11: MQTT subscriptions — status only, no response topics

**Status**: Accepted

**Context**: The Sirius MQTT broker publishes two message types per device:

- `.../devices/{id}/status` — periodic state snapshots and push updates
  whenever a value changes. Payload contains a flat `values` array with
  `{id, value}` pairs that directly map to device capabilities.

- `.../devices/{id}/response/{uuid}` — simple acknowledgements returned
  after a `setValue` command is processed. Payload contains only a
  timestamp and a status field (e.g. `{"timestamp": ..., "status": "OK"}`).
  No state data.

**Decision**: Only subscribe to `/status`. The `/response/#` topic carries
no information that the component needs — command success is confirmed by
the subsequent status update that the device publishes via MQTT after
processing the command.

**Consequences**:
- Half the subscriptions (one topic per device instead of two).
- No wasted messages, no payload parsing for acks.
- The HTTP `set_value` call may still fail with a dropped connection
  (see ADR-9), but the command is still processed and the status update
  arrives via MQTT.