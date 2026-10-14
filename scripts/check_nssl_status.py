#!/usr/bin/env python3
"""Publish an honest health status for the external NSSL GEFS ML v1.2 source.

Accessibility of an HTML page is not proof that a new forecast map exists.
This check never treats the retired EAX image mirror or an unverified endpoint
as fresh model imagery.
"""
from __future__ import annotations

import datetime as dt
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path

SOURCES = {
    "nssl_gefs_ml": "https://apps.nssl.noaa.gov/s2s-severe/forecast_gefs_ml.html",
    "nssl_swerve": "https://apps.nssl.noaa.gov/s2s-severe/forecast_gefs_mlSWERVE.html",
}


def check(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "severe-weather-ml-dashboard/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=10, context=ssl.create_default_context()) as response:
            return {"http_status": response.status, "reachable": response.status == 200}
    except urllib.error.HTTPError as error:
        return {"http_status": error.code, "reachable": False, "error": f"HTTP {error.code}"}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"http_status": None, "reachable": False, "error": str(error.reason) if hasattr(error, "reason") else str(error)}


def generate(out_dir: Path) -> dict:
    status = {
        "checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_status": {name: check(url) for name, url in SOURCES.items()},
        # A reachable viewer is not a verified, date-stamped image data source.
        "imagery_verified": False,
        "message": "No verified live NSSL GEFS ML v1.2 raster feed is configured. Frozen EAX mirrored images are deliberately hidden.",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="site/nssl")
    args = parser.parse_args()
    print(json.dumps(generate(Path(args.out_dir)), indent=2))
