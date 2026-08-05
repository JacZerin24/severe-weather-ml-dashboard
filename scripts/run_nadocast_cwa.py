#!/usr/bin/env python3
"""Create CWA-specific NADOCast probability maps for a static dashboard."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import numpy as np
import requests
from bs4 import BeautifulSoup

BASE_URL = "http://data.nadocast.com"
CWA_ZIPS = [
    "https://www.weather.gov/source/gis/Shapefiles/WSOM/w_16ap26.zip",
    "https://www.weather.gov/source/gis/Shapefiles/WSOM/w_18mr25.zip",
]
RUN_ORDER = ["t18z", "t12z", "t0z", "t14z", "t10z", "t20z"]
MODEL_ORDER = ["2024_preliminary_models", "2022_models", "2021_models"]
REGULAR_HAZARDS = {"tornado", "wind", "wind_adj", "hail"}
VALID_HAZARDS = REGULAR_HAZARDS | {"sig_tornado", "sig_wind", "sig_wind_adj", "sig_hail"}
LABELS = {
    "tornado": "Tornado",
    "wind": "Severe Wind",
    "wind_adj": "Severe Wind, Adjusted/Reweighted",
    "hail": "Severe Hail",
    "sig_tornado": "Significant Tornado",
    "sig_wind": "Significant Wind",
    "sig_wind_adj": "Significant Wind, Adjusted/Reweighted",
    "sig_hail": "Significant Hail",
}
HEADERS = {"User-Agent": "severe-weather-ml-dashboard/1.0"}


@dataclass(frozen=True)
class Product:
    url: str
    filename: str
    hazard: str
    lead: str
    run_date: str
    run_dir: str
    model_rank: int


def log(message: str) -> None:
    print(message, flush=True)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_text(url: str, timeout: int = 25) -> str:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def download(url: str, destination: Path, timeout: int = 120) -> Path:
    ensure_dir(destination.parent)
    temp = destination.with_suffix(destination.suffix + ".part")
    with requests.get(url, headers=HEADERS, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        with temp.open("wb") as handle:
            for chunk in response.iter_content(1024 * 512):
                if chunk:
                    handle.write(chunk)
    temp.replace(destination)
    return destination


def folder_url(run_date: str, run_dir: str) -> str:
    return f"{BASE_URL}/{run_date[:6]}/{run_date}/{run_dir}/"


def model_rank(filename: str) -> int:
    for index, token in enumerate(MODEL_ORDER):
        if token in filename:
            return index
    return len(MODEL_ORDER)


def lead_from_name(filename: str) -> str:
    match = re.search(r"_(f\d{1,3}(?:-\d{1,3})?)\.grib2$", filename)
    return match.group(1) if match else "unknown"


def list_products(run_date: str, run_dir: str, hazards: list[str], lead_filter: str | None) -> list[Product]:
    base = folder_url(run_date, run_dir)
    soup = BeautifulSoup(get_text(base), "html.parser")
    products: list[Product] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].split("?", 1)[0]
        if not href.lower().endswith(".grib2"):
            continue
        url = urljoin(base, href)
        filename = Path(urlparse(url).path).name
        for hazard in hazards:
            pattern = rf"_conus_{re.escape(hazard)}_\d{{8}}_t\d{{1,2}}z_f"
            if not re.search(pattern, filename):
                continue
            if lead_filter and lead_filter not in filename:
                continue
            products.append(Product(url, filename, hazard, lead_from_name(filename), run_date, run_dir, model_rank(filename)))
    return products


def find_products(date_arg: str, run_arg: str, hazards: list[str], days_back: int, lead_filter: str | None) -> tuple[str, str, list[Product]]:
    today = dt.datetime.now(dt.UTC).date()
    if date_arg != "latest":
        dates = [date_arg]
    else:
        dates = [(today - dt.timedelta(days=offset)).strftime("%Y%m%d") for offset in range(days_back + 1)]
    runs = RUN_ORDER if run_arg == "latest" else [run_arg.lower()]
    errors: list[str] = []
    for run_date in dates:
        for run_dir in runs:
            try:
                found = list_products(run_date, run_dir, hazards, lead_filter)
            except Exception as exc:
                errors.append(f"{folder_url(run_date, run_dir)}: {exc}")
                continue
            if found:
                return run_date, run_dir, found
    detail = "\n".join(errors[:8])
    raise FileNotFoundError(f"No matching NADOCast GRIB2 files found.\n{detail}")


def best_products(products: list[Product]) -> list[Product]:
    selected: dict[tuple[str, str], Product] = {}
    for product in products:
        key = (product.hazard, product.lead)
        old = selected.get(key)
        if old is None or (product.model_rank, product.filename) < (old.model_rank, old.filename):
            selected[key] = product
    return sorted(selected.values(), key=lambda item: (item.hazard, item.lead, item.model_rank))


def load_cwas(cache_dir: Path):
    import geopandas as gpd

    target_dir = ensure_dir(cache_dir / "cwa_boundaries")
    existing = list(target_dir.glob("*.shp"))
    if not existing:
        last_error: Exception | None = None
        for url in CWA_ZIPS:
            try:
                archive = target_dir / Path(urlparse(url).path).name
                log(f"Downloading CWA boundaries: {url}")
                download(url, archive)
                with zipfile.ZipFile(archive) as zipped:
                    zipped.extractall(target_dir)
                existing = list(target_dir.glob("*.shp"))
                if existing:
                    break
            except Exception as exc:
                last_error = exc
        if not existing:
            raise RuntimeError(f"Could not load CWA boundaries: {last_error}")
    cwas = gpd.read_file(existing[0])
    return cwas.set_crs("EPSG:4326") if cwas.crs is None else cwas.to_crs("EPSG:4326")


def select_cwa(cwas, cwa: str):
    mask = None
    for field in ("CWA", "WFO", "WFOID"):
        if field in cwas.columns:
            part = cwas[field].astype(str).str.upper().eq(cwa)
            mask = part if mask is None else mask | part
    if mask is None or not mask.any():
        raise ValueError(f"CWA {cwa} was not found in the NWS boundary file")
    return cwas.loc[mask].copy()


def open_probability(path: Path):
    import xarray as xr

    try:
        dataset = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
    except Exception:
        import cfgrib
        datasets = cfgrib.open_datasets(str(path), indexpath="")
        dataset = max(datasets, key=lambda ds: max((ds[var].ndim for var in ds.data_vars), default=0))
    numeric = [name for name in dataset.data_vars if np.issubdtype(dataset[name].dtype, np.number)]
    if not numeric:
        raise ValueError(f"No numeric probability field found in {path.name}")
    data = max((dataset[name] for name in numeric), key=lambda value: value.ndim).squeeze(drop=True)
    while data.ndim > 2:
        data = data.isel({data.dims[0]: 0}).squeeze(drop=True)
    lat_name = next((name for name in ("latitude", "lat", "gridlat_0") if name in data.coords), None)
    lon_name = next((name for name in ("longitude", "lon", "gridlon_0") if name in data.coords), None)
    if not lat_name or not lon_name:
        raise ValueError(f"Latitude/longitude coordinates were not found in {path.name}")
    lats = np.asarray(data[lat_name])
    lons = np.asarray(data[lon_name])
    lons = np.where(lons > 180, lons - 360, lons)
    values = np.asarray(data, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size and np.nanmax(finite) <= 1.5:
        values *= 100.0
    return values, lats, lons


def subset(values, lats, lons, bounds):
    minx, miny, maxx, maxy = bounds
    if lats.ndim == 1 and lons.ndim == 1:
        lat_mask = (lats >= miny) & (lats <= maxy)
        lon_mask = (lons >= minx) & (lons <= maxx)
        return values[np.ix_(lat_mask, lon_mask)], lats[lat_mask], lons[lon_mask]
    mask = (lats >= miny) & (lats <= maxy) & (lons >= minx) & (lons <= maxx)
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if not rows.size or not cols.size:
        raise ValueError("No NADOCast grid points intersect the requested map")
    return values[rows.min():rows.max()+1, cols.min():cols.max()+1], lats[rows.min():rows.max()+1, cols.min():cols.max()+1], lons[rows.min():rows.max()+1, cols.min():cols.max()+1]


def grid_coordinates(lats, lons):
    if lats.ndim == 1 and lons.ndim == 1:
        return np.meshgrid(lons, lats)
    return lons, lats


def stats(values, lats, lons, target, buffered) -> dict:
    from shapely import contains_xy

    lon2d, lat2d = grid_coordinates(lats, lons)
    target_union = target.geometry.union_all() if hasattr(target.geometry, "union_all") else target.unary_union
    buffer_union = buffered.geometry.union_all() if hasattr(buffered.geometry, "union_all") else buffered.unary_union
    valid = np.isfinite(values)
    in_cwa = contains_xy(target_union, lon2d, lat2d) & valid
    in_buffer = contains_xy(buffer_union, lon2d, lat2d) & valid
    cwa_values = values[in_cwa]
    buffer_values = values[in_buffer]
    return {
        "max_cwa": float(np.nanmax(cwa_values)) if cwa_values.size else None,
        "mean_cwa": float(np.nanmean(cwa_values)) if cwa_values.size else None,
        "max_buffer": float(np.nanmax(buffer_values)) if buffer_values.size else None,
    }


def style(hazard: str) -> dict:
    if hazard == "tornado":
        return {"bounds": [0, .1, 1, 2, 3, 5, 10, 15, 30, 45, 60, 100], "colors": ["#e6e6e6", "#d9d9d9", "#bfbfbf", "#149b1a", "#39d13a", "#9b552b", "#ffd22e", "#ff1f1f", "#df42f5", "#9147f2", "#2d67b2"], "sig": "sig_tornado"}
    return {"bounds": [0, 1, 5, 15, 30, 45, 60, 100], "colors": ["#f2f2f2", "#d9d9d9", "#9b552b", "#ffd22e", "#ff1f1f", "#df42f5", "#9147f2"], "sig": {"wind": "sig_wind", "wind_adj": "sig_wind_adj", "hail": "sig_hail"}.get(hazard)}


def make_map(product: Product, grib_path: Path, overlay_path: Path | None, cwas, target, buffered, out_dir: Path, cwa: str, dpi: int) -> dict:
    import matplotlib.pyplot as plt

    values, lats, lons = open_probability(grib_path)
    values, lats, lons = subset(values, lats, lons, buffered.total_bounds)
    lon2d, lat2d = grid_coordinates(lats, lons)
    result_stats = stats(values, lats, lons, target, buffered)
    palette = style(product.hazard)

    fig, ax = plt.subplots(figsize=(10, 8.5))
    mesh = ax.contourf(lon2d, lat2d, values, levels=palette["bounds"], colors=palette["colors"], extend="max", antialiased=True, zorder=1)
    finite = values[np.isfinite(values)]
    contour_levels = [level for level in palette["bounds"][1:-1] if finite.size and np.nanmin(finite) < level < np.nanmax(finite)]
    if contour_levels:
        contours = ax.contour(lon2d, lat2d, values, levels=contour_levels, colors="black", linewidths=.65, zorder=4)
        ax.clabel(contours, fmt=lambda value: f"{value:g}%", fontsize=7)

    if overlay_path:
        try:
            sig_values, sig_lats, sig_lons = open_probability(overlay_path)
            sig_values, sig_lats, sig_lons = subset(sig_values, sig_lats, sig_lons, buffered.total_bounds)
            sig_lon2d, sig_lat2d = grid_coordinates(sig_lats, sig_lons)
            if np.nanmax(sig_values) >= 10:
                ax.contourf(sig_lon2d, sig_lat2d, sig_values, levels=[10, max(10.001, float(np.nanmax(sig_values)) + .001)], colors="none", hatches=["////"], alpha=0, zorder=5)
        except Exception as exc:
            log(f"Could not add significant-severe hatching: {exc}")

    minx, miny, maxx, maxy = buffered.total_bounds
    try:
        context = cwas.cx[minx:maxx, miny:maxy]
        context.boundary.plot(ax=ax, color="0.55", linewidth=.55, zorder=6)
    except Exception:
        pass
    buffered.boundary.plot(ax=ax, color="0.3", linestyle="--", linewidth=1.0, zorder=7)
    target.boundary.plot(ax=ax, color="black", linewidth=2.5, zorder=8)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(f"NADOCast {LABELS.get(product.hazard, product.hazard)} Probability — {cwa} CWA\n{product.run_date} {product.run_dir.upper()} | {product.lead} | Experimental guidance", fontsize=12)
    colorbar = fig.colorbar(mesh, ax=ax, shrink=.82, pad=.02, boundaries=palette["bounds"], ticks=palette["bounds"][:-1])
    colorbar.set_label("Probability (%)")
    pieces = []
    if result_stats["max_cwa"] is not None:
        pieces.append(f"CWA max {result_stats['max_cwa']:.1f}%")
    if result_stats["mean_cwa"] is not None:
        pieces.append(f"CWA mean {result_stats['mean_cwa']:.1f}%")
    if result_stats["max_buffer"] is not None:
        pieces.append(f"Buffer max {result_stats['max_buffer']:.1f}%")
    if pieces:
        ax.text(.01, .01, " | ".join(pieces), transform=ax.transAxes, fontsize=9, bbox={"facecolor": "white", "alpha": .78, "edgecolor": "none"}, zorder=10)
    fig.text(.5, .01, "Experimental third-party guidance from data.nadocast.com. Not official NWS/SPC guidance.", ha="center", fontsize=8)
    output = out_dir / product.filename.replace(".grib2", f"_{cwa}.png")
    fig.tight_layout(rect=[0, .03, 1, 1])
    fig.savefig(output, dpi=dpi)
    plt.close(fig)
    return {"png": str(output), "filename": product.filename, "url": product.url, "hazard": product.hazard, "lead_label": product.lead, "run_date": product.run_date, "run_dir": product.run_dir, **result_stats}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download NADOCast GRIB2 files and create CWA-specific maps")
    parser.add_argument("--cwa", default="LIX")
    parser.add_argument("--date", default="latest")
    parser.add_argument("--run", default="latest")
    parser.add_argument("--hazards", nargs="+", default=["tornado", "wind_adj", "hail", "sig_tornado", "sig_wind_adj", "sig_hail"])
    parser.add_argument("--lead", default=None)
    parser.add_argument("--days-back", type=int, default=5)
    parser.add_argument("--buffer-miles", type=float, default=125.0)
    parser.add_argument("--out-dir", default="outputs")
    parser.add_argument("--cache-dir", default="cache")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--no-html", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hazards = [hazard.lower() for hazard in args.hazards]
    invalid = sorted(set(hazards) - VALID_HAZARDS)
    if invalid:
        raise ValueError(f"Unsupported hazards: {', '.join(invalid)}")
    cwa = args.cwa.upper()
    out_dir = ensure_dir(Path(args.out_dir))
    cache_dir = ensure_dir(Path(args.cache_dir))
    grib_dir = ensure_dir(cache_dir / "grib2")

    run_date, run_dir, products = find_products(args.date.lower(), args.run.lower(), hazards, args.days_back, args.lead)
    products = best_products(products)
    log(f"Using {run_date} {run_dir.upper()} with {len(products)} products")
    for product in products:
        log(f"  {product.hazard:14s} {product.lead:8s} {product.filename}")
    if args.list:
        return 0

    paths: dict[tuple[str, str], Path] = {}
    for product in products:
        local = grib_dir / product.filename
        if not local.exists() or local.stat().st_size == 0:
            log(f"Downloading {product.filename}")
            download(product.url, local)
        paths[(product.hazard, product.lead)] = local
    if args.download_only:
        return 0

    cwas = load_cwas(cache_dir)
    target = select_cwa(cwas, cwa)
    target_projected = target.to_crs("EPSG:5070")
    buffered = target_projected.copy()
    buffered["geometry"] = buffered.geometry.buffer(args.buffer_miles * 1609.344)
    buffered = buffered.to_crs("EPSG:4326")

    results: list[dict] = []
    for product in products:
        if product.hazard not in REGULAR_HAZARDS:
            continue
        sig_hazard = style(product.hazard).get("sig")
        overlay = paths.get((sig_hazard, product.lead)) if sig_hazard else None
        log(f"Plotting {product.filename}")
        results.append(make_map(product, paths[(product.hazard, product.lead)], overlay, cwas, target, buffered, out_dir, cwa, args.dpi))
    if not results:
        raise RuntimeError("No regular-hazard maps were created")
    summary = out_dir / f"nadocast_{cwa}_summary.json"
    summary.write_text(json.dumps(results, indent=2), encoding="utf-8")
    log(f"Wrote {summary}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
