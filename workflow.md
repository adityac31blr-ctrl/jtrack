# Jobs Radar - Orchestrator and Three-Agent Workflow

**Version:** 1.0  
**Applies to:** An orchestrator coordinating exactly three specialized agents: UI/UX, Research, and Data Quality.  
**Primary objective:** Retrieve live, publicly listed jobs via permitted open/read-only APIs, normalize into JSON, quality-check, and display them in a lightweight static frontend.  
**Canonical UI and data contract:** [`frontend-design.md`](./frontend-design.md), especially section 5.

> **Orchestrator operating instruction:** Execute the stages below, enforce handoff contracts, block low-quality or unlicensed data, and publish only the QA-approved `data/jobs.json`. Never fabricate open jobs, hiring companies, salary, location eligibility, or freshness.

## 1. Implementation target and boundaries

- **Frontend:** `index.html`, `styles.css`, `app.js`; zero frontend framework dependencies.
- **Data pipeline:** Python standard library is sufficient (`urllib.request`, `json`, `datetime`, `html`, `re`, `hashlib`, `pathlib`); optionally use a maintained HTTP library if already available.
- **Storage:** JSON artifacts in a repository; no SQL/NoSQL database in MVP.
- **Deployment:** static hosting with scheduled pipeline / CI. Default schedule: once daily, not on each page load.
- **Geography:** India-based roles and remote roles explicitly eligible for Indian applicants. Global coverage can be added through a config change.
- **Functions:** all MBA/business functions; prioritize Marketing, Growth, Digital Marketing, Brand, Sales, Business Development, Product Marketing, and Market Research.
- **No credentials for MVP:** use keyless endpoints. Future paid/keyed sources must keep keys in server-side secrets.
- **No automated applications, candidate messages, account creation, login bypass, private-page scraping, or personal data collection.**

## 2. Ownership: who does what

| Agent | Sole ownership | Inputs | Outputs | Must not do |
|---|---|---|---|---|
| **Research Agent** | Discover and fetch permitted public job data; map provider-specific fields; attach provenance | `pipeline/sources.json`, permitted API docs, prior run manifest | `staging/raw/*.json`, `staging/research_jobs.json`, `reports/research_report.json` | Claim data is independently verified; publish to UI; invent missing data |
| **Data Quality Agent** | Validate schema, India eligibility, URLs, availability, timestamps, duplicates, classification, and scoring | Research outputs, `frontend-design.md`, previously published snapshot | `staging/validated_jobs.json`, `reports/qa_report.json`, `reports/rejected_jobs.json` | Change source facts without an audit trail; publish directly; guess salary or experience |
| **UI/UX Agent** | Design and implement responsive job-board view against approved schema | `frontend-design.md`, `staging/validated_jobs.json` or safe fixtures | `index.html`, `styles.css`, `app.js`, `reports/ui_test_report.md` | Call third-party job APIs from browser; bypass QA; change original apply links |
| **Orchestrator** | Schedule, dispatch, check gates, request approval, and atomically publish | All handoffs and reports | `data/jobs.json`, `reports/run_manifest.json`, deployment decision | Directly alter facts to make tests pass; deploy blocked runs |

The orchestrator may have the UI/UX Agent build the interface **in parallel** with the Research Agent against the agreed JSON schema. Final end-to-end UI testing must wait for QA-approved data.

## 3. Open API connectors and source policy

| Provider | Supported read endpoint | Implementation detail | Critical constraint |
|---|---|---|---|
| Himalayas | `GET https://himalayas.app/jobs/api/search?q=marketing&country=IN&sort=recent&page=1` | Iterate configured search keywords and page numbers; stop when a page has no jobs; dedupe by `guid`. Response has `jobs`. | API data updates roughly daily; country may include worldwide roles. Check actual location/timezone eligibility. `applicationLink` must be used **unchanged**; visible attribution required. API is not browser-CORS enabled. |
| Greenhouse | `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true` | Iterate **verified employer-specific** board tokens from `sources.json`; response has `jobs`. | Do not guess tokens. API provides public published postings; original descriptions can contain HTML. |
| Lever | `GET https://api.lever.co/v0/postings/{site}?mode=json` | Iterate **verified employer-specific** site IDs; handle `skip` and `limit` if needed; JSON response is an array. | Preserve provider-supplied apply/hosted URLs. Query only the public postings endpoint. |

