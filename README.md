# Severe Weather ML Dashboard

Static GitHub Pages dashboard that combines SPC, CSU MLP, NSSL GEFS ML, long-range CFS guidance, and locally generated CWA-specific NADOCast probability maps.

## How it works

- `index.html` is the dashboard shown by GitHub Pages.
- `scripts/run_nadocast_cwa.py` downloads NADOCast GRIB2 files and creates CWA-centered PNG maps.
- `scripts/build_site.py` builds the static site, runs the mapper for each configured office, and writes a small `latest.json` manifest that the dashboard reads.
- `.github/workflows/deploy-pages.yml` rebuilds and deploys the site after pushes, manual runs, and three times daily after the normal NADOCast update windows.

The original dashboard used proxied CONUS NADOCast PNGs. This version replaces that card with generated maps centered on the selected CWA, including CWA/buffer statistics and significant-severe hatching when the corresponding significant product is available.

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
