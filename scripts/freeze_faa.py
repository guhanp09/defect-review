"""Freeze selected public facts, never narratives or submitter contact details.

Usage: python scripts/freeze_faa.py data/raw/SDR-2025.csv
The adjacent retrieval.json must identify the original download.
"""

import csv
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

FIELDS = {
    "report_id": "OperatorControlNumber",
    "occurrence_date": "DifficultyDate",
    "submitted_at": "SubmissionDate",
    "make": "AircraftMake",
    "model": "AircraftModel",
    "jasc": "JASCCode",
    "part_name": "PartName",
    "part_number": "PartNumber",
    "part_condition": "PartCondition",
    "component_name": "ComponentName",
}


def freeze(raw, destination):
    provenance = json.loads(raw.with_name("retrieval.json").read_text())
    actual_hash = hashlib.sha256(raw.read_bytes()).hexdigest()
    if actual_hash != provenance["sha256"]:
        raise ValueError("Download differs from its retrieval manifest")
    rows = []
    with raw.open(encoding="utf-8-sig", newline="") as source:
        for original in csv.DictReader(source):
            row = {key: " ".join(original[value].split()) for key, value in FIELDS.items()}
            registry = original["RegistryNNumber"].strip().upper()
            # A public registry identifier is a linkage key, not a particular component.
            row["aircraft_key"] = (
                hashlib.sha256(("FAA-registry:" + registry).encode()).hexdigest()[:24]
                if registry
                else ""
            )
            rows.append(row)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=[*FIELDS, "aircraft_key"])
    writer.writeheader()
    writer.writerows(rows)
    payload = gzip.compress(stream.getvalue().encode(), mtime=0)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    provenance.update(
        {
            "selected_rows": len(rows),
            "fact_file": destination.name,
            "fact_sha256": hashlib.sha256(payload).hexdigest(),
            "extract_version": 1,
            "excluded_fields": "Narratives, submitter/operator identifiers, serials and registry text",
            "aircraft_key": "First 24 hex characters of SHA256('FAA-registry:' + normalized registry). Public linkage, not anonymization.",
            "year_basis": "Observed: all selected DifficultyDate values are in 2025; submissions include 2026. The downloaded filename is not used to infer submission year.",
        }
    )
    destination.with_name("provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"rows": len(rows), "compressed_bytes": len(payload)}))


if __name__ == "__main__":
    freeze(Path(sys.argv[1]), Path("data/faa_2025_facts.csv.gz"))
