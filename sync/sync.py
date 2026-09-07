"""
Baut data/training-data.json aus Garmin + Strava + Renpho + data/plan-template.json.

Aufruf:
    python sync.py

Gedacht zum wiederholten Ausfuehren (z. B. per Windows-Aufgabenplanung alle
15-30 Minuten). Einzelne Quellen duerfen fehlschlagen, ohne den ganzen Lauf
abzubrechen - dann werden die zuletzt bekannten Werte fuer diesen Abschnitt
beibehalten.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(Path(__file__).parent / ".env")

import garmin_source
import renpho_source
import crypto_utils
from plan_match import activities_on_date, unit_matches_activity
from common import weekday_de, monday_of, iso_date, fmt_short, month_name_de

PLAN_PATH = ROOT / "data" / "plan-template.json"
OUTPUT_PATH = ROOT / "data" / "training-data.json"
ENCRYPTED_OUTPUT_PATH = ROOT / "data" / "training-data.enc.json"

WINDOW_WEEKS = 9  # 8 Wochen Performance-Verlauf + aktuelle Woche


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def week_type_and_label(plan: dict, monday: datetime):
    rotation = plan["rotation"]
    cycle_start = datetime.strptime(rotation["cycleStartMonday"], "%Y-%m-%d")
    pattern = rotation["pattern"]
    weeks_since = (monday - cycle_start).days // 7
    idx = weeks_since % len(pattern)
    week_type = pattern[idx]
    if week_type == "aufbau":
        aufbau_count = pattern.count("aufbau")
        label = f"Woche {idx + 1} von {aufbau_count} · Aufbau"
    else:
        label = "Recovery-Woche"
    return week_type, label


def parse_pace_to_sec(pace_str: str) -> float:
    m, s = pace_str.split(":")
    return int(m) * 60 + int(s)


def estimate_week_hours(plan: dict, week_type: str):
    """Grobe Stunden-Schaetzung je Sportart aus den km-Zielen (fuer das
    Wochenplan-Balkendiagramm) - Kraft/EMOM/Core-Zeit ist im Wochenmuster
    ohnehin fix, unabhaengig vom Aufbau/Recovery-Typ."""
    targets = plan["targetsByType"][week_type]
    profile = plan["profile"]
    zone2_avg_sec = (parse_pace_to_sec(profile["zone2PaceFastMinKm"]) + parse_pace_to_sec(profile["zone2PaceSlowMinKm"])) / 2
    run_hours = targets["runVolumeKm"] * zone2_avg_sec / 3600
    bike_avg_kmh = (profile["bikeAvgSpeedLowKmh"] + profile["bikeAvgSpeedHighKmh"]) / 2
    bike_hours = targets["bikeVolumeKm"] / bike_avg_kmh if bike_avg_kmh > 0 else 0
    strength_min = sum(
        u.get("plannedDurationMin", 0)
        for day in plan["weekPattern"]
        for u in day["units"]
        if u["type"] in ("kraft", "emom", "core")
    )
    return round(run_hours, 1), round(bike_hours, 1), round(strength_min / 60, 1)


def build_upcoming_plan(plan: dict, this_monday: datetime, weeks_ahead: int = 6) -> list:
    out = []
    for i in range(weeks_ahead):
        wk_monday = this_monday + timedelta(weeks=i)
        week_type, _ = week_type_and_label(plan, wk_monday)
        run_h, bike_h, strength_h = estimate_week_hours(plan, week_type)
        out.append({
            "label": fmt_short(iso_date(wk_monday)),
            "weekType": week_type,
            "isCurrent": i == 0,
            "runHours": run_h,
            "bikeHours": bike_h,
            "strengthHours": strength_h,
        })
    return out


def build_day(plan_day: dict, date: datetime, activities: list, today: datetime, steps_by_date: dict) -> dict:
    date_str = iso_date(date)
    day_acts = activities_on_date(activities, date_str)
    units = []
    for pu in plan_day["units"]:
        matched = next((a for a in day_acts if unit_matches_activity(pu, a)), None)
        if matched:
            status = "done"
        elif date.date() < today.date():
            status = "skipped"
        else:
            status = "planned"
        units.append({
            "name": pu["name"], "type": pu["type"], "tag": pu["tag"],
            "status": status, "detail": pu.get("detail", ""),
            **({"keySession": True} if pu.get("keySession") else {}),
            **({"plannedDurationMin": pu["plannedDurationMin"]} if pu.get("plannedDurationMin") else {}),
            **({"planLabel": pu["planLabel"]} if pu.get("planLabel") else {}),
            **({"exercises": pu["exercises"]} if pu.get("exercises") else {}),
        })
    out = {"date": date_str, "weekday": plan_day["weekday"], "focus": plan_day["focus"], "units": units}
    if plan_day.get("fallbackNote"):
        out["fallbackNote"] = plan_day["fallbackNote"]
    day_steps = steps_by_date.get(date_str)
    if day_steps:
        out["steps"] = day_steps.get("steps")
        out["stepGoal"] = day_steps.get("stepGoal")
    return out


def hr_weighted_share(acts: list, low: float, high: float) -> float:
    total, in_zone = 0.0, 0.0
    for a in acts:
        if a["type"] not in ("lauf", "rad") or not a.get("avgHr"):
            continue
        dur = a.get("durationMin") or 0
        total += dur
        if low <= a["avgHr"] <= high:
            in_zone += dur
    return round((in_zone / total) * 100, 0) if total > 0 else 0


def hr_hard_share(acts: list, high: float) -> float:
    total, hard = 0.0, 0.0
    for a in acts:
        if a["type"] not in ("lauf", "rad") or not a.get("avgHr"):
            continue
        dur = a.get("durationMin") or 0
        total += dur
        if a["avgHr"] > high + 5:
            hard += dur
    return round((hard / total) * 100, 0) if total > 0 else 0


def weight_on_or_before(weights: list, date_str: str, fallback=None):
    candidates = [w for w in weights if w["date"] <= date_str]
    return candidates[-1]["weightKg"] if candidates else fallback


def value_on_or_before(series: list, date_str: str, fallback=None):
    """series: [{date, value}] - liefert den letzten Wert an/vor date_str."""
    candidates = [e for e in series if e["date"] <= date_str]
    return candidates[-1]["value"] if candidates else fallback


def weight_avg_in_week(weights: list, monday_str: str, sunday_str: str, fallback=None):
    vals = [w["weightKg"] for w in weights if monday_str <= w["date"] <= sunday_str]
    return round(sum(vals) / len(vals), 1) if vals else fallback


def main():
    print(f"[{datetime.now().isoformat(timespec='seconds')}] Sync startet...")
    plan = load_json(PLAN_PATH)
    previous = load_json(OUTPUT_PATH) if OUTPUT_PATH.exists() else {}

    today = datetime.now()
    this_monday = monday_of(today)
    window_start = this_monday - timedelta(weeks=WINDOW_WEEKS - 1)

    # --- Garmin (einzige Aktivitaetsquelle + Gesundheitsdaten) ---
    try:
        api = garmin_source.get_client()
        activities = garmin_source.fetch_activities(api, window_start, today)
        sleep_today = garmin_source.fetch_daily_metrics(api, today)
        hrv_baseline = garmin_source.fetch_hrv_baseline(api, today)
        vo2max_history = garmin_source.fetch_vo2max_history(api, today, days=WINDOW_WEEKS * 7 + 60)
        vo2max = vo2max_history[-1]["value"] if vo2max_history else None
        weekly_steps = garmin_source.fetch_weekly_steps(api, this_monday, this_monday + timedelta(days=6))
        print(f"  Garmin: {len(activities)} Aktivitaeten geladen")
    except Exception as e:
        print(f"[FEHLER] Garmin-Sync fehlgeschlagen, breche ab: {e}")
        sys.exit(1)

    # --- Renpho (Gewicht) ---
    try:
        weights = renpho_source.fetch_weight_history()
        print(f"  Renpho: {len(weights)} Gewichtsmessungen geladen")
    except Exception as e:
        print(f"  [warn] Renpho-Sync uebersprungen: {e}")
        weights = []
        prev_weight = (previous.get("today") or {}).get("body", {}).get("weightKg")
        if prev_weight:
            weights = [{"date": iso_date(today), "weightKg": prev_weight}]

    # --- Woche bauen ---
    week_type, week_label = week_type_and_label(plan, this_monday)
    targets = plan["targetsByType"][week_type]
    upcoming_plan = build_upcoming_plan(plan, this_monday)

    week_days = [
        build_day(plan["weekPattern"][i], this_monday + timedelta(days=i), activities, today, weekly_steps)
        for i in range(7)
    ]
    week_start_str, week_end_str = iso_date(this_monday), iso_date(this_monday + timedelta(days=6))
    week_acts = [a for a in activities if week_start_str <= (a["startTime"] or "")[:10] <= week_end_str]

    run_volume_km = round(sum(a["distanceKm"] for a in week_acts if a["type"] == "lauf"), 1)
    bike_volume_km = round(sum(a["distanceKm"] for a in week_acts if a["type"] == "rad"), 1)
    volume_km = round(run_volume_km + bike_volume_km, 1)
    time_min = round(sum(a["durationMin"] for a in week_acts), 0)

    prev_weeks_acts = [
        a for a in activities
        if iso_date(this_monday - timedelta(weeks=4)) <= (a["startTime"] or "")[:10] < week_start_str
    ]
    prev_time_min = sum(a["durationMin"] for a in prev_weeks_acts)
    prev_avg_time_min = prev_time_min / 4 if prev_weeks_acts else 0
    load_vs_avg = round(((time_min - prev_avg_time_min) / prev_avg_time_min) * 100) if prev_avg_time_min > 0 else (
        -100 if time_min == 0 else 0
    )

    week = {
        "label": week_label, "type": week_type,
        "startDate": week_start_str, "endDate": week_end_str,
        "targets": targets,
        "actuals": {
            "runVolumeKm": run_volume_km, "bikeVolumeKm": bike_volume_km, "timeMin": time_min,
            "zone2SharePct": hr_weighted_share(week_acts, plan["profile"]["zone2HrLow"], plan["profile"]["zone2HrHigh"]),
            "hardSharePct": hr_hard_share(week_acts, plan["profile"]["zone2HrHigh"]),
            "loadVsAvgPct": load_vs_avg,
        },
        "days": week_days,
        "selfCoaching": plan["selfCoaching"],
    }

    # --- Heute ---
    today_idx = today.weekday()
    today_plan_units = week_days[today_idx]["units"]
    today_obj = {
        "date": iso_date(today), "weekday": weekday_de(today),
        "dayFocus": plan["weekPattern"][today_idx]["focus"],
        "units": today_plan_units,
        "sleep": {**sleep_today, "hrvBaseline": hrv_baseline},
        "body": {
            "weightKg": weight_on_or_before(weights, iso_date(today), fallback=(previous.get("today") or {}).get("body", {}).get("weightKg")),
            "vo2max": vo2max,
        },
        "steps": week_days[today_idx].get("steps"),
        "stepGoal": week_days[today_idx].get("stepGoal"),
    }

    # --- Verlauf: Wochen-/Monatsvergleich + Log ---
    last_monday = this_monday - timedelta(weeks=1)
    last_week_acts = [
        a for a in activities
        if iso_date(last_monday) <= (a["startTime"] or "")[:10] <= iso_date(last_monday + timedelta(days=6))
    ]
    this_month_str = today.strftime("%Y-%m")
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    this_month_acts = [a for a in activities if (a["startTime"] or "").startswith(this_month_str)]
    last_month_acts = [
        a for a in activities
        if iso_date(last_month_start) <= (a["startTime"] or "")[:10] <= iso_date(last_month_end)
    ]

    history = {
        "weekCompare": {
            "thisWeek": {"label": f"{fmt_short(week_start_str)}–{fmt_short(week_end_str)}",
                         "distanceKm": volume_km, "sessions": len(week_acts)},
            "lastWeek": {"label": f"{fmt_short(iso_date(last_monday))}–{fmt_short(iso_date(last_monday + timedelta(days=6)))}",
                         "distanceKm": round(sum(a["distanceKm"] for a in last_week_acts if a["type"] in ("lauf", "rad")), 1),
                         "sessions": len(last_week_acts)},
        },
        "monthCompare": {
            "thisMonth": {"label": month_name_de(today), "distanceKm": round(sum(a["distanceKm"] for a in this_month_acts if a["type"] in ("lauf", "rad")), 1), "sessions": len(this_month_acts)},
            "lastMonth": {"label": month_name_de(last_month_end), "distanceKm": round(sum(a["distanceKm"] for a in last_month_acts if a["type"] in ("lauf", "rad")), 1), "sessions": len(last_month_acts)},
        },
        "log": [
            {
                "date": (a["startTime"] or "")[:10], "weekday": weekday_de(datetime.strptime((a["startTime"] or iso_date(today))[:10], "%Y-%m-%d")),
                "name": a["name"], "type": a["type"],
                "distanceKm": a["distanceKm"], "durationMin": round(a["durationMin"]),
                "note": f"Ø {round(a['avgHr'])} bpm" if a.get("avgHr") else "",
            }
            for a in activities[:20]
        ],
    }

    # --- Performance: letzte 8 Wochen + Session-Verlaeufe ---
    perf_weeks = []
    for w in range(WINDOW_WEEKS - 1, -1, -1):
        wk_monday = this_monday - timedelta(weeks=w)
        wk_sunday = wk_monday + timedelta(days=6)
        wk_acts = [a for a in activities if iso_date(wk_monday) <= (a["startTime"] or "")[:10] <= iso_date(wk_sunday)]
        z2_runs = [a for a in wk_acts if a["type"] == "lauf" and a.get("paceSecPerKm") and a.get("avgHr")
                   and plan["profile"]["zone2HrLow"] - 5 <= a["avgHr"] <= plan["profile"]["zone2HrHigh"] + 5]
        pace = round(sum(a["paceSecPerKm"] for a in z2_runs) / len(z2_runs)) if z2_runs else None
        perf_weeks.append({
            "label": fmt_short(iso_date(wk_monday)),
            "vo2max": value_on_or_before(vo2max_history, iso_date(wk_sunday)),
            "zone2PaceSecPerKm": pace,
            "runVolumeKm": round(sum(a["distanceKm"] for a in wk_acts if a["type"] == "lauf"), 1),
            "bikeVolumeKm": round(sum(a["distanceKm"] for a in wk_acts if a["type"] == "rad"), 1),
            "weightKg": weight_avg_in_week(weights, iso_date(wk_monday), iso_date(wk_sunday)),
        })
    # Luecken bei vo2max/weightKg mit letztem bekannten Wert auffuellen
    last_v, last_w = None, None
    for pw in perf_weeks:
        if pw["vo2max"] is None:
            pw["vo2max"] = last_v
        else:
            last_v = pw["vo2max"]
        if pw["weightKg"] is None:
            pw["weightKg"] = last_w
        else:
            last_w = pw["weightKg"]

    run_pace_points = [
        {"date": (a["startTime"] or "")[:10], "paceSecPerKm": round(a["paceSecPerKm"])}
        for a in sorted(activities, key=lambda a: a["startTime"] or "")
        if a["type"] == "lauf" and a.get("paceSecPerKm")
        and (not a.get("avgHr") or a["avgHr"] <= plan["profile"]["zone2HrHigh"] + 8)
        and (a["startTime"] or "")[:10] >= iso_date(window_start)
    ]
    bike_speed_points = [
        {"date": (a["startTime"] or "")[:10], "avgSpeedKmh": a["avgSpeedKmh"]}
        for a in sorted(activities, key=lambda a: a["startTime"] or "")
        if a["type"] == "rad" and a.get("avgSpeedKmh") and (a["startTime"] or "")[:10] >= iso_date(window_start)
    ]

    performance = {"weeks": perf_weeks, "runPace": run_pace_points, "bikeSpeed": bike_speed_points}

    output = {
        "syncedAt": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "profile": {**plan["profile"], "vo2max": today_obj["body"]["vo2max"]},
        "today": today_obj,
        "week": week,
        "history": history,
        "performance": performance,
        "upcomingPlan": upcoming_plan,
    }

    save_json(OUTPUT_PATH, output)
    print(f"[{datetime.now().isoformat(timespec='seconds')}] Fertig -> {OUTPUT_PATH}")

    dek_b64 = os.environ.get("DATA_ENCRYPTION_KEY")
    if dek_b64:
        dek = crypto_utils.unb64(dek_b64)
        plaintext_bytes = json.dumps(output, ensure_ascii=False).encode("utf-8")
        encrypted = crypto_utils.encrypt_json_bytes(dek, plaintext_bytes)
        save_json(ENCRYPTED_OUTPUT_PATH, encrypted)
        print(f"  Verschluesselte Fassung -> {ENCRYPTED_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
