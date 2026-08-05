#!/usr/bin/env python3
"""Build the static GitHub Pages site and generate configured CWA NADOCast maps."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

DISPLAY_HAZARDS = {"tornado", "wind_adj", "hail"}
ALL_HAZARDS = ["tornado", "wind_adj", "hail", "sig_tornado", "sig_wind_adj", "sig_hail"]


def read_cwas(path: Path) -> list[str]:
    values: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip().upper()
        if line and line not in values:
            values.append(line)
    if not values:
        raise ValueError(f"No CWA identifiers found in {path}")
    return values


def lead_start(label: str) -> int:
    try:
        return int(label.lower().lstrip("f").split("-", 1)[0])
    except (TypeError, ValueError):
        return 999


def classify_day(lead_label: str) -> int:
    # NADOCast 12Z f24-47 is the Day 2 period. Other routinely published
    # windows (00Z f12-35, 12Z f02-23, 18Z f02-17) are displayed as Day 1.
    return 2 if lead_start(lead_label) >= 24 else 1


def build_manifest(results: list[dict], cwa: str, out_dir: Path) -> Path:
    candidates: dict[tuple[int, str], dict] = {}
    for item in results:
        hazard = item.get("hazard")
        if hazard not in DISPLAY_HAZARDS:
            continue
        day = classify_day(str(item.get("lead_label", "")))
        key = (day, hazard)
        current = candidates.get(key)
        if current is None or lead_start(str(item.get("lead_label", ""))) < lead_start(str(current.get("lead_label", ""))):
            candidates[key] = item

    products: dict[str, dict] = {"day1": {}, "day2": {}}
    run_labels: list[str] = []
    for (day, hazard), item in sorted(candidates.items()):
        png_name = Path(item["png"]).name
        products[f"day{day}"][hazard] = {
            "image": png_name,
            "hazard": hazard,
            "lead_label": item.get("lead_label"),
            "run_date": item.get("run_date"),
            "run_dir": item.get("run_dir"),
            "max_cwa": item.get("max_cwa"),
            "mean_cwa": item.get("mean_cwa"),
            "max_buffer": item.get("max_buffer"),
        }
        run_labels.append(f"{item.get('run_date', '')} {str(item.get('run_dir', '')).upper()}".strip())

    manifest = {
        "schema_version": 1,
        "cwa": cwa,
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "run_label": sorted(set(run_labels))[-1] if run_labels else "latest available NADOCast run",
        "products": products,
    }
    path = out_dir / "latest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def run_for_cwa(root: Path, site_dir: Path, cache_dir: Path, cwa: str, days_back: int) -> dict:
    out_dir = site_dir / "nadocast" / cwa
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(root / "scripts" / "run_nadocast_cwa_context.py"),
        "--cwa", cwa,
        "--date", "latest",
        "--run", "latest",
        "--days-back", str(days_back),
        "--hazards", *ALL_HAZARDS,
        "--out-dir", str(out_dir),
        "--cache-dir", str(cache_dir),
        "--no-html",
    ]
    print(f"\n=== Generating {cwa} ===", flush=True)
    subprocess.run(cmd, cwd=root, check=True)
    summary = out_dir / f"nadocast_{cwa}_summary.json"
    results = json.loads(summary.read_text(encoding="utf-8"))
    build_manifest(results, cwa, out_dir)
    return {"cwa": cwa, "ok": True, "products": len(results)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwas-file", default="config/cwas.txt")
    parser.add_argument("--site-dir", default="site")
    parser.add_argument("--cache-dir", default="cache")
    parser.add_argument("--days-back", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    site_dir = (root / args.site_dir).resolve()
    cache_dir = (root / args.cache_dir).resolve()
    cwas = read_cwas(root / args.cwas_file)

    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "index.html", site_dir / "index.html")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    statuses: list[dict] = []
    for cwa in cwas:
        try:
            statuses.append(run_for_cwa(root, site_dir, cache_dir, cwa, args.days_back))
        except Exception as exc:  # Keep the rest of the configured offices available.
            print(f"ERROR generating {cwa}: {exc}", file=sys.stderr, flush=True)
            statuses.append({"cwa": cwa, "ok": False, "error": str(exc)})

    availability = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "configured_cwas": cwas,
        "statuses": statuses,
    }
    (site_dir / "nadocast" / "availability.json").parent.mkdir(parents=True, exist_ok=True)
    (site_dir / "nadocast" / "availability.json").write_text(json.dumps(availability, indent=2), encoding="utf-8")

    if not any(s.get("ok") for s in statuses):
        raise RuntimeError("No configured CWA generated successfully.")
    print(f"Static site ready in {site_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
