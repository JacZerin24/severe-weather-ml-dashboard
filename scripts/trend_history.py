#!/usr/bin/env python3
"""Preserve locally generated NADOCast CWA forecast cycles between Pages builds.

GitHub Pages deploys a brand-new site directory on every run. This module
stores a bounded, per-CWA snapshot archive in a GitHub Actions cache, then
publishes only existing frames into the site's static directory.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

HAZARDS = ("tornado", "wind_adj", "hail")
DAYS = ("day1", "day2")
RUN_HOURS = {"t0z": 0, "t00z": 0, "t10z": 10, "t12z": 12, "t14z": 14, "t18z": 18, "t20z": 20}


def safe_filename(day: str, hazard: str, product: dict) -> str:
    date = str(product.get("run_date", ""))
    run = str(product.get("run_dir", "")).lower()
    lead = str(product.get("lead_label", ""))
    if not re.fullmatch(r"\d{8}", date) or run not in RUN_HOURS or not re.fullmatch(r"f\d{1,3}(?:-\d{1,3})?", lead):
        raise ValueError(f"Unexpected run identifiers: {date}, {run}, {lead}")
    return f"{day}_{hazard}_{date}_{run}_{lead}.png"


def sort_key(frame: dict) -> tuple:
    return (
        str(frame.get("run_date", "")),
        RUN_HOURS.get(str(frame.get("run_dir", "")).lower(), -1),
        str(frame.get("lead_label", "")),
    )


def update_cwa_trends(manifest_path: Path, archive_root: Path, max_frames: int = 4) -> dict:
    """Update the archived recent frames and publish them beside latest.json.

    All displayed images exist in the currently deployed Pages artifact. A
    repeated build of the same forecast run does not duplicate the timeline.
    """
    if max_frames < 1:
        raise ValueError("max_frames must be at least one")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cwa = manifest["cwa"]
    archive_dir = archive_root / cwa
    archive_dir.mkdir(parents=True, exist_ok=True)
    history_file = archive_dir / "history.json"
    try:
        history = json.loads(history_file.read_text(encoding="utf-8")) if history_file.exists() else {}
    except (OSError, json.JSONDecodeError):
        history = {}

    for day in DAYS:
        day_history = history.setdefault(day, {})
        products = manifest.get("products", {}).get(day, {})
        for hazard in HAZARDS:
            entries = day_history.get(hazard, [])
            # Retain only cache entries that still have a corresponding image.
            entries = [entry for entry in entries if (archive_dir / Path(str(entry.get("image", ""))).name).is_file()
                       and entry.get("image") and not Path(str(entry["image"])).is_absolute()]
            current = products.get(hazard)
            if current:
                filename = safe_filename(day, hazard, current)
                src = manifest_path.parent / current["image"]
                if not src.is_file():
                    raise FileNotFoundError(f"Generated NADOCast map absent: {src}")
                shutil.copy2(src, archive_dir / filename)
                entry = {k: current.get(k) for k in (
                    "hazard", "run_date", "run_dir", "lead_label",
                    "max_cwa", "mean_cwa", "max_buffer")}
                entry["image"] = filename
                # Replace duplicate run/lead combinations rather than appending.
                entries = [e for e in entries if safe_filename(day, hazard, e) != filename]
                entries.append(entry)
            entries.sort(key=sort_key, reverse=True)
            day_history[hazard] = entries[:max_frames]

    # Delete unreferenced files to keep workflow caches bounded.
    retained = {
        e["image"] for day in DAYS for hazard in HAZARDS
        for e in history[day].get(hazard, [])
    }
    for path in archive_dir.glob("*.png"):
        if path.name not in retained:
            path.unlink()

    published = {}
    out_history = manifest_path.parent / "history"
    out_history.mkdir(exist_ok=True)
    for day in DAYS:
        published[day] = {}
        for hazard in HAZARDS:
            frames = []
            for entry in history[day].get(hazard, []):
                src = archive_dir / entry["image"]
                if not src.is_file():
                    continue
                shutil.copy2(src, out_history / src.name)
                frames.append({**entry, "image": "history/" + src.name})
            if frames:
                published[day][hazard] = frames

    history_file.write_text(json.dumps(history, indent=2), encoding="utf-8")
    manifest["trends"] = published
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
