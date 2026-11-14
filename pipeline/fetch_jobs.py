#!/usr/bin/env python3
"""Fetch permitted public job feeds and preserve provider provenance."""

from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id(value: str) -> str:
    return value.replace(":", "-")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temp.replace(path)


def request_json(url: str, config: dict[str, Any]) -> tuple[Any, int]:
    attempts = int(config["http"].get("max_attempts", 3))
    timeout = float(config["http"].get("timeout_seconds", 25))
    headers = {"User-Agent": config["http"]["user_agent"], "Accept": "application/json"}
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"unexpected HTTP {response.status}")
                return json.load(response), attempt
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < attempts:
                retry_after = exc.headers.get("Retry-After", "1")
                try:
                    delay = min(float(retry_after), 60.0)
                except ValueError:
                    delay = 1.0
                time.sleep(delay)
                continue
            if 500 <= exc.code < 600 and attempt < attempts:
                time.sleep((2 ** (attempt - 1)) + random.random() / 4)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == attempts:
                raise RuntimeError(str(exc)) from exc
            time.sleep((2 ** (attempt - 1)) + random.random() / 4)
    raise RuntimeError("request attempts exhausted")


def raw_ref(raw_dir: Path, source: str, suffix: str) -> Path:
    return raw_dir / f"{source}-{suffix}.json"


