"""Renpho-Waage: inoffizielle Cloud-API ueber das renpho-api Paket."""

import os
from datetime import datetime

from renpho import RenphoClient


def fetch_weight_history() -> list:
    """Liefert [{date, weightKg}] sortiert aufsteigend, ein Eintrag pro Tag
    (letzte Messung des Tages, meist die Morgen-Wiegung)."""
    email = os.environ.get("RENPHO_EMAIL")
    password = os.environ.get("RENPHO_PASSWORD")
    if not email or not password:
        raise RuntimeError("RENPHO_EMAIL/RENPHO_PASSWORD fehlen in sync/.env.")

    client = RenphoClient(email, password)
    client.login()

    raw = client.get_all_measurements() or []
    if not raw:
        # get_all_measurements() liefert bei manchen Konten nichts zurueck -
        # dann ueber die Geraeteliste direkt nachfragen (laut renpho-api README).
        device_info = client.get_device_info()
        scales = (device_info or {}).get("scale") or []
        for table in scales:
            table_name, user_id, count = table.get("tableName"), client.user_id, table.get("count")
            measurements = client.get_body_composition_measurements(table_name=table_name, user_id=user_id)
            if not measurements:
                measurements = client.get_measurements(table_name=table_name, user_id=user_id, total_count=count)
            raw.extend(measurements or [])

    by_day = {}
    for m in raw:
        weight = m.get("weight")
        local_created = m.get("localCreatedAt")  # z.B. "2026-08-31 21:26:44", schon in Lokalzeit
        if weight is None:
            continue
        if local_created:
            day = str(local_created)[:10]
        else:
            ts = m.get("timeStamp")
            if ts is None:
                continue
            day = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
        # letzte Messung des Tages gewinnt (Liste ist typischerweise neueste zuerst)
        if day not in by_day:
            by_day[day] = float(weight)

    return [{"date": d, "weightKg": round(w, 1)} for d, w in sorted(by_day.items())]
