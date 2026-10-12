from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import re
import shutil
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pyodbc
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[2]
API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
BOUNDS = {"minlatitude": -20, "maxlatitude": 0, "minlongitude": -84, "maxlongitude": -68}
COLUMNS = [
    "event_id",
    "time_utc",
    "date_key",
    "year_month",
    "latitude",
    "longitude",
    "depth_km",
    "magnitude",
    "magnitude_type",
    "zone_key",
    "zone",
    "magnitude_key",
    "magnitude_band",
    "depth_band",
    "place",
    "status",
    "updated_utc",
    "source_url",
]
ZONES = [
    (1, "Norte (-7 a 0°)", -7, 0),
    (2, "Centro (-14 a -7°)", -14, -7),
    (3, "Sur (-20 a -14°)", -20, -14),
]
MAGNITUDES = [
    (1, "3.5 a <4", 3.5, 4),
    (2, "4 a <5", 4, 5),
    (3, "5 a <6", 5, 6),
    (4, "6 o más", 6, None),
]


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )


def client():
    s = requests.Session()
    s.headers["User-Agent"] = "PeruSeismicAnalytics/1.0 (educational portfolio)"
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def download(start: date, end: date, min_magnitude: float, raw_dir: Path):
    """Year-sized requests avoid the API's 20,000-result limit; truncate is an error."""
    features, manifests = [], []
    with client() as session:
        cursor = start
        while cursor < end:
            stop = min(date(cursor.year + 1, 1, 1), end)
            params = {
                "format": "geojson",
                "starttime": cursor.isoformat(),
                "endtime": stop.isoformat(),
                "minmagnitude": min_magnitude,
                "eventtype": "earthquake",
                "orderby": "time-asc",
                "limit": 20000,
                **BOUNDS,
            }
            logging.info("Descargando %s a %s", cursor, stop)
            response = session.get(API, params=params, timeout=(15, 120))
            response.raise_for_status()
            payload = response.json()
            if payload.get("type") != "FeatureCollection" or not isinstance(
                payload.get("features"), list
            ):
                raise ValueError("USGS did not return a valid FeatureCollection")
            if len(payload["features"]) >= 20000:
                raise ValueError(
                    "Possible truncated response. Narrow the extraction period or increase the minimum magnitude."
                )
            raw_path = raw_dir / f"usgs_{cursor}_{stop}.geojson"
            write_json(raw_path, payload)
            manifests.append(
                {
                    "file": str(raw_path.relative_to(ROOT)),
                    "count": len(payload["features"]),
                    "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                    "request": response.url,
                }
            )
            features.extend(payload["features"])
            cursor = stop
            time.sleep(0.2)
    return features, manifests


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def transform(features, start: date, end: date, min_magnitude=3.5):
    # Resolve source revisions BEFORE applying analytical filters. An older revision
    # must not survive when the latest magnitude/location falls outside the scope.
    latest, invalid = {}, []
    for feature in features:
        if not isinstance(feature, dict):
            invalid.append(feature)
            continue
        props = feature.get("properties")
        if (
            not isinstance(props, dict)
            or not isinstance(feature.get("id"), str)
            or not finite(props.get("updated"))
        ):
            invalid.append(feature)
            continue
        key = feature["id"]
        if key not in latest or props["updated"] >= latest[key]["properties"]["updated"]:
            latest[key] = feature
    selected = list(latest.values()) + invalid
    duplicates = len(features) - len(selected)
    rows, rejected = [], []
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    outside = 0
    for feature in selected:
        if (
            not isinstance(feature, dict)
            or not isinstance(feature.get("properties"), dict)
            or not isinstance(feature.get("geometry"), dict)
        ):
            rejected.append({"event_id": None, "reason": "invalid_record_structure"})
            continue
        event_id = feature.get("id")
        props = feature.get("properties") or {}
        geom = feature.get("geometry") or {}
        coord = geom.get("coordinates")
        if not isinstance(coord, list):
            coord = []
        reason = None
        if not isinstance(event_id, str) or not event_id:
            reason = "missing_id"
        elif geom.get("type") != "Point" or len(coord) < 3 or not all(finite(v) for v in coord[:3]):
            reason = "invalid_coordinates_or_depth"
        elif not finite(props.get("mag")):
            reason = "missing_or_invalid_magnitude"
        elif not finite(props.get("time")) or not finite(props.get("updated")):
            reason = "invalid_timestamp"
        elif props.get("type") != "earthquake":
            reason = "not_earthquake"
        if reason:
            rejected.append({"event_id": event_id, "reason": reason})
            continue
        lon, lat, depth = coord[:3]
        if (
            not -180 <= lon <= 180
            or not -90 <= lat <= 90
            or not -100 <= depth <= 1000
            or not -2 <= props["mag"] <= 10
        ):
            rejected.append({"event_id": event_id, "reason": "out_of_domain"})
            continue
        try:
            timestamp = pd.to_datetime(props["time"], unit="ms", utc=True)
            updated = pd.to_datetime(props["updated"], unit="ms", utc=True)
        except (ValueError, OverflowError):
            rejected.append({"event_id": event_id, "reason": "invalid_timestamp"})
            continue
        if not (
            start_ts <= timestamp < end_ts
            and -84 <= lon <= -68
            and -20 <= lat <= 0
            and props["mag"] >= min_magnitude
        ):
            outside += 1
            continue
        zone = ZONES[0] if lat >= -7 else ZONES[1] if lat >= -14 else ZONES[2]
        mag_key = 1 if props["mag"] < 4 else 2 if props["mag"] < 5 else 3 if props["mag"] < 6 else 4
        rows.append(
            [
                event_id,
                timestamp,
                int(timestamp.strftime("%Y%m%d")),
                timestamp.strftime("%Y-%m"),
                lat,
                lon,
                depth,
                props["mag"],
                props.get("magType") or "No informado",
                zone[0],
                zone[1],
                mag_key,
                MAGNITUDES[mag_key - 1][1],
                "Superficial (<70 km)"
                if depth < 70
                else "Intermedio (70-300 km)"
                if depth < 300
                else "Profundo (≥300 km)",
                props.get("place") or "No informado",
                props.get("status") or "No informado",
                updated,
                props.get("url") or f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}",
            ]
        )
    frame = pd.DataFrame(rows, columns=COLUMNS)
    before = len(frame)
    if not frame.empty:
        frame = (
            frame.sort_values(["updated_utc", "event_id"])
            .drop_duplicates("event_id", keep="last")
            .sort_values("time_utc")
            .reset_index(drop=True)
        )
    quality = {
        "received": len(features),
        "valid_unique": len(frame),
        "duplicates_removed": duplicates + before - len(frame),
        "excluded_by_scope": outside,
        "rejected_count": len(rejected),
        "rejections": rejected,
        "completeness": "Events reported in this USGS extraction; not every earthquake that occurred.",
    }
    return frame, quality


