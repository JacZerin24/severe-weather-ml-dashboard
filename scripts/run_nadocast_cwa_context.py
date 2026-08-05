#!/usr/bin/env python3
"""Run the NADOCast CWA mapper with state, interstate, and city context layers."""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd

import run_nadocast_cwa as base

STATE_ZIP_URLS = [
    "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_500k.zip",
    "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_state_500k.zip",
]
ROAD_URL_TEMPLATES = [
    "https://www2.census.gov/geo/tiger/TIGER2024/PRISECROADS/tl_2024_{statefp}_prisecroads.zip",
    "https://www2.census.gov/geo/tiger/TIGER2023/PRISECROADS/tl_2023_{statefp}_prisecroads.zip",
]

# name, latitude, longitude, priority. Lower priorities are labeled first.
MAJOR_CITIES = [
    ("New York", 40.7128, -74.0060, 1), ("Boston", 42.3601, -71.0589, 1),
    ("Philadelphia", 39.9526, -75.1652, 1), ("Baltimore", 39.2904, -76.6122, 1),
    ("Washington", 38.9072, -77.0369, 1), ("Pittsburgh", 40.4406, -79.9959, 1),
    ("Buffalo", 42.8864, -78.8784, 2), ("Cleveland", 41.4993, -81.6944, 1),
    ("Columbus", 39.9612, -82.9988, 1), ("Cincinnati", 39.1031, -84.5120, 1),
    ("Detroit", 42.3314, -83.0458, 1), ("Chicago", 41.8781, -87.6298, 1),
    ("Milwaukee", 43.0389, -87.9065, 1), ("Indianapolis", 39.7684, -86.1581, 1),
    ("Louisville", 38.2527, -85.7585, 1), ("St. Louis", 38.6270, -90.1994, 1),
    ("Kansas City", 39.0997, -94.5786, 1), ("Omaha", 41.2565, -95.9345, 1),
    ("Des Moines", 41.5868, -93.6250, 1), ("Minneapolis", 44.9778, -93.2650, 1),
    ("Fargo", 46.8772, -96.7898, 2), ("Grand Forks", 47.9253, -97.0329, 3),
    ("Bismarck", 46.8083, -100.7837, 2), ("Aberdeen", 45.4647, -98.4865, 3),
    ("Pierre", 44.3683, -100.3510, 3), ("Rapid City", 44.0805, -103.2310, 2),
    ("Spearfish", 44.4908, -103.8596, 3), ("Sturgis", 44.4097, -103.5091, 3),
    ("Sioux Falls", 43.5460, -96.7313, 2), ("Sioux City", 42.4963, -96.4059, 3),
    ("North Platte", 41.1403, -100.7601, 3), ("Valentine", 42.8728, -100.5501, 4),
    ("Chadron", 42.8294, -102.9999, 4), ("Scottsbluff", 41.8666, -103.6672, 3),
    ("Cheyenne", 41.1400, -104.8202, 2), ("Casper", 42.8501, -106.3252, 2),
    ("Gillette", 44.2911, -105.5022, 3), ("Sheridan", 44.7972, -106.9562, 3),
    ("Billings", 45.7833, -108.5007, 2), ("Bozeman", 45.6770, -111.0429, 3),
    ("Great Falls", 47.5053, -111.3008, 3), ("Missoula", 46.8721, -113.9940, 3),
    ("Denver", 39.7392, -104.9903, 1), ("Colorado Springs", 38.8339, -104.8214, 2),
    ("Pueblo", 38.2544, -104.6091, 3), ("Albuquerque", 35.0844, -106.6504, 1),
    ("Santa Fe", 35.6870, -105.9378, 3), ("El Paso", 31.7619, -106.4850, 1),
    ("Salt Lake City", 40.7608, -111.8910, 1), ("Boise", 43.6150, -116.2023, 1),
    ("Seattle", 47.6062, -122.3321, 1), ("Spokane", 47.6588, -117.4260, 2),
    ("Portland", 45.5152, -122.6784, 1), ("Las Vegas", 36.1699, -115.1398, 1),
    ("Reno", 39.5296, -119.8138, 2), ("Sacramento", 38.5816, -121.4944, 1),
    ("San Francisco", 37.7749, -122.4194, 1), ("San Jose", 37.3382, -121.8863, 1),
    ("Los Angeles", 34.0522, -118.2437, 1), ("San Diego", 32.7157, -117.1611, 1),
    ("Phoenix", 33.4484, -112.0740, 1), ("Tucson", 32.2226, -110.9747, 1),
    ("Oklahoma City", 35.4676, -97.5164, 1), ("Tulsa", 36.1540, -95.9928, 1),
    ("Wichita", 37.6872, -97.3301, 1), ("Topeka", 39.0473, -95.6752, 2),
    ("Dodge City", 37.7528, -100.0171, 3), ("Amarillo", 35.2219, -101.8313, 2),
    ("Lubbock", 33.5779, -101.8552, 2), ("Midland", 31.9973, -102.0779, 2),
    ("Dallas", 32.7767, -96.7970, 1), ("Fort Worth", 32.7555, -97.3308, 1),
    ("Austin", 30.2672, -97.7431, 1), ("San Antonio", 29.4241, -98.4936, 1),
    ("Houston", 29.7604, -95.3698, 1), ("Corpus Christi", 27.8006, -97.3964, 2),
    ("Brownsville", 25.9017, -97.4975, 3), ("Little Rock", 34.7465, -92.2896, 1),
    ("Memphis", 35.1495, -90.0490, 1), ("Nashville", 36.1627, -86.7816, 1),
    ("Jackson", 32.2988, -90.1848, 2), ("Shreveport", 32.5252, -93.7502, 2),
    ("Monroe", 32.5093, -92.1193, 3), ("Alexandria", 31.3113, -92.4451, 3),
    ("Lake Charles", 30.2266, -93.2174, 3), ("Lafayette", 30.2241, -92.0198, 2),
    ("Baton Rouge", 30.4515, -91.1871, 1), ("New Orleans", 29.9511, -90.0715, 1),
    ("Hammond", 30.5044, -90.4612, 3), ("Slidell", 30.2752, -89.7812, 3),
    ("Houma", 29.5958, -90.7195, 3), ("Gulfport", 30.3674, -89.0928, 3),
    ("Biloxi", 30.3960, -88.8853, 3), ("Mobile", 30.6954, -88.0399, 2),
    ("Pensacola", 30.4213, -87.2169, 2), ("Birmingham", 33.5186, -86.8104, 1),
    ("Tuscaloosa", 33.2098, -87.5692, 2), ("Montgomery", 32.3668, -86.3000, 2),
    ("Huntsville", 34.7304, -86.5861, 2), ("Atlanta", 33.7490, -84.3880, 1),
    ("Macon", 32.8407, -83.6324, 2), ("Savannah", 32.0809, -81.0912, 2),
    ("Charlotte", 35.2271, -80.8431, 1), ("Raleigh", 35.7796, -78.6382, 1),
    ("Greensboro", 36.0726, -79.7920, 2), ("Columbia", 34.0007, -81.0348, 2),
    ("Charleston", 32.7765, -79.9311, 2), ("Richmond", 37.5407, -77.4360, 1),
    ("Norfolk", 36.8508, -76.2859, 2), ("Jacksonville", 30.3322, -81.6557, 1),
    ("Tallahassee", 30.4383, -84.2807, 2), ("Orlando", 28.5383, -81.3792, 1),
    ("Tampa", 27.9506, -82.4572, 1), ("Miami", 25.7617, -80.1918, 1),
]

