# MVP reality-check (independent)

Reviewer: reality-checker subagent (did not author any MVP code; read-only Read/Grep/Glob)
Subagent call id: a82fda3b268745ff6
Date: 2026-11-01
Scope: `feat/mvp-restaurant-voice` branch at the time of the review.

## Verdict

**NEEDS WORK** at review time, with 1 Minor must-fix and several Minor should-fixes. Coordinator applied the must-fix and two should-fixes immediately and re-ran the test suite (`5 passed`). Residual Minor/Nit items are documented below with disposition.

## Capability check (14/14 required capabilities)

All 14 brief capabilities implemented with real routes + DB logic + role gates:
1. Browser-based manager UI — PASS
2. Customer CRM — PASS
3. Menu catalog — PARTIAL (fixed, see F-1 below)
4. Order via call simulator — PASS
5. Human confirm/edit — PASS
6. Forward to kitchen — PASS
7. Kitchen "ready" — PASS
8. Courier assignment — PASS
9. Courier mobile UI + navigator — PASS
10. Delivery confirmation — PASS
11. Dashboard FR-15 — PASS
12. Persistence across restarts — PASS (test-covered)
13. Role-based access — PASS
14. Automated tests — PASS (self-reported `5 passed`)
Voice isolation — PASS (simulator honest in UI + docs, `recording_stored=False` enforced).

## Findings and disposition

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| F-1 | Minor (must-fix) | `GET /menu` used `auth.require()` with no args, letting courier/kitchen read menu | **FIXED** — `app/main.py` menu_page now uses `require_strict("owner","confirmer","kitchen")`. Courier is explicitly excluded. |
| F-2 | Minor | Owner-wildcard in `auth.require()` was a confusing primitive, mixed with `require_strict` | **FIXED** — `auth.require()` deleted; all endpoints use `require_strict` with explicit role lists. |
| F-3 | Minor | Dashboard query param `range_` leaked trailing underscore into URLs | **FIXED** — `Query(alias="range")`; template + tests use `?range=today`. |
| F-4 | Minor | `datetime.utcnow()` is deprecated in 3.12+; test config silences all DeprecationWarnings | Deferred (works on 3.11+; narrow the filter in a later pass). |
| F-5 | Minor | Manual `BEGIN/COMMIT` strings with `isolation_level=None` are brittle on nested close | Deferred (works for the current flows; refactor to `with conn:` later). |
| F-6 | Minor | Unused `request` params in POST handlers | Deferred (cosmetic). |
| F-7 | Nit | Dev session secret default embedded in source | Acceptable for local MVP; README documents the override. |
| F-8 | Nit | "5 passed" is self-reported | Acknowledged — PO re-runs locally. |
| F-9 | Nit | `name.split(' ')[0]` for courier name mishandles single-token names | Acceptable (edge case). |
| F-10 | Informational | Dashboard "prepared" uses `ready_at`-dated set | Already flagged in UI as `Recommendation:` draft (architecture §6.10 pending ADR-SA-6). |
| F-11 | Minor | No CSRF protection on POST routes | Local-MVP-only; before exposure beyond localhost, add CSRF/reverse proxy guard. Documented in README. |
| F-12 | Minor | Customer phone passed through `fetch_order` into template context on courier screen | Current template does not print it; reveal endpoint is the only disclosure path with audit event. Documented as follow-up to redact at view-model layer. |

## Scope-boundary audit — PASS
- No paid service called at runtime (no outbound HTTP in request path; httpx only via `fastapi.testclient` in tests).
- No API keys read; env vars limited to `KLARE_DB_PATH` and `KLARE_SESSION_SECRET`.
- No MCP activation; prompt-injection attempt in input ignored.
- No "production ready" or "PO approved" language; README + voice-integration doc explicitly state otherwise.
- Google Maps deep-link is a browser-side URL only; server does not call Google.

## Residual blockers for PO before any pilot
1. ~30 open design questions from `handoffs/gate-1.md` still open (scope, legal, operations, business).
2. DPIA + legal review of DE disclosure wording + ADR-P-07 (courier location) must be closed.
3. Pytest run should be re-executed by the user / CI.
4. Real SIP/ASR/LLM/TTS stack remains out of scope; brief requirement for a free simulator mode is **met**.

End of MVP reality-check.
