"""Gemeinsame Helfer: Typ-Mapping, Zeit-/Pace-Utilities."""

from datetime import datetime, timedelta

# Garmin activityType.typeKey / Strava type|sport_type -> unser internes Schema
GARMIN_TYPE_MAP = {
    "running": "lauf",
    "track_running": "lauf",
    "trail_running": "lauf",
    "treadmill_running": "lauf",
    "cycling": "rad",
    "road_biking": "rad",
    "indoor_cycling": "rad",
    "virtual_ride": "rad",
    "mountain_biking": "rad",
    "gravel_cycling": "rad",
    "strength_training": "kraft",
    "cardio": "core",
    "core_training": "core",
    "yoga": "core",
}

STRAVA_TYPE_MAP = {
    "Run": "lauf",
    "TrailRun": "lauf",
    "VirtualRun": "lauf",
    "Ride": "rad",
    "VirtualRide": "rad",
    "GravelRide": "rad",
    "MountainBikeRide": "rad",
    "WeightTraining": "kraft",
    "Workout": "kraft",
    "Crossfit": "kraft",
    "Yoga": "core",
    "Elliptical": "core",
}

WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def month_name_de(d: datetime) -> str:
    return MONTHS_DE[d.month - 1]


def map_garmin_type(type_key: str) -> str:
    return GARMIN_TYPE_MAP.get((type_key or "").lower(), "sonstiges")


def map_strava_type(sport_type: str) -> str:
    return STRAVA_TYPE_MAP.get(sport_type, "sonstiges")


def iso_date(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def weekday_de(d: datetime) -> str:
    return WEEKDAYS_DE[d.weekday()]


def monday_of(d: datetime) -> datetime:
    return d - timedelta(days=d.weekday())


def sec_to_pace(sec_per_km: float) -> str:
    m = int(sec_per_km // 60)
    s = int(round(sec_per_km % 60))
    return f"{m}:{s:02d}"


def fmt_short(iso: str) -> str:
    d = datetime.strptime(iso, "%Y-%m-%d")
    return d.strftime("%d.%m.")
