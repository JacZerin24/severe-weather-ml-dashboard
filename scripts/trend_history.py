#!/usr/bin/env python3
"""Persist NADOCast CWA history by actual UTC outlook valid date (12Z–12Z).

The cache may contain older day1/day2-keyed entries. Migrate them by
recomputing valid dates from initialization and forecast lead, not old labels.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

from forecast_validity import RUN_HOURS, annotate

HAZARDS = ("tornado", "wind_adj", "hail")
FRAME_FIELDS = (
    "hazard", "run_date", "run_dir", "lead_label",
    "max_cwa", "mean_cwa", "max_buffer",
    "valid_date", "valid_start_utc", "valid_end_utc",
    "outlook_start_utc", "outlook_end_utc", "init_utc",
)


def safe_filename(hazard: str, item: dict) -> str:
    valid = str(item.get("valid_date", ""))
    date = str(item.get("run_date", ""))
    run = str(item.get("run_dir", "")).lower()
    lead = str(item.get("lead_label", ""))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valid) or not re.fullmatch(r"\d{8}", date):
        raise ValueError("Invalid NADOCast date identifier")
    if run not in RUN_HOURS or not re.fullmatch(r"f\d{1,3}-\d{1,3}", lead):
        raise ValueError("Invalid NADOCast run or lead identifier")
    if hazard not in HAZARDS:
        raise ValueError("Invalid NADOCast hazard")
    return f"{valid}_{hazard}_{date}_{run}_{lead}.png"


def sort_key(frame: dict) -> tuple:
    return (frame["init_utc"], frame["valid_start_utc"], frame["lead_label"])


def update_cwa_trends(
    manifest_path: Path,
    archive_root: Path,
    max_frames: int = 4,
    *,
    today: dt.date | None = None,
) -> dict:
    """Preserve latest N valid-date-matched model cycles per hazard.

    Only valid periods matching today's or future 12Z-based outlook date
    appear on the dashboard. Cached imagery for yesterday is retained briefly
    for midnight rollover, never shown for today's outlook.
    """
    if max_frames < 1:
        raise ValueError("max_frames must be at least one")
    today = today or dt.datetime.now(dt.timezone.utc).date()
    allowed_dates = {
        (today + dt.timedelta(days=offset)).isoformat()
        for offset in (-1, 0, 1, 2)
    }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive_dir = archive_root / manifest["cwa"]
    archive_dir.mkdir(parents=True, exist_ok=True)
    history_file = archive_dir / "history.json"
    try:
        existing = json.loads(history_file.read_text(encoding="utf-8")) if history_file.exists() else {}
    except (OSError, json.JSONDecodeError):
        existing = {}

    frames_by_date: dict[str, dict[str, list[dict]]] = {}

    def insert(item: dict, hazard: str, source: Path | None = None) -> None:
        if hazard not in HAZARDS:
            return
        try:
            frame = annotate(item)
        except (ValueError, KeyError, TypeError):
            return
        date = frame["valid_date"]
        if date not in allowed_dates:
            return
        filename = safe_filename(hazard, frame)
        archived_file = archive_dir / filename
        if source is not None:
            if not source.is_file():
                raise FileNotFoundError(f"NADOCast source map missing: {source}")
            shutil.copy2(source, archived_file)
        elif not archived_file.is_file():
            # Migrate a correctly dated existing archive image only.
            original = Path(str(item.get("image", ""))).name
            prior = archive_dir / original
            if not original or not prior.is_file():
                return
            shutil.copy2(prior, archived_file)
        data = {key: frame.get(key) for key in FRAME_FIELDS}
        data["image"] = filename
        entries = frames_by_date.setdefault(date, {}).setdefault(hazard, [])
        entries[:] = [old for old in entries if old["image"] != filename]
        entries.append(data)

    if existing.get("schema_version") == 2:
        sources = [
            (hazard, item)
            for date_group in existing.get("valid_dates", {}).values()
            for hazard, frames in date_group.items()
            for item in frames
        ]
    else:
        # The legacy cache incorrectly classified some frames by Day 1/Day 2.
        sources = [
            (hazard, item)
            for day in ("day1", "day2")
            for hazard, frames in existing.get(day, {}).items()
            for item in frames
        ]
    for hazard, item in sources:
        insert(item, hazard)

    # Insert the new build's real valid-date map(s).
    for _valid_date, products in manifest.get("valid_products", {}).items():
        for hazard, item in products.items():
            insert(item, hazard, manifest_path.parent / item["image"])

    for date, hazards in frames_by_date.items():
        for hazard, frames in hazards.items():
            frames.sort(key=sort_key, reverse=True)
            hazards[hazard] = frames[:max_frames]

    retained = {
        f["image"]
        for hazards in frames_by_date.values()
        for frames in hazards.values()
        for f in frames
    }
    for path in archive_dir.glob("*.png"):
        if path.name not in retained:
            path.unlink()

    output_dir = manifest_path.parent / "history"
    output_dir.mkdir(exist_ok=True)
    published: dict[str, dict[str, list[dict]]] = {}
    for valid_date, hazards in sorted(frames_by_date.items()):
        for hazard, frames in hazards.items():
            for item in frames:
                saved = archive_dir / item["image"]
                if not saved.is_file():
                    continue
                shutil.copy2(saved, output_dir / saved.name)
                published.setdefault(valid_date, {}).setdefault(hazard, []).append(
                    {**item, "image": "history/" + item["image"]}
                )

    history_file.write_text(json.dumps({
        "schema_version": 2, "valid_dates": frames_by_date
    }, indent=2), encoding="utf-8")
    manifest["trends_by_valid_date"] = published
    # Drop old trend keys so clients cannot accidentally present mixed periods.
    manifest.pop("trends", None)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
