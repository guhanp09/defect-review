"""Build reproducible public-count and synthetic-exposure reviews."""

import argparse
import csv
import gzip
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

import duckdb

from defect_review.reliability import rate_review


def normalize(rows, catalog, as_of, audit=None):
    """Apply the cutoff before identity resolution. Quarantine conflicting identities."""
    grouped = defaultdict(list)
    quality = Counter()

    def rejected(row, reason):
        quality[reason] += 1
        if audit is not None:
            audit.append(
                {
                    "report_id": row.get("report_id", ""),
                    "reason": reason,
                    "occurrence_date": row.get("occurrence_date", ""),
                    "submitted_at": row.get("submitted_at", ""),
                }
            )

    for row in rows:
        cleaned = {key: " ".join(str(value or "").split()) for key, value in row.items()}
        try:
            occurrence = datetime.strptime(cleaned["occurrence_date"], "%m/%d/%Y").date()
            submitted = datetime.fromisoformat(cleaned["submitted_at"])
            if submitted.tzinfo is None:
                raise ValueError("submission timezone absent")
            submitted = submitted.astimezone(timezone.utc).date()
        except (KeyError, ValueError):
            rejected(cleaned, "invalid_date")
            continue
        if submitted > as_of:
            rejected(cleaned, "after_cutoff")
            continue
        if occurrence > submitted:
            rejected(cleaned, "occurrence_after_submission")
            continue
        if not cleaned.get("report_id"):
            rejected(cleaned, "missing_identity")
            continue
        cleaned.update(occurrence_date=occurrence.isoformat(), submitted_at=submitted.isoformat())
        grouped[cleaned["report_id"]].append(cleaned)
    accepted = []
    for identity in sorted(grouped):
        versions = {json.dumps(row, sort_keys=True) for row in grouped[identity]}
        if len(versions) > 1:
            for row in grouped[identity]:
                rejected(row, "conflicting_identity_rows")
            continue
        quality["exact_duplicate_rows"] += len(grouped[identity]) - 1
        row = grouped[identity][0]
        mapping = catalog.get(row["jasc"])
        row.update(
            jasc_title=mapping["title"] if mapping else "",
            ata_chapter=(mapping["ata_chapter"] or "") if mapping else "",
        )
        if mapping is None:
            quality["unrecognized_jasc"] += 1
        if not row["ata_chapter"]:
            quality["ata_grouping_requires_review"] += 1
        accepted.append(row)
    quality["accepted_reports"] = len(accepted)
    return accepted, dict(quality)


def warehouse(rows):
    connection = duckdb.connect()
    fields = {
        "report_id": "VARCHAR",
        "occurrence_date": "DATE",
        "submitted_at": "DATE",
        "make": "VARCHAR",
        "model": "VARCHAR",
        "jasc": "VARCHAR",
        "part_name": "VARCHAR",
        "part_number": "VARCHAR",
        "part_condition": "VARCHAR",
        "component_name": "VARCHAR",
        "aircraft_key": "VARCHAR",
        "jasc_title": "VARCHAR",
        "ata_chapter": "VARCHAR",
    }
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "accepted.csv"
        with source.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        connection.execute(
            "CREATE TABLE accepted AS SELECT * FROM read_csv(?, columns=?, nullstr='')",
            [str(source), fields],
        )
    connection.execute(Path(__file__).with_name("review.sql").read_text())
    return connection


