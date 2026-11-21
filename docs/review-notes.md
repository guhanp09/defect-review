# Engineering review notes

## Observations worth carrying forward

JASC 5320 has 8,540 accepted reports, 3350 has 7,824, and 2560 has 3,264. The queue
therefore starts with fuselage miscellaneous structure, emergency lighting and
emergency equipment as reporting workload. It cannot establish which system is
least reliable without comparable exposure, capture and operating context.

The 18,866 same-day linked candidates are a warning against counting every linked
pair as recurrence. The 9,998 later-day candidates still require maintenance record
and installed-component reconciliation. A human investigation should establish:

1. Whether two reports concern the same event, physical item and configuration.
2. The applicable manufacturer ATA code, operating condition and maintenance task.
3. What was observed, removed, inspected, repaired or tested, with source evidence.
4. Competing explanations and what evidence would distinguish them.
5. Proposed corrective action, review authority, cost, owner and completion evidence.

No repair recommendation is generated from a word such as LEAKING. A condition is
an observation, not a complete failure mechanism.

## Changes made during review

| Concern | Resolution and evidence |
| --- | --- |
| A year label could hide late reporting | Separate occurrence and UTC submission dates; retain source offsets and explain the 2,484/2,487 distinction |
| Rejected records could disappear into a counter | Added a source-identity quarantine CSV for the four date inconsistencies |
| Same-day findings could inflate recurrence claims | Report 18,866 same-day and 9,998 later-day candidates separately |
| Modified JASC coding could imply exact ATA equivalence | Preserve source codes; leave stall warning/unmapped chapter groupings for review |
| An absent month could be interpreted as zero events | Require consecutive explicit month rows in the exposure example |
| Zero events could look certain; unknown exposure could look healthy | Positive zero-event upper bound; undefined missing/zero-exposure rate; invalid event/exposure combinations fail |
| Platform math could create meaningless output diffs | Pin numerical dependencies and round interval exports to nine decimals; display three |

Twenty-one tests cover independent rate values, date/timezone errors, conflicting
identities, cutoff-before-deduplication, SQL grain and 0/30/31-day boundaries.
Artifact checks reconcile accepted counts, exports, hashes and the rendered review.

The next useful input is an exposure and maintenance-history extract with an
agreed grain and capture definition. More elaborate models on these public counts
would not supply that missing information.