**Source setup:** In `pipeline/sources.json`, include keywords (e.g., `marketing`, `growth marketing`, `sales`, `business analyst`, `finance`, `human resources`, `operations`) and arrays `greenhouse_boards` and `lever_sites`. The default arrays may start empty; the Research Agent must discover/verify genuine public careers-page slugs before adding them and record their documentation/careers URL. Never infer that a company uses a given ATS from its name alone.

**Provider compliance:** Display source attribution. Use the original apply link dictated by the provider, avoid passing a provider's job feed to downstream third-party aggregators, remove known-expired jobs, avoid aggressive polling, and respect rate limits / `429` + `Retry-After`. Himalayas explicitly permits display on sites/apps you operate but restricts syndication to other boards/aggregators. Review each provider's current terms prior to a production launch. Do not publish a public third-party redistribution feed.

**Sources:**
- https://himalayas.app/docs/remote-jobs-api
- https://docs.greenhouse.io/job-board
- https://github.com/lever/postings-api

## 4. Required handoff contracts

### A. Research output: `staging/research_jobs.json`

```json
{
  "run_id": "2026-11-14T08-00-00Z",
  "fetched_at": "2026-11-14T08:00:00Z",
  "jobs": [
    {
      "source_key": "himalayas",
      "source_job_id": "API-RETURNED-ID",
      "raw_payload_ref": "staging/raw/himalayas-page-1.json",
      "title": "Raw API title",
      "company": "Raw API company",
      "location_raw": "Raw API location or restrictions",
      "description_raw": "Raw text or HTML",
      "application_url_raw": "https://example.com/source-given-link",
      "source_url_raw": "https://example.com/source-given-link",
      "published_raw": null,
      "expires_raw": null,
      "fetched_at": "2026-11-14T08:00:00Z"
    }
  ]
}
```

This is a **structural example only**, not a real job. Real runs require API-returned IDs and URLs. The Research Agent must preserve provider-specific fields that support provenance, remote eligibility, compensation, and source-specific date semantics, even if those fields do not appear in the abbreviated example.

### B. QA output: `staging/validated_jobs.json`

Exactly follows the `data/jobs.json` contract in `frontend-design.md` (including `schema_version`, `sources`, `stats`, and `jobs`). The QA Agent populates `stats` from the accepted jobs only. **Never place demo/example records into `validated_jobs.json`.**

### C. Quality report: `reports/qa_report.json`

```json
{
  "run_id": "2026-11-14T08-00-00Z",
  "decision": "pass",
  "input_records": 120,
  "accepted_records": 100,
  "rejected_records": 20,
  "duplicate_records": 8,
  "warning_records": 4,
  "source_failures": [],
  "blockers": [],
  "warnings": [],
  "changes_since_previous": { "added": 12, "removed": 4 },
  "validated_file": "staging/validated_jobs.json"
}
```

All counts are examples; compute actual run values. Allowed decisions: `pass`, `warn_requires_approval`, `block`.

### D. UI report: `reports/ui_test_report.md`

Record: browser/viewport checks, JSON-load test, search/filter/sort, external link behavior, stale banner, zero-results state, accessibility quick checks, and remaining known issues.

## 5. Orchestrator state machine

