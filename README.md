# IRBridge

IRBridge is a Home Assistant HACS custom integration for creating virtual infrared-controlled devices that send commands through local IR blasters.

The current backend publishes directly to MQTT for Zigbee2MQTT-compatible IR blasters such as TS1201, ZS06, and UFO-R11. Future backends may include ESPHome IR devices, Broadlink, and Home Assistant native IR support while keeping control fully local.

## What Problem It Solves

Many IR-controlled devices still work well, but their original remotes are awkward to automate. IRBridge lets Home Assistant expose those devices as virtual entities backed by stored IR codes.

You can start with manual commands, select bundled SmartIR-compatible codepacks, or add your own custom SmartIR-style JSON files without editing IRBridge source files.

## How it works

IRBridge focuses on the transport and workflow around local IR blasters:

- direct local MQTT publishing
- Zigbee2MQTT IR blaster discovery
- manual command mapping
- bundled SmartIR-compatible codepacks
- user-provided custom codepacks
- future IR learning, import, export, and conversion workflows

IRBridge includes and builds upon SmartIR-style code definitions, but it is not a drop-in replacement for every SmartIR feature.

## Supported Backends

Current backend:

```text
IRBridge entity
-> IRBridge backend abstraction
-> MQTT
-> Zigbee2MQTT
-> IR blaster
```

Currently targeted IR blasters:

- Zigbee2MQTT TS1201
- Zigbee2MQTT ZS06
- Zigbee2MQTT UFO-R11

Planned future backends:

- Home Assistant native IR backends
- ESPHome IR
- Broadlink

Native Home Assistant InfraredEntity support is not implemented yet. The backend structure is intentionally kept modular so it can be added later.

## Installation With HACS

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

## Quick Start

1. Make sure the Home Assistant MQTT integration is configured.
2. Pair your Zigbee2MQTT IR blaster.
3. Add IRBridge from Settings > Devices & services.
4. Select a discovered IR blaster, or use the manual Zigbee2MQTT friendly name/topic fallback.
5. Choose either manual commands or a codepack.
6. For codepacks, select device type, manufacturer, and model/code ID.
7. Finish setup and test the created entities or `irbridge.send_command`.

If a device is not discovered, choose the manual fallback and enter either the Zigbee2MQTT friendly name or the full MQTT set topic.

## MQTT Payload

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

For MQTT Raw codepacks whose command value is already a JSON payload string, IRBridge publishes that payload directly.

## Manual Commands

Manual mode stores command mappings in the config entry.

Example:

```json
{
  "power": "...",
  "volume_up": "...",
  "volume_down": "...",
  "mute": "..."
}
```

Simple aliases are supported for service calls and entity actions, including `on`, `off`, `power`, `volume_up`, `volumeDown`, `mute`, `play`, `pause`, `stop`, `next`, `previous`, `brighten`, and `dim`.

## Bundled Codepacks

Bundled SmartIR-compatible codepacks live in:

```text
custom_components/irbridge/codepacks/
  climate/
  media_player/
  fan/
  light/
```

Each JSON file should follow the SmartIR-style format:

```json
{
  "manufacturer": "Example",
  "supportedModels": ["Example Model"],
  "supportedController": "Broadlink",
  "commandsEncoding": "Base64",
  "commands": {
    "on": "...",
    "off": "..."
  }
}
```

IRBridge validates the `commands` object and reads SmartIR metadata when present. Optional fields are handled gracefully and logged as warnings instead of crashing Home Assistant.

When a bundled codepack is selected, IRBridge stores only the codepack reference in the config entry. Commands are loaded from the JSON file at runtime.

## Custom Codepacks

User-provided SmartIR-style codepacks can be added without modifying IRBridge source files.

Create this folder structure in your Home Assistant config directory:

```text
config/custom_codes/
  climate/
  media_player/
  fan/
  light/
```

Then copy JSON files into the matching device type folder:

```text
config/custom_codes/climate/my_ac.json
config/custom_codes/media_player/my_tv.json
config/custom_codes/fan/my_fan.json
config/custom_codes/light/my_light.json
```

Restart Home Assistant or reload IRBridge, then add a new IRBridge device and choose the custom codepack. Custom entries appear in the same codepack picker and are marked like:

```text
Custom: Mitsubishi Electric MSY-GM18VA (my_ac) [Broadlink Base64]
```

If a custom codepack has the same device type, manufacturer, and supported models as a bundled one, IRBridge prefers the custom codepack.

Invalid custom JSON files are skipped with log warnings. They should not crash Home Assistant.

## Entity Creation

IRBridge always keeps the generic RemoteEntity and command ButtonEntities available where commands exist.

Codepack device types create native entities when the structure is suitable:

- `climate` -> ClimateEntity
- `media_player` -> MediaPlayerEntity when common media commands are available
- `fan` -> FanEntity when speed commands are available
- `light` -> LightEntity when clear on/off commands are available
- fallback -> ButtonEntities and, for simple fan on/off codepacks, SwitchEntity

If a codepack cannot be represented cleanly as a native Home Assistant entity, IRBridge does not force a bad abstraction. The raw command buttons remain available.

