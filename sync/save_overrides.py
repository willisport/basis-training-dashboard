"""
Wird von .github/workflows/save-overrides.yml aufgerufen, wenn im Browser
eine Einheit verschoben/abgehakt oder eine Tagesnotiz geschrieben wird.
Schreibt das vom Client bereits verschluesselte Payload (iv + ciphertext)
unveraendert nach data/overrides.enc.json - der Server sieht nie den
Klartext, nur der Browser mit dem passenden Passwort kann es entschluesseln.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_PATH = ROOT / "data" / "overrides.enc.json"


def main():
    payload_raw = os.environ.get("OVERRIDES_PAYLOAD", "")
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        print("Payload ist kein gueltiges JSON.")
        sys.exit(1)

    if "iv" not in payload or "ciphertext" not in payload:
        print("Payload braucht 'iv' und 'ciphertext'.")
        sys.exit(1)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("Overrides gespeichert.")


if __name__ == "__main__":
    main()
