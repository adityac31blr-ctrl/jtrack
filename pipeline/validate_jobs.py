#!/usr/bin/env python3
"""Deterministically validate research jobs and make a release decision."""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

FUNCTION_RULES = [
    ("Marketing", ("marketing", "brand", "seo", "content", "campaign", "communications")),
    ("Sales & BD", ("sales", "business development", "account executive", "partnership")),
    ("Finance", ("finance", "financial", "accounting", "treasury", "investment")),
    ("HR", ("human resources", "people operations", "talent", "recruit")),
    ("Operations", ("operations", "supply chain", "procurement", "program manager")),
    ("Consulting", ("consultant", "consulting", "strategy")),
    ("Product", ("product manager", "product marketing", "product operations")),
    ("Analytics", ("analyst", "analytics", "business intelligence", "research")),
]
FUNCTIONS = {name for name, _ in FUNCTION_RULES} | {"Other"}
WORK_MODES = {"remote", "hybrid", "onsite", "unknown"}
EXPERIENCE = {"intern", "entry", "mid", "senior", "unknown"}
EMPLOYMENT = {"full_time", "part_time", "contract", "internship", "other", "unknown"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: Any, milliseconds: bool = False) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            seconds = value / 1000 if milliseconds or value > 10_000_000_000 else value
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def iso(value: datetime | None) -> str | None:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z") if value else None


