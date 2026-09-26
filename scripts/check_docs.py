"""Check local Markdown links/images without remote requests or secret access."""

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    failures = []
    paths = list(ROOT.glob("*.md")) + [
        path
        for path in (ROOT / "docs").rglob("*.md")
        if "node_modules" not in path.parts and ".venv" not in path.parts
    ]
    for path in paths:
        text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = target.split(' "', 1)[0].strip("<>")
            if not target or target.startswith("#") or urlsplit(target).scheme:
                continue
            linked = (ROOT if target.startswith("/") else path.parent) / unquote(
                target.split("#")[0]
            ).lstrip("/")
            if not linked.exists():
                failures.append(f"{path.relative_to(ROOT)}: missing {target}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        f"PASS: local links/images in {len(paths)} Markdown files (external URLs not checked)"
    )


if __name__ == "__main__":
    main()