```text
INIT
  |
  v
CONFIG_VALIDATED
  |-------------------------------|
  v                               v
RESEARCH_RUNNING                 UI_SCAFFOLD_RUNNING
  |                               |
  v                               |
RESEARCH_COMPLETE                 |
  |                               |
  v                               |
QA_RUNNING                        |
  |                               |
  +--> QA_BLOCKED --> retain prior snapshot + alert human
  |
  +--> QA_WARNED --> HUMAN_REVIEW --> approve / reject
  |
  v
QA_PASSED ------------------------|
  |
  v
UI_INTEGRATION_TEST
  |--> FAILED --> UI_FIX --> retest
  v
READY_TO_PUBLISH
  |
  v
ATOMIC_PUBLISH --> DEPLOYED --> RUN_REPORTED
```

**Hard dependency:** Research -> QA -> Publish. UI scaffold may be parallel; UI's final tests require validated JSON. No agent can self-approve a QA block or human-review condition.

## 6. Detailed execution sequence

### Step 0 - Validate config and source eligibility (Orchestrator)

1. Read `frontend-design.md`, `workflow.md`, and `pipeline/sources.json`.
2. Confirm each source has a verified endpoint, permitted use, request budget, and attribution handling.
3. Confirm scope parameters, previous successful snapshot, and output directories.
4. Create `run_id` and `reports/run_manifest.json` containing run start time, code version, and config hash (not secrets).
5. Stop and request a source-policy review if API terms materially changed.

**Gate:** Valid config and at least one enabled, policy-approved source.

### Step 1 - Gather jobs (Research Agent)

1. Query Himalayas using configured role keywords, `country=IN`, and `sort=recent`; page with `page=1,2,...` until `jobs=[]` or the configured request/record cap. Deduplicate `guid` across pages and search terms. Do not use its deprecated browse `offset` parameter if the browse endpoint is used later; use `nextCursor` instead.
2. Query each configured Greenhouse and Lever employer board with their documented public read endpoints; implement pagination where applicable.
3. Respect response codes: `200` parse; `404` mark board invalid; `429` honor `Retry-After`; `5xx` bounded exponential backoff (up to 3 attempts); parse/schema failures go into source errors.
4. Record original source ID, raw URL, source attribution, fetch timestamp, location/timezone restrictions, original timestamps, compensation fields, and original job text. Save individual provider payloads to `staging/raw/` for audit only; do not publish them.
5. Map source fields into a candidate unified structure, keeping missing values as `null`/`unknown` rather than guessing.
6. Write `staging/research_jobs.json` plus `reports/research_report.json` (request count, failures, jobs per source, paging truncation, and links to official docs).

**Gate:** At least one successful API response, explicit partial-failure accounting, no synthetic jobs. Zero jobs is valid if real responses confirm zero; otherwise classify as source failure, not verified emptiness.

### Step 2 - Validate and enrich deterministically (Data Quality Agent)

1. **Provenance:** Require source key, real API-returned job ID, source name, title, company, valid original apply URL, and last-checked time. Reject missing mandatory values.
2. **Status:** Exclude known closed jobs, explicit expired jobs, and placeholders. Being present in a feed means `source_listed`, not employer-confirmed live recruitment.
3. **India eligibility:** For explicit India locations accept when grounded; for Himalayas remote roles, require `locationRestrictions` to be empty (worldwide) or include India, **and** `timezoneRestrictions` to be empty or compatible with UTC+05:30. If uncertain, set `india_eligible=null` and hold for review rather than representing it as true.
4. **Sanitization:** Convert HTML descriptions to short plain text; remove tags/scripts and normalize whitespace; escape text on rendering. Do not erase meaningful role text. URLs must be absolute HTTPS and use permitted schemes/domains.
5. **Dates/salary:** Convert documented provider timestamps correctly (Himalayas `pubDate` is the most recent update and must not be silently called original posting date); preserve uncertain `posted_at=null`. Keep provider currency and pay period; check `min <= max` when both exist.
6. **Duplicates:** Exact repeats of `(source_key, source_job_id)` are merged deterministically. Exact repeated canonical URLs may be flagged; same company/title/location across different sources is only a *possible duplicate* and should not erase source-specific compliance/link obligations.
7. **Classification:** Use a fixed keyword rulebook for business functions. Marketing priority is an explainable ranking hint, **not** a claim of campus eligibility. Example score: title marketing match +30, department/category match +25, explicitly entry/associate/intern +15, India eligibility +15, recent confirmed date +10, direct employer career feed +5; clamp to 0-100. Do not award points for unknown properties.
8. **Coverage:** Track jobs per source, accepted/rejected counts, missing-field rates, changes vs last good run, and API failures.
9. **Quality gates:** `block` on malformed schema, invalid JSON, noncompliant link use, fabricated records, zero verifiably successful sources, or failed essential tests. `warn_requires_approval` on suspicious >40% drop in accepted listings vs last run, partial source outage materially affecting the feed, or unusually high (>15%) rejection rate. Otherwise `pass`.
10. Write `staging/validated_jobs.json`, `reports/qa_report.json`, and `reports/rejected_jobs.json` with reason codes and original provider IDs.

