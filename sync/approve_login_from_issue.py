"""
Wird von .github/workflows/approve-login.yml aufgerufen, wenn der Owner auf
GitHub ein "login-request"-Issue mit dem Label "genehmigt" versieht. Liest
Benutzername + Credential aus dem Issue-Text (Umgebungsvariable ISSUE_BODY)
und schaltet den Nutzer frei - gleiche Logik wie approve_login.py, nur ohne
manuelle Eingabe.
"""

import json
import os
import re
import sys
from pathlib import Path

import crypto_utils as cu

ROOT = Path(__file__).parent.parent
AUTH_CONFIG_PATH = ROOT / "data" / "auth-config.json"


def main():
    body = os.environ.get("ISSUE_BODY", "")
    user_match = re.search(r"Benutzername:\s*(\S+)", body, re.IGNORECASE)
    cred_match = re.search(r"Credential[^:]*:\s*([0-9a-f]{64})", body, re.IGNORECASE)

    if not user_match or not cred_match:
        print("Konnte Benutzername/Credential nicht aus dem Issue-Text lesen.")
        sys.exit(1)

    username = user_match.group(1).strip().lower()
    credential_secret = cred_match.group(1).strip().lower()

    if not re.fullmatch(r"[a-z0-9_-]{2,24}", username):
        print(f"Ungueltiger Benutzername: {username}")
        sys.exit(1)

    dek_b64 = os.environ.get("DATA_ENCRYPTION_KEY")
    if not dek_b64:
        print("DATA_ENCRYPTION_KEY fehlt.")
        sys.exit(1)
    dek = cu.unb64(dek_b64)

    with open(AUTH_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    config.setdefault("users", {})
    config["users"][username] = {**cu.wrap_key(dek, credential_secret), "role": "viewer"}

    with open(AUTH_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Nutzer '{username}' automatisch freigeschaltet.")


if __name__ == "__main__":
    main()
