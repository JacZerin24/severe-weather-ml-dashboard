#!/usr/bin/env python3
"""Best-effort diagnostic of NSSL's official v1.2 viewer asset references.

Does not serve images or infer freshness from fixed PNG URLs. Use the workflow
logs to identify documented/verified upstream imagery before wiring automation.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests
import urllib3

PAGES = [
    "https://apps.nssl.noaa.gov/s2s-severe/forecast_gefs_ml.html",
    "https://apps.nssl.noaa.gov/s2s-severe/forecast_gefs_mlSWERVE.html",
    "https://apps.nssl.noaa.gov/s2s-severe/forecast_products.html",
    "https://apps.nssl.noaa.gov/tgalarneau/realtime/swerve/day08_dprogdt/2026_day8_dprogdt.html",
    "https://inside.nssl.noaa.gov/tgalarneau/swerve-forecast-links/",
]

HEADERS = {"User-Agent": "SevereWeatherDashboard/1.0 NSSL source-discovery"}


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.js = []
        self.images = []
        self.forms = []

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if tag == "script" and props.get("src"):
            self.js.append(props["src"])
        elif tag == "img" and props.get("src"):
            self.images.append(props["src"])
        elif tag == "input" and ("v1.2" in str(props) or "severe" in str(props).lower()):
            self.forms.append(props)


def main():
    for url in PAGES:
        try:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=8)
                unverified = False
            except requests.exceptions.SSLError:
                print(f"Certificate-chain validation failure for {url}; retrying for diagnostic only", flush=True)
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                resp = requests.get(url, headers=HEADERS, timeout=8, verify=False)
                unverified = True
            print(f"PROBE {resp.status_code} {resp.url} bytes={len(resp.content)} verified_tls={not unverified}", flush=True)
            if resp.status_code != 200:
                continue
            refs = References()
            refs.feed(resp.text)
            print("  scripts", [urljoin(resp.url, x) for x in refs.js[:20]], flush=True)
            print("  images", refs.images[:10], flush=True)
            print("  inputs", refs.forms[:5], flush=True)
            if "swerve-forecast-links" in resp.url:
                links = re.findall(r'<a[^>]*href=["\\\']([^"\\\']+)["\\\'][^>]*>(.*?)</a>', resp.text, re.I | re.S)
                for href, title in links:
                    visible = re.sub(r'<[^>]*>', '', title).strip()
                    if any(k in visible.lower() for k in ("nssl", "ml", "gefs", "severe")):
                        print(f"  RELATED LINK {visible[:75]} => {urljoin(resp.url, href)}", flush=True)
            for match in re.findall(r'.{0,65}(?:v1[._]2|gefs|\\.png).{0,100}', resp.text, re.I)[:8]:
                print("  HTML CLUE", match.strip(), flush=True)
        except requests.RequestException as err:
            print(f"PROBE FAILED {url}: {err}", flush=True)


if __name__ == "__main__":
    main()