def dimensions(start, end):
    dates = pd.date_range(start, end - pd.Timedelta(days=1))
    return pd.DataFrame(
        {
            "date_key": dates.strftime("%Y%m%d").astype(int),
            "date": dates.strftime("%Y-%m-%d"),
            "year": dates.year,
            "month": dates.month,
            "year_month": dates.strftime("%Y-%m"),
            "month_start": dates.to_period("M").to_timestamp().strftime("%Y-%m-%d"),
        }
    )


def connection(database=None):
    server = os.getenv("SQL_SERVER", "localhost")
    db = database or os.getenv("SQL_DATABASE", "SeismicAnalytics")
    driver = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", db):
        raise ValueError("Invalid database name")
    if db != "master" and db != "SeismicAnalytics":
        raise ValueError(
            "This portfolio loader only writes to the dedicated SeismicAnalytics database"
        )
    if any(c in server + driver for c in [";", "{", "}"]):
        raise ValueError("Invalid connection configuration")
    return pyodbc.connect(
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={db};Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate={os.getenv('SQL_TRUST_CERTIFICATE', 'yes')};",
        timeout=15,
        autocommit=db == "master",
    )


def schema():
    with connection("master") as con:
        con.execute("IF DB_ID(N'SeismicAnalytics') IS NULL CREATE DATABASE [SeismicAnalytics]")
    sql = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    with connection() as con:
        for batch in re.split(r"^GO\s*$", sql, flags=re.MULTILINE):
            if batch.strip():
                con.execute(batch)
        con.commit()


