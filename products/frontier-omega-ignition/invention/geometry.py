"""Geometric planning on known public sky positions, with no telescope connection."""
import hashlib
import json
import math
import re
from datetime import datetime, timedelta


def digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def utc(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("UTC timestamp with explicit Z required")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def julian(moment):
    return moment.timestamp() / 86400 + 2440587.5


def check_number(value, low, high, name, integer=False):
    if (type(value) not in ((int,) if integer else (int, float)) or not math.isfinite(value)
            or not low <= value <= high):
        raise ValueError(f"{name} outside the supported range")


def validate(mission, catalog):
    try:
        if mission["scope"] != "public-catalog desk rehearsal" or not mission["id"]:
            raise ValueError("desk rehearsal scope required")
        latitude, longitude = mission["site"]["latitude_deg"], mission["site"]["longitude_deg"]
        check_number(latitude, -90, 90, "latitude")
        check_number(longitude, -180, 180, "longitude")
        check_number(mission["duration_minutes"], 1, 1440, "whole-minute duration", True)
        check_number(mission["visits_per_target"], 1, 2, "visits per target", True)
        check_number(mission["guard_deg"], 0.2, 10, "angular clearance")
        check_number(mission["min_target_alt_deg"], 0, 90, "target altitude")
        check_number(mission["max_sun_alt_deg"], -90, 0, "solar altitude")
        check_number(mission["min_revisit_hours"], 0, 8760, "revisit hours")
        starts = [utc(s) for s in mission["slots_utc"]]
        check_number(mission["max_slots"], 0, len(starts), "slot budget", True)
        cutoff = utc(mission["cutoff_utc"])
        if cutoff != utc(catalog["cutoff_utc"]):
            raise ValueError("source observation cutoff differs from mission")
        end = timedelta(minutes=mission["duration_minutes"])
        if starts != sorted(starts) or any(a + end > b for a, b in zip(starts, starts[1:])):
            raise ValueError("offer windows must be ordered and disjoint")
        if any(s < cutoff or not 1900 <= s.year <= 2100 for s in starts):
            raise ValueError("window precedes decision or exceeds ephemeris scope")
        seen = set()
        beginning = utc(catalog["selection_start_utc"])
        if beginning >= cutoff:
            raise ValueError("empty selection interval")
        for obj in catalog["targets"]:
            name = obj["id"]
            if not isinstance(name, str) or not re.fullmatch(r"ZTF\d{2}[a-z]{7}", name) or name in seen:
                raise ValueError("duplicate or invalid source ID")
            seen.add(name)
            check_number(obj["ra_deg"], 0.0, 360.0, "right ascension")
            if obj["ra_deg"] == 360.0:
                raise ValueError("right ascension must be below 360")
            check_number(obj["dec_deg"], -90.0, 90.0, "declination")
            if not julian(beginning) <= obj["alert_jd"] < julian(cutoff):
                raise ValueError("alert is stale or after the decision")
        return starts
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError("incomplete or invalid mission/catalog") from exc


def geometry_scope(mission, catalog):
    return digest({
        "site": mission["site"], "starts": mission["slots_utc"],
        "duration": mission["duration_minutes"],
        "targets": [[o["id"], o["ra_deg"], o["dec_deg"]] for o in catalog["targets"]]
    })


def precess(ra_deg, dec_deg, t):
    """J2000 to mean equator of date, IAU 1976 precession (t in Julian centuries)."""
    rad = math.radians
    zeta = rad((2306.2181*t + 0.30188*t*t + 0.017998*t**3) / 3600)
    z = rad((2306.2181*t + 1.09468*t*t + 0.018203*t**3) / 3600)
    theta = rad((2004.3109*t - 0.42665*t*t - 0.041833*t**3) / 3600)
    a, d = rad(ra_deg) + zeta, rad(dec_deg)
    x = math.cos(theta)*math.cos(d)*math.cos(a) - math.sin(theta)*math.sin(d)
    y = math.cos(d)*math.sin(a)
    h = math.sin(theta)*math.cos(d)*math.cos(a) + math.cos(theta)*math.sin(d)
    return math.atan2(y, x) + z, math.atan2(h, math.hypot(x, y))


def altitudes(moment, site, target):
    rad, deg = math.radians, math.degrees
    days = julian(moment) - 2451545.0
    t = days / 36525
    sidereal = rad((280.46061837 + 360.98564736629 * days + 0.000387933*t*t
                   - t**3/38710000 + site["longitude_deg"]) % 360)
    latitude = rad(site["latitude_deg"])
    anomaly = rad((357.529 + 0.98560028 * days) % 360)
    longitude = rad((280.459 + 0.98564736*days + 1.915*math.sin(anomaly)
                     + 0.020*math.sin(2*anomaly)) % 360)
    tilt = rad(23.439 - 0.00000036*days)
    sun_ra = math.atan2(math.cos(tilt)*math.sin(longitude), math.cos(longitude))
    sun_dec = math.asin(math.sin(tilt)*math.sin(longitude))
    ra, dec = precess(target["ra_deg"], target["dec_deg"], t)

    def altitude(a, d):
        sine = math.sin(latitude)*math.sin(d) + math.cos(latitude)*math.cos(d)*math.cos(sidereal - a)
        return deg(math.asin(max(-1.0, min(1.0, sine))))
    return altitude(ra, dec), altitude(sun_ra, sun_dec)


def extrema(mission, start, target):
    moments = (start + timedelta(minutes=i) for i in range(mission["duration_minutes"] + 1))
    angles = [altitudes(moment, mission["site"], target) for moment in moments]
    return min(a[0] for a in angles), max(a[1] for a in angles)


def admissible(mission, low, high):
    return (low >= mission["min_target_alt_deg"] + mission["guard_deg"]
            and high <= mission["max_sun_alt_deg"] - mission["guard_deg"])
