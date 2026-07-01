"""Validate basic IRBridge climate command resolution without Home Assistant."""

from __future__ import annotations

import importlib.util
import logging
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEPACKS = ROOT / "custom_components" / "irbridge" / "codepacks" / "climate"


def _load_codepacks_module():
    """Load codepack helpers with a tiny Home Assistant exception stub."""
    homeassistant = types.ModuleType("homeassistant")
    exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        """Stub Home Assistant error."""

    exceptions.HomeAssistantError = HomeAssistantError
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.exceptions"] = exceptions

    package = types.ModuleType("custom_components.irbridge")
    package.__path__ = [str((ROOT / "custom_components" / "irbridge").resolve())]
    sys.modules["custom_components.irbridge"] = package

    spec = importlib.util.spec_from_file_location(
        "custom_components.irbridge.codepacks",
        ROOT / "custom_components" / "irbridge" / "codepacks.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    """Validate default climate command resolution for bundled climate packs."""
    logging.disable(logging.CRITICAL)
    codepacks = _load_codepacks_module()
    checked = 0
    failures: list[str] = []

    for path in sorted(CODEPACKS.glob("*.json")):
        checked += 1
        try:
            data = codepacks.load_codepack("climate", path.stem)
            climate = codepacks.parse_climate_codepack(data)
            codepacks.resolve_climate_command(data, "off", None, None, None)
            mode = (
                "cool"
                if "cool" in climate.operation_modes
                else climate.operation_modes[0]
            )
            fan = climate.fan_modes[0] if climate.fan_modes else None
            swing = climate.swing_modes[0] if climate.swing_modes else None
            codepacks.resolve_climate_command(
                data, mode, climate.min_temperature, fan, swing
            )
        except Exception as err:
            failures.append(f"{path.name}: {err}")

    print(f"Checked climate codepacks: {checked}")
    print(f"Default resolution failures: {len(failures)}")
    for failure in failures[:50]:
        print(f"- {failure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