**Gate:** A machine-readable QA decision and a snapshot meeting `frontend-design.md` schema. A warning requires named human approval; a block cannot publish.

### Step 3 - Build and test the UI (UI/UX Agent)

1. Implement `index.html`, `styles.css`, `app.js` against `frontend-design.md`; no build system.
2. Fetch `./data/jobs.json` from the same origin; a local preview may **temporarily** point to `staging/validated_jobs.json`, but production always points to `data/jobs.json`.
3. Render external descriptions as text only, never provider HTML; display source attribution and unmodified apply URLs.
4. Add search, combined filters, marketing-priority/recent sort, card pagination, error/empty states, stale timestamp warning, and accessible keyboard controls.
5. Test on a small safe fixture containing remote, hybrid, unknown salary/date, marketing/nonmarketing, empty results, API-partial, and stale data scenarios. Fixtures must remain test-only.
6. Run an integration test against QA-approved real data; save `reports/ui_test_report.md`.

**Gate:** UI tests pass with zero dummy records appearing in deployed production data.

### Step 4 - Review, publish, and report (Orchestrator)

1. Read QA decision and UI test report.
2. **First launch:** require a human to approve the source list, attribution text, India eligibility logic, and public deployment. **Future clean daily refreshes:** permit automatic publication when QA=`pass` and UI integration checks pass. Require human reapproval for new source, changed source terms, modified ranking policy, or QA=`warn_requires_approval`.
3. Publish via safe atomic write: write `data/jobs.json.tmp`, validate JSON/schema one last time, then replace `data/jobs.json`. Never expose `staging/raw/` publicly.
4. Trigger the static-site deployment; confirm the published page loads the latest approved schema and sample apply links still point to original providers.
5. Save `reports/run_manifest.json` with final state, sources read, counts, QA decision, approval reference if required, artifact checksums, published UTC timestamp, and errors.
6. On failed runs, **keep the last good snapshot** and log failure; the frontend's age-based stale warning must make the age visible. Never silently overwrite with empty/invalid data.

**Gate:** Source terms satisfied, QA passed/approved, UI tests passed, and atomic data publish succeeded.

## 7. Minimal acceptance commands (illustrative implementation contract)

```bash
# From repository root (run on a machine with network access)
python pipeline/fetch_jobs.py --config pipeline/sources.json --out staging/research_jobs.json
python pipeline/validate_jobs.py --in staging/research_jobs.json --out staging/validated_jobs.json --report reports/qa_report.json

# Orchestrator checks QA before copying/atomically publishing validated output.
python -m json.tool staging/validated_jobs.json > /dev/null
python -m http.server 8000
```

These commands define expected CLI interfaces for the agents **to implement**; they are not claims that these Python scripts already exist. The orchestrator must not treat `json.tool` alone as a schema or quality check.

### Automated checks to implement

