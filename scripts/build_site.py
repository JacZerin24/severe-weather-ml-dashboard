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

from trend_history import update_cwa_trends
from forecast_validity import annotate, describe_product

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


def build_manifest(results: list[dict], cwa: str, out_dir: Path, *, today: dt.date | None = None) -> Path:
    """Key all source products by their *actual* 12Z–12Z UTC valid date.

    A 12Z f24–47 source from yesterday can be today's Day 1 guidance.
    Merely mapping lead <24 to Day 1 loses this important relationship.
    """
    today = today or dt.datetime.now(dt.timezone.utc).date()
    candidates: dict[tuple[str, str], dict] = {}
    skipped: list[str] = []
    for source in results:
        hazard = source.get("hazard")
        if hazard not in DISPLAY_HAZARDS:
            continue
        try:
            item = annotate(source)
        except (ValueError, KeyError) as exc:
            skipped.append(f"{source.get('filename', 'unknown')}: {exc}")
            continue
        key = (item["valid_date"], hazard)
        old = candidates.get(key)
        # Prefer newer model initializations, not the shorter lead label alone.
        if old is None or (
            item["init_utc"], item["valid_start_utc"], item["lead_label"]
        ) > (
            old["init_utc"], old["valid_start_utc"], old["lead_label"]
        ):
            candidates[key] = item

    by_date: dict[str, dict[str, dict]] = {}
    for (valid_date, hazard), item in sorted(candidates.items()):
        out = {
            "image": Path(item["png"]).name,
            "hazard": hazard,
            "lead_label": item["lead_label"],
            "run_date": item["run_date"],
            "run_dir": item["run_dir"],
            "max_cwa": item.get("max_cwa"),
            "mean_cwa": item.get("mean_cwa"),
            "max_buffer": item.get("max_buffer"),
        }
        out.update(describe_product(item["run_date"], item["run_dir"], item["lead_label"]).as_dict())
        by_date.setdefault(valid_date, {})[hazard] = out

    # Kept for backwards compatibility but strictly filter by UTC outlook day.
    products = {
        "day1": by_date.get(today.isoformat(), {}),
        "day2": by_date.get((today + dt.timedelta(days=1)).isoformat(), {}),
    }
    manifest = {
        "schema_version": 2,
        "cwa": cwa,
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "outlook_day_basis": "12Z–12Z UTC",
        "valid_products": by_date,
        "products": products,
        "skipped_invalid_windows": skipped[:25],
    }
    path = out_dir / "latest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def run_for_cwa(root: Path, site_dir: Path, cache_dir: Path, archive_dir: Path, cwa: str, days_back: int) -> dict:
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
    manifest_path = build_manifest(results, cwa, out_dir)
    update_cwa_trends(manifest_path, archive_dir)
    return {"cwa": cwa, "ok": True, "products": len(results)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwas-file", default="config/cwas.txt")
    parser.add_argument("--site-dir", default="site")
    parser.add_argument("--cache-dir", default="cache")
    parser.add_argument("--archive-dir", default="archive/nadocast")
    parser.add_argument("--days-back", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    site_dir = (root / args.site_dir).resolve()
    cache_dir = (root / args.cache_dir).resolve()
    archive_dir = (root / args.archive_dir).resolve()
    cwas = read_cwas(root / args.cwas_file)

    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "index.html", site_dir / "index.html")
    shutil.copy2(root / "nssl-v12.js", site_dir / "nssl-v12.js")
    shutil.copy2(root / "dashboard.css", site_dir / "dashboard.css")
    shutil.copy2(root / "resources.js", site_dir / "resources.js")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    statuses: list[dict] = []
    for cwa in cwas:
        try:
            statuses.append(run_for_cwa(root, site_dir, cache_dir, archive_dir, cwa, args.days_back))
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
