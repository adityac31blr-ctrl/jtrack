# Source policy

Jobs Radar uses only public, read-only endpoints whose provider contract supports the display and attribution model.

## Himalayas

- Endpoint: `GET https://himalayas.app/jobs/api/search`
- Status: enabled
- Authentication: no key required for the public allowance
- Required behavior: use `applicationLink` unchanged, show visible Himalayas credit, fetch at most daily, and honor `429 Retry-After`
- Eligibility evidence: `locationRestrictions` and `timezoneRestrictions`; remote work is not assumed to include India
- Date semantics: `pubDate` is treated as a provider update time, not an invented original posting date
- Documentation: https://himalayas.app/docs/remote-jobs-api

## Greenhouse

- Endpoint template: `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`
- Status: connector implemented, disabled until employer board tokens are verified from official careers pages
- Required behavior: preserve `absolute_url` and identify the employer careers source
- Documentation: https://docs.greenhouse.io/job-board.html

## Lever

- Endpoint template: `GET https://api.lever.co/v0/postings/{site}?mode=json`
- Status: connector implemented, disabled until employer site IDs are verified from official careers pages
- Required behavior: preserve provider `applyUrl` and `hostedUrl`
- Documentation: https://github.com/lever/postings-api

No private pages, authentication bypasses, guessed board identifiers, applicant data, automated applications, or downstream job-feed syndication are permitted. A new or changed source requires policy review and human approval before publication.
