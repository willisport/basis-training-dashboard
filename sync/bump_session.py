"""
Wird von .github/workflows/logout-login.yml aufgerufen, wenn der Owner in
der App bei einem Nutzer auf "Abmelden" klickt. Erhoeht sessionVersion in
data/auth-config.json um 1 - dadurch verwirft die App beim naechsten Laden
die gespeicherte Sitzung dieses Nutzers und verlangt eine erneute Anmeldung.
Das Passwort selbst bleibt gueltig, der Nutzer kann sich sofort wieder
einloggen.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
AUTH_CONFIG_PATH = ROOT / "data" / "auth-config.json"


def main():
    username = os.environ.get("LOGOUT_USERNAME", "").strip().lower()
    if not username:
        print("LOGOUT_USERNAME fehlt.")
        sys.exit(1)

    with open(AUTH_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    entry = config.get("users", {}).get(username)
    if not entry:
        print(f"Nutzer '{username}' existiert nicht (nichts zu tun).")
        return

    entry["sessionVersion"] = entry.get("sessionVersion", 0) + 1
    with open(AUTH_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Sitzung von '{username}' invalidiert (sessionVersion={entry['sessionVersion']}).")


if __name__ == "__main__":
    main()
