"""Reject automatic deployment, floating actions, excessive global permissions."""

from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]


def check():
    failures = []
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        data = yaml.safe_load(path.read_text())
        events = data.get("on", data.get(True, {}))  # PyYAML's YAML 1.1 boolean key.
        if data.get("permissions") not in ({"contents": "read"}, {}):
            failures.append(f"{path.name}: global permissions must be read-only")
        for name, job in data.get("jobs", {}).items():
            if job.get("environment"):
                if set(events) != {"workflow_dispatch"}:
                    failures.append(
                        f"{path.name}/{name}: deployments must be manual only"
                    )
            for step in job.get("steps", []):
                action = step.get("uses", "")
                if (
                    action
                    and not action.startswith("./")
                    and not re.fullmatch(r"[^@]+@[a-f0-9]{40}", action)
                ):
                    failures.append(f"{path.name}/{name}: unpinned action")
                if "PAGES_ADMIN_TOKEN" in str(step):
                    failures.append(
                        f"{path.name}/{name}: Pages administration token forbidden"
                    )
        if "pull_request_target" in events:
            failures.append(f"{path.name}: privileged PR trigger forbidden")
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        "PASS: workflow actions pinned; environment promotions manual; no Pages admin token"
    )


if __name__ == "__main__":
    check()
