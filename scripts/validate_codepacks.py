"""Validate bundled IRBridge codepacks without importing Home Assistant."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CODEPACKS_DIR = ROOT / "custom_components" / "irbridge" / "codepacks"
REQUIRED_FIELDS = {"commands"}


def validate_codepack(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return basic SmartIR-style codepack validation errors and warnings."""
    errors: list[str] = []
    warnings: list[str] = []
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        errors.append(f"missing fields: {', '.join(sorted(missing))}")

    if not isinstance(data.get("manufacturer"), str) or not data.get("manufacturer"):
        warnings.append("manufacturer is missing or invalid")
    if not isinstance(data.get("supportedModels"), list):
        warnings.append("supportedModels is missing or invalid")
    if not isinstance(data.get("commands"), dict):
        errors.append("commands must be an object")
    if not isinstance(data.get("commandsEncoding"), str) or not data.get(
        "commandsEncoding"
    ):
        warnings.append("commandsEncoding is missing or invalid")
    if not isinstance(data.get("supportedController"), str) or not data.get(
        "supportedController"
    ):
        warnings.append("supportedController is missing or invalid")
    return errors, warnings


def main() -> int:
    """Validate all bundled codepacks."""
    counts: Counter[str] = Counter()
    invalid: list[tuple[Path, str]] = []
    warnings: list[tuple[Path, str]] = []

    for path in sorted(CODEPACKS_DIR.rglob("*.json")):
        relative_path = path.relative_to(CODEPACKS_DIR)
        if "__MACOSX" in path.parts or path.name.startswith("._"):
            invalid.append((relative_path, "macOS metadata file"))
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            invalid.append((relative_path, f"JSON error: {err}"))
            continue

        if not isinstance(data, dict):
            invalid.append((relative_path, "root must be an object"))
            continue

        errors, codepack_warnings = validate_codepack(data)
        if errors:
            invalid.append((relative_path, "; ".join(errors)))
            continue
        if codepack_warnings:
            warnings.append((relative_path, "; ".join(codepack_warnings)))

        counts[relative_path.parts[0]] += 1

    print(f"Valid codepacks: {sum(counts.values())}")
    for device_type, count in sorted(counts.items()):
        print(f"- {device_type}: {count}")
    print(f"Codepack warnings: {len(warnings)}")

    if invalid:
        print(f"Invalid codepacks: {len(invalid)}")
        for path, reason in invalid:
            print(f"- {path}: {reason}")
        return 1

    print("Invalid codepacks: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
