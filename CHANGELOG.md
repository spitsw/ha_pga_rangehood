# CHANGELOG


## v1.4.0 (2026-10-21)

### Bug Fixes

- Baseline the config-entry version at 2
  ([`a02b715`](https://github.com/spitsw/ha_pga_rangehood/commit/a02b7159343a5a2e2054c62c8c6f6e24f25d4396))

- Correct device labelling and make the setup menu translatable
  ([`739710c`](https://github.com/spitsw/ha_pga_rangehood/commit/739710cd1242b8e8a2f476fb4579a84565302b5b))

- Harden the MQTT client lifecycle and surface failures
  ([`7478554`](https://github.com/spitsw/ha_pga_rangehood/commit/7478554cf61993a88a473f8d1e02b41e59bd74a2))

- Import the platform modules off the event loop
  ([`09b1f94`](https://github.com/spitsw/ha_pga_rangehood/commit/09b1f94a8d9765211b3c8ad02c48ad0a277e82c9))

### Chores

- **deps**: Update dependency python to 3.15
  ([`fef8b6c`](https://github.com/spitsw/ha_pga_rangehood/commit/fef8b6ca43529912cf50bca6dc2d0b2619f95dc8))

- **deps**: Update dependency ruff to v0.17.1
  ([`11efb24`](https://github.com/spitsw/ha_pga_rangehood/commit/11efb249ccb2fe452b50837b7fd141354b542dd5))

### Documentation

- Correct the MQTT TLS description
  ([`5049d0b`](https://github.com/spitsw/ha_pga_rangehood/commit/5049d0b6586d515016f934c2383c3e83647d5018))

- Lead the HACS install with a search
  ([`e56fb6d`](https://github.com/spitsw/ha_pga_rangehood/commit/e56fb6dc20119b89c449ba992f4eac675648a1bd))

### Features

- Capability-driven entities with confirmed, fresh MQTT state
  ([`99032c9`](https://github.com/spitsw/ha_pga_rangehood/commit/99032c9580440f56c54e79b733625526af64c876))

### Refactoring

- Name the shared classes after the platform, not the brand
  ([`a69b0d2`](https://github.com/spitsw/ha_pga_rangehood/commit/a69b0d22119461ece11e0b705febba2e171506a0))

- Simplify the entity layer and the sensor definitions
  ([`31c80fc`](https://github.com/spitsw/ha_pga_rangehood/commit/31c80fca3f55839efceb924608f46335a01b83a2))


## v1.3.0 (2026-10-13)


## v1.2.0 (2026-10-13)

### Chores

- Rename repository references to ha_pga_rangehood
  ([`d86fedf`](https://github.com/spitsw/ha_pga_rangehood/commit/d86fedf7a51def860dd9d198f68b167e0f152eb8))

- **deps**: Update dependency pytest to v9.1.1
  ([`b168921`](https://github.com/spitsw/ha_pga_rangehood/commit/b168921cd9078241f5557fe4b3cd5cfe140455f5))

- **deps**: Update dependency pytest-homeassistant-custom-component to v0.13.371
  ([`592d06b`](https://github.com/spitsw/ha_pga_rangehood/commit/592d06bcecb039f21f2e0b7ee0a6a7d0af5644d8))

- **deps**: Update dependency ruff to v0.17.0
  ([`bb64aeb`](https://github.com/spitsw/ha_pga_rangehood/commit/bb64aeb85dcb7fb71e666dc6fd02f74f3888506e))

### Documentation

- Add a security policy
  ([`20a877c`](https://github.com/spitsw/ha_pga_rangehood/commit/20a877cd4573cc54aaeb0d48832887e104e6d51d))

### Features

- Add a filter-worn reset button
  ([`f7e0219`](https://github.com/spitsw/ha_pga_rangehood/commit/f7e02193df3e7c5580859876373d76eb17d6dbaf))

- Add secondary filter and light entities
  ([`2340957`](https://github.com/spitsw/ha_pga_rangehood/commit/23409575024f57b1837bb4ab60e6e135ef87c3d3))

- Allow renaming a device from Home Assistant
  ([`551b779`](https://github.com/spitsw/ha_pga_rangehood/commit/551b7793a1f7c02ffaf108d3bed4185dc4c6f7cb))

- Confirm commands via the MQTT response topic
  ([`b51cec5`](https://github.com/spitsw/ha_pga_rangehood/commit/b51cec590d92c6617de8b5bf33f0da0cdf122e5f))

- Support Pando rangehoods alongside Sirius
  ([`cbb4814`](https://github.com/spitsw/ha_pga_rangehood/commit/cbb4814065a59a1183331caa3b1fbe2a8587b255))

- Trigger a minor release
  ([`8eb4095`](https://github.com/spitsw/ha_pga_rangehood/commit/8eb4095a58c7b7caba4fe49b43b4e7c2c8d5ea45))

### Refactoring

- Migrate the MQTT client to aiomqtt
  ([`9a06a30`](https://github.com/spitsw/ha_pga_rangehood/commit/9a06a30aa368b4b30408cb46ac090e4b6766aa70))

- Neutralise endpoint naming and migrate config entry keys
  ([`2916474`](https://github.com/spitsw/ha_pga_rangehood/commit/2916474c670005a4c3bf7c2cbb49181c0b5ae646))


## v1.1.1 (2026-10-03)

### Bug Fixes

- Keep api VERSION in sync with the released version
  ([`32b0b4b`](https://github.com/spitsw/ha_pga_rangehood/commit/32b0b4b39e5b2c14bb3daffbd06e8cb083d096e3))


## v1.1.0 (2026-10-03)

### Continuous Integration

- Harden the release workflow for protected main
  ([`f100dae`](https://github.com/spitsw/ha_pga_rangehood/commit/f100dae08c4012db0b8f135afa51401a41ca8fc6))

### Features

- Trigger a minor release
  ([`1d5a9d1`](https://github.com/spitsw/ha_pga_rangehood/commit/1d5a9d12fa0e3ab3d5b95cda019f88af024513d9))


## v1.0.0 (2026-10-03)

- Initial Release
