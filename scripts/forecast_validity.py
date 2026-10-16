#!/usr/bin/env python3
"""NADOCast 12Z–12Z outlook-day validity calculations.

A filename's fAA-BB means an inclusive range of forecast hours from the
initialization, not a Day 1/Day 2 label. Reject products crossing an outlook
boundary or with unknown run metadata rather than silently mislabeling them.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

UTC = dt.timezone.utc
RUN_HOURS = {"t0z": 0, "t00z": 0, "t10z": 10, "t12z": 12, "t14z": 14, "t18z": 18, "t20z": 20}
LEAD_PATTERN = re.compile(r"^f(\d{1,3})-(\d{1,3})$")
DATE_PATTERN = re.compile(r"^\d{8}$")


@dataclass(frozen=True)
class Validity:
    outlook_date: str
    valid_start_utc: str
    valid_end_utc: str
    outlook_start_utc: str
    outlook_end_utc: str
    init_utc: str

    def as_dict(self) -> dict[str, str]:
        return {
            "valid_date": self.outlook_date,
            "valid_start_utc": self.valid_start_utc,
            "valid_end_utc": self.valid_end_utc,
            "outlook_start_utc": self.outlook_start_utc,
            "outlook_end_utc": self.outlook_end_utc,
            "init_utc": self.init_utc,
        }


def describe_product(run_date: str, run_dir: str, lead_label: str) -> Validity:
    if not DATE_PATTERN.fullmatch(str(run_date)):
        raise ValueError(f"Invalid NADOCast run date: {run_date}")
    run_hour = RUN_HOURS.get(str(run_dir).lower())
    if run_hour is None:
        raise ValueError(f"Unknown NADOCast initialization: {run_dir}")
    m = LEAD_PATTERN.fullmatch(str(lead_label).lower())
    if not m:
        raise ValueError(f"Unknown NADOCast forecast period: {lead_label}")
    first, last = map(int, m.groups())
    if first < 0 or last < first or last - first >= 24:
        raise ValueError(f"Invalid NADOCast lead span: {lead_label}")
    init = dt.datetime.strptime(str(run_date), "%Y%m%d").replace(tzinfo=UTC)
    init += dt.timedelta(hours=run_hour)
    start = init + dt.timedelta(hours=first)
    end = init + dt.timedelta(hours=last + 1)  # exclusive
    outlook = (start - dt.timedelta(hours=12)).date()
    anchor = dt.datetime.combine(outlook, dt.time(12), tzinfo=UTC)
    if start < anchor or end > anchor + dt.timedelta(days=1):
        raise ValueError(
            f"NADOCast {run_date} {run_dir} {lead_label} crosses 12Z outlook boundary: "
            f"{start.isoformat()} to {end.isoformat()}"
        )
    return Validity(
        outlook_date=outlook.isoformat(),
        valid_start_utc=start.strftime("%Y-%m-%d %HZ"),
        valid_end_utc=(end - dt.timedelta(hours=1)).strftime("%Y-%m-%d %HZ"),
        outlook_start_utc=anchor.strftime("%Y-%m-%d %HZ"),
        outlook_end_utc=(anchor + dt.timedelta(days=1)).strftime("%Y-%m-%d %HZ"),
        init_utc=init.strftime("%Y-%m-%d %HZ"),
    )


def annotate(product: dict) -> dict:
    return {**product, **describe_product(
        product["run_date"], product["run_dir"], product["lead_label"]
    ).as_dict()}
