# DefectReview

Aircraft service-difficulty analysis in SQL and Python. The question is what a
public defect-report extract can support before fleet exposure and maintenance
records are available.

**[Read the engineering review](https://guhanp09.github.io/defect-review/)** ·
[SQL](src/defect_review/review.sql) · [Machine-readable results](reports/review.json)

The frozen FAA export contains **67,653 reports**. Four occurrence/submission-date
inconsistencies are quarantined, leaving **67,649 accepted reports**, **519
make/model pairs** and **436 distinct JASC values**. Counts reconcile across monthly,
system/model and part/condition reports. These public records are not a complete
operator fleet extract.

The date distinction matters: all occurrences in this snapshot are dated 2025,
but **2,487 accepted reports were submitted in 2026 on a UTC date basis**. Counting
by the file's name would hide reporting delay. The original timestamp offsets are
retained in the frozen facts.

The same-aircraft/JASC, 30-day queue contains **9,998 later-day candidates** and
**18,866 same-day candidates**. These are links for investigation, not confirmed
repeat defects. Different components and findings can share that code and day.

## Run the review

Python 3.12 or later. The checked-in, selected-field FAA extract is about 1.8 MB;
normal reproduction needs no network download.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]' -c constraints.txt
python -m pytest -q
ruff check src tests scripts
defect-review
python scripts/check_artifacts.py
```

Open `reports/index.html`. GitHub Actions regenerates the review, checks committed
output parity and publishes the verified artifact to Pages.

## What is calculated

- **Public reports:** distinct report identities, occurrence/submission dates,
  JASC titles, limited ATA chapter grouping, system/model/part drilldowns and
  traceable adjacent-report candidates. Exact duplicates collapse; conflicting
  identities are quarantined after the reporting cutoff.
- **Separate synthetic fleet:** removals per 1,000 flight hours, two-sided Garwood
  Poisson intervals, MTBUR and a predeclared six-month baseline. A later-month
  screening example identifies August for investigation. September's absent
  exposure blocks its rate. These invented hours are never joined to FAA assets.

Public SDR counts cannot establish failure rates, dispatch reliability, fleet risk,
root cause or the effectiveness of a repair. JASC is a modified ATA taxonomy;
manufacturer-specific coding still needs review. Code 3418 is deliberately not
silently relabeled ATA 34. No maintenance interval or airworthiness decision is made.

## Evidence

- [Methods and counting contract](docs/methods.md)
- [Engineering handoff and review findings](docs/review-notes.md)
- [Quarantined identities](reports/quarantine.csv)
- [Source URL, retrieval time and checksums](data/provenance.json)
- [Synthetic assumptions](data/synthetic_exposure.json)

The FAA supplies the public records. This project supplies the extract, analysis,
tests and reports. Narratives, submitter identities and serial numbers are not
redistributed. A registry-derived hash is a stable public linkage key, not a claim
of anonymization. Original report identifiers remain for source reconciliation.

[FAA annual SDR export](https://www.faa.gov/av-info/download_SDR) ·
[FAA JASC reference](https://www.faa.gov/sites/faa.gov/files/JASC_Code.pdf) ·
[FAA reliability-program guidance](https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentID/1035253)

MIT license for repository code. FAA material retains its source attribution.