_STATE_CACHE: dict[str, object] = {}
_ROAD_CACHE: dict[tuple[str, tuple[str, ...]], object] = {}
_CITY_CACHE = None


def empty_gdf():
    import geopandas as gpd

    return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")


def extract_first_shapefile(url: str, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    existing = list(target_dir.glob("*.shp"))
    if existing:
        return existing[0]
    archive = target_dir / Path(urlparse(url).path).name
    base.download(url, archive)
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(target_dir)
    shapefiles = list(target_dir.glob("*.shp"))
    if not shapefiles:
        raise FileNotFoundError(f"No shapefile found in {archive.name}")
    return shapefiles[0]


def load_states(cache_dir: Path):
    import geopandas as gpd

    key = str(cache_dir.resolve())
    if key in _STATE_CACHE:
        return _STATE_CACHE[key]
    last_error = None
    for url in STATE_ZIP_URLS:
        try:
            path = extract_first_shapefile(url, cache_dir / "state_boundaries")
            states = gpd.read_file(path)
            states = states.set_crs("EPSG:4326") if states.crs is None else states.to_crs("EPSG:4326")
            if "STUSPS" in states.columns:
                states = states[~states["STUSPS"].astype(str).isin(["PR", "VI", "GU", "MP", "AS"])]
            _STATE_CACHE[key] = states
            return states
        except Exception as exc:
            last_error = exc
    base.log(f"Warning: state borders unavailable: {last_error}")
    states = empty_gdf()
    _STATE_CACHE[key] = states
    return states


def interstate_label(name) -> str | None:
    if name is None:
        return None
    text = str(name)
    match = re.search(r"\bI[- ]?(\d{1,3})\b", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"\bInterstate\s+(\d{1,3})\b", text, flags=re.IGNORECASE)
    return f"I-{match.group(1)}" if match else None


def load_interstates(cache_dir: Path, statefps: list[str]):
    import geopandas as gpd

    normalized = tuple(sorted({str(value).zfill(2) for value in statefps if str(value).strip()}))
    key = (str(cache_dir.resolve()), normalized)
    if key in _ROAD_CACHE:
        return _ROAD_CACHE[key]
    frames = []
    for statefp in normalized:
        road_dir = cache_dir / "primary_secondary_roads" / statefp
        path = None
        for template in ROAD_URL_TEMPLATES:
            try:
                path = extract_first_shapefile(template.format(statefp=statefp), road_dir)
                break
            except Exception as exc:
                base.log(f"Could not use roads source for state {statefp}: {exc}")
        if path is None:
            continue
        try:
            roads = gpd.read_file(path)
            roads = roads.set_crs("EPSG:4326") if roads.crs is None else roads.to_crs("EPSG:4326")
            mask = pd.Series(False, index=roads.index)
            if "RTTYP" in roads.columns:
                mask |= roads["RTTYP"].astype(str).str.upper().eq("I")
            if "FULLNAME" in roads.columns:
                mask |= roads["FULLNAME"].astype(str).str.contains(
                    r"\bI[- ]?\d{1,3}\b|Interstate\s+\d{1,3}", case=False, regex=True, na=False
                )
            roads = roads.loc[mask].copy()
            if roads.empty:
                continue
            if "FULLNAME" in roads.columns:
                roads["road_label"] = roads["FULLNAME"].apply(interstate_label)
                roads["road_label"] = roads["road_label"].fillna(roads["FULLNAME"].astype(str))
            else:
                roads["road_label"] = "Interstate"
            frames.append(roads[["road_label", "geometry"]])
        except Exception as exc:
            base.log(f"Could not read roads for state {statefp}: {exc}")
    if frames:
        result = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    else:
        result = empty_gdf()
    _ROAD_CACHE[key] = result
    return result


def load_cities():
    global _CITY_CACHE
    if _CITY_CACHE is not None:
        return _CITY_CACHE
    import geopandas as gpd

    frame = pd.DataFrame(MAJOR_CITIES, columns=["city", "lat", "lon", "priority"])
    _CITY_CACHE = gpd.GeoDataFrame(
        frame,
        geometry=gpd.points_from_xy(frame["lon"], frame["lat"]),
        crs="EPSG:4326",
    )
    return _CITY_CACHE


def label_point(geometry):
    try:
        if geometry.geom_type == "LineString":
            return geometry.interpolate(0.5, normalized=True)
        if geometry.geom_type == "MultiLineString":
            pieces = list(geometry.geoms)
            longest = max(pieces, key=lambda item: item.length)
            return longest.interpolate(0.5, normalized=True)
    except Exception:
        pass
    return geometry.representative_point()


def enhanced_make_map(product, grib_path, overlay_path, cwas, target, buffered, out_dir, cwa, dpi):
    import geopandas as gpd
    import matplotlib.pyplot as plt
    from shapely.geometry import box

    cache_dir = grib_path.parent.parent
    values, lats, lons = base.open_probability(grib_path)
    values, lats, lons = base.subset(values, lats, lons, buffered.total_bounds)
    lon2d, lat2d = base.grid_coordinates(lats, lons)
    result_stats = base.stats(values, lats, lons, target, buffered)
    palette = base.style(product.hazard)

    minx, miny, maxx, maxy = buffered.total_bounds
    bbox = box(minx, miny, maxx, maxy)
    states = load_states(cache_dir)
    context_states = states[states.intersects(bbox)].copy() if len(states) else states
    statefps = context_states["STATEFP"].astype(str).tolist() if len(context_states) and "STATEFP" in context_states.columns else []
    roads = load_interstates(cache_dir, statefps)
    context_roads = roads[roads.intersects(bbox)].copy() if len(roads) else roads
    cities = load_cities()
    context_cities = cities[cities.intersects(bbox)].copy()

    fig, ax = plt.subplots(figsize=(10, 8.5))
    mesh = ax.contourf(
        lon2d,
        lat2d,
        values,
        levels=palette["bounds"],
        colors=palette["colors"],
        extend="max",
        antialiased=True,
        zorder=1,
    )

    finite = values[np.isfinite(values)]
    contour_levels = [
        level for level in palette["bounds"][1:-1]
        if finite.size and np.nanmin(finite) < level < np.nanmax(finite)
    ]
    if contour_levels:
        contours = ax.contour(
            lon2d, lat2d, values, levels=contour_levels,
            colors="black", linewidths=0.65, alpha=0.85, zorder=4
        )
        ax.clabel(contours, fmt=lambda value: f"{value:g}%", fontsize=7)

    if overlay_path:
        try:
            sig_values, sig_lats, sig_lons = base.open_probability(overlay_path)
            sig_values, sig_lats, sig_lons = base.subset(sig_values, sig_lats, sig_lons, buffered.total_bounds)
            sig_lon2d, sig_lat2d = base.grid_coordinates(sig_lats, sig_lons)
            finite_sig = sig_values[np.isfinite(sig_values)]
            if finite_sig.size and np.nanmax(finite_sig) >= 10:
                upper = max(10.001, float(np.nanmax(finite_sig)) + 0.001)
                ax.contourf(
                    sig_lon2d, sig_lat2d, sig_values,
                    levels=[10, upper], colors="none", hatches=["////"], alpha=0, zorder=5
                )
                ax.contour(sig_lon2d, sig_lat2d, sig_values, levels=[10], colors="black", linewidths=0.8, zorder=5)
        except Exception as exc:
            base.log(f"Could not add significant-severe hatching: {exc}")

    # Draw geographic context above the probability field so it remains readable.
    if len(context_states):
        context_states.boundary.plot(ax=ax, linewidth=1.2, color="0.15", alpha=0.95, zorder=8)

    try:
        context_cwas = cwas[cwas.intersects(bbox)]
    except Exception:
        context_cwas = cwas
    context_cwas.boundary.plot(ax=ax, linewidth=0.55, color="0.48", alpha=0.70, zorder=7)
    buffered.boundary.plot(ax=ax, linewidth=1.0, linestyle="--", color="0.28", alpha=0.75, zorder=9)
    target.boundary.plot(ax=ax, linewidth=2.7, color="black", zorder=12)

    if len(context_roads):
        try:
            context_roads.plot(ax=ax, linewidth=3.0, color="white", alpha=0.96, zorder=10)
            context_roads.plot(ax=ax, linewidth=1.35, color="#0057b8", alpha=0.96, zorder=11)
            labels = context_roads.dropna(subset=["road_label"]).copy()
            labels = labels[labels["road_label"].astype(str).str.len() > 0]
            if len(labels):
                metric = labels.to_crs("EPSG:5070")
                labels["_length"] = metric.geometry.length.to_numpy()
                labels = labels.sort_values("_length", ascending=False).drop_duplicates("road_label")
                placed = 0
                for _, row in labels.iterrows():
                    if placed >= 12:
                        break
                    point = label_point(row.geometry)
                    if not (minx + 0.02 * (maxx - minx) <= point.x <= maxx - 0.02 * (maxx - minx)):
                        continue
                    if not (miny + 0.02 * (maxy - miny) <= point.y <= maxy - 0.02 * (maxy - miny)):
                        continue
                    ax.text(
                        point.x, point.y, str(row["road_label"]),
                        fontsize=7.2, color="#0057b8", ha="center", va="center", zorder=14,
                        bbox={"facecolor": "white", "edgecolor": "#0057b8", "linewidth": 0.4, "alpha": 0.88, "pad": 0.15},
                    )
                    placed += 1
        except Exception as exc:
            base.log(f"Could not plot or label interstates: {exc}")

    if len(context_cities):
        try:
            x_span = maxx - minx
            y_span = maxy - miny
            context_cities = context_cities[
                (context_cities.geometry.x >= minx + 0.025 * x_span)
                & (context_cities.geometry.x <= maxx - 0.025 * x_span)
                & (context_cities.geometry.y >= miny + 0.025 * y_span)
                & (context_cities.geometry.y <= maxy - 0.025 * y_span)
            ].sort_values(["priority", "city"]).head(18)
            ax.scatter(
                context_cities.geometry.x,
                context_cities.geometry.y,
                s=18,
                marker="o",
                facecolors="white",
                edgecolors="black",
                linewidths=0.8,
                zorder=15,
            )
            for _, row in context_cities.iterrows():
                ax.text(
                    row.geometry.x + 0.008 * x_span,
                    row.geometry.y + 0.008 * y_span,
                    str(row["city"]),
                    fontsize=7.4,
                    color="black",
                    ha="left",
                    va="bottom",
                    zorder=16,
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.74, "pad": 0.18},
                )
        except Exception as exc:
            base.log(f"Could not plot or label cities: {exc}")

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(
        f"NADOCast {base.LABELS.get(product.hazard, product.hazard)} Probability — {cwa} CWA\n"
        f"{product.run_date} {product.run_dir.upper()} | {product.lead} | Experimental guidance",
        fontsize=12,
    )
    colorbar = fig.colorbar(
        mesh,
        ax=ax,
        shrink=0.82,
        pad=0.02,
        boundaries=palette["bounds"],
        ticks=palette["bounds"][:-1],
    )
    colorbar.set_label("Probability (%)")

    pieces = []
    if result_stats["max_cwa"] is not None:
        pieces.append(f"CWA max {result_stats['max_cwa']:.1f}%")
    if result_stats["mean_cwa"] is not None:
        pieces.append(f"CWA mean {result_stats['mean_cwa']:.1f}%")
    if result_stats["max_buffer"] is not None:
        pieces.append(f"Buffer max {result_stats['max_buffer']:.1f}%")
    if pieces:
        ax.text(
            0.01, 0.01, " | ".join(pieces), transform=ax.transAxes, fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.78, "edgecolor": "none"}, zorder=20
        )

    fig.text(
        0.5,
        0.01,
        "Experimental third-party guidance from data.nadocast.com. Not official NWS/SPC guidance.",
        ha="center",
        fontsize=8,
    )
    output = out_dir / product.filename.replace(".grib2", f"_{cwa}.png")
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(output, dpi=dpi)
    plt.close(fig)
    return {
        "png": str(output),
        "filename": product.filename,
        "url": product.url,
        "hazard": product.hazard,
        "lead_label": product.lead,
        "run_date": product.run_date,
        "run_dir": product.run_dir,
        **result_stats,
    }


def main() -> int:
    base.make_map = enhanced_make_map
    return base.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
