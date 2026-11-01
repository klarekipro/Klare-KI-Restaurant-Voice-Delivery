# Task board

Completed: reproduce PR #2 from exact source; isolated venv install; baseline 5 tests; session-key hardening; cross-origin/Host guards; strict order-item validation and rollback; idempotent simulator submission; stable per-order contact snapshot; transactional transitions; Berlin delivery-day reports; negative/auth tests; real-process acceptance and restart; manual agent handoff protocol.

Remaining, priority order:
1. Browser acceptance at kitchen/courier mobile widths; test form/network errors, retry feedback and external navigation handoff using synthetic data.
2. Address correction UI scoped to order snapshots (CRM edits intentionally do not alter existing deliveries).
3. Stress concurrent editing/dispatch and idempotent retries; verify migration on a copied pre-hardening synthetic DB. Historical contact snapshots can only use current CRM data at migration time.
4. CSRF tokens in addition to browser Origin/Fetch-Metadata guards; login throttling, credential rotation and production session design before any pilot.
5. Resolve product/legal open questions, failed-delivery recovery UI, dependency upgrade/pinning across supported Python versions.

No permission to merge, deploy or connect real telephony. No human demo acceptance recorded yet.

Mission 04 completed: persistent runner, two real adapters, native/outer isolation probes, actual automatic Claude→Codex review cycle, controlled validators, operator controls, recovery tests and redacted evidence.
Remaining: actual browser/mobile acceptance; complete preserved simulator repair after provider capacity/inspection; live quota takeover after corrected parser; wider process-termination/race coverage. These remain distinct from the completed review cycle.