def load_sql(frame, calendar, quality, run_id, started, start, end, min_mag):
    schema()
    with connection() as con:
        try:
            cur = con.cursor()
            cur.execute("SET XACT_ABORT ON")
            cur.execute(
                "DECLARE @result int; EXEC @result=sys.sp_getapplock @Resource=N'PortfolioSeismicSnapshot', @LockMode=N'Exclusive', @LockOwner=N'Transaction', @LockTimeout=15000; IF @result<0 THROW 50001, 'Another extraction is writing the snapshot. Try again later.', 1;"
            )
            cur.execute("DELETE FROM dbo.FactEvent")
            cur.execute("DELETE FROM dbo.DimDate")
            cur.fast_executemany = True
            cur.executemany(
                "INSERT INTO dbo.DimDate(date_key,[date],[year],[month],year_month,month_start) VALUES (?,?,?,?,?,?)",
                list(calendar.itertuples(index=False, name=None)),
            )
            cols = [
                "event_id",
                "time_utc",
                "date_key",
                "latitude",
                "longitude",
                "depth_km",
                "magnitude",
                "magnitude_type",
                "zone_key",
                "magnitude_key",
                "depth_band",
                "place",
                "status",
                "updated_utc",
                "source_url",
            ]
            values = []
            for row in frame[cols].itertuples(index=False, name=None):
                values.append(
                    tuple(
                        v.to_pydatetime().replace(tzinfo=None) if isinstance(v, pd.Timestamp) else v
                        for v in row
                    )
                )
            if values:
                cur.executemany(
                    "INSERT INTO dbo.FactEvent("
                    + ",".join(cols)
                    + ") VALUES ("
                    + ",".join("?" for _ in cols)
                    + ")",
                    values,
                )
            cur.execute(
                "INSERT INTO dbo.ETLRun(run_id,started_utc,completed_utc,start_date,end_date,min_magnitude,received,loaded,rejected,duplicates_removed) VALUES (?,?,?,?,?,?,?,?,?,?)",
                run_id,
                started,
                datetime.now(timezone.utc).replace(tzinfo=None),
                start,
                end,
                min_mag,
                quality["received"],
                len(frame),
                quality["rejected_count"],
                quality["duplicates_removed"],
            )
            con.commit()
        except Exception:
            con.rollback()
            raise


