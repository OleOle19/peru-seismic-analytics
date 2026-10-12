"""Opt-in checks against this portfolio's dedicated local database."""

import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from seismic.pipeline import connection
import pyodbc

pytestmark = pytest.mark.skipif(
    os.getenv("SEISMIC_TEST_SQL") != "1", reason="Set SEISMIC_TEST_SQL=1 to verify local SQL Server"
)


def test_snapshot_grain_and_relationships():
    with connection() as con:
        count, unique = con.execute(
            "SELECT COUNT(*),COUNT(DISTINCT event_id) FROM dbo.FactEvent"
        ).fetchone()
        assert count > 0 and count == unique
        missing = con.execute(
            "SELECT COUNT(*) FROM dbo.FactEvent f LEFT JOIN dbo.DimDate d ON f.date_key=d.date_key LEFT JOIN dbo.DimZone z ON f.zone_key=z.zone_key LEFT JOIN dbo.DimMagnitude m ON f.magnitude_key=m.magnitude_key WHERE d.date_key IS NULL OR z.zone_key IS NULL OR m.magnitude_key IS NULL"
        ).fetchval()
        assert missing == 0


def test_failed_write_rolls_back_previous_changes():
    with connection() as con:
        original = con.execute("SELECT COUNT(*) FROM dbo.FactEvent").fetchval()
        con.execute(
            "DELETE FROM dbo.FactEvent WHERE event_id=(SELECT TOP 1 event_id FROM dbo.FactEvent ORDER BY event_id)"
        )
        with pytest.raises(pyodbc.IntegrityError):
            con.execute(
                "INSERT INTO dbo.DimDate(date_key,[date],[year],[month],year_month,month_start) VALUES (20990101,'2099-01-01',2099,13,'2099-01','2099-01-01')"
            )
        con.rollback()
        assert con.execute("SELECT COUNT(*) FROM dbo.FactEvent").fetchval() == original


def test_monthly_view_keeps_calendar_months():
    with connection() as con:
        monthly, events = con.execute(
            "SELECT COUNT(*),SUM(events) FROM dbo.vw_MonthlyEvents"
        ).fetchone()
        expected = con.execute("SELECT COUNT(DISTINCT year_month) FROM dbo.DimDate").fetchval()
        assert (
            monthly == expected
            and events == con.execute("SELECT COUNT(*) FROM dbo.FactEvent").fetchval()
        )
