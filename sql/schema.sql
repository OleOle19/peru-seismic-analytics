-- Dedicated portfolio database. Executed by the Python loader in SeismicAnalytics only.
IF OBJECT_ID('dbo.DimDate','U') IS NULL
CREATE TABLE dbo.DimDate(date_key int NOT NULL PRIMARY KEY, [date] date NOT NULL UNIQUE,
    [year] smallint NOT NULL, [month] tinyint NOT NULL CHECK([month] BETWEEN 1 AND 12),
    year_month char(7) NOT NULL, month_start date NOT NULL);
IF OBJECT_ID('dbo.DimZone','U') IS NULL
BEGIN
    CREATE TABLE dbo.DimZone(zone_key tinyint NOT NULL PRIMARY KEY, zone nvarchar(60) NOT NULL,
        latitude_min decimal(6,2) NOT NULL, latitude_max decimal(6,2) NOT NULL);
    INSERT INTO dbo.DimZone VALUES (1,N'Norte (-7 a 0°)',-7,0),(2,N'Centro (-14 a -7°)',-14,-7),(3,N'Sur (-20 a -14°)',-20,-14);
END;
IF OBJECT_ID('dbo.DimMagnitude','U') IS NULL
BEGIN
    CREATE TABLE dbo.DimMagnitude(magnitude_key tinyint NOT NULL PRIMARY KEY,
        magnitude_band nvarchar(40) NOT NULL, magnitude_min decimal(4,2) NOT NULL, magnitude_max decimal(4,2) NULL);
    INSERT INTO dbo.DimMagnitude VALUES (1,N'3.5 a <4',3.5,4),(2,N'4 a <5',4,5),(3,N'5 a <6',5,6),(4,N'6 o más',6,NULL);
END;
IF OBJECT_ID('dbo.FactEvent','U') IS NULL
BEGIN
    CREATE TABLE dbo.FactEvent(
        event_id varchar(80) NOT NULL PRIMARY KEY, time_utc datetime2(3) NOT NULL,
        date_key int NOT NULL REFERENCES dbo.DimDate(date_key),
        latitude decimal(9,5) NOT NULL CHECK(latitude BETWEEN -90 AND 90),
        longitude decimal(9,5) NOT NULL CHECK(longitude BETWEEN -180 AND 180),
        depth_km decimal(9,3) NOT NULL CHECK(depth_km BETWEEN -100 AND 1000),
        magnitude decimal(4,2) NOT NULL CHECK(magnitude BETWEEN -2 AND 10),
        magnitude_type nvarchar(30) NOT NULL, zone_key tinyint NOT NULL REFERENCES dbo.DimZone(zone_key),
        magnitude_key tinyint NOT NULL REFERENCES dbo.DimMagnitude(magnitude_key),
        depth_band nvarchar(60) NOT NULL, place nvarchar(300) NOT NULL, status nvarchar(30) NOT NULL,
        updated_utc datetime2(3) NOT NULL, source_url nvarchar(400) NOT NULL);
    CREATE INDEX IX_FactEvent_Date ON dbo.FactEvent(date_key) INCLUDE(magnitude,depth_km,zone_key);
    CREATE INDEX IX_FactEvent_ZoneMagnitude ON dbo.FactEvent(zone_key,magnitude) INCLUDE(date_key);
END;
IF OBJECT_ID('dbo.ETLRun','U') IS NULL
CREATE TABLE dbo.ETLRun(run_id varchar(40) NOT NULL PRIMARY KEY, started_utc datetime2 NOT NULL,
    completed_utc datetime2 NOT NULL, start_date date NOT NULL, end_date date NOT NULL,
    min_magnitude decimal(4,2) NOT NULL, received int NOT NULL, loaded int NOT NULL,
    rejected int NOT NULL, duplicates_removed int NOT NULL);
GO
CREATE OR ALTER VIEW dbo.vw_EventDetail AS
SELECT f.*,d.[date],d.[year],d.[month],d.year_month,d.month_start,z.zone,m.magnitude_band
FROM dbo.FactEvent f JOIN dbo.DimDate d ON d.date_key=f.date_key
JOIN dbo.DimZone z ON z.zone_key=f.zone_key JOIN dbo.DimMagnitude m ON m.magnitude_key=f.magnitude_key;
GO
CREATE OR ALTER VIEW dbo.vw_MonthlyEvents AS
SELECT d.[year],d.[month],d.year_month,d.month_start,COUNT(f.event_id) AS events,
    AVG(f.magnitude) AS avg_magnitude,MAX(f.magnitude) AS max_magnitude,
    SUM(CASE WHEN f.magnitude>=5 THEN 1 ELSE 0 END) AS events_m5_plus
FROM dbo.DimDate d LEFT JOIN dbo.FactEvent f ON f.date_key=d.date_key
GROUP BY d.[year],d.[month],d.year_month,d.month_start;
GO
