#!/usr/bin/env python3
"""Redact private PVS discovery captures into commit-safe fixtures."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def redact_obj(obj: Any, pvs_serial: str) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if key.upper() == "SERIAL" or key == "sn" or str(key).endswith("/sn"):
                out[key] = "SERIAL_REDACTED"
            else:
                out[key] = redact_obj(value, pvs_serial)
        return out
    if isinstance(obj, list):
        return [redact_obj(item, pvs_serial) for item in obj]
    if isinstance(obj, str):
        if obj == pvs_serial:
            return "PVS_SERIAL_REDACTED"
        if re.fullmatch(r"E00\d{12}", obj):
            return "INVERTER_SERIAL_REDACTED"
        if re.fullmatch(r"PVS6M\d{8,}[pc]", obj):
            return "METER_SERIAL_REDACTED"
        if re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", obj):
            return "00:00:00:00:00:00"
        return obj
    return obj


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--private-dir",
        type=Path,
        default=Path("docs/discovery/private"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("fixtures/pvs6"),
    )
    args = parser.parse_args()

    supervisor = json.loads(
        (args.private_dir / "supervisor-info.raw.json").read_text(encoding="utf-8")
    )
    pvs_serial = supervisor["supervisor"]["SERIAL"]
    mapping = {
        "supervisor-info.raw.json": "supervisor-info.json",
        "vars-sw-rev.raw.json": "vars-sw-rev.json",
        "vars-livedata.raw.json": "vars-livedata.json",
        "vars-meter.raw.json": "vars-meter.json",
        "vars-inverter.raw.json": "vars-inverter.json",
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for src, dest in mapping.items():
        data = json.loads((args.private_dir / src).read_text(encoding="utf-8"))
        text = json.dumps(redact_obj(data, pvs_serial), indent=2) + "\n"
        if pvs_serial in text:
            raise SystemExit(f"refusing to write {dest}: serial still present")
        (args.out_dir / dest).write_text(text, encoding="utf-8")
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
