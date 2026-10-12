from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from seismic.pipeline import transform, dimensions

START, END = date(2024, 1, 1), date(2025, 1, 1)


def event(id="a", mag=4.5, lat=-12, lon=-77, depth=30, updated=1704153600000, time=1704067200000):
    return {
        "id": id,
        "geometry": {"type": "Point", "coordinates": [lon, lat, depth]},
        "properties": {
            "mag": mag,
            "time": time,
            "updated": updated,
            "type": "earthquake",
            "place": "Test",
            "magType": "mb",
            "status": "reviewed",
        },
    }


def test_keep_latest_revision_and_count_duplicates():
    df, q = transform([event(mag=4), event(mag=4.7, updated=1704240000000)], START, END)
    assert len(df) == 1 and df.iloc[0].magnitude == 4.7 and q["duplicates_removed"] == 1


def test_missing_magnitude_is_rejected_not_filled():
    df, q = transform([event(mag=None)], START, END)
    assert df.empty and q["rejections"][0]["reason"] == "missing_or_invalid_magnitude"


def test_end_exclusive_and_bounds():
    df, q = transform(
        [event(id="end", time=1735689600000), event(id="outside", lon=-60), event(id="good")],
        START,
        END,
    )
    assert df.event_id.tolist() == ["good"] and q["excluded_by_scope"] == 2


def test_zone_and_depth_boundaries():
    df, _ = transform(
        [
            event(id="north", lat=-7, depth=70),
            event(id="center", lat=-14, depth=300),
            event(id="south", lat=-20, depth=30),
        ],
        START,
        END,
    )
    rows = df.set_index("event_id")
    assert (
        rows.loc["north", "zone_key"] == 1
        and rows.loc["center", "zone_key"] == 2
        and rows.loc["south", "zone_key"] == 3
    )
    assert (
        rows.loc["north", "depth_band"] == "Intermedio (70-300 km)"
        and rows.loc["center", "depth_band"] == "Profundo (≥300 km)"
    )


def test_invalid_coordinates_and_nonfinite():
    df, q = transform([event(id="bad", lat=91), event(id="nan", mag=float("nan"))], START, END)
    assert df.empty and q["rejected_count"] == 2


def test_calendar_contains_days_without_events_and_leap_day():
    df = dimensions(START, END)
    assert len(df) == 366 and 20240229 in df.date_key.values and df.date_key.is_unique


def test_latest_revision_outside_scope_removes_older_event():
    df, q = transform([event(mag=4.5), event(mag=3.0, updated=1704240000000)], START, END)
    assert df.empty and q["duplicates_removed"] == 1 and q["excluded_by_scope"] == 1


def test_latest_revision_with_missing_magnitude_is_not_replaced_by_old_value():
    df, q = transform([event(mag=4.5), event(mag=None, updated=1704240000000)], START, END)
    assert df.empty and q["rejected_count"] == 1 and q["duplicates_removed"] == 1


def test_malformed_records_are_reported_not_crashed():
    df, q = transform([None, {"id": "bad", "properties": []}, event()], START, END)
    assert len(df) == 1 and q["rejected_count"] == 2
