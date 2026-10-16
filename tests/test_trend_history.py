#!/usr/bin/env python3
"""Test NADOCast UTC valid-day grouping and midnight rollover."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from forecast_validity import annotate, describe_product
from trend_history import update_cwa_trends
from build_site import build_manifest


def item(date, run, lead, hazard="tornado", image="current.png"):
    return {
        "image": image, "hazard": hazard, "run_date": date, "run_dir": run,
        "lead_label": lead, "max_cwa": 12.0, "mean_cwa": 3.0, "max_buffer": 18.0,
    }


class ValidityTests(unittest.TestCase):
    def test_all_major_nadocast_windows(self):
        cases = [
            ("20261016", "t0z", "f12-35", "2026-10-16", "2026-10-16 12Z", "2026-10-17 11Z"),
            ("20261016", "t12z", "f02-23", "2026-10-16", "2026-10-16 14Z", "2026-10-17 11Z"),
            ("20261016", "t18z", "f02-17", "2026-10-16", "2026-10-16 20Z", "2026-10-17 11Z"),
            ("20261016", "t12z", "f24-47", "2026-10-17", "2026-10-17 12Z", "2026-10-18 11Z"),
            ("20261016", "t18z", "f01-17", "2026-10-16", "2026-10-16 19Z", "2026-10-17 11Z"),
            ("20261231", "t12z", "f24-47", "2027-01-01", "2027-01-01 12Z", "2027-01-02 11Z"),
        ]
        for run_date, run, lead, date, start, end in cases:
            with self.subTest(run_date=run_date, run=run, lead=lead):
                result = describe_product(run_date, run, lead)
                self.assertEqual((result.outlook_date, result.valid_start_utc, result.valid_end_utc),
                                 (date, start, end))

    def test_never_accept_windows_spanning_two_outlooks(self):
        for lead in ("f01-24", "f12-36", "f02-28", "f05-04", "f00-48", "foo"):
            with self.subTest(lead=lead):
                with self.assertRaises(ValueError):
                    describe_product("20261016", "t12z", lead)

    def test_manifest_uses_real_valid_date_not_lead_bin(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            results = []
            for i, (date, run, lead) in enumerate([
                ("20261014", "t12z", "f02-23"),
                ("20261014", "t12z", "f24-47"),
                ("20261015", "t0z", "f12-35"),
            ]):
                results.append({
                    **item(date, run, lead),
                    "png": str(out / f"map{i}.png"), "filename": f"run{i}.grib2",
                })
            path = build_manifest(results, "LIX", out, today=dt.date(2026, 10, 15))
            data = json.loads(path.read_text())
            self.assertEqual(data["products"]["day1"]["tornado"]["run_date"], "20261015")
            self.assertEqual(data["products"]["day2"], {})
            self.assertEqual(data["valid_products"]["2026-10-14"]["tornado"]["lead_label"], "f02-23")
            self.assertEqual(data["valid_products"]["2026-10-15"]["tornado"]["valid_start_utc"], "2026-10-15 12Z")


class ArchiveTests(unittest.TestCase):
    def test_trends_match_outlook_date_with_midnight_rollover(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            site=root/"site"/"nadocast"/"LIX"
            site.mkdir(parents=True)
            archive=root/"archive"/"nadocast"
            path=site/"latest.json"

            def publish(run_date, run, lead, today):
                product=annotate(item(run_date,run,lead))
                (site/"current.png").write_bytes(b"PNG"+run_date.encode()+run.encode()+lead.encode())
                path.write_text(json.dumps({
                    "cwa": "LIX",
                    "valid_products": {product["valid_date"]: {"tornado": product}},
                    "products": {},
                }))
                return update_cwa_trends(path,archive,today=today)

            a=publish("20261014","t12z","f02-23",dt.date(2026,10,14))
            self.assertEqual(len(a["trends_by_valid_date"]["2026-10-14"]["tornado"]),1)
            b=publish("20261014","t12z","f24-47",dt.date(2026,10,14))
            self.assertEqual(len(b["trends_by_valid_date"]["2026-10-15"]["tornado"]),1)
            c=publish("20261015","t0z","f12-35",dt.date(2026,10,15))
            frames=c["trends_by_valid_date"]["2026-10-15"]["tornado"]
            self.assertEqual(len(frames),2)
            self.assertEqual([f["run_date"] for f in frames],["20261015","20261014"])
            self.assertTrue(all(f["valid_date"]=="2026-10-15" for f in frames))
            self.assertNotIn("2026-10-14", [f["valid_date"] for f in frames])
            again=publish("20261015","t0z","f12-35",dt.date(2026,10,15))
            self.assertEqual(len(again["trends_by_valid_date"]["2026-10-15"]["tornado"]),2)
            for f in frames:
                self.assertTrue((site/f["image"]).is_file())

    def test_legacy_cache_reclassified_by_real_validity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            site=root/"site"/"nadocast"/"LIX"
            site.mkdir(parents=True)
            cache=root/"archive"/"nadocast"/"LIX"
            cache.mkdir(parents=True)
            (cache/"legacy_day2.png").write_bytes(b"VALID ARCHIVED FORECAST")
            (cache/"legacy_day1.png").write_bytes(b"OLD DAY 1")
            old = {
                "day1": {"tornado": [{**item("20261014","t12z","f02-23"),"image":"legacy_day1.png"}]},
                "day2": {"tornado": [{**item("20261014","t12z","f24-47"),"image":"legacy_day2.png"}]},
            }
            (cache/"history.json").write_text(json.dumps(old))
            (site/"latest.json").write_text(json.dumps({"cwa":"LIX","valid_products":{}}))
            data=update_cwa_trends(site/"latest.json",root/"archive"/"nadocast",
                                   today=dt.date(2026,10,15))
            self.assertEqual(data["trends_by_valid_date"]["2026-10-15"]["tornado"][0]["lead_label"],"f24-47")
            self.assertEqual(data["trends_by_valid_date"]["2026-10-14"]["tornado"][0]["lead_label"],"f02-23")


if __name__=="__main__":
    unittest.main()
