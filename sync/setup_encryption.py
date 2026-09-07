"""
Einmalig ausfuehren, um Owner- und Viewer-Passwort fuer die verschluesselte
Online-Version (GitHub Pages) festzulegen.

Erzeugt:
  - data/auth-config.json          (unbedenklich oeffentlich - enthaelt nur
                                     passwortverpackte Schluessel, keine Klartext-
                                     Passwoerter)
  - DATA_ENCRYPTION_KEY in sync/.env (GEHEIM - fuer lokales Verschluesseln beim
                                     Testen; fuer den echten Online-Sync muss
                                     derselbe Wert zusaetzlich als GitHub Actions
                                     Secret hinterlegt werden, siehe Ausgabe)

Aufruf:
    python setup_encryption.py
"""

import json
import os
from getpass import getpass
from pathlib import Path

from dotenv import set_key

import crypto_utils as cu

ROOT = Path(__file__).parent.parent
ENV_PATH = Path(__file__).parent / ".env"
AUTH_CONFIG_PATH = ROOT / "data" / "auth-config.json"


def main():
    print("Legt die Login-Passwoerter fuer die verschluesselte Online-Version fest.")
    print("(Wird lokal verarbeitet, landet nirgendwo im Klartext.)\n")

    owner_pw = getpass("Owner-Passwort (voller Zugriff inkl. Abhaken/Notiz): ").strip()
    owner_pw2 = getpass("Owner-Passwort wiederholen: ").strip()
    if owner_pw != owner_pw2 or not owner_pw:
        print("Passwoerter stimmen nicht ueberein oder sind leer. Abgebrochen.")
        return

    viewer_pw = getpass("Viewer-Passwort (nur Ansicht, fuer Mitleser): ").strip()
    viewer_pw2 = getpass("Viewer-Passwort wiederholen: ").strip()
    if viewer_pw != viewer_pw2 or not viewer_pw:
        print("Passwoerter stimmen nicht ueberein oder sind leer. Abgebrochen.")
        return

    if owner_pw == viewer_pw:
        print("Owner- und Viewer-Passwort sollten unterschiedlich sein. Abgebrochen.")
        return

    dek = cu.generate_dek()
    config = {
        "kdf": {"iterations": cu.PBKDF2_ITERATIONS, "hash": "SHA-256"},
        "owner": cu.wrap_key(dek, owner_pw),
        "viewer": cu.wrap_key(dek, viewer_pw),
    }

    AUTH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUTH_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    dek_b64 = cu.b64(dek)
    if not ENV_PATH.exists():
        open(ENV_PATH, "w").close()
    set_key(str(ENV_PATH), "DATA_ENCRYPTION_KEY", dek_b64)

    print(f"\nGespeichert: {AUTH_CONFIG_PATH} (kann bedenkenlos oeffentlich/committed sein)")
    print(f"DATA_ENCRYPTION_KEY in {ENV_PATH} eingetragen (fuer lokale Tests).")
    print("\nFuer den echten automatischen Online-Sync per GitHub Actions:")
    print("  1. Repo-Einstellungen -> Settings -> Secrets and variables -> Actions")
    print("  2. Neues Secret 'DATA_ENCRYPTION_KEY' anlegen mit genau diesem Wert:")
    print(f"     {dek_b64}")
    print("  3. Ausserdem GARMIN_EMAIL, GARMIN_PASSWORD, RENPHO_EMAIL, RENPHO_PASSWORD")
    print("     als Secrets dort eintragen (gleiche Werte wie in sync/.env).")


if __name__ == "__main__":
    main()
