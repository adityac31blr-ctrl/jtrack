#!/usr/bin/env python3
"""Deterministic UI contract checks that require only the Python standard library."""

from html.parser import HTMLParser
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MarkupParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])


html = (ROOT / "index.html").read_text(encoding="utf-8")
css = (ROOT / "styles.css").read_text(encoding="utf-8")
js = (ROOT / "app.js").read_text(encoding="utf-8")
fixture = json.loads((ROOT / "tests/fixtures/data/jobs.json").read_text(encoding="utf-8"))

parser = MarkupParser()
parser.feed(html)
required_ids = {
    "search-input", "filter-function", "filter-mode", "filter-location",
    "filter-experience", "filter-source", "sort-order", "jobs", "load-more",
    "error-state", "retry-load", "empty-state", "notices", "results-count",
}
assert not required_ids - parser.ids, f"missing UI ids: {sorted(required_ids - parser.ids)}"
for tag in ("main", "form", "article", "button", "a"):
    if tag == "article":
        assert 'document.createElement("article")' in js
    else:
        assert tag in parser.tags, f"missing semantic {tag}"

assert 'fetch("./data/jobs.json", { cache: "no-cache"' in js
assert "himalayas.app/jobs/api" not in js
assert "boards-api.greenhouse.io" not in js
assert "api.lever.co" not in js
assert 'apply.target = "_blank"' in js
assert 'apply.rel = "noopener noreferrer"' in js
assert "textContent" in js and "innerHTML" not in js
assert "aria-live=\"polite\"" in html
assert "@media (max-width: 720px)" in css
assert "prefers-reduced-motion" in css
assert sum((ROOT / name).stat().st_size for name in ("index.html", "styles.css", "app.js")) <= 100_000

assert fixture["schema_version"] == "1.0"
assert len(fixture["jobs"]) >= 2
assert all(job["id"].startswith("fixture:") for job in fixture["jobs"])
assert any(job["function"] == "Marketing" for job in fixture["jobs"])
assert any(job["function"] != "Marketing" for job in fixture["jobs"])
assert any(job["posted_at"] is None for job in fixture["jobs"])
assert any(job["salary"]["min"] is None for job in fixture["jobs"])
assert any(source["status"] != "ok" for source in fixture["sources"])

print("Static UI contract checks passed.")
