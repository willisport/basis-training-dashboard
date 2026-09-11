"""Ordnet synchronisierte Garmin-Aktivitaeten den geplanten Einheiten eines Tages zu."""


def activities_on_date(activities: list, date_str: str) -> list:
    return [a for a in activities if (a.get("startTime") or "").startswith(date_str)]


EMOM_MAX_DURATION_MIN = 10  # Garmin nennt jede Kraft-Aktivitaet nur "Krafttraining" -
# EMOM und die laengeren Kraft-Einheiten (Supersaetze/Stabi/schweres Bein) sind fuer
# Garmin nicht unterscheidbar, daher ueber die Dauer trennen: <=10 min war das EMOM,
# laenger war die andere Kraft-Einheit des Tages.


def unit_matches_activity(unit: dict, activity: dict) -> bool:
    unit_type = unit.get("type")
    duration = activity.get("durationMin") or 0

    if unit_type == "emom":
        return activity.get("type") == "kraft" and duration <= EMOM_MAX_DURATION_MIN
    if unit_type == "kraft":
        if activity.get("type") != "kraft" or duration <= EMOM_MAX_DURATION_MIN:
            return False
    elif activity.get("type") != unit_type:
        return False

    min_km = (unit.get("matchHint") or {}).get("minDistanceKm")
    if min_km and (activity.get("distanceKm") or 0) < min_km:
        return False
    return True
