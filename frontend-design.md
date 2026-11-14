# Jobs Radar - Lightweight Frontend Design

**Document type:** Build-ready UI/UX specification  
**Version:** 1.0  
**Goal:** Display currently listed jobs gathered from permitted public job APIs, normalized into one JSON file.  
**Default audience:** MBA/PGDM students and placement researchers in India, with marketing roles highlighted. Filters support all business functions.

## 1. MVP decision: static site, no application server

Build a responsive **single-page website using HTML, CSS, and vanilla JavaScript**. Serve a generated `data/jobs.json` file from the same origin as the website. Use Python only for scheduled API ingestion and validation, not for serving individual page requests.

```text
Public read-only job APIs
       |
       v
Research Agent (scheduled Python fetch and normalization)
       |
       v
Data Quality Agent (validate, classify, deduplicate)
       |
       v
 data/jobs.json (versioned, approved snapshot)
       |
       v
 index.html + styles.css + app.js (static hosting)
```

**Why:** No React, build tooling, backend server, user accounts, or database is needed for v1. A local static server and GitHub Pages, Cloudflare Pages, or Netlify are sufficient. Fetch API providers **server-side / during a build step**, not from the browser: the Himalayas API documents that browser cross-origin fetches are blocked.

**Explicitly out of scope for v1:** user logins, saved jobs synced across devices, one-click applications, résumé uploads, automated recruiter outreach, maps, social-media scraping, live websocket updates, and employer-specific custom application forms.

## 2. User goal and core user journeys

1. Open the page and immediately see recent listings plus when they were last checked.
2. Search by title, company, skill, or location.
3. Filter by business function, city/remote, work mode, entry level, and source.
4. Notice marketing-related roles first without hiding jobs in other functions.
5. Open the original posting and apply on the source's required destination.
6. Distinguish a listing present in a public API from a vacancy independently confirmed by an employer.

### Primary UI components

- **Header:** `Jobs Radar`, subtitle `Opportunities for MBA/PGDM students`, and an unobtrusive `Data updated: ...` timestamp.
- **Hero/search row:** prominent search box with placeholder `Search job title, company, skill, or city` and a `Clear` action.
- **Summary strip:** `Available listings`, `Marketing-related`, `Added in last 7 days`, `Sources reporting` (show counts only when computed from approved data).
- **Filter row:** dropdown/chips for Function, Work mode, Location, Experience, Source; `Reset filters`.
- **Job cards:** title, company, location, work mode, function, posted date if known, short description, optional salary, `View & apply` link, source attribution.
- **Results controls:** results count, sort selector (`Marketing priority`, `Most recent`), and `Load more` (12 cards at a time).
- **Alerts/empty states:** stale snapshot warning, source partially unavailable warning, retry state for JSON fetch failure, no-match state.
- **Footer:** data provenance and a note that job availability can change; check the original listing before applying.

### Desktop wireframe (illustrative)

```text
+-----------------------------------------------------------------------+
| Jobs Radar                       Jobs last checked: 14 Nov 2026       |
| Find your next opportunity                                           |
| [Search jobs, company, location...____________________] [Clear]       |
|                                                                       |
| [All jobs: 280] [Marketing: 92] [New: 34] [Sources: 3]               |
|                                                                       |
| Function v  Work mode v  Location v  Experience v  Source v  Reset    |
|                                                                       |
| Showing 1-12 of 280                       Sort: Marketing priority v  |
| +-------------------------------------------------------------------+ |
| | Growth Marketing Associate       Sample Co | Bengaluru / Hybrid  | |
| | Marketing  Entry level  Posted 2 days ago                        | |
| | Short, plain-text description ...                                 | |
| | Source: Employer careers                         [View & apply]   | |
| +-------------------------------------------------------------------+ |
| | Business Analyst ...                                              | |
| +-------------------------------------------------------------------+ |
|                              [Load more]                              |
+-----------------------------------------------------------------------+
```

The wireframe is **mock content only**; sample companies and counts must never be published as real jobs.

### Mobile behavior

At widths below 720px, show one-column cards and a compact, horizontally scrollable filter row or a single `Filters` expandable region. Put each `View & apply` link at the bottom of its card. Avoid sticky elements that hide content. No complex table layout.

## 3. Visual system

| Token | MVP value |
|---|---|
| Background | `#F8FAFC` |
| Surface | `#FFFFFF` |
| Main text | `#0F172A` |
| Secondary text | `#475569` |
| Brand/action | `#1D4ED8` |
| Border | `#E2E8F0` |
| Positive metadata | `#166534` |
| Warning metadata | `#92400E` |
| Font | System stack: `system-ui, -apple-system, Segoe UI, sans-serif` |
| Container | `max-width: 1120px; margin: auto; padding: 16px` |
| Radius | 10px cards, 8px inputs |
| Layout | CSS Grid/Flexbox; no component library |

