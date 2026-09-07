"""
Traegt Garmin- und Renpho-Zugangsdaten interaktiv in sync/.env ein.
Passwoerter werden beim Tippen nicht angezeigt (wie bei einem normalen Login).

Aufruf:
    python set_credentials.py
"""

import os
from getpass import getpass

from dotenv import set_key

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
if not os.path.exists(ENV_PATH):
    open(ENV_PATH, "w").close()


def ask(label, current, secret=False):
    hint = " (leer lassen = unveraendert)" if current else ""
    prompt = f"{label}{hint}: "
    value = getpass(prompt) if secret else input(prompt)
    return value.strip() if value.strip() else current


def read_current(key):
    if not os.path.exists(ENV_PATH):
        return ""
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""


def main():
    print("Garmin:")
    garmin_email = ask("  E-Mail", read_current("GARMIN_EMAIL"))
    garmin_password = ask("  Passwort", read_current("GARMIN_PASSWORD"), secret=True)

    print("\nRenpho:")
    renpho_email = ask("  E-Mail", read_current("RENPHO_EMAIL"))
    renpho_password = ask("  Passwort", read_current("RENPHO_PASSWORD"), secret=True)

    set_key(ENV_PATH, "GARMIN_EMAIL", garmin_email)
    set_key(ENV_PATH, "GARMIN_PASSWORD", garmin_password)
    set_key(ENV_PATH, "RENPHO_EMAIL", renpho_email)
    set_key(ENV_PATH, "RENPHO_PASSWORD", renpho_password)

    print(f"\nGespeichert in {ENV_PATH}")
    print("Jetzt testen mit: python sync.py")


if __name__ == "__main__":
    main()
