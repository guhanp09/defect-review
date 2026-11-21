-- All event-count outputs use accepted, distinct report identities.
-- No public output is a failure rate: fleet exposure and reporting coverage are absent.
CREATE VIEW monthly_reports AS
SELECT strftime(occurrence_date, '%Y-%m') AS month, count(*) AS reports,
       count(DISTINCT aircraft_key) AS linked_aircraft,
       count(*) FILTER (WHERE year(submitted_at) > year(occurrence_date)) AS later_year_submissions
FROM accepted GROUP BY 1 ORDER BY 1;

CREATE VIEW system_drilldown AS
SELECT coalesce(ata_chapter, 'REVIEW') AS ata_chapter,
       jasc, jasc_title, make, model,
       count(*) AS reports, count(DISTINCT aircraft_key) AS linked_aircraft
FROM accepted GROUP BY 1,2,3,4,5 ORDER BY reports DESC, jasc, make, model;

CREATE VIEW component_drilldown AS
SELECT jasc, part_name, part_number, part_condition, count(*) AS reports
FROM accepted GROUP BY 1,2,3,4 ORDER BY reports DESC, jasc, part_name, part_number;

CREATE VIEW repeat_candidates AS
WITH preceding AS (
  SELECT *, lag(report_id) OVER w AS prior_report_id,
    lag(occurrence_date) OVER w AS prior_date
  FROM accepted
  WHERE aircraft_key IS NOT NULL AND jasc_title IS NOT NULL
  WINDOW w AS (PARTITION BY aircraft_key, jasc ORDER BY occurrence_date, report_id)
)
SELECT report_id, prior_report_id, aircraft_key, jasc, occurrence_date, prior_date,
       date_diff('day', prior_date, occurrence_date) AS gap_days
FROM preceding
WHERE date_diff('day', prior_date, occurrence_date) BETWEEN 0 AND 30
ORDER BY occurrence_date, report_id;
