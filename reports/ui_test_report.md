# UI test report

## Scope

- Interface scaffold: `index.html`, `styles.css`, and `app.js`
- Fixture: `tests/fixtures/data/jobs.json`
- Deterministic checks: `python tests/static_check.py`
- Browser checks: `node tests/ui_test.mjs` against a server whose `data/jobs.json` is the fixture

The fixture is synthetic and test-only. It must never be copied to production `data/jobs.json`.

## Results

- Static HTML structure and required controls: pass
- Same-origin `./data/jobs.json` fetch and absence of provider API calls: pass
- Text-only rendering and external-link safety attributes: pass
- Frontend size budget: pass (HTML, CSS, and JavaScript total under 100 KB)
- Fixture coverage for marketing/nonmarketing, remote/hybrid, null date/salary, partial source, and stale snapshot: pass
- JavaScript syntax check: pass
- Fixture JSON parse: pass
- HTTP same-origin load: pass
- Chromium mobile/desktop interaction run: pass in the supported Playwright container at 360 x 800 and 1280 x 900
- Approved real-data integration: pass against the Data Quality-approved 237-record snapshot at both viewports

## Browser suite coverage

The committed Playwright suite checks 360 px and 1280 px viewports, search, zero-results reset, function filtering, stale and partial warnings, safe external links, console errors, and horizontal overflow. Run it in CI after installing Playwright Chromium.

## Known issues

No application defect was found by the completed checks. The approved snapshot is integrated and the browser suite passes; first-launch publication remains gated only on user approval.
