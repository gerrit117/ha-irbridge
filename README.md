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
- ClimateEntity support for bundled SmartIR climate codepacks
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

Each JSON file must include a `commands` object. IRBridge also reads SmartIR metadata when present:

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

The bundled database is SmartIR-compatible and includes multiple controller/encoding variants, including Broadlink Base64, MQTT Raw, ESPHome Raw, Xiaomi Raw, LOOKin Raw, and Pronto-style packs. IRBridge normalizes these internally with compatibility types such as `broadlink_base64`, `mqtt_raw`, `z2m_base64`, and `esphome_raw`.

For Broadlink/Base64-style packs, IRBridge publishes:

```json
{
  "ir_code_to_send": "<stored_code>"
}
```

For MQTT Raw packs whose command value is already a JSON payload string, IRBridge publishes that payload directly.

Simple command aliases are supported for service calls, including `on`, `off`, `power`, `volumeUp`, `volumeDown`, `volume_up`, `volume_down`, and `mute`.

## Climate Codepacks

When you select a bundled `climate` codepack, IRBridge creates a real Home Assistant `ClimateEntity` for the virtual air conditioner.

IRBridge reads SmartIR climate fields when present:

- `minTemperature`
- `maxTemperature`
- `precision`
- `operationModes`
- `fanModes`
- `swingModes`
- `commands`

Climate commands are resolved from SmartIR-style nested command trees, such as mode -> fan -> swing -> temperature. Temperature keys may be strings or numbers. If a fan or swing mode is needed but the exact command is missing, IRBridge raises an error instead of sending a guessed command.

IR-controlled devices usually provide no feedback. Climate entities therefore use assumed state and restore the last known mode, target temperature, fan mode, and swing mode after Home Assistant restarts.

### Climate Test Procedure

1. Call `climate.turn_off` and confirm the air conditioner turns off.
2. Set HVAC mode to `cool` with a supported temperature.
3. Change the target temperature by one supported step.
4. Change fan mode if the codepack exposes fan modes.
5. Change swing mode if the codepack exposes swing modes.

### Troubleshooting Climate Commands

- Confirm the selected codepack has an `off` command.
- Confirm the selected HVAC mode exists in `operationModes` and `commands`.
- Confirm the target temperature exists in the nested command tree.
- Confirm the selected fan/swing mode exists for that HVAC mode and temperature.
- MQTT Raw codepacks must contain command payload strings that are valid JSON if they should be published directly.

## Service Example

```yaml
service: irbridge.send_command
data:
  device: Living Room TV
  command: power
```

The `device` field accepts the virtual device name, Zigbee2MQTT friendly name, or config entry ID.

## Zigbee2MQTT IR Blaster Discovery

During setup, IRBridge looks at the Home Assistant device and entity registries for MQTT/Zigbee2MQTT devices that look like local IR blasters. Known device hints include TS1201, ZS06, UFO-R11, infrared, IR, remote, blaster, `ir_code_to_send`, `learn_ir_code`, and `learned_ir_code`.

The registry is only used for discovery and better setup UX. IRBridge still sends commands by publishing directly to MQTT.

If a device is not discovered, choose `Manual MQTT topic` and enter either the Zigbee2MQTT friendly name or the full MQTT set topic.

## Current Limitations

- No IR learning UI yet
- No SmartIR importing yet
- No real device feedback
- Assumed state only
- Codepack commands must be compatible with your Zigbee2MQTT IR blaster payload format
- IRBridge does not yet convert between Broadlink Base64, Pronto, ESPHome raw, and Tuya/Zigbee2MQTT raw formats
- Registry discovery uses heuristics and may miss unusually named IR blasters
- Media player, fan, and light codepack device types are stored for future use but do not create full entity platforms yet

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