## Climate Codepacks

Climate codepacks create a Home Assistant ClimateEntity.

IRBridge reads these SmartIR fields when present:

- `manufacturer`
- `supportedModels`
- `minTemperature`
- `maxTemperature`
- `precision`
- `operationModes`
- `fanModes`
- `swingModes`
- `commands`

Commands are resolved from SmartIR-style nested command trees such as mode -> fan -> swing -> temperature. Temperature keys may be strings or numbers. If the exact command cannot be resolved, IRBridge raises a clear Home Assistant error and does not send a guessed command.

### Climate Test Procedure

1. Test `climate.turn_off`.
2. Set HVAC mode to `cool` with a supported temperature.
3. Change the target temperature by one supported step.
4. Test fan mode if the codepack exposes fan modes.
5. Test swing mode if the codepack exposes swing modes.

### Troubleshooting Climate Commands

- Confirm the selected codepack has an `off` command.
- Confirm the selected HVAC mode exists in `operationModes` and `commands`.
- Confirm the target temperature exists in the nested command tree.
- Confirm the selected fan/swing mode exists for that HVAC mode and temperature.
- Confirm your IR blaster can send the code format used by the selected codepack.

## Media Player Codepacks

Media player codepacks create a MediaPlayerEntity when common commands are present.

Supported command families include:

- `on`, `off`, `power`
- `volumeUp`, `volumeDown`, `mute`
- `play`, `pause`, `stop`
- `previousChannel`, `nextChannel`, previous/next track variants
- `sources` for input/source selection when source commands are strings

Source entries that are lists or empty strings remain available only through future import/normalization work.

## Fan Codepacks

Fan codepacks create a FanEntity when IRBridge can identify speed commands.

Supported structures include flat speed commands and SmartIR-style directional speed maps such as:

```json
{
  "speed": ["low", "medium", "high"],
  "commands": {
    "off": "...",
    "forward": {
      "low": "...",
      "medium": "...",
      "high": "..."
    }
  }
}
```

Simple fan codepacks with only clear `on` and `off` commands can fall back to a SwitchEntity and command buttons.

## Light Codepacks

Light codepacks create an on/off LightEntity when clear `on` and `off` commands are present.

Many IR light remotes expose relative commands such as `brighten`, `dim`, `warmer`, or `colder` instead of absolute brightness/color values. Those commands remain available as buttons. Absolute brightness and color mode support will be added only when the codepack structure can be mapped reliably.

## Service Example

```yaml
service: irbridge.send_command
data:
  device: Living Room TV
  command: power
```

The `device` field accepts the virtual device name, Zigbee2MQTT friendly name, or config entry ID.

## Zigbee2MQTT IR Blaster Discovery

During setup, IRBridge looks at the Home Assistant device and entity registries for MQTT/Zigbee2MQTT devices that look like local IR blasters. Known hints include TS1201, ZS06, UFO-R11, infrared, IR, remote, blaster, `ir_code_to_send`, `learn_ir_code`, and `learned_ir_code`.

The registry is only used for discovery and better setup UX. IRBridge still sends commands by publishing directly to MQTT.

## Assumed State And Feedback Limits

IR devices normally do not report real state back to Home Assistant.

IRBridge entities therefore use assumed state:

- Home Assistant state changes after IRBridge successfully publishes a command.
- IRBridge cannot know if the real device received the command.
- IRBridge cannot know if someone used the original remote.
- Restored state after restart is the last assumed Home Assistant state, not confirmed device state.

## Current Limitations

- No real device feedback
- Assumed state only
- No IR learning UI yet
- No command testing UI yet
- No SmartIR folder import UI yet
- No export of learned commands yet
- No automatic conversion between Broadlink, LIRC, Pronto, Tuya, ESPHome raw, and Zigbee2MQTT raw formats yet
- Codepack command format must be compatible with your IR blaster/backend
- Registry discovery uses heuristics and may miss unusually named IR blasters

## Adding More Codes

For personal use:

1. Add SmartIR-compatible JSON files to `config/custom_codes/<device_type>/`.
2. Restart Home Assistant or reload IRBridge.
3. Select the new codepack in the IRBridge config flow.

To contribute codes upstream:

- Open a GitHub issue with device type, manufacturer, model, remote control model if known, tested commands, and the JSON file.
- Or open a pull request adding the codepack to `custom_components/irbridge/codepacks/<device_type>/`.

Submitted codes should be tested on real hardware whenever possible.

## Future Code Workflow TODOs

- UI-based IR learning
- Exporting learned commands as SmartIR-style JSON
- Importing SmartIR folders directly
- Converting Broadlink/LIRC/Pronto/Tuya/ESPHome/Zigbee2MQTT formats where possible
- Community codepack review and sharing workflow


## Acknowledgements

IRBridge includes and builds upon IR code definitions originally created
by the SmartIR project and its contributors.

Huge thanks to the SmartIR community for maintaining the extensive IR
device database over the years.

SmartIR:
https://github.com/smartHomeHub/SmartIR
