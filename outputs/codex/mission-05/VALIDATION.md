# Mission 05 operator and validation record

Source: PR4, 96ee67214f7e92cd212705e8942d42accb665d04. Separate feature worktree: restaurant-takeover-hardening. No other application worktree was modified.

## Preserved original

Historical mission 92bd71a914ab is unchanged and remains held in its original store. Its template SHA-256 is still f8b73c12c939aaea3e547335b3ff6572474548fe871a2c35ad37923d142f587a. A private pre-recovery archive includes the template, binary Git diff, manifest and SQLite backup. Recovery imports use read-only SQLite, separate branches/worktrees and explicit recorded Mission 05 authorization; they do not clear the original approval hold. Private databases, snapshots and credentials are excluded from Git.

## Real CLI coverage

Actual installed versions checked: Claude 2.1.119, Codex 0.166.0. Isolation/auth/tool policies remain in place.

- The source response is a historical REAL Claude process with structured API429, not an injected error. No new Claude CLI request was made in Mission 05 to exhaust quota. The importer transfers the recorded unfinished task automatically.
- First live Codex continuation (3f815e309965) stopped at a DOM-test fixture defect: standard createElement/replaceChildren were missing from the stub. That run and dirty worktree are retained. The fixture was corrected; no failed result was promoted.
- Second continuation (2423183b75aa) passed checks but its separate real Codex review found that edits before retry changed the payload under the same key. Runner correctly rejected the review and ended FAILED at its configured retry limit.
- Explicitly authorized bounded follow-up 46ae6de714e3 automatically read/forwarded that structured finding. A real Codex process repaired the template; a second fresh Codex process independently reviewed it. Both exited 0; runner external pytest, real-process HTTP acceptance and actual-template JavaScript behavior checks passed. Mission COMPLETED. Same-provider review is explicitly recorded because Claude was unavailable; it is not a claimed live Claude cross-review.
- Separate-process resume retained exactly two final-run attempts. Verified repair source commit: 1587f11 (full SHA in live-recovery.json). Published template bytes match the verified worktree exactly.

Early importer versions used wider 600s/4 fields; this was corrected to inherit the original 360s/3 caps. Recorded elapsed time/attempt counts did not exceed the inherited caps. Final follow-up used 360s/3 and no retry-budget reset of the failed source mission.

## Automated coverage and limits

36 runner tests cover validation-before-checkpoint, failed/untrusted/symlink holds, content changes during/after validation, committed-tree identity, reverse Codex→Claude continuation, unique handoffs, import/follow-up idempotency and restart at outcome/preservation/validation/Git/SQLite/queue/finalization boundaries. A separate OS process exits with code 73 between Git commit and SQLite acknowledgement; reopening the store resumes without duplicate commit or provider action and retains the file bytes. Provider failure/limit responses in those fault tests are simulated adapters; reverse direction was not exercised with a new real Claude request.

22 restaurant regressions pass. scripts/local_acceptance.py passes through actual loopback HTTP and application restart. check_simulator.cjs executes actual template JavaScript with a DOM/fetch stub, including uncertain-response retries with changed form fields, duplicate clicks, reset and new-key/new-payload submission. It is not browser/mobile acceptance.

Full delivery classifications and validation receipts were added after the live run and checked in regression tests; the live evidence retains original checks/results rather than fabricating retroactive receipts. Unknown in-flight children, changed fingerprints, out-of-scope work and failed safety checks still require explicit approval. New arbitrary dependency installation, force push, auto merge, deployment and paid services are not implemented.

Next: independent security/recovery review, real browser/mobile acceptance, and wider validation/error UX (e.g. known input rejection recovery) before a public demonstration or pilot. Existing local-only demo credential restrictions still apply.