Aim for strong spacing, readable labels, keyboard focus rings, and subdued metadata. Do not use the source provider's logos unless the provider permits them; readable source names are enough.

## 4. Exact MVP behavior

| Feature | Required behavior |
|---|---|
| Initial load | `fetch('./data/jobs.json', { cache: 'no-cache' })`; parse, validate top-level version, render cards. |
| Search | Case-insensitive across title, company, summary, skills, and location; 150-250ms debounce. |
| Filters | Applied in-browser; combined with logical AND; accessible labels for every control. |
| Default ordering | `marketing_priority_score` descending, then `posted_at` descending; null dates last. |
| Recent sorting | Use actual `posted_at`; never derive an invented posted date. |
| Pagination | Render first 12; `Load more` adds another 12 from the currently filtered list. |
| Apply action | External link to **unaltered** approved `application_url`; `target='_blank'` and `rel='noopener noreferrer'`. |
| Attribution | Each card displays `Source: <name>` linking to `source_url`; Himalayas must be visibly credited. |
| Expired/closed | Never render records with known expiry before `generated_at` or a closed status. |
| Stale data | When `generated_at` is older than 48h, show `Listings may be outdated - verify on source`. |
| Partial outage | When any source has a degraded/failed status, show a source coverage warning, not a misleading complete count. |
| Loading/error | Friendly loading skeleton/text, network error explanation and `Retry` to reload the JSON. |
| No results | `No listings match these filters` with an interactive reset. |

The frontend never fetches provider APIs directly, never collects applicant PII, and never claims every listed job is independently verified or guaranteed open.

## 5. Data contract: `data/jobs.json`

This is the **authoritative schema** for all three agents. The orchestrator may publish a new snapshot only after the Data Quality Agent approves it. Dates are UTC ISO-8601 strings or `null`. Salary and publication dates must never be guessed.

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-11-14T08:00:00Z",
  "scope": {
    "default_country": "IN",
    "include_india_eligible_remote": true,
    "marketing_priority": true
  },
  "sources": [
    {
      "key": "himalayas",
      "name": "Himalayas",
      "status": "ok",
      "fetched_at": "2026-11-14T07:55:00Z",
      "records_received": 1,
      "records_published": 1,
      "attribution_url": "https://himalayas.app"
    }
  ],
  "stats": {
    "total": 1,
    "marketing": 1,
    "new_last_7_days": 1,
    "sources_ok": 1
  },
  "jobs": [
    {
      "id": "himalayas:EXAMPLE-ID",
      "source_key": "himalayas",
      "source_job_id": "EXAMPLE-ID",
      "source_name": "Himalayas",
      "title": "Growth Marketing Associate - DEMO RECORD",
      "company": "Example Company (synthetic)",
      "function": "Marketing",
      "marketing_priority_score": 85,
      "location_text": "Remote - India eligible",
      "country": "IN",
      "india_eligible": true,
      "work_mode": "remote",
      "experience_level": "entry",
      "employment_type": "full_time",
      "salary": {
        "min": null,
        "max": null,
        "currency": null,
        "period": null
      },
      "posted_at": "2026-11-12T00:00:00Z",
      "expires_at": null,
      "summary": "Example placeholder. Replace only with a real sourced job.",
      "skills": ["Marketing"],
      "application_url": "https://example.com/placeholder-apply",
      "source_url": "https://example.com/placeholder-listing",
      "last_checked_at": "2026-11-14T07:55:00Z",
      "availability_status": "source_listed"
    }
  ]
}
```

**IMPORTANT:** The JSON example above is entirely illustrative, not a live job. Synthetic `EXAMPLE` records and `example.com` URLs are forbidden in production output.

### Field rules and enums

- **Required nonempty strings per job:** `id`, `source_key`, `source_job_id`, `source_name`, `title`, `company`, `function`, `location_text`, `application_url`, `source_url`, `last_checked_at`, `availability_status`.
- **Required booleans/numbers:** `marketing_priority_score` integer `0..100`; `india_eligible` boolean or null.
- `function` enum: `Marketing`, `Sales & BD`, `Finance`, `HR`, `Operations`, `Consulting`, `Product`, `Analytics`, `Other`.
- `work_mode`: `remote`, `hybrid`, `onsite`, `unknown`.
- `experience_level`: `intern`, `entry`, `mid`, `senior`, `unknown`.
- `employment_type`: `full_time`, `part_time`, `contract`, `internship`, `other`, `unknown`.
- `availability_status`: published records must be `source_listed`; never convert this into `employer_confirmed` without an actual employer confirmation.
- Dates: `posted_at` and `expires_at` are nullable UTC ISO-8601 strings. Treat update time as distinct from original publication time.
- Salary: optional numeric min/max, nullable three-letter currency and nullable pay period (`hourly`, `weekly`, `fortnightly`, `monthly`, `annual`). Do not mix currencies or salary periods or assume LPA.
- Text is plain text and short (recommended summary <= 280 characters). Strip HTML and scripts in the data pipeline; render text via `textContent`, not `innerHTML`.
- `application_url` and `source_url` must use HTTPS and come from the original API/provider; links are checked for syntactic validity but are not assumed safe from every external risk.
- `stats` are calculated from the **published** `jobs` array, never copied from a provider response.
- Source status values: `ok`, `partial`, `failed`. Source status is about the fetch, not an endorsement of each employer.

### Source-specific link policy

- **Himalayas:** set `application_url` to its `applicationLink` **unchanged**, and visibly credit/link the Himalayas listing or platform. Confirm India eligibility using location and timezone restrictions rather than assuming all remote jobs are globally open.
- **Greenhouse:** use the job's `absolute_url`, plus the actual employer/Greenhouse board attribution.
- **Lever:** use the published job's provided `applyUrl` / `hostedUrl` as appropriate; avoid constructing application URLs.
- If a job is reported by multiple sources, do not silently swap a provider's application URL for another source's URL. Prefer keeping separate compliant records until a deterministic, policy-safe deduplication rule is defined.

## 6. Hosting and file structure

```text
jobs-radar/
├── index.html                 # single page, semantic HTML
├── styles.css                 # 1 stylesheet
├── app.js                     # fetch + filtering + cards
├── data/
│   └── jobs.json              # only QA-approved data, no demo entries
├── pipeline/
│   ├── fetch_jobs.py          # implement per workflow.md
│   ├── validate_jobs.py       # implement per workflow.md
│   └── sources.json           # configured employer board slugs/queries
├── reports/                   # quality and research run reports
├── frontend-design.md
└── workflow.md
```

Local preview: `python -m http.server 8000` from the project directory, then open `http://localhost:8000`. Do not open the HTML via `file://` because browsers may block JSON fetches.

