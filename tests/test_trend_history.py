#!/usr/bin/env python3
"""Regression checks for retained CWA map history; no external data needed."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from trend_history import update_cwa_trends  # noqa: E402


class CwaHistoryTests(unittest.TestCase):
    def test_cycle_history_and_day2_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = root / "site" / "nadocast" / "LIX"
            site.mkdir(parents=True)
            archive = root / "archive" / "nadocast"
            path = site / "latest.json"

            def write(run, day2=False):
                run_date, run_dir = run
                product = {
                    "image": "current.png",
                    "hazard": "tornado",
                    "run_date": run_date,
                    "run_dir": run_dir,
                    "lead_label": "f02-23",
                    "max_cwa": float({"t0z": 10, "t12z": 15, "t18z": 20}.get(run_dir, 0)),
                    "mean_cwa": 3.0,
                    "max_buffer": 18.0,
                }
                (site / "current.png").write_bytes(b"PNG TEST BYTES" + run_dir.encode())
                products = {"day1": {"tornado": product}, "day2": {}}
                if day2:
                    d2 = {**product, "lead_label": "f24-47"}
                    (site / "day2.png").write_bytes(b"PNG DAY2 TEST")
                    d2["image"] = "day2.png"
                    products["day2"]["tornado"] = d2
                path.write_text(json.dumps({"cwa": "LIX", "products": products}))
                return update_cwa_trends(path, archive)

            first = write(("20261014", "t0z"))
            self.assertEqual(len(first["trends"]["day1"]["tornado"]), 1)
            second = write(("20261014", "t12z"), day2=True)
            self.assertEqual(len(second["trends"]["day1"]["tornado"]), 2)
            self.assertEqual(len(second["trends"]["day2"]["tornado"]), 1)
            third = write(("20261014", "t18z"))
            self.assertEqual(len(third["trends"]["day1"]["tornado"]), 3)
            self.assertEqual(third["trends"]["day1"]["tornado"][0]["run_dir"], "t18z")
            self.assertEqual(len(third["trends"]["day2"]["tornado"]), 1)
            repeated = write(("20261014", "t18z"))
            self.assertEqual(len(repeated["trends"]["day1"]["tornado"]), 3)
            for frame in repeated["trends"]["day1"]["tornado"]:
                self.assertTrue((site / frame["image"]).is_file())
            fourth = write(("20261015", "t0z"))
            self.assertEqual(len(fourth["trends"]["day1"]["tornado"]), 4)
            fifth = write(("20261015", "t12z"))
            self.assertEqual(len(fifth["trends"]["day1"]["tornado"]), 4)
            self.assertEqual(fifth["trends"]["day1"]["tornado"][0]["run_date"], "20261015")
            self.assertEqual(len(list((archive / "LIX").glob("day1_tornado*.png"))), 4)


if __name__ == "__main__":
    unittest.main()
