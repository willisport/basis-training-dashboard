"""
Einmaliges Hilfsskript: legt einen benannten Owner-Login (Benutzername +
Passwort) in data/auth-config.json an, zusaetzlich zum bestehenden
passwortlosen Owner-Slot. Nutzt denselben Mechanismus wie approve_login.py,
nur mit role="owner" statt "viewer".
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


def sha256_hex(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    username = sys.argv[1].strip().lower()
    password = sys.argv[2]

    if not re.fullmatch(r"[a-z0-9_-]{2,24}", username):
        print("Ungueltiger Benutzername.")
        sys.exit(1)

    dek_b64 = os.environ.get("DATA_ENCRYPTION_KEY")
    if not dek_b64:
        print("DATA_ENCRYPTION_KEY fehlt in sync/.env")
        sys.exit(1)
    dek = cu.unb64(dek_b64)

    credential_secret = sha256_hex(f"{username}:{password}")

    with open(AUTH_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    config.setdefault("users", {})
    config["users"][username] = {**cu.wrap_key(dek, credential_secret), "role": "owner"}

    with open(AUTH_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Owner-Login '{username}' angelegt.")


if __name__ == "__main__":
    main()