def records(connection, query):
    result = connection.execute(query)
    columns = [column[0] for column in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def write_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def table(rows, columns):
    region = escape(" / ".join(label for _, label in columns[:2]), quote=True)
    head = "".join("<th scope='col'>" + escape(label) + "</th>" for _, label in columns)
    body = []
    for row in rows:
        values = []
        for key, _ in columns:
            value = row.get(key)
            if isinstance(value, float):
                value = f"{value:.3f}"
            values.append("<td>" + escape("—" if value is None else str(value)) + "</td>")
        body.append("<tr>" + "".join(values) + "</tr>")
    return (
        f"<div class='scroll' role='region' aria-label='{region}' tabindex='0'><table><thead><tr>"
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def build(root, as_of):
    data = root / "data"
    output = root / "reports"
    output.mkdir(exist_ok=True)
    provenance = json.loads((data / "provenance.json").read_text())
    facts = data / provenance["fact_file"]
    if hashlib.sha256(facts.read_bytes()).hexdigest() != provenance["fact_sha256"]:
        raise ValueError("Frozen fact checksum mismatch")
    catalog = json.loads((data / "jasc_catalog.json").read_text())["codes"]
    with gzip.open(facts, "rt", newline="") as handle:
        original = list(csv.DictReader(handle))
    audit = []
    accepted, quality = normalize(original, catalog, as_of, audit=audit)
    write_csv(output / "quarantine.csv", audit)
    connection = warehouse(accepted)
    summary = records(
        connection,
        """
        SELECT count(*) AS reports,
        count(*) FILTER (WHERE year(submitted_at)=2026) AS submitted_in_2026,
        count(DISTINCT make || ':' || model) AS make_model_pairs,
        count(*) FILTER (WHERE aircraft_key IS NULL) AS missing_aircraft_key,
        count(DISTINCT jasc) AS jasc_values,
        min(occurrence_date)::VARCHAR AS first_occurrence,
        max(occurrence_date)::VARCHAR AS last_occurrence
        FROM accepted
    """,
    )[0]
    outputs = {}
    for view in ["monthly_reports", "system_drilldown", "component_drilldown", "repeat_candidates"]:
        outputs[view] = records(connection, f"SELECT * FROM {view}")
        write_csv(output / (view + ".csv"), outputs[view])
    summary["repeat_candidate_reports"] = len(outputs["repeat_candidates"])
    summary["same_day_candidates"] = sum(r["gap_days"] == 0 for r in outputs["repeat_candidates"])
    top = records(
        connection,
        """
        SELECT jasc, jasc_title, coalesce(ata_chapter,'REVIEW') AS ata_chapter,
          count(*) AS reports FROM accepted GROUP BY 1,2,3
        ORDER BY reports DESC, jasc LIMIT 12
    """,
    )
    # Synthetic asset identities never overlap the public registry-derived keys.
    synthetic = json.loads((data / "synthetic_exposure.json").read_text())
    rates = rate_review(synthetic["months"])
    write_csv(output / "synthetic_rates.csv", rates)
    result = {
        "as_of": as_of.isoformat(),
        "public_source": provenance,
        "summary": summary,
        "quality": quality,
        "top_systems": top,
        "monthly": outputs["monthly_reports"],
        "synthetic_exposure": {**synthetic, "results": rates},
        "public_failure_rates": None,
        "rate_reason": "No fleet-level flight-hour/cycle exposure or reporting coverage supplied.",
    }
    (output / "review.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    count = summary["reports"]
    late = summary["submitted_in_2026"]
    repeats = summary["repeat_candidate_reports"]
    month_table = table(
        outputs["monthly_reports"],
        [
            ("month", "Occurrence month"),
            ("reports", "Reports"),
            ("linked_aircraft", "Distinct linked aircraft"),
            ("later_year_submissions", "Submitted in a later year"),
        ],
    )
    system_table = table(
        top,
        [
            ("jasc", "JASC"),
            ("jasc_title", "FAA JASC title"),
            ("ata_chapter", "ATA chapter grouping*"),
            ("reports", "Reports"),
        ],
    )
    rate_table = table(
        rates,
        [
            ("month", "Synthetic month"),
            ("removals", "Unscheduled removals"),
            ("flight_hours", "Assumed flight hours"),
            ("rate", "/1,000 h"),
            ("lower", "95% lower"),
            ("upper", "95% upper"),
            ("mtbur_hours", "MTBUR h"),
            ("screen", "Screen"),
        ],
    )
    html = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>DefectReview | Engineering review</title>
<style>body{{font:16px/1.55 system-ui,sans-serif;color:#20313c;background:#f4f6f7;margin:0}}
main{{max-width:1140px;margin:auto;padding:32px 22px}}h1{{font-size:2.5rem;margin:.2em 0}}
h2{{margin-top:2em}}a{{color:#065b82}}.kpis{{display:flex;gap:16px;flex-wrap:wrap}}
.card{{background:white;border:1px solid #bdcbd1;padding:16px;flex:1;min-width:180px}}
.card strong{{display:block;font-size:2rem}}.note{{border-left:4px solid #ad6619;padding:12px;background:#fff7e8}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;background:white;font-size:.9rem}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid #c4d1d7}}th{{background:#e3edf1}}
code{{overflow-wrap:anywhere}}footer{{margin-top:3rem;border-top:1px solid #bdcbd1;padding-top:16px}}</style>
<main><header><p>FAA public reports · frozen source snapshot · review cutoff {as_of}</p>
<h1>DefectReview</h1><p>Aircraft service-difficulty reports, with the counting rules exposed.</p>
<a href="https://github.com/guhanp09/defect-review">Source, SQL and reproduction</a></header>
<div class="kpis"><div class="card"><strong>{count:,}</strong>Accepted public reports</div>
<div class="card"><strong>{late:,}</strong>2025 occurrences submitted in 2026 (UTC)</div>
<div class="card"><strong>{repeats:,}</strong>30-day same-aircraft/JASC candidates</div></div>
<p class="note">These are report counts, not fleet failure rates. Public reporting coverage and fleet exposure
are unavailable. A repeat candidate does not establish the same component, a recurring physical defect or root cause.
{summary["same_day_candidates"]:,} candidates are same-day reports and may describe separate findings.</p>
<h2>Occurrence and reporting time</h2>{month_table}
<p>Cutoff applies to submission date in UTC. The filename does not determine submission year.
This extract's occurrence dates run from {summary["first_occurrence"]} to {summary["last_occurrence"]}.</p>
<h2>System review queue</h2>{system_table}
<p>*Chapter grouping is a limited crosswalk. JASC is a modified ATA taxonomy, not an interchangeable
manufacturer code. Stall-warning code 3418 and unmapped chapters remain for review.</p>
<p>Counts rank reporting workload, not risk or system reliability. Obtain fleet hours/cycles, operating context,
removal history, current approved documentation and maintenance findings before corrective-action decisions.</p>
<p><a href="system_drilldown.csv">All system/model groups</a> ·
<a href="component_drilldown.csv">Part/condition counts</a> ·
<a href="repeat_candidates.csv">Traceable repeat-candidate pairs</a> ·
<a href="monthly_reports.csv">Monthly counts</a></p>
<h2>Separate synthetic fleet: exposure and removals</h2>
<p>Illustrative pump fleet, invented monthly removals and flight hours. No public FAA aircraft are joined
to these assumptions. Six baseline months are fixed before later-month screening.</p>{rate_table}
<p>Exact two-sided Garwood intervals assume Poisson counts and known exposure. Zero removals have a positive
upper bound; MTBUR is undefined at zero removals. September's missing hours block a rate.
The screen compares an interval to a baseline point estimate, without repeated-look or baseline-uncertainty
adjustment. It is a review aid, not an approved alert limit or maintenance-program change.</p>
<a href="synthetic_rates.csv">Synthetic rate calculations</a>
<h2>Engineering handoff</h2><ol><li>Reconcile linked reports with source maintenance records; confirm component identity and ATA coding.</li>
<li>Collect exposure, configuration, repair history and part findings before assigning a failure mode.</li>
<li>Write an investigation scope with owner, evidence needed, due date and review authority. Changes require the operator's applicable approvals.</li></ol>
<details><summary>Data quality and source integrity</summary><pre>{escape(json.dumps(quality, indent=2))}</pre>
<p><a href="quarantine.csv">Quarantined rows and reasons</a>. Raw-source SHA256: <code>{provenance["sha256"]}</code>. Exact duplicates collapse;
conflicting report identities are quarantined. Registry text is replaced by a stable linkage key;
this is not an anonymization claim. Narratives and submitter identities are excluded.</p></details>
<footer><a href="https://www.faa.gov/av-info/download_SDR">FAA annual SDR source</a> ·
<a href="https://www.faa.gov/sites/faa.gov/files/JASC_Code.pdf">FAA JASC table</a> ·
<a href="review.json">Machine-readable review</a><p>Independent analysis. No airline affiliation,
maintenance instruction, airworthiness determination or approval.</p></footer></main></html>"""
    (output / "index.html").write_text(html)
    manifest = {"as_of": as_of.isoformat(), "inputs": {}, "outputs": {}}
    for group, paths in [
        ("inputs", sorted(data.glob("*.*"))),
        ("outputs", sorted(output.glob("*.*"))),
    ]:
        for path in paths:
            if path.is_file() and path.name != "build_manifest.json":
                manifest[group][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"summary": summary, "quality": quality}))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 11, 21))
    args = parser.parse_args()
    build(args.root, args.as_of)


if __name__ == "__main__":
    main()