def plain_text(value: Any, limit: int = 280) -> str:
    text = str(value or "")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def valid_https(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def flatten(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(flatten(item) for item in value)
    if isinstance(value, dict):
        return " ".join(flatten(item) for item in value.values())
    return str(value or "")


def india_eligibility(candidate: dict[str, Any]) -> tuple[bool | None, str]:
    location = flatten(candidate.get("location_raw")).lower()
    restrictions = flatten(candidate.get("location_restrictions")).lower()
    timezones = flatten(candidate.get("timezone_restrictions")).lower()
    combined = f"{location} {restrictions}"
    explicit_india = bool(re.search(r"\b(india|bharat)\b", combined)) or location.strip() == "in"
    worldwide = not restrictions.strip() or any(term in restrictions for term in ("worldwide", "anywhere", "global"))
    timezone_ok = not timezones.strip() or any(term in timezones for term in ("india", "kolkata", "ist", "+05:30", "+0530", "asia"))
    excluded = any(term in combined for term in ("united states only", "us only", "europe only", "canada only", "uk only"))
    if explicit_india and not excluded:
        return True, "IN"
    if candidate.get("source_key") == "himalayas" and worldwide and timezone_ok and not excluded:
        return True, "IN"
    if excluded or (restrictions.strip() and not explicit_india):
        return False, "IN"
    return None, "IN"


def classify(text: str) -> str:
    lowered = text.lower()
    for name, keywords in FUNCTION_RULES:
        if any(keyword in lowered for keyword in keywords):
            return name
    return "Other"


def experience(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("intern", "trainee")):
        return "intern"
    if any(term in lowered for term in ("entry", "associate", "graduate", "junior", "fresher")):
        return "entry"
    if any(term in lowered for term in ("senior", "director", "head of", "lead", "vice president", "vp ")):
        return "senior"
    if any(term in lowered for term in ("manager", "specialist", "consultant")):
        return "mid"
    return "unknown"


def work_mode(text: str) -> str:
    lowered = text.lower()
    if "hybrid" in lowered:
        return "hybrid"
    if "remote" in lowered or "anywhere" in lowered:
        return "remote"
    if lowered.strip():
        return "onsite"
    return "unknown"


def employment(value: Any, title: str) -> str:
    lowered = f"{flatten(value)} {title}".lower().replace("-", " ")
    if "intern" in lowered:
        return "internship"
    if "part time" in lowered:
        return "part_time"
    if any(term in lowered for term in ("contract", "temporary", "freelance")):
        return "contract"
    if any(term in lowered for term in ("full time", "permanent")):
        return "full_time"
    return "unknown"


def salary(value: Any) -> dict[str, Any]:
    result = {"min": None, "max": None, "currency": None, "period": None}
    if not isinstance(value, dict):
        return result
    aliases = {"min": ("min", "minimum", "minSalary"), "max": ("max", "maximum", "maxSalary"), "currency": ("currency",), "period": ("period", "interval")}
    for target, keys in aliases.items():
        for key in keys:
            if value.get(key) is not None:
                result[target] = value[key]
                break
    if result["currency"] is not None:
        currency = str(result["currency"]).upper()
        result["currency"] = currency if re.fullmatch(r"[A-Z]{3}", currency) else None
    periods = {"year": "annual", "yearly": "annual", "annual": "annual", "month": "monthly", "monthly": "monthly", "week": "weekly", "weekly": "weekly", "hour": "hourly", "hourly": "hourly", "fortnightly": "fortnightly"}
    result["period"] = periods.get(str(result["period"]).lower()) if result["period"] else None
    for key in ("min", "max"):
        if not isinstance(result[key], (int, float)) or isinstance(result[key], bool):
            result[key] = None
    return result


def score(job: dict[str, Any]) -> int:
    title = job["title"].lower()
    value = 0
    if any(term in title for term in ("marketing", "brand", "growth", "seo", "content")):
        value += 30
    if job["function"] == "Marketing":
        value += 25
    if job["experience_level"] in {"entry", "intern"}:
        value += 15
    if job["india_eligible"] is True:
        value += 15
    posted = parse_time(job["posted_at"])
    if posted and posted >= datetime.now(timezone.utc) - timedelta(days=30):
        value += 10
    if job["source_key"].startswith(("greenhouse:", "lever:")):
        value += 5
    return min(value, 100)


def validate_candidate(candidate: dict[str, Any], generated_at: datetime) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    required = ("source_key", "source_job_id", "source_name", "title", "company", "application_url_raw", "source_url_raw", "fetched_at")
    for field in required:
        if candidate.get(field) in (None, ""):
            reasons.append(f"missing_{field}")
    for field in ("application_url_raw", "source_url_raw"):
        if candidate.get(field) and not valid_https(candidate[field]):
            reasons.append(f"invalid_{field}")
    if candidate.get("source_key") == "himalayas":
        payload = candidate.get("provider_payload") or {}
        if payload.get("applicationLink") != candidate.get("application_url_raw"):
            reasons.append("himalayas_application_link_modified")
    expires = parse_time(candidate.get("expires_raw"))
    if expires and expires < generated_at:
        reasons.append("expired")
    india, country = india_eligibility(candidate)
    if india is not True:
        reasons.append("india_eligibility_unknown" if india is None else "not_india_eligible")
    if reasons:
        return None, sorted(set(reasons))

    title = plain_text(candidate["title"], 160)
    company = plain_text(candidate["company"], 120)
    summary = plain_text(candidate.get("description_raw"), 280)
    location = plain_text(candidate.get("location_raw"), 160) or "Remote - India eligible"
    semantics = candidate.get("published_semantics")
    posted = parse_time(candidate.get("published_raw"), milliseconds=candidate.get("source_key", "").startswith("lever:")) if semantics == "provider_created_at" else None
    text = f"{title} {summary}"
    job = {
        "id": f"{candidate['source_key']}:{candidate['source_job_id']}",
        "source_key": str(candidate["source_key"]),
        "source_job_id": str(candidate["source_job_id"]),
        "source_name": plain_text(candidate["source_name"], 100),
        "title": title,
        "company": company,
        "function": classify(text),
        "marketing_priority_score": 0,
        "location_text": location,
        "country": country,
        "india_eligible": india,
        "work_mode": work_mode(location),
        "experience_level": experience(text),
        "employment_type": employment(candidate.get("employment_type_raw"), title),
        "salary": salary(candidate.get("salary_raw")),
        "posted_at": iso(posted),
        "expires_at": iso(expires),
        "summary": summary,
        "skills": [classify(text)] if classify(text) != "Other" else [],
        "application_url": candidate["application_url_raw"],
        "source_url": candidate["source_url_raw"],
        "last_checked_at": iso(parse_time(candidate["fetched_at"])),
        "availability_status": "source_listed",
    }
    job["marketing_priority_score"] = score(job)
    return job, []


def schema_errors(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if snapshot.get("schema_version") != "1.0":
        errors.append("schema_version")
    if parse_time(snapshot.get("generated_at")) is None:
        errors.append("generated_at")
    scope = snapshot.get("scope")
    if not isinstance(scope, dict) or scope.get("default_country") != "IN" or not isinstance(scope.get("include_india_eligible_remote"), bool) or not isinstance(scope.get("marketing_priority"), bool):
        errors.append("scope")
    sources = snapshot.get("sources")
    if not isinstance(sources, list):
        errors.append("sources")
        sources = []
    source_keys: set[str] = set()
    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(prefix)
            continue
        for field in ("key", "name", "status", "attribution_url"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                errors.append(f"{prefix}.{field}")
        if source.get("key") in source_keys:
            errors.append(f"{prefix}.duplicate_key")
        source_keys.add(source.get("key"))
        if source.get("status") not in {"ok", "partial", "failed"}:
            errors.append(f"{prefix}.status")
        if source.get("fetched_at") is not None and parse_time(source.get("fetched_at")) is None:
            errors.append(f"{prefix}.fetched_at")
        for field in ("records_received", "records_published"):
            if not isinstance(source.get(field), int) or isinstance(source.get(field), bool) or source[field] < 0:
                errors.append(f"{prefix}.{field}")
        if not valid_https(source.get("attribution_url")):
            errors.append(f"{prefix}.attribution_url")
    stats = snapshot.get("stats")
    if not isinstance(stats, dict):
        errors.append("stats")
        stats = {}
    jobs = snapshot.get("jobs")
    if not isinstance(jobs, list):
        errors.append("jobs")
        jobs = []
    expected_stats = {
        "total": len(jobs),
        "marketing": sum(isinstance(job, dict) and job.get("function") == "Marketing" for job in jobs),
        "sources_ok": sum(source.get("status") == "ok" for source in sources if isinstance(source, dict)),
    }
    for field in ("total", "marketing", "new_last_7_days", "sources_ok"):
        if not isinstance(stats.get(field), int) or isinstance(stats.get(field), bool) or stats[field] < 0:
            errors.append(f"stats.{field}")
    for field, expected in expected_stats.items():
        if stats.get(field) != expected:
            errors.append(f"stats.{field}_mismatch")
    ids: set[str] = set()
    for index, job in enumerate(jobs):
        prefix = f"jobs[{index}]"
        if not isinstance(job, dict):
            errors.append(prefix)
            continue
        required_strings = ("id", "source_key", "source_job_id", "source_name", "title", "company", "function", "location_text", "application_url", "source_url", "last_checked_at", "availability_status")
        for field in required_strings:
            if not isinstance(job.get(field), str) or not job[field].strip():
                errors.append(f"{prefix}.{field}")
        if job.get("id") in ids:
            errors.append(f"{prefix}.duplicate_id")
        ids.add(job.get("id"))
        if job.get("function") not in FUNCTIONS or job.get("work_mode") not in WORK_MODES or job.get("experience_level") not in EXPERIENCE or job.get("employment_type") not in EMPLOYMENT:
            errors.append(f"{prefix}.enum")
        if not isinstance(job.get("marketing_priority_score"), int) or not 0 <= job["marketing_priority_score"] <= 100:
            errors.append(f"{prefix}.marketing_priority_score")
        if job.get("india_eligible") not in (True, False, None):
            errors.append(f"{prefix}.india_eligible")
        if not valid_https(job.get("application_url")) or not valid_https(job.get("source_url")):
            errors.append(f"{prefix}.url")
        if job.get("availability_status") != "source_listed":
            errors.append(f"{prefix}.availability_status")
        for field in ("last_checked_at",):
            if parse_time(job.get(field)) is None:
                errors.append(f"{prefix}.{field}")
        for field in ("posted_at", "expires_at"):
            if job.get(field) is not None and parse_time(job.get(field)) is None:
                errors.append(f"{prefix}.{field}")
        if job.get("country") not in {"IN", None}:
            errors.append(f"{prefix}.country")
        pay = job.get("salary")
        if not isinstance(pay, dict) or set(pay) != {"min", "max", "currency", "period"}:
            errors.append(f"{prefix}.salary_shape")
            pay = {}
        for field in ("min", "max"):
            if pay.get(field) is not None and (not isinstance(pay[field], (int, float)) or isinstance(pay[field], bool)):
                errors.append(f"{prefix}.salary_{field}")
        if pay.get("currency") is not None and not re.fullmatch(r"[A-Z]{3}", str(pay["currency"])):
            errors.append(f"{prefix}.salary_currency")
        if pay.get("period") not in {None, "hourly", "weekly", "fortnightly", "monthly", "annual"}:
            errors.append(f"{prefix}.salary_period")
        if pay.get("min") is not None and pay.get("max") is not None and pay["min"] > pay["max"]:
            errors.append(f"{prefix}.salary_range")
    return errors


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temp.replace(path)


def validate(input_path: Path, output_path: Path, report_path: Path, rejected_path: Path, previous_path: Path | None) -> int:
    research = json.loads(input_path.read_text(encoding="utf-8"))
    generated = datetime.now(timezone.utc).replace(microsecond=0)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for candidate in research.get("jobs", []):
        key = (str(candidate.get("source_key")), str(candidate.get("source_job_id")))
        if key in seen:
            duplicates += 1
            rejected.append({"source_key": key[0], "source_job_id": key[1], "reasons": ["duplicate_source_id"]})
            continue
        seen.add(key)
        job, reasons = validate_candidate(candidate, generated)
        if job:
            accepted.append(job)
        else:
            rejected.append({"source_key": candidate.get("source_key"), "source_job_id": candidate.get("source_job_id"), "reasons": reasons})

    source_rows = []
    for source in research.get("sources", []):
        source_rows.append({
            "key": source["key"],
            "name": source["name"],
            "status": source["status"],
            "fetched_at": source.get("fetched_at"),
            "records_received": source.get("records_received", 0),
            "records_published": sum(1 for job in accepted if job["source_key"] == source["key"]),
            "attribution_url": source.get("attribution_url"),
        })
    accepted.sort(key=lambda job: (job["marketing_priority_score"], job.get("posted_at") or ""), reverse=True)
    snapshot = {
        "schema_version": "1.0",
        "generated_at": iso(generated),
        "scope": {"default_country": "IN", "include_india_eligible_remote": True, "marketing_priority": True},
        "sources": source_rows,
        "stats": {
            "total": len(accepted),
            "marketing": sum(job["function"] == "Marketing" for job in accepted),
            "new_last_7_days": sum(bool(parse_time(job["posted_at"])) and parse_time(job["posted_at"]) >= generated - timedelta(days=7) for job in accepted),
            "sources_ok": sum(source["status"] == "ok" for source in source_rows),
        },
        "jobs": accepted[:500],
    }
    errors = schema_errors(snapshot)
    successful_sources = [source for source in source_rows if source["status"] in {"ok", "partial"} and source.get("fetched_at")]
    failures = [source["key"] for source in source_rows if source["status"] != "ok"]
    warnings: list[str] = []
    blockers: list[str] = []
    if errors:
        blockers.append("malformed_schema")
    if not successful_sources:
        blockers.append("zero_verifiably_successful_sources")
    input_count = len(research.get("jobs", []))
    rejection_rate = len(rejected) / input_count if input_count else 0
    if rejection_rate > 0.15:
        warnings.append("rejection_rate_above_15_percent")
    if failures and successful_sources:
        warnings.append("partial_source_outage")
    previous_ids: set[str] = set()
    if previous_path and previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        previous_ids = {job["id"] for job in previous.get("jobs", [])}
        if previous_ids and len(accepted) < len(previous_ids) * 0.6:
            warnings.append("accepted_listing_drop_above_40_percent")
    current_ids = {job["id"] for job in accepted}
    decision = "block" if blockers else ("warn_requires_approval" if warnings else "pass")
    report = {
        "run_id": research.get("run_id"),
        "decision": decision,
        "input_records": input_count,
        "accepted_records": len(accepted),
        "rejected_records": len(rejected),
        "duplicate_records": duplicates,
        "warning_records": sum(bool(item["reasons"]) for item in rejected),
        "source_failures": failures,
        "blockers": blockers,
        "warnings": warnings,
        "schema_errors": errors,
        "changes_since_previous": {"added": len(current_ids - previous_ids), "removed": len(previous_ids - current_ids)},
        "validated_file": output_path.as_posix(),
    }
    write_json(output_path, snapshot)
    write_json(report_path, report)
    write_json(rejected_path, {"run_id": research.get("run_id"), "rejected": rejected})
    return 0 if decision == "pass" else (2 if decision == "warn_requires_approval" else 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--rejected", default="reports/rejected_jobs.json")
    parser.add_argument("--previous", default="data/jobs.json")
    args = parser.parse_args()
    return validate(Path(args.input), Path(args.out), Path(args.report), Path(args.rejected), Path(args.previous))


if __name__ == "__main__":
    raise SystemExit(main())
