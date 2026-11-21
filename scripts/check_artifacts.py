"""Verify data/artifact integrity and public-versus-synthetic separation."""

import csv
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "reports/build_manifest.json").read_text())
for group, directory in [("inputs", "data"), ("outputs", "reports")]:
    for name, expected in manifest[group].items():
        assert hashlib.sha256((root / directory / name).read_bytes()).hexdigest() == expected, name
review = json.loads((root / "reports/review.json").read_text())
assert review["public_failure_rates"] is None
assert review["summary"]["reports"] == review["quality"]["accepted_reports"]
assert sum(r["reports"] for r in review["monthly"]) == review["summary"]["reports"]
with (root / "reports/system_drilldown.csv").open() as handle:
    assert (
        sum(int(row["reports"]) for row in csv.DictReader(handle)) == review["summary"]["reports"]
    )
html = (root / "reports/index.html").read_text()
assert f"{review['summary']['reports']:,}</strong>" in html
assert "Separate synthetic fleet" in html
assert review["public_source"]["sha256"] in html
print("Input checksums, report totals, HTML and public/synthetic boundaries agree.")
