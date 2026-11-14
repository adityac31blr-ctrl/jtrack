#!/usr/bin/env python3
"""Publish a validated snapshot only when the QA decision is pass."""

import argparse
import json
from pathlib import Path

from validate_jobs import schema_errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validated", default="staging/validated_jobs.json")
    parser.add_argument("--qa-report", default="reports/qa_report.json")
    parser.add_argument("--destination", default="data/jobs.json")
    args = parser.parse_args()
    qa = json.loads(Path(args.qa_report).read_text(encoding="utf-8"))
    if qa.get("decision") != "pass":
        print(f"publication refused: QA decision is {qa.get('decision')}")
        return 2
    snapshot = json.loads(Path(args.validated).read_text(encoding="utf-8"))
    errors = schema_errors(snapshot)
    if errors:
        print(f"publication refused: schema errors: {errors[:10]}")
        return 3
    destination = Path(args.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    temp.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temp.replace(destination)
    print(f"published {len(snapshot['jobs'])} jobs to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
