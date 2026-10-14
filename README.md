# Severe Weather ML Dashboard

Static GitHub Pages dashboard that combines SPC, CSU MLP, NSSL GEFS ML, long-range CFS guidance, locally generated CWA-specific NADOCast probability maps, and optional CONUS NADOCast archive imagery.

## How it works

- `index.html` is the dashboard shown by GitHub Pages.
- `scripts/run_nadocast_cwa.py` downloads NADOCast GRIB2 files and creates CWA-centered PNG maps.
- `scripts/build_site.py` builds the static site, runs the mapper for each configured office, and writes a small `latest.json` manifest that the dashboard reads.
- `.github/workflows/deploy-pages.yml` rebuilds and deploys the site after pushes, manual runs, and three times daily after the normal NADOCast update windows.

The dashboard defaults to generated NADOCast maps centered on the selected CWA, including CWA/buffer statistics and significant-severe hatching when the corresponding significant product is available. Switch the NADOCast **Local CWA / CONUS + Trends** tabs to view the reference dashboard's proxied CONUS forecast cycles, without losing the CWA-specific maps.

## Interactive dashboard controls

- Select a WFO to switch SPC partner outlooks and locally generated NADOCast panels; the selection remains in the `?wfo=` URL for sharing.
- Hover or click SPC hazard tabs (categorical, tornado, wind, hail). NADOCast panels also have clickable hazard tabs.
- CSU MLP Day 1–7 cards and NSSL GEFS ML Day 1–7 cards have **Prev / Next** trend controls. CSU trends remain anchored to the **valid date of the image that actually loaded**, including when the default run falls back.
- The **CONUS + Trends** NADOCast Day 1 panel shows recent tornado, wind, and hail forecast cycles. Its Day 2 image appears when the 12Z product window is selected; the generated local Day 2 CWA map is still shown whenever it is available.
- Click any forecast image to enlarge it. When a trend image is enlarged, **Left Arrow** shows an older frame, **Right Arrow** a newer frame, and **Escape** closes it.
- Failed remote forecast images are rechecked every five seconds. The page automatically refreshes every 30 minutes.
- The CONUS image service uses `api.allorigins.win` to proxy HTTP images from `data.nadocast.com`; that third-party proxy or the archive may be unavailable. This does **not** block locally generated CWA imagery.

Run the dependency-free JavaScript regression check with `node scripts/check_dashboard.mjs`. GitHub Actions runs this before building and deploying the site.

## Enable the site

In the repository, open **Settings → Pages** and set **Source** to **GitHub Actions**. Then open the **Actions** tab and run **Build and deploy severe weather dashboard**. After the first successful deployment, the site will be available at the repository's GitHub Pages URL.

## Add more CWA-specific offices

Edit `config/cwas.txt` and add one three-letter office identifier per line:

```text
LIX
MOB
JAN
LCH
```

The WFO dropdown still supports all listed offices for SPC and the other national guidance. A selected office receives CWA-specific NADOCast panels only when its identifier is included in `config/cwas.txt` and has completed a successful workflow build.

Generating every CWA on every scheduled run would create hundreds of large maps and may exceed normal GitHub Actions runtime/storage limits, so the repository intentionally uses an explicit office list.

## Run locally

Create the conda environment:

```bash
conda env create -f environment.yml
conda activate nadocast-dashboard
python scripts/build_site.py
```

Open `site/index.html` through a local web server, not directly from the filesystem, because the dashboard fetches JSON manifests:

```bash
python -m http.server 8000 --directory site
```

Then browse to `http://localhost:8000`.

## Manual mapper example

```bash
python scripts/run_nadocast_cwa.py --cwa LIX --date latest --run latest \
  --hazards tornado wind_adj hail sig_tornado sig_wind_adj sig_hail \
  --out-dir outputs/LIX --cache-dir cache
```

NADOCast is experimental third-party guidance and is not official NWS or SPC guidance.
