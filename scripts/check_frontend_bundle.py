"""Fail production artifacts containing known demo fixtures/reset routes/secrets."""

import argparse
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if not (args.directory / "index.html").is_file():
        raise SystemExit("No production build found")
    patterns = [
        rb"demo-data\.json",
        rb"/demo/reset",
        rb"/demo-reset",
        rb"minioadmin",
        rb"postgresql(?:\+psycopg2)?://",
        rb"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
    ]
    failures = []
    for path in args.directory.rglob("*"):
        if not path.is_file():
            continue
        if path.name == "demo-data.json" or "recognition-demo" in path.parts:
            failures.append(str(path))
        if path.suffix in {".js", ".json", ".html", ".map"}:
            content = path.read_bytes()
            if any(re.search(pattern, content) for pattern in patterns):
                failures.append(str(path))
    if failures:
        raise SystemExit(
            "Production artifact boundary failed: " + ", ".join(sorted(set(failures)))
        )
    print("PASS: production artifact fixture/reset/known-secret checks")


if __name__ == "__main__":
    main()
