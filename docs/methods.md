# Counting and rate contract

## Source and time

The annual FAA CSV was retrieved on 21 November 2026. Its byte-level SHA256 and
retrieval timestamp are in `data/provenance.json`. `scripts/freeze_faa.py` checks
that hash before selecting factual fields. `gzip` has a fixed timestamp, making
the compressed extract deterministic. Re-fetching the live FAA URL can produce a
different snapshot; retain a new manifest instead of overwriting the old claim.

`DifficultyDate` is an occurrence date without a timezone. `SubmissionDate` is an
offset timestamp; analysis converts it to a UTC date. Submission cutoff is applied
before deduplication. No information submitted after a chosen cutoff resolves an
earlier report identity. This is not a reconstructed point-in-time operator database:
the downloaded export may itself include later revisions to older records.

Four rows with occurrence dates after submission are quarantined rather than
corrected by guessing. The original identities and dates appear in the output.
The accepted extract has 2,487 UTC-year 2026 submissions; counting the literal
source timestamp year gives 2,484 in the entire raw file. Midnight timezone
boundaries account for the distinction. Neither count is a failure rate.

## Identity, coding and drilldowns

One accepted identity is one report, not one aircraft failure. Identical selected
facts with the same report ID collapse. Differing selected facts under one ID
quarantine all versions; the file does not supply a reliable revision ordering.
Conflicts solely in excluded narrative fields are outside this selected-fact
identity check. No fuzzy text matching merges two different report IDs.

Blank aircraft linkage is SQL NULL and does not form a repeat group. A known JASC
code and two adjacent accepted reports with the same linkage key form a candidate
when the occurrence-date gap is 0–30 days, inclusive. Same-day candidates remain
explicit because structural inspections can produce several separate findings.
The queue does not establish the same installed component or event.

The frozen FAA JASC table supplies titles. A limited crosswalk supplies coarse ATA
chapters where supported by the shared system taxonomy. The original code is
always retained. JASC 3418 stall warning and unmapped chapters have no asserted ATA
match. There are 112 accepted reports whose ATA grouping requires review.

SQL outputs use the same accepted table and reconcile to its total. Missing part
numbers/conditions are retained as unknown, not inferred from a component name.
Top reported systems describe the extract's workload, not risk rankings across
systems or manufacturers.

## Separate exposure example

The synthetic fleet has one fixed system/fleet population per month. For removals
`n` and known fleet flight hours `H`, the rate is `1,000 n/H`. MTBUR is `H/n` for
positive removals and exposure; zero removals do not establish infinite life.
No installed-position multiplier is used or implied.

For confidence 95%, the Garwood count bounds are `0.5 χ²(.025, 2n)` (zero when
`n=0`) and `0.5 χ²(.975, 2(n+1))`; multiply by `1,000/H` for rate bounds. At zero
events and 1,000 hours the upper bound is 3.688879454 per 1,000 hours, not zero.
Missing hours and zero hours do not become zero rates. Events at zero hours fail
reconciliation. Missing calendar months must be explicit rows.

The first six months define a frozen baseline of 6 removals / 12,300 hours, or
0.487805 per 1,000 hours. A later month is a screening candidate when its lower
interval exceeds that point estimate. This ignores baseline uncertainty,
multiple looks, event dependence, fleet mix and capture errors. It is not a
validated operational alarm, an FAA-accepted reliability program or authority to
change maintenance intervals.

FAA context: [AC 120-17B, active information page](https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentID/1035253).
The [July 2026 editorial update](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_120-17B_Ed_Upd_%287-9-26%29.pdf)
describes reliability-program data, standards, investigation and approval processes.
This small study does not implement that complete program.
