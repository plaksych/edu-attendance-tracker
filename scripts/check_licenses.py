"""Reject unreviewed application-license obligations from Trivy's JSON inventory."""

import json
from pathlib import Path
import sys


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    licenses = [
        entry
        for result in data.get("Results", [])
        for entry in result.get("Licenses", [])
    ]
    if not licenses:
        raise SystemExit(
            "No license inventory returned; cannot claim license verification"
        )
    blocked = [
        entry
        for entry in licenses
        if "AGPL" in entry.get("Name", "").upper()
        or entry.get("Name", "").lower() in {"unknown", "unlicensed", "none"}
    ]
    if blocked:
        names = sorted({entry.get("PkgName", "unknown package") for entry in blocked})
        raise SystemExit(
            "Owner/legal review required; no blanket exception: " + ", ".join(names)
        )
    print(
        f"PASS: {len(licenses)} license records; not a substitute for media/model provenance review"
    )


if __name__ == "__main__":
    main()