Deploy as a static site; a scheduled CI job (e.g., once daily) fetches API data, validates it, and commits/publishes an approved snapshot. Never expose API keys in `app.js` or `jobs.json`.

## 7. Performance and accessibility budgets

- No external UI framework, icon font, or CDN requirement.
- Target HTML + CSS + JS combined <= 100 KB uncompressed for MVP.
- Cap the published snapshot to the latest/relevant ~500 jobs initially; keep JSON <= 500 KB compressed where practical, and trim descriptions to summaries.
- Aim for first useful render under 2 seconds on normal broadband (performance target, not a guarantee).
- Use semantic `<main>`, `<form>`, `<article>`, `<button>`, and `<a>`; keyboard-compatible controls, visible focus styles, and contrast-compliant text.
- Provide an `aria-live='polite'` region for result-count changes; never rely on color alone for job status.
- Do not inject unsanitized external descriptions or URLs into the DOM.

## 8. Definition of done: frontend acceptance checks

1. A clean checkout can be opened using `python -m http.server 8000` with no `npm install`.
2. The page works at ~360px and desktop widths without horizontal page overflow.
3. It loads a **real QA-approved** `data/jobs.json` and renders cards, verified attribution, and correct apply links.
4. Search, all filters, sorting, Reset, and Load more work together.
5. Null salary or date displays `Not disclosed` or is omitted; no fabricated values.
6. Failed fetch, empty feed, partially failed sources, and a snapshot older than 48h have clear UI states.
7. Zero applications, messages, or recruiter contact actions occur from this frontend.
8. Browser console contains no errors; buttons and links work with keyboard navigation.

## 9. Verified public API references (review terms before deployment)

- Himalayas public jobs API and usage terms: https://himalayas.app/docs/remote-jobs-api
- Greenhouse read-only public Job Board API: https://docs.greenhouse.io/job-board
- Lever published job postings API: https://github.com/lever/postings-api

These APIs **do not constitute all Indian job vacancies**. Himalayas is remote-focused, while Greenhouse and Lever require a curated list of employer board identifiers. Do not scrape private platforms or claim complete market coverage.
