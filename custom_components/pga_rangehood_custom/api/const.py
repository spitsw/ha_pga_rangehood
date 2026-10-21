# Copyright (c) 2026 Warren Spits
"""Constants for the PGA rangehood API layer."""

VERSION = "1.3.0"

# API endpoints
API_LOGIN = "/users/login"
API_DEVICES = "/devices/"
API_SET_VALUE = "/devices/{device_id}/set_value"
API_RENAME = "/devices/{device_id}/rename"

# Property IDs (from properties[]) — static configuration data
PROP_DEVICE_NAME = "property.device_name"
PROP_DEVICE_REF = "property.device.ref"
PROP_DEVICE_TYPE = "property.device.type"
PROP_DEVICE_CLASS = "property.device_class"
PROP_FW_CODE = "property.device.fw.code"
PROP_FW_VERSION = "property.device.fw.version"
PROP_SECURE_ID = "property.device.secureId"
PROP_RSSI = "property.device.network.rssi"
PROP_SSID = "property.device.network.ssid"
PROP_IP_ADDRESS = "property.device.network.address"

# Capability UIDs (from capabilities[].capabilityUid) — live operational data
CAP_POWER = "device.onOff"
CAP_FAN_SPEED = "device.fanSpeed"
CAP_LIGHT_ONOFF = "device.lightOnOff"
CAP_TIMER_VALUE = "device.timerValue"
CAP_FILTER_WORN = "device.filter1.worn"
CAP_FILTER_VALUE = "device.filter1Value"
CAP_TIMER_ACTIVE = "device.timer.active"
CAP_TIMER_ENABLE = "device.timer.enable"
CAP_BI_POWER_ENABLED = "device.biPowerEnabled"
CAP_LIGHT_BRIGHTNESS = "device.lightBrightness"
CAP_TIMER_MODIFIABLE = "device.timer.modifiable"
CAP_LIGHT_COLOR_TEMP = "device.lightColorTemperature"
CAP_LIGHT_POWER = "device.lightPower"
CAP_FILTER2_WORN = "device.filter2.worn"
CAP_FILTER2_VALUE = "device.filter2Value"
CAP_LIGHT2_ONOFF = "device.light2OnOff"
CAP_LIGHT2_BRIGHTNESS = "device.light2Brightness"
CAP_LIGHT2_COLOR_TEMP = "device.light2ColorTemperature"
CAP_LIGHT2_POWER = "device.light2Power"
CAP_FAN_POWER = "device.fanPower"
CAP_HOOD_POWER = "device.hoodPower"
CAP_FAN_FLOW = "device.fanFlow"
CAP_CLEAN_AIR_ENABLED = "device.cleanAirEnabled"

# Capabilities the integration is permitted to write via setValue.
WRITABLE_CAPABILITIES = frozenset(
    {
        CAP_POWER,
        CAP_FAN_SPEED,
        CAP_LIGHT_ONOFF,
        CAP_LIGHT_BRIGHTNESS,
        CAP_LIGHT_COLOR_TEMP,
        CAP_LIGHT2_ONOFF,
        CAP_LIGHT2_BRIGHTNESS,
        CAP_LIGHT2_COLOR_TEMP,
        CAP_BI_POWER_ENABLED,
        CAP_CLEAN_AIR_ENABLED,
        CAP_TIMER_ACTIVE,
        CAP_TIMER_VALUE,
        CAP_FILTER_WORN,
    }
)

# Fan speed values; the range is taken from each device's limits at runtime.
FAN_SPEED_OFF = 0
FAN_SPEED_LOW = 1
FAN_SPEED_BOOST = 4

# Light brightness: API range 10-100 percent
LIGHT_BRIGHTNESS_MIN = 10
LIGHT_BRIGHTNESS_MAX = 100

# Light colour temperature: API returns/sets Kelvin directly
LIGHT_COLOR_TEMP_KELVIN_MIN = 2700
LIGHT_COLOR_TEMP_KELVIN_MAX = 6000

# API request timeout
API_TIMEOUT = 10

# Default server endpoints per provider (Sirius / Pando)
DEFAULT_SIRIUS_ENDPOINT = "https://sirius.iotpga.it"
DEFAULT_SIRIUS_MQTTS_ENDPOINT = "mqtts://sirius.iotpga.it:8884"
DEFAULT_PANDO_ENDPOINT = "https://pando.iotpga.it"
DEFAULT_PANDO_MQTTS_ENDPOINT = "mqtts://pando.iotpga.it:8883"

# MQTT topic tenants. The status topic is
# ``root/{tenant}/devices/{uid}/status`` — the tenant differs per provider.
SIRIUS_MQTT_TENANT = "codermine"
PANDO_MQTT_TENANT = "pando"

# Heartbeat interval — sends getStatus to trigger MQTT refresh (seconds)
GET_STATUS_INTERVAL = 300