def upload_s3(paths, run_id):
    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket:
        raise ValueError("Set AWS_S3_BUCKET and configure an AWS profile before using --upload-s3")
    import boto3

    session = boto3.Session(
        profile_name=os.getenv("AWS_PROFILE") or None,
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    s3 = session.client("s3")
    for path in paths:
        key = f"peru-seismic/{run_id}/{path.relative_to(ROOT).as_posix()}"
        s3.upload_file(str(path), bucket, key, ExtraArgs={"ServerSideEncryption": "AES256"})
        # Verify the remote content, not only a successful HTTP upload.
        response = s3.get_object(Bucket=bucket, Key=key)
        digest = hashlib.sha256()
        try:
            for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
                digest.update(chunk)
        finally:
            response["Body"].close()
        if (
            digest.hexdigest() != hashlib.sha256(path.read_bytes()).hexdigest()
            or response.get("ServerSideEncryption") != "AES256"
        ):
            raise ValueError(f"S3 integrity/encryption verification failed for {key}")
        logging.info("S3: %s", key)


def run(args):
    load_dotenv(ROOT / ".env")
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if end <= start or end > datetime.now(timezone.utc).date() + pd.Timedelta(days=1):
        raise ValueError("The end date must follow start and cannot be in the future")
    if not finite(args.min_magnitude) or not 3.5 <= args.min_magnitude <= 10:
        raise ValueError("Minimum magnitude must be ≥3.5 for the defined magnitude dimension")
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    run_id = started.strftime("%Y%m%dT%H%M%S%fZ")
    raw = ROOT / "data" / "raw" / run_id
    processed = ROOT / "data" / "staging" / run_id
    processed.mkdir(parents=True, exist_ok=True)
    if args.from_raw:
        features, manifest = [], []
        for path in sorted(Path(args.from_raw).glob("*.geojson")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("type") != "FeatureCollection" or not isinstance(
                payload.get("features"), list
            ):
                raise ValueError("Invalid archived USGS collection")
            features.extend(payload["features"])
            raw.mkdir(parents=True, exist_ok=True)
            copied = raw / path.name
            shutil.copyfile(path, copied)
            manifest.append(
                {
                    "file": str(copied.relative_to(ROOT)),
                    "count": len(payload["features"]),
                    "sha256": hashlib.sha256(copied.read_bytes()).hexdigest(),
                    "reused_archive": True,
                }
            )
        if not features:
            raise ValueError("No events found in the specified raw directory")
    else:
        features, manifest = download(start, end, args.min_magnitude, raw)
    frame, quality = transform(features, start, end, args.min_magnitude)
    if frame.empty:
        raise ValueError("No valid events. Database snapshot was not replaced.")
    calendar = dimensions(start, end)
    frame.to_csv(processed / "events.csv", index=False, encoding="utf-8")
    calendar.to_csv(processed / "dim_date.csv", index=False, encoding="utf-8")
    pd.DataFrame(ZONES, columns=["zone_key", "zone", "latitude_min", "latitude_max"]).to_csv(
        processed / "dim_zone.csv", index=False, encoding="utf-8"
    )
    pd.DataFrame(
        MAGNITUDES, columns=["magnitude_key", "magnitude_band", "magnitude_min", "magnitude_max"]
    ).to_csv(processed / "dim_magnitude.csv", index=False, encoding="utf-8")
    fact_columns = [
        "event_id",
        "time_utc",
        "date_key",
        "latitude",
        "longitude",
        "depth_km",
        "magnitude",
        "magnitude_type",
        "zone_key",
        "magnitude_key",
        "depth_band",
        "place",
        "status",
        "updated_utc",
        "source_url",
    ]
    frame[fact_columns].to_csv(processed / "fact_event.csv", index=False, encoding="utf-8")
    quality.update(
        {
            "run_id": run_id,
            "source": "USGS",
            "start_inclusive": str(start),
            "end_exclusive": str(end),
            "min_magnitude": args.min_magnitude,
            "bounds": BOUNDS,
            "downloaded_at_utc": started.isoformat() + "Z",
            "files": manifest,
        }
    )
    write_json(processed / "quality.json", quality)
    write_json(raw / "manifest.json", quality)
    if not args.no_sql:
        load_sql(frame, calendar, quality, run_id, started, start, end, args.min_magnitude)
        with connection() as con:
            cursor = con.execute(
                "SELECT run_id,completed_utc,start_date,end_date,min_magnitude,received,loaded,rejected,duplicates_removed FROM dbo.ETLRun ORDER BY completed_utc"
            )
            pd.DataFrame.from_records(
                [tuple(r) for r in cursor.fetchall()], columns=[c[0] for c in cursor.description]
            ).to_csv(processed / "etl_runs.csv", index=False, encoding="utf-8")
    else:
        pd.DataFrame(
            [
                {
                    "run_id": run_id,
                    "completed_utc": datetime.now(timezone.utc).replace(tzinfo=None),
                    "start_date": start,
                    "end_date": end,
                    "min_magnitude": args.min_magnitude,
                    "received": quality["received"],
                    "loaded": len(frame),
                    "rejected": quality["rejected_count"],
                    "duplicates_removed": quality["duplicates_removed"],
                }
            ]
        ).to_csv(processed / "etl_runs.csv", index=False, encoding="utf-8")
    # Do not replace the published CSV snapshot when a SQL transaction fails.
    published = ROOT / "data" / "processed"
    published.mkdir(parents=True, exist_ok=True)
    for path in processed.iterdir():
        os.replace(path, published / path.name)
    processed.rmdir()
    processed = published
    from seismic.insights import build_insights

    build_insights(
        frame,
        calendar,
        quality,
        ROOT / "docs" / "Resultados.md",
        ROOT / "artifacts" / "summary.json",
    )
    if args.upload_s3:
        upload_s3(
            list(raw.glob("*.geojson")) + list(processed.glob("*")) + [raw / "manifest.json"],
            run_id,
        )
    logging.info(
        "Listo: %s eventos válidos; %s rechazados; %s duplicados.",
        len(frame),
        quality["rejected_count"],
        quality["duplicates_removed"],
    )
    return frame, quality


def main():
    parser = argparse.ArgumentParser(
        description="USGS → Python/Pandas → SQL Server → Power BI; optional AWS S3"
    )
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument(
        "--end",
        default=(datetime.now(timezone.utc).date() + pd.Timedelta(days=1)).isoformat(),
        help="Exclusive end, in UTC",
    )
    parser.add_argument("--min-magnitude", type=float, default=3.5)
    parser.add_argument("--no-sql", action="store_true")
    parser.add_argument("--upload-s3", action="store_true")
    parser.add_argument("--from-raw", help="Reuse an archived raw directory without downloading")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args)


if __name__ == "__main__":
    main()
