-- Run in SeismicAnalytics. All queries are read-only.
-- 1. Events and high-magnitude events per month, including months with zero records.
SELECT year_month, events, events_m5_plus, max_magnitude
FROM dbo.vw_MonthlyEvents ORDER BY year_month;

-- 2. Monthly change. The final month may be incomplete.
WITH series AS (
 SELECT year_month, events,LAG(events) OVER (ORDER BY year_month) AS previous_month
 FROM dbo.vw_MonthlyEvents
)
SELECT *,CAST(100.0*(events-previous_month)/NULLIF(previous_month,0) AS decimal(10,2)) AS change_percent
FROM series ORDER BY year_month;

-- 3. Descriptive geographic bands (not Peruvian administrative regions).
SELECT zone,COUNT(*) AS events,MAX(magnitude) AS max_magnitude,AVG(depth_km) AS avg_depth_km
FROM dbo.vw_EventDetail GROUP BY zone ORDER BY events DESC;

-- 4. Most significant magnitudes in the selected catalog.
SELECT TOP(10) event_id,time_utc,place,magnitude,magnitude_type,depth_km,source_url
FROM dbo.FactEvent ORDER BY magnitude DESC,time_utc DESC;

-- 5. Extraction traceability.
SELECT TOP(10) * FROM dbo.ETLRun ORDER BY completed_utc DESC;

-- 6. Grain and integrity: one row per unique USGS event.
SELECT COUNT(*) AS rows,COUNT(DISTINCT event_id) AS unique_ids FROM dbo.FactEvent;
