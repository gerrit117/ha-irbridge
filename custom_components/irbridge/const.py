"""Constants for the IRBridge integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "irbridge"
NAME: Final = "IRBridge"
VERSION: Final = "0.1.0"

PLATFORMS: Final = [
    "remote",
    "button",
    "climate",
    "media_player",
    "fan",
    "light",
    "switch",
]

CONF_COMMANDS: Final = "commands"
CONF_CODEPACK_DEVICE_TYPE: Final = "codepack_device_type"
CONF_CODEPACK_ID: Final = "codepack_id"
CONF_CODEPACK_MANUFACTURER: Final = "codepack_manufacturer"
CONF_CODEPACK_PATH: Final = "codepack_path"
CONF_CODEPACK_SOURCE: Final = "codepack_source"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_FRIENDLY_NAME: Final = "friendly_name"
CONF_IR_BLASTER_DEVICE_ID: Final = "ir_blaster_device_id"
CONF_IR_BLASTER_SELECTOR: Final = "ir_blaster"
CONF_MQTT_TOPIC: Final = "mqtt_topic"
CONF_SETUP_MODE: Final = "setup_mode"
CONF_VIRTUAL_NAME: Final = "virtual_name"

DEVICE_TYPE_GENERIC: Final = "generic"
DEVICE_TYPE_CLIMATE: Final = "climate"
DEVICE_TYPE_FAN: Final = "fan"
DEVICE_TYPE_LIGHT: Final = "light"
DEVICE_TYPE_MEDIA_PLAYER: Final = "media_player"
DEVICE_TYPES: Final = [
    DEVICE_TYPE_GENERIC,
    DEVICE_TYPE_CLIMATE,
    DEVICE_TYPE_FAN,
    DEVICE_TYPE_LIGHT,
    DEVICE_TYPE_MEDIA_PLAYER,
]
CODEPACK_DEVICE_TYPES: Final = [
    DEVICE_TYPE_CLIMATE,
    DEVICE_TYPE_MEDIA_PLAYER,
    DEVICE_TYPE_FAN,
    DEVICE_TYPE_LIGHT,
]

CODEPACK_SOURCE_BUNDLED: Final = "bundled"
CODEPACK_SOURCE_CUSTOM: Final = "custom"
CUSTOM_CODEPACK_DIR: Final = "custom_codes"

SETUP_MODE_MANUAL: Final = "manual"
SETUP_MODE_CODEPACK: Final = "codepack"
SETUP_MODES: Final = [SETUP_MODE_MANUAL, SETUP_MODE_CODEPACK]

MANUAL_IR_BLASTER_SELECTOR: Final = "__manual__"

DEFAULT_COMMANDS: Final = {
    "power": "",
    "volume_up": "",
    "volume_down": "",
    "mute": "",
}

SERVICE_SEND_COMMAND: Final = "send_command"

ATTR_DEVICE: Final = "device"
ATTR_COMMAND: Final = "command"
ATTR_FRIENDLY_NAME: Final = "friendly_name"
ATTR_DEVICE_TYPE: Final = "device_type"

MQTT_TOPIC_TEMPLATE: Final = "zigbee2mqtt/{friendly_name}/set"
MQTT_PAYLOAD_KEY: Final = "ir_code_to_send"
