"""
Wird von .github/workflows/revoke-login.yml aufgerufen, wenn der Owner in
der App bei einem freigeschalteten Login auf "Entfernen" klickt. Entfernt
den Benutzernamen einfach aus data/auth-config.json - kein Zugriff auf den
Daten-Schluessel noetig, da nur der Eintrag geloescht wird.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
AUTH_CONFIG_PATH = ROOT / "data" / "auth-config.json"


def main():
    username = os.environ.get("REVOKE_USERNAME", "").strip().lower()
    if not username:
        print("REVOKE_USERNAME fehlt.")
        sys.exit(1)

    with open(AUTH_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    if username in config.get("users", {}):
        del config["users"][username]
        with open(AUTH_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"Nutzer '{username}' entfernt.")
    else:
        print(f"Nutzer '{username}' existierte nicht (nichts zu tun).")


if __name__ == "__main__":
    main()
