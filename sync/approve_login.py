"""
Schaltet einen ueber den "Login erstellen"-Dialog angefragten Benutzer frei.

Die angefragte Person hat ihr Passwort NIE im Klartext irgendwohin geschickt -
im Browser wurde nur sha256("<benutzername>:<passwort>") berechnet und als
oeffentlich unbedenkliches "Credential" in einem GitHub-Issue (Label
"login-request") hinterlegt. Dieses Skript nimmt Benutzername + Credential aus
dem Issue, verpackt den vorhandenen Daten-Schluessel (DATA_ENCRYPTION_KEY aus
sync/.env) damit und traegt den neuen Eintrag in data/auth-config.json ein.

Aufruf (Werte aus dem Logins-Tab bzw. dem GitHub-Issue kopieren):
    python approve_login.py <benutzername> <credential-hex>

Danach committen & pushen:
    git add data/auth-config.json
    git commit -m "Login fuer <benutzername> freigeschaltet"
    git push
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

import crypto_utils as cu

ROOT = Path(__file__).parent.parent
load_dotenv(Path(__file__).parent / ".env")
AUTH_CONFIG_PATH = ROOT / "data" / "auth-config.json"


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    username = sys.argv[1].strip().lower()
    credential_secret = sys.argv[2].strip().lower()

    if not re.fullmatch(r"[a-z0-9_-]{2,24}", username):
        print("Ungueltiger Benutzername (2-24 Zeichen, a-z/0-9/-/_).")
        sys.exit(1)
    if not re.fullmatch(r"[0-9a-f]{64}", credential_secret):
        print("Credential sieht nicht wie ein SHA-256-Hex-Wert aus (64 Hex-Zeichen erwartet).")
        sys.exit(1)

    dek_b64 = os.environ.get("DATA_ENCRYPTION_KEY")
    if not dek_b64:
        print("DATA_ENCRYPTION_KEY fehlt in sync/.env - erst setup_encryption.py ausfuehren.")
        sys.exit(1)
    dek = cu.unb64(dek_b64)

    with open(AUTH_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    config.setdefault("users", {})
    if username in config["users"]:
        print(f"Hinweis: '{username}' existierte schon und wird ueberschrieben (neues Passwort).")

    config["users"][username] = {**cu.wrap_key(dek, credential_secret), "role": "viewer"}

    with open(AUTH_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\nNutzer '{username}' freigeschaltet (Rolle: viewer).")
    print(f"Jetzt committen & pushen:")
    print(f"  git add data/auth-config.json")
    print(f"  git commit -m \"Login fuer {username} freigeschaltet\"")
    print(f"  git push")


if __name__ == "__main__":
    main()
