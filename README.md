# IRBridge

IRBridge is a Home Assistant HACS custom integration for creating virtual infrared-controlled devices that send commands through local IR blasters.

The first target backend is Zigbee2MQTT-compatible IR blasters such as TS1201, ZS06, and UFO-R11. Future backends may include ESPHome IR devices and Broadlink, while keeping control fully local.

## Why IRBridge Exists

Many infrared integrations start from a database of known devices. IRBridge starts from the transport: if Home Assistant can publish an IR code to a local blaster, IRBridge can expose a virtual device around it.

The goal is to make manual IR command mapping, learning, testing, import/export, and virtual device entities feel native in Home Assistant.

## IRBridge vs SmartIR

SmartIR focuses on ready-made device code libraries and predefined entity behavior.

IRBridge is intended to focus on local IR transports, user-owned command mappings, and future importers. SmartIR compatibility and importing are planned, but not part of v0.1.

## Integration vs Add-on

IRBridge is not a Home Assistant add-on. It does not run a separate container or service.

IRBridge is a custom integration installed under:

```text
custom_components/irbridge/
```

It loads inside Home Assistant and uses the existing MQTT integration to publish commands.

## Current MVP

Version 0.1 provides:

- UI config flow
- One virtual remote entity per config entry
- Button entities for configured commands
- `irbridge.send_command` service
- MQTT publishing to Zigbee2MQTT-style IR blasters
- Local config entry storage for command mappings

Configurable commands in v0.1:

```json
{
  "power": "...",
  "volume_up": "...",
  "volume_down": "...",
  "mute": "..."
}
```

## HACS Installation

1. Open HACS.
2. Add `https://github.com/gerrit117/ha-irbridge` as a custom repository.
3. Choose category `Integration`.
4. Install IRBridge.
5. Restart Home Assistant.
6. Add IRBridge from Settings > Devices & services.

## Manual Installation

1. Copy `custom_components/irbridge` into your Home Assistant configuration directory.
2. Restart Home Assistant.
3. Add IRBridge from Settings > Devices & services.

## Zigbee2MQTT Payload

For a Zigbee2MQTT friendly name of `living_room_ir`, IRBridge publishes to:

```text
zigbee2mqtt/living_room_ir/set
```

Payload:

```json
{
  "ir_code_to_send": "<stored_code>"
}
```

You can override the MQTT topic in the config flow if your backend uses a different topic.

## Service Example

```yaml
service: irbridge.send_command
data:
  device: Living Room TV
  command: power
```

The `device` field accepts the virtual device name, Zigbee2MQTT friendly name, or config entry ID.

## Current Limitations

- No IR learning UI yet
- No SmartIR importing yet
- No real device feedback
- Assumed state only
- Climate and media player device types are stored for future use but do not create full `ClimateEntity` or `MediaPlayerEntity` platforms yet

## Roadmap

### Phase 1

- Zigbee2MQTT TS1201/ZS06/UFO-R11 support
- Generic remote/button devices
- Manual command mapping

### Phase 2

- IR learning support
- Command testing UI
- Import/export code packs

### Phase 3

- ClimateEntity support
- MediaPlayerEntity support
- FanEntity support
- Switch/Button entities

### Phase 4

- SmartIR importer
- LIRC/Pronto/Broadlink/Tuya converters
- Community code packs
