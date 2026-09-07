"""Ordnet synchronisierte Garmin-Aktivitaeten den geplanten Einheiten eines Tages zu."""


def activities_on_date(activities: list, date_str: str) -> list:
    return [a for a in activities if (a.get("startTime") or "").startswith(date_str)]


def unit_matches_activity(unit: dict, activity: dict) -> bool:
    if activity.get("type") != unit.get("type"):
        return False
    min_km = (unit.get("matchHint") or {}).get("minDistanceKm")
    if min_km and (activity.get("distanceKm") or 0) < min_km:
        return False
    return True
