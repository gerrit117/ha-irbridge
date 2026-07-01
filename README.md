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
- Optional bundled SmartIR-compatible codepack selection

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

## SmartIR-Compatible Codepacks

IRBridge can use bundled SmartIR-style JSON codepacks from:

```text
custom_components/irbridge/codepacks/
```

Folder format:

```text
custom_components/irbridge/codepacks/
  climate/
    1000.json
  media_player/
    1000.json
  fan/
    1000.json
  light/
    1000.json
```

Each JSON file must include these basic fields:

```json
{
  "manufacturer": "Example",
  "supportedModels": ["Example Model"],
  "commandsEncoding": "Base64",
  "supportedController": "Broadlink",
  "commands": {
    "on": "...",
    "off": "..."
  }
}
```

When using a bundled codepack, IRBridge stores only the selected codepack type and code ID in the config entry. Commands are loaded from the bundled JSON file at runtime.

The current bundled database is SmartIR-compatible and mostly uses Broadlink Base64 command strings. IRBridge currently forwards those stored strings as-is to the configured MQTT IR backend using `ir_code_to_send`.

Simple command aliases are supported for service calls, including `on`, `off`, `power`, `volumeUp`, `volumeDown`, `volume_up`, `volume_down`, and `mute`.

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
- Codepack commands are assumed to be compatible with your Zigbee2MQTT IR blaster payload format
- Bundled SmartIR codepacks are currently treated as Broadlink Base64 payloads and are not converted
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
