"""Record advisory results for pinned locks. Never applies dependency fixes."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

from tasks import ROOT, python


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "scripts/ops/evidence/dependency-audit"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {
        "scanner": "pip-audit==2.9.0 / npm audit",
        "time": datetime.now(timezone.utc).isoformat(),
        "scope": "locked packages; no application exploitability determination",
        "checks": {},
    }
    for service in ("backend", "capture", "recognition", "ops"):
        lock = ROOT / f"scripts/ops/locks/{service}.txt"
        output = args.output / f"{service}.json"
        output.unlink(missing_ok=True)
        result = subprocess.run(
            [
                python("ops"),
                "-m",
                "pip_audit",
                "--no-deps",
                "--disable-pip",
                "--progress-spinner",
                "off",
                "-r",
                str(lock),
                "--format",
                "json",
                "-o",
                str(output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        record = {
            "exit_code": result.returncode,
            "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        }
        if output.is_file():
            data = json.loads(output.read_text())
            record["vulnerabilities"] = sum(
                len(item.get("vulns", [])) for item in data.get("dependencies", [])
            )
            record["unassessed"] = [
                item["name"]
                for item in data.get("dependencies", [])
                if item.get("skip_reason")
            ]
        else:
            record["status"] = "scanner_failed"
        summary["checks"][service] = record
    # PyPI advisory lookup cannot find the official local-version +cpu wheels.
    # Assess their exact upstream versions as well; keep the raw coverage gap.
    recognition_lock = (ROOT / "scripts/ops/locks/recognition.txt").read_text()
    upstream = re.findall(r"^(torch|torchvision)==([^\s\\;]+)", recognition_lock, re.M)
    if len(upstream) != 2:
        raise SystemExit(
            "Expected two pinned Torch packages for upstream advisory assessment"
        )
    requirements = args.output / "recognition-upstream.txt"
    requirements.write_text(
        "\n".join(f"{name}=={version.split('+')[0]}" for name, version in upstream)
        + "\n"
    )
    output = args.output / "recognition-upstream.json"
    output.unlink(missing_ok=True)
    result = subprocess.run(
        [
            python("ops"),
            "-m",
            "pip_audit",
            "--no-deps",
            "--disable-pip",
            "--progress-spinner",
            "off",
            "-r",
            str(requirements),
            "--format",
            "json",
            "-o",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    dependencies = (
        json.loads(output.read_text()).get("dependencies", [])
        if output.is_file()
        else []
    )
    assessed = {item["name"] for item in dependencies if not item.get("skip_reason")}
    summary["checks"]["recognition-upstream"] = {
        "exit_code": result.returncode if len(assessed) == 2 else 2,
        "requirements_sha256": hashlib.sha256(requirements.read_bytes()).hexdigest(),
        "vulnerabilities": sum(len(item.get("vulns", [])) for item in dependencies),
        "scope": "Official CPU wheel upstream package versions; binary/OS scan remains separate",
    }
    recognition = summary["checks"]["recognition"]
    recognition["platform_index_unassessed"] = recognition.get("unassessed", [])
    recognition["unassessed"] = [
        name for name in recognition.get("unassessed", []) if name not in assessed
    ]
    npm = subprocess.run(
        ["npm", "audit", "--json"],
        cwd=ROOT / "frontend",
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(npm.stdout)
    except json.JSONDecodeError:
        report = {"error": "npm audit returned no JSON"}
    (args.output / "frontend.json").write_text(json.dumps(report, indent=2))
    summary["checks"]["frontend"] = {
        "exit_code": npm.returncode,
        "lock_sha256": hashlib.sha256(
            (ROOT / "frontend/package-lock.json").read_bytes()
        ).hexdigest(),
        "counts": report.get("metadata", {}).get("vulnerabilities", {}),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    raise SystemExit(
        int(
            any(
                check["exit_code"] or check.get("unassessed")
                for check in summary["checks"].values()
            )
        )
    )


if __name__ == "__main__":
    main()
