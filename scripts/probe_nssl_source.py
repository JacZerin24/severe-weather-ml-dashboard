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

PAGE = "https://apps.nssl.noaa.gov/s2s-severe/forecast_gefs_ml.html"
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
    try:
        try:
            resp = requests.get(PAGE, headers=HEADERS, timeout=15)
            unverified = False
        except requests.exceptions.SSLError:
            print("NSSL HTTPS certificate chain failed verification. Diagnostic retry ONLY with unverified TLS.", flush=True)
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(PAGE, headers=HEADERS, timeout=15, verify=False)
            unverified = True
        print(f"NSSL source probe: page HTTP {resp.status_code}, size {len(resp.content)}, url {resp.url}", flush=True)
        resp.raise_for_status()
        refs = References()
        refs.feed(resp.text)
        print("NSSL linked scripts:", [urljoin(resp.url, x) for x in refs.js[:24]], flush=True)
        print("NSSL image sample:", refs.images[:20], flush=True)
        print("NSSL input sample:", refs.forms[:12], flush=True)
        matches = []
        for pattern in (r'.{0,95}severe.{0,95}v1[_.]2.{0,95}', r'.{0,80}\\.png.{0,80}', r'.{0,80}\\.gif.{0,80}'):
            matches.extend(re.findall(pattern, resp.text, flags=re.I)[:10])
        print("NSSL embedded source clues:", matches[:20], flush=True)
        # Fetch only a bounded number of same-origin custom scripts for investigation.
        for script in refs.js[:15]:
            url = urljoin(resp.url, script)
            if not url.startswith("https://apps.nssl.noaa.gov/"):
                continue
            if not any(token in url.lower() for token in ("gefs", "forecast", "s2s", "product", "map")):
                continue
            try:
                js = requests.get(url, headers=HEADERS, timeout=10, verify=not unverified)
                print(f"Script {url}: HTTP {js.status_code}, {len(js.content)} bytes", flush=True)
                print("  matching snippets:", re.findall(r'.{0,90}(?:v1[_.]2|\\.png|\\.gif|gefs).{0,130}', js.text, re.I)[:8], flush=True)
            except requests.RequestException as err:
                print(f"  script request failed: {err}", flush=True)
    except requests.RequestException as err:
        print(f"NSSL source probe unavailable: {err}", flush=True)


if __name__ == "__main__":
    main()
