"""Build the compact hurricane review cases from checksum-pinned NOAA and ECCC files."""

import argparse
import csv
import hashlib
import json
import resource
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


HURDAT = "noaa.nhc.hurdat2.atlantic"
IBTRACS = "noaa.ncei.ibtracs.v04r01.north_atlantic"
HURDAT_SOURCES = {
    "hurdat_current": (HURDAT, "1851–2025 / 2026-09-23", "2026-09-23", "NHC archive release date"),
    "hurdat_previous": (HURDAT, "1851–2025 / 2026-02-27", "2026-02-27", "NHC archive release date"),
}
SOURCE_RELEASES = {
    **HURDAT_SOURCES,
    "ibtracs_na": (IBTRACS, "v04r01", "2026-11-22", "HTTP Last-Modified of the rolling CSV snapshot"),
    "ibtracs_columns": ("noaa.ncei.ibtracs.columns", "v04r01", "2025-09-23", "PDF date"),
    "ibtracs_tech": ("noaa.ncei.ibtracs.technical_details", "v04r01", "2025-04", "PDF month"),
    "nhc_format": ("noaa.nhc.hurdat2.format", "Atlantic format through 2021", "2022-04", "PDF month"),
    "nhc_michael_report": ("noaa.nhc.tcr.AL142018", "2019-05-17 revision", "2019-05-17", "PDF date"),
    "nhc_ian_report": ("noaa.nhc.tcr.AL092022", "2026-03-12 revision", "2026-03-12", "PDF date"),
    "nhc_fiona_report": ("noaa.nhc.tcr.AL072022", "2023-03-23", "2023-03-23", "PDF date"),
    "smart_44488": ("smartatlantic.eccc_opp_44488_east_chedabucto_bay", "time-bounded CSV extract", None, "rolling archive"),
    "eccc_hart_sample": ("eccc.msc.climate-hourly.8202318", "ECCC GeoMet feature", None, "archive feature"),
}
DOCS = {
    "nhc_archive": "https://prod-east-nhc.woc.noaa.gov/data/",
    "noaa_reanalysis": "https://www.aoml.noaa.gov/hrd/data_sub/re_anal.html?print=yes",
    "buoy_metadata": "https://www.ndbc.noaa.gov/station_page.php?station=44488",
    "hart_metadata": "https://climate.weather.gc.ca/climate_normals/results_1991_2020_e.html?climate_id=8202318",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def number(raw):
    return int(raw) if raw not in {"", "-999"} else None


def stamp(date, hour):
    return f"{date[:4]}-{date[4:6]}-{date[6:]}T{hour[:2]}:{hour[2:]}:00Z"


def coordinate(raw):
    magnitude = float(raw[:-1])
    return -magnitude if raw[-1] in {"W", "S"} else magnitude


def verify_sources(source_dir):
    manifest = {
        result["source_key"]: result for result in json.loads((source_dir / "fetch.json").read_text())
    }
    sources = {}
    for key, (dataset_id, version, release_date, release_date_basis) in SOURCE_RELEASES.items():
        fetch = manifest[key]
        file_path = source_dir / key
        with file_path.open("rb") as raw:
            digest = hashlib.file_digest(raw, "sha256").hexdigest()
        if digest != fetch["sha256"] or file_path.stat().st_size != fetch["bytes"]:
            raise ValueError(f"download manifest does not match {key}")
        sources[key] = {
            "dataset_id": dataset_id,
            "version": version,
            "release_date": release_date,
            "release_date_basis": release_date_basis,
            "uri": fetch["effective_url"],
            "sha256": digest,
            "bytes": fetch["bytes"],
            "download_started_at_utc": fetch["started_at_utc"],
            "download_wall_seconds": fetch["fetch_seconds"],
            "http_last_modified": fetch["last_modified"],
            "http_etag": fetch["etag"],
            "failed_attempts": fetch["failed_attempts"],
        }
    return sources


def read_hurdat(file_path, release):
    track_id = None
    remaining = 0
    with file_path.open("rb") as f:
        for line, raw in enumerate(f, 1):
            row = [value.strip() for value in raw.decode("ascii").split(",")]
            if row[0].startswith("AL"):
                if remaining:
                    raise ValueError(f"HURDAT2 header count invalid near line {line}")
                track_id, name, length = row[:3]
                remaining = int(length)
                continue
            if not track_id or not remaining:
                raise ValueError(f"unexpected HURDAT2 row at line {line}")
            remaining -= 1
            date, hour, marker, status, lat, lon, wind, pressure = row[:8]
            yield (
                release, track_id, stamp(date, hour), line, name, marker, status,
                coordinate(lat), coordinate(lon), number(wind), number(pressure),
            )
    if remaining:
        raise ValueError("incomplete final HURDAT2 track")


def read_ibtracs(file_path):
    fields = (
        "SID", "NAME", "ISO_TIME", "TRACK_TYPE", "IFLAG", "USA_AGENCY", "WMO_AGENCY",
        "USA_ATCF_ID", "USA_WIND", "USA_PRES", "WMO_WIND", "WMO_PRES",
    )
    with file_path.open(newline="") as f:
        rows = csv.reader(f)
        header = next(rows)
        indexes = [header.index(field) for field in fields]
        next(rows)  # IBTrACS CSV unit labels
        for line, row in enumerate(rows, 3):
            sid, name, at, kind, flags, usa, wmo, atcf, uw, up, ww, wp = (
                row[index].strip() for index in indexes
            )
            yield (
                line, sid, name, at.replace(" ", "T") + "Z", kind, flags, usa.lower(),
                wmo.lower(), atcf, number(uw), number(up), number(ww), number(wp),
            )


def get_database(source_dir):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE hurdat (
            release, atcf, stamp, line, name, marker, status, latitude, longitude, wind, pressure,
            PRIMARY KEY (release, atcf, stamp)
        );
        CREATE TABLE ibtracs (
            line INTEGER PRIMARY KEY, sid, name, stamp, track_type, iflag, usa_agency, wmo_agency,
            atcf, usa_wind, usa_pressure, wmo_wind, wmo_pressure
        );
    """)
    with db:
        for key in HURDAT_SOURCES:
            db.executemany("INSERT INTO hurdat VALUES (?,?,?,?,?,?,?,?,?,?,?)", read_hurdat(source_dir / key, key))
        db.executemany("INSERT INTO ibtracs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", read_ibtracs(source_dir / "ibtracs_na"))
    return db


COHORT_SQL = """
WITH joined AS (
    SELECT h.*, i.usa_wind, i.usa_pressure, i.wmo_wind, i.wmo_pressure,
           i.usa_agency, i.wmo_agency, substr(i.iflag, 1, 1) AS usa_flag
    FROM hurdat h
    JOIN ibtracs i ON i.atcf = h.atcf AND i.stamp = h.stamp
    WHERE h.release = 'hurdat_current' AND i.track_type = 'main'
), lineage AS (
    SELECT *,
         usa_agency='hurdat_atl' AND wmo_agency='hurdat_atl' AND usa_flag IN ('O','V') AS shared,
         wind = usa_wind AND wind = wmo_wind AS wind_agrees,
         pressure = usa_pressure AND pressure = wmo_pressure AS pressure_agrees
    FROM joined
    WHERE stamp >= :start AND stamp < :stop
)
SELECT count(*) AS exact_key_joined_rows,
       count(DISTINCT atcf || ' ' || stamp) AS distinct_exact_joined_storm_time_keys,
       count(DISTINCT atcf) AS joined_storms,
       count(*) FILTER (WHERE shared) AS shared_hurdat_atl_original_wind_pressure_rows,
       count(*) FILTER (WHERE shared AND wind_agrees) AS shared_exact_wind_triples,
       count(DISTINCT atcf || ' ' || stamp) FILTER (WHERE shared AND wind_agrees) AS distinct_shared_exact_wind_triples,
       count(*) FILTER (WHERE shared AND pressure_agrees) AS shared_exact_nonmissing_pressure_triples,
       count(*) FILTER (WHERE shared AND wind_agrees AND pressure_agrees) AS shared_exact_wind_and_pressure_triples,
       count(DISTINCT atcf || ' ' || stamp) FILTER (WHERE shared AND wind_agrees AND pressure_agrees) AS distinct_shared_exact_wind_and_pressure_triples,
       count(*) FILTER (WHERE shared AND (wind <> usa_wind OR wind <> wmo_wind)) AS shared_nonmissing_wind_disagreements,
       count(*) FILTER (WHERE shared AND (pressure <> usa_pressure OR pressure <> wmo_pressure)) AS shared_nonmissing_pressure_disagreements,
       count(*) FILTER (WHERE usa_flag='I' AND pressure IS NULL AND usa_pressure IS NOT NULL AND wmo_pressure IS NULL) AS exact_key_pressure_fills,
       count(*) FILTER (WHERE usa_agency='hurdat_atl' AND wmo_agency='atcf' AND wind_agrees) AS same_wind_with_different_source_labels
FROM lineage
"""


def fetch_native(db, atcf, at, release="hurdat_current"):
    return db.execute(
        "SELECT * FROM hurdat WHERE release=? AND atcf=? AND stamp=?", (release, atcf, at)
    ).fetchone()


def fetch_ibtracs(db, atcf, at):
    rows = db.execute(
        "SELECT * FROM ibtracs WHERE atcf=? AND stamp=? AND track_type='main'", (atcf, at)
    ).fetchall()
    if len(rows) != 1:
        raise ValueError(f"expected one main IBTrACS row for {atcf} at {at}, got {len(rows)}")
    return rows[0]


def best_track_id(atcf, at):
    return f"nhc-best-track:{atcf}:{at}"


def record(sources, source_key, record_id, source_locator, normalized, origin_records, origin_datasets, role, **extra):
    source = sources[source_key]
    return {
        "record_id": record_id,
        "source_key": source_key,
        "dataset_id": source["dataset_id"],
        "source_locator": source_locator,
        "release_date": source["release_date"],
        "release_date_basis": source["release_date_basis"],
        "uri": source["uri"],
        "sha256": source["sha256"],
        "origin_record_ids": origin_records,
        "origin_dataset_ids": origin_datasets,
        "normalized": normalized,
        "role": role,
        **extra,
    }


def values(wind, pressure, pressure_only):
    if pressure_only:
        return {"pressure_hpa": pressure}
    return {"wind_kt": wind, "pressure_hpa": pressure}


def native_record(sources, row, role="native_best_track", pressure_only=False):
    origin = best_track_id(row["atcf"], row["stamp"])
    return record(
        sources, row["release"], f"{row['release']}:{origin}",
        {"line_1_based": row["line"], "storm_atcf_id": row["atcf"], "timestamp_utc": row["stamp"]},
        values(row["wind"], row["pressure"], pressure_only),
        [origin], [HURDAT], role,
        best_track_status=row["status"], record_marker=row["marker"],
        latitude_deg=row["latitude"], longitude_deg=row["longitude"],
    )


def ibtracs_record(sources, row, group, role, origin_records, origin_datasets, pressure_only=False):
    return record(
        sources, "ibtracs_na", f"ibtracs:{row['sid']}:{row['stamp']}:{group}",
        {"line_1_based": row["line"], "sid": row["sid"], "storm_atcf_id": row["atcf"],
         "timestamp_utc": row["stamp"], "fields": [f"{group.upper()}_{field}" for field in (
             ("PRES",) if pressure_only else ("WIND", "PRES")
         )]},
        values(row[f"{group}_wind"], row[f"{group}_pressure"], pressure_only),
        origin_records, origin_datasets, role, usa_agency=row["usa_agency"],
        wmo_agency=row["wmo_agency"], iflag=row["iflag"],
    )


def shared_case(db, sources, case_id, storm, atcf, at, report, report_locator, use, expected):
    native = fetch_native(db, atcf, at)
    ib = fetch_ibtracs(db, atcf, at)
    assert (native["wind"], native["pressure"]) == expected
    assert ib["usa_agency"] == ib["wmo_agency"] == "hurdat_atl"
    assert ib["iflag"][0] in {"O", "V"}
    assert (ib["usa_wind"], ib["usa_pressure"]) == (ib["wmo_wind"], ib["wmo_pressure"]) == expected
    origin = best_track_id(atcf, at)
    return {
        "case_id": case_id,
        "claim": f"HURDAT2 and IBTrACS independently corroborate the published best-track wind and pressure for {storm}.",
        "review_use": use,
        "records": [native_record(sources, native)] + [
            ibtracs_record(sources, ib, group, "redistributed_best_track", [origin], [HURDAT])
            for group in ("usa", "wmo")
        ],
        "reference": {
            "disposition": "shared_best_track_origin",
            "accept_as_independent_corroboration": False,
            "distinct_best_track_origins": 1,
            "independent_physical_measurement_count": None,
            "accepted_numeric_values": values(*expected, False),
            "evidence": [
                {"source_key": report, "locator": report_locator},
                {"source_key": "ibtracs_columns", "locator": "IFLAG, USA_AGENCY, USA_ATCF_ID"},
                {"source_key": "ibtracs_tech", "locator": "WMO variables and §6.7"},
            ],
            "basis": "Both IBTrACS fields identify hurdat_atl and match the exact native key. The NHC post-analysis estimate can synthesize several observations. The fields and releases do not identify their physical observation inputs, and IBTrACS does not identify the exact source file digest.",
        },
    }


def make_cases(db, sources, source_dir):
    cases = [
        shared_case(db, sources, "michael-landfall", "Michael at Florida landfall", "AL142018",
                    "2018-10-10T17:30:00Z", "nhc_michael_report", "Table 1, 10/1730",
                    "Reviewing an exact, off-synoptic landfall record", (140, 919)),
        shared_case(db, sources, "ian-peak", "Ian at peak intensity", "AL092022",
                    "2022-09-28T12:00:00Z", "nhc_ian_report", "Table 1, 28/1200",
                    "Reviewing a historical storm peak", (140, 937)),
        shared_case(db, sources, "fiona-landfall", "Fiona at Nova Scotia landfall", "AL072022",
                    "2022-09-24T07:00:00Z", "nhc_fiona_report", "Table 1, 24/0700",
                    "Reviewing a Canadian landfall while keeping center and station pressures distinct", (85, 931)),
    ]

    milton = "AL142024"
    at = "2024-10-07T15:00:00Z"
    ib = fetch_ibtracs(db, milton, at)
    anchors = [fetch_native(db, milton, t) for t in ("2024-10-07T12:00:00Z", "2024-10-07T18:00:00Z")]
    assert fetch_native(db, milton, at) is None
    assert ib["iflag"][0] == "P" and ib["wmo_wind"] is ib["wmo_pressure"] is None
    assert (ib["usa_wind"], ib["usa_pressure"]) == (135, 926)
    assert [anchor["wind"] for anchor in anchors] == [120, 150]
    assert [anchor["pressure"] for anchor in anchors] == [943, 908]
    cases.append({
        "case_id": "milton-interpolated",
        "claim": "The IBTrACS 15:00 UTC value for Milton is an original best-track row or a direct measurement at that time.",
        "review_use": "Detect a generated time step before using a trace as observational evidence",
        "records": [ibtracs_record(sources, ib, "usa", "interpolated_best_track",
                                   [best_track_id(milton, row["stamp"]) for row in anchors], [HURDAT])],
        "context_records": [native_record(sources, row) for row in anchors],
        "reference": {
            "disposition": "interpolated_no_original_at_target",
            "accept_as_independent_corroboration": False,
            "distinct_best_track_origins_at_target": 0,
            "independent_physical_measurement_count": None,
            "accepted_numeric_values": None,
            "evidence": [{"source_key": "ibtracs_columns", "locator": "IFLAG P"},
                         {"source_key": "ibtracs_tech", "locator": "§6.7"}],
            "basis": "The exact timestamp is absent from HURDAT2. The neighboring winds and pressures give linear midpoint values of 135 kt and 925.5 hPa, consistent with the integer CSV output of 926 hPa. WMO fields are blank at the target under the no-interpolation policy.",
        },
    })

    ginger = "AL141971"
    at = "1971-09-13T12:00:00Z"
    native = fetch_native(db, ginger, at)
    ib = fetch_ibtracs(db, ginger, at)
    assert native["pressure"] is None and ib["wmo_pressure"] is None
    assert ib["iflag"][0] == "I" and ib["usa_pressure"] == 963
    origin = best_track_id(ginger, at)
    cases.append({
        "case_id": "ginger-pressure-fill",
        "claim": "The 963 hPa value for Ginger at 12:00 UTC was present in the original best-track row.",
        "review_use": "Keep field-level gaps and fills explicit even when the original timestamp exists",
        "records": [native_record(sources, native, "missing_pressure", pressure_only=True),
                    ibtracs_record(sources, ib, "wmo", "missing_pressure", [origin], [HURDAT], True),
                    ibtracs_record(sources, ib, "usa", "interpolated_pressure", [], [HURDAT], True)],
        "reference": {
            "disposition": "native_value_missing_derived_fill_available",
            "accept_as_independent_corroboration": False,
            "distinct_best_track_origins_at_target_with_pressure": 0,
            "independent_physical_measurement_count": None,
            "accepted_numeric_values": {"pressure_hpa": None},
            "evidence": [{"source_key": "ibtracs_columns", "locator": "IFLAG I"},
                         {"source_key": "ibtracs_tech", "locator": "§6.7"}],
            "basis": "NHC uses -999 for missing pressure, WMO preserves the gap, and USA_PRES is filled. The exact underlying record IDs used for this fill were left unresolved.",
        },
    })

    dawn = "AL131972"
    at = "1972-09-08T00:00:00Z"
    current = fetch_native(db, dawn, at)
    previous = fetch_native(db, dawn, at, "hurdat_previous")
    ib = fetch_ibtracs(db, dawn, at)
    assert (previous["wind"], current["wind"], ib["usa_wind"], ib["wmo_wind"]) == (70, 55, 55, 55)
    assert (previous["status"], current["status"]) == ("HU", "TS")
    assert ib["usa_agency"] == ib["wmo_agency"] == "hurdat_atl" and ib["iflag"][0] in {"O", "V"}
    origin = best_track_id(dawn, at)
    cases.append({
        "case_id": "dawn-release-revision",
        "claim": "The 70 and 55 kt best-track values for Dawn represent independent hurricane intensity estimates.",
        "review_use": "Resolve an archived intensity conflict by identifying an official revision of the same track",
        "records": [native_record(sources, previous, "superseded_best_track"), native_record(sources, current)] + [
            ibtracs_record(sources, ib, group, "redistributed_best_track", [origin], [HURDAT])
            for group in ("usa", "wmo")
        ],
        "reference": {
            "disposition": "same_origin_official_revision",
            "accept_as_independent_corroboration": False,
            "distinct_best_track_origins": 1,
            "independent_physical_measurement_count": None,
            "accepted_numeric_values": {"wind_kt": 55, "pressure_hpa": 998},
            "evidence": [{"uri": DOCS["noaa_reanalysis"], "locator": "September 2026, Dawn downgrade"}],
            "basis": "The identical ATCF key has 70 kt and HU in the February NHC release, then 55 kt and TS in the September NHC release. Both IBTrACS fields use the updated values. NOAA reports a formal reanalysis, so this is a revision of one logical best-track record.",
        },
    })

    alt = db.execute("""
        SELECT h.atcf, h.stamp FROM hurdat h
        JOIN ibtracs i ON i.atcf=h.atcf AND i.stamp=h.stamp
        WHERE h.release='hurdat_current' AND i.track_type='main' AND i.usa_agency='hurdat_atl'
          AND i.wmo_agency='atcf' AND h.wind=i.usa_wind AND h.wind=i.wmo_wind AND h.wind>=34
        ORDER BY h.stamp, h.atcf LIMIT 1
    """).fetchone()
    native = fetch_native(db, alt["atcf"], alt["stamp"])
    ib = fetch_ibtracs(db, alt["atcf"], alt["stamp"])
    origin = best_track_id(alt["atcf"], alt["stamp"])
    cases.append({
        "case_id": "atcf-origin-unresolved",
        "claim": "Matching wind values labeled HURDAT_ATL and ATCF establish independent physical evidence.",
        "review_use": "Require underlying provenance when an aggregator exposes different source labels",
        "records": [native_record(sources, native),
                    ibtracs_record(sources, ib, "usa", "redistributed_best_track", [origin], [HURDAT]),
                    ibtracs_record(sources, ib, "wmo", "upstream_overlap_unresolved", [], ["ibtracs-source.atcf"])],
        "reference": {
            "disposition": "different_labels_physical_lineage_unresolved",
            "accept_as_independent_corroboration": None,
            "distinct_best_track_origins": None,
            "independent_physical_measurement_count": None,
            "evidence": [{"source_key": "nhc_format", "locator": "p.1, HURDAT2 is based on ATCF best-track b-decks"},
                         {"source_key": "ibtracs_columns", "locator": "USA_AGENCY"}],
            "basis": "Source labels are distinct and the normalized winds agree. The HURDAT2 format document describes its relationship to ATCF best tracks. The exact lineage from the ATCF-labeled value to any shared or distinct physical observations is unresolved.",
        },
    })

    with (source_dir / "smart_44488").open(newline="") as f:
        rows = csv.DictReader(f)
        buoy = next(row for row in rows if row["time"] == "2022-09-24T07:40:00Z")
    hart = json.loads((source_dir / "eccc_hart_sample").read_text())
    h = hart["properties"]
    assert buoy["station_name"] == "44488" and buoy["avg_stn_pres_pst10mts"] == "931.2"
    assert h["CLIMATE_IDENTIFIER"] == "8202318" and h["UTC_DATE"] == "2022-09-24T07:00:00"
    assert h["STATION_PRESSURE"] == 93.16
    buoy_id = "eccc:wmo-44488:2022-09-24T07:40:00Z:station-pressure"
    hart_id = "eccc:wmo-71419:2022-09-24T07:00:00Z:station-pressure"
    cases.append({
        "case_id": "fiona-local-pressure-instruments",
        "claim": "Two physical instruments recorded local pressure near Fiona's Nova Scotia landfall.",
        "review_use": "Preserve evidence from separate instruments while enforcing time, place and pressure datum",
        "records": [
            record(sources, "smart_44488", buoy_id, {"line_1_based": 7, "timestamp_utc": buoy["time"],
                   "field": "avg_stn_pres_pst10mts", "wmo_station_id": "44488"},
                   {"station_pressure_hpa": float(buoy["avg_stn_pres_pst10mts"])},
                   [buoy_id], ["eccc.msc.observations.buoy.44488"], "station_observation",
                   physical_observation_ids=[buoy_id], latitude_deg=45.44, longitude_deg=-60.95,
                   averaging_minutes=10, qa_summary=buoy["avg_stn_pres_pst10mts_qa_summary"]),
            record(sources, "eccc_hart_sample", hart_id, {"feature_id": hart["id"], "timestamp_utc": h["UTC_DATE"]+"Z",
                   "field": "STATION_PRESSURE", "wmo_station_id": "71419"},
                   {"station_pressure_hpa": round(h["STATION_PRESSURE"] * 10, 2)},
                   [hart_id], ["eccc.msc.observations.station.8202318"], "station_observation",
                   physical_observation_ids=[hart_id], latitude_deg=hart["geometry"]["coordinates"][1],
                   longitude_deg=hart["geometry"]["coordinates"][0], source_pressure_kpa=h["STATION_PRESSURE"]),
        ],
        "reference": {
            "disposition": "distinct_local_physical_observations",
            "accept_as_independent_corroboration": True,
            "distinct_physical_observation_origins": 2,
            "presented_observations_at_exact_center_pressure_target": 0,
            "independent_physical_measurement_count_for_exact_center_pressure_at_landfall": None,
            "accepted_numeric_values": {"buoy_44488_station_pressure_hpa": 931.2, "hart_71419_station_pressure_hpa": 931.6},
            "evidence": [{"source_key": "nhc_fiona_report", "locator": "p.6 Canada observations and Table 3 sea-level pressure"},
                         {"uri": DOCS["buoy_metadata"], "locator": "WMO station 44488 identity"},
                         {"uri": DOCS["hart_metadata"], "locator": "Climate ID 8202318, WMO ID 71419"}],
            "basis": "Distinct ECCC platforms sampled different places and times. NOAA reports 931.2 hPa at the buoy and 932.7 hPa sea-level pressure at Hart Island. ECCC supplies 93.16 kPa station pressure at Hart Island, a different pressure datum. The readings support a regional low-pressure event. Cyclone-center pressure at landfall is a separate target from either station reading.",
        },
    })
    return cases


def freeze_rows(cases, source_dir):
    records_by_source = {}
    for case in cases:
        for source_record in case["records"] + case.get("context_records", []):
            key = source_record["source_key"]
            records_by_source.setdefault(key, []).append(source_record)
    frozen = {}
    for key, records in records_by_source.items():
        file_path = source_dir / key
        lines = {r["source_locator"].get("line_1_based") for r in records}
        selected = {}
        headers = {}
        current_header = None
        with file_path.open("rb") as raw:
            for n, row in enumerate(raw, 1):
                if key in HURDAT_SOURCES and row.startswith(b"AL"):
                    current_header = (n, row)
                if key in {"ibtracs_na", "smart_44488"} and n <= 2:
                    selected[n] = row
                if n in lines:
                    selected[n] = row
                    if current_header:
                        header_number, header = current_header
                        headers[n] = header_number
                        selected[header_number] = header
        if None in lines:
            selected[None] = file_path.read_bytes()
        for line, excerpt in selected.items():
            frozen[f"{key}:{line or 'complete-feature'}"] = {
                "source_key": key, "line_1_based": line, "sha256": sha256(excerpt),
                "utf8_bytes": excerpt.decode("utf-8"),
            }
        for source_record in records:
            line = source_record["source_locator"].get("line_1_based")
            source_record["frozen_source_row_id"] = f"{key}:{line or 'complete-feature'}"
            if line in headers:
                source_record["frozen_storm_header_id"] = f"{key}:{headers[line]}"
    return frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory of source bytes and fetch.json manifest")
    parser.add_argument("output", type=Path, help="Write the versioned compact case data to this JSON file")
    args = parser.parse_args()
    started = datetime.now(timezone.utc)
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    sources = verify_sources(args.source_dir)
    verified_at = time.perf_counter()
    db = get_database(args.source_dir)
    db_ready_at = time.perf_counter()
    scopes = {"all_1851_2025": ("1851", "2026"), "modern_1980_2025": ("1980", "2026"),
              "reanalysis_1971_1975": ("1971", "1976")}
    cohorts = {
        name: dict(db.execute(COHORT_SQL, {"start": start, "stop": stop}).fetchone())
        for name, (start, stop) in scopes.items()
    }
    queries_done_at = time.perf_counter()
    case_data = make_cases(db, sources, args.source_dir)
    frozen_rows = freeze_rows(case_data, args.source_dir)
    rows_loaded = {key: db.execute("SELECT count(*) FROM hurdat WHERE release=?", (key,)).fetchone()[0]
                   for key in HURDAT_SOURCES}
    rows_loaded["ibtracs_na"] = db.execute("SELECT count(*) FROM ibtracs").fetchone()[0]
    db.close()
    measurements = {
        "started_at_utc": started.isoformat(timespec="seconds"),
        "source_hash_verification_wall_seconds": round(verified_at - wall_start, 4),
        "parse_and_sqlite_load_wall_seconds": round(db_ready_at - verified_at, 4),
        "three_cohort_queries_wall_seconds": round(queries_done_at - db_ready_at, 4),
        "case_and_cohort_pipeline_wall_seconds": round(time.perf_counter() - wall_start, 4),
        "case_and_cohort_pipeline_cpu_seconds": round(time.process_time() - cpu_start, 4),
        "peak_rss_kib_linux": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python_version": sys.version.split()[0],
        "sqlite_version": sqlite3.sqlite_version,
        "downloaded_source_bytes": sum(source["bytes"] for source in sources.values()),
        "billing": "Public HTTP downloads and local CPU. The measured run used freely accessible datasets. Manual source review time remains unmeasured.",
    }
    fixture = {
        "schema_version": "hurricane-lineage-cases.v1",
        "title": "Hurricane best-track provenance for scientific intake review",
        "review_context": "Public evidence stress test for MONTREAL.AI scientific intake. Catalog agreement, release changes, and actual sensor support can lead to different review decisions. Adoption and market demand remain unmeasured.",
        "sources": sources,
        "source_notes": DOCS,
        "normalization": {
            "wind_kt": "Knots, 1-minute sustained wind for the North Atlantic HURDAT2 cases",
            "pressure_hpa": "Cyclone-center pressure. hPa and mb are numerically equal; -999 and blank are missing.",
            "station_pressure_hpa": "Station pressure at the platform, with 1 kPa = 10 hPa",
            "origin_record_ids": "Logical best-track or physical observation IDs. A logical best-track ID can persist across a release revision.",
            "unknown": "Null count means the physical evidence is unresolved. An empty ID list means no exact origin record was established.",
        },
        "control": {
            "method": "SQLite exact join of NHC storm ATCF ID plus UTC time to main IBTrACS rows. Domain-native USA_AGENCY, WMO_AGENCY and first IFLAG classify original and filled values. NHC reports and source releases anchor individual review dispositions.",
            "reproduction": "Run hurricane-lineage-control.py with a directory holding source-key-named input files and fetch.json, followed by the output path. The included exact source rows support review of the eight cases. A cohort rerun requires the full checksum-matching CSV snapshot. The live IBTrACS endpoint can change within version v04r01.",
            "reference_sql": COHORT_SQL.strip(),
            "rows_loaded": rows_loaded,
            "cohorts": cohorts,
            "measurements": measurements,
        },
        "frozen_source_rows": frozen_rows,
        "review_cases": case_data,
    }
    staged_output = args.output.with_suffix(args.output.suffix + ".tmp")
    staged_output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n")
    staged_output.replace(args.output)


if __name__ == "__main__":
    main()
