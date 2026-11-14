# Jobs Radar

Jobs Radar is a lightweight, static job board for MBA/PGDM students and placement researchers in India. It displays only records that pass deterministic provenance, eligibility, link, status, date, duplication, and schema checks.

## Local checks

```bash
python -m unittest discover -s tests -v
python pipeline/fetch_jobs.py --config pipeline/sources.json --out staging/research_jobs.json
python pipeline/validate_jobs.py --in staging/research_jobs.json --out staging/validated_jobs.json --report reports/qa_report.json
python -m http.server 8000
```

Open `http://localhost:8000`. The browser reads only `data/jobs.json`; it never calls provider APIs.

## Release controls

- Raw responses remain in ignored staging storage.
- `validate_jobs.py` returns `pass`, `warn_requires_approval`, or `block`.
- `publish_jobs.py` refuses every decision except `pass` and replaces the snapshot atomically.
- The scheduled workflow collects a candidate snapshot as an artifact. It does not commit or deploy refreshed data automatically.
- The initial public launch and every source-policy change require human approval.

The configured source is the public [Himalayas Remote Jobs API](https://himalayas.app/docs/remote-jobs-api). Greenhouse and Lever support is implemented but disabled until specific employer board identifiers and their careers URLs are verified. Source availability does not guarantee that a role remains open; always verify on the original listing.

## GitHub Pages

After the bootstrap pull request is approved and merged, set **Settings -> Pages -> Build and deployment -> Source** to **GitHub Actions**. The Pages workflow then deploys the static repository on pushes to `main`.

