# Severe Weather ML Dashboard

Static GitHub Pages dashboard that combines SPC, CSU MLP, NSSL GEFS ML, long-range CFS guidance, locally generated CWA-specific NADOCast probability maps, and optional CONUS NADOCast archive imagery.

## How it works

- `index.html` is the dashboard shown by GitHub Pages.
- `scripts/run_nadocast_cwa.py` downloads NADOCast GRIB2 files and creates CWA-centered PNG maps.
- `scripts/build_site.py` builds the static site, runs the mapper for each configured office, and writes a small `latest.json` manifest that the dashboard reads.
- `.github/workflows/deploy-pages.yml` rebuilds and deploys the site after pushes, manual runs, and three times daily after the normal NADOCast update windows.

The dashboard defaults to generated NADOCast maps centered on the selected CWA, including CWA/buffer statistics and significant-severe hatching when the corresponding significant product is available. Switch the NADOCast **Local CWA / CONUS + Trends** tabs to view the reference dashboard's proxied CONUS forecast cycles, without losing the CWA-specific maps.

## Interactive dashboard controls

- Select any WFO to view its SPC outlooks and the locally generated CWA NADOCast tornado, wind, and hail probabilities.
- **NADOCast CWA trends** show up to four distinct saved model cycles per hazard and office. Run labels, actual lead windows, and CWA/buffer statistics change with each frame. Use **Prev / Next**, or **Left / Right Arrow** while zoomed. **Escape** closes zoom.
- Trend images are preserved between scheduled deploys using a GitHub Actions cache restored before the map build and saved afterward. The first updated deployment will have one cycle; more accumulate as fresh cycles become available. Older or failed runs are never presented as new.
- CSU MLP and NSSL replacement guidance are treated independently. CSU maintains valid-date-anchored forecast-cycle trends. SPC retains clickable hazard tabs.
- **NSSL GEFS ML v1.2:** the former weather.gov/EAX mirrored PNGs have stopped updating. Until the official image service can be reliably fetched and its forecast initialization validated, the dashboard links directly to the official NSSL v1.2 interactive viewer rather than presenting stale images as current. A nonblocking source diagnostic runs in GitHub Actions to determine a suitable new ingestion method.
- The page retries missing remote images every five seconds and refreshes every 30 minutes.

The historical CONUS NADOCast tabs and AllOrigins proxy have been removed because they frequently fail to load. The CWA products are generated from NADOCast GRIB2 input; original geographic context, meaningful probabilities and significant-severe overlays are retained.

**Local checks:**

```bash
node scripts/check_dashboard.mjs
python -m unittest discover -s tests -p 'test_*.py'
```

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