```text
[ ] Source responses are real and documented, with fetch timestamps.
[ ] Raw API credentials or private candidate details are never committed.
[ ] Every approved job has the schema's required fields.
[ ] IDs unique; URLs HTTPS; no dead placeholder/example records.
[ ] Himalayas applicationLink remains unchanged; source credit visible.
[ ] Known closed/expired roles excluded.
[ ] Remote India eligibility is evidenced, not assumed.
[ ] All counts and scores are deterministically computed and reproducible.
[ ] Search/filters/sort/Load more operate on approved JSON.
[ ] Snapshot timestamp, partial outage, and stale-data states render.
[ ] No block/warn condition bypasses its required gate.
[ ] Publication is atomic; previous good file survives failures.
```

## 8. Run modes and escalation

| Mode | Trigger | Action | Human approval |
|---|---|---|---|
| `bootstrap` | First setup | Verify sources, write static UI, fetch jobs, QA, preview, deploy | Required before first public launch |
| `refresh` | Daily schedule/manual run | Research -> QA -> conditional publish | Not required if all checks pass and policy/config unchanged |
| `ui_change` | New design/filter request | UI/UX update -> fixture tests -> real-data test | Required for changes affecting source attribution or apply behavior |
| `source_change` | Add/remove/modify an API connector | Research probe -> provider terms review -> QA regression | Required |
| `incident` | QA block, suspicious coverage loss, policy issue | Do not publish; preserve last-good snapshot; alert owner | Required to unblock |

**Failure notification:** Report which source failed, last successful refresh time, published feed age, accepted job count, and the exact human decision needed. A source API being unavailable must not be described as zero available jobs.

## 9. Copy-ready agent dispatch prompts

### Research Agent

> You are the Research Agent for Jobs Radar. Read `workflow.md` section 3 and the canonical schema in `frontend-design.md`. Query only approved public read-only endpoints in `pipeline/sources.json`. Respect paging, rate limits, published terms and India eligibility metadata. Save original payload references, stable source IDs, and original apply links. Produce `staging/research_jobs.json` and `reports/research_report.json`. Treat missing values as unknown. Never fabricate a job or publish a frontend snapshot.

### Data Quality Agent

> You are the Data Quality Agent for Jobs Radar. Review `staging/research_jobs.json` against the canonical `frontend-design.md` data contract and `workflow.md` section 6 Step 2. Validate sources, job IDs, URLs, dates, India eligibility, expiry, duplicates, HTML safety, functions and marketing scoring. Record all rejected IDs and reasons. Produce `staging/validated_jobs.json`, `reports/qa_report.json`, and `reports/rejected_jobs.json`; return `pass`, `warn_requires_approval`, or `block`. Never self-approve or change source links to make a record pass.

### UI/UX Agent

> You are the UI/UX Agent for Jobs Radar. Implement the lightweight responsive interface specified in `frontend-design.md`, using only `index.html`, `styles.css`, and `app.js`. Read the approved JSON schema, but do not fetch job-source APIs in browser code. Display accurate job metadata and provider attribution, link out using approved original apply URLs, and implement search, filters, sorting, load-more, empty/error/stale states, and accessible navigation. Test with safe fixtures and with QA-approved data. Deliver `reports/ui_test_report.md` and do not publish unapproved jobs.

### Orchestrator decision instruction

> On each run: validate configuration; launch Research and UI scaffold (parallel if needed); require Research completion before Data Quality; require Data Quality pass or human-approved warning before publication; require UI integration tests; atomically publish approved JSON; report final status. If QA blocks, external source terms are unclear, or UI tests fail, preserve prior published data and escalate with evidence. Never apply to jobs or contact recruiters.

## 10. MVP completion criteria

The workflow is complete when (1) at least one actual public API responds, (2) the Research Agent extracts genuine listings and audit metadata, (3) the Data Quality Agent writes an accepted canonical JSON snapshot with a QA report, (4) the UI/UX Agent displays those genuine listings from `data/jobs.json` in a standalone static page, and (5) a failed refresh leaves the previous approved snapshot intact and visibly aging.