def first(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if value.get(key) not in (None, "", []):
            return value[key]
    return None


def map_himalayas(job: dict[str, Any], raw_path: Path, fetched_at: str) -> dict[str, Any]:
    source_id = first(job, "guid", "id")
    return {
        "source_key": "himalayas",
        "source_name": "Himalayas",
        "source_job_id": str(source_id) if source_id is not None else None,
        "raw_payload_ref": raw_path.as_posix(),
        "title": first(job, "title", "jobTitle"),
        "company": first(job, "companyName", "company"),
        "location_raw": first(job, "location", "locationRestrictions", "candidateRequiredLocation"),
        "location_restrictions": job.get("locationRestrictions"),
        "timezone_restrictions": job.get("timezoneRestrictions"),
        "description_raw": first(job, "description", "descriptionText", "excerpt"),
        "application_url_raw": first(job, "applicationLink"),
        "source_url_raw": first(job, "link", "url") or "https://himalayas.app",
        "published_raw": first(job, "pubDate"),
        "published_semantics": "provider_last_updated",
        "expires_raw": first(job, "expiryDate", "expiresAt"),
        "employment_type_raw": first(job, "employmentType"),
        "salary_raw": first(job, "salary", "compensation"),
        "provider_payload": job,
        "fetched_at": fetched_at,
    }


def map_greenhouse(job: dict[str, Any], board: dict[str, Any], raw_path: Path, fetched_at: str) -> dict[str, Any]:
    location = job.get("location") or {}
    return {
        "source_key": f"greenhouse:{board['token']}",
        "source_name": f"{board['employer']} careers",
        "source_job_id": str(job.get("id")) if job.get("id") is not None else None,
        "raw_payload_ref": raw_path.as_posix(),
        "title": job.get("title"),
        "company": board["employer"],
        "location_raw": location.get("name") if isinstance(location, dict) else location,
        "description_raw": job.get("content"),
        "application_url_raw": job.get("absolute_url"),
        "source_url_raw": job.get("absolute_url"),
        "published_raw": job.get("updated_at"),
        "published_semantics": "provider_last_updated",
        "expires_raw": None,
        "employment_type_raw": None,
        "salary_raw": None,
        "provider_payload": job,
        "fetched_at": fetched_at,
    }


def map_lever(job: dict[str, Any], site: dict[str, Any], raw_path: Path, fetched_at: str) -> dict[str, Any]:
    categories = job.get("categories") or {}
    return {
        "source_key": f"lever:{site['site']}",
        "source_name": f"{site['employer']} careers",
        "source_job_id": str(job.get("id")) if job.get("id") is not None else None,
        "raw_payload_ref": raw_path.as_posix(),
        "title": job.get("text"),
        "company": site["employer"],
        "location_raw": categories.get("location"),
        "description_raw": job.get("descriptionPlain") or job.get("description"),
        "application_url_raw": job.get("applyUrl") or job.get("hostedUrl"),
        "source_url_raw": job.get("hostedUrl") or job.get("applyUrl"),
        "published_raw": job.get("createdAt"),
        "published_semantics": "provider_created_at",
        "expires_raw": None,
        "employment_type_raw": categories.get("commitment"),
        "salary_raw": job.get("salaryRange"),
        "provider_payload": job,
        "fetched_at": fetched_at,
    }


def fetch(config: dict[str, Any], output: Path, raw_dir: Path, report_path: Path) -> int:
    started_at = utc_now()
    candidates: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    request_count = 0

    def add(items: list[dict[str, Any]]) -> None:
        for item in items:
            key = (str(item.get("source_key")), str(item.get("source_job_id")))
            if item.get("source_job_id") and key not in seen:
                seen.add(key)
                candidates.append(item)

    hcfg = config["sources"].get("himalayas", {})
    if hcfg.get("enabled"):
        entry = {"key": "himalayas", "name": "Himalayas", "status": "ok", "requests": 0, "records_received": 0, "errors": [], "fetched_at": None, "documentation_url": hcfg["documentation_url"], "attribution_url": hcfg["attribution_url"], "paging_truncated": False}
        for keyword in hcfg.get("keywords", []):
            for page in range(1, int(hcfg.get("max_pages_per_keyword", 1)) + 1):
                params = urllib.parse.urlencode({"q": keyword, "country": config["scope"]["country"], "sort": "recent", "page": page})
                url = f"{hcfg['endpoint']}?{params}"
                entry["requests"] += 1
                request_count += 1
                try:
                    payload, _ = request_json(url, config)
                    fetched_at = utc_now()
                    raw_path = raw_ref(raw_dir, "himalayas", f"{urllib.parse.quote(keyword, safe='').replace('%', '_')}-page-{page}")
                    write_json(raw_path, {"request_url": url, "fetched_at": fetched_at, "payload": payload})
                    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
                    if not isinstance(jobs, list):
                        raise RuntimeError("response.jobs is not an array")
                    entry["records_received"] += len(jobs)
                    entry["fetched_at"] = fetched_at
                    add([map_himalayas(job, raw_path, fetched_at) for job in jobs if isinstance(job, dict)])
                    if not jobs:
                        break
                    if page == int(hcfg.get("max_pages_per_keyword", 1)):
                        entry["paging_truncated"] = True
                except Exception as exc:  # Error is recorded per request for partial accounting.
                    entry["errors"].append({"keyword": keyword, "page": page, "error": str(exc)[:500]})
                    entry["status"] = "partial" if entry["fetched_at"] else "failed"
                    break
                time.sleep(float(hcfg.get("request_interval_seconds", 0)))
        sources.append(entry)

    gcfg = config["sources"].get("greenhouse", {})
    if gcfg.get("enabled"):
        for board in gcfg.get("boards", []):
            key = f"greenhouse:{board['token']}"
            entry = {"key": key, "name": f"{board['employer']} careers", "status": "failed", "requests": 1, "records_received": 0, "errors": [], "fetched_at": None, "documentation_url": gcfg["documentation_url"], "attribution_url": board["careers_url"]}
            request_count += 1
            try:
                url = gcfg["endpoint_template"].format(board_token=urllib.parse.quote(board["token"], safe=""))
                payload, _ = request_json(url, config)
                fetched_at = utc_now()
                raw_path = raw_ref(raw_dir, "greenhouse", board["token"])
                write_json(raw_path, {"request_url": url, "fetched_at": fetched_at, "payload": payload})
                jobs = payload.get("jobs", [])
                if not isinstance(jobs, list):
                    raise RuntimeError("response.jobs is not an array")
                entry.update(status="ok", records_received=len(jobs), fetched_at=fetched_at)
                add([map_greenhouse(job, board, raw_path, fetched_at) for job in jobs if isinstance(job, dict)])
            except Exception as exc:
                entry["errors"].append({"error": str(exc)[:500]})
            sources.append(entry)

    lcfg = config["sources"].get("lever", {})
    if lcfg.get("enabled"):
        for site in lcfg.get("sites", []):
            key = f"lever:{site['site']}"
            entry = {"key": key, "name": f"{site['employer']} careers", "status": "failed", "requests": 1, "records_received": 0, "errors": [], "fetched_at": None, "documentation_url": lcfg["documentation_url"], "attribution_url": site["careers_url"]}
            request_count += 1
            try:
                url = lcfg["endpoint_template"].format(site=urllib.parse.quote(site["site"], safe=""))
                payload, _ = request_json(url, config)
                fetched_at = utc_now()
                raw_path = raw_ref(raw_dir, "lever", site["site"])
                write_json(raw_path, {"request_url": url, "fetched_at": fetched_at, "payload": payload})
                if not isinstance(payload, list):
                    raise RuntimeError("response is not an array")
                entry.update(status="ok", records_received=len(payload), fetched_at=fetched_at)
                add([map_lever(job, site, raw_path, fetched_at) for job in payload if isinstance(job, dict)])
            except Exception as exc:
                entry["errors"].append({"error": str(exc)[:500]})
            sources.append(entry)

    research = {"run_id": run_id(started_at), "fetched_at": utc_now(), "sources": sources, "jobs": candidates}
    successful = [source for source in sources if source["status"] in {"ok", "partial"} and source["fetched_at"]]
    report = {
        "run_id": research["run_id"],
        "started_at": started_at,
        "completed_at": research["fetched_at"],
        "request_count": request_count,
        "candidate_records": len(candidates),
        "successful_sources": len(successful),
        "sources": sources,
        "paging_truncated": any(source.get("paging_truncated", False) for source in sources),
    }
    write_json(output, research)
    write_json(report_path, report)
    return 0 if successful else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="pipeline/sources.json")
    parser.add_argument("--out", default="staging/research_jobs.json")
    parser.add_argument("--raw-dir", default="staging/raw")
    parser.add_argument("--report", default="reports/research_report.json")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    return fetch(config, Path(args.out), Path(args.raw_dir), Path(args.report))


if __name__ == "__main__":
    raise SystemExit(main())
